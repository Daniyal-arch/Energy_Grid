"""Wave 9 (docs/tasks/28-wave9-customer-needs.md): probe and build the sources of
scripts/wave9_sources.yaml.

    python scripts/wave9.py probe [--cat N] [--id ID]      # status, size, type, licence quote
    python scripts/wave9.py build --cat N [--upload]       # the `build` sources of a category
    python scripts/wave9.py search [--family F]             # open-data portal hits per country

Probe results go to `data/wave9_probes.json` (committed: the evidence behind every registry
cell and docs/research/wave9-sources.md). Builds go to the lake (`lake/w9_<id>/...`) and write
`data/wave9_built.json` (rows, columns and the answer of each table's example query).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave5_common as w  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# the wave this run serves (WAVE=10 for wave 10): its registry, lake dataset, app files and ids
WAVE = int(os.environ.get("WAVE", "9"))
WN = f"wave{WAVE}"  # lake dataset, registry and catalogue name
PFX = f"w{WAVE}"  # app folders (eu/w9, eu/w9c) and map ids (w9_<id>, w9c_<id>)
BRIEF = {9: "brief 28", 10: "brief 29"}.get(WAVE, f"wave {WAVE}")
REGISTRY = ROOT / "scripts" / f"{WN}_sources.yaml"
PROBES = ROOT / "data" / f"{WN}_probes.json"
SCRIPT = "scripts/wave9.py"
TMP = Path(f"/tmp/{WN}")
UA = w.UA
LICENCE_WORDS = re.compile(
    r"(licen[cs]e|commercial|CC[ -]BY|CC0|Open Government|Licence Ouverte|public domain|"
    r"copyright|terms of use|dl-de|ODbL|reuse|re-use)",
    re.I,
)


def sources(cat: int | None = None, sid: str | None = None) -> list[dict[str, Any]]:
    out = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["sources"]
    return [s for s in out if (cat is None or s["cat"] == cat) and (sid is None or s["id"] == sid)]


def text_of(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html))


def quotes(text: str, n: int = 3) -> list[str]:
    """Up to n sentences around licence words."""
    out: list[str] = []
    for m in LICENCE_WORDS.finditer(text):
        q = text[max(0, m.start() - 140) : m.end() + 160].strip()
        if not any(q[:60] in o for o in out):
            out.append("… " + q + " …")
        if len(out) >= n:
            break
    return out


def probe_one(s: dict[str, Any]) -> dict[str, Any]:
    """GET the source's URL (first 256 kB), and its licence page when it has one."""
    r: dict[str, Any] = {"id": s["id"], "url": s["url"], "checked": time.strftime("%Y-%m-%d")}
    t0 = time.time()
    try:
        with httpx.Client(headers=UA, timeout=60, follow_redirects=True) as c:
            url = s["url"]
            if s.get("kind") == "arcgis" and "/wfs" not in url:
                meta = c.get(url, params={"f": "json"})
                r["http"] = meta.status_code
                j = meta.json() if meta.status_code == 200 else {}
                r["type"] = "arcgis layer"
                r["name"] = j.get("name")
                r["error"] = (j.get("error") or {}).get("message")
                cnt = c.get(
                    url + "/query",
                    params={"where": s.get("where", "1=1"), "returnCountOnly": "true", "f": "json"},
                )
                r["rows"] = (cnt.json() if cnt.status_code == 200 else {}).get("count")
            else:
                with c.stream("GET", url) as resp:
                    r["http"] = resp.status_code
                    r["final_url"] = str(resp.url) if str(resp.url) != url else None
                    r["type"] = resp.headers.get("content-type", "").split(";")[0]
                    length = resp.headers.get("content-length")
                    r["size"] = int(length) if length else None
                    head = b""
                    for chunk in resp.iter_bytes(65536):
                        head += chunk
                        if len(head) >= 262144:
                            break
                txt = head.decode("utf-8", "replace")
                if "html" in r["type"]:
                    page = text_of(txt)
                    r["title"] = (re.search(r"(?is)<title>(.*?)</title>", txt) or [None, None])[1]
                    r["quotes"] = quotes(page)
                elif "json" in r["type"] or txt.lstrip()[:1] in "[{":
                    r["sample"] = txt[:400]
                else:
                    r["sample"] = txt[:300] if txt.isprintable() or "\n" in txt[:300] else None
            if s.get("lic_url"):
                lp = c.get(s["lic_url"])
                r["lic_http"] = lp.status_code
                r["lic_quotes"] = quotes(text_of(lp.text))
    except (httpx.HTTPError, ValueError) as e:
        r["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    r["seconds"] = round(time.time() - t0, 1)
    return r


def probe(args: argparse.Namespace) -> None:
    todo = sources(args.cat, args.id)
    old = json.loads(PROBES.read_text(encoding="utf-8")) if PROBES.exists() else {}
    with cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(probe_one, todo):
            old[r["id"]] = r
            size = f"{r['size'] / 1e6:,.1f} MB" if r.get("size") else "?"
            rows = f", {r['rows']:,} rows" if r.get("rows") is not None else ""
            lic = (r.get("lic_quotes") or r.get("quotes") or [""])[0][:110]
            print(
                f"{r['id']}: HTTP {r.get('http')} {r.get('type') or ''} {size}{rows} "
                f"{r.get('error') or ''} | {lic}",
                flush=True,
            )
    PROBES.write_text(json.dumps(old, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


FAMILIES = ROOT / "scripts" / f"{WN}_families.yaml"
SEARCH = ROOT / "data" / f"{WN}_search.json"


def families() -> dict[str, dict[str, Any]]:
    return yaml.safe_load(FAMILIES.read_text(encoding="utf-8"))["families"]


def search_one(fam: str, q: str) -> dict[str, Any]:
    """The open datasets a query finds: per EU country on data.europa.eu, on catalog.data.gov
    and on data.gov.uk (top three titles and the count): evidence for a dark cell."""
    from coverage import EU27

    out: dict[str, Any] = {}
    with httpx.Client(headers=UA, timeout=60) as c:
        for cc in EU27:
            try:
                r = c.get(
                    "https://data.europa.eu/api/hub/search/search",
                    params={
                        "q": f'"{q}"',  # the phrase, not its words ORed
                        "filters": "dataset",
                        "limit": 3,
                        "facets": json.dumps({"country": [cc.lower()]}),
                    },
                ).json()["result"]
                titles = [
                    (x.get("title") or {}).get("en")
                    or next(iter((x.get("title") or {}).values()), "")
                    for x in r["results"]
                ]
                out[cc] = {
                    "count": r["count"],
                    "top": [t[:90] for t in titles],
                    "portal": "data.europa.eu",
                }
            except (httpx.HTTPError, ValueError, KeyError) as e:
                out[cc] = {"error": type(e).__name__, "portal": "data.europa.eu"}
        try:
            r = c.get("https://catalog.data.gov/search", params={"q": q}).json()
            out["US"] = {
                "count": r.get("total") or len(r.get("results") or []),
                "top": [
                    ((x.get("dcat") or {}).get("title") or "")[:90]
                    for x in (r.get("results") or [])[:3]
                ],
                "portal": "catalog.data.gov",
            }
        except (httpx.HTTPError, ValueError) as e:
            out["US"] = {"error": type(e).__name__, "portal": "catalog.data.gov"}
        try:
            r = c.get(
                "https://ckan.publishing.service.gov.uk/api/action/package_search",
                params={"q": q, "rows": 3},
            ).json()["result"]
            out["GB"] = {
                "count": r["count"],
                "top": [x["title"][:90] for x in r["results"]],
                "portal": "data.gov.uk",
            }
        except (httpx.HTTPError, ValueError, KeyError) as e:
            out["GB"] = {"error": type(e).__name__, "portal": "data.gov.uk"}
    return {"query": q, "checked": time.strftime("%Y-%m-%d"), "hits": out}


def search(args: argparse.Namespace) -> None:
    fams = families()
    todo = [args.family] if args.family else list(fams)
    old = json.loads(SEARCH.read_text(encoding="utf-8")) if SEARCH.exists() else {}
    with cf.ThreadPoolExecutor(6) as ex:
        for fam, res in zip(todo, ex.map(lambda f: search_one(f, fams[f]["q"]), todo), strict=True):
            old[fam] = res
            print(
                f"{fam}: " + " ".join(f"{k}:{v.get('count', '?')}" for k, v in res["hits"].items()),
                flush=True,
            )
    SEARCH.write_text(json.dumps(old, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


# ---------------------------------------------------------------------- build


def con_spatial():  # noqa: ANN201 - a DuckDB connection with spatial and httpfs
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs")
    con.execute("SET geometry_always_xy = true")
    return con


def safe_cols(con, table: str) -> None:  # noqa: ANN001
    """Column names in lower snake case (the lake's convention), the geometry as `geometry`."""
    for (name,) in con.execute(f"SELECT column_name FROM (DESCRIBE {table})").fetchall():
        new = re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_") or "col"
        if new[0].isdigit():
            new = "c_" + new
        if new in ("geom", "shape", "the_geom", "wkb_geometry", "geometrie"):
            new = "geometry"
        if new != name:
            try:
                con.execute(f'ALTER TABLE {table} RENAME COLUMN "{name}" TO "{new}"')
            except Exception as e:  # noqa: BLE001 - duplicate after cleaning: keep the original
                print(f"  column {name!r} kept ({type(e).__name__})", flush=True)


def first_file(folder: Path, exts: tuple[str, ...]) -> Path:
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in exts)
    if not files:
        raise SystemExit(f"no {exts} file in {folder}")
    return max(files, key=lambda p: p.stat().st_size)


def read_geo(con, path: Path, s: dict[str, Any]) -> None:  # noqa: ANN001
    """Any GDAL vector file into table t, geometry moved to WGS 84 from the layer's own CRS."""
    layer = f", layer = '{s['layer']}'" if s.get("layer") else ""
    con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM ST_Read('{path}'{layer})")
    crs = s.get("crs")
    if not crs:
        meta = con.execute(f"SELECT layers FROM ST_Read_Meta('{path}')").fetchone()[0]
        lyr = next((x for x in meta if not s.get("layer") or x["name"] == s["layer"]), meta[0])
        g = (lyr.get("geometry_fields") or [{}])[0].get("crs") or {}
        crs = f"{g.get('auth_name')}:{g.get('auth_code')}" if g.get("auth_code") else None
    geom = next(
        c
        for (c,) in con.execute("SELECT column_name FROM (DESCRIBE t)").fetchall()
        if c.lower() in ("geom", "geometry", "shape", "wkb_geometry")
    )
    if crs == "ESRI:104000":  # "GCS_Assumed_Geographic_1": degrees with no datum, as published
        crs = None
    # a new table, not UPDATE: a column typed with the file's CRS refuses other geometries
    g = f"ST_GeomFromWKB(ST_AsWKB({geom}))"
    if crs and crs not in ("EPSG:4326", "OGC:CRS84"):
        print(f"  {path.name}: {crs} to EPSG:4326", flush=True)
        g = f"ST_Transform({g}, '{crs}', 'EPSG:4326', always_xy := true)"
    con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * REPLACE ({g} AS {geom}) FROM t")


def arcgis_pages(s: dict[str, Any], dest: Path) -> Path:
    """Every feature of an ArcGIS layer, paged (its maxRecordCount), as one GeoJSON file."""
    meta = w.get_json(s["url"], params={"f": "json"})
    step = min(int(meta.get("maxRecordCount") or 1000), 2000)  # type: ignore[union-attr]
    feats: list[dict[str, Any]] = []
    while True:
        page = w.get_json(
            s["url"] + "/query",
            params={
                "where": s.get("where", "1=1"), "outFields": s.get("fields", "*"), "outSR": "4326", "f": "geojson",
                "resultOffset": len(feats), "resultRecordCount": step, "orderByFields": s.get("order", ""),
            },
            timeout=300,
        )  # fmt: skip
        got = page.get("features") or []  # type: ignore[union-attr]
        feats += got
        if len(feats) % 20000 < step:
            print(f"  {s['id']}: {len(feats):,} features", flush=True)
        if not got or not (page.get("exceededTransferLimit") or len(got) == step):  # type: ignore[union-attr]
            break
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return dest


# ENTSO-E time-series fields kept with each point (what the value is)
ENTSOE_META = ("businessType", "flowDirection.direction", "type_MarketAgreement.type", "mktPSRType",
               "psrType", "quantity_Measure_Unit.name", "price_Measure_Unit.name", "currency_Unit.name")  # fmt: skip


class KeyMissing(RuntimeError):
    """A source whose URL or headers need a key that is not in the environment."""


ENV_REF = re.compile(r"\{env:([A-Z0-9_]+)\}")


def with_keys(s: dict[str, Any]) -> dict[str, Any]:
    """`{env:NAME}` in url, urls or headers replaced by the environment's value (brief 30); a
    missing key raises KeyMissing, so the build is a skip that names the key."""

    def sub(v: Any) -> Any:
        if isinstance(v, str):
            for name in ENV_REF.findall(v):
                if not os.environ.get(name):
                    raise KeyMissing(f"{name} is not set: skipped (set it as a repo secret)")
            return ENV_REF.sub(lambda m: os.environ[m.group(1)], v)
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v

    return {k: sub(v) if k in ("url", "urls", "headers", "params") else v for k, v in s.items()}


STATE_FIPS = (  # noqa: SIM905
    "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 "
    "34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56 72"
).split()


def census_tracts(con, s: dict[str, Any], d: Path) -> None:  # noqa: ANN001
    """kind census: an ACS table per tract, state by state (the API answers one state's tracts
    at a time). `url` is the dataset endpoint, `get` the variables; values as published (the
    Census Bureau's negative codes such as -666666666 mark a missing estimate, kept)."""
    if not os.environ.get("CENSUS_API_KEY"):
        raise KeyMissing("CENSUS_API_KEY is not set: skipped (set it as a repo secret)")
    rows: list[list[str]] = []
    head: list[str] = []
    for st in STATE_FIPS:
        r = httpx.get(
            s["url"],
            params={
                "get": s["get"],
                "for": "tract:*",
                "in": f"state:{st}",
                "key": os.environ.get("CENSUS_API_KEY", ""),
            },
            timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        head, rows = data[0], rows + data[1:]
    f = d / "src.csv"
    import csv

    with f.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow([*head, "geoid"])
        for row in rows:
            rec = dict(zip(head, row, strict=False))
            wr.writerow([*row, f"{rec['state']}{rec['county']}{rec['tract']}"])
    con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{f}', all_varchar = true)")


def zip_member(folder: Path, s: dict[str, Any]) -> Path:
    """The table file of an unzipped archive: the one whose path matches `member` (a regex),
    else the first CSV or text file. A matching zip inside the zip (zip-in-zip, e.g. SMU's heat
    flow release) is unzipped in turn and read the same way with `inner`."""
    if not s.get("member"):
        return first_file(folder, (".csv", ".txt"))
    rx = re.compile(s["member"], re.I)
    hits = sorted(p for p in folder.rglob("*") if p.is_file() and rx.search(p.as_posix()))
    if not hits:
        raise SystemExit(f"no file matching {s['member']!r} in the archive")
    f = hits[0]
    if f.suffix.lower() == ".zip":
        return zip_member(w.unzip(f), {"member": s.get("inner")} if s.get("inner") else {})
    return f


def _entsoe_docs(client: httpx.Client, params: dict[str, str]) -> list[Any]:
    """The documents of one ENTSO-E request: plain XML, or a zip of XML documents (balancing
    data is often zipped); an acknowledgement (no data) gives none."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    q = {"securityToken": os.environ["ENTSOE_API_KEY"].strip(), **params}
    r = client.get("https://web-api.tp.entsoe.eu/api", params=q)
    if r.status_code != 200:
        return []
    blobs = [r.content]
    if r.content[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(r.content))
        blobs = [z.read(n) for n in z.namelist() if n.lower().endswith(".xml")]
    roots = [ET.fromstring(b) for b in blobs]
    return [x for x in roots if not x.tag.endswith("Acknowledgement_MarketDocument")]


def load(con, s: dict[str, Any]) -> None:  # noqa: ANN001
    """The source into DuckDB table t, by kind; `urls` (several files of one kind) are stacked."""
    if s.get("urls"):
        for i, u in enumerate(s["urls"]):
            load_one(con, {**s, "url": u, "id": f"{s['id']}/{i}"})
            con.execute(f"CREATE OR REPLACE TABLE part_{i} AS SELECT * FROM t")
        union = " UNION ALL BY NAME ".join(f"SELECT * FROM part_{i}" for i in range(len(s["urls"])))
        con.execute(f"CREATE OR REPLACE TABLE t AS {union}")
        return
    load_one(con, s)


def load_one(con, s: dict[str, Any]) -> None:  # noqa: ANN001
    kind, url = s["kind"], s["url"]
    d = TMP / s["id"]
    d.mkdir(parents=True, exist_ok=True)
    if kind == "ods_api":  # an Opendatasoft dataset: its CSV export (semicolons), as published
        url = url if "/exports/" in url else url.rstrip("/") + "/exports/csv"
        url += ("&" if "?" in url else "?") + "delimiter=%3B"
        s, kind = {**s, "url": url, "kind": "csv", "sep": ";"}, "csv"
    if kind == "census":
        census_tracts(con, s, d)
    elif kind == "parquet":  # (Geo)Parquet: read as is; a WKB `geometry` becomes a geometry
        f = w.download(url, d / "src.parquet", timeout=3600)
        con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_parquet('{f}')")
        cols = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE t)").fetchall())
        if cols.get("geometry") == "BLOB":
            con.execute(
                "CREATE OR REPLACE TABLE t AS SELECT * EXCLUDE (geometry), "
                "ST_GeomFromWKB(geometry) AS geometry FROM t"
            )
    elif (
        kind == "aqviewer"
    ):  # EEA AQ Viewer: a POSTed filter, a zipped CSV, one country and year at a time
        import io
        import zipfile

        frames = []
        for country in s["countries"]:
            for year in s["years"]:
                body = {"Page": 0, "SortBy": None, "SortAscending": True, "RequestFilter": {
                    "Country": {"FieldName": "Country", "Values": [country]},
                    "ReportingYear": {"FieldName": "ReportingYear", "Values": [str(year)]}}}  # fmt: skip
                r = httpx.post(url, json=body, headers=UA, timeout=600)
                r.raise_for_status()
                if r.content[:2] != b"PK":
                    continue  # no rows for this country and year
                z = zipfile.ZipFile(io.BytesIO(r.content))
                f = d / f"{country}_{year}.csv".replace(" ", "_")
                f.write_bytes(z.read(z.namelist()[0]))
                n = con.execute(
                    f"SELECT count(*) FROM read_csv('{f}', all_varchar = true)"
                ).fetchone()[0]
                if n >= 100_000:  # the viewer stops at 100,000 rows: a cut answer is not kept
                    raise SystemExit(
                        f"{country} {year}: {n} rows, the viewer's cap; split the request"
                    )
                frames.append(str(f))
        if not frames:
            raise SystemExit("no rows for any country and year")
        files = ", ".join(f"'{f}'" for f in frames)
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv([{files}], all_varchar = true, union_by_name = true)"
        )
    elif kind == "entsoe":  # brief 30: any Transparency document per area, points as published
        if not os.environ.get("ENTSOE_API_KEY"):
            raise KeyMissing("ENTSOE_API_KEY is not set: skipped (set it as a repo secret)")
        from datetime import UTC, datetime, timedelta

        import entsoe

        end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=int(s.get("days", 30)))
        stamp = {
            "periodStart": start.strftime("%Y%m%d%H%M"),
            "periodEnd": end.strftime("%Y%m%d%H%M"),
        }
        rows = []
        with httpx.Client(timeout=120) as client:
            for area in s["areas"]:
                eic = entsoe.AREA_EIC.get(area) or entsoe.ZONE_EIC.get(area)
                if not eic:
                    continue
                params = {
                    **{k: str(v) for k, v in s["params"].items()},
                    s["domain_param"]: eic,
                    **stamp,
                }
                docs = _entsoe_docs(client, params)
                for meta, points in [
                    p
                    for root in docs
                    for p in entsoe.points_of(root, s.get("value_tag", "quantity"))
                ]:
                    for t, minutes, value in points:
                        rows.append({"area": area, "start_utc": t.isoformat(), "minutes": minutes, "value": value,
                                     **{k: v for k, v in meta.items() if k in ENTSOE_META}})  # fmt: skip
        if not rows:
            raise SystemExit("no data for any area in the window")
        f = d / "src.json"
        f.write_text(json.dumps(rows), encoding="utf-8")
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array')"
        )
    elif kind == "datafair_agg":  # data-fair values_agg: nested counts flattened to rows
        data = w.get_json(url, timeout=600)
        fields = re.search(r"field=([^&]+)", url).group(1).split(";")  # type: ignore[union-attr]
        rows: list[dict[str, Any]] = []

        def walk(aggs: list[dict[str, Any]], keys: dict[str, Any], depth: int) -> None:
            for a in aggs:
                k = {**keys, fields[depth]: a.get("value")}
                if a.get("aggs") and depth + 1 < len(fields):
                    walk(a["aggs"], k, depth + 1)
                else:
                    rows.append({**k, "count": a.get("total")})

        walk(data.get("aggs") or [], {}, 0)  # type: ignore[union-attr]
        f = d / "src.json"
        f.write_text(json.dumps(rows), encoding="utf-8")
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array')"
        )
    elif kind == "arcgis":
        read_geo(con, arcgis_pages(s, d / "layer.geojson"), {**s, "crs": "EPSG:4326"})
    elif kind in ("shp_zip", "gpkg_zip", "geojson_zip"):
        z = w.unzip(w.download(url, d / "src.zip", timeout=3600))
        ext = {
            "shp_zip": (".shp", ".gml"),
            "gpkg_zip": (".gpkg",),
            "geojson_zip": (".geojson", ".json"),
        }
        if s.get("all_files"):  # every layer file of the zip (points and polygons), stacked
            files = sorted(p for p in z.rglob("*") if p.is_file() and p.suffix.lower() in ext[kind])
            for i, f in enumerate(files):
                read_geo(con, f, s)
                con.execute(
                    f"CREATE OR REPLACE TABLE zpart_{i} AS SELECT *, '{f.stem}' AS src_file FROM t"
                )
            union = " UNION ALL BY NAME ".join(
                f"SELECT * FROM zpart_{i}" for i in range(len(files))
            )
            con.execute(f"CREATE OR REPLACE TABLE t AS {union}")
        else:
            read_geo(con, first_file(z, ext[kind]), s)
    elif kind in ("geojson", "gpkg"):
        read_geo(con, w.download(url, d / f"src.{kind}", timeout=3600), s)
    elif kind in ("csv", "csv_zip", "csv_gz"):
        f = w.download(
            url,
            d
            / ("src.zip" if kind == "csv_zip" else "src.csv.gz" if kind == "csv_gz" else "src.csv"),
            timeout=3600,
            headers=s.get("headers"),
        )
        # Eurostat queues a large extraction (a SOAP "queued" answer) and serves it from its
        # cache once ready: ask again until the table comes
        for wait in range(40):
            if f.stat().st_size > 2000 or b"<queued>" not in f.read_bytes()[:2000]:
                break
            print(f"  Eurostat queued the extraction; asking again ({wait + 1})", flush=True)
            f.unlink()
            time.sleep(30)
            f = w.download(url, f, timeout=3600)
        if kind == "csv_zip":
            f = zip_member(w.unzip(f), s)
        if s.get("recode"):  # a legacy encoding DuckDB does not read: to UTF-8 first
            utf8 = f.with_suffix(".utf8.csv")
            utf8.write_text(f.read_bytes().decode(s["recode"], errors="replace"), encoding="utf-8")
            f = utf8
        parts = ["sample_size = -1", "ignore_errors = true", "header = true"]
        if s.get("sep"):
            parts.append(f"delim = '{s['sep']}'")
        if s.get("skip"):
            parts.append(f"skip = {s['skip']}")
        if s.get("encoding"):
            parts.append(f"encoding = '{s['encoding']}'")
        if s.get("varchar"):
            parts.append("all_varchar = true")
        opts = ", ".join(parts)
        con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{f}', {opts})")
    elif kind == "xlsx" and not (s.get("sheets") or s.get("pandas")):
        f = w.download(url, d / "src.xlsx", timeout=3600)
        con.execute("INSTALL excel; LOAD excel")
        sheet = f", sheet = '{s['sheet']}'" if s.get("sheet") else ""
        rng = f", range = '{s['range']}'" if s.get("range") else ""
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_xlsx('{f}'{sheet}{rng}, all_varchar = true)"
        )
    elif kind == "json":
        data = w.get_json(url, timeout=600)
        for k in (s.get("records") or "").split(".") if s.get("records") else []:
            data = data[k]  # type: ignore[index]
        if isinstance(data, dict):
            data = [data]
        if s.get(
            "coords"
        ):  # a nested [a, b] pair, e.g. "geometry.coordinates" (`latlon`: lat first)
            for rec in data:  # type: ignore[union-attr]
                v: Any = rec
                for k in s["coords"].split("."):
                    v = v.get(k) if isinstance(v, dict) else None
                if isinstance(v, list) and len(v) >= 2:
                    rec["lon"], rec["lat"] = (v[1], v[0]) if s.get("latlon") else (v[0], v[1])
                rec.pop(s["coords"].split(".")[0], None)  # the pair now lives in lon and lat
        f = d / "src.json"
        f.write_text(json.dumps(data))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000, sample_size = -1)"
        )
    elif kind == "socrata":
        rows: list[dict[str, Any]] = []
        while True:
            page = w.get_json(
                url, params={"$limit": 50000, "$offset": len(rows), "$order": ":id"}, timeout=600
            )
            rows += page  # type: ignore[arg-type]
            if len(page) < 50000:  # type: ignore[arg-type]
                break
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000, sample_size = -1)"
        )
    elif kind == "pxweb":  # a PxWeb table, every variable asked for (left out, it is summed away)
        meta = w.get_json(url, timeout=300)
        variables = meta.get("variables") or []  # type: ignore[union-attr]
        # the API refuses a request over its cell limit (403): the largest variable in batches
        limit = int(s.get("max_cells", 100_000))
        sizes = [len(v["values"]) for v in variables] or [1]
        cells = 1
        for n in sizes:
            cells *= n
        big = max(range(len(sizes)), key=lambda i: sizes[i])
        per = max(1, limit // max(1, cells // sizes[big]))
        rows = []
        for k in range(0, sizes[big], per):
            query = [
                {
                    "code": v["code"],
                    "selection": {"filter": "item", "values": v["values"][k : k + per]},
                }
                if i == big
                else {"code": v["code"], "selection": {"filter": "all", "values": ["*"]}}
                for i, v in enumerate(variables)
            ]
            body = {"query": query, "response": {"format": "json-stat2"}}
            r = httpx.post(url, json=body, headers=UA, timeout=600)
            r.raise_for_status()
            rows += jsonstat_rows(r.json())
            time.sleep(1)  # the APIs allow a few requests a second
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1)"
        )
    elif kind == "jsonstat":
        con.execute("CREATE OR REPLACE TABLE t AS SELECT * FROM (VALUES (1)) LIMIT 0")
        rows = jsonstat_rows(w.get_json(url, timeout=300))  # type: ignore[arg-type]
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1)"
        )
    elif kind == "odata":
        rows = []
        while True:
            page = w.get_json(url, params={"$top": 10000, "$skip": len(rows)}, timeout=600)
            got = page["value"]  # type: ignore[index]
            rows += got
            if len(got) < 10000:
                break
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000, sample_size = -1)"
        )
    elif kind == "ckan":
        # the newest CSV (or `fmt`) resource of the first package the search finds
        res = w.get_json(url)["result"]  # type: ignore[index]
        if isinstance(res, list):  # package_list names packages only: no resources to pick from
            raise SystemExit(
                f"CKAN answered a list of {len(res)} names: use package_show?id=<name>"
            )
        pkgs = res.get("results", [res])
        fmt = (s.get("fmt") or "csv").lower()
        cand = [
            r for p in pkgs[: s.get("packages", 1)] for r in p["resources"]
            if (r.get("format") or "").lower() == fmt and re.search(s.get("match", ""), r.get("name") or r.get("url") or "", re.I)
        ]  # fmt: skip
        if not cand:
            raise SystemExit(f"no {fmt} resource in {[p['name'] for p in pkgs[:3]]}")
        r0 = max(cand, key=lambda r: r.get("last_modified") or r.get("created") or "")
        print(f"  CKAN resource: {r0.get('name')} {r0['url']}", flush=True)
        load_one(con, {**s, "kind": fmt if fmt != "geojson" else "geojson", "url": r0["url"]})
    elif kind == "sciencebase":
        item = w.get_json(url, params={"format": "json"})
        files = [
            f
            for f in item.get("files", []) + [x for a in item.get("attachments", []) for x in [a]]
            if re.search(s["match"], f.get("name", ""), re.I)
        ]  # type: ignore[union-attr]
        if not files:
            raise SystemExit(f"no file matching {s['match']} in the ScienceBase item")
        f0 = files[0]
        print(
            f"  ScienceBase file: {f0['name']} ({(f0.get('size') or 0) / 1e6:,.1f} MB)", flush=True
        )
        load_one(con, {**s, "kind": s["inner"], "url": f0["url"]})
    elif kind in ("ods", "xls", "xlsx"):  # xlsx here when `sheets` or `pandas` is set
        import pandas as pd

        f = w.download(
            url,
            d / ("src.zip" if url.split("?")[0].endswith(".zip") else f"src.{kind}"),
            timeout=3600,
        )
        if f.suffix == ".zip":  # a workbook inside a zip: the member named by `member`
            f = next(
                p
                for p in sorted(w.unzip(f).rglob("*"))
                if p.is_file() and re.search(s["member"], p.name, re.I)
            )
        book = pd.ExcelFile(f, engine="odf" if kind == "ods" else None)
        # the first sheet that is not a cover, contents or notes page (or the one named)
        skip = re.compile(r"cover|content|note|info|about|meta|guidance", re.I)
        sheet = s.get("sheet") or next(
            (n for n in book.sheet_names if not skip.search(n)), book.sheet_names[0]
        )
        # `sheets`: every sheet whose name matches, stacked with its name in column `sheet`
        names = (
            [n for n in book.sheet_names if re.search(s["sheets"], n)]
            if s.get("sheets")
            else [sheet]
        )
        print(
            f"  sheet(s) {names[:6]}{' ...' if len(names) > 6 else ''} of {len(book.sheet_names)}",
            flush=True,
        )
        parts = []
        for name in names:
            raw = book.parse(name, header=None, dtype=str)
            # the header is the first row with at least three filled cells (title rows come first)
            filled = raw.head(40).notna().sum(axis=1)
            h = int(next(i for i, n in filled.items() if n >= max(3, 0.6 * filled.max())))
            body = raw.iloc[h + 1 :].copy()
            cols = [str(c) if str(c) != "nan" else f"col_{i}" for i, c in enumerate(raw.iloc[h])]
            # one name per column across sheets (headers differ in spaces and line breaks)
            cols = [
                re.sub(r"[^0-9a-z]+", "_", c.lower()).strip("_") or f"col_{i}"
                for i, c in enumerate(cols)
            ]
            body.columns = [c if c not in cols[:i] else f"{c}_{i}" for i, c in enumerate(cols)]
            if s.get("sheets"):
                body.insert(0, "sheet", name)
            parts.append(body.dropna(how="all"))
        out = d / "src.csv"
        pd.concat(parts, ignore_index=True).to_csv(out, index=False)
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{out}', all_varchar = true, header = true)"
        )
    elif kind == "fwf":  # a fixed-width text table with a header line and a dashes line
        import pandas as pd

        f = w.download(url, d / "src.txt", timeout=600)
        tab = pd.read_fwf(f, skiprows=[1], dtype=str)
        out = d / "src.csv"
        tab.to_csv(out, index=False)
        con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{out}', header = true)")
    elif kind == "govuk":
        # a gov.uk publication: the attachment whose title matches, loaded by its file type
        page = w.get_json("https://www.gov.uk/api/content/government/" + url)
        att = [
            a
            for a in page["details"]["attachments"]
            if re.search(s["match"], a.get("title", ""), re.I)
        ]  # type: ignore[index]
        if not att:
            raise SystemExit(f"no attachment matching {s['match']}")
        a = att[0]
        print(f"  gov.uk attachment: {a['title'][:80]} {a['url']}", flush=True)
        ext = a["url"].rsplit(".", 1)[-1].lower()
        load_one(
            con,
            {
                **s,
                "kind": {"ods": "ods", "xlsx": "xlsx", "csv": "csv", "xls": "xls"}[ext],
                "url": a["url"],
            },
        )
    elif kind == "dirlist":
        # the newest file of a directory listing whose name matches
        page = httpx.get(url, headers=UA, timeout=120, follow_redirects=True).text
        names = sorted(set(re.findall(s["match"], page)))
        if not names:
            raise SystemExit(f"no file matching {s['match']} in {url}")
        print(f"  newest file: {names[-1]}", flush=True)
        load_one(con, {**s, "kind": s["inner"], "url": url.rstrip("/") + "/" + names[-1]})
    elif kind == "eurostat_tsv":
        # a Eurostat table too big for one SDMX-CSV extraction (HTTP 413 above 5 million rows):
        # the same API's gzipped TSV (no row cap, one column per period), turned long like the
        # SDMX-CSV tables: one column per dimension, time_period, obs_value, obs_flag
        f = w.download(url, d / "src.tsv.gz", timeout=3600)
        con.execute(
            f"CREATE OR REPLACE TABLE raw AS SELECT * FROM read_csv('{f}', delim = '\\t', header = true, all_varchar = true, compression = 'gzip')"
        )
        first = con.execute("SELECT column_name FROM (DESCRIBE raw) LIMIT 1").fetchone()[0]
        dims = [x.strip().lower() for x in first.split("\\")[0].split(",")]
        keys = ", ".join(
            f'split_part("{first}", \',\', {i + 1}) AS "{n}"' for i, n in enumerate(dims)
        )
        con.execute(
            f"""CREATE OR REPLACE TABLE t AS
            WITH u AS (UNPIVOT raw ON COLUMNS(* EXCLUDE ("{first}")) INTO NAME time_period VALUE raw_value)
            SELECT {keys}, trim(time_period) AS time_period,
                   TRY_CAST(regexp_extract(raw_value, '^\\s*(-?[0-9.]+(e-?[0-9]+)?)', 1) AS DOUBLE) AS obs_value,
                   nullif(trim(regexp_replace(raw_value, '^[\\s:0-9.e-]+', '')), '') AS obs_flag
            FROM u WHERE trim(raw_value) NOT IN (':', '')"""
        )
        con.execute("DROP TABLE raw")
    elif kind == "wdi":
        # a World Bank WDI indicator: every country and aggregate, every year (CC BY 4.0); the
        # aggregates (regions, income groups) are marked from the country list
        meta = w.get_json("https://api.worldbank.org/v2/country?format=json&per_page=400")
        agg = {
            c["iso2Code"] for c in meta[1] if (c.get("region") or {}).get("value") == "Aggregates"
        }  # type: ignore[index]
        rows, page = [], 1
        while True:
            r = w.get_json(f"{url}&per_page=20000&page={page}", timeout=300)
            for x in r[1] or []:  # type: ignore[index]
                rows.append({
                    "indicator": x["indicator"]["id"], "indicator_name": x["indicator"]["value"],
                    "iso2": x["country"]["id"], "iso3": x["countryiso3code"], "country": x["country"]["value"],
                    "aggregate": x["country"]["id"] in agg, "year": int(x["date"]), "value": x["value"],
                    "unit": x.get("unit") or "", "obs_status": x.get("obs_status") or "",
                })  # fmt: skip
            if page >= int(r[0]["pages"]):  # type: ignore[index]
                break
            page += 1
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', "
            "columns = {indicator: 'VARCHAR', indicator_name: 'VARCHAR', iso2: 'VARCHAR', iso3: 'VARCHAR', "
            "country: 'VARCHAR', aggregate: 'BOOLEAN', year: 'INTEGER', value: 'DOUBLE', unit: 'VARCHAR', "
            "obs_status: 'VARCHAR'})"
        )
    elif kind == "custom":
        CUSTOM[s["id"]](con, s, d)
    else:
        raise SystemExit(f"kind {kind} is not built")


def jsonstat_rows(d: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON-stat 2.0 to one row per cell: a label per dimension and the value."""
    ids, sizes, dims = d["id"], d["size"], d["dimension"]
    labels = []
    for k in ids:
        cat = dims[k]["category"]
        index = cat["index"]
        order = sorted(index, key=index.get) if isinstance(index, dict) else index
        labels.append([(c, (cat.get("label") or {}).get(c, c)) for c in order])
    values = d["value"]
    out = []
    n = 1
    for x in sizes:
        n *= x
    for i in range(n):
        v = values.get(str(i)) if isinstance(values, dict) else values[i]
        rest, row = i, {}
        for k, size, lab in zip(reversed(ids), reversed(sizes), reversed(labels), strict=True):
            code, label = lab[rest % size]
            rest //= size
            row[k] = label
            row[k + "_code"] = code
        row["value"] = v
        out.append(row)
    return out


CUSTOM: dict[str, Any] = {}


def overture_comm_lines(con, s: dict[str, Any], d: Path) -> None:  # noqa: ANN001
    """OSM communication lines through Overture's base/infrastructure theme (class
    communication_line) in the Europe box, read in place from Overture's public bucket (no
    credentials: the R2 keys in AWS_* would be refused there); OSM tags kept as published."""
    con.execute(
        "CREATE OR REPLACE SECRET overture (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2', "
        "SCOPE 's3://overturemaps-us-west-2')"
    )
    con.execute(
        f"""CREATE OR REPLACE TABLE t AS
            SELECT id, class, subtype, names.primary AS name, source_tags,
                   ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry
            FROM read_parquet('{s["url"]}', hive_partitioning = false)
            WHERE class = 'communication_line'
              AND bbox.xmin < 45 AND bbox.xmax > -25 AND bbox.ymin < 72 AND bbox.ymax > 34"""
    )


CUSTOM["eur_overture_comm_lines"] = overture_comm_lines


def build_raster(s: dict[str, Any]) -> dict[str, Any]:
    """A raster source (kind raster, brief 30): each file in `url`/`urls` (GeoTIFF, NetCDF with
    `var`, or a zip with `member`) becomes one cloud-optimised GeoTIFF, values as published, in
    the private lake: `lake/rasters/<wave>/<id>[_<n>].tif`. The build record keeps the CRS, cell
    size, band, unit and the min and max of the band (read on an overview) so the
    catalogue can describe it; area_stats reads it through agent/rasters_waves.yaml."""
    import subprocess
    import zipfile

    import rasterio

    t0 = time.time()
    urls = s.get("urls") or [s["url"]]
    d = TMP / s["id"]
    d.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    for i, url in enumerate(urls):
        name = url.split("?")[0].rsplit("/", 1)[-1] or f"src{i}"
        src = d / name
        if not src.exists():
            with httpx.stream("GET", url, headers=UA, timeout=600, follow_redirects=True) as r:
                r.raise_for_status()
                with src.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as z:
                member = s.get("member") or next(
                    m for m in z.namelist() if m.lower().endswith((".tif", ".tiff", ".nc", ".asc"))
                )
                z.extract(member, d)
                src = d / member
        inputs.append(f'NETCDF:"{src}":{s["var"]}' if s.get("var") else str(src))
    # several files (tiles) become one mosaic: one COG per source
    gd = inputs[0]
    if len(inputs) > 1:
        gd = str(d / "mosaic.vrt")
        subprocess.run(["gdalbuildvrt", gd, *inputs], check=True)
    out = d / f"{s['id']}.tif"
    cmd = ["gdal_translate", "-of", "COG", "-co", "COMPRESS=ZSTD", "-co", "PREDICTOR=YES"]
    if isinstance(s.get("band"), int):  # a band number; a text `band` only describes it
        cmd += ["-b", str(s["band"])]
    if s.get("assign_crs"):  # a file without a CRS: the one its publisher states
        cmd += ["-a_srs", s["assign_crs"]]
    subprocess.run([*cmd, gd, str(out)], check=True)
    with rasterio.open(out) as r:
        a = r.read(1, masked=True, out_shape=(min(r.height, 2000), min(r.width, 2000)))
        files = [
            {
                "key": f"lake/rasters/{WN}/{out.name}",
                "bytes": out.stat().st_size,
                "crs": str(r.crs),
                "cell": [abs(r.transform.a), abs(r.transform.e)],
                "size": [r.width, r.height],
                "bounds": [round(x, 4) for x in r.bounds],
                "nodata": r.nodata,
                "dtype": r.dtypes[0],
                # on a read of at most 2,000 x 2,000 cells (an overview): a description only
                "min": float(a.min()) if a.count() else None,
                "max": float(a.max()) if a.count() else None,
            }
        ]
    if UPLOAD["on"]:
        subprocess.run(
            ["aws", "s3", "cp", "--only-show-errors", "--endpoint-url",
             f"https://{w.env('CLOUDFLARE_ACCOUNT_ID')}.r2.cloudflarestorage.com",
             str(out), f"s3://infraatlas-raw/{files[0]['key']}"],
            check=True,
        )  # fmt: skip
    return {
        "rows": 0, "raster": files, "unit": s.get("unit"), "band": s.get("band_meaning") or str(s.get("band") or ""),
        "seconds": round(time.time() - t0), "built": time.strftime("%Y-%m-%d"),
        "example": {"sql": f"area_stats(measure='{PFX}_{s['id']}')", "answer": None},
    }  # fmt: skip


def as_of(s: dict[str, Any]) -> dict[str, str]:
    """The source's own date (brief 30): the registry's `as_of` when it names one (a release or
    reference date stated by the publisher), else the newest Last-Modified header of the files
    downloaded for it; empty when neither exists (the build date is then all we know)."""
    if s.get("as_of"):
        return {
            "as_of": str(s["as_of"]),
            "as_of_basis": s.get("as_of_basis", "stated by the publisher"),
        }
    from email.utils import parsedate_to_datetime

    dates = []
    for f in (TMP / s["id"]).rglob("*.last-modified"):
        try:
            dates.append(parsedate_to_datetime(f.read_text(encoding="utf-8").strip()))
        except (TypeError, ValueError):
            continue
    if not dates:
        return {}
    return {
        "as_of": max(dates).date().isoformat(),
        "as_of_basis": "Last-Modified of the published file",
    }


def build_one(con, lk, s: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN001
    """One source into the lake (table = its id); the example query's answer."""
    if s["kind"] == "raster":
        return build_raster(s)
    t0 = time.time()
    load(con, s)
    safe_cols(con, "t")
    cols = [c for (c,) in con.execute("SELECT column_name FROM (DESCRIBE t)").fetchall()]
    lon, lat = s.get("lon"), s.get("lat")
    geometry = None
    if "geometry" in cols:
        geometry = "geometry"
        kind_of = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE t)").fetchall())
        if kind_of["geometry"] == "VARCHAR":  # WKT text (planning.data.gov.uk and others)
            # planning.data.gov.uk fills `point` where `geometry` (the site outline) is empty
            alt = ", TRY(ST_GeomFromText(point))" if "point" in cols else ""
            query = f"SELECT * EXCLUDE (geometry), coalesce(TRY(ST_GeomFromText(geometry)){alt}) AS geometry FROM t"
        else:
            query = "SELECT * FROM t"
    elif lon and lat:
        lon, lat = (re.sub(r"[^0-9a-z]+", "_", x.lower()).strip("_") for x in (lon, lat))
        geometry = "geometry"
        query = (
            f"SELECT *, CASE WHEN TRY_CAST({lon} AS DOUBLE) BETWEEN -180 AND 180 AND TRY_CAST({lat} AS DOUBLE) "
            f"BETWEEN -90 AND 90 THEN ST_Point(TRY_CAST({lon} AS DOUBLE), TRY_CAST({lat} AS DOUBLE)) END AS geometry FROM t"
        )
    elif s.get("x") and s.get("y"):
        x, y = (re.sub(r"[^0-9a-z]+", "_", c.lower()).strip("_") for c in (s["x"], s["y"]))
        geometry = "geometry"
        query = (
            f"SELECT *, ST_Transform(ST_Point(TRY_CAST({x} AS DOUBLE), TRY_CAST({y} AS DOUBLE)), "
            f"'{s['crs']}', 'EPSG:4326', always_xy := true) AS geometry FROM t"
        )
    elif s.get("wkt"):
        geometry = "geometry"
        query = (
            f"SELECT * EXCLUDE ({s['wkt']}), TRY(ST_GeomFromText({s['wkt']})) AS geometry FROM t"
        )
    else:
        query = "SELECT * FROM t"
    import lake

    sort = [lake.hilbert()] if geometry else [f'"{cols[0]}"']
    asof = as_of(s)
    lk.write(
        con,
        s["id"],
        query,
        sort=sort,
        geometry=geometry,
        meta={**asof, "refresh": s.get("refresh", "")},
    )
    n = con.execute("SELECT count(*) FROM t").fetchone()[0]
    out = {
        "rows": n, "columns": cols[:60], "geometry": bool(geometry), "seconds": round(time.time() - t0),
        "example": {"sql": f"SELECT count(*) FROM {WN}.{s['id']}", "answer": n},
        "built": time.strftime("%Y-%m-%d"),
        **asof,
    }  # fmt: skip
    if s.get("choro"):
        out["choro"] = choro_file(con, s)
    if geometry:
        if not app_file(con, s, query):
            out["tiles"] = tiles_file(con, s, query, n)
        bb = con.execute(
            f"SELECT min(ST_XMin(geometry)), min(ST_YMin(geometry)), max(ST_XMax(geometry)), max(ST_YMax(geometry)), count(geometry) FROM ({query})"
        ).fetchone()
        out["bbox"] = [round(x, 3) if x is not None else None for x in bb[:4]]
        out["with_position"] = bb[4]
    return out


APP = ROOT / "frontend" / "public" / "data" / "eu" / PFX
APP_MAX_POINTS = 30000
NAME_COLS = (
    "name",
    "site_name",
    "facility_name",
    "company",
    "dam_name",
    "plant_name",
    "project_name",
    "title",
    "label",
    "operator",
    "site",
    "ident",
)


def app_file(con, s: dict[str, Any], query: str) -> None:  # noqa: ANN001
    """A small map file (points only, at most APP_MAX_POINTS, all of them or none): position,
    a name and up to six columns as published, for the generic wave-9 layer."""
    n, pts = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE ST_GeometryType(geometry)::VARCHAR = 'POINT') FROM ({query}) WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)"
    ).fetchone()
    if not n or pts != n or n > APP_MAX_POINTS:
        return False
    cols = [
        c
        for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE ({query}))").fetchall()
        if c not in ("geometry", "bbox")
    ]
    name = next((c for c in NAME_COLS if c in cols), None) or next(
        (c for c in cols if "name" in c), None
    )
    keep = [
        c
        for c in (s.get("show") or cols)
        if c in cols
        and c not in (name, "lon", "lat", "name")
        and not c.startswith(("ogc_fid", "objectid", "fid", "shape_", "globalid"))
    ][:6]
    sel = ", ".join(
        ["round(ST_X(geometry), 4)", "round(ST_Y(geometry), 4)", f'"{name}"' if name else "NULL"]
        + [f'"{c}"' for c in keep]
    )
    rows = con.execute(f"SELECT {sel} FROM ({query}) WHERE geometry IS NOT NULL").fetchall()
    APP.mkdir(parents=True, exist_ok=True)
    w.write_json(
        APP / f"{s['id']}.json",
        {
            "fetched": w.now(),
            "source": f"{title_of(s)} ({s['licence']})",
            "fields": ["lon", "lat", "name", *keep],
            "points": [
                [
                    r[0],
                    r[1],
                    *(
                        v if isinstance(v, (int, float, str)) or v is None else str(v)
                        for v in r[2:]
                    ),
                ]
                for r in rows
            ],
        },  # fmt: skip
        max_mb=6,
    )
    return True


UPLOAD = {"on": False}
PUBLIC = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev"
APPC = ROOT / "frontend" / "public" / "data" / "eu" / f"{PFX}c"
EUROSTAT_ISO2 = {"EL": "GR", "UK": "GB"}


def tiles_file(con, s: dict[str, Any], query: str, n: int) -> dict[str, Any] | None:  # noqa: ANN001
    """Vector tiles of every record (lines, polygons, or more points than a map file holds):
    tippecanoe over GeoJSONSeq, uploaded to the public bucket as w9/<id>.pmtiles. Every record
    is in the tiles at the layer's own zoom range; nothing is dropped (no feature or size limit)."""
    import shutil
    import subprocess

    if not shutil.which("tippecanoe"):
        print(f"  {s['id']}: no tippecanoe here, tiles skipped", flush=True)
        return None
    cols = [
        c
        for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE ({query}))").fetchall()
        if c not in ("geometry", "bbox")
    ]
    name = next((c for c in NAME_COLS if c in cols), None) or next(
        (c for c in cols if "name" in c), None
    )
    keep = [
        c
        for c in cols
        if c != name and not c.startswith(("ogc_fid", "objectid", "fid", "shape_", "globalid"))
    ][:6]
    kind = con.execute(
        f"SELECT mode(replace(ST_GeometryType(geometry)::VARCHAR, 'MULTI', '')) FROM ({query}) WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)"
    ).fetchone()[0]
    minzoom = 6 if n > 200_000 else 4 if n > 20_000 else 0
    d = TMP / s["id"]
    seq = d / "tiles.geojsons"
    props = ", ".join(
        [f"'name', CAST(\"{name}\" AS VARCHAR)"] * bool(name) + [f"'{c}', \"{c}\"" for c in keep]
    )
    cur = con.execute(
        f"SELECT json_object('type', 'Feature', 'geometry', ST_AsGeoJSON(geometry)::JSON, "
        f"'properties', json_object({props}))::VARCHAR FROM ({query}) WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)"
    )
    with seq.open("w", encoding="utf-8") as fh:
        while rows := cur.fetchmany(50_000):
            fh.writelines(r[0] + "\n" for r in rows)
    out = d / f"{s['id']}.pmtiles"
    cmd = ["tippecanoe", "-o", str(out), "-l", "d", f"-Z{minzoom}", "-z12", "--no-feature-limit", "--no-tile-size-limit",
           "--simplification=4", "--force", "-P", str(seq)]  # fmt: skip
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:  # the table is in the lake; only its tiles failed
        err = (run.stderr or "").strip().splitlines()[-3:]
        print(f"  {s['id']}: tippecanoe failed: {err}", flush=True)
        return {"error": " | ".join(err)[:300]}
    print(
        f"  {s['id']}: {out.stat().st_size / 1e6:,.1f} MB of tiles (zoom {minzoom}-12)", flush=True
    )
    if UPLOAD["on"]:
        w.upload_public(out, f"{PFX}/{s['id']}.pmtiles", "application/vnd.pmtiles")
    return {
        "url": f"pmtiles://{PUBLIC}/{PFX}/{s['id']}.pmtiles",
        "kind": kind.lower(),
        "minzoom": minzoom,
        "fields": ["name", *keep] if name else keep,
    }


