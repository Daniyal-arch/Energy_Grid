"""Shared helpers for the wave-7 builders (docs/tasks/22-coverage-wave7.md).

ArcGIS feature-layer queries with paging, numbers as published, and rows handed to the lake
as snapshot partitions. Downloads, compact JSON and the lake writer come from `wave5_common`.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import wave5_common as w

TODAY = datetime.now(UTC).date().isoformat()
TMP = Path("/tmp/wave7")
UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) InfraAtlas (github.com/Daniyal-arch/Energy_Grid)"
}


def get(
    url: str, *, tries: int = 4, timeout: float = 90, headers: dict | None = None, **kw: object
) -> httpx.Response:
    """One answer, retried on network errors, 429 and 5xx; raises on other errors."""
    last = ""
    for attempt in range(1, tries + 1):
        try:
            r = httpx.get(
                url, timeout=timeout, follow_redirects=True, headers={**UA, **(headers or {})}, **kw
            )  # type: ignore[arg-type]
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(8 * attempt)
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPError as err:
            last = f"{type(err).__name__} {err}"
            time.sleep(5 * attempt)
    raise SystemExit(f"{url}: {last}")


def arcgis(
    layer: str,
    *,
    where: str = "1=1",
    geometry: bool = True,
    page: int = 1000,
    extra: dict | None = None,
) -> list[dict]:
    """Every feature of an ArcGIS feature layer: attributes, plus `_lon`/`_lat` (points, WGS84),
    `_polys` (polygons as [polygon][ring] flat lon/lat) or `_paths` (lines as [[lon, lat]...]
    per path) when `geometry`; `extra` adds query parameters (maxAllowableOffset...)."""
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where, "outFields": "*", "f": "json", "resultOffset": offset,
            "resultRecordCount": page, "returnGeometry": str(geometry).lower(), "outSR": 4326,
        }  # fmt: skip
        d = get(f"{layer}/query", params=params | (extra or {})).json()
        if "error" in d:
            raise SystemExit(f"{layer}: {d['error']}")
        for f in d.get("features", []):
            row = dict(f["attributes"])
            g = f.get("geometry") or {}
            if "x" in g:
                row["_lon"], row["_lat"] = round(g["x"], 5), round(g["y"], 5)
            elif "rings" in g:
                row["_polys"] = esri_polygons(g["rings"])
            elif "paths" in g:
                row["_paths"] = [[[round(x, 3), round(y, 3)] for x, y in p] for p in g["paths"]]
            out.append(row)
        if not d.get("exceededTransferLimit") and len(d.get("features", [])) < page:
            return out
        offset += page


def esri_polygons(rings: list[list[list[float]]], digits: int = 3) -> list[list[list[float]]]:
    """Esri rings to [polygon][ring] flat lon/lat: a clockwise ring starts a polygon (Esri's
    outer rings), a counter-clockwise one is a hole of the polygon before it."""
    out: list[list[list[float]]] = []
    for r in rings:
        area = sum(x0 * y1 - x1 * y0 for (x0, y0, *_), (x1, y1, *_) in zip(r, r[1:], strict=False))
        flat = [round(c, digits) for xy in r for c in xy[:2]]
        if area <= 0 or not out:
            out.append([flat])
        else:
            out[-1].append(flat)
    return out


def number(v: object) -> float | None:
    """A published value as a number when it is one ("12.5", "1 234,5", 3); else None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int | float):
        return float(v)
    t = str(v).strip().replace(" ", "").replace(" ", "")
    if re.fullmatch(r"-?\d+,\d+", t):
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def lake_rows(
    dataset: str,
    tables: list[tuple[str, list[dict], list[str], tuple[str, str] | None]],
    *,
    lake_dir: Path,
    upload: bool,
    source: str,
    licence: str,
    script: str,
) -> None:
    """[(table, rows, sort, (lon, lat) columns or None)] as snapshot partitions of
    lake/<dataset>/<table>."""
    import duckdb
    import lake

    TMP.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lake.iso_codes(con)
    lk = w.lake_for(dataset, lake_dir, source, licence, script, TODAY)
    for table, rows, sort, geometry in tables:
        if not rows:
            continue
        tmp = TMP / f"{dataset}_{table}.json"
        tmp.write_text(json.dumps(rows, ensure_ascii=False, default=str), encoding="utf-8")
        geo = ""
        if geometry:
            lon, lat = geometry
            geo = f", CASE WHEN {lon} IS NOT NULL THEN ST_Point({lon}, {lat}) END AS geometry"
        lk.write(
            con, table,
            f"SELECT *{geo} FROM read_json('{tmp}', sample_size = -1, maximum_object_size = 1000000000)",
            sort=sort, partition={"snapshot": TODAY}, geometry="geometry" if geometry else None,
        )  # fmt: skip
    w.lake_done(lk, upload)
