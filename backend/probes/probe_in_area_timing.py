"""Timing of in_area on the lake's large tables (brief 27 A7), from a Lambda-sized container.

    R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \\
        uv run python probes/probe_in_area_timing.py

Four areas (a country, a region, a city, a drawn polygon) and three tables (Overture power
sites, MaStR solar units, Global Renewables Watch solar arrays and wind turbines); each query
runs twice (cold, then warm). Prints a Markdown table for the PR.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RUHR = [[6.6, 51.33], [7.75, 51.33], [7.75, 51.65], [6.6, 51.65], [6.6, 51.33]]
QUERIES = {
    "Overture power sites": "SELECT count(*) FROM overture_power.sites "
    "WHERE intersects_area(geometry, '{a}', bbox)",
    "MaStR solar units": "SELECT count(*), round(sum(gross_kw) / 1000) FROM mastr.units_solar "
    "WHERE in_area(lon, lat, '{a}')",
    "GRW solar arrays": "SELECT count(*) FROM grw.solar WHERE intersects_area(geometry, '{a}', bbox)",
    "GRW wind turbines": "SELECT count(*) FROM grw.wind WHERE intersects_area(geometry, '{a}', bbox)",
}


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    os.environ.setdefault("AGENT_MODEL", "fake")
    os.environ["RESULTS_DIR"] = str(tmp)
    os.environ["LOCAL_STORE_DIR"] = str(tmp / "store")
    from app.settings import Settings
    from tools.areas import resolve_area
    from tools.context import ToolContext
    from tools.sql import run_sql

    s = Settings()
    s.sql_timeout_s = 120
    ctx = ToolContext(s)
    print(f"lake: {ctx.lake.lake_mode}; tables: {len(ctx.lake.tables())}", flush=True)
    areas = {}
    for label, args in (
        ("country: Germany", {"names": ["Germany"]}),
        ("region: Bavaria", {"names": ["Bayern"], "level": "region"}),
        ("city: Berlin", {"names": ["Berlin"], "level": "city"}),
        ("drawn polygon: Ruhr box", None),
    ):
        if args is None:
            ctx.view = {"drawn": {"kind": "polygon", "ring": RUHR[:-1], "name": "Ruhr"}}
            args = {"from_view": "drawn"}
        r = resolve_area(ctx, **args)["data"]
        a = r.get("area")
        if not a and label.startswith("region"):
            a = resolve_area(ctx, names=["Bavaria"], level="region")["data"].get("area")
        if not a:
            print(f"{label}: not resolved: {r}")
            continue
        areas[label] = a
        print(f"{label}: {a['name']} ({a['level']}, {a['area_km2']:,.0f} km², {a['area_id']})")
    rows = []
    for table, sql in QUERIES.items():
        for label, a in areas.items():
            times, result = [], None
            for _ in range(2):
                t0 = time.perf_counter()
                out = run_sql(ctx, sql.replace("{a}", a["area_id"]))["data"]
                times.append(time.perf_counter() - t0)
                result = out.get("rows") or out.get("error")
            rows.append((table, label, result, times))
            print(f"{table} | {label} | {result} | {times[0]:.2f} s | {times[1]:.2f} s", flush=True)
    print("\n| Table | Area | Result | Cold | Warm |\n|---|---|---|---|---|")
    for table, label, result, t in rows:
        print(f"| {table} | {label} | {result} | {t[0]:.2f} s | {t[1]:.2f} s |")


if __name__ == "__main__":
    main()
