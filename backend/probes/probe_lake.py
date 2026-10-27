"""Probe: DuckDB over the lake on R2 (or, without the R2 token, the public map files: bundled and the eu-days branch).

Measures the cold open and a typical query, and checks the security settings the service relies
on: extensions loadable from a local directory, `allowed_directories` / `allowed_paths` with
`enable_external_access = false`, and `lock_configuration`.

    uv run python probes/probe_lake.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public" / "data"
REMOTE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu/"


def timed(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[float, list]:
    t = time.perf_counter()
    rows = con.execute(sql).fetchall()
    return time.perf_counter() - t, rows


def main() -> None:
    print("duckdb", duckdb.__version__)
    con = duckdb.connect()
    for ext in ("httpfs", "spatial"):
        t = time.perf_counter()
        con.install_extension(ext)
        con.load_extension(ext)
        print(f"install+load {ext}: {time.perf_counter() - t:.2f} s")
    print(
        "extension_directory:",
        con.execute("SELECT current_setting('extension_directory')").fetchone(),
    )

    if os.environ.get("R2_ACCESS_KEY_ID") and os.environ.get("R2_SECRET_ACCESS_KEY"):
        acct = os.environ["R2_ACCOUNT_ID"]
        con.execute(
            "CREATE SECRET r2 (TYPE r2, KEY_ID ?, SECRET ?, ACCOUNT_ID ?)",
            [os.environ["R2_ACCESS_KEY_ID"], os.environ["R2_SECRET_ACCESS_KEY"], acct],
        )
        dt, rows = timed(
            con, "SELECT count(*) FROM read_json_auto('r2://infraatlas-raw/lake/_catalog.json')"
        )
        print(f"lake catalogue cold: {dt:.2f} s {rows}")
        dt, rows = timed(
            con,
            "SELECT count(*), sum(customers_out) FROM read_parquet('r2://infraatlas-raw/lake/eaglei/outages/year=2024/*.parquet') WHERE fips = '48201'",
        )
        print(f"eaglei 2024 Harris County cold: {dt:.2f} s {rows}")
    else:
        print(
            "LAKE BLOCKED: R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ACCOUNT_ID not set; reading the public map files"
        )

    # public map files: bundled (local) and the eu-data branch (HTTPS)
    dt, rows = timed(
        con,
        f"SELECT len(plants) FROM read_json('{PUBLIC}/eu/plants.json', maximum_object_size=200000000)",
    )
    print(f"local plants.json: {dt:.2f} s, {rows[0][0]} plants")
    dt, rows = timed(
        con,
        f"SELECT fetched, len(json_keys(zones)) FROM read_json('{REMOTE}prices.json', maximum_object_size=200000000, columns={{'fetched': 'VARCHAR', 'zones': 'JSON'}})",
    )
    print(f"remote eu-days prices.json cold: {dt:.2f} s {rows}")
    dt, rows = timed(
        con,
        f"SELECT fetched FROM read_json('{REMOTE}prices.json', maximum_object_size=200000000, columns={{'fetched': 'VARCHAR', 'zones': 'JSON'}})",
    )
    print(f"remote eu-days prices.json warm: {dt:.2f} s")

    # the lockdown: only allowed paths, then the configuration locked
    sec = duckdb.connect()
    sec.load_extension("httpfs")
    # persistent secrets live under ~/.duckdb: off, or the lockdown blocks every remote read
    sec.execute("SET allow_persistent_secrets = false")
    sec.execute(f"SET allowed_directories = ['{PUBLIC}/', '{REMOTE}']")
    # HTTPS needs the CA bundle readable under the lockdown (DuckDB 2.0)
    ca = os.environ.get("SSL_CERT_FILE") or "/etc/ssl/certs/ca-certificates.crt"
    sec.execute(f"SET ca_cert_file = '{ca}'")
    sec.execute(f"SET allowed_paths = ['{ca}']")
    sec.execute("SET enable_external_access = false")
    sec.execute("SET lock_configuration = true")
    for label, sql in [
        (
            "allowed local file",
            f"SELECT count(*) FROM read_json('{PUBLIC}/eu/countries.json', maximum_object_size=200000000)",
        ),
        (
            "allowed remote prefix",
            f"SELECT fetched FROM read_json('{REMOTE}prices.json', maximum_object_size=200000000, columns={{'fetched': 'VARCHAR'}})",
        ),
        ("refused /etc/passwd", "SELECT * FROM read_csv('/etc/passwd')"),
        ("refused other URL", "SELECT * FROM read_csv('https://example.com/x.csv')"),
        ("refused SET", "SET enable_external_access = true"),
        ("refused INSTALL", "INSTALL tpch"),
    ]:
        try:
            t = time.perf_counter()
            r = sec.execute(sql).fetchall()
            print(f"{label}: OK {time.perf_counter() - t:.2f} s {str(r)[:60]}")
        except Exception as e:  # noqa: BLE001
            print(f"{label}: REFUSED {type(e).__name__}: {str(e).splitlines()[0][:110]}")


if __name__ == "__main__":
    main()
