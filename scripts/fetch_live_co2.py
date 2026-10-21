"""Live mix and CO₂ per kWh from the operators' own feeds (brief 22, family 3), where they add
what ENTSO-E does not: CO₂ per kWh as the operator publishes it, at its own time step.

    python scripts/fetch_live_co2.py fr|es|ie|eu|us|all [--out DIR]    (eu = fr es ie)

fr  RTE éCO2mix national, real time (ODRÉ `eco2mix-national-tr`, Licence Ouverte): every 15 min,
    the mix in MW and `taux_co2` (g CO₂ per kWh, RTE's estimate) as published; the last 48 h.
es  REE REData (`generacion/no-renovables-detalle-emisiones-CO2`, no key): the daily emission
    factor of the national system (t CO₂-eq per MWh, shown as g per kWh = × 1000) and the
    emissions per technology, the last 30 days.
ie  EirGrid Smart Grid Dashboard (`/api/chart/`, the request its own chart makes): CO₂ intensity
    (g per kWh) every 15 min for Ireland (ROI) and the island (ALL), yesterday and today.
us  EIA-930 Hourly Electric Grid Monitor files (one xlsx per region, ~38 MB each, ~0.5 GB for
    the 13 regions and the Lower 48; weekly in Actions): EIA's hourly "CO2 Emissions Intensity
    for Generated Electricity" and "... for Consumed Electricity" (lb per kWh, EIA's estimate from
    its fuel emission factors; × 453.592 = g per kWh), the last 14 days.

Writes <out>/live_co2.json (fr, es, ie) and <out>/../us/co2.json (us). Nothing is computed from
emission factors: every intensity is the operator's or EIA's own figure.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
LB_TO_G = 453.592  # g per kWh in one lb per kWh

ODRE = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"
FR_MIX = [
    "nucleaire",
    "hydraulique",
    "eolien",
    "solaire",
    "gaz",
    "charbon",
    "fioul",
    "bioenergies",
    "pompage",
]
REE = "https://apidatos.ree.es/es/datos/generacion/no-renovables-detalle-emisiones-CO2"
EIRGRID = "https://www.smartgriddashboard.com/api/chart/"
EIA_REGIONS = [
    "US48",
    "CAL",
    "CAR",
    "CENT",
    "FLA",
    "MIDA",
    "MIDW",
    "NE",
    "NW",
    "NY",
    "SE",
    "SW",
    "TEN",
    "TEX",
]
EIA_FILE = "https://www.eia.gov/electricity/gridmonitor/knownissues/xls/Region_{r}.xlsx"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------- France


def fr_series(records: list[dict]) -> list[list]:
    """[time, g CO₂/kWh, {fuel: MW}] per 15 min, oldest first, rows with a CO₂ figure only."""
    out = []
    for r in records:
        if r.get("taux_co2") is None:
            continue
        mix = {k: r[k] for k in FR_MIX if isinstance(r.get(k), int | float)}
        out.append([r.get("date_heure"), r["taux_co2"], mix])
    return sorted(out, key=lambda x: x[0] or "")


def fetch_fr() -> dict:
    recs = w7.get(
        ODRE, params={"order_by": "date_heure desc", "limit": 100, "where": "taux_co2 is not null"}
    ).json()["results"]
    more = w7.get(
        ODRE,
        params={
            "order_by": "date_heure desc",
            "limit": 100,
            "offset": 100,
            "where": "taux_co2 is not null",
        },
    ).json()["results"]
    series = fr_series(recs + more)
    if not series:
        raise SystemExit("éCO2mix: no CO₂ rows")
    return {"source": "RTE éCO2mix national real time (ODRÉ eco2mix-national-tr)", "licence": "Licence Ouverte v2.0", "step_min": 15,
            "unit": "g CO₂ per kWh (RTE's estimate of the French generation's emissions)", "series": series}  # fmt: skip


# ---------------------------------------------------------------- Spain


def es_parts(d: dict) -> tuple[list[list], dict[str, list[list]]]:
    """The daily factor ([day, t/MWh]) and emissions per technology ({tech: [[day, t], ...]})."""
    factor: list[list] = []
    tech: dict[str, list[list]] = {}
    for inc in d.get("included", []):
        vals = [[v["datetime"][:10], v["value"]] for v in inc["attributes"].get("values", [])]
        if inc.get("type", "").startswith("tCO2 eq./MWh"):
            factor = vals
        elif not inc.get("type", "").startswith("Total"):
            tech[inc["type"]] = vals
    return factor, tech


def fetch_es() -> dict:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=30)
    params = {
        "start_date": f"{start}T00:00",
        "end_date": f"{end}T23:59",
        "time_trunc": "day",
        "geo_trunc": "electric_system",
        "geo_limit": "nacional",
        "geo_ids": "8741",
    }
    factor, tech = es_parts(w7.get(REE, params=params).json())
    if not factor:
        raise SystemExit("REE: no emission factor")
    return {"source": "Red Eléctrica (REE) REData, emissions and emission factor of the national system", "licence": "REE terms (reuse with attribution)", "step_min": 1440,
            "unit": "t CO₂-eq per MWh as published (× 1000 = g per kWh)", "factor": factor, "by_technology_t": tech}  # fmt: skip


# ---------------------------------------------------------------- Ireland


def fetch_ie() -> dict:
    """Today and yesterday (Irish dates), as the dashboard's own chart requests them."""
    today = datetime.now(UTC).date()
    out = {}
    for region in ("ROI", "ALL"):
        rows = []
        for day in (today - timedelta(days=1), today):
            params = {
                "region": region,
                "chartType": "co2",
                "dateRange": "day",
                "dateFrom": day.isoformat(),
                "dateTo": day.isoformat(),
                "areas": "co2intensity",
            }
            rows += [
                r
                for r in w7.get(EIRGRID, params=params).json().get("Rows", [])
                if r.get("FieldName") == "CO2_INTENSITY"
            ]
        out[region] = [[r["EffectiveTime"], r["Value"]] for r in rows if r.get("Value") is not None]
    if not any(out.values()):
        raise SystemExit("EirGrid: no CO₂ rows")
    return {"source": "EirGrid Smart Grid Dashboard, CO₂ intensity", "licence": "EirGrid terms (reuse with attribution)", "step_min": 15,
            "unit": "g CO₂ per kWh as published", "regions": {"ROI": "Ireland", "ALL": "the island of Ireland"}, "series": out}  # fmt: skip


