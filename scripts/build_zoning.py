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
  gb_england    England, planning.data.gov.uk: green belt, conservation areas, article 4
                directions, brownfield land

    uv run python scripts/build_zoning.py fr_gpu ie_myplan --lake lake-out [--upload]
    uv run python scripts/build_zoning.py ie_myplan --limit 5000   # a quick local test

In GitHub Actions: Lake catalogue > Run workflow with `zoning` = all (or a list of sources);
`zoning` = discover runs scripts/zoning_discover.py (both sweeps) and keeps the CSVs.
"""

from __future__ import annotations

import argparse
import json
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
    # England: each dataset is one designation.
    "gb_england": {},
    "fi_helsinki": {},
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
    c: httpx.Client, layer: str, *, limit: int | None = None, order: str = "OBJECTID"
) -> Iterator[dict[str, Any]]:
    """ArcGIS FeatureServer layer as GeoJSON in EPSG:4326, paged by resultOffset."""
    page = int(_get(c, layer, {"f": "json"}).json().get("maxRecordCount") or 1000)
    start = 0
    while True:
        n = min(page, limit - start) if limit else page
        params = {"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
                  "resultOffset": start, "resultRecordCount": n, "orderByFields": order}  # fmt: skip
        feats = _get(c, f"{layer}/query", params).json().get("features") or []
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


ENGLAND = ("green-belt", "conservation-area", "article-4-direction-area", "brownfield-land")


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
    "gb_england": (fetch_gb, "planning.data.gov.uk (MHCLG): green belt, conservation area, "
                   "article 4 direction area, brownfield land", "OGL 3.0"),
}  # fmt: skip

STANDARD = ["country", "authority", "plan_id", "plan_name", "plan_status", "adopted", "zone_code", "zone_label", "class_code", "class", "doc_url"]  # fmt: skip


def select_sql(source: str, path: Path) -> str:
    if source == "gb_england":
        parts = []
        for d in ENGLAND:
            csv = path.with_name(f"{d}.csv")
            doc = '"document-url"' if d == "conservation-area" else "NULL"
            parts.append(
                f"SELECT 'GB' AS country, organisation AS authority, reference AS plan_id, "
                f'name AS plan_name, CASE WHEN "end-date" IS NULL OR "end-date" = \'\' '
                f"THEN 'in force' ELSE 'ended' END AS plan_status, \"start-date\" AS adopted, "
                f"'{d}' AS zone_code, name AS zone_label, '{d}' AS class_code, "
                f"'designation' AS class, "
                f"{doc} AS doc_url, "
                f"to_json(t) AS attributes, ST_GeomFromText(coalesce(nullif(geometry, ''), "
                f"nullif(point, ''))) AS geometry "
                f"FROM read_csv('{csv}', all_varchar=true) t "
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", choices=list(SOURCES))
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--tmp", type=Path, default=Path("/tmp/zoning"))
    ap.add_argument("--limit", type=int, default=None, help="features per layer (tests)")
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    args.tmp.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET preserve_insertion_order=false")
    with httpx.Client(timeout=300, headers=UA, follow_redirects=True) as c:
        for s in args.sources:
            fetch, source, licence = SOURCES[s]
            raw = args.tmp / f"{s}.ndjson"
            raw.unlink(missing_ok=True)
            fetch(c, raw, args.limit)
            lake = Lake("zoning", args.lake, source=source, licence=licence, script=SCRIPT)
            if args.upload:
                lake.pull_catalog()
            con.execute(f"CREATE OR REPLACE TABLE z AS {select_sql(s, raw)}")
            con.execute(
                "UPDATE z SET geometry = ST_MakeValid(geometry) WHERE NOT ST_IsValid(geometry)"
            )
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
            )  # fmt: skip
            lake.finish()
            if args.upload:
                lake.upload()


if __name__ == "__main__":
    main()
