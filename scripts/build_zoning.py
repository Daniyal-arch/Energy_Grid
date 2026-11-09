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
  be_wallonia   Belgium, Wallonia: plan de secteur in force, zones d'affectation (SPW)
  es_barcelona  Spain, Mapa Urbanístic de Catalunya for the province of Barcelona
                (Diputació de Barcelona service): land qualification and classification
  lu_pag        Luxembourg, PAG zones of every commune (INSPIRE OGC API Features)
  de_berlin     Germany, Berlin: B-Plan outlines in force and in procedure, with PDF links
  at_ooe        Austria, Upper Austria: Flächenwidmung zones (DORIS)

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
    "at_ooe": {},
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


def _count(c: httpx.Client, layer: str) -> int:
    return int(_get(c, f"{layer}/query", {"where": "1=1", "returnCountOnly": "true",
                                          "f": "json"}).json()["count"])  # fmt: skip


def _arcgis_all(c: httpx.Client, out: Path, layer: str, limit: int | None,
                extra: dict[str, Any], tag: str) -> None:  # fmt: skip
    """A whole ArcGIS layer; stops when the rows read differ from the service's count."""
    total = _count(c, layer)
    n = _ndjson(out, arcgis(c, layer, limit=limit), extra)
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
    rows = con.execute(
        f"SELECT * EXCLUDE ({gcol}), ST_AsGeoJSON({geo}) AS __g FROM st_read(?, layer = ?) "
        f"{f'LIMIT {limit}' if limit else ''}", [url, layer])  # fmt: skip
    names = [d[0] for d in rows.description]
    n = 0
    with out.open("a", encoding="utf-8") as f:
        while batch := rows.fetchmany(10_000):
            for r in batch:
                props = {k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v))
                         for k, v in zip(names[:-1], r[:-1])}  # fmt: skip
                g = json.loads(r[-1]) if r[-1] else None
                f.write(json.dumps({"a": {**props, **extra}, "g": g}, ensure_ascii=False) + "\n")
                n += 1
    print(f"  {tag}: {n:,} (GDAL counts {total:,}; CRS {crs})", flush=True)
    if not limit and total is not None and total >= 0 and n != total:
        raise SystemExit(f"{tag}: {n:,} read, the layer counts {total:,}")


def fetch_lu(c: httpx.Client, out: Path, limit: int | None) -> None:
    _ogr(out, "OAPIF:https://wms.inspire.geoportail.lu/geoserver/lu/ogc/features/v1",
         "LU.SpatialPlan.PAG", limit, {}, "lu PAG", latlon=True)  # fmt: skip


def fetch_de_berlin(c: httpx.Client, out: Path, limit: int | None) -> None:
    for layer, status in (("bplan:b_bp_fs", "in force"), ("bplan:a_bp_iv", "in procedure")):
        _ogr(out, "WFS:https://gdi.berlin.de/services/wfs/bplan", layer, limit,
             {"_status": status}, f"de-berlin {layer}")  # fmt: skip


def fetch_at_ooe(c: httpx.Client, out: Path, limit: int | None) -> None:
    _arcgis_all(c, out, "https://ags.doris.at/arcgis/rest/services/HVD/MapServer/12", limit, {},
                "at-ooe Widmungen Flächen")  # fmt: skip


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
    "at_ooe": {
        "country": "'AT'", "authority": a("GEM_NR"), "plan_id": a("GEM_NR"),
        "plan_name": "'Flächenwidmungsplan, Gemeinde ' || " + a("GEM_NR"),
        "plan_status": "'in force'", "adopted": "NULL", "zone_code": a("KENNZAHL"),
        "zone_label": a("ZUSATZTEXT"), "class_code": a("KENNZAHL"), "class": "'other'",
        "doc_url": "NULL",
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
    "be_wallonia": (fetch_be, "Plan de secteur en vigueur, Service public de Wallonie (SPW "
                    "Territoire), ArcGIS AMENAGEMENT_TERRITOIRE/PDS layer 22", "CC BY 4.0"),
    "es_barcelona": (fetch_es_bcn, "Mapa Urbanístic de Catalunya (Generalitat de Catalunya, "
                     "Departament de Territori), served for the province of Barcelona by the "
                     "Diputació de Barcelona (CARTOBASE/MUC)", "no licence stated on the service"),
    "lu_pag": (fetch_lu, "Plans d'aménagement général (PAG) of every commune, INSPIRE Planned "
               "Land Use, Administration du cadastre et de la topographie (geoportail.lu, OGC API "
               "Features LU.SpatialPlan.PAG)",
               "CC0 (data.public.lu, PAG géométries de tous les PAG version 2011 en vigueur)"),
    "de_berlin": (fetch_de_berlin, "Bebauungspläne Berlin, Senatsverwaltung für "
                  "Stadtentwicklung (gdi.berlin.de WFS bplan: in force and in procedure)",
                  "dl-de/zero-2-0"),
    "at_ooe": (fetch_at_ooe, "Flächenwidmungspläne Oberösterreich, Widmungen Flächen (DORIS, "
               "Land Oberösterreich, ArcGIS HVD/MapServer layer 12)",
               "no licence stated on the service (owner question 9)"),
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
            )  # fmt: skip
            lake.finish()
            if args.upload:
                lake.upload()


if __name__ == "__main__":
    main()
