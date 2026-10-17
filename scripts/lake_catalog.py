"""The lake's catalogue and its DuckDB file (docs/DATA_LAKE.md sections 3, 5 and 8).

Reads every dataset's `lake/<dataset>/_catalog.json` from R2 and writes
  lake/_catalog.json  {"updated", "rows", "bytes", "datasets": {name: {source, licence,
                       updated, rows, bytes, tables: {table: {path, partitions, rows, bytes, columns}}}}}
  lake/lake.duckdb    read-only: one schema per dataset with a view per table over its R2 path
                       (hive partitioning), and the topic views of section 3 in `main`:
                       plants, prices, outages, emissions, grid_capacity, water_risk, each with
                       a `source` column. A topic view takes the sources whose tables exist;
                       sources added later join when the catalogue runs again.

DuckDB binds a view when it is created, so the file is built where R2 is readable: in GitHub
Actions (.github/workflows/lake-catalog.yml) with S3 credentials derived from the Cloudflare
API token (key id = the token's id, secret = SHA-256 of the token; never printed, never
stored in the file). The agent opens the file and creates its own R2 secret:

    ATTACH 'lake.duckdb' (READ_ONLY); USE lake;
    CREATE SECRET (TYPE r2, KEY_ID '...', SECRET '...', ACCOUNT_ID '...');
    SELECT * FROM outages WHERE source = 'EAGLE-I' AND area = '48201' LIMIT 5;

    python scripts/lake_catalog.py --out lake-out [--upload]
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import lake

R2 = f"r2://{lake.BUCKET}"

# Topic views: per source a table and, per standard column, the candidate source columns
# (the first one the table has is used, else NULL). Values pass through; nothing is computed.
TOPICS: dict[str, dict] = {
    "plants": {
        "columns": [
            "id",
            "name",
            "technology",
            "capacity_mw",
            "status",
            "start",
            "lon",
            "lat",
            "iso2",
            "iso3",
            "admin1",
        ],
        "sources": [
            (
                "MaStR",
                "mastr",
                "units_*",
                {
                    "id": ["mastr_nr"],
                    "name": ["namestromerzeugungseinheit", "NameStromerzeugungseinheit"],
                    "technology": ["energietraeger", "Energietraeger"],
                    "capacity_mw": ["gross_kw / 1000"],
                    "status": ["status"],
                    "start": ["commissioned"],
                    "lon": ["lon"],
                    "lat": ["lat"],
                },
            ),
            (
                "EIA-860M",
                "eia860m",
                "generators",
                {
                    "id": ["plant_id || '-' || generator_id"],
                    "name": ["plant_name"],
                    "technology": ["technology"],
                    "capacity_mw": ["nameplate_capacity_mw"],
                    "status": ["status", "sheet"],
                    "start": ["operating_year"],
                    "lon": ["longitude"],
                    "lat": ["latitude"],
                },
            ),
            (
                "JRC-PPDB",
                "power_plants_eu",
                "jrc_units",
                {
                    "id": ["eic_g"],
                    "name": ["name_g"],
                    "technology": ["type_g"],
                    "capacity_mw": ["capacity_g"],
                    "status": ["status_g"],
                    "start": ["year_commissioned"],
                    "lon": ["lon_", "lon"],
                    "lat": ["lat_", "lat"],
                },
            ),
            (
                "powerplantmatching",
                "power_plants_eu",
                "ppm_plants",
                {
                    "id": ["id"],
                    "name": ["name"],
                    "technology": ["fueltype"],
                    "capacity_mw": ["capacity"],
                    "status": ["NULL"],
                    "start": ["datein"],
                    "lon": ["lon"],
                    "lat": ["lat"],
                },
            ),
            (
                "ENTSO-E",
                "entsoe",
                "units",
                {
                    "id": ["unit_eic"],
                    "name": ["name"],
                    "technology": ["psr_type"],
                    "capacity_mw": ["capacity_mw"],
                    "status": ["NULL"],
                    "start": ["NULL"],
                    "lon": ["lon"],
                    "lat": ["lat"],
                },
            ),
            (
                "GEM",
                "gem",
                "integrated_power_*",
                {
                    "id": ["gem_unit_phase_id", "gem_unit_id", "gem_location_id"],
                    "name": ["plant_project_name", "project_name", "plant_name", "unit_name"],
                    "technology": ["type", "technology", "fuel"],
                    "capacity_mw": ["capacity_mw"],
                    "status": ["status"],
                    "start": ["start_year"],
                    "lon": ["longitude"],
                    "lat": ["latitude"],
                },
            ),
        ],
    },
    "prices": {
        "columns": ["ts", "area", "resolution_min", "price", "currency", "iso2", "iso3", "admin1"],
        "sources": [
            (
                "ENTSO-E day-ahead",
                "entsoe",
                "prices",
                {
                    "ts": ["ts"],
                    "area": ["area"],
                    "resolution_min": ["resolution_min"],
                    "price": ["price"],
                    "currency": ["currency"],
                },
            ),
            (
                "US nodal day-ahead",
                "us_lmp",
                "day_ahead",
                {
                    "ts": ["ts"],
                    "area": ["node_id"],
                    "resolution_min": ["60"],
                    "price": ["lmp"],
                    "currency": ["'USD'"],
                },
            ),
        ],
    },
    "outages": {
        "columns": ["source_id", "area", "start", "end", "value", "unit", "iso2", "iso3", "admin1"],
        "sources": [
            (
                "EAGLE-I",
                "eaglei",
                "outages",
                {
                    "source_id": ["NULL"],
                    "area": ["fips"],
                    "start": ["ts"],
                    "end": ["ts + INTERVAL 15 MINUTE"],
                    "value": ["customers_out"],
                    "unit": ["'customers out (utility meters)'"],
                },
            ),
            (
                "ENTSO-E A80",
                "entsoe",
                "outages",
                {
                    "source_id": ["mrid || '/' || revision"],
                    "area": ["asset_eic"],
                    "start": ['"start"'],
                    "end": ['"end"'],
                    "value": ["available_mw"],
                    "unit": ["'MW available during the outage'"],
                },
            ),
        ],
    },
    "emissions": {
        "columns": ["id", "name", "year", "value", "unit", "iso2", "iso3", "admin1"],
        "sources": [
            (
                "EU ETS verified",
                "euets",
                "verified_emissions",
                {
                    "id": ["installation_identifier", "installation_id", "id"],
                    "name": ["installation_name", "name"],
                    "year": ["year"],
                    "value": ["verified_emissions", "verified"],
                    "unit": ["'t CO2e'"],
                },
            ),
        ],
    },
    "grid_capacity": {
        "columns": ["id", "name", "status", "mw", "iso2", "iso3", "admin1"],
        "sources": [
            (
                "NESO TEC",
                "neso_tec",
                "projects",
                {
                    "id": ["project_id"],
                    "name": ["project_name"],
                    "status": ["project_status"],
                    "mw": ["cumulative_total_capacity_mw"],
                },
            ),
            (
                "Netbeheer Nederland",
                "nl_capacity",
                "areas",
                {
                    "id": ["objectid", "fid"],
                    "name": ["naam", "name"],
                    "status": ["afname"],
                    "mw": ["wachtrij_afname"],
                },
            ),
            (
                "REE",
                "ree_nodes",
                "nodes",
                {"id": ["nudo"], "name": ["nudo"], "status": ["NULL"], "mw": ["NULL"]},
            ),
            (
                "LBNL Queued Up",
                "lbnl_queue",
                "requests",
                {"id": ["q_id"], "name": ["project_name"], "status": ["q_status"], "mw": ["mw1"]},
            ),
        ],
    },
    "water_risk": {
        "columns": [
            "id",
            "basin",
            "indicator_bws_cat",
            "indicator_bws_label",
            "rfr_label",
            "cfr_label",
            "drr_label",
            "geometry",
            "iso2",
            "iso3",
            "admin1",
        ],
        "sources": [
            (
                "WRI Aqueduct 4.0",
                "aqueduct",
                "baseline_annual",
                {
                    "id": ["aq30_id"],
                    "basin": ["pfaf_id"],
                    "indicator_bws_cat": ["bws_cat"],
                    "indicator_bws_label": ["bws_label"],
                    "rfr_label": ["rfr_label"],
                    "cfr_label": ["cfr_label"],
                    "drr_label": ["drr_label"],
                    "geometry": ["geometry"],
                },
            ),
        ],
    },
}


def r2_secret(con: duckdb.DuckDBPyConnection) -> bool:
    key, secret = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or lake.ACCOUNT_ID
    if not key or not secret:
        return False
    con.execute("INSTALL httpfs; LOAD httpfs")
    con.execute(
        f"CREATE OR REPLACE SECRET lake (TYPE r2, KEY_ID '{key}', SECRET '{secret}', ACCOUNT_ID '{account}')"
    )
    return True


def read_catalogues(con: duckdb.DuckDBPyConnection, have_s3: bool, tmp: Path) -> dict[str, dict]:
    """Every lake/<dataset>/_catalog.json (S3 glob; else wrangler for the known datasets)."""
    out: dict[str, dict] = {}
    if have_s3:
        for path, text in con.execute(
            f"SELECT filename, content FROM read_text('{R2}/{lake.PREFIX}/*/_catalog.json')"
        ).fetchall():
            cat = json.loads(text)
            out[cat.get("dataset") or path.split("/")[-2]] = cat
        return out
    tmp.mkdir(parents=True, exist_ok=True)
    for name in KNOWN:
        local = tmp / f"{name}.json"
        if lake.wrangler(
            "r2",
            "object",
            "get",
            f"{lake.BUCKET}/{lake.PREFIX}/{name}/_catalog.json",
            "--file",
            str(local),
            "--remote",
        ):
            out[name] = json.loads(local.read_text(encoding="utf-8"))
    return out


KNOWN = [
    "eaglei", "aqueduct", "mastr", "entsoe", "overture_power", "entsog", "eia930", "eia860m",
    "lbnl_queue", "irena", "power_plants_eu", "gem", "osm", "euets", "neso_tec", "nl_capacity",
    "ree_nodes", "us_lmp",
]  # fmt: skip


def repair(con: duckdb.DuckDBPyConnection, cats: dict[str, dict], out: Path, upload: bool) -> None:
    """Rebuild each dataset's file list, rows and bytes from the files on R2 (parallel jobs of
    one dataset can overwrite each other's catalogue); upload the catalogues that changed."""
    for ds, cat in cats.items():
        found = con.execute(
            f"""SELECT file_name, sum(row_group_num_rows) FILTER (WHERE column_id = 0)
                FROM parquet_metadata('{R2}/{lake.PREFIX}/{ds}/**/*.parquet') GROUP BY 1"""
        ).fetchall()
        sizes = (
            dict(
                con.execute(
                    f"SELECT filename, size FROM read_blob('{R2}/{lake.PREFIX}/{ds}/**/*.parquet')"
                ).fetchall()
            )
            if found
            else {}
        )
        prefix = f"{R2}/{lake.PREFIX}/{ds}/"
        changed = False
        for f, rows in found:
            rel = f.removeprefix(prefix)
            table = rel.split("/", 1)[0].removesuffix(".parquet")
            t = cat.setdefault("tables", {}).get(table)
            if t is None:
                print(f"  {ds}: {rel} belongs to no table in the catalogue")
                continue
            stats = t.setdefault("file_stats", {})
            entry = [int(rows or 0), int(sizes.get(f, 0))]
            if stats.get(rel) != entry or rel not in t.get("files", []):
                stats[rel] = entry
                t["files"] = sorted({*t.get("files", []), rel})
                changed = True
        for t in cat.get("tables", {}).values():
            stats = t.get("file_stats", {})
            gone = [f for f in t.get("files", []) if f"{prefix}{f}" not in {x for x, _ in found}]
            for f in gone:
                t["files"].remove(f)
                stats.pop(f, None)
                changed = True
            t["rows"] = sum(v[0] for v in stats.values())
            t["bytes"] = sum(v[1] for v in stats.values())
        if changed:
            path = out / "catalogues" / f"{ds}.repaired.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"  {ds}: catalogue repaired from R2", flush=True)
            if upload and not lake.wrangler(
                "r2",
                "object",
                "put",
                f"{lake.BUCKET}/{lake.PREFIX}/{ds}/_catalog.json",
                "--file",
                str(path),
                "--remote",
            ):
                raise SystemExit(f"upload of {ds}/_catalog.json failed")


