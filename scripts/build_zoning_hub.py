"""Zoning layers of the ArcGIS services found by `zoning_discover.py --hub` into the lake.

Reads `data/zoning_discovery/hub_services.csv` (one row per ArcGIS Hub item whose title names
zoning), drops titles that are not maps (feedback forms, surveys, hearings; NOISE below), and
for every service keeps the polygon layers whose names say zoning, land use, overlay or plan
(LAYER below; parcels, boundaries and roads are left out). Each layer is read in full by object
id (`returnIdsOnly`, then `objectIds` in pages of the layer's `maxRecordCount`) as GeoJSON in
EPSG:4326, reprojected by the publisher's own server.

Rows go to `lake/zoning/zones` (the same columns as every other source), partition `source=us_hub` (or `eu_hub`, `gb_hub`), in the same
standard columns as `build_zoning.py`. The zone code and label are the values of the fields
whose names say so (CODE and LABEL below; `country` is the GISCO outline holding the layer's
first zone, NULL when none does; the field names are kept in `class_code` and
`attributes`). `class` is read from the label's words (WORDS below): a label without one of
those words stays `other`. Every attribute is kept verbatim in `attributes`.

`hub_layers` lists every layer looked at (read, skipped and why, failed and why) with the Hub
item's licence text, so a missing city can be traced. Most licences are empty
(owner question 9); the lake bucket is private.

    uv run python scripts/build_zoning_hub.py --region us --shard 0 --shards 48 --lake lake-out
    uv run python scripts/build_zoning_hub.py --region us --services 5 --lake lake-out  # test
    uv run python scripts/build_zoning_hub.py --merge parts/*/_catalog.json --lake lake-out --upload
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import duckdb
import httpx
from build_zoning import HILUCS, STANDARD, UA, VOCAB, make_valid
from lake import Lake, hilbert

SCRIPT = "scripts/build_zoning_hub.py"
LIST = Path(__file__).resolve().parents[1] / "data" / "zoning_discovery" / "hub_services.csv"
REGIONS = ["us", "us_ak_hi", "gb", "eu", "wfs"]
WFS_LIST = LIST.with_name("wfs_services.csv")  # INSPIRE / XPlanung WFS (zoning_discover.py --wfs)
# zones (ZoningElement, XPlanung areas), regulations, and plan outlines (a plan published
# only as a scanned map still has its outline and document links); `code` names the layer
WFS_LAYER = re.compile(
    r"ZoningElement|SupplementaryRegulation|SpatialPlan|(BP|FP|RP|SO)_Plan$|"
    r"BaugebietsTeilFlaeche|BebauungsFlaeche|Widmung",
    re.I,
)
DATASET_SOURCE = ("Zoning and land-use plans, per partition `source` (docs/DATA_SOURCES.md); the "
                  "*_hub partitions: ArcGIS services found by scripts/zoning_discover.py, each read "
                  "from its publisher's server")  # fmt: skip
DATASET_LICENCE = "per source (docs/DATA_SOURCES.md); *_hub: per service, in zoning.hub_layers"
OUTLINES = LIST.parents[2] / "frontend" / "public" / "data" / "eu"


def countries(con: duckdb.DuckDBPyConnection) -> None:
    """Table `outline (iso2, geom)`: the app's GISCO outlines (Europe in countries.json, the
    rest of the world in world.json); a layer's country is the one holding its first zone."""
    from lake import iso_codes

    iso_codes(con)
    to2 = dict(con.execute("SELECT iso3, iso2 FROM iso_codes").fetchall())
    rows: list[tuple[str, str]] = []
    world = json.loads((OUTLINES / "world.json").read_text(encoding="utf-8"))
    for f in world["features"]:
        if f["properties"].get("iso3") in to2:
            rows.append((to2[f["properties"]["iso3"]], json.dumps(f["geometry"])))
    eu = json.loads((OUTLINES / "countries.json").read_text(encoding="utf-8"))
    for c in eu["countries"]:
        polys = [[[r[i : i + 2] for i in range(0, len(r), 2)] for r in p] for p in c["polygons"]]
        rows.append((c["iso"], json.dumps({"type": "MultiPolygon", "coordinates": polys})))
    con.execute("CREATE OR REPLACE TABLE outline (iso2 VARCHAR, gj VARCHAR)")
    con.executemany("INSERT INTO outline VALUES (?, ?)", rows)
    con.execute(
        "CREATE OR REPLACE TABLE outline AS SELECT iso2, ST_GeomFromGeoJSON(gj) AS geom FROM outline"
    )