GB_DISTRICT = r"(E0[6-9]|W06|S12|N09)\d{6}"  # GB local authority district codes (no totals)


def choro_file(con, s: dict[str, Any]) -> dict[str, Any] | None:  # noqa: ANN001
    """One published series per area for the map's colouring (w9c/<id>.json): the rows the
    source publishes for each country (Eurostat's country rows), US county or GB district, the
    newest period published for at least 90 % of the most areas any period has; values as published, nothing aggregated or split."""
    c = s["choro"]
    where = " AND ".join(
        [f"CAST(\"{k}\" AS VARCHAR) = '{v}'" for k, v in (c.get("filter") or {}).items()]
        or ["true"]
    )
    key, val, per = c.get("key", "geo"), c.get("value", "obs_value"), c.get("period", "time_period")
    scope = c.get("scope", "country")
    keyok = {
        "country": "length(k) = 2",
        "gb_lad": f"regexp_full_match(k, '{GB_DISTRICT}')",
        "gb_lad24": f"regexp_full_match(k, '{GB_DISTRICT}')",
    }.get(scope, "true")
    sql = f"""WITH r AS (SELECT CAST("{key}" AS VARCHAR) AS k, CAST({per} AS VARCHAR) AS p, TRY_CAST("{val}" AS DOUBLE) AS v FROM t WHERE {where})
              , n AS (SELECT p, count(DISTINCT k) AS n FROM r WHERE v IS NOT NULL AND {keyok} GROUP BY p)
              SELECT p, n FROM n WHERE n >= 0.9 * (SELECT max(n) FROM n) ORDER BY p DESC LIMIT 1"""
    best = (
        con.execute(sql).fetchone()
        if per in [c_ for (c_,) in con.execute("SELECT column_name FROM (DESCRIBE t)").fetchall()]
        else None
    )
    period = best[0] if best else c.get("period_label")
    pwhere = f"AND CAST({per} AS VARCHAR) = '{period}'" if best else ""
    rows = con.execute(
        f"""SELECT CAST("{key}" AS VARCHAR) AS k, any_value(TRY_CAST("{val}" AS DOUBLE)) FROM t
            WHERE {where} {pwhere} AND TRY_CAST("{val}" AS DOUBLE) IS NOT NULL GROUP BY 1"""
    ).fetchall()
    values = {}
    for k, v in rows:
        if k is None:
            continue
        if scope == "country":
            if len(k) != 2:
                continue
            k = EUROSTAT_ISO2.get(k, k)
        elif scope == "us_county":
            k = k.zfill(5)
        elif scope in ("gb_lad", "gb_lad24") and not re.fullmatch(GB_DISTRICT, k):
            continue  # districts only: no county or region totals, no footnote rows
        values[k] = v
    if not values:
        print(f"  {s['id']}: no rows for the colouring filter {c.get('filter')}", flush=True)
        return None
    APPC.mkdir(parents=True, exist_ok=True)
    w.write_json(
        APPC / f"{s['id']}.json",
        {
            "fetched": w.now(),
            "source": f"{title_of(s)} ({s['licence']})",
            "label": c["label"],
            "unit": c.get("unit", ""),
            "period": period,
            "scope": scope,
            "filter": c.get("filter") or {},
            "values": values,
        },  # fmt: skip
    )
    print(f"  {s['id']}: colouring of {len(values)} areas, period {period}", flush=True)
    return {"scope": scope, "areas": len(values), "period": period}


