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


FAMILIES = ROOT / "scripts" / "wave9_families.yaml"
SEARCH = ROOT / "data" / "wave9_search.json"


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
        ext = {
            "shp_zip": (".shp", ".gml"),
            "gpkg_zip": (".gpkg",),
            "geojson_zip": (".geojson", ".json"),
        }
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
        if isinstance(data, dict):
            data = [data]
        f = d / "src.json"
        f.write_text(json.dumps(data))
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000)"
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
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000)"
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
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_json('{f}', format = 'array', map_inference_threshold = -1, maximum_object_size = 1000000000)"
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
    elif kind in ("ods", "xls"):
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
        print(f"  sheet {sheet!r} of {book.sheet_names[:8]}", flush=True)
        raw = book.parse(sheet, header=None, dtype=str)
        # the header is the first row with at least three filled cells (title rows come first)
        filled = raw.head(40).notna().sum(axis=1)
        h = int(next(i for i, n in filled.items() if n >= max(3, 0.6 * filled.max())))
        body = raw.iloc[h + 1 :].copy()
        body.columns = [
            str(c) if str(c) != "nan" else f"col_{i}" for i, c in enumerate(raw.iloc[h])
        ]
        out = d / "src.csv"
        body.dropna(how="all").to_csv(out, index=False)
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
        kind_of = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE t)").fetchall())
        if kind_of["geometry"] == "VARCHAR":  # WKT text (planning.data.gov.uk and others)
            query = "SELECT * EXCLUDE (geometry), TRY(ST_GeomFromText(geometry)) AS geometry FROM t"
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
    lk.write(con, s["id"], query, sort=sort, geometry=geometry)
    n = con.execute("SELECT count(*) FROM t").fetchone()[0]
    out = {
        "rows": n, "columns": cols[:60], "geometry": bool(geometry), "seconds": round(time.time() - t0),
        "example": {"sql": f"SELECT count(*) FROM wave9.{s['id']}", "answer": n},
        "built": time.strftime("%Y-%m-%d"),
    }  # fmt: skip
    if geometry:
        app_file(con, s, query)
        bb = con.execute(
            f"SELECT min(ST_XMin(geometry)), min(ST_YMin(geometry)), max(ST_XMax(geometry)), max(ST_YMax(geometry)), count(geometry) FROM ({query})"
        ).fetchone()
        out["bbox"] = [round(x, 3) if x is not None else None for x in bb[:4]]
        out["with_position"] = bb[4]
    return out


APP = ROOT / "frontend" / "public" / "data" / "eu" / "w9"
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
        f"SELECT count(*), count(*) FILTER (WHERE ST_GeometryType(geometry)::VARCHAR = 'POINT') FROM ({query}) WHERE geometry IS NOT NULL"
    ).fetchone()
    if not n or pts != n or n > APP_MAX_POINTS:
        return
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


def build(args: argparse.Namespace) -> None:
    todo = [s for s in sources(args.cat, args.id) if s["status"] == "build" and s["kind"] != "page"]
    lk = w.lake_for(
        "wave9",
        args.lake,
        "wave 9 sources (see each table's source in agent/catalog)",
        "per table",
        SCRIPT,
    )
    # a category job keeps <cat>.json, a single-source job its own file (jobs run in parallel)
    name = str(args.cat) if args.cat is not None else (f"s_{args.id}" if args.id else "all")
    out_path = ROOT / "data" / "wave9_built" / f"{name}.json"
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
)


def covers(places: list[str], cc: str) -> bool:
    from coverage import EU27

    return (
        "WORLD" in places
        or cc in places
        or ("EUR" in places and (cc in EU27 or cc == "GB"))
        or ("EU27" in places and cc in EU27)
    )


def built_records() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in sorted((ROOT / "data" / "wave9_built").glob("*.json")):
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
    if b.get("rows"):
        return "built"
    if s["kind"] == "page":
        return "page"
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
            "dataset": ", ".join(s.get("dataset") or f"lake wave9.{s['id']}" for s in ok),
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
            "note": ("no source built in wave 9. " + " | ".join(notes)) if notes else "no source found in wave 9"}  # fmt: skip


