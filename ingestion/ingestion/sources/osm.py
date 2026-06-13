"""AOI refinement for solar sites — replace the capacity-buffer guess with a real footprint.

Priority per site:
  1. OSM ground-mounted-solar polygon (the actual array outline)        aoi_method=osm_polygon
  2. MaStR InAnspruchGenommeneFlaeche (reported area, hectares) buffer   aoi_method=mastr_area
  3. (left as-is — keep the existing capacity buffer)

Tighter AOIs measure the array instead of surrounding fields, which sharpens detection
(fewer false positives) and frames the satellite chips on the real panels. After running
this, re-backfill GEE on the changed sites (without --skip-existing) and re-detect.
"""

from __future__ import annotations

import io
import logging
import zipfile
from collections.abc import Iterable
from pathlib import Path

import httpx
import pandas as pd
from app.config import get_settings
from shapely import STRtree
from shapely.geometry import MultiPolygon, Point, Polygon

from ingestion import geo
from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

log = logging.getLogger("ingestion")

OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_UA = {"User-Agent": "gridwatch/0.1 (research; construction monitoring)"}
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="DE"][admin_level=2]->.de;
(
  way["landuse"="solar"](area.de);
  way["power"="plant"]["plant:source"="solar"](area.de);
);
out geom;
"""
CONTAIN_BUFFER = 0.012  # ~1.3 km bbox prefilter
NEAR_DEG = 0.009  # ~1 km: nearest polygon still counts as the same site

SOLAR_CSV = "bnetza_mastr_solar_raw.csv"
C_ID = "EinheitMastrNummer"
C_AREA = "InAnspruchGenommeneFlaeche"  # hectares
C_CAP = "Nettonennleistung"
C_LAGE = "Lage"


def _osm_polygons() -> list[Polygon]:
    r = httpx.post(OVERPASS, data={"data": QUERY}, timeout=240, headers=OVERPASS_UA)
    r.raise_for_status()
    polys: list[Polygon] = []
    for el in r.json()["elements"]:
        geom = el.get("geometry")
        if not geom or len(geom) < 4:
            continue
        ring = [(p["lon"], p["lat"]) for p in geom]
        try:
            poly = Polygon(ring)
            if poly.is_valid and poly.area > 0:
                polys.append(poly.simplify(0.0001))
        except Exception:  # noqa: BLE001 — skip malformed rings
            continue
    return polys


def _area_map(mastr_ids: set[str]) -> dict[str, float]:
    """mastr_id -> reported area in hectares (ground-mounted >=5MW solar)."""
    path = Path(get_settings().mastr_zip_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    z = zipfile.ZipFile(path)
    member = next(n for n in z.namelist() if n.endswith(SOLAR_CSV))
    out: dict[str, float] = {}
    with z.open(member) as f:
        for chunk in pd.read_csv(
            io.TextIOWrapper(f, encoding="utf-8"),
            usecols=lambda c: c in (C_ID, C_AREA, C_CAP, C_LAGE),
            chunksize=200_000,
            low_memory=False,
        ):
            cap = pd.to_numeric(chunk[C_CAP], errors="coerce")
            sel = chunk[(cap >= 5000) & (chunk[C_LAGE] == "Freifläche")]
            for row in sel.to_dict("records"):
                sid = str(row[C_ID])
                if sid in mastr_ids:
                    area = pd.to_numeric(row.get(C_AREA), errors="coerce")
                    if pd.notna(area) and area > 0:
                        out[sid] = float(area)
    return out


@register
class OSMSource(BaseSource):
    meta = SourceMeta(
        name="osm",
        description="Refine solar AOIs from OSM polygons + MaStR reported area",
        cadence="monthly",
        requires_credentials=(),
        phase=2,
        site_scoped=True,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        # the runner subsets by --technology; treat all provided sites as candidates
        polygons = _osm_polygons()
        tree = STRtree(polygons)
        areas = _area_map({s.mastr_id for s in ctx.sites if s.mastr_id})

        for s in ctx.sites:
            if s.lat is None or s.lon is None:
                continue
            pt = Point(s.lon, s.lat)
            poly = self._match(tree, polygons, pt)
            if poly is not None:
                yield {
                    "id": str(s.id),
                    "geom_wkt": MultiPolygon([poly]).wkt,
                    "aoi_method": "osm_polygon",
                }
            elif s.mastr_id in areas:
                side = (areas[s.mastr_id] * 10_000) ** 0.5  # hectares -> m2 -> square side
                yield {
                    "id": str(s.id),
                    "geom_wkt": geo.square_wkt(s.lon, s.lat, side),
                    "aoi_method": "mastr_area",
                }

    @staticmethod
    def _match(tree: STRtree, polygons: list[Polygon], pt: Point) -> Polygon | None:
        idxs = tree.query(pt.buffer(CONTAIN_BUFFER))
        best, best_d = None, 1e9
        for i in idxs:
            poly = polygons[int(i)]
            if poly.contains(pt):
                return poly
            d = poly.distance(pt)
            if d < best_d:
                best, best_d = poly, d
        return best if best is not None and best_d <= NEAR_DEG else None

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[RawRecord]:
        return raw

    def load(self, records: Iterable[RawRecord], db: Client) -> LoadStats:
        records = list(records)
        for r in records:
            db.table("sites").update(
                {"geom": f"SRID=4326;{r['geom_wkt']}", "aoi_method": r["aoi_method"]}
            ).eq("id", r["id"]).execute()
        osm = sum(1 for r in records if r["aoi_method"] == "osm_polygon")
        area = sum(1 for r in records if r["aoi_method"] == "mastr_area")
        log.info("AOI refined: osm_polygon=%d mastr_area=%d", osm, area)
        return LoadStats(loaded=len(records))
