"""Time agent-like queries against PUDL's public Parquet in place (docs/DATA_LAKE.md section 1,
"already in a public cloud bucket": query in place only if rule 2 holds, ~5 s).

Runs on a GitHub runner (.github/workflows/lake-catalog.yml, job `pudl`), where the agent
would run: DuckDB over HTTPS range requests, no copy. Three questions:
  1. EPA CEMS hourly: one plant in one month
  2. EPA CEMS hourly: one state in one year
  3. EIA-923 monthly generation: one plant, every month
Each is run twice (cold, then with DuckDB's metadata cache) and the file's size and row groups
are printed, so the timings can be read against the rule.

    python scripts/probe_pudl.py
"""

from __future__ import annotations

import time

import duckdb
import httpx

BASE = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable"
CEMS = f"{BASE}/core_epacems__hourly_emissions.parquet"
GEN = f"{BASE}/core_eia923__monthly_generation.parquet"
PLANT = 3  # Barry (Alabama), a large coal and gas plant reporting to both


def timed(con: duckdb.DuckDBPyConnection, label: str, sql: str) -> float:
    t = time.time()
    try:
        rows = con.execute(sql).fetchall()
    except duckdb.Error as e:  # a column named otherwise: say so, keep going
        print(f"{label}: failed after {time.time() - t:.1f} s: {str(e)[:200]}", flush=True)
        return float("inf")
    dt = time.time() - t
    print(f"{label}: {dt:.1f} s -> {rows[:3]}", flush=True)
    return dt


def main() -> None:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET enable_object_cache = true")
    for url in (CEMS, GEN):
        size = int(httpx.head(url, timeout=60).headers.get("content-length", 0))
        meta = con.execute(
            f"SELECT count(DISTINCT row_group_id), max(row_group_num_rows) FROM parquet_metadata('{url}')"
        ).fetchone()
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{url}'").fetchall()]
        print(
            f"{url.rsplit('/', 1)[1]}: {size / 1e9:.2f} GB, {meta[0]} row groups of up to {meta[1]:,} rows; columns {cols}",
            flush=True,
        )
    results = {}
    for run in ("cold", "warm"):
        results[run] = [
            timed(
                con,
                f"[{run}] CEMS plant {PLANT}, July 2023",
                f"""SELECT count(*), sum(gross_load_mw), sum(co2_mass_tons) FROM '{CEMS}'
                    WHERE plant_id_eia = {PLANT} AND operating_datetime_utc >= '2023-07-01'
                      AND operating_datetime_utc < '2023-08-01'""",
            ),
            timed(
                con,
                f"[{run}] CEMS Texas, 2023",
                f"""SELECT count(*), sum(gross_load_mw), sum(co2_mass_tons) FROM '{CEMS}'
                    WHERE state = 'TX' AND year = 2023""",
            ),
            timed(
                con,
                f"[{run}] EIA-923 plant {PLANT}, monthly generation",
                f"""SELECT count(*), min(report_date), max(report_date), sum(net_generation_mwh)
                    FROM '{GEN}' WHERE plant_id_eia = {PLANT}""",
            ),
        ]
    slow = [i + 1 for i, t in enumerate(results["cold"]) if t > 5]
    print(f"over 5 s (cold): questions {slow or 'none'}", flush=True)


if __name__ == "__main__":
    main()
