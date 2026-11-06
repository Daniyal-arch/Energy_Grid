"""Probe: what alternative names Overture divisions carry (brief 30 Track 1.2).

Reads only the `names` and key columns of `type=division` (about 0.58 GB in all; the filter on
country and subtype reads a fraction) from the public Overture bucket, for the names the agent
must resolve first try: English names and exonyms of Bavaria, Brittany, Lower Saxony, Silesia,
the Ruhr, Greater Manchester, Puglia and North Rhine-Westphalia.

    uv run python scripts/probe_overture_names.py [release]
"""

from __future__ import annotations

import sys
import time

import duckdb
import httpx

OVERTURE = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/"
WANTED = {
    "DE": ["Bayern", "Niedersachsen", "Nordrhein-Westfalen", "Ruhr", "Regionalverband Ruhr"],
    "FR": ["Bretagne"],
    "PL": ["województwo śląskie", "Śląskie", "Silesia"],
    "GB": ["Greater Manchester"],
    "IT": ["Puglia"],
}


def newest() -> str:
    import re

    xml = httpx.get(
        OVERTURE, params={"list-type": "2", "prefix": "release/", "delimiter": "/"}, timeout=60
    ).text
    return sorted(re.findall(r"<Prefix>release/([^<]+)/</Prefix>", xml))[-1]


def main() -> None:
    rel = sys.argv[1] if len(sys.argv) > 1 else newest()
    print("release", rel)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region = 'us-west-2'")
    base = f"s3://overturemaps-us-west-2/release/{rel}/theme=divisions/type=division/*"
    t0 = time.time()
    con.execute(
        f"""CREATE TABLE d AS SELECT id, subtype, country, names
            FROM read_parquet('{base}', hive_partitioning = false)
            WHERE country IN ('DE', 'FR', 'PL', 'GB', 'IT')
              AND subtype IN ('region', 'macroregion', 'county', 'macrocounty')"""
    )
    print(
        f"read {con.execute('SELECT count(*) FROM d').fetchone()[0]:,} rows in {time.time() - t0:.0f} s"
    )
    print("names struct:", con.execute("SELECT typeof(names) FROM d LIMIT 1").fetchone()[0][:300])
    for cc, ns in WANTED.items():
        for n in ns:
            rows = con.execute(
                """SELECT subtype, names.primary, names.common['en'],
                          cardinality(names.common), names.rules
                   FROM d WHERE country = $c AND (lower(names.primary) = lower($n)
                     OR list_contains(list_transform(map_values(names.common), lambda x: lower(x)), lower($n)))""",
                {"c": cc, "n": n},
            ).fetchall()
            for r in rows:
                print(
                    f"{cc} {n!r}: {r[0]} primary={r[1]!r} en={r[2]!r} languages={r[3]} rules={str(r[4])[:200]}"
                )
            if not rows:
                print(f"{cc} {n!r}: no match")


if __name__ == "__main__":
    main()
