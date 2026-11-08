"""Tier 2 of brief 32: the lake rewritten for selective reads.

    python scripts/lake_rewrite.py inspect [--out data/lake_rowgroups.json]
    python scripts/lake_rewrite.py rewrite --tables outlines.divisions flood.england ... [--upload]
    python scripts/lake_rewrite.py rewrite --breaches [--max-gb 20] [--upload]

`inspect` reads the Parquet footer of every file the lake catalogues list (no data, only the
metadata) and reports per table: files, row groups, the largest row group in rows and in
compressed MB, whether it has a geometry, and whether it breaks the standard of
docs/DATA_LAKE.md section 4 as brief 32 sets it:

- geometry tables: 10,000-100,000 rows a group and at most 32 MB compressed;
- other tables: about 1,000,000 rows a group (at most 128 MB compressed).

`rewrite` writes each file again under the same key:

- rows in Hilbert order of their position (geometry, or lon/lat), so nearby rows share groups;
  tables without a position keep their catalogue sort columns;
- row groups capped by rows and by bytes (ZSTD level 9);
- a `bbox` covering column (xmin, ymin, xmax, ymax) on geometry tables that lack one;
- the file's own key-value metadata (source, licence, ...) carried over.

Every file is checked before it replaces the old one: the same row count and, per original
column, the same count of values and the same order-independent checksum (bit_xor of the
row hashes). A difference stops the run for that file and leaves the old file in place. The
lake catalogue's file sizes are updated after the upload. Runs in Actions (job `rewrite` of
`lake-catalog.yml`), where R2 is readable and writable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lake  # noqa: E402
from lake_catalog import R2, r2_secret  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GEO_ROWS, GEO_MB = 100_000, 32
FLAT_ROWS, FLAT_MB = 1_000_000, 128


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    if not r2_secret(con):
        raise SystemExit("R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY not set: the rewrite needs R2")
    con.execute("INSTALL spatial; LOAD spatial")
    con.execute("SET preserve_insertion_order = true")
    return con


def catalogue(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    return json.loads(
        con.execute(
            f"SELECT content FROM read_text('{R2}/{lake.PREFIX}/_catalog.json')"
        ).fetchone()[0]
    )


def dataset_catalogue(con: duckdb.DuckDBPyConnection, ds: str) -> dict[str, Any]:
    return json.loads(
        con.execute(
            f"SELECT content FROM read_text('{R2}/{lake.PREFIX}/{ds}/_catalog.json')"
        ).fetchone()[0]
    )


def is_geo(cols: dict[str, str]) -> bool:
    return any(c.lower() in ("geometry", "geom") for c in cols)


def inspect(con: duckdb.DuckDBPyConnection, out: Path) -> dict[str, Any]:
    cat = catalogue(con)
    res: dict[str, Any] = {}
    for ds in sorted(cat.get("datasets") or {}):
        if ds in ("rollups",):
            continue
        try:
            dcat = dataset_catalogue(con, ds)
        except duckdb.Error:
            continue
        for t, info in sorted((dcat.get("tables") or {}).items()):
            files = [f"{R2}/{lake.PREFIX}/{ds}/{f}" for f in info.get("files", [])]
            if not files:
                continue
            geo = is_geo(info.get("columns") or {})
            try:
                rows = con.execute(
                    "SELECT file_name, row_group_id, any_value(row_group_num_rows), sum(total_compressed_size) "
                    "FROM parquet_metadata(?) GROUP BY 1, 2",
                    [files],
                ).fetchall()
            except duckdb.Error as e:
                res[f"{ds}.{t}"] = {"error": str(e)[:200]}
                continue
            max_rows = max(r[2] for r in rows)
            max_mb = max(r[3] for r in rows) / 1e6
            lim_rows, lim_mb = (GEO_ROWS, GEO_MB) if geo else (FLAT_ROWS, FLAT_MB)
            res[f"{ds}.{t}"] = {
                "files": len(files),
                "row_groups": len(rows),
                "rows": info.get("rows"),
                "gb": round((info.get("bytes") or 0) / 1e9, 3),
                "geometry": geo,
                "max_group_rows": max_rows,
                "max_group_mb": round(max_mb, 1),
                "breach": max_rows > lim_rows * 1.05 or max_mb > lim_mb,
            }
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    bad = {k: v for k, v in res.items() if v.get("breach")}
    print(f"{len(res)} tables inspected; {len(bad)} break the row-group standard "
          f"({sum(v['gb'] for v in bad.values()):.2f} GB):")  # fmt: skip
    print(
        "| table | files | groups | largest group rows | largest group MB | GB | geometry |\n|---|---:|---:|---:|---:|---:|---|"
    )
    for k, v in sorted(bad.items(), key=lambda kv: -kv[1]["gb"]):
        print(
            f"| `{k}` | {v['files']} | {v['row_groups']} | {v['max_group_rows']:,} | {v['max_group_mb']} | {v['gb']} | {v['geometry']} |"
        )
    return res


def sql_str(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def checksums(con: duckdb.DuckDBPyConnection, src: str, cols: list[str]) -> dict[str, Any]:
    parts = ["count(*)"] + [f"count({q(c)}), bit_xor(hash({q(c)}))" for c in cols]
    r = con.execute(f"SELECT {', '.join(parts)} FROM {src}").fetchone()
    return {"rows": r[0], **{c: [r[1 + 2 * i], r[2 + 2 * i]] for i, c in enumerate(cols)}}


def rewrite_file(
    con: duckdb.DuckDBPyConnection, url: str, sort: list[str], work: Path
) -> dict[str, Any]:
    src = f"read_parquet('{url}')"
    cols = {r[0]: str(r[1]) for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    names = list(cols)
    before = checksums(con, src, names)
    kv = {
        r[0].decode() if isinstance(r[0], bytes) else r[0]: r[1].decode()
        if isinstance(r[1], bytes)
        else r[1]
        for r in con.execute(f"SELECT key, value FROM parquet_kv_metadata('{url}')").fetchall()
    }
    kv.pop("geo", None)  # DuckDB writes the GeoParquet metadata itself
    low = {c.lower(): c for c in cols}
    geom = low.get("geometry") or low.get("geom")
    if geom and "GEOMETRY" not in cols[geom].upper():
        gexpr = f"ST_GeomFromWKB({q(geom)})"
    else:
        gexpr = q(geom) if geom else None
    extra = ""
    if gexpr and "bbox" not in low:
        extra = (
            f", struct_pack(xmin := ST_XMin({gexpr}), ymin := ST_YMin({gexpr}), "
            f"xmax := ST_XMax({gexpr}), ymax := ST_YMax({gexpr})) AS bbox"
        )
    if gexpr:
        pos = f"ST_Centroid({gexpr})"
    elif (
        "lon" in low
        and "lat" in low
        and cols[low["lon"]].upper().startswith(("DOUBLE", "FLOAT", "DECIMAL", "REAL"))
    ):
        pos = f"ST_Point({q(low['lon'])}, {q(low['lat'])})"
    else:
        pos = None
    con.execute(f"CREATE OR REPLACE TEMP TABLE _rows AS SELECT *{extra} FROM {src}")
    if pos:
        ext = con.execute(
            f"SELECT min(ST_X({pos})), min(ST_Y({pos})), max(ST_X({pos})), max(ST_Y({pos})) FROM _rows"
        ).fetchone()
        if ext[0] is None:
            order = ""
        else:
            box = f"{{'min_x': {ext[0]!r}, 'min_y': {ext[1]!r}, 'max_x': {ext[2]!r}, 'max_y': {ext[3]!r}}}::BOX_2D"
            order = f" ORDER BY ST_Hilbert({pos}, {box}) NULLS LAST"
    else:
        order = (
            " ORDER BY " + ", ".join(q(c) for c in sort if c in cols)
            if [c for c in sort if c in cols]
            else ""
        )
    rows_cap, mb_cap = (GEO_ROWS, GEO_MB) if gexpr else (FLAT_ROWS, FLAT_MB)
    # DuckDB caps groups by bytes only without insertion order (which the sort needs): the rows
    # a group may hold come from the file's own compressed bytes per row, aiming at 80 % of the cap
    size = con.execute(
        f"SELECT sum(total_compressed_size) FROM parquet_metadata('{url}')"
    ).fetchone()[0]
    per_row = (size or 0) / max(before["rows"], 1)
    if per_row > 0:
        # 2,048 rows: DuckDB's smallest group (few, very large polygons stay above the MB cap)
        rows_cap = max(2_048, min(rows_cap, int(0.8 * mb_cap * 1e6 / per_row)))
    out = work / "rewrite.parquet"
    out.unlink(missing_ok=True)
    # string literals, not quoted identifiers: an empty value would be a zero-length identifier
    meta = ", ".join(f"{sql_str(k)}: {sql_str(str(v))}" for k, v in kv.items())
    con.execute(
        f"COPY (SELECT * FROM _rows{order}) TO '{out}' (FORMAT parquet, COMPRESSION zstd, "
        f"COMPRESSION_LEVEL 9, PARQUET_VERSION V2, ROW_GROUP_SIZE {rows_cap}"
        + (f", KV_METADATA {{{meta}}}" if meta else "")
        + ")"
    )
    after = checksums(con, f"read_parquet('{out}')", names)
    if after != before:
        diff = [c for c in ["rows", *names] if after.get(c) != before.get(c)]
        raise SystemExit(f"{url}: checksums differ in {diff[:5]}; the old file stays")
    groups = con.execute(
        f"SELECT count(DISTINCT row_group_id), max(row_group_num_rows) FROM parquet_metadata('{out}')"
    ).fetchone()
    con.execute("DROP TABLE _rows")
    return {"file": str(out), "bytes": out.stat().st_size, "rows": before["rows"], "groups": groups[0],
            "max_group_rows": groups[1], "checksums": "equal", "bbox_added": bool(extra)}  # fmt: skip


def upload(local: str, key: str, tries: int = 4) -> None:
    """Copy to R2, retried: R2 sometimes refuses a multipart upload's completion (InvalidPart);
    a failed upload leaves the old object in place."""
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or lake.ACCOUNT_ID
    cmd = ["aws", "s3", "cp", "--only-show-errors", "--endpoint-url",
           f"https://{acct}.r2.cloudflarestorage.com", local, f"s3://{lake.BUCKET}/{key}"]  # fmt: skip
    for i in range(tries):
        if subprocess.run(cmd).returncode == 0:
            return
        print(f"  upload of {key} failed (try {i + 1} of {tries})", flush=True)
        time.sleep(2 ** (i + 1))
    raise SystemExit(f"{key}: upload failed {tries} times; the old file stays")


def rewrite(con: duckdb.DuckDBPyConnection, tables: list[str], do_upload: bool, work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    by_ds: dict[str, list[str]] = {}
    for t in tables:
        ds, name = t.split(".", 1)
        by_ds.setdefault(ds, []).append(name)
    for ds, names in by_ds.items():
        dcat = dataset_catalogue(con, ds)
        changed = False
        try:
            for name in names:
                info = (dcat.get("tables") or {}).get(name)
                if not info:
                    print(f"{ds}.{name}: not in the catalogue")
                    continue
                for f in info.get("files", []):
                    key = f"{lake.PREFIX}/{ds}/{f}"
                    t0 = time.time()
                    r = rewrite_file(con, f"{R2}/{key}", info.get("sort") or [], work)
                    old = (info.get("file_stats") or {}).get(f, [None, None])[1]
                    print(f"  {key}: {r['rows']:,} rows, checksums equal, {r['groups']} groups (largest "
                          f"{r['max_group_rows']:,} rows), {old or 0:,} -> {r['bytes']:,} bytes"
                          f"{', bbox added' if r['bbox_added'] else ''} ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip
                    if do_upload:
                        upload(r["file"], key)
                        info.setdefault("file_stats", {})[f] = [r["rows"], r["bytes"]]
                        info["bytes"] = sum(v[1] for v in info["file_stats"].values())
                        info["layout"] = (
                            "brief 32: Hilbert order, row groups capped by rows and bytes, bbox"
                        )
                        changed = True
        finally:
            # written even when a later file fails, so the catalogue matches the files on R2
            if changed and do_upload:
                p = work / f"{ds}_catalog.json"
                p.write_text(json.dumps(dcat, indent=1, ensure_ascii=False), encoding="utf-8")
                upload(str(p), f"{lake.PREFIX}/{ds}/_catalog.json")
                print(f"catalogue lake/{ds} updated", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["inspect", "rewrite"])
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "lake_rowgroups.json")
    ap.add_argument("--tables", nargs="*", default=[])
    ap.add_argument("--breaches", action="store_true", help="rewrite every table inspect flags")
    ap.add_argument("--max-gb", type=float, default=20.0, help="stop after this much rewritten")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--work", type=Path, default=Path("/tmp/lake-rewrite"))
    a = ap.parse_args()
    con = connect()
    if a.action == "inspect":
        inspect(con, a.out)
        return
    tables = list(a.tables)
    if a.breaches:
        res = inspect(con, a.out)
        total = 0.0
        for k, v in sorted(res.items(), key=lambda kv: kv[1].get("gb", 0)):
            if v.get("breach") and total + v["gb"] <= a.max_gb:
                tables.append(k)
                total += v["gb"]
    rewrite(con, tables, a.upload, a.work)


if __name__ == "__main__":
    main()