AREA_WORD = {"country": "countries", "us_county": "counties", "gb_lad": "local authority districts",
             "gb_lad24": "local authority districts"}  # fmt: skip
SCOPE_PLACE = {"us_county": "US", "gb_lad": "GB", "gb_lad24": "GB"}
ONS_AGOL = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
# the shapes per GB colouring scope: ONS service, code and name fields, app file, label
GB_LAD = {
    "gb_lad": ("Local_Authority_Districts_December_2021_UK_BUC_2022", "LAD21CD", "LAD21NM",
               "gb_lad.json", "ONS Local Authority Districts (December 2021) UK BUC (OGL v3)"),
    "gb_lad24": ("Local_Authority_Districts_December_2024_Boundaries_UK_BUC", "LAD24CD", "LAD24NM",
                 "gb_lad24.json", "ONS Local Authority Districts (December 2024) UK BUC (OGL v3)"),
}  # fmt: skip


def gb_lad(args: argparse.Namespace) -> None:
    """The ONS local authority district shapes (ultra generalised, OGL v3) for the GB
    colourings: December 2021 (gb_lad.json, codes of DfT VEH0131) and December 2024
    (gb_lad24.json, codes of the DESNZ and Census tables); flat rings to 4 decimals."""
    for service, code, name, file, label in GB_LAD.values():
        feats: list[dict[str, Any]] = []
        with httpx.Client(timeout=120) as cl:
            while True:
                r = cl.get(
                    f"{ONS_AGOL}/{service}/FeatureServer/0/query",
                    params={
                        "where": "1=1",
                        "outFields": f"{code},{name}",
                        "outSR": 4326,
                        "f": "geojson",
                        "resultOffset": len(feats),
                        "resultRecordCount": 200,
                    },
                )
                r.raise_for_status()
                page = r.json()["features"]
                feats += page
                if len(page) < 200:
                    break
        out = []
        for f in feats:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            out.append(
                {
                    "code": f["properties"][code],
                    "name": f["properties"][name],
                    "polygons": [
                        [[round(v, 4) for pt in ring for v in pt] for ring in poly]
                        for poly in polys
                    ],
                }
            )
        path = ROOT / "frontend" / "public" / "data" / "eu" / file
        w.write_json(path, {"fetched": w.now(), "source": label, "areas": out})
        print(f"{len(out)} districts, {path.stat().st_size:,} bytes -> {path}")