def summary(cats: dict[str, dict]) -> dict:
    datasets = {}
    for name, c in sorted(cats.items()):
        tables = {
            t: {
                k: v[k]
                for k in ("path", "partitions", "sort", "rows", "bytes", "columns")
                if k in v
            }
            for t, v in c.get("tables", {}).items()
        }
        datasets[name] = {
            "source": c.get("source"),
            "licence": c.get("licence"),
            "updated": c.get("updated"),
            "rows": sum(t["rows"] for t in tables.values()),
            "bytes": sum(t["bytes"] for t in tables.values()),
            "tables": tables,
        }
    return {
        "updated": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": sum(d["rows"] for d in datasets.values()),
        "bytes": sum(d["bytes"] for d in datasets.values()),
        "datasets": datasets,
    }


def view_path(table: dict) -> str:
    return f"{R2}/{table['path']}"


def pick(columns: dict[str, str], candidates: list[str]) -> str:
    """The first candidate the table has (an expression whose first word is a column counts
    when that column exists; literals and NULL always count)."""
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        head = cand.split()[0].strip('"')
        if cand == "NULL" or cand.startswith("'") or cand[0].isdigit():
            return cand
        if cand.startswith('"'):
            if head.lower() in lower:
                return cand
            continue
        if head.lower() in lower:
            return cand.replace(head, f'"{lower[head.lower()]}"', 1) if " " not in cand else cand
    return "NULL"