NOISE = re.compile(
    r"feedback|survey|comment|\bform\b|request|petition|notice|hearing|\bcase|application|"
    r"permit|violation|complaint|workshop|story|dashboard|\btest\b|\bcopy\b",
    re.I,
)
LAYER = re.compile(
    r"zon|land.?use|\bflu\b|overlay|special.?district|specific.?plan|planned.?(unit|dev)|"
    r"general.?plan|comprehensive.?plan|future.?land",
    re.I,
)
NOT_LAYER = re.compile(
    r"parcel|boundar|limit|footprint|address|tract|block.?group|road|street|centerline|"
    r"hydrant|label|annotation|dissolve",
    re.I,
)
CODE = [
    re.compile(p, re.I)
    for p in (
        r"^zon(e|ing)?_?(code|class|cd|dist(rict)?|type|desig(nation)?|abbr)$",
        r"^(zoning|zone|zone_|zn_?code|zoneclass|zonecode|zoningcode|district|flu|lu_?code)$",
        r"zon",
        r"land_?use|^lu$|flu",
    )
]
LABEL = [
    re.compile(p, re.I)
    for p in (
        r"^zon(e|ing)?_?(desc(ription)?|name|label|title)$",
        r"(zon|dist|flu|land_?use).*(desc|name|label)",
        r"^(desc|description|label|name)$",
    )
]
# the label's words to the harmonised vocabulary; the first match wins, in this order
WORDS: list[tuple[str, re.Pattern[str]]] = [
    ("mixed", re.compile(r"mixed", re.I)),
    (
        "residential",
        re.compile(
            r"residen|dwelling|single.?family|multi.?family|duplex|"
            r"townhouse|apartment|housing|mobile.?home",
            re.I,
        ),
    ),  # fmt: skip
    ("industrial", re.compile(r"industr|manufactur|warehous", re.I)),
    ("commercial", re.compile(r"commerc|business|retail|office|shopping", re.I)),
    ("agricultural", re.compile(r"agricult|farm|ranch", re.I)),
    ("open_space", re.compile(r"open.?space|park|recreation|green", re.I)),
    ("natural", re.compile(r"conservation|forest|resource|wetland|preserv", re.I)),
    ("community", re.compile(r"institution|public|civic|school|government|community", re.I)),
    ("infrastructure", re.compile(r"airport|transport|utilit|railroad|right.?of.?way", re.I)),
    ("water", re.compile(r"\bwater\b|lake|river", re.I)),
]
assert all(w in VOCAB for w, _ in WORDS)


def classify(label: str | None) -> tuple[str, str | None]:
    for cls, rx in WORDS:
        if label and (m := rx.search(label)):
            return cls, m.group(0).lower()
    return "other", None


def get(c: httpx.Client, url: str, data: dict[str, Any], post: bool = False) -> dict[str, Any]:
    for attempt in range(4):
        try:
            r = c.post(url, data=data) if post else c.get(url, params=data)
            if r.status_code < 500:
                r.raise_for_status()
                d = r.json()
                if isinstance(d, dict) and "error" in d:
                    raise RuntimeError(str(d["error"].get("message") or d["error"])[:120])
                return d
        except (httpx.HTTPError, json.JSONDecodeError):
            if attempt == 3:
                raise
        time.sleep(2**attempt)
    raise RuntimeError(f"no answer after retries ({r.status_code})")


def pick(fields: list[str], rules: list[re.Pattern[str]], skip: str | None = None) -> str | None:
    for rx in rules:
        for f in fields:
            if f != skip and rx.search(f) and not re.search(r"shape|objectid|globalid", f, re.I):
                return f
    return None


