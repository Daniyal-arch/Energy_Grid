"""Wave 9 (docs/tasks/28-wave9-customer-needs.md): probe and build the sources of
scripts/wave9_sources.yaml.

    python scripts/wave9.py probe [--cat N] [--id ID]      # status, size, type, licence quote
    python scripts/wave9.py build --cat N [--upload]       # the `build` sources of a category
    python scripts/wave9.py search FAMILY QUERY            # data.europa.eu hits per dark country

Probe results go to `data/wave9_probes.json` (committed: the evidence behind every registry
cell and docs/research/wave9-sources.md). Builds go to the lake (`lake/w9_<id>/...`) and write
`data/wave9_built.json` (rows, columns and the answer of each table's example query).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
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
REGISTRY = ROOT / "scripts" / "wave9_sources.yaml"
PROBES = ROOT / "data" / "wave9_probes.json"
BUILT = ROOT / "data" / "wave9_built.json"
SCRIPT = "scripts/wave9.py"
TMP = Path("/tmp/wave9")
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


def search(args: argparse.Namespace) -> None:
    """data.europa.eu: the datasets a query finds per country (evidence for dark cells)."""
    from coverage import EU27

    out = {}
    for cc in EU27:
        facets = json.dumps({"country": [cc.lower() if cc != "GR" else "gr"]})
        d = w.get_json(
            "https://data.europa.eu/api/hub/search/search",
            params={"q": args.query, "filters": "dataset", "limit": 3, "facets": facets},
        )
        res = d["result"]  # type: ignore[index]
        titles = [
            (x.get("title") or {}).get("en") or next(iter((x.get("title") or {}).values()), "")
            for x in res["results"]
        ]
        out[cc] = {"count": res["count"], "top": titles}
        print(f"{cc}: {res['count']} | {' | '.join(t[:60] for t in titles)}", flush=True)
    path = ROOT / "data" / "wave9_search.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old[args.family] = {"query": args.query, "checked": time.strftime("%Y-%m-%d"), "hits": out}
    path.write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n")


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
    if crs and crs not in ("EPSG:4326", "OGC:CRS84"):
        print(f"  {path.name}: {crs} to EPSG:4326", flush=True)
        con.execute(
            f"UPDATE t SET {geom} = ST_Transform({geom}, '{crs}', 'EPSG:4326', always_xy := true)"
        )
    con.execute(f"UPDATE t SET {geom} = ST_GeomFromWKB(ST_AsWKB({geom}))")


def arcgis_pages(s: dict[str, Any], dest: Path) -> Path:
    """Every feature of an ArcGIS layer, paged (its maxRecordCount), as one GeoJSON file."""
    meta = w.get_json(s["url"], params={"f": "json"})
    step = min(int(meta.get("maxRecordCount") or 1000), 2000)  # type: ignore[union-attr]
    feats: list[dict[str, Any]] = []
    while True:
        page = w.get_json(
            s["url"] + "/query",
            params={
                "where": s.get("where", "1=1"), "outFields": "*", "outSR": "4326", "f": "geojson",
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
    if kind == "arcgis":
        read_geo(con, arcgis_pages(s, d / "layer.geojson"), {**s, "crs": "EPSG:4326"})
    elif kind in ("shp_zip", "gpkg_zip", "geojson_zip"):
        z = w.unzip(w.download(url, d / "src.zip", timeout=3600))
        ext = {"shp_zip": (".shp",), "gpkg_zip": (".gpkg",), "geojson_zip": (".geojson", ".json")}
        read_geo(con, first_file(z, ext[kind]), s)
    elif kind in ("geojson", "gpkg"):
        read_geo(con, w.download(url, d / f"src.{kind}", timeout=3600), s)
    elif kind in ("csv", "csv_zip", "csv_gz"):
        f = w.download(
            url,
            d
            / ("src.zip" if kind == "csv_zip" else "src.csv.gz" if kind == "csv_gz" else "src.csv"),
            timeout=3600,
        )
        if kind == "csv_zip":
            f = first_file(w.unzip(f), (".csv", ".txt"))
        opts = ", ".join(
            [f"delim = '{s['sep']}'"] * bool(s.get("sep"))
            + [f"skip = {s['skip']}"] * bool(s.get("skip"))
            + [f"encoding = '{s['encoding']}'"] * bool(s.get("encoding"))
            + ["all_varchar = true"] * bool(s.get("varchar"))
            + ["sample_size = -1", "ignore_errors = true", "header = true"]
        )
        con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{f}', {opts})")
    elif kind == "xlsx":
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
        f = d / "src.json"
        f.write_text(json.dumps(data))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json_auto('{f}', maximum_object_size = 1000000000)"
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
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json_auto('{f}', maximum_object_size = 1000000000)"
        )
    elif kind == "jsonstat":
        con.execute("CREATE OR REPLACE TABLE t AS SELECT * FROM (VALUES (1)) LIMIT 0")
        rows = jsonstat_rows(w.get_json(url, timeout=300))  # type: ignore[arg-type]
        f = d / "src.json"
        f.write_text(json.dumps(rows))
        con.execute(f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json_auto('{f}')")
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
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json_auto('{f}', maximum_object_size = 1000000000)"
        )
    elif kind == "ckan":
        # the newest CSV (or `fmt`) resource of the first package the search finds
        res = w.get_json(url)["result"]  # type: ignore[index]
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


def build_one(con, lk, s: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN001
    """One source into the lake (table = its id); the example query's answer."""
    t0 = time.time()
    load(con, s)
    safe_cols(con, "t")
    cols = [c for (c,) in con.execute("SELECT column_name FROM (DESCRIBE t)").fetchall()]
    lon, lat = s.get("lon"), s.get("lat")
    geometry = None
    if "geometry" in cols:
        geometry = "geometry"
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
    lk.write(con, s["id"], query, sort=sort, geometry=geometry)
    n = con.execute("SELECT count(*) FROM t").fetchone()[0]
    out = {
        "rows": n, "columns": cols[:60], "geometry": bool(geometry), "seconds": round(time.time() - t0),
        "example": {"sql": f"SELECT count(*) FROM wave9.{s['id']}", "answer": n},
        "built": time.strftime("%Y-%m-%d"),
    }  # fmt: skip
    if geometry:
        bb = con.execute(
            f"SELECT min(ST_XMin(geometry)), min(ST_YMin(geometry)), max(ST_XMax(geometry)), max(ST_YMax(geometry)), count(geometry) FROM ({query})"
        ).fetchone()
        out["bbox"] = [round(x, 3) if x is not None else None for x in bb[:4]]
        out["with_position"] = bb[4]
    return out


def build(args: argparse.Namespace) -> None:
    todo = [s for s in sources(args.cat, args.id) if s["status"] == "build" and s["kind"] != "page"]
    lk = w.lake_for(
        "wave9",
        args.lake,
        "wave 9 sources (see each table's source in agent/catalog)",
        "per table",
        SCRIPT,
    )
    out_path = ROOT / "data" / "wave9_built" / f"{args.cat if args.cat is not None else 'all'}.json"
    status = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    con = con_spatial()
    for s in todo:
        print(f"== {s['id']}", flush=True)
        try:
            status[s["id"]] = build_one(con, lk, s)
            print(
                f"  {s['id']}: {status[s['id']]['rows']:,} rows in {status[s['id']]['seconds']} s",
                flush=True,
            )
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
    s = sub.add_parser("search")
    s.add_argument("family")
    s.add_argument("query")
    s.set_defaults(fn=search)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
