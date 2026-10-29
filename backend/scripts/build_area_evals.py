"""Build agent/evals/areas.yaml: twenty area questions (brief 27 A7) with the tool calls that
answer them and, where the app's map files hold the data, the answer computed by those calls.

    uv run python scripts/build_area_evals.py

Each case: the question, the view the browser sends (for "what I drew" and "here"), the
resolve_area arguments, the expected area level, the SQL over the resolved area ({area} stands
for its id) and the expected numbers. `needs: lake` cases need the lake on R2 (outline sets,
GRW, room to connect, protected areas) and keep their expected numbers empty until a run with
the lake fills them (`--lake`). The scripted fake model (agent/fake.py) plays these calls so the
whole graph runs them in CI; a real model is scored on the same file by evals/run.py.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "agent" / "evals" / "areas.yaml"

RUHR = [[6.6, 51.33], [7.75, 51.33], [7.75, 51.65], [6.6, 51.65], [6.6, 51.33]]

CASES: list[dict[str, Any]] = [
    {
        "id": "area-benelux-plants",
        "q": "How much power plant capacity of 20 MW and more is in the Benelux?",
        "resolve": {"names": ["Benelux"]},
        "level": "group",
        # countries and groups: by the table's country key (offshore and coastal sites count)
        "sql": "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE country IN ('BE', 'NL', 'LU')",
    },
    {
        "id": "area-lyon-30km",
        "q": "What generating capacity lies within 30 km of Lyon?",
        "resolve": {"names": ["Lyon"], "radius_km": 30},
        "level": "circle",
        "sql": "SELECT fuel, count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE in_area(lon, lat, '{area}') GROUP BY fuel ORDER BY mw DESC",
    },
    {
        "id": "area-drawn-substations",
        "q": "How many substations are in the area I drew?",
        "view": {"drawn": {"kind": "polygon", "ring": RUHR[:-1], "name": "Drawn area"}},
        "resolve": {"from_view": "drawn"},
        "level": "polygon",
        "sql": "SELECT count(*) AS substations FROM app.eu_substations "
        "WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-screen-plants",
        "q": "How many plants are on the map on screen right now?",
        "view": {"camera": {"center": [4.5, 52.1], "zoom": 8, "bounds": [3.9, 51.7, 5.1, 52.5]}},
        "resolve": {"from_view": "screen"},
        "level": "bbox",
        "sql": "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-harris-county",
        "q": "Which power plants operate in Harris County, Texas?",
        "resolve": {"names": ["Harris County, Texas"]},
        "level": "us_county",
        "sql": "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.us_plants "
        "WHERE status = 'operating' AND in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-texas-map",
        "q": "Show the operating power plants in Texas on a map, clipped to the state.",
        "resolve": {"names": ["Texas"]},
        "level": "us_state",
        "sql": "SELECT name, type, mw, lon, lat FROM app.us_plants "
        "WHERE status = 'operating' AND in_area(lon, lat, '{area}')",
        "map": {"kind": "points", "key": "lon/lat"},
    },
    {
        "id": "area-nordics-fuel",
        "q": "Power plant capacity in the Nordics by fuel.",
        "resolve": {"names": ["the Nordics"]},
        "level": "group",
        "sql": "SELECT fuel, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE country IN ('DK', 'FI', 'IS', 'NO', 'SE') GROUP BY fuel ORDER BY mw DESC",
    },
    {
        "id": "area-munich-50km",
        "q": "How many plants of 20 MW and more are within 50 km of Munich?",
        "resolve": {"names": ["Munich"], "radius_km": 50},
        "level": "circle",
        "sql": "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-belgium-buffer",
        "q": "How many substations are in Belgium and within 20 km of its border?",
        "resolve": {"names": ["Belgium"], "buffer_km": 20},
        "level": "polygon",
        "sql": "SELECT count(*) AS substations FROM app.eu_substations "
        "WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-world-coal",
        "q": "How much coal capacity operates in the world?",
        "resolve": {"names": ["world"]},
        "level": "world",
        "sql": "SELECT round(sum(mw)) AS mw FROM app.world_plants "
        "WHERE type = 'coal' AND status = 'operating' AND in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-baltics-fuel",
        "q": "Generating capacity in the Baltic states by fuel.",
        "resolve": {"names": ["Baltics"]},
        "level": "group",
        "sql": "SELECT fuel, round(sum(mw)) AS mw FROM app.eu_plants "
        "WHERE country IN ('EE', 'LV', 'LT') GROUP BY fuel ORDER BY mw DESC",
    },
    {
        "id": "area-belgium-lines",
        "q": "How many km of high-voltage line run inside Belgium?",
        "resolve": {"names": ["Belgium"]},
        "level": "country",
        "sql": "SELECT round(sum(km_inside(geometry, '{area}')), 1) AS km FROM app.eu_lines "
        "WHERE intersects_area(geometry, '{area}')",
    },
    {
        "id": "area-bavaria-solar",
        "q": "Show the solar farms in Bavaria on a map.",
        "resolve": {"names": ["Bavaria"]},
        "level": "region",
        "needs": "lake",
        "sql": "SELECT count(*) AS arrays, round(sum(area_km2), 2) AS km2 FROM grw.solar "
        "WHERE intersects_area(geometry, '{area}', bbox)",
        "map": {"kind": "hexbin", "key": "lon/lat"},
    },
    {
        "id": "area-lyon-free-capacity",
        "q": "How much free grid capacity is published within 30 km of Lyon?",
        "resolve": {"names": ["Lyon"], "radius_km": 30},
        "level": "circle",
        "needs": "lake",
        "sql": "SELECT count(*) AS substations, round(sum(free_mw), 1) AS free_mw "
        "FROM connect_harmonised.sites WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-london-lines",
        "q": "How many km of high-voltage line are in Greater London?",
        "resolve": {"names": ["London"], "level": "region"},
        "level": "nuts1",
        "needs": "lake",
        "sql": "SELECT round(sum(km_inside(geometry, '{area}')), 1) AS km FROM app.eu_lines "
        "WHERE intersects_area(geometry, '{area}')",
    },
    {
        "id": "area-dublin-datacentres",
        "q": "How many data centres are in Dublin, and in which bidding zone?",
        "resolve": {"names": ["Dublin"], "level": "county"},
        "level": "county",
        "needs": "lake",
        "sql": "SELECT count(*) AS data_centres FROM app.data_centres "
        "WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-ruhr-people-protected",
        "q": "What is the population and the share under Natura 2000 of the Ruhr area I drew?",
        "view": {"drawn": {"kind": "polygon", "ring": RUHR[:-1], "name": "Ruhr"}},
        "resolve": {"from_view": "drawn"},
        "level": "polygon",
        "needs": "lake",
        "sql": "SELECT round(sum(km2_inside(geometry, '{area}')), 1) AS km2_protected "
        "FROM protected.natura2000 WHERE intersects_area(geometry, '{area}')",
    },
    {
        "id": "area-world-coal-by-country",
        "q": "Map the world's operating coal capacity by country.",
        "resolve": {"names": ["world"]},
        "level": "world",
        "needs": "lake",
        "sql": "SELECT a.iso3, round(sum(p.mw)) AS mw FROM app.world_plants p JOIN shapes.admin1 a "
        "ON ST_Contains(a.geometry, ST_Point(p.lon, p.lat)) WHERE p.type = 'coal' "
        "AND p.status = 'operating' GROUP BY a.iso3 ORDER BY mw DESC",
        "map": {"kind": "choropleth", "key": "iso3"},
    },
    {
        "id": "area-paris-vs-paris",
        "q": "Compare Paris, France with Paris, Texas: power plants inside each.",
        "resolve": {"names": ["Paris, France"]},
        "level": "locality",
        "needs": "lake",
        "sql": "SELECT count(*) AS plants FROM app.eu_plants WHERE in_area(lon, lat, '{area}')",
    },
    {
        "id": "area-amsterdam-buurt",
        "q": "What is the average electricity use per dwelling in Burgwallen-Oude Zijde, Amsterdam?",
        "resolve": {"names": ["Burgwallen-Oude Zijde"], "level": "nl_buurt"},
        "level": "nl_buurt",
        "needs": "lake",
        "sql": "SELECT electricity_kwh_per_dwelling FROM small_area_energy.nl_buurt "
        "WHERE code = (SELECT id FROM areas WHERE area_id = '{area}')",
    },
]


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    os.environ.setdefault("AGENT_MODEL", "fake")
    os.environ.setdefault("LAKE_DB", "")
    os.environ["RESULTS_DIR"] = str(tmp)
    os.environ["LOCAL_STORE_DIR"] = str(tmp / "store")
    from app.settings import Settings
    from tools.areas import resolve_area
    from tools.context import ToolContext
    from tools.sql import run_sql

    out = []
    for c in CASES:
        case = {"needs": "app", **c}
        if case["needs"] == "app":
            ctx = ToolContext(Settings())
            ctx.view = c.get("view")
            r = resolve_area(ctx, **c["resolve"])["data"]
            a = r.get("area")
            if not a or a["level"] != c["level"]:
                raise SystemExit(f"{c['id']}: area {a and a['level']} != {c['level']}: {r}")
            res = run_sql(ctx, c["sql"].replace("{area}", a["area_id"]))["data"]
            if "error" in res:
                raise SystemExit(f"{c['id']}: {res['error']}")
            rows = res["rows"][:3] if "map" not in c else []
            nums = [str(v) for row in rows for v in row if isinstance(v, int | float)]
            case["numbers"] = nums
            case["answer"] = (
                "; ".join(", ".join(str(v) for v in row) for row in res["rows"][:3])
                if "map" not in c
                else f"{res['row_count']} rows"
            )
            case["area_name"] = a["name"]
        out.append(case)
        print(case["id"], case.get("answer", "(lake)"))
    OUT.write_text(
        "# Generated by backend/scripts/build_area_evals.py; area questions of brief 27 (A7).\n"
        + yaml.safe_dump({"questions": out}, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} cases")


if __name__ == "__main__":
    main()