def build(args: argparse.Namespace) -> None:
    UPLOAD["on"] = bool(args.upload)
    todo = [s for s in sources(args.cat, args.id) if s["status"] == "build" and s["kind"] != "page"]
    lk = w.lake_for(
        WN,
        args.lake,
        f"wave {WAVE} sources (see each table's source in agent/catalog)",
        "per table",
        SCRIPT,
    )
    # a category job keeps <cat>.json, a single-source job its own file (jobs run in parallel)
    name = str(args.cat) if args.cat is not None else (f"s_{args.id}" if args.id else "all")
    out_path = ROOT / "data" / f"{WN}_built" / f"{name}.json"
    status = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    con = con_spatial()
    for s in todo:
        print(f"== {s['id']}", flush=True)
        try:
            status[s["id"]] = build_one(con, lk, with_keys(s))
            print(
                f"  {s['id']}: {status[s['id']]['rows']:,} rows in {status[s['id']]['seconds']} s",
                flush=True,
            )
        except KeyMissing as e:
            print(f"  {s['id']}: {e}", flush=True)
            status[s["id"]] = {"skipped": str(e), "built": None}
        except (SystemExit, Exception) as e:  # noqa: BLE001 - one source failing does not stop the others
            import traceback

            traceback.print_exc()
            status[s["id"]] = {"error": f"{type(e).__name__}: {str(e)[:300]}", "built": None}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(status, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    )
    if lk.tables:
        w.lake_done(lk, args.upload)