class Shard:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.lock = threading.Lock()
        self.log: list[dict[str, Any]] = []
        self.rows = 0

    def record(self, **kw: Any) -> None:
        with self.lock:
            self.log.append(kw)

    def read_layer(self, c: httpx.Client, svc: dict[str, str], ly: dict[str, Any]) -> None:
        url = f"{svc['url']}/{ly['id']}"
        base = {"service": svc["url"], "layer": ly["id"], "layer_name": ly.get("name"),
                "item": svc["id"], "title": svc["title"], "owner": svc["source"] or svc["owner"],
                "licence": svc.get("licence") or None}  # fmt: skip
        t0 = time.time()
        try:
            meta = get(c, url, {"f": "json"})
            geom = meta.get("geometryType")
            fields = [f["name"] for f in meta.get("fields") or []]
            if geom != "esriGeometryPolygon":
                self.record(**base, status="skipped", reason=f"geometry {geom}", rows=0)
                return
            code = pick(fields, CODE)
            label = pick(fields, LABEL, skip=code)
            if not code and not label:
                self.record(**base, status="skipped", reason="no zoning field", rows=0)
                return
            ids = get(c, f"{url}/query", {"where": "1=1", "returnIdsOnly": "true", "f": "json"})
            oids = sorted(ids.get("objectIds") or [])
            oid_field = ids.get("objectIdFieldName") or "OBJECTID"
            page = min(int(meta.get("maxRecordCount") or 1000), 2000)
            n = 0
            # each page goes to this layer's own file (a layer of millions of polygons held in
            # memory stopped the runner); the file joins the shard only when the layer is whole
            part = self.out.with_name(f"{self.out.stem}-{abs(hash(url))}.part")
            pf = part.open("w", encoding="utf-8")
            for i in range(0, len(oids), page):
                chunk = oids[i : i + page]
                d = get(c, f"{url}/query", {"objectIds": ",".join(map(str, chunk)),
                        "outFields": "*", "outSR": 4326, "f": "geojson"}, post=True)  # fmt: skip
                feats = d.get("features") or []
                if len(feats) != len(chunk):
                    raise RuntimeError(f"asked {len(chunk)} ids, got {len(feats)}")
                lines: list[str] = []
                for ft in feats:
                    p = ft.get("properties") or {}
                    lab = p.get(label) if label else None
                    cls, word = classify(str(lab) if lab is not None else None)
                    lines.append(json.dumps({
                        "a": p, "g": ft.get("geometry"), "svc": svc["url"], "layer": ly["id"],
                        "layer_name": ly.get("name"), "title": svc["title"],
                        "owner": base["owner"], "licence": svc.get("licence") or None,
                        "code": None if not code else p.get(code),
                        "label": lab, "fields": f"{code or ''}|{label or ''}",
                        "cls": cls, "word": word, "oid": p.get(oid_field),
                    }, ensure_ascii=False, default=str))  # fmt: skip
                if lines:
                    pf.write("\n".join(lines) + "\n")
                n += len(feats)
            pf.close()
            with (
                self.lock,
                self.out.open("a", encoding="utf-8") as f,
                part.open(encoding="utf-8") as src,
            ):
                shutil.copyfileobj(src, f, 1 << 20)
                self.rows += n
            part.unlink()
            self.record(**base, status="read", reason=None, rows=n, code_field=code,
                        label_field=label, seconds=round(time.time() - t0, 1))  # fmt: skip
        except Exception as e:  # noqa: BLE001 - every failure is listed in hub_layers
            for f in self.out.parent.glob(f"{self.out.stem}-{abs(hash(url))}.part"):
                f.unlink()
            self.record(**base, status="failed", reason=str(e)[:160], rows=0)

    def read_wfs(self, svc: dict[str, str]) -> None:
        """An INSPIRE Planned Land Use or XPlanung WFS through GDAL: every ZoningElement (or
        XPlanung zone) layer in full, reprojected to EPSG:4326 by PROJ, checked against the
        count the service reports. The class comes from the zone's HILUCS code."""
        import os

        os.environ["GML_ATTRIBUTES_TO_OGR_FIELDS"] = "YES"
        os.environ["OGR_WFS_PAGING_ALLOWED"] = "ON"  # servers cap a response; GDAL pages
        os.environ["OGR_WFS_PAGE_SIZE"] = "1000"
        url = f"WFS:{svc['url']}"
        con = duckdb.connect()
        con.execute("LOAD spatial")
        base = {"service": svc["url"], "item": svc["id"], "title": svc["title"],
                "owner": svc["source"], "licence": svc.get("licence") or None}  # fmt: skip
        try:
            layers = con.execute(
                "SELECT l.name, l.feature_count, l.geometry_fields[1].crs.auth_name, "
                "l.geometry_fields[1].crs.auth_code FROM (SELECT unnest(layers) AS l "
                "FROM st_read_meta(?))", [url]).fetchall()  # fmt: skip
        except Exception as e:  # noqa: BLE001
            self.record(**base, status="failed", reason=f"service: {str(e)[:150]}", rows=0)
            return
        for name, total, auth, code in layers:
            lb = {**base, "layer": name, "layer_name": name}
            if not WFS_LAYER.search(name):
                self.record(**lb, status="skipped", reason="layer name", rows=0)
                continue
            t0 = time.time()
            part = self.out.with_name(f"{self.out.stem}-{abs(hash(url + name))}.part")
            try:
                cur = con.execute("SELECT * FROM st_read(?, layer = ?) LIMIT 0", [url, name])
                types = [(d[0], str(d[1])) for d in cur.description]
                gcol, gtype = next((c, t) for c, t in types if t.upper().startswith("GEOMETRY"))
                crs = gtype[gtype.find("'") + 1 : gtype.rfind("'")] if "'" in gtype else (
                    f"{auth}:{code}" if auth and code else "EPSG:4326")  # fmt: skip
                rows = con.execute(
                    f"SELECT * EXCLUDE ({gcol}), ST_AsGeoJSON(ST_Transform({gcol}::GEOMETRY, "
                    f"'{crs}', 'EPSG:4326', always_xy := true)) FROM st_read(?, layer = ?)",
                    [url, name])  # fmt: skip
                names = [d[0] for d in rows.description][:-1]
                n = 0
                with part.open("w", encoding="utf-8") as pf:
                    while batch := rows.fetchmany(5000):
                        lines = []
                        for r in batch:
                            p = {k: (v if isinstance(v, (str, int, float, bool)) or v is None
                                     else str(v)) for k, v in zip(names, r[:-1], strict=True)}  # fmt: skip
                            hil = str(p.get("hilucsLandUse_href") or "")
                            hcode = hil.rsplit("/", 1)[-1] if hil else None
                            cls = next((v for k, v in HILUCS if hcode and hcode.startswith(k)),
                                       "other")  # fmt: skip
                            spec = p.get("specificLandUse_href") or p.get("allgArtDerBaulNutzung")
                            lines.append(json.dumps({
                                "a": p, "g": json.loads(r[-1]) if r[-1] else None,
                                "svc": svc["url"], "layer": name, "layer_name": name,
                                "title": svc["title"], "owner": svc["source"],
                                "licence": svc.get("licence") or None,
                                "code": (str(spec).rsplit("/", 1)[-1] if spec
                                         else name.split(":")[-1]),
                                "label": (p.get("name") or p.get("officialTitle") or hcode),
                                "fields": "hilucsLandUse|name",
                                "cls": cls, "word": hcode, "oid": p.get("gml_id"),
                            }, ensure_ascii=False, default=str))  # fmt: skip
                        pf.write("\n".join(lines) + "\n")
                        n += len(batch)
                if total is not None and total >= 0 and n != total:
                    raise RuntimeError(f"read {n}, the service counts {total}")
                with (self.lock, self.out.open("a", encoding="utf-8") as f,
                      part.open(encoding="utf-8") as src):  # fmt: skip
                    shutil.copyfileobj(src, f, 1 << 20)
                    self.rows += n
                part.unlink()
                self.record(**lb, status="read", reason=None, rows=n, code_field="specificLandUse",
                            label_field="name", seconds=round(time.time() - t0, 1))  # fmt: skip
            except Exception as e:  # noqa: BLE001 - every failure is listed in hub_layers
                part.unlink(missing_ok=True)
                self.record(**lb, status="failed", reason=str(e)[:160], rows=0)

    def read_service(self, c: httpx.Client, svc: dict[str, str]) -> None:
        try:
            d = get(c, svc["url"], {"f": "json"})
        except Exception as e:  # noqa: BLE001
            self.record(service=svc["url"], item=svc["id"], title=svc["title"],
                        owner=svc["source"] or svc["owner"], licence=svc.get("licence") or None,
                        status="failed",
                        reason=f"service: {str(e)[:150]}", rows=0)  # fmt: skip
            return
        layers = [*(d.get("layers") or [])]
        if not layers:
            self.record(service=svc["url"], item=svc["id"], title=svc["title"],
                        owner=svc["source"] or svc["owner"], licence=svc.get("licence") or None,
                        status="skipped", reason="no layers", rows=0)  # fmt: skip
        for ly in layers:
            name = ly.get("name") or ""
            if LAYER.search(name) and not NOT_LAYER.search(name):
                self.read_layer(c, svc, ly)
            elif LAYER.search(svc["title"]) and len(layers) == 1:
                self.read_layer(c, svc, ly)  # a one-layer service named for zoning
            else:
                self.record(service=svc["url"], layer=ly.get("id"), layer_name=name,
                            item=svc["id"], title=svc["title"], owner=svc["source"] or svc["owner"],
                            licence=svc.get("licence") or None, status="skipped", reason="layer name", rows=0)  # fmt: skip