# ---------------------------------------------------------------- United States


def eia_rows(path: Path, days: int = 14) -> list[list]:
    """[UTC hour, intensity generated, intensity consumed] in lb/kWh as published, the last `days`."""
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["Published Hourly Data"]
    it = ws.iter_rows(values_only=True)
    head = list(next(it))
    t = head.index("UTC time")
    gen = head.index("CO2 Emissions Intensity for Generated Electricity")
    con = head.index("CO2 Emissions Intensity for Consumed Electricity")
    rows = [
        [r[t], r[gen], r[con]]
        for r in it
        if r[t] is not None and (r[gen] is not None or r[con] is not None)
    ]
    if not rows:
        return []
    cut = rows[-1][0] - timedelta(days=days)
    return [[r[0].isoformat(timespec="minutes"), r[1], r[2]] for r in rows if r[0] > cut]


def fetch_us() -> dict:
    w7.TMP.mkdir(parents=True, exist_ok=True)
    regions = {}
    for r in EIA_REGIONS:
        path = w7.TMP / f"eia_{r}.xlsx"
        path.write_bytes(w7.get(EIA_FILE.format(r=r), timeout=600).content)
        print(f"  {r}: {path.stat().st_size / 1e6:.0f} MB", flush=True)
        regions[r] = eia_rows(path)
        path.unlink()
    return {"fetched": now(), "source": "EIA-930 Hourly Electric Grid Monitor, CO₂ emissions intensity (EIA's estimate)", "licence": "public domain",
            "unit": "lb CO₂ per kWh as published (× 453.592 = g per kWh)", "lb_to_g_kwh": LB_TO_G, "regions": regions}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["fr", "es", "ie", "eu", "us", "all"])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    todo = {"all": ["fr", "es", "ie", "us"], "eu": ["fr", "es", "ie"]}.get(args.what, [args.what])
    path = args.out / "live_co2.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    failed = []
    for what in todo:
        try:
            if what == "us":
                us = fetch_us()
                p = args.out.parent / "us" / "co2.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(us, separators=(",", ":"), default=str), encoding="utf-8")
                print(f"-> {p}", flush=True)
                continue
            part = {
                "fetch": {"fr": fetch_fr, "es": fetch_es, "ie": fetch_ie}[what](),
                "fetched": now(),
            }
            data[what] = {**part["fetch"], "fetched": part["fetched"]}
            print(f"  {what}: ok", flush=True)
        except (SystemExit, Exception) as e:  # one feed down must not stop the others
            print(f"  {what} failed: {type(e).__name__} {str(e)[:300]}", flush=True)
            failed.append(what)
    # only when a Europe feed was asked and answered: `us` alone must leave live_co2.json as it is
    # (us-queues.yml commits only the US files; a rewritten live_co2.json stopped its pull --rebase)
    if any(k in data and k not in failed for k in todo if k != "us"):
        data["fetched"] = now()
        args.out.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
        )
        print(f"-> {path}", flush=True)
    if failed:
        raise SystemExit(f"failed: {' '.join(failed)}")


if __name__ == "__main__":
    main()
