"""Zoning and land-use plans into the lake (docs/research/zoning.md, docs/DATA_SOURCES.md).

One lake dataset `zoning`, table `zones`, partitioned by source. Every row keeps the source's
own zone code and label, the plan it belongs to, the plan's dates and document link, and all of
the source's attributes verbatim (`attributes`, JSON). `class` is a harmonised use class read
from a documented lookup of each source's own codes (CLASSES below); a code the lookup does
not name stays `other`, with the source label kept. Nothing is estimated or generalised: the
geometry is the publisher's, reprojected to EPSG:4326 by the publisher's own service.

Sources (all open, no key):
  fr_gpu        France, Géoportail de l'Urbanisme, every PLU / PLUi / carte communale zone
  ie_myplan     Ireland, MyPlan generalised zoning (Department of Housing), current + expired
  dk_plandata   Denmark, Plandata: kommuneplanrammer and lokalplaner (adopted), incl. the
                solar and wind local plans
  fi_helsinki   Finland, Helsinki detailed plans in force (plan index)
  us_ca         US, California statewide zoning (north and south)
  gb_england    England, planning.data.gov.uk: local plans and their boundaries, green belt,
                housing allocations, development policy areas, conservation areas, article 4
                directions, brownfield land, tree preservation zones, landscape and heritage
                designations
  be_wallonia   Belgium, Wallonia: plan de secteur in force, zones d'affectation (SPW)
  es_barcelona  Spain, Mapa Urbanístic de Catalunya for the province of Barcelona
                (Diputació de Barcelona service): land qualification and classification
  lu_pag        Luxembourg, PAG zones of every commune (INSPIRE OGC API Features)
  de_berlin     Germany, Berlin: B-Plan outlines in force and in procedure, with PDF links
  at_ooe        Austria, Upper Austria: Flächenwidmung zones (DORIS)
  nl_plu        Netherlands, every plan in the national DSO-LV harmonised to INSPIRE (11.6 GB)
  es_siu        Spain, national SIU: land classes and the plan in force per municipality
  cz_praha      Czechia, Prague: land-use plan functional areas
  lv_riga       Latvia, Riga: spatial plan functional zoning
  ee_plan       Estonia, national planning register: general plan land use, detailed plans
  at_tirol      Austria, Tyrol: Flächenwidmung zones
  at_bgld       Austria, Burgenland: INSPIRE zoning elements (HILUCS classes)
  at_wien       Austria, Vienna: generalised zoning plan

    uv run python scripts/build_zoning.py fr_gpu ie_myplan --lake lake-out [--upload]
    uv run python scripts/build_zoning.py ie_myplan --limit 5000   # a quick local test

In GitHub Actions: Lake catalogue > Run workflow with `zoning` = all (or a list of sources);
`zoning` = discover runs scripts/zoning_discover.py (both sweeps) and keeps the CSVs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import duckdb
import httpx
from lake import Lake, hilbert

UA = {"User-Agent": "Europe-InfraAtlas zoning build"}
SCRIPT = "scripts/build_zoning.py"

# --- harmonised classes ------------------------------------------------------------------
# One vocabulary for every source; each mapping is a lookup of the source's own code list.
VOCAB = [
    "residential",
    "mixed",
    "commercial",
    "industrial",
    "employment",
    "community",
    "open_space",
    "agricultural",
    "natural",
    "water",
    "infrastructure",
    "urban",
    "to_urbanise",
    "reserve",
    "extraction",
    "designation",
    "other",
]

CLASSES: dict[str, dict[str, str]] = {
    # France: CNIG standard `typezone` (U urban, AUc/AUs to be urbanised, A agricultural,
    # N natural and forest).
    "fr_gpu": {"U": "urban", "AUc": "to_urbanise", "AUs": "to_urbanise", "AU": "to_urbanise",
               "A": "agricultural", "N": "natural", "Nh": "natural", "Ah": "agricultural"},
    # Ireland: the Generalised Zoning Types (MyPlan GZT code list).
    "ie_myplan": {
        "R1": "residential", "R2": "residential", "R3": "residential", "R4": "reserve",
        "C1.1": "commercial", "C1.2": "commercial", "C2.1": "industrial", "C2.2": "industrial",
        "C3": "commercial", "C4": "industrial", "C5": "commercial", "C6": "employment",
        "C7": "employment", "M1": "mixed", "M2": "mixed", "M3": "mixed", "M4": "urban",
        "M5": "mixed", "G1": "open_space", "G2": "open_space", "G3": "open_space",
        "G4": "open_space", "G5": "open_space", "N1.1": "infrastructure",
        "N1.2": "infrastructure", "N1.3": "infrastructure", "N1.4": "infrastructure",
        "N1.5": "infrastructure", "N1.6": "infrastructure", "N2.1": "water",
        "N2.2": "infrastructure", "N2.3": "infrastructure", "N2.4": "infrastructure",
        "N3.1": "infrastructure", "N3.2": "infrastructure", "N3.3": "infrastructure",
        "N3.4": "infrastructure", "N4": "infrastructure", "N5": "infrastructure",
        "N6": "infrastructure", "O1": "reserve", "P1": "agricultural", "P2": "agricultural",
        "P3": "agricultural", "P4": "extraction", "P5": "agricultural", "P6": "agricultural",
        "S1": "community", "S2": "community", "S3": "community", "S4": "community",
        "S5": "community", "S6": "community",
    },
    # Denmark: Plandata general use (`anvgen`).
    "dk_plandata": {"11": "residential", "21": "mixed", "31": "industrial", "41": "mixed",
                    "51": "open_space", "61": "residential", "71": "community",
                    "81": "infrastructure", "91": "agricultural"},
    # California: the publisher's harmonised `ucd_description`.
    "us_ca": {
        "Agricultural": "agricultural", "Urban reserve": "reserve",
        "Mixed use of residential and commercial": "mixed", "Industrial": "industrial",
        "Open space and public lands": "open_space", "Water": "water",
        "Exurban residential": "residential", "Rural residential": "residential",
        "Suburban residential": "residential", "Urban residential": "residential",
        "High intensity commercial": "commercial",
        "Low intensity commercial and public facilities": "commercial",
    },
    # Wallonia: plan de secteur `AFFECT` codes, labels from the service (`DESCRIPTION`).
    "be_wallonia": {
        "H01": "residential", "H02": "residential", "A01": "employment", "A02": "industrial",
        "A11": "employment", "A12": "commercial", "D01": "reserve", "D02": "reserve",
        "R01": "agricultural", "R02": "natural", "R03": "open_space", "R04": "natural",
        "R05": "open_space", "P01": "community", "P02": "infrastructure", "E01": "water",
        "E02": "water", "X01": "extraction", "XR1": "extraction", "XR3": "extraction",
        "XR4": "extraction",
    },
    # Mapa Urbanístic de Catalunya: qualification codes and labels from the service's legend
    # (A activity, D development sectors, M mixed, N non-developable, R residential, S systems);
    # the classification layer by its label.
    "es_barcelona": {
        "A1": "industrial", "A2": "commercial", "A3": "industrial", "D1": "residential",
        "D2": "employment", "D3": "mixed", "D4": "community", "D5": "to_urbanise",
        "M1": "mixed", "M2": "mixed", "M3": "mixed", "N1": "agricultural", "N2": "natural",
        "N3": "natural", "R1": "residential", "R2": "residential", "R3": "residential",
        "R4": "residential", "R5": "residential", "R6": "residential", "SA": "infrastructure",
        "SC": "water", "SD": "community", "SE": "community", "SF": "infrastructure",
        "SH": "water", "SP": "infrastructure", "ST": "infrastructure", "SV": "open_space",
        "SX0": "infrastructure", "SX1": "infrastructure", "SX2": "infrastructure",
        "SX3": "infrastructure", "Sòl urbà": "urban", "Sòl urbà no consolidat": "urban",
        "Sòl urbanitzable delimitat": "to_urbanise", "Sòl urbanitzable no delimitat": "to_urbanise",
    },
    # England: each dataset is one designation.
    "gb_england": {},
    "fi_helsinki": {},
    # codes kept as published; no harmonised lookup yet (class `other`)
    "lu_pag": {},
    "de_berlin": {},
    # Brandenburg: the plan's main use (Hauptnutzung, BauNVO Bauflächen)
    "de_bb": {"Wohnbauflächen": "residential", "Gemischte Bauflächen": "mixed",
              "Gewerbliche Bauflächen": "employment", "Gemeinbedarfsflächen": "community",
              "Freiraum": "open_space"},
    "de_mv": {},  # plan outlines
    "de_nrw": {},  # plan outlines; plan type kept in zone_code
    "at_ooe": {},
    "ee_plan": {},
    "at_tirol": {},
    "at_bgld": {},  # HILUCS (see HILUCS below)
    "nl_plu": {},  # HILUCS
    # Spain SIU: the land classes of the Ley de Suelo as the service labels them
    "es_siu": {"SUELO URBANO": "urban", "SUELO URBANO NO CONSOLIDADO": "urban",
               "SUELO URBANIZABLE DELIMITADO O SECTORIZADO": "to_urbanise",
               "SUELO URBANIZABLE NO DELIMITADO O SECTORIZADO": "to_urbanise",
               "SUELO NO URBANIZABLE": "natural", "SISTEMAS GENERALES Y OTROS": "infrastructure"},
    "cz_praha": {},
    "pt_crus": {},  # PT_CRUS_CLASS (categories of Decreto Regulamentar 15/2015)
    "lv_riga": {},
    # Vienna: Widmungsklasse codes with the service's own labels (Wiener Bauordnung)
    "at_wien": {"WO": "residential", "WOGV": "residential", "WOGF": "residential",
                "WOFB": "residential", "WOGFGV": "residential", "GS": "residential",
                "GB": "mixed", "GBGV": "mixed", "GBGF": "mixed", "GBGFGV": "mixed",
                "GBFB": "mixed", "GBBG": "employment", "IG": "industrial",
                "E": "open_space", "S": "natural", "L": "agricultural", "VB": "infrastructure",
                "F": "community"},
}  # fmt: skip


# --- fetchers ----------------------------------------------------------------------------
def _get(c: httpx.Client, url: str, params: dict[str, Any]) -> httpx.Response:
    for attempt in range(6):
        try:
            r = c.get(url, params=params)
            if r.status_code < 500:
                r.raise_for_status()
                return r
        except httpx.HTTPError:
            if attempt == 5:
                raise
        time.sleep(2**attempt)
    raise SystemExit(f"{url}: no answer after retries")


def wfs(
    c: httpx.Client, url: str, typename: str, *, page: int = 5000, sort: str | None = None,
    limit: int | None = None,
) -> Iterator[dict[str, Any]]:  # fmt: skip
    """WFS 2.0 GetFeature as GeoJSON in EPSG:4326 (lon/lat), paged by startIndex."""
    start = 0
    while True:
        n = min(page, limit - start) if limit else page
        params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                  "typeNames": typename, "count": n, "startIndex": start,
                  "srsName": "EPSG:4326", "outputFormat": "application/json"}  # fmt: skip
        if sort:
            params["sortBy"] = sort
        feats = _get(c, url, params).json().get("features") or []
        yield from feats
        start += len(feats)
        if len(feats) < n or (limit and start >= limit):
            return


def arcgis(
    c: httpx.Client, layer: str, *, limit: int | None = None, order: str = "OBJECTID",
    page: int | None = None,
) -> Iterator[dict[str, Any]]:  # fmt: skip
    """ArcGIS FeatureServer layer as GeoJSON in EPSG:4326, paged by resultOffset; `page`
    caps the page below the server's maxRecordCount where full pages fail."""
    page = page or int(_get(c, layer, {"f": "json"}).json().get("maxRecordCount") or 1000)
    start = 0
    while True:
        n = min(page, limit - start) if limit else page
        params = {"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
                  "resultOffset": start, "resultRecordCount": n, "orderByFields": order}  # fmt: skip
        r = _get(c, f"{layer}/query", params)
        try:
            feats = r.json().get("features") or []
        except json.JSONDecodeError:
            # Some servers answer an HTML error page for a page too large to render (Spain
            # SIU): ask the same offset again with half the rows, down to one row.
            if n == 1:
                raise SystemExit(f"{layer}: no JSON answer at offset {start}") from None
            page = max(1, n // 2)
            continue
        yield from feats
        start += len(feats)
        if not feats or (limit and start >= limit):
            return


def england_csv(c: httpx.Client, dataset: str, path: Path) -> None:
    with c.stream("GET", f"https://files.planning.data.gov.uk/dataset/{dataset}.csv") as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


# --- sources: (fetch to NDJSON, SQL mapping to the standard columns) ----------------------
Fetch = Callable[[httpx.Client, Path, int | None], None]


def _ndjson(path: Path, feats: Iterator[dict[str, Any]], extra: dict[str, Any]) -> int:
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for ft in feats:
            if not ft.get("geometry"):
                ft["geometry"] = None
            f.write(json.dumps({"a": {**ft.get("properties", {}), **extra},
                                "g": ft["geometry"]}, ensure_ascii=False) + "\n")  # fmt: skip
            n += 1
    return n


def fetch_fr(c: httpx.Client, out: Path, limit: int | None) -> None:
    """Paged by gid ranges (`cql_filter`): offset paging over 1.35 M zones timed out deep in
    the table (run 42492842706); a range of 5,000 ids answers in about 2 s."""
    from concurrent.futures import ThreadPoolExecutor

    base = "https://data.geopf.fr/wfs/ows"
    common = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeNames": "wfs_du:zone_urba", "outputFormat": "application/json"}  # fmt: skip
    top = _get(c, base, {**common, "count": 1, "sortBy": "gid DESC", "propertyName": "gid"})
    gid_max = int(top.json()["features"][0]["properties"]["gid"])
    total = int(top.json().get("numberMatched") or 0)
    width = 5000
    starts = list(range(0, gid_max + 1, width))
    if limit:
        starts = starts[: max(1, limit // width)]

    def page(lo: int) -> list[dict[str, Any]]:
        params = {**common, "srsName": "EPSG:4326", "count": width * 2,
                  "cql_filter": f"gid>={lo} AND gid<{lo + width}"}  # fmt: skip
        feats = _get(c, base, params).json().get("features") or []
        if len(feats) >= width * 2:
            raise SystemExit(f"fr gid range {lo}: page full, rows would be lost")
        return feats

    n = 0
    with ThreadPoolExecutor(4) as pool:
        for i, feats in enumerate(pool.map(page, starts)):
            n += _ndjson(out, iter(feats), {})
            if i % 100 == 0:
                print(f"  fr gid {starts[i]:,} of {gid_max:,}: {n:,} zones", flush=True)
    print(f"  fr zone_urba: {n:,} (the service counts {total:,})", flush=True)
    if not limit and n != total:
        raise SystemExit(f"fr: {n:,} zones read, the service counts {total:,}")


def fetch_ie(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services"
    for name, status in (("GZT_Current_Plan", "in force"), ("GZT_Expired_Plan", "expired")):
        n = _ndjson(out, arcgis(c, f"{base}/{name}/FeatureServer/0", limit=limit),
                    {"_status": status})  # fmt: skip
        print(f"  ie {name}: {n:,}", flush=True)


def fetch_dk(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://geoserver.plandata.dk/geoserver/wfs"
    for t, kind in (
        ("pdk:theme_pdk_kommuneplanramme_vedtaget_v", "kommuneplanramme"),
        ("pdk:theme_pdk_lokalplan_vedtaget", "lokalplan"),
        ("pdk:theme_pdk_lokalplan_vedtaget_solcelle", "lokalplan solar"),
        ("pdk:theme_pdk_lokalplan_vedtaget_vindmoelle", "lokalplan wind"),
    ):
        n = _ndjson(out, wfs(c, base, t, limit=limit), {"_kind": kind})
        print(f"  dk {kind}: {n:,}", flush=True)


def fetch_fi(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
    n = _ndjson(out, wfs(c, base, "avoindata:Kaavahakemisto_alue_kaava_voimassa", limit=limit),
                {})  # fmt: skip
    print(f"  fi helsinki plans in force: {n:,}", flush=True)


def fetch_ca(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://services8.arcgis.com/Xr1lDrwMv89PhjD9/arcgis/rest/services"
    for name, layer in (("South", 0), ("North", 1)):
        url = f"{base}/California_Statewide_Zoning_{name}/FeatureServer/{layer}"
        n = _ndjson(out, arcgis(c, url, limit=limit), {"_part": name})
        print(f"  us_ca {name}: {n:,}", flush=True)


def _count(c: httpx.Client, layer: str) -> int:
    return int(_get(c, f"{layer}/query", {"where": "1=1", "returnCountOnly": "true",
                                          "f": "json"}).json()["count"])  # fmt: skip


def _arcgis_all(c: httpx.Client, out: Path, layer: str, limit: int | None,
                extra: dict[str, Any], tag: str, order: str = "OBJECTID",
                page: int | None = None) -> None:  # fmt: skip
    """A whole ArcGIS layer; stops when the rows read differ from the service's count."""
    total = _count(c, layer)
    n = _ndjson(out, arcgis(c, layer, limit=limit, order=order, page=page), extra)
    print(f"  {tag}: {n:,} (the service counts {total:,})", flush=True)
    if not limit and n != total:
        raise SystemExit(f"{tag}: {n:,} read, the service counts {total:,}")


def fetch_be(c: httpx.Client, out: Path, limit: int | None) -> None:
    url = ("https://geoservices.wallonie.be/arcgis/rest/services/AMENAGEMENT_TERRITOIRE/PDS/"
           "MapServer/22")  # fmt: skip
    _arcgis_all(c, out, url, limit, {}, "be zones d'affectation")


def fetch_es_bcn(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://gissrv.diba.cat/arcgis/rest/services/CARTOBASE/MUC/MapServer"
    for layer, kind in ((1, "qualificació"), (0, "classificació")):
        _arcgis_all(c, out, f"{base}/{layer}", limit, {"_kind": kind}, f"es {kind}")


def _ogr(out: Path, url: str, layer: str, limit: int | None, extra: dict[str, Any],
         tag: str, latlon: bool = False) -> None:  # fmt: skip
    """Any GDAL source (WFS:, OAPIF:, a file or /vsizip/ path) through DuckDB's ST_Read.
    The geometry is reprojected from the layer's declared CRS to EPSG:4326 (lon/lat) with
    PROJ; `latlon` marks a layer whose coordinates are WGS84 latitude, longitude whatever CRS
    it declares (they are swapped, not reprojected). The rows read are checked against the
    layer's feature count when GDAL reports one."""
    import os

    os.environ["GML_ATTRIBUTES_TO_OGR_FIELDS"] = "YES"  # INSPIRE codes sit in xlink:href
    # WFS servers cap a response (Burgenland: 1,000); GDAL pages through the whole layer.
    os.environ["OGR_WFS_PAGING_ALLOWED"] = "ON"
    os.environ["OGR_WFS_PAGE_SIZE"] = "1000"
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    meta = con.execute(
        "SELECT l.feature_count, l.geometry_fields[1].crs.auth_name, "
        "l.geometry_fields[1].crs.auth_code FROM (SELECT unnest(layers) AS l "
        "FROM st_read_meta(?)) WHERE l.name = ?", [url, layer]
    ).fetchone()  # fmt: skip
    if meta is None:
        raise SystemExit(f"{tag}: layer {layer} not found at {url}")
    total, auth, code = meta
    cur = con.execute(f"SELECT * FROM st_read(?, layer = ?) {f'LIMIT {limit}' if limit else ''}",
                      [url, layer])  # fmt: skip
    cols = [d[0] for d in cur.description]
    gtype = next(str(d[1]) for d in cur.description if str(d[1]).upper().startswith("GEOMETRY"))
    gcol = cols[[str(d[1]) for d in cur.description].index(gtype)]
    typed = gtype[gtype.find("'") + 1 : gtype.rfind("'")] if "'" in gtype else ""
    crs = typed or (f"{auth}:{code}" if auth and code else "EPSG:4326")
    geo = (
        f"ST_FlipCoordinates({gcol}::GEOMETRY)"
        if latlon
        else f"ST_Transform({gcol}::GEOMETRY, '{crs}', 'EPSG:4326', always_xy := true)"
    )
    if latlon:
        crs = "WGS84 latitude, longitude (swapped)"
    # COPY streams to disk; a Python fetch materialises the whole layer (the Netherlands
    # ZoningElement layer ran out of 12 GB that way).
    con.execute("SET preserve_insertion_order = false")
    part = out.with_suffix(".ogr.json")
    con.execute(
        f"COPY (SELECT * EXCLUDE ({gcol}), ST_AsGeoJSON({geo}) AS __g FROM st_read(?, layer = ?) "
        f"{f'LIMIT {limit}' if limit else ''}) TO '{part}' (FORMAT JSON)", [url, layer])  # fmt: skip
    n = 0
    with out.open("a", encoding="utf-8") as f, part.open(encoding="utf-8") as src:
        for line in src:
            r = json.loads(line)
            g = r.pop("__g", None)
            props = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                     for k, v in r.items()}  # fmt: skip
            g = json.loads(g) if isinstance(g, str) else g  # a JSON value already
            f.write(json.dumps({"a": {**props, **extra}, "g": g}, ensure_ascii=False) + "\n")
            n += 1
    part.unlink()
    print(f"  {tag}: {n:,} (GDAL counts {total:,}; CRS {crs[:60]})", flush=True)
    if not limit and total is not None and total >= 0 and n != total:
        raise SystemExit(f"{tag}: {n:,} read, the layer counts {total:,}")


def fetch_lu(c: httpx.Client, out: Path, limit: int | None) -> None:
    _ogr(out, "OAPIF:https://wms.inspire.geoportail.lu/geoserver/lu/ogc/features/v1",
         "LU.SpatialPlan.PAG", limit, {}, "lu PAG", latlon=True)  # fmt: skip


def fetch_de_berlin(c: httpx.Client, out: Path, limit: int | None) -> None:
    for layer, status in (("bplan:b_bp_fs", "in force"), ("bplan:a_bp_iv", "in procedure")):
        _ogr(out, "WFS:https://gdi.berlin.de/services/wfs/bplan", layer, limit,
             {"_status": status}, f"de-berlin {layer}")  # fmt: skip


NRW_PLANTYP = {"1000": "Bebauungsplan", "2000": "Flächennutzungsplan",
               "3000": "Innen- oder Außenbereichssatzung", "4000": "Sonstige Satzung oder Plan"}  # fmt: skip
# Only 4000 is confirmed: the state's OGC API gives it as ProcessStepGeneral legalForce
# ("rechtsverbindlich oder in Kraft"); NRW publishes no list for the other codes, kept as codes.
NRW_STAND = {"4000": "in force"}


def fetch_de_nrw(c: httpx.Client, out: Path, limit: int | None) -> None:
    """Bauleitpläne NRW (the state's INSPIRE planned land use, the plans the municipalities
    report): one GeoPackage, layer PlaeneNachBauGB, EPSG:25832. The plan type and process step
    codes are the state's code lists (ogc-api.nrw.de/codelist, luplantypenamevalue and the
    INSPIRE ProcessStepGeneralValue numbering), kept with their labels."""
    z = out.with_name("de_nrw_bplan.zip")
    _download(c, "https://www.opengeodata.nrw.de/produkte/infrastruktur_bauen_wohnen/"
              "bauleitplanung/bplan_EPSG25832_GeoPackage.zip", z)  # fmt: skip
    _ogr(out, f"/vsizip/{z}/bplan.gpkg", "PlaeneNachBauGB", limit, {}, "de-nrw Bauleitpläne")
    z.unlink()


MV_LAYERS = {"sm:B_Plan_wfs": "Bebauungsplan", "sm:BP_Bereiche_wfs": "Bebauungsplan, Bereich",
             "sm:F_Plan_wfs": "Flächennutzungsplan", "sm:FP_Bereich_wfs": "Flächennutzungsplan, Bereich",
             "sm:SO_Plan_wfs": "Sonderplan", "sm:SO_Bereich_wfs": "Sonderplan, Bereich"}  # fmt: skip


def fetch_de_mv(c: httpx.Client, out: Path, limit: int | None) -> None:
    """Bauleitpläne in MV: the state WFS with the outlines of every development, land-use and
    special plan held in the Bauportal MV, and their parts (Bereiche); legal status as text."""
    for layer, kind in MV_LAYERS.items():
        _ogr(out, "WFS:https://www.geodaten-mv.de/dienste/bauleitplan_wfs", layer, limit,
             {"_layer": kind}, f"de-mv {layer}")  # fmt: skip


def fetch_de_bb(c: httpx.Client, out: Path, limit: int | None) -> None:
    """Brandenburg: outlines of the legally effective development plans (PLIS, Landesamt für
    Bauen und Verkehr), WFS as GeoJSON (GDAL's reader stops at the curved geometries)."""
    base = "https://plis-bb.de/plisproject/inspire/index.php/geoserver/bebauungsplaene_rechtswirksam_wfs/wfs"
    for layer in (
        "bp_rechtswirksam_flaechen",
        "bp_rechtswirksam_linien",
        "bp_rechtswirksam_punkte",
    ):
        tn = f"bebauungsplaene_rechtswirksam_wfs:{layer}"
        n = _ndjson(out, wfs(c, base, tn, sort="bp_id", limit=limit), {"_layer": layer})
        print(f"  de-bb {layer}: {n:,}", flush=True)


def _download(c: httpx.Client, url: str, path: Path, tries: int = 6) -> None:
    """Stream a file to disk; a dropped connection resumes with a Range request (PDOK cut
    the 11.6 GB Netherlands file at 9.0 GB and at 8.6 GB)."""
    path.unlink(missing_ok=True)
    total = None
    for attempt in range(tries):
        have = path.stat().st_size if path.exists() else 0
        # PDOK answers an open range ("bytes=N-") with the whole file; a closed one works.
        headers = {"Range": f"bytes={have}-{total - 1 if total else ''}"} if have else {}
        try:
            with c.stream("GET", url, headers=headers) as r:
                r.raise_for_status()
                if have and r.status_code != 206:
                    raise SystemExit(f"{url}: the server does not resume (HTTP {r.status_code})")
                if not have:
                    total = int(r.headers.get("content-length") or 0) or None
                with path.open("ab") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            if total is None or path.stat().st_size == total:
                break
        except (httpx.TransportError, httpx.RemoteProtocolError) as e:
            print(f"  download cut at {path.stat().st_size:,} bytes ({e}); resuming", flush=True)
            time.sleep(10 * (attempt + 1))
    else:
        raise SystemExit(f"{url}: incomplete after {tries} tries")
    if total is not None and path.stat().st_size != total:
        raise SystemExit(f"{url}: {path.stat().st_size:,} of {total:,} bytes")
    print(f"  downloaded {url}: {path.stat().st_size / 1e6:.1f} MB", flush=True)


def fetch_at_ooe(c: httpx.Client, out: Path, limit: int | None) -> None:
    """The OGD shapefile: the ArcGIS service does not answer GitHub's runners (run
    42571441861); the file holds the same 231,589 zones."""
    z = out.with_name("at_ooe.zip")
    _download(c, "https://e-gov.ooe.gv.at/at.gv.ooe.dorisdaten/DORIS_Basisdaten/"
              "FLWI_WIDMUNGEN_F.zip", z)  # fmt: skip
    _ogr(out, f"/vsizip/{z}/FLWI_WIDMUNGEN_F.shp", "FLWI_WIDMUNGEN_F", limit, {},
         "at-ooe Widmungen Flächen")  # fmt: skip


def fetch_nl(c: httpx.Client, out: Path, limit: int | None) -> None:
    """The national INSPIRE file (11.6 GB GML, PDOK Atom feed, refreshed by Kadaster): every
    plan in the DSO-LV (Omgevingswet) harmonised to INSPIRE Planned Land Use."""
    url = (
        "https://service.pdok.nl/kadaster/omgevingswet-planned-land-use/atom/downloads/land_use.gml"
    )
    if limit:
        _ogr(out, f"/vsicurl/{url}", "ZoningElement", limit, {}, "nl ZoningElement")
        return
    src = out.with_name("nl_land_use.gml")
    _download(c, url, src)
    # DuckDB's st_read ran out of 12 GB on this file (whole-municipality geometries, read 2,048
    # rows at a time); GDAL's ogr2ogr writes one feature at a time.
    _ogr2ogr(out, src, "ZoningElement", {}, "nl ZoningElement")
    src.unlink()


def _ogr2ogr(out: Path, src: Path, layer: str, extra: dict[str, Any], tag: str) -> None:
    """One layer of a local GDAL file through the ogr2ogr command (GeoJSONSeq in EPSG:4326,
    longitude first), checked against the feature count ogrinfo reports."""
    import re
    import subprocess

    cfg = ["--config", "GML_ATTRIBUTES_TO_OGR_FIELDS", "YES"]
    seq = out.with_suffix(".ogr.geojsonl")
    subprocess.run(["ogr2ogr", *cfg, "-f", "GeoJSONSeq", "-t_srs", "EPSG:4326", str(seq),
                    str(src), layer], check=True)  # fmt: skip
    info = subprocess.run(["ogrinfo", *cfg, "-so", str(src), layer], check=True,
                          capture_output=True, text=True).stdout  # fmt: skip
    m = re.search(r"Feature Count: (-?\d+)", info)
    total = int(m.group(1)) if m else None
    n = 0
    with out.open("a", encoding="utf-8") as f, seq.open(encoding="utf-8") as lines:
        for line in lines:
            feat = json.loads(line)
            props = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                     for k, v in (feat.get("properties") or {}).items()}  # fmt: skip
            f.write(json.dumps({"a": {**props, **extra}, "g": feat.get("geometry")},
                               ensure_ascii=False) + "\n")  # fmt: skip
            n += 1
    seq.unlink()
    print(f"  {tag}: {n:,} (GDAL counts {total if total is None else f'{total:,}'})", flush=True)
    if total is not None and total >= 0 and n != total:
        raise SystemExit(f"{tag}: {n:,} read, the layer counts {total:,}")


def fetch_pt_crus(c: httpx.Client, out: Path, limit: int | None) -> None:
    """DGT's national Carta do Regime de Uso do Solo WFS (mainland Portugal, every PDM in one
    harmonised layer). The Intergraph server answers GDAL's WFS driver with no layers, ignores
    `startIndex` (offset 50,000 returns the first features again), refuses attribute filters
    and reports no hit count, so the layer is read by bounding box: WFS 1.1 with
    `maxFeatures=20000` (the largest value it accepts; 50,000 is refused), 20 km tiles over the
    mainland in EPSG:3763, a tile that returns the cap split in four until none does. A zone
    crossing tile edges comes back from each tile and is kept once, by its ID; every zone
    intersects some tile, so the read is complete. Each tile is read by GDAL as a local file
    (EPSG:3763 reprojected by PROJ)."""
    url = "https://servicos.dgterritorio.pt/SDISNITWFSCRUS/WFService.aspx"
    cap, step = 20_000, 20_000
    tmp, part = out.with_name("pt_crus_tile.gml"), out.with_name("pt_crus_tile.ndjson")
    seen: set[Any] = set()
    n = tiles = dup = 0
    # Mainland Portugal in PT-TM06 / ETRS89 (EPSG:3763) is inside x -130 to 180 km,
    # y -320 to 290 km; empty tiles answer in about a second.
    todo = [(x, y, x + step, y + step) for x in range(-130_000, 180_000, step)
            for y in range(-320_000, 290_000, step)]  # fmt: skip
    while todo:
        x0, y0, x1, y1 = todo.pop(0)
        params = {"service": "WFS", "version": "1.1.0", "request": "GetFeature",
                  "typeName": "gmgml:CRUS", "maxFeatures": cap,
                  "bbox": f"{x0},{y0},{x1},{y1},EPSG:3763"}  # fmt: skip
        # The server answers some requests with "Value provided for a parameter is invalid"
        # and the same request moments later with features; ask again.
        for attempt in range(8):
            try:
                r = c.get(url, params=params, timeout=600)
                r.raise_for_status()
                if b"FeatureCollection" not in r.content[:2000]:
                    raise httpx.HTTPError(f"no feature collection: {r.content[:120]!r}")
                break
            except httpx.HTTPError as e:
                print(f"  pt CRUS tile {x0},{y0}: {str(e)[:80]}; retry {attempt + 1}", flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"pt CRUS: tile {x0},{y0} failed eight times")
        tiles += 1
        m = re.search(rb'numberOfFeatures="(\d+)"|numberReturned="(\d+)"', r.content[:3000])
        got = int(next(g for g in m.groups() if g)) if m else 0
        if got >= cap:
            h = (x1 - x0) // 2
            todo[:0] = [(x0, y0, x0 + h, y0 + h), (x0 + h, y0, x1, y0 + h),
                        (x0, y0 + h, x0 + h, y1), (x0 + h, y0 + h, x1, y1)]  # fmt: skip
            continue
        if not got:
            continue
        tmp.write_bytes(r.content)
        # DuckDB's spatial reader crashed once on a page it reads cleanly on its own
        # (an internal error after four hours); read the tile again.
        for _attempt in range(3):
            part.unlink(missing_ok=True)
            try:
                _ogr(part, str(tmp), "CRUS", None, {}, f"pt CRUS tile {x0},{y0}")
                break
            except duckdb.Error as e:
                print(f"  pt CRUS tile {x0},{y0}: {str(e)[:80]}; read again", flush=True)
        else:
            raise SystemExit(f"pt CRUS: tile {x0},{y0} could not be read three times")
        with out.open("a", encoding="utf-8") as f, part.open(encoding="utf-8") as src:
            for line in src:
                zid = json.loads(line)["a"].get("ID")
                if zid is None:
                    raise SystemExit(f"pt CRUS: a zone without an ID in tile {x0},{y0}")
                if zid in seen:
                    dup += 1
                    continue
                seen.add(zid)
                f.write(line)
                n += 1
        if limit and n >= limit:
            break
    tmp.unlink(missing_ok=True)
    part.unlink(missing_ok=True)
    print(f"  pt CRUS: {n:,} zones from {tiles:,} tiles ({dup:,} edge repeats dropped)", flush=True)


def fetch_es_siu(c: httpx.Client, out: Path, limit: int | None) -> None:
    base = "https://mapas.fomento.gob.es/arcgis/rest/services/SIU"
    _arcgis_all(c, out, f"{base}/CLASES_DE_SUELO/MapServer/0", limit,
                {"_kind": "land class"}, "es SIU clases de suelo", page=500)  # fmt: skip
    _arcgis_all(c, out, f"{base}/Planeamiento_Vigente/MapServer/0", limit,
                {"_kind": "plan in force"}, "es SIU planeamiento vigente",
                order="GIS_SIU.SIU.EGRN_recintos_municipales_inspire.OBJECTID",
                page=500)  # fmt: skip


def fetch_cz_praha(c: httpx.Client, out: Path, limit: int | None) -> None:
    _arcgis_all(c, out, "https://mp.iprpraha.cz/arcgis/rest/services/Hosted/PUP_CUR_PVP_FVU_P/"
                "FeatureServer/0", limit, {}, "cz-praha funkční plochy", order="objectid")  # fmt: skip


def fetch_lv_riga(c: httpx.Client, out: Path, limit: int | None) -> None:
    g = out.with_name("lv_riga.gpkg")
    _download(c, "https://data.gov.lv/dati/dataset/f5fa538b-8e2a-4bee-ab64-a9c41937337a/"
              "resource/26352840-5766-4a3b-bb85-170ce89fdbc3/download/funkcionalais_zonejums.gpkg",
              g)  # fmt: skip
    _ogr(out, str(g), "funkcionalais_zonejums", limit, {}, "lv-riga funkcionālais zonējums")


def fetch_ee(c: httpx.Client, out: Path, limit: int | None) -> None:
    url = "WFS:https://gsavalik.envir.ee/geoserver/planeeringud/wfs"
    for layer, kind in (("planeeringud:yld_plan_maakas", "general plan land use"),
                        ("planeeringud:detail_plan_ala", "detailed plan area")):  # fmt: skip
        _ogr(out, url, layer, limit, {"_kind": kind}, f"ee {layer}")


def fetch_at_tirol(c: httpx.Client, out: Path, limit: int | None) -> None:
    url = ("https://services3.arcgis.com/hG7UfxX49PQ8XkXh/arcgis/rest/services/"
           "FLW_Flaechenwidmung/FeatureServer/0")  # fmt: skip
    _arcgis_all(c, out, url, limit, {}, "at-tirol Flächenwidmung")


def fetch_at_bgld(c: httpx.Client, out: Path, limit: int | None) -> None:
    _ogr(out, "WFS:https://haleconnect.com/ows/services/"
         "org.868.6316de7d-2c9e-470e-addf-026d89df2dae_wfs", "plu:ZoningElement", limit, {},
         "at-bgld ZoningElement")  # fmt: skip


def fetch_at_wien(c: httpx.Client, out: Path, limit: int | None) -> None:
    feats = wfs(c, "https://data.wien.gv.at/daten/geo", "ogdwien:GENFLWIDMUNGOGD", limit=limit)
    n = _ndjson(out, feats, {})
    print(f"  at-wien GENFLWIDMUNGOGD: {n:,}", flush=True)


# Planning designations published nationally on planning.data.gov.uk (OGL). `local-plan` is
# the plan register (adopted dates, PDF links, no geometry of its own); `local-plan-boundary`
# its areas. Nature and flood layers are left to their own datasets.
ENGLAND = ("green-belt", "conservation-area", "article-4-direction-area", "brownfield-land",
           "local-plan", "local-plan-boundary", "development-policy-area", "housing-allocation",
           "tree-preservation-zone", "area-of-outstanding-natural-beauty", "national-park",
           "world-heritage-site", "world-heritage-site-buffer-zone", "park-and-garden",
           "scheduled-monument", "listed-building-outline", "heritage-coast")  # fmt: skip
ENGLAND_CLASS = {"housing-allocation": "residential"}


def fetch_gb(c: httpx.Client, out: Path, limit: int | None) -> None:
    out.unlink(missing_ok=True)
    for d in ENGLAND:
        england_csv(c, d, out.with_name(f"{d}.csv"))
        print(f"  gb {d}: {out.with_name(f'{d}.csv').stat().st_size / 1e6:.1f} MB", flush=True)


def _cls(source: str, code_sql: str) -> str:
    pairs = CLASSES[source]
    if not pairs:
        return "'other'"
    whens = " ".join(f"WHEN {code_sql} = '{k}' THEN '{v}'" for k, v in pairs.items())
    return f"CASE {whens} ELSE 'other' END"


# INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) to the vocabulary,
# most specific prefix first; codes are read from the end of the codelist URI.
HILUCS = [
    ("3_4_4", "open_space"), ("6_3_2", "water"), ("6_3", "natural"), ("1_1", "agricultural"),
    ("1_2", "natural"), ("1_3", "extraction"), ("1_4", "agricultural"), ("1_5", "agricultural"),
    ("2_", "industrial"), ("3_1", "commercial"), ("3_2", "commercial"), ("3_3", "community"),
    ("3_4", "community"), ("3_5", "commercial"), ("4_", "infrastructure"), ("5_", "residential"),
]  # fmt: skip


def _hilucs(uri_sql: str) -> str:
    code = f"regexp_extract({uri_sql}, '/HILUCSValue/([0-9_]+)', 1)"
    whens = " ".join(f"WHEN starts_with({code}, '{k}') THEN '{v}'" for k, v in HILUCS)
    return f"CASE {whens} ELSE 'other' END"


PT_CRUS_CLASS = (
    "CASE WHEN {c} ILIKE '%habitacion%' THEN 'residential' "
    "WHEN {c} ILIKE '%centra%' THEN 'mixed' "
    "WHEN {c} ILIKE '%atividades econ%' OR {c} ILIKE '%actividades econ%' THEN 'employment' "
    "WHEN {c} ILIKE '%industria%' THEN 'industrial' "
    "WHEN {c} ILIKE '%verde%' THEN 'open_space' "
    "WHEN {c} ILIKE '%equipamento%' OR {c} ILIKE '%uso especial%' THEN 'community' "
    "WHEN {c} ILIKE '%agr%' THEN 'agricultural' "
    "WHEN {c} ILIKE '%florest%' OR {c} ILIKE '%natura%' THEN 'natural' "
    "WHEN {c} ILIKE '%recursos geol%' OR {c} ILIKE '%recursos energ%' THEN 'extraction' "
    "WHEN {c} ILIKE '%infraestrutura%' THEN 'infrastructure' "
    "WHEN {c} ILIKE '%gua%' AND {c} ILIKE '%plano%' THEN 'water' "
    "WHEN {r} ILIKE 'Solo Urbano%' THEN 'urban' ELSE 'other' END"
)


def a(field: str) -> str:
    return f"nullif(trim(a->>'{field}'), '')"


# Each source's mapping to the standard columns; `a` is the source attributes (JSON).
MAPS: dict[str, dict[str, str]] = {
    "fr_gpu": {
        "country": "'FR'", "authority": a("partition"), "plan_id": a("idurba"),
        "plan_name": a("idurba"), "plan_status": "'in force'", "adopted": a("datappro"),
        "zone_code": a("libelle"), "zone_label": a("libelong"), "class_code": a("typezone"),
        "class": _cls("fr_gpu", a("typezone")), "doc_url": a("urlfic"),
    },
    "ie_myplan": {
        "country": "'IE'", "authority": a("LA_NAME"), "plan_id": a("PLAN_ID"),
        "plan_name": a("PLAN_NAME"), "plan_status": a("_status"), "adopted": a("PLAN_FROM"),
        "zone_code": a("ZONE_ORIG"), "zone_label": a("ZONE_DESC"), "class_code": a("ZONE_GZT"),
        "class": _cls("ie_myplan", a("ZONE_GZT")), "doc_url": a("ZONE_LINK"),
    },
    "dk_plandata": {
        "country": "'DK'", "authority": a("kommunenavn"), "plan_id": a("planid"),
        "plan_name": "concat_ws(' ', " + a("plannr") + ", " + a("plannavn") + ")",
        "plan_status": "'adopted'", "adopted": a("datovedt"), "zone_code": a("_kind"),
        "zone_label": a("anvendelsegenerel"), "class_code": a("anvgen"),
        "class": _cls("dk_plandata", a("anvgen")), "doc_url": a("doklink"),
    },
    "fi_helsinki": {
        "country": "'FI'", "authority": "'Helsinki'", "plan_id": a("kaavatunnus"),
        "plan_name": a("kaavatunnus"), "plan_status": a("luokka"),
        "adopted": a("hyvaksymispvm"), "zone_code": a("tyyppi"), "zone_label": a("tyyppi"),
        "class_code": "NULL", "class": "'other'", "doc_url": "NULL",
    },
    "us_ca": {
        "country": "'US'", "authority": a("Jurisdiction"), "plan_id": "NULL",
        "plan_name": "concat_ws(', ', " + a("Jurisdiction") + ", " + a("County") + ")",
        "plan_status": "'in force'", "adopted": a("Date"), "zone_code": a("Code"),
        "zone_label": a("Description"), "class_code": a("ucd_description"),
        "class": _cls("us_ca", a("ucd_description")), "doc_url": a("Source"),
    },
    "be_wallonia": {
        "country": "'BE'", "authority": "'Wallonia (SPW)'", "plan_id": "NULL",
        "plan_name": "'Plan de secteur'", "plan_status": "'in force'", "adopted": "NULL",
        "zone_code": a("AFFECT"), "zone_label": a("DESCRIPTION"), "class_code": a("AFFECT"),
        "class": _cls("be_wallonia", a("AFFECT")), "doc_url": a("LIEN_WALLEX"),
    },
    "es_barcelona": {
        "country": "'ES'", "authority": a("CODI_INE"), "plan_id": a("CODI_INE"),
        "plan_name": "'Mapa Urbanístic de Catalunya, ' || " + a("_kind"),
        "plan_status": "'in force'", "adopted": "NULL",
        "zone_code": "coalesce(" + a("C_QUAL_MUC") + ", " + a("D_CLAS_MUC") + ")",
        "zone_label": "coalesce(" + a("D_QUAL_AJT") + ", " + a("D_CLAS_MUC") + ")",
        "class_code": "coalesce(" + a("C_QUAL_MUC") + ", " + a("D_CLAS_MUC") + ")",
        "class": _cls("es_barcelona", "coalesce(" + a("C_QUAL_MUC") + ", " + a("D_CLAS_MUC") + ")"),
        "doc_url": "NULL",
    },
    "lu_pag": {
        "country": "'LU'", "authority": "json_extract_string(" + a("gml_description") + ", '$.CODE_COM')",
        "plan_id": a("plan_id"), "plan_name": a("plantypename_xlink_title"),
        "plan_status": "'in force'",
        "adopted": a("legislationcitation_legislationcitation_date_ci_date_date_date"),
        "zone_code": a("categorie"), "zone_label": a("specificlanduse0_xlink_title"),
        "class_code": a("categorie"), "class": "'other'", "doc_url": a("regulationtext"),
    },
    "de_berlin": {
        "country": "'DE'", "authority": "'Berlin, ' || " + a("bezirk"), "plan_id": a("planid"),
        "plan_name": a("planname"), "plan_status": a("_status"), "adopted": a("festsg_am"),
        "zone_code": a("planartname"), "zone_label": a("inhalt"), "class_code": "NULL",
        "class": "'other'", "doc_url": a("scan_www"),
    },
    "de_nrw": {
        "country": "'DE'", "authority": a("kommune"), "plan_id": a("planid"),
        "plan_name": a("name"),
        "plan_status": "CASE " + a("stand") + " " + " ".join(
            f"WHEN '{k}' THEN '{v}'" for k, v in NRW_STAND.items()) + " ELSE 'NRW stand ' || " + a("stand") + " END",
        "adopted": "left(" + a("datum") + ", 10)",
        "zone_code": "CASE " + a("plantyp") + " " + " ".join(
            f"WHEN '{k}' THEN '{v}'" for k, v in NRW_PLANTYP.items()) + " ELSE " + a("plantyp") + " END",
        "zone_label": a("nr"), "class_code": a("planart"), "class": "'other'",
        "doc_url": "coalesce(" + a("scanurl") + ", " + a("texturl") + ", " + a("sonsturl") + ")",
    },
    "de_mv": {
        "country": "'DE'",
        "authority": "regexp_extract(" + a("gemeinde") + ", '\"gemeindename\":\"([^\"]+)\"', 1)",
        "plan_id": a("gmlid"), "plan_name": a("anzeigename"),
        "plan_status": a("rechtsstand_text"), "adopted": "left(" + a("inkrafttretensdatum") + ", 10)",
        "zone_code": a("_layer"), "zone_label": a("planart_text"), "class_code": a("planart"),
        "class": "'other'", "doc_url": a("link"),
    },
    "de_bb": {
        "country": "'DE'", "authority": a("gemname"), "plan_id": a("bp_id"),
        "plan_name": a("bp_bez"), "plan_status": a("bp_t_ent_g"),
        "adopted": "strftime(try_strptime(" + a("bp_dat_bek") + ", '%d.%m.%Y'), '%Y-%m-%d')",
        "zone_code": a("bp_t_part"), "zone_label": a("bp_t_vart"), "class_code": a("bp_t_haupt"),
        "class": _cls("de_bb", a("bp_t_haupt")), "doc_url": "NULL",
    },
    "at_ooe": {
        "country": "'AT'", "authority": a("GEM_NR"), "plan_id": a("GEM_NR"),
        "plan_name": "'Flächenwidmungsplan, Gemeinde ' || " + a("GEM_NR"),
        "plan_status": "'in force'", "adopted": "NULL", "zone_code": a("KENNZAHL"),
        "zone_label": a("ZUSATZTEXT"), "class_code": a("KENNZAHL"), "class": "'other'",
        "doc_url": "NULL",
    },
    "ee_plan": {
        "country": "'EE'", "authority": "NULL", "plan_id": a("planid"),
        "plan_name": "coalesce(" + a("plannim") + ", " + a("kihi_nimi") + ")",
        "plan_status": "coalesce(" + a("planseis_vaste") + ", 'in force')",
        "adopted": a("kehtestkp"), "zone_code": "coalesce(" + a("tahis") + ", " + a("_kind") + ")",
        "zone_label": "coalesce(" + a("juhtots") + ", " + a("planeesm") + ")",
        "class_code": a("tahis"), "class": "'other'", "doc_url": a("planviide"),
    },
    "at_tirol": {
        "country": "'AT'", "authority": a("GEMNR"), "plan_id": a("GEMNR"),
        "plan_name": "'Flächenwidmungsplan, Gemeinde ' || " + a("GEMNR"),
        "plan_status": "'in force'", "adopted": a("STAND"), "zone_code": a("BESCHTXT"),
        "zone_label": a("WIDMUNG"), "class_code": a("OBJEKT"), "class": "'other'",
        "doc_url": "NULL",
    },
    "at_bgld": {
        "country": "'AT'", "authority": "'Burgenland'", "plan_id": a("plan_href"),
        "plan_name": "'Flächenwidmung Burgenland (INSPIRE)'", "plan_status": "'in force'",
        "adopted": a("beginLifespanVersion"),
        "zone_code": "regexp_extract(" + a("specificLandUse_href") + ", '[^/]+$')",
        "zone_label": "regexp_extract(" + a("hilucsLandUse_href") + ", '[^/]+$')",
        "class_code": "regexp_extract(" + a("hilucsLandUse_href") + ", '[^/]+$')",
        "class": _hilucs(a("hilucsLandUse_href")), "doc_url": a("officialDocument_href"),
    },
    "nl_plu": {
        "country": "'NL'", "authority": "regexp_extract(" + a("plan_href") + ", '([^/.]+)\\.[^/]*$', 1)",
        "plan_id": a("plan_href"), "plan_name": a("plan_href"), "plan_status": "'in force'",
        "adopted": a("beginLifespanVersion"),
        "zone_code": "regexp_extract(" + a("specificLandUse_href") + ", '[^/]+$')",
        "zone_label": "coalesce(" + a("name") + ", regexp_extract(" + a("specificLandUse_href") + ", '[^/]+$'))",
        "class_code": "regexp_extract(" + a("hilucsLandUse_href") + ", '[^/]+$')",
        "class": _hilucs(a("hilucsLandUse_href")), "doc_url": a("officialDocument_href"),
    },
    "es_siu": {
        "country": "'ES'",
        "authority": "coalesce(" + a("ProvINE") + ", " + a("GIS_SIU.SIU.plan_mun.ProvMunText") + ")",
        "plan_id": a("GIS_SIU.SIU.plan_mun.ProvMunText"),
        "plan_name": "concat_ws(', ', " + a("GIS_SIU.SIU.plan_mun.FiguraVigente") + ", "
                     + a("GIS_SIU.SIU.plan_mun.nombre") + ")",
        "plan_status": "'in force'", "adopted": a("GIS_SIU.SIU.plan_mun.FechaFigura"),
        "zone_code": "coalesce(" + a("ClaseSuelo") + ", " + a("_kind") + ")",
        "zone_label": "coalesce(" + a("ClaseSuelo") + ", " + a("GIS_SIU.SIU.plan_mun.FiguraVigente") + ")",
        "class_code": a("ClaseSuelo"), "class": _cls("es_siu", a("ClaseSuelo")),
        "doc_url": a("GIS_SIU.SIU.plan_mun.UrlLink"),
    },
    "cz_praha": {
        "country": "'CZ'", "authority": "'Praha (IPR)'", "plan_id": a("zdroj"),
        "plan_name": "'Územní plán hl. m. Prahy, ' || " + a("zdroj"),
        "plan_status": "'in force'", "adopted": "NULL", "zone_code": a("kodfp1_a"),
        "zone_label": a("popis"), "class_code": a("kodfp1_a"), "class": "'other'",
        "doc_url": "NULL",
    },
    "lv_riga": {
        "country": "'LV'", "authority": "'Rīga'", "plan_id": "'Rīgas teritorijas plānojums'",
        "plan_name": "'Rīgas teritorijas plānojums (spēkā)'", "plan_status": "'in force'",
        "adopted": "NULL", "zone_code": a("planotais_"), "zone_label": a("planotais_"),
        "class_code": a("planotais_"), "class": "'other'", "doc_url": a("vairak_inf"),
    },
    "at_wien": {
        "country": "'AT'", "authority": "'Wien, Bezirk ' || " + a("BEZIRK"),
        "plan_id": "NULL", "plan_name": "'Flächenwidmungsplan Wien (generalisiert)'",
        "plan_status": "'in force'", "adopted": "NULL", "zone_code": a("WIDMUNG"),
        "zone_label": a("WIDMUNG_TXT"), "class_code": a("WIDMUNGSKLASSE"),
        "class": _cls("at_wien", a("WIDMUNGSKLASSE")), "doc_url": "NULL",
    },
    "pt_crus": {
        "country": "'PT'", "authority": "'Município de ' || " + a("Municipio"),
        "plan_id": a("DTCC"), "plan_name": "'PDM ' || " + a("Municipio"),
        "plan_status": a("Situação_PDM"), "adopted": "left(" + a("Data_PublicaçãoPDM") + ", 10)",
        "zone_code": a("Classe") + " || ' / ' || " + a("Categoria"),
        "zone_label": a("Designação_PlantaOrdenamento"), "class_code": a("Categoria"),
        "class": PT_CRUS_CLASS.format(c=a("Categoria"), r=a("Classe")), "doc_url": "NULL",
    },
}  # fmt: skip

SOURCES: dict[str, tuple[Fetch, str, str]] = {
    "fr_gpu": (fetch_fr, "Géoportail de l'Urbanisme (IGN, Géoplateforme WFS wfs_du:zone_urba)",
               "Licence Ouverte 2.0"),
    "ie_myplan": (fetch_ie, "MyPlan, Department of Housing, Local Government and Heritage "
                  "(Generalised Zoning Types, current and expired plans)", "CC BY 4.0"),
    "dk_plandata": (fetch_dk, "Plandata.dk (Plansystemet), Danish Agency for Planning and Rural "
                    "Affairs: kommuneplanrammer and lokalplaner, adopted", "Plandata terms (open)"),
    "fi_helsinki": (fetch_fi, "City of Helsinki, Kaavahakemisto (plans in force), WFS avoindata",
                    "CC BY 4.0"),
    "us_ca": (fetch_ca, "California Statewide Zoning, Office of Land Use and Climate Innovation "
              "(ArcGIS FeatureServer)", "no licence stated (public access)"),
    "gb_england": (fetch_gb, "planning.data.gov.uk (MHCLG): local plans and boundaries, green "
                   "belt, housing allocations, development policy areas, conservation area, "
                   "article 4 direction area, brownfield land, tree preservation zones, landscape "
                   "and heritage designations", "OGL 3.0"),
    "be_wallonia": (fetch_be, "Plan de secteur en vigueur, Service public de Wallonie (SPW "
                    "Territoire), ArcGIS AMENAGEMENT_TERRITOIRE/PDS layer 22", "CC BY 4.0"),
    "es_barcelona": (fetch_es_bcn, "Mapa Urbanístic de Catalunya (Generalitat de Catalunya, "
                     "Departament de Territori), served for the province of Barcelona by the "
                     "Diputació de Barcelona (CARTOBASE/MUC)", "no licence stated on the service"),
    "lu_pag": (fetch_lu, "Plans d'aménagement général (PAG) of every commune, INSPIRE Planned "
               "Land Use, Administration du cadastre et de la topographie (geoportail.lu, OGC API "
               "Features LU.SpatialPlan.PAG)",
               "CC0 (data.public.lu, PAG géométries de tous les PAG version 2011 en vigueur)"),
    "de_bb": (fetch_de_bb, "Rechtswirksame Bebauungspläne Brandenburg, Landesamt für Bauen und "
              "Verkehr (PLIS WFS)", "no fees and no access constraints (service capabilities)"),
    "de_mv": (fetch_de_mv, "Bauleitpläne in MV, Ministerium für Inneres, Bau und Digitalisierung "
              "Mecklenburg-Vorpommern (geodaten-mv.de bauleitplan_wfs)", "dl-de/by-2-0"),
    "de_nrw": (fetch_de_nrw, "Bauleitpläne NRW (INSPIRE planned land use), Ministerium für "
               "Heimat, Kommunales, Bau und Digitalisierung NRW, opengeodata.nrw.de GeoPackage",
               "no public-access limitations (INSPIRE metadata); no licence named"),
    "de_berlin": (fetch_de_berlin, "Bebauungspläne Berlin, Senatsverwaltung für "
                  "Stadtentwicklung (gdi.berlin.de WFS bplan: in force and in procedure)",
                  "dl-de/zero-2-0"),
    "at_ooe": (fetch_at_ooe, "Flächenwidmungspläne Oberösterreich, Widmungen Flächen (DORIS, "
               "Land Oberösterreich, OGD shapefile FLWI_WIDMUNGEN_F)",
               "CC BY 4.0 (DORIS metadata 8FC62F91-E0F6-4DB0-91E1-9CBC329FFBA0)"),
    "nl_plu": (fetch_nl, "Gepland landgebruik DSO-LV Omgevingswet (INSPIRE geharmoniseerd), "
               "Kadaster via PDOK Atom download land_use.gml", "Public Domain Mark 1.0 (PDOK Atom feed)"),
    "es_siu": (fetch_es_siu, "Sistema de Información Urbana (SIU), Ministerio de Vivienda y "
               "Agenda Urbana: clases de suelo and planeamiento vigente per municipality (ArcGIS "
               "mapas.fomento.gob.es SIU)", "CC BY 4.0 (data.europa.eu record of the SIU)"),
    "cz_praha": (fetch_cz_praha, "Plán využití ploch, funkční plochy (územní plán hl. m. Prahy), "
                 "IPR Praha (ArcGIS PUP_CUR_PVP_FVU_P)", "CC BY (ArcGIS item licence)"),
    "lv_riga": (fetch_lv_riga, "Rīgas teritorijas plānojums (spēkā), funkcionālais zonējums, "
                "Rīgas valstspilsētas pašvaldība (data.gov.lv GeoPackage)", "CC BY 4.0"),
    "ee_plan": (fetch_ee, "Maa- ja Ruumiamet planeeringute infosüsteem (PLANK): general plan "
                "land use (yld_plan_maakas) and detailed plan areas (detail_plan_ala), WFS "
                "gsavalik.envir.ee planeeringud", "no fees, no access constraints (service)"),
    "at_tirol": (fetch_at_tirol, "Flächenwidmung Tirol, Land Tirol (ArcGIS FeatureServer "
                 "FLW_Flaechenwidmung)", "no licence stated on the service"),
    "at_bgld": (fetch_at_bgld, "Flächenwidmung Burgenland, INSPIRE Planned Land Use "
                "ZoningElement (hale connect WFS)", "otherRestrictions, not named (service)"),
    "at_wien": (fetch_at_wien, "Generalisierter Flächenwidmungs- und Bebauungsplan, Stadt Wien "
                "(data.wien.gv.at WFS ogdwien:GENFLWIDMUNGOGD)", "CC BY 3.0 AT (Stadt Wien)"),
    "pt_crus": (fetch_pt_crus, "Carta do Regime de Uso do Solo (CRUS), Direção-Geral do "
                "Território, national WFS SDISNITWFSCRUS (mainland Portugal)", "CC BY 4.0 (DGT)"),
}  # fmt: skip

STANDARD = ["country", "authority", "plan_id", "plan_name", "plan_status", "adopted", "zone_code", "zone_label", "class_code", "class", "doc_url"]  # fmt: skip


def _split_lines(path: Path, size: int) -> list[Path]:
    """Split an NDJSON file into parts of about `size` bytes, each ending on a whole line."""
    parts: list[Path] = []
    out = None
    with path.open("rb") as f:
        for line in f:
            if out is None or out.tell() >= size:
                if out:
                    out.close()
                parts.append(path.with_name(f"{path.stem}.part{len(parts):03d}{path.suffix}"))
                out = parts[-1].open("wb")
            out.write(line)
    if out:
        out.close()
    return parts or [path]


def select_sql(source: str, path: Path) -> str:
    if source == "gb_england":
        parts = []
        for d in ENGLAND:
            csv = path.with_name(f"{d}.csv")
            with csv.open(encoding="utf-8", errors="replace") as f:
                head = set(f.readline().strip().split(","))
            # Landscape outlines run to several MB a line (AONB 7.1 MB); DuckDB stops at 2 MB
            # unless told the longest line, so measure it (bytes, as DuckDB counts).
            with csv.open("rb") as f:
                longest = max((len(line) for line in f), default=0)
            size = f", max_line_size={longest + 1024}" if longest > 2_000_000 else ""

            def col(*names: str, head: set[str] = head) -> str:
                got = [f"nullif(\"{n}\", '')" for n in names if n in head]
                return f"coalesce({', '.join(got)})" if got else "NULL"

            geo = col("geometry", "point")
            parts.append(
                f"SELECT 'GB' AS country, "
                f"{col('organisation', 'organisations', 'organisation-entity')} AS authority, "
                f"reference AS plan_id, name AS plan_name, "
                f"CASE WHEN {col('end-date')} IS NULL THEN 'in force' ELSE 'ended' END "
                f"AS plan_status, {col('adopted-date', 'start-date')} AS adopted, "
                f"'{d}' AS zone_code, name AS zone_label, '{d}' AS class_code, "
                f"'{ENGLAND_CLASS.get(d, 'designation')}' AS class, "
                f"{col('document-url', 'documentation-url')} AS doc_url, "
                f"to_json(t) AS attributes, "
                f"CASE WHEN {geo} IS NULL THEN NULL ELSE ST_GeomFromText({geo}) END AS geometry "
                f"FROM read_csv('{csv}', all_varchar=true{size}) t "
            )
        return " UNION ALL ".join(parts)
    m = MAPS[source]
    cols = ", ".join(f"({m[k]})::VARCHAR AS {k}" for k in STANDARD)
    return (
        f"SELECT {cols}, a AS attributes, "
        f"CASE WHEN g IS NULL THEN NULL ELSE ST_GeomFromGeoJSON(g::VARCHAR) END AS geometry "
        f"FROM read_json('{path}', format='newline_delimited', "
        f"columns={{'a': 'JSON', 'g': 'JSON'}}, maximum_object_size=200000000)"
    )


def make_valid(con: duckdb.DuckDBPyConnection, s: str) -> None:
    """Repair invalid geometries; a geometry GEOS cannot repair is kept as published."""
    fix = "ST_MakeValid(ST_Force2D(geometry))"
    try:
        con.execute(f"UPDATE z SET geometry = {fix} WHERE NOT ST_IsValid(geometry)")
        return
    except duckdb.Error:
        pass
    ids = [
        r[0] for r in con.execute("SELECT rowid FROM z WHERE NOT ST_IsValid(geometry)").fetchall()
    ]
    kept = 0
    for i in ids:
        try:
            con.execute(f"UPDATE z SET geometry = {fix} WHERE rowid = ?", [i])
        except duckdb.Error:
            kept += 1
    print(
        f"  {s}: {len(ids):,} invalid geometries, {kept:,} kept as published (GEOS cannot repair)"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", choices=list(SOURCES))
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--tmp", type=Path, default=Path("/tmp/zoning"))
    ap.add_argument("--limit", type=int, default=None, help="features per layer (tests)")
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    args.tmp.mkdir(parents=True, exist_ok=True)
    # A database file, not memory: the Netherlands' 5,705 municipality-wide zones ran a
    # 12 GB runner out of memory while writing; tables and sorts spill to disk this way.
    db = args.tmp / "build.duckdb"
    db.unlink(missing_ok=True)
    con = duckdb.connect(str(db))
    con.execute("INSTALL spatial; LOAD spatial; SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory = '{args.tmp / 'spill'}'; SET memory_limit = '8GB'")
    with httpx.Client(timeout=300, headers=UA, follow_redirects=True) as c:
        for s in args.sources:
            fetch, source, licence = SOURCES[s]
            raw = args.tmp / f"{s}.ndjson"
            raw.unlink(missing_ok=True)
            fetch(c, raw, args.limit)
            lake = Lake("zoning", args.lake, source=source, licence=licence, script=SCRIPT)
            if args.upload:
                lake.pull_catalog()
            # Each read_json thread holds whole objects in memory; the Netherlands' raw file
            # (municipality-wide geometries) ran 8 GB out with every core reading at once.
            gb = (
                raw.stat().st_size / 1e9 if raw.exists() else 0.0
            )  # England reads its CSVs directly
            print(f"  {s}: raw NDJSON {gb:.1f} GB", flush=True)
            con.execute(f"SET threads = {1 if gb > 2 else os.cpu_count() or 4}")
            parts = _split_lines(raw, 256_000_000) if gb > 2 else [raw]
            con.execute(f"CREATE OR REPLACE TABLE z AS {select_sql(s, parts[0])}")
            # A big raw file is read in parts of whole lines: one read_json over 5.5 GB still
            # ran 8 GB out even on one thread.
            for part in parts[1:]:
                con.execute(f"INSERT INTO z {select_sql(s, part)}")
                part.unlink()
            if len(parts) > 1:
                parts[0].unlink()
            make_valid(con, s)
            n, nogeo = con.execute(
                "SELECT count(*), count(*) FILTER (WHERE geometry IS NULL) FROM z"
            ).fetchone()  # type: ignore[misc]
            bad = sorted(
                set(r[0] for r in con.execute("SELECT DISTINCT class FROM z").fetchall())
                - set(VOCAB)
            )
            if bad:
                raise SystemExit(f"{s}: classes outside the vocabulary: {bad}")
            print(f"  {s}: {n:,} zones ({nogeo:,} without geometry, kept)", flush=True)
            print("  classes:", con.execute(
                "SELECT class, count(*) FROM z GROUP BY 1 ORDER BY 2 DESC").fetchall(), flush=True)  # fmt: skip
            lake.write(
                con, "zones", f"SELECT '{s}' AS source, * FROM z",
                sort=[hilbert("geometry")], bloom=["country", "class", "plan_id"],
                partition={"source": s}, geometry="geometry",
                meta={"refresh": "on demand (scripts/build_zoning.py)"},
                group_rows=128 if gb > 2 else None,  # rows of ~1 MB: files of 128 rows
            )  # fmt: skip
            lake.finish()
            if args.upload:
                lake.upload()


if __name__ == "__main__":
    main()