# ---------------------------------------------------------------------- render

RANK = {"point": 0, "line": 0, "polygon": 0, "raster": 0, "grid_100m": 0, "small_area": 1,
        "municipality": 2, "county": 3, "region": 4, "zone": 4, "country": 5}  # fmt: skip
EXISTING = (
    "consumption",
    "heating",
    "outlines",
    "flood_zones",
    "oil_gas_facilities",
    "co2_storage",
    "congestion",
    "energy_poverty",
)


LANDLOCKED = ("AT", "CZ", "HU", "LU", "SK")  # marine sources (EMODnet) do not cover them


NEIGHBOURS = ("NO", "CH", "IS", "BA", "RS", "ME", "MK", "AL", "XK", "MD", "UA", "TR")


def covers(places: list[str], cc: str) -> bool:
    from coverage import EU27

    return (
        "WORLD" in places
        or cc in places
        or ("EUR" in places and (cc in EU27 or cc == "GB"))
        or ("EU27" in places and cc in EU27)
        or ("EUSEA" in places and (cc in EU27 or cc == "GB") and cc not in LANDLOCKED)
    )


def built_records() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in sorted((ROOT / "data" / f"{WN}_built").glob("*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if v.get("rows") is not None or k not in out:
                out[k] = v
    return out


def outcome(s: dict[str, Any], built: dict[str, Any], probes: dict[str, Any]) -> str:
    """built | failed | page | blocked | left_out | not_published."""
    if s["status"] == "have":
        return "built"
    if s["status"] != "build":
        return s["status"]
    b = built.get(s["id"]) or {}
    if b.get("rows") or b.get("raster"):
        return "built"
    if s["kind"] == "page":
        return "page"
    if b.get("skipped"):  # a key not set yet: not a failure
        return "pending"
    return "failed" if b else "pending"


def title_of(s: dict[str, Any]) -> str:
    return s.get("title") or s.get("note") or s["id"].replace("_", " ")


def cell_for(fam: str, f: dict[str, Any], cc: str, srcs: list[dict[str, Any]], built: dict[str, Any],
             probes: dict[str, Any], hits: dict[str, Any]) -> dict[str, Any] | None:  # fmt: skip
    mine = [s for s in srcs if s["fam"] == fam and covers(s["places"], cc)]
    ok = [s for s in mine if outcome(s, built, probes) == "built"]
    today = time.strftime("%Y-%m-%d")
    if ok:
        finest = min(ok, key=lambda s: RANK.get(s["level"], 5))
        cell = {
            "status": "have" if all(x["status"] == "have" for x in ok) else "built",
            "source": "; ".join(dict.fromkeys(title_of(s) for s in ok)),
            "url": finest["url"]
            if finest["kind"] not in ("ckan", "govuk", "sciencebase")
            else (finest.get("lic_url") or finest["url"]),
            "licence": "; ".join(dict.fromkeys(s["licence"] for s in ok)),
            "dataset": ", ".join(s.get("dataset") or f"lake {WN}.{s['id']}" for s in ok),
            "checked": max(
                ((built.get(s["id"]) or {}).get("built") or s.get("checked") or today) for s in ok
            ),
        }
        if RANK.get(finest["level"], 5) > RANK.get(f.get("want", "point"), 0):
            cell["partial"] = True
            cell["note"] = f"published at {finest['level']} level ({title_of(finest)})"
        return cell
    if fam in EXISTING:
        return None
    blocked = [s for s in mine if s["status"] == "blocked"]
    if blocked:
        b = blocked[0]
        return {"status": "blocked", "source": title_of(b), "url": b["url"], "checked": today,
                "note": f"{b.get('why', 'blocked')}. Data request: {b.get('request', 'an open download')}"}  # fmt: skip
    notes = []
    for s in mine:
        o = outcome(s, built, probes)
        pr = probes.get(s["id"]) or {}
        if o == "left_out":
            notes.append(f"{title_of(s)} left out: {s.get('why')}")
        elif o == "not_published":
            notes.append(f"{title_of(s)}: {s.get('why')}")
        elif o in ("page", "failed", "pending"):
            err = (built.get(s["id"]) or {}).get("error")
            notes.append(
                f"{title_of(s)} probed ({s['url'][:90]}, HTTP {pr.get('http')}): "
                + (f"build failed ({err[:120]})" if err else "no machine-readable download located")
            )
    h = (hits.get(fam) or {}).get("hits", {}).get(cc) or {}
    if h:
        top = "; ".join(t for t in h.get("top", []) if t)
        notes.append(
            f"{h.get('portal')} search '{(hits.get(fam) or {}).get('query')}' ({(hits.get(fam) or {}).get('checked')}): {h.get('count', '?')} results"
            + (f", top: {top}" if top else "")
        )
    url = (
        mine[0]["url"]
        if mine
        else {"US": "https://catalog.data.gov/", "GB": "https://www.data.gov.uk/"}.get(
            cc, "https://data.europa.eu/data/datasets"
        )
    )
    return {"status": "not_published", "url": url, "checked": today,
            "note": (f"no source built in wave {WAVE}. " + " | ".join(notes)) if notes else f"no source found in wave {WAVE}"}  # fmt: skip


RASTERS = ROOT / "agent" / "rasters_waves.yaml"
_EV = ROOT / "data" / "dark_evidence.yaml"
EVIDENCE: dict[str, dict[str, dict[str, str]]] = (
    (yaml.safe_load(_EV.read_text(encoding="utf-8")) or {}) if _EV.exists() else {}
)


def updates_text(s: dict[str, Any], b: dict[str, Any]) -> str:
    """The layer card's "Updated:" line (brief 30): the source's own date when known (stated, or
    the file's Last-Modified), else the date it was built here, and its refresh rhythm."""
    from freshness import refresh_of

    every, basis = refresh_of(s)
    if b.get("as_of"):
        when = f"as of {b['as_of']} ({b.get('as_of_basis', 'stated by the publisher')})"
    else:
        when = f"built {b.get('built') or 'n/a'} (the source states no date)"
    return f"{when}; refreshed {every} ({basis})"


def render_rasters(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    """agent/rasters_waves.yaml: one area_stats measure per built raster source of this wave
    (`<pfx>_<id>`), the mean of the cells whose centre lies inside the area unless the registry
    says `stat: sum`; the other waves' measures are kept."""
    doc = yaml.safe_load(RASTERS.read_text(encoding="utf-8")) if RASTERS.exists() else None
    ms = {
        k: v for k, v in ((doc or {}).get("measures") or {}).items() if not k.startswith(f"{PFX}_")
    }
    for s in srcs:
        b = built.get(s["id"]) or {}
        if s["kind"] != "raster" or not b.get("raster"):
            continue
        stat = s.get("stat", "mean")
        cover = s["places"] if isinstance(s["places"], str) else ", ".join(s["places"])
        ms[f"{PFX}_{s['id']}"] = {
            "title": title_of(s),
            "unit": s.get("unit") or "as published",
            "stat": stat,
            "how": f"{'sum' if stat == 'sum' else 'mean'} of the cells whose centre lies inside the area"
            + (f"; band: {s['band_meaning']}" if s.get("band_meaning") else ""),
            "licence": s.get("licence", ""),
            "layers": [
                {"url": f"r2://infraatlas-raw/{f['key']}", "cell": f"{f['cell'][0]:g} x {f['cell'][1]:g} ({f['crs']})", "cover": cover}
                for f in b["raster"]
            ],
        }  # fmt: skip
    RASTERS.write_text(
        "# Generated by scripts/wave9.py render (brief 30): the registry rasters of waves 9 and\n"
        "# 10 as area_stats measures. Edit scripts/wave*_sources.yaml, not this file.\n"
        + yaml.safe_dump(
            {"measures": dict(sorted(ms.items()))}, sort_keys=False, allow_unicode=True, width=200
        ),
        encoding="utf-8",
    )


def render(args: argparse.Namespace) -> None:
    from coverage import COUNTRIES, REGISTRY

    srcs = sources()
    built = built_records()
    render_rasters(srcs, built)
    probes = json.loads(PROBES.read_text(encoding="utf-8")) if PROBES.exists() else {}
    hits = json.loads(SEARCH.read_text(encoding="utf-8")) if SEARCH.exists() else {}
    fams = families()
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for fam, f in fams.items():
        cells = {cc: cell_for(fam, f, cc, srcs, built, probes, hits) for cc in COUNTRIES}
        for cc, ev in (EVIDENCE.get(fam) or {}).items():  # the second research pass (brief 30)
            c = cells.get(cc)
            if c and c.get("status") in ("not_published", "blocked") and ev.get("note"):
                c["note"] = (
                    f"{c.get('note', '')} Second pass ({ev.get('checked', '')}): {ev['note']}".strip()
                )
        # brief 30 Track 2.5: neighbours get a cell where a built source covers them (a world
        # source, or one naming the country); elsewhere they stay unassessed, not "dark"
        near = {}
        for cc in NEIGHBOURS:
            c = cell_for(fam, f, cc, srcs, built, probes, hits)
            if c and c.get("status") in ("built", "have"):
                c["note"] = "; ".join(
                    x for x in (c.get("note"), "neighbour: the source covers it") if x
                )
                near[cc] = c
        if near:  # the family then lists the neighbours, each with a cell (scripts/coverage.py)
            for cc in NEIGHBOURS:
                cells[cc] = near.get(cc) or {
                    "status": "not_published", "url": next(iter(near.values()))["url"],
                    "checked": time.strftime("%Y-%m-%d"),
                    "note": f"no source of this family covers {cc}; its national sources were not searched",
                }  # fmt: skip
        reg["families"][fam] = {
            "name": f["name"],
            "shows": f["shows"],
            "category": f["cat"],
            **({"regions": ["neighbours"]} if any(cc in cells for cc in NEIGHBOURS) else {}),
            "cells": cells,
        }
    for fam in EXISTING:
        for cc in COUNTRIES:
            c = cell_for(fam, {"want": "point"}, cc, srcs, built, probes, hits)
            if c and c["status"] == "built":
                old = reg["families"][fam]["cells"].get(cc) or {}
                if old.get("status") in ("built", "have") and old.get("dataset"):
                    # the earlier dataset first, each name once (render runs again and again)
                    for k, sep in (("source", "; "), ("dataset", ", "), ("licence", "; ")):
                        parts = [p for p in f"{old.get(k) or ''}{sep}{c[k]}".split(sep) if p]
                        c[k] = sep.join(dict.fromkeys(parts))
                reg["families"][fam]["cells"][cc] = c
    REGISTRY.write_text(
        REGISTRY.read_text(encoding="utf-8").split("families:")[0]
        + yaml.safe_dump(
            {"families": reg["families"]}, sort_keys=False, allow_unicode=True, width=200
        ),
        encoding="utf-8",
    )
    research(srcs, built, probes)
    docs(srcs, built)
    app_manifest(srcs, built)
    catalog(srcs, built)
    levels(srcs, built)
    counts = {}
    for s in srcs:
        counts[outcome(s, built, probes)] = counts.get(outcome(s, built, probes), 0) + 1
    print(f"{len(srcs)} sources: {counts}")


CATS = {0: "Part A: finishing wave 8", 1: "1. Land, permitting and planning", 2: "2. Grid planning, connection and network charges",
        3: "3. Markets and revenues", 4: "4. Physical climate and hazard risk", 5: "5. Demand and electrification",
        6: "6. Offshore and maritime", 7: "7. Supply chain, materials and industry", 8: "8. Finance, public money and incentives",
        9: "9. Social and community", 10: "10. Telecom and digital", 11: "11. Water and cooling", 12: "12. Heat networks and geothermal",
        13: "13. Mobility", 14: "14. Nuclear", 15: "15. Air quality near plants", 16: "16. Reliability below the country", 17: "17. Night lights"}  # fmt: skip
CATS10 = {1: "1. Energy supply, balances and trade", 2: "2. Energy prices, taxes and markets",
          3: "3. Emissions and environmental accounts", 4: "4. Transport, vehicles and fuels",
          5: "5. Water, materials and circular economy", 6: "6. Sustainable development indicators",
          7: "7. World energy and climate indicators", 8: "8. GB local authority energy and emissions",
          9: "9. US facilities and emissions"}  # fmt: skip
if WAVE == 10:
    CATS = CATS10


def research(srcs: list[dict[str, Any]], built: dict[str, Any], probes: dict[str, Any]) -> None:
    lines = [
        f"# Wave {WAVE} sources ({BRIEF})",
        "",
        f"Every source probed for {BRIEF}: category, places, level, licence as",
        f"found, size or rows, status, link and the date checked. Generated by `WAVE={WAVE} python scripts/wave9.py render`",
        f"from scripts/{WN}_sources.yaml, data/{WN}_probes.json and data/{WN}_built/. Status: **built** (in the",
        f"lake, `{WN}.<id>`), **blocked** (key, login or refusal; the data request is in data/coverage.yaml),",
        "**left out** (licence does not allow a paid product), **not published** (no machine-readable file),",
        "**page only** (the publisher's page was probed, no download located in this wave), **failed** (the",
        "build failed; the error is shown).",
        "",
    ]
    for cat, name in CATS.items():
        rows = [s for s in srcs if s["cat"] == cat]
        if not rows:
            continue
        lines += [
            f"## {name}",
            "",
            "| Source | Places | Level | Licence | Size / rows | Status | Checked |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in rows:
            o = outcome(s, built, probes)
            if s["status"] == "have":
                o = "have"
            b, pr = built.get(s["id"]) or {}, probes.get(s["id"]) or {}
            size = (
                f"{b['rows']:,} rows"
                if b.get("rows")
                else (
                    f"{pr['size'] / 1e6:,.1f} MB"
                    if pr.get("size")
                    else (f"{pr['rows']:,} features" if pr.get("rows") else "")
                )
            )
            status = {"built": "built", "have": f"have (earlier wave: {s.get('dataset')})", "failed": f"failed: {(b.get('error') or '')[:100]}", "page": f"page only (HTTP {pr.get('http')})",
                      "pending": "not yet built", "blocked": f"blocked: {s.get('why')}", "left_out": f"left out: {s.get('why')}",
                      "not_published": f"not published: {s.get('why')}"}[o]  # fmt: skip
            lines.append(
                f"| [{title_of(s)}]({s['url']}) (`{s['id']}`) | {', '.join(s['places'])} | {s['level']} | {s['licence']} | {size} | "
                f"{status.replace('|', '/')} | {b.get('built') or pr.get('checked') or ''} |"
            )
        lines.append("")
    (ROOT / "docs" / "research" / f"{WN}-sources.md").write_text("\n".join(lines), encoding="utf-8")


GROUP = {0: None, 1: "Land & planning", 2: "Power grid", 3: "Prices", 4: "Risk", 5: "Industry & demand", 6: "Offshore",
         7: "Industry & demand", 8: "Money", 9: "People & places", 10: "Water & telecom", 11: "Water & telecom",
         12: "Resources", 13: "Mobility", 14: "Power plants", 15: "Emissions", 16: "Power grid", 17: "People & places"}  # fmt: skip
if WAVE == 10:
    GROUP = {1: "Energy statistics", 2: "Prices", 3: "Emissions", 4: "Mobility", 5: "Water & telecom",
             6: "Energy statistics", 7: "World indicators", 8: "Energy statistics", 9: "Emissions"}  # fmt: skip
FAMILY_GROUP = {
    "oil_gas_facilities": "Gas, oil & coal",
    "co2_storage": "Industry & demand",
    "flood_zones": "Risk",
}
FAMILY_FIRST = {"local_homes_gb": "People & places", "water_materials": "Industry & demand"}
GROUP_COLOUR = {"Land & planning": "rgb(206,184,140)", "Power grid": "rgb(236,178,120)", "Prices": "rgb(255,196,90)",
                "Risk": "rgb(255,120,96)", "Industry & demand": "rgb(214,160,255)", "Offshore": "rgb(96,190,255)",
                "Money": "rgb(150,220,150)", "People & places": "rgb(240,200,220)", "Water & telecom": "rgb(120,200,230)",
                "Resources": "rgb(255,170,110)", "Mobility": "rgb(190,190,255)", "Power plants": "rgb(255,214,72)",
                "Emissions": "rgb(200,200,200)", "Gas, oil & coal": "rgb(230,140,90)",
                "Energy statistics": "rgb(140,200,255)", "World indicators": "rgb(170,230,200)"}  # fmt: skip


def where_of(places: list[str]) -> list[str]:
    return [
        {"EU27": "EU", "EUR": "Europe", "EUSEA": "Europe", "WORLD": "World"}.get(p, p)
        for p in places
    ]


def pr_tables(args: argparse.Namespace) -> None:
    """The PR's coverage tables (one per category, 29 columns) and the source counts."""
    from coverage import COUNTRIES, REGISTRY

    srcs, built = sources(), built_records()
    probes = json.loads(PROBES.read_text(encoding="utf-8")) if PROBES.exists() else {}
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["families"]
    counts: dict[str, int] = {}
    for x in srcs:
        o = "have" if x["status"] == "have" else outcome(x, built, probes)
        counts[o] = counts.get(o, 0) + 1
    probed = sum(v for k, v in counts.items() if k != "have")
    print(f"**Sources probed: {probed}; built: {counts.get('built', 0)}** ({counts})\n")
    print(
        "Legend: **B** built, **H** on the map before, **P** partial (coarser level or part of the country), **–** not published, **X** blocked.\n"
    )
    sym = {"built": "B", "have": "H", "not_published": "–", "blocked": "X"}
    fams = families()
    for cat, name in CATS.items():
        rows = [f for f, v in fams.items() if v["cat"] == cat] if cat else list(EXISTING)
        if not rows:
            continue
        print(f"#### {name}\n")
        print("| Family | " + " | ".join(COUNTRIES) + " |")
        print("|---|" + "---|" * len(COUNTRIES))
        for fam in rows:
            cells = reg[fam]["cells"]
            out = []
            for cc in COUNTRIES:
                c = cells.get(cc) or {}
                v = sym.get(c.get("status"), "?")
                if v in ("B", "H") and c.get("partial"):
                    v = "P"
                out.append(v)
            print(f"| {reg[fam]['name']} | " + " | ".join(out) + " |")
        print()


def between(path: Path, block: str) -> None:
    """Replace the generated block of a doc (or append it once)."""
    begin, end = f"<!-- {WN}:begin (generated by scripts/wave9.py render) -->", f"<!-- {WN}:end -->"
    text = path.read_text(encoding="utf-8")
    new = f"{begin}\n{block}\n{end}"
    if begin in text:
        text = text[: text.index(begin)] + new + text[text.index(end) + len(end) :]
    else:
        text = text.rstrip("\n") + "\n\n" + new + "\n"
    path.write_text(text, encoding="utf-8")


def docs(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    """The wave 9 rows of docs/DATA_SOURCES.md and docs/DATA_LAKE.md."""
    ok = [s for s in srcs if (built.get(s["id"]) or {}).get("rows")]
    src = [f"## Wave {WAVE} sources (`WAVE={WAVE} scripts/wave9.py`, lake `{WN}/<id>`)", "",
           "Every table is passthrough: the publisher's rows and columns as published (column names in",
           "lower snake case), one table per source; positions are moved to WGS 84 from the source's CRS",
           "(computed), points from published coordinates. On the map: a point source of at most 30,000",
        f"records gets a map file (`{PFX}/<id>.json`, all records); every other positioned source is cut into",
        "vector tiles in Actions (tippecanoe, every record, no feature or size limit; larger sets from",
        f"zoom 4 or 6) published as `{PFX}/<id>.pmtiles` in the public bucket. Area series become colourings",
        f"(`{PFX}c/<id>.json`): one named series per table (the filter is in the file), Eurostat's country",
        "rows, USGS's US counties or GB districts, the newest period published for at least 90 % of the most areas, colour stops at the quartiles",
        "(computed). The full list of the","sources probed, with the ones blocked or left out, is docs/research/wave9-sources.md.", "",
           "| Source | Category | Places | Level | Licence | Rows | Table |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    lake_rows = [
        f"### Wave {WAVE} ({BRIEF})",
        "",
        "| Table | Kept as | Rows | Positioned |",
        "|---|---|---|---|",
    ]
    for s in ok:
        b = built[s["id"]]
        src.append(
            f"| [{title_of(s)}]({s['url']}) | {CATS.get(s['cat'], '')} | {', '.join(where_of(s['places']))} | {s['level']} | {s['licence']} | {b['rows']:,} | `{WN}.{s['id']}` |"
        )
        lake_rows.append(
            f"| `wave9/{s['id']}` | {'GeoParquet (bbox, Hilbert order)' if b.get('geometry') else 'Parquet'} | {b['rows']:,} | {b.get('with_position', '') if b.get('geometry') else 'no'} |"
        )
    between(ROOT / "docs" / "DATA_SOURCES.md", "\n".join(src))
    between(ROOT / "docs" / "DATA_LAKE.md", "\n".join(lake_rows))


def app_manifest(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    """frontend/src/app/wave9.json: a layer and a dataset entry per source on the map (a point
    file, or vector tiles), and a colouring and its dataset entry per published area series."""
    layers, datasets, colours = [], [], []
    for s in srcs:
        b = built.get(s["id"]) or {}
        if not b.get("rows"):
            continue
        group = (
            FAMILY_FIRST.get(s["fam"])
            or GROUP.get(s["cat"])
            or FAMILY_GROUP.get(s["fam"], "Industry & demand")
        )
        colour = GROUP_COLOUR.get(group, "rgb(200,200,200)")
        fam = families().get(s["fam"], {})
        where = where_of(s["places"])
        shows = fam.get("shows", s["fam"].replace("_", " "))
        src = f"{title_of(s)} ({s['licence']})"
        lid = f"{PFX}_{s['id']}"
        layer = None
        if (APP / f"{s['id']}.json").exists():
            layer = {"id": lid}
        elif (b.get("tiles") or {}).get("url"):
            t = b["tiles"]
            layer = {
                "id": lid,
                "tiles": t["url"],
                "kind": t["kind"],
                "minzoom": t["minzoom"],
                "fields": t["fields"],
                "source": src,
            }
        if layer:
            desc = shows.capitalize() + (
                f" (shown from zoom {layer['minzoom']}: zoom in)" if layer.get("minzoom") else ""
            )
            layers.append({**layer, "label": title_of(s), "desc": desc, "group": group,
                           "coverage": ", ".join(w for w in where if w != "World") or "World", "color": colour})  # fmt: skip
            datasets.append({"id": lid, "name": title_of(s), "category": group, "description": f"{title_of(s)}: {b['rows']:,} records as published",
                             "color": colour, "family": s["fam"], "updates": updates_text(s, b),
                             "parts": [{"layer": lid, "where": where, "what": shows, "source": src, "doc": f"Wave {WAVE} sources"}]})  # fmt: skip
        ch = b.get("choro")
        if ch and (APPC / f"{s['id']}.json").exists():
            cid = f"{PFX}c_{s['id']}"
            label = s["choro"]["label"]
            colours.append(
                {
                    "id": cid,
                    "label": label,
                    "group": group,
                    "modes": ["live"],
                    "scope": ch["scope"],
                    "file": s["id"],
                }
            )
            datasets.append({"id": f"colour-{cid}", "name": label, "category": group,
                             "description": f"{label} ({s['choro'].get('unit', '')}), {ch['areas']} {AREA_WORD[ch['scope']]}, {ch.get('period') or ''}: {title_of(s)}",
                             "color": colour, "family": s["fam"], "colour": cid, "updates": updates_text(s, b),
                             "parts": [{"where": where if ch["scope"] == "country" else [SCOPE_PLACE[ch["scope"]]], "what": label, "source": src, "doc": f"Wave {WAVE} sources"}]})  # fmt: skip
    (ROOT / "frontend" / "src" / "app" / f"{WN}.json").write_text(
        json.dumps(
            {"layers": layers, "colours": colours, "datasets": datasets},
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def catalog(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    tables = {}
    for s in srcs:
        b = built.get(s["id"]) or {}
        if not b.get("rows"):
            continue
        tables[s["id"]] = {
            "grain": f"{title_of(s)}: one row per record as published ({', '.join(s['places'])}; level {s['level']})",
            "source": s["url"],
            "licence": s["licence"],
            "category": CATS.get(s["cat"], ""),
            "columns": ", ".join(b.get("columns", [])[:40]),
            "examples": [{"q": f"how many records in {title_of(s)}", "sql": b["example"]["sql"], "answer": b["example"]["answer"]}],
        }  # fmt: skip
    out = {"dataset": WN, "title": f"Wave {WAVE} datasets ({BRIEF}): one table per source", "licence": "per table (see each table)",
           "notes": "Positioned tables are GeoParquet with a bbox column: use in_area(geometry, area_id). Values as published.",
           "tables": tables}  # fmt: skip
    (ROOT / "agent" / "catalog" / f"{WN}.yaml").write_text(
        f"# Generated by `WAVE={WAVE} python scripts/wave9.py render` from the build records (data/{WN}_built/).\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=160),
        encoding="utf-8",
    )


def levels(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    path = ROOT / "agent" / "areas" / "levels.yaml"
    # this wave's block replaced in place (the other waves' blocks kept)
    old = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    head = f"  # wave {WAVE} (generated"
    start = next((i for i, x in enumerate(old) if x.startswith(head)), len(old))
    end = next((i for i in range(start + 1, len(old)) if old[i].startswith("  # wave ")), len(old))
    rows = [f"  # wave {WAVE} (generated by scripts/wave9.py render)"]
    for s in srcs:
        if (built.get(s["id"]) or {}).get("rows"):
            lvl = (
                s["level"]
                if s["level"] in ("point", "line", "polygon", "raster")
                else {"grid_100m": "small_area", "zone": "region"}.get(s["level"], s["level"])
            )
            rows.append(f'  {WN}.{s["id"]}: {{{lvl}: "{", ".join(s["places"])}: {title_of(s)}"}}')
    path.write_text("\n".join(old[:start] + rows + old[end:]) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--cat", type=int)
    p.add_argument("--id")
    p.set_defaults(fn=probe)
    b = sub.add_parser("build")
    b.add_argument("--cat", type=int)
    b.add_argument("--id")
    b.add_argument("--lake", type=Path, default=Path("lake-out"))
    b.add_argument("--upload", action="store_true")
    b.set_defaults(fn=build)
    q = sub.add_parser("pr")
    q.set_defaults(fn=pr_tables)
    r = sub.add_parser("render")
    r.set_defaults(fn=render)
    g = sub.add_parser("gb-lad")
    g.set_defaults(fn=gb_lad)
    s = sub.add_parser("search")
    s.add_argument("--family")
    s.set_defaults(fn=search)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