SELECT = """
SELECT NULL::VARCHAR AS country, owner AS authority, svc || '/' || layer AS plan_id,
       title || ' / ' || layer_name AS plan_name, NULL AS plan_status, NULL AS adopted,
       json_extract_string(code, '$') AS zone_code, json_extract_string(label, '$') AS zone_label,
       fields || coalesce(':' || word, '') AS class_code, cls AS class, NULL AS doc_url,
       a AS attributes,
       CASE WHEN g IS NULL THEN NULL ELSE ST_GeomFromGeoJSON(g::VARCHAR) END AS geometry
FROM read_json('{path}', format='newline_delimited', maximum_object_size=200000000,
     columns={{'a': 'JSON', 'g': 'JSON', 'svc': 'VARCHAR', 'layer': 'VARCHAR',
     'layer_name': 'VARCHAR', 'title': 'VARCHAR', 'owner': 'VARCHAR', 'licence': 'VARCHAR',
     'code': 'JSON', 'label': 'JSON', 'fields': 'VARCHAR', 'cls': 'VARCHAR', 'word': 'VARCHAR',
     'oid': 'VARCHAR'}})
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us", choices=REGIONS)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--services", type=int, default=None, help="first N services (tests)")
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--tmp", type=Path, default=Path("/tmp/zoning-hub"))
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--upload", action="store_true", help="files only; the catalogue is merged by the last job")  # fmt: skip
    ap.add_argument("--merge", nargs="*", type=Path, help="merge the shards' catalogues, upload it")
    a = ap.parse_args()
    if a.merge is not None:
        lake = Lake("zoning", a.lake, source=DATASET_SOURCE, licence=DATASET_LICENCE, script=SCRIPT)
        lake.dir.mkdir(parents=True, exist_ok=True)
        if a.upload:
            lake.pull_catalog()
        cat = json.loads(lake.finish(partials=a.merge).read_text(encoding="utf-8"))
        for name in ("zones", "hub_layers"):
            t = cat["tables"].get(name) or {}
            print(f"zoning.{name}: {t.get('rows', 0):,} rows, {len(t.get('files', [])):,} files")
        if a.upload:
            lake.upload(catalog_only=True)
        return
    t0 = time.time()
    svcs: dict[str, dict[str, str]] = {}
    if a.region == "wfs":
        rows = list(csv.DictReader(WFS_LIST.open(encoding="utf-8")))
        for r in rows:
            svcs.setdefault(r["url"], {**r, "owner": r["source"]})
    else:
        rows = [r for r in csv.DictReader(LIST.open(encoding="utf-8")) if r["region"] == a.region]
    for r in rows if a.region != "wfs" else []:
        if not NOISE.search(r["title"]) and r["type"] in ("Feature Service", "Map Service"):
            svcs.setdefault(r["url"].rstrip("/"), {**r, "url": r["url"].rstrip("/")})
    todo = [svcs[u] for u in sorted(svcs)][a.shard :: a.shards][: a.services]
    print(f"{len(rows):,} items, {len(svcs):,} services after the noise filter; shard "
          f"{a.shard}/{a.shards}: {len(todo):,}", flush=True)  # fmt: skip
    a.tmp.mkdir(parents=True, exist_ok=True)
    raw = a.tmp / f"{a.region}-{a.shard}.ndjson"
    raw.unlink(missing_ok=True)
    sh = Shard(raw)
    if a.region == "wfs":  # installed once here; each WFS thread only loads it
        duckdb.connect().execute("INSTALL spatial")
    done = 0
    stopped = None

    def one(svc: dict[str, str]) -> None:
        nonlocal done
        if a.region == "wfs":
            sh.read_wfs(svc)
        else:
            with httpx.Client(timeout=120, headers=UA, follow_redirects=True) as c:
                sh.read_service(c, svc)
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(todo)} services, {sh.rows:,} zones, {time.time() - t0:.0f} s", flush=True)  # fmt: skip

    with ThreadPoolExecutor(a.threads) as pool:
        futs = []
        for svc in todo:
            futs.append(pool.submit(lambda s=svc: None if time.time() - t0 > a.max_minutes * 60 else one(s)))  # fmt: skip
        for f in futs:
            f.result()
    if done < len(todo):
        stopped = len(todo) - done
        print(f"  time budget reached: {stopped} services not read", flush=True)

    src = {"us": "us_hub", "us_ak_hi": "us_hub", "gb": "gb_hub", "eu": "eu_hub",
           "wfs": "eu_wfs"}[a.region]  # fmt: skip
    lake = Lake("zoning", a.lake, source=DATASET_SOURCE, licence=DATASET_LICENCE, script=SCRIPT)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET preserve_insertion_order=false")
    stem = f"{a.region}-s{a.shard}"
    if sh.rows:
        con.execute(f"CREATE TABLE z AS {SELECT.format(path=raw)}")
        make_valid(con, src)
        countries(con)
        con.execute("""
            UPDATE z SET country = lc.iso2 FROM (
                SELECT p.plan_id, any_value(o.iso2) AS iso2
                FROM (SELECT plan_id, ST_PointOnSurface(any_value(geometry)) AS pt FROM z
                      WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry) GROUP BY 1) p
                JOIN outline o ON ST_Contains(o.geom, p.pt) GROUP BY 1) lc
            WHERE z.plan_id = lc.plan_id""")
        print("  countries:", con.execute("SELECT country, count(*) FROM z GROUP BY 1 ORDER BY 2 DESC").fetchall())  # fmt: skip
        cols = ", ".join(STANDARD)
        lake.write(
            con, "zones", f"SELECT '{src}' AS source, {cols}, attributes, geometry FROM z",
            sort=[hilbert("geometry")], bloom=["country", "class", "plan_id"],
            partition={"source": src}, geometry="geometry", stem=stem,
            meta={"refresh": "on demand (scripts/build_zoning_hub.py)"},
        )  # fmt: skip
    con.execute("CREATE TABLE l (service VARCHAR, layer VARCHAR, layer_name VARCHAR, item VARCHAR, "
                "title VARCHAR, owner VARCHAR, licence VARCHAR, status VARCHAR, reason VARCHAR, rows BIGINT, "
                "code_field VARCHAR, label_field VARCHAR, seconds DOUBLE)")  # fmt: skip
    keys = ["service", "layer", "layer_name", "item", "title", "owner", "licence", "status", "reason",
            "rows", "code_field", "label_field", "seconds"]  # fmt: skip
    con.executemany(
        f"INSERT INTO l VALUES ({', '.join('?' * len(keys))})",
        [[(str(r[k]) if k == "layer" and r.get(k) is not None else r.get(k)) for k in keys] for r in sh.log],
    )  # fmt: skip
    lake.write(con, "hub_layers", f"SELECT '{src}' AS source, * FROM l", sort=["service", "layer"],
               partition={"source": src}, stem=stem)  # fmt: skip
    st = con.execute("SELECT status, count(*), sum(rows) FROM l GROUP BY 1 ORDER BY 1").fetchall()
    print("  layers:", st, flush=True)
    if sh.rows:
        print("  classes:", con.execute("SELECT class, count(*) FROM z GROUP BY 1 ORDER BY 2 DESC").fetchall())  # fmt: skip
    lake.finish()
    if a.upload:
        lake.upload(catalog=False)
    print(f"shard {a.shard}: {sh.rows:,} zones from {done} services in {time.time() - t0:.0f} s"
          + (f"; {stopped} services left at the time budget" if stopped else ""), flush=True)  # fmt: skip


if __name__ == "__main__":
    main()