def render(args: argparse.Namespace) -> None:
    from coverage import COUNTRIES, REGISTRY

    srcs = sources()
    built = built_records()
    probes = json.loads(PROBES.read_text(encoding="utf-8")) if PROBES.exists() else {}
    hits = json.loads(SEARCH.read_text(encoding="utf-8")) if SEARCH.exists() else {}
    fams = families()
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for fam, f in fams.items():
        cells = {cc: cell_for(fam, f, cc, srcs, built, probes, hits) for cc in COUNTRIES}
        reg["families"][fam] = {
            "name": f["name"],
            "shows": f["shows"],
            "category": f["cat"],
            "cells": cells,
        }
    for fam in EXISTING:
        for cc in COUNTRIES:
            c = cell_for(fam, {"want": "point"}, cc, srcs, built, probes, hits)
            if c and c["status"] == "built":
                old = reg["families"][fam]["cells"].get(cc) or {}
                if old.get("status") in ("built", "have") and old.get("dataset"):
                    c["source"] = f"{old.get('source')}; {c['source']}"
                    c["dataset"] = f"{old.get('dataset')}, {c['dataset']}"
                    c["licence"] = f"{old.get('licence') or ''}; {c['licence']}".strip("; ")
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


def research(srcs: list[dict[str, Any]], built: dict[str, Any], probes: dict[str, Any]) -> None:
    lines = [
        "# Wave 9 sources (brief 28)",
        "",
        "Every source probed for docs/tasks/28-wave9-customer-needs.md: category, places, level, licence as",
        "found, size or rows, status, link and the date checked. Generated by `python scripts/wave9.py render`",
        "from scripts/wave9_sources.yaml, data/wave9_probes.json and data/wave9_built/. Status: **built** (in the",
        "lake, `wave9.<id>`), **blocked** (key, login or refusal; the data request is in data/coverage.yaml),",
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
    (ROOT / "docs" / "research" / "wave9-sources.md").write_text("\n".join(lines), encoding="utf-8")


GROUP = {0: None, 1: "Land & planning", 2: "Power grid", 3: "Prices", 4: "Risk", 5: "Industry & demand", 6: "Offshore",
         7: "Industry & demand", 8: "Money", 9: "People & places", 10: "Water & telecom", 11: "Water & telecom",
         12: "Resources", 13: "Mobility", 14: "Power plants", 15: "Emissions", 16: "Power grid", 17: "People & places"}  # fmt: skip
FAMILY_GROUP = {
    "oil_gas_facilities": "Gas, oil & coal",
    "co2_storage": "Industry & demand",
    "flood_zones": "Risk",
}
GROUP_COLOUR = {"Land & planning": "rgb(206,184,140)", "Power grid": "rgb(236,178,120)", "Prices": "rgb(255,196,90)",
                "Risk": "rgb(255,120,96)", "Industry & demand": "rgb(214,160,255)", "Offshore": "rgb(96,190,255)",
                "Money": "rgb(150,220,150)", "People & places": "rgb(240,200,220)", "Water & telecom": "rgb(120,200,230)",
                "Resources": "rgb(255,170,110)", "Mobility": "rgb(190,190,255)", "Power plants": "rgb(255,214,72)",
                "Emissions": "rgb(200,200,200)", "Gas, oil & coal": "rgb(230,140,90)"}  # fmt: skip


def where_of(places: list[str]) -> list[str]:
    return [{"EU27": "EU", "EUR": "Europe", "WORLD": "World"}.get(p, p) for p in places]


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
    begin, end = "<!-- wave9:begin (generated by scripts/wave9.py render) -->", "<!-- wave9:end -->"
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
    src = ["## Wave 9 sources (`scripts/wave9.py`, lake `wave9/<id>`)", "",
           "Every table is passthrough: the publisher's rows and columns as published (column names in",
           "lower snake case), one table per source; positions are moved to WGS 84 from the source's CRS",
           "(computed), points from published coordinates. A map file (`w9/<id>.json`) is written when a",
           "source is points and holds at most 30,000 records: all of them or none. The full list of the",
           "sources probed, with the ones blocked or left out, is docs/research/wave9-sources.md.", "",
           "| Source | Category | Places | Level | Licence | Rows | Table |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    lake_rows = [
        "### Wave 9 (brief 28)",
        "",
        "| Table | Kept as | Rows | Positioned |",
        "|---|---|---|---|",
    ]
    for s in ok:
        b = built[s["id"]]
        src.append(
            f"| [{title_of(s)}]({s['url']}) | {CATS.get(s['cat'], '')} | {', '.join(where_of(s['places']))} | {s['level']} | {s['licence']} | {b['rows']:,} | `wave9.{s['id']}` |"
        )
        lake_rows.append(
            f"| `wave9/{s['id']}` | {'GeoParquet (bbox, Hilbert order)' if b.get('geometry') else 'Parquet'} | {b['rows']:,} | {b.get('with_position', '') if b.get('geometry') else 'no'} |"
        )
    between(ROOT / "docs" / "DATA_SOURCES.md", "\n".join(src))
    between(ROOT / "docs" / "DATA_LAKE.md", "\n".join(lake_rows))


def app_manifest(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    """frontend/src/app/wave9.json: a layer and a dataset entry per source with a map file."""
    layers, datasets = [], []
    for s in srcs:
        if not (built.get(s["id"]) or {}).get("rows") or not (APP / f"{s['id']}.json").exists():
            continue
        group = GROUP.get(s["cat"]) or FAMILY_GROUP.get(s["fam"], "Industry & demand")
        colour = GROUP_COLOUR.get(group, "rgb(200,200,200)")
        fam = families().get(s["fam"], {})
        lid = f"w9_{s['id']}"
        where = where_of(s["places"])
        layers.append({"id": lid, "label": title_of(s), "desc": fam.get("shows", s["fam"].replace("_", " ")).capitalize(),
                       "group": group, "coverage": ", ".join(w for w in where if w != "World") or "World", "color": colour})  # fmt: skip
        datasets.append({"id": lid, "name": title_of(s), "category": group, "description": f"{title_of(s)}: {built[s['id']]['rows']:,} records as published",
                         "color": colour, "family": s["fam"],
                         "parts": [{"layer": lid, "where": where, "what": fam.get("shows", ""), "source": f"{title_of(s)} ({s['licence']})", "doc": "Wave 9 sources"}]})  # fmt: skip
    (ROOT / "frontend" / "src" / "app" / "wave9.json").write_text(
        json.dumps({"layers": layers, "datasets": datasets}, indent=1, ensure_ascii=False) + "\n",
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
    out = {"dataset": "wave9", "title": "Wave 9 datasets (brief 28): one table per source", "licence": "per table (see each table)",
           "notes": "Positioned tables are GeoParquet with a bbox column: use in_area(geometry, area_id). Values as published.",
           "tables": tables}  # fmt: skip
    (ROOT / "agent" / "catalog" / "wave9.yaml").write_text(
        "# Generated by `python scripts/wave9.py render` from the build records (data/wave9_built/).\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=160),
        encoding="utf-8",
    )


def levels(srcs: list[dict[str, Any]], built: dict[str, Any]) -> None:
    path = ROOT / "agent" / "areas" / "levels.yaml"
    text = path.read_text(encoding="utf-8").split("  # wave 9 (generated")[0].rstrip("\n") + "\n"
    rows = ["  # wave 9 (generated by scripts/wave9.py render)"]
    for s in srcs:
        if (built.get(s["id"]) or {}).get("rows"):
            lvl = (
                s["level"]
                if s["level"] in ("point", "line", "polygon", "raster")
                else {"grid_100m": "small_area", "zone": "region"}.get(s["level"], s["level"])
            )
            rows.append(f'  wave9.{s["id"]}: {{{lvl}: "{", ".join(s["places"])}: {title_of(s)}"}}')
    path.write_text(text + "\n".join(rows) + "\n", encoding="utf-8")


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
    s = sub.add_parser("search")
    s.add_argument("--family")
    s.set_defaults(fn=search)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
