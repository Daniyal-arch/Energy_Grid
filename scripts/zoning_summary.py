"""Zoning coverage: rows and plans per source and country, and every Hub service with its
publisher, US state and county, from the lake tables `zoning.zones` and `zoning.hub_layers`.

Counts only (rows as stored in the lake). A Hub service's state and county are those holding the
centre of its ArcGIS Hub extent (`data/zoning_discovery/hub_services.csv`, `lon`/`lat`), matched
against the Census county outlines in `frontend/public/data/us/counties.json`; a service with no
centre or outside every county stays blank.

Writes `docs/research/zoning-coverage.md` and `data/zoning_coverage.csv`. Needs R2 (run in
`lake-catalog.yml`, input `zoning: summary`).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
import lake  # noqa: E402
from lake_catalog import R2, r2_secret  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "data" / "zoning_discovery" / "hub_services.csv"
COUNTIES = ROOT / "frontend" / "public" / "data" / "us" / "counties.json"
OUT_MD = ROOT / "docs" / "research" / "zoning-coverage.md"
OUT_CSV = ROOT / "data" / "zoning_coverage.csv"


def ring_wkt(flat: list[float]) -> str:
    pts = [f"{flat[i]} {flat[i + 1]}" for i in range(0, len(flat) - 1, 2)]
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return "(" + ", ".join(pts) + ")"


def counties(con: duckdb.DuckDBPyConnection) -> None:
    data = json.loads(COUNTIES.read_text(encoding="utf-8"))["counties"]
    rows = []
    for c in data:
        polys = [p for p in c["polygons"] if p and len(p[0]) >= 8]
        if not polys:
            continue
        wkt = (
            "MULTIPOLYGON("
            + ", ".join("(" + ", ".join(ring_wkt(r) for r in p) + ")" for p in polys)
            + ")"
        )
        rows.append((c["code"], c["name"], c["state"], wkt))
    con.execute("CREATE TABLE county (code VARCHAR, name VARCHAR, state VARCHAR, wkt VARCHAR)")
    con.executemany("INSERT INTO county VALUES (?, ?, ?, ?)", rows)
    con.execute(
        "CREATE TABLE cty AS SELECT code, name, state, ST_GeomFromText(wkt) AS g FROM county"
    )


def table(rows: list[tuple], head: list[str]) -> str:
    def fmt(v: object) -> str:
        return f"{v:,}" if isinstance(v, int) else ("" if v is None else str(v).replace("|", "/"))

    out = [
        "| " + " | ".join(head) + " |",
        "|" + "|".join("---:" if i else "---" for i in range(len(head))) + "|",
    ]
    out += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    con = duckdb.connect()
    if not r2_secret(con):
        raise SystemExit("R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY not set")
    con.execute("INSTALL spatial; LOAD spatial")
    base = f"{R2}/{lake.PREFIX}/zoning"
    zones = f"read_parquet('{base}/zones/**/*.parquet', hive_partitioning = true)"
    layers = f"read_parquet('{base}/hub_layers/**/*.parquet', hive_partitioning = true)"

    by_src = con.execute(f"""
        SELECT source, coalesce(country, '(none)') AS country, count(*)::BIGINT AS zones,
               count(DISTINCT plan_id)::BIGINT AS plans
        FROM {zones} GROUP BY ALL ORDER BY source, zones DESC""").fetchall()
    by_country = con.execute(f"""
        SELECT coalesce(country, '(none)'), count(*)::BIGINT, count(DISTINCT source)::BIGINT
        FROM {zones} GROUP BY ALL ORDER BY 2 DESC""").fetchall()
    total = con.execute(f"SELECT count(*)::BIGINT FROM {zones}").fetchone()[0]

    con.execute(f"""
        CREATE TABLE svc AS
        SELECT source, service, any_value(title) AS title, any_value(owner) AS owner,
               count(*)::BIGINT AS layers, sum(rows)::BIGINT AS zones
        FROM {layers} WHERE status = 'read' AND rows > 0 GROUP BY ALL""")
    con.execute("CREATE TABLE hub (url VARCHAR, src VARCHAR, lon DOUBLE, lat DOUBLE)")
    hub = []
    for r in csv.DictReader(SERVICES.open(encoding="utf-8")):
        try:
            hub.append((r["url"].rstrip("/"), r["source"], float(r["lon"]), float(r["lat"])))
        except ValueError:
            hub.append((r["url"].rstrip("/"), r["source"], None, None))
    con.executemany("INSERT INTO hub VALUES (?, ?, ?, ?)", hub)
    counties(con)
    con.execute("""
        CREATE TABLE out AS
        WITH h AS (SELECT url, any_value(src) AS publisher, any_value(lon) AS lon, any_value(lat) AS lat
                   FROM hub GROUP BY url),
        j AS (SELECT s.*, h.publisher, h.lon, h.lat FROM svc s LEFT JOIN h ON h.url = s.service)
        SELECT j.source, j.title, coalesce(j.publisher, j.owner) AS publisher, c.state, c.name AS county,
               j.layers, j.zones, j.service
        FROM j LEFT JOIN cty c
          ON j.lon IS NOT NULL AND ST_Contains(c.g, ST_Point(j.lon, j.lat))
        ORDER BY j.zones DESC""")
    con.execute(f"COPY out TO '{OUT_CSV}' (HEADER)")
    by_state = con.execute("""
        SELECT coalesce(state, '(no county match)'), count(*)::BIGINT, count(DISTINCT publisher)::BIGINT,
               sum(zones)::BIGINT
        FROM out WHERE source IN ('us_hub') GROUP BY ALL ORDER BY 4 DESC""").fetchall()
    top = con.execute("""
        SELECT publisher, state, county, count(*)::BIGINT, sum(zones)::BIGINT FROM out
        GROUP BY ALL ORDER BY 5 DESC LIMIT 150""").fetchall()
    n_pub = con.execute("SELECT count(DISTINCT publisher)::BIGINT FROM out").fetchone()[0]

    md = [
        "# Zoning coverage",
        "",
        "Built by `scripts/zoning_summary.py` from the lake tables `zoning.zones` and `zoning.hub_layers`",
        "(counts of stored rows). Every Hub service is in `data/zoning_coverage.csv`. A Hub service's",
        "state and county hold the centre of its ArcGIS Hub extent (Census county outlines); a",
        "service's rows may reach beyond that county, and some publishers serve one layer twice.",
        "",
        f"All zones: {total:,}.",
        "",
        "## By country (country holding each layer's first zone)",
        "",
        table(by_country, ["country", "zones", "sources"]),
        "",
        "## By source and country",
        "",
        table(by_src, ["source", "country", "zones", "plans or layers"]),
        "",
        "## United States Hub services by state",
        "",
        table(by_state, ["state", "services", "publishers", "zones"]),
        "",
        f"## Publishers with the most zones (150 of {n_pub:,})",
        "",
        table(top, ["publisher", "state", "county", "services", "zones"]),
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:40]))


if __name__ == "__main__":
    main()