def build_duckdb(path: Path, cats: dict[str, dict]) -> dict[str, list[str]]:
    """lake.duckdb: schemas with a view per table, topic views in main. Returns, per topic,
    the sources it holds."""
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    if not r2_secret(con):
        raise SystemExit("R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY not set: lake.duckdb needs R2")
    tables: dict[tuple[str, str], dict] = {}
    for ds, c in sorted(cats.items()):
        con.execute(f'CREATE SCHEMA IF NOT EXISTS "{ds}"')
        for t, v in sorted(c.get("tables", {}).items()):
            hive = "true" if v.get("partitions") else "false"
            try:
                con.execute(
                    f"""CREATE OR REPLACE VIEW "{ds}"."{t}" AS SELECT * FROM read_parquet(
                        '{view_path(v)}', hive_partitioning = {hive}, union_by_name = true)"""
                )
                tables[(ds, t)] = {
                    r[0]: r[1] for r in con.execute(f'DESCRIBE "{ds}"."{t}"').fetchall()
                }
            except duckdb.Error as e:
                print(f"  {ds}.{t}: no view ({str(e)[:160]})", flush=True)
    held: dict[str, list[str]] = {}
    for topic, spec in TOPICS.items():
        parts = []
        for source, ds, pattern, cols in spec["sources"]:
            names = [
                t
                for (d, t) in tables
                if d == ds
                and (
                    pattern == "*"
                    or t == pattern
                    or (pattern.endswith("*") and t.startswith(pattern[:-1]))
                )
            ]
            for t in names:
                have = tables[(ds, t)]
                if (
                    pattern.endswith("*")
                    and pick(have, cols.get("capacity_mw", ["NULL"])) == "NULL"
                ):
                    continue  # a GEM sheet without capacities is not a plant list
                sel = [f"'{source}' AS source", f"'{ds}.{t}' AS source_table"]
                for col in spec["columns"]:
                    sel.append(f'{pick(have, cols.get(col, [col]))} AS "{col}"')
                parts.append(f'SELECT {", ".join(sel)} FROM "{ds}"."{t}"')
                held.setdefault(topic, []).append(f"{source} ({ds}.{t})")
        if parts:
            con.execute(
                f"CREATE OR REPLACE VIEW main.{topic} AS {' UNION ALL BY NAME '.join(parts)}"
            )
    con.close()
    return held


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("lake-out"))
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    have_s3 = r2_secret(con)
    cats = read_catalogues(con, have_s3, args.out / "catalogues")
    if have_s3:
        repair(con, cats, args.out, args.upload)
    cat = summary(cats)
    cat_path = args.out / "_catalog.json"
    print("| dataset | table | rows | bytes |\n|---|---|---:|---:|")
    for ds, d in cat["datasets"].items():
        for t, v in d["tables"].items():
            print(f"| {ds} | {t} | {v['rows']:,} | {v['bytes']:,} |")
    print(f"| **all** | | **{cat['rows']:,}** | **{cat['bytes']:,}** |")
    print("\n| dataset | tables | rows | bytes |\n|---|---:|---:|---:|")
    for ds, d in cat["datasets"].items():
        print(f"| {ds} | {len(d['tables'])} | {d['rows']:,} | {d['bytes']:,} |")
    db = args.out / "lake.duckdb"
    if have_s3:
        cat["topics"] = build_duckdb(db, cats)
        print(f"lake.duckdb: {db.stat().st_size / 1e6:.2f} MB; topics {json.dumps(cat['topics'])}")
    cat_path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.upload:
        for f in [cat_path, *([db] if db.exists() else [])]:
            key = f"{lake.BUCKET}/{lake.PREFIX}/{f.name}"
            if not lake.wrangler("r2", "object", "put", key, "--file", str(f), "--remote"):
                raise SystemExit(f"upload of {f.name} failed")


if __name__ == "__main__":
    main()
