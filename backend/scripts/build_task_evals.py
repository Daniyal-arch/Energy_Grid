"""Build agent/evals/tasks.yaml: the customer-task questions of brief 28 (part C), one per task
skill that runs on the app's tables in CI with the scripted fake model, plus questions over the
wave-9 lake tables whose answers come from the built tables.

    uv run python scripts/build_task_evals.py [--lake DIR]

`needs: app` cases resolve their area and run their SQL here (the app's map files, including the
wave-9 map files as app.w9_<id>), like scripts/build_area_evals.py. `needs: lake` cases read the
wave-9 tables of a local lake folder (`--lake`, written by `scripts/wave9.py build --lake DIR`);
without it their expected numbers stay as last written. Each case names the skill it exercises.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "agent" / "evals" / "tasks.yaml"


def app(
    id_: str, skill: str, q: str, resolve: dict[str, Any], level: str, sql: str
) -> dict[str, Any]:
    return {
        "needs": "app",
        "id": id_,
        "skill": skill,
        "q": q,
        "resolve": resolve,
        "level": level,
        "sql": sql,
    }


def lake(id_: str, skill: str, q: str, sql: str) -> dict[str, Any]:
    return {
        "needs": "lake",
        "id": id_,
        "skill": skill,
        "q": q,
        "resolve": {"names": ["Europe"]},
        "level": "group",
        "sql": sql,
    }


CASES: list[dict[str, Any]] = [
    app(
        "task-dc-frankfurt",
        "datacentre-siting",
        "Data-centre siting: how many substations lie within 30 km of Frankfurt?",
        {"names": ["Frankfurt am Main"], "radius_km": 30},
        "circle",
        "SELECT count(*) AS substations FROM app.eu_substations WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-battery-leeds",
        "battery-siting",
        "Battery siting: how many substations lie within 20 km of Leeds?",
        {"names": ["Leeds"], "radius_km": 20},
        "circle",
        "SELECT count(*) AS substations FROM app.eu_substations WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-solar-seville",
        "solar-wind-siting",
        "Solar and wind siting: which plants of 20 MW and more lie within 50 km of Sevilla, by fuel?",
        {"names": ["Sevilla"], "radius_km": 50},
        "circle",
        "SELECT fuel, count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants WHERE in_area(lon, lat, '{area}') GROUP BY fuel ORDER BY mw DESC",
    ),
    app(
        "task-offshore-aberdeen",
        "offshore-wind",
        "Offshore wind: how many offshore installations lie within 200 km of Aberdeen?",
        {"names": ["Aberdeen"], "radius_km": 200},
        "circle",
        "SELECT count(*) AS installations FROM app.w9_eu_emodnet_platforms WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-risk-milan",
        "physical-risk",
        "Physical risk: how much generating capacity of 20 MW and more lies within 40 km of Milan?",
        {"names": ["Milan"], "radius_km": 40},
        "circle",
        "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-grid-lyon",
        "grid-planning",
        "Grid planning: how many substations lie within 50 km of Lyon?",
        {"names": ["Lyon"], "radius_km": 50},
        "circle",
        "SELECT count(*) AS substations FROM app.eu_substations WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-revenues-germany",
        "revenues",
        "Revenues: how many negative-price hours did Germany's bidding zone have?",
        {"names": ["Germany"]},
        "country",
        "SELECT zone, negative_hours FROM app.eu_prices WHERE country = 'DE' ORDER BY negative_hours DESC",
    ),
    app(
        "task-industry-chicago",
        "industrial-decarbonisation",
        "Industrial decarbonisation: how many landfill gas energy projects lie within 100 km of Chicago?",
        {"names": ["Chicago"], "radius_km": 100},
        "circle",
        "SELECT count(*) AS projects FROM app.w9_us_epa_lmop WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-heat-amsterdam",
        "heat-networks",
        "Heat networks: how many data centres lie within 20 km of Amsterdam?",
        {"names": ["Amsterdam"], "radius_km": 20},
        "circle",
        "SELECT count(*) AS data_centres FROM app.data_centres WHERE in_area(lon, lat, '{area}')",
    ),
    app(
        "task-ev-munich",
        "ev-electrification",
        "Electrification: how much solar capacity of 20 MW and more lies within 60 km of Munich?",
        {"names": ["Munich"], "radius_km": 60},
        "circle",
        "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants WHERE fuel = 'solar' AND in_area(lon, lat, '{area}')",
    ),
    app(
        "task-money-katowice",
        "public-money",
        "Public money and transition: how much coal capacity of 20 MW and more lies within 100 km of Katowice?",
        {"names": ["Katowice"], "radius_km": 100},
        "circle",
        "SELECT count(*) AS plants, round(sum(mw)) AS mw FROM app.eu_plants WHERE fuel IN ('coal', 'lignite') AND in_area(lon, lat, '{area}')",
    ),
    lake(
        "task-rail-electrified-de",
        "grid-planning",
        "How many km of electrified railway line does Germany have, newest year?",
        "SELECT time_period, obs_value FROM wave9.eu_rail_electrified WHERE geo = 'DE' AND unit = 'KM' ORDER BY time_period DESC LIMIT 1",
    ),
    lake(
        "task-nuclear-fr",
        "industrial-decarbonisation",
        "How many nuclear power plants does EMODnet list in France?",
        "SELECT count(*) FROM wave9.eu_emodnet_nuclear WHERE country ILIKE 'France%'",
    ),
    lake(
        "task-ports-count",
        "offshore-wind",
        "How many ports does EMODnet Human Activities list?",
        "SELECT count(*) FROM wave9.eu_emodnet_ports",
    ),
    lake(
        "task-platforms-count",
        "offshore-wind",
        "How many offshore installations does EMODnet list?",
        "SELECT count(*) FROM wave9.eu_emodnet_platforms",
    ),
    lake(
        "task-ocean-energy",
        "offshore-wind",
        "How many wave and tidal energy projects does EMODnet list?",
        "SELECT count(*) FROM wave9.eu_emodnet_ocean_energy",
    ),
    lake(
        "task-wind-farms-emodnet",
        "offshore-wind",
        "How many offshore wind farm outlines does EMODnet hold?",
        "SELECT count(*) FROM wave9.eu_emodnet_wind_farms",
    ),
    lake(
        "task-boem-leases",
        "offshore-wind",
        "How many offshore wind lease outlines does BOEM publish?",
        "SELECT count(*) FROM wave9.us_boem_wind_leases",
    ),
    lake(
        "task-ethanol",
        "industrial-decarbonisation",
        "How many ethanol plants does EIA list in the US?",
        "SELECT count(*) FROM wave9.us_eia_ethanol",
    ),
    lake(
        "task-biodiesel",
        "industrial-decarbonisation",
        "How many biodiesel plants does EIA list in the US?",
        "SELECT count(*) FROM wave9.us_eia_biodiesel",
    ),
    lake(
        "task-lmop",
        "industrial-decarbonisation",
        "How many landfill gas energy projects does EPA LMOP list?",
        "SELECT count(*) FROM wave9.us_epa_lmop",
    ),
    lake(
        "task-refineries-tx",
        "industrial-decarbonisation",
        "How many petroleum refineries does EIA list in Texas?",
        "SELECT count(*) FROM wave9.us_eia_refineries WHERE state = 'Texas'",
    ),
    lake(
        "task-lng",
        "industrial-decarbonisation",
        "How many LNG import and export terminals does EIA list?",
        "SELECT count(*) FROM wave9.us_eia_lng",
    ),
    lake(
        "task-gas-storage",
        "physical-risk",
        "How many underground gas storage fields does EIA list?",
        "SELECT count(*) FROM wave9.us_eia_gas_storage",
    ),
    lake(
        "task-water-use-tx",
        "datacentre-siting",
        "How many counties does the USGS 2015 water-use table cover in Texas?",
        "SELECT count(*) FROM wave9.us_usgs_water_use WHERE state = 'TX'",
    ),
    lake(
        "task-tnuos-rows",
        "revenues",
        "How many TNUoS tariff rows does NESO publish in its newest tariff file?",
        "SELECT count(*) FROM wave9.gb_neso_tnuos",
    ),
    lake(
        "task-dc-ireland",
        "datacentre-siting",
        "How many quarters of data-centre electricity does CSO publish for Ireland?",
        "SELECT count(DISTINCT tlist_q1) FROM wave9.ie_cso_datacentres",
    ),
    lake(
        "task-npg-headroom",
        "battery-siting",
        "How many substations does the Northern Powergrid heat map list?",
        "SELECT count(*) FROM wave9.gb_npg_heatmap_substations",
    ),
    lake(
        "task-heat-pumps-rows",
        "heat-networks",
        "How many countries report heat pump characteristics to Eurostat?",
        "SELECT count(DISTINCT geo) FROM wave9.eu_heat_pumps",
    ),
    lake(
        "task-degree-days-regions",
        "heat-networks",
        "For how many NUTS 3 regions does Eurostat publish degree days?",
        "SELECT count(DISTINCT geo) FROM wave9.eu_degree_days WHERE length(geo) = 5",
    ),
    lake(
        "task-ev-nuts2",
        "ev-electrification",
        "For how many regions does Eurostat publish vehicle stocks by fuel?",
        "SELECT count(DISTINCT geo) FROM wave9.eu_ev_stock_nuts2",
    ),
    lake(
        "task-broadband-regions",
        "datacentre-siting",
        "For how many regions does Eurostat publish household broadband access?",
        "SELECT count(DISTINCT geo) FROM wave9.eu_broadband_nuts2",
    ),
    lake(
        "task-income-regions",
        "public-money",
        "For how many regions does Eurostat publish household income?",
        "SELECT count(DISTINCT geo) FROM wave9.eu_household_income",
    ),
    # wave 10 (brief 29): country, world and GB district series
    lake(
        "w10-gross-inland-de",
        "energy-statistics",
        "What was Germany's gross inland energy consumption in the newest year (Eurostat simplified balance, ktoe)?",
        "SELECT time_period, obs_value FROM wave10.eu_nrg_bal_s WHERE nrg_bal = 'GIC' AND siec = 'TOTAL' AND unit = 'KTOE' AND geo = 'DE' ORDER BY time_period DESC LIMIT 1",
    ),
    lake(
        "w10-access-lowest",
        "energy-statistics",
        "Which country had the lowest access to electricity in 2024 according to the World Bank?",
        "SELECT country, value FROM wave10.wb_eg_elc_accs_zs WHERE NOT aggregate AND year = 2024 ORDER BY value LIMIT 1",
    ),
    lake(
        "w10-gb-ren-capacity-cornwall",
        "energy-statistics",
        "How much renewable electricity capacity was installed in Cornwall at the end of 2025?",
        "SELECT total FROM wave10.gb_desnz_ren_capacity_la WHERE local_authority_code_note_1 = 'E06000052' AND sheet = 'LA - Capacity, 2025'",
    ),
    lake(
        "w10-gb-elec-household-westminster",
        "energy-statistics",
        "What was the mean domestic electricity consumption per household in Westminster in 2024?",
        "SELECT mean_domestic_consumption_kwh_per_household FROM wave10.gb_desnz_elec_la WHERE code = 'E09000033' AND sheet = '2024'",
    ),
    lake(
        "w10-gb-ghg-per-capita-leeds",
        "emissions",
        "What were Leeds' territorial greenhouse gas emissions per person in 2023?",
        "SELECT per_capita_emissions_t_co2e FROM wave10.gb_desnz_ghg_la WHERE local_authority_code = 'E08000035' AND calendar_year = '2023'",
    ),
    lake(
        "w10-gb-chargers-edinburgh",
        "ev-electrification",
        "How many public EV charging devices did the City of Edinburgh have in October 2025?",
        "SELECT oct_25 FROM wave10.gb_dft_evcd_devices WHERE local_authority_region_code = 'S12000036'",
    ),
    lake(
        "w10-gb-mains-gas-hartlepool",
        "heat-networks",
        "What share of households in Hartlepool heat with mains gas only (Census 2021)?",
        "SELECT obs_value FROM wave10.gb_census_heating WHERE geography_code = 'E06000001' AND c2021_heating_13_name = 'Mains gas only' AND measures_name = 'Percent'",
    ),
    lake(
        "w10-gb-gas-meter-manchester",
        "energy-statistics",
        "What was the mean domestic gas consumption per meter in Manchester in 2024?",
        "SELECT mean_consumption_kwh_per_meter_domestic FROM wave10.gb_desnz_gas_la WHERE code = 'E08000003' AND sheet = '2024'",
    ),
]


def run_app(c: dict[str, Any]) -> None:
    from app.settings import Settings
    from tools.areas import resolve_area
    from tools.context import ToolContext
    from tools.sql import run_sql

    ctx = ToolContext(Settings())
    r = resolve_area(ctx, **c["resolve"])["data"]
    a = r.get("area")
    if not a or a["level"] != c["level"]:
        raise SystemExit(f"{c['id']}: area {a and a['level']} != {c['level']}: {r}")
    res = run_sql(ctx, c["sql"].replace("{area}", a["area_id"]))["data"]
    if "error" in res:
        raise SystemExit(f"{c['id']}: {res['error']}")
    rows = res["rows"][:3]
    c["numbers"] = [str(v) for row in rows for v in row if isinstance(v, int | float)]
    c["answer"] = "; ".join(", ".join(str(v) for v in row) for row in rows)
    c["area_name"] = a["name"]


def run_lake(c: dict[str, Any], root: Path) -> None:
    import duckdb

    con = duckdb.connect()
    sql = re.sub(
        r"(wave\d+)\.([a-z0-9_]+)",
        lambda m: (
            f"read_parquet('{root}/{m.group(1)}/{m.group(2)}/**/*.parquet', union_by_name = true)"
        ),
        c["sql"],
    )
    rows = con.execute(sql).fetchall()[:3]

    def num(v: object) -> bool:  # numbers, also those a workbook table keeps as text
        try:
            return not isinstance(v, bool) and v is not None and float(str(v)) == float(str(v))
        except ValueError:
            return False

    c["numbers"] = [str(v) for row in rows for v in row if num(v)]
    c["answer"] = "; ".join(", ".join(str(v) for v in row) for row in rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    os.environ.setdefault("AGENT_MODEL", "fake")
    os.environ.setdefault("LAKE_DB", "")
    os.environ["RESULTS_DIR"] = str(tmp)
    os.environ["LOCAL_STORE_DIR"] = str(tmp / "store")
    old = {}
    if OUT.exists():
        old = {c["id"]: c for c in yaml.safe_load(OUT.read_text(encoding="utf-8"))["questions"]}
    out = []
    for c in CASES:
        c = dict(c)
        if c["needs"] == "app":
            run_app(c)
        elif args.lake:
            try:
                run_lake(c, args.lake)
            except Exception as e:  # noqa: BLE001 - a table not built locally keeps its old answer
                print(f"  {c['id']}: {type(e).__name__}: {str(e)[:120]}")
                c.update(
                    {k: v for k, v in old.get(c["id"], {}).items() if k in ("numbers", "answer")}
                )
        else:
            c.update({k: v for k, v in old.get(c["id"], {}).items() if k in ("numbers", "answer")})
        out.append(c)
        print(c["id"], c.get("answer", "(lake)"))
    OUT.write_text(
        "# Generated by backend/scripts/build_task_evals.py; customer-task questions of brief 28 (C).\n"
        + yaml.safe_dump({"questions": out}, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} cases")


if __name__ == "__main__":
    main()
