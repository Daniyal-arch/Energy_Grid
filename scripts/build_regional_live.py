"""More regional and live grids (brief 21, group F).

    python scripts/build_regional_live.py fr|es|nz|za [--out DIR]

fr  RTE éCO2mix régional temps réel (ODRÉ `eco2mix-regional-tr`, Licence Ouverte / Etalab, no key):
    per region the newest 15-minute interval with consumption reported, consumption and generation
    by source (MW) and physical exchanges as published, and the last 24 hours of consumption;
    each region's NUTS-1 id (2024) for the agent -> DIR/fr_regions.json (refreshed with the snapshot).
es  Red Eléctrica REData (`generacion/estructura-generacion`, no key): generation by technology
    per autonomous community (geo_limit=ccaa), monthly, the last 13 months, MWh as published (days
    answer 500/502; one request every 2 s, Incapsula refuses faster) -> DIR/es_regions.json (daily).
nz  New Zealand: Transpower's live data page (`/em6/data/current_generation`, `/so/data/load_data_graph`;
    "HVDC data and Generation data sourced from em6"): generation and capacity by fuel (MW) and
    5-minute demand for NZ, North and South Island as published -> DIR/nz.json (snapshot).
za  South Africa: Eskom's data portal CSVs (hourly demand, station build-up by type) and the
    load-shedding status (loadshedding.eskom.co.za; the answer minus 1 is the stage, 0 = none)
    -> DIR/za.json (snapshot).
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import time
from collections import defaultdict
from pathlib import Path

import wave5_common as w

ODRE = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records"
FR_NUTS1 = {
    "11": "FR1",
    "24": "FRB",
    "27": "FRC",
    "28": "FRD",
    "32": "FRE",
    "44": "FRF",
    "52": "FRG",
    "53": "FRH",
    "75": "FRI",
    "76": "FRJ",
    "84": "FRK",
    "93": "FRL",
    "94": "FRM",
}
FR_FIELDS = [
    "consommation",
    "nucleaire",
    "eolien",
    "solaire",
    "hydraulique",
    "thermique",
    "bioenergies",
    "pompage",
    "stockage_batterie",
    "destockage_batterie",
    "ech_physiques",
]
REE = "https://apidatos.ree.es/es/datos/generacion/estructura-generacion"
ES_CCAA = {
    4: ("Andalucía", "ES61"), 5: ("Aragón", "ES24"), 6: ("Cantabria", "ES13"), 7: ("Castilla-La Mancha", "ES42"),
    8: ("Castilla y León", "ES41"), 9: ("Cataluña", "ES51"), 10: ("País Vasco", "ES21"), 11: ("Principado de Asturias", "ES12"),
    13: ("Comunidad de Madrid", "ES30"), 14: ("Comunidad Foral de Navarra", "ES22"), 15: ("Comunitat Valenciana", "ES52"),
    16: ("Extremadura", "ES43"), 17: ("Galicia", "ES11"), 20: ("La Rioja", "ES23"), 21: ("Región de Murcia", "ES62"),
    8742: ("Canarias", "ES70"), 8743: ("Illes Balears", "ES53"), 8744: ("Ceuta", "ES63"), 8745: ("Melilla", "ES64"),
}  # fmt: skip
TRANSPOWER = "https://www.transpower.co.nz"
ESKOM = "https://www.eskom.co.za/dataportal"
ESKOM_PAGES = {
    "demand": f"{ESKOM}/demand-side/system-hourly-actual-and-forecasted-demand/",
    "supply": f"{ESKOM}/supply-side/station-build-up-for-the-last-7-days/",
}
LOADSHEDDING = "https://loadshedding.eskom.co.za/LoadShedding/GetStatus"


# ---------------------------------------------------------------- France


def fr_newest(records: list[dict]) -> dict[str, dict]:
    """Per region the newest record with consumption, its values and the consumption series."""
    by: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("consommation") is not None:
            by[str(r["code_insee_region"])].append(r)
    out = {}
    for code, rows in by.items():
        rows.sort(key=lambda r: r["date_heure"])
        last = rows[-1]
        num = lambda v: (
            float(v)
            if isinstance(v, int | float)
            or (isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v))
            else None
        )  # noqa: E731
        out[code] = {
            "name": last["libelle_region"], "nuts1": FR_NUTS1.get(code), "ts": last["date_heure"],
            "mw": {k: num(last.get(k)) for k in FR_FIELDS},
            "consumption_24h": [[r["date_heure"], num(r["consommation"])] for r in rows[-96:]],
        }  # fmt: skip
    return out


def build_fr(out: Path) -> None:
    recs: list[dict] = []
    for offset in range(0, 9900, 100):
        d = w.get_json(f"{ODRE}?order_by=date_heure%20desc&limit=100&offset={offset}", timeout=60)
        rows = d.get("results", [])  # type: ignore[union-attr]
        recs += rows
        have = {str(r["code_insee_region"]) for r in recs if r.get("consommation") is not None}
        if len(recs) >= 13 * 96 + 13 * 8 and len(have) >= 12 or not rows:
            break
    regions = fr_newest(recs)
    print(
        f"  {len(recs)} records; {len(regions)} regions, newest {max(r['ts'] for r in regions.values())}",
        flush=True,
    )
    if len(regions) < 10:
        raise SystemExit(f"only {len(regions)} regions")
    w.write_json(
        out / "fr_regions.json",
        {
            "fetched": w.now(),
            "source": "RTE éCO2mix régional temps réel (ODRÉ, Licence Ouverte v2.0)",
            "regions": regions,
        },
    )


# ---------------------------------------------------------------- Spain


def es_series(answer: dict) -> dict[str, dict[str, float]]:
    """{technology: {YYYY-MM: MWh}} from one REData answer."""
    out: dict[str, dict[str, float]] = {}
    for inc in answer.get("included", []):
        a = inc.get("attributes", {})
        vals = {
            v["datetime"][:7]: round(v["value"], 3)
            for v in a.get("values", [])
            if v.get("value") is not None
        }
        if vals:
            out[a.get("title") or inc.get("type")] = vals
    return out


def build_es(out: Path) -> None:
    from datetime import UTC, datetime

    import httpx

    now = datetime.now(UTC)
    start = f"{now.year - 1}-{now.month:02d}-01T00:00"
    end = now.strftime("%Y-%m-%dT23:59")
    regions = {}
    errors = {}
    for geo, (name, nuts2) in ES_CCAA.items():
        params = {
            "start_date": start,
            "end_date": end,
            "time_trunc": "month",
            "geo_trunc": "electric_system",
            "geo_limit": "ccaa",
            "geo_ids": str(geo),
        }
        for attempt in range(1, 3):
            r = httpx.get(REE, params=params, headers=w.UA, timeout=60)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith(
                "application/json"
            ):
                regions[str(geo)] = {"name": name, "nuts2": nuts2, "mwh": es_series(r.json())}
                break
            errors[str(geo)] = f"HTTP {r.status_code}"
            time.sleep(5 * attempt)
        time.sleep(2)
    print(
        f"  {len(regions)} of {len(ES_CCAA)} regions; failed {errors if len(regions) < len(ES_CCAA) else {}}",
        flush=True,
    )
    if len(regions) < 10:
        raise SystemExit(f"REData: only {len(regions)} regions answered ({errors})")
    w.write_json(
        out / "es_regions.json",
        {
            "fetched": w.now(),
            "source": "Red Eléctrica, REData (generación, estructura por comunidad autónoma)",
            "unit": "MWh",
            "regions": regions,
        },
    )


# ---------------------------------------------------------------- New Zealand


def nz_load(points: list) -> list[list]:
    """Transpower's [{day, month (0-based), year, hour, minute}, MW] as [ISO local time, MW]."""
    out = []
    for t, mw in points:
        out.append(
            [
                f"{t['year']:04d}-{t['month'] + 1:02d}-{t['day']:02d}T{t['hour']:02d}:{t['minute']:02d}",
                mw,
            ]
        )
    return out


def build_nz(out: Path) -> None:
    gen = w.get_json(f"{TRANSPOWER}/em6/data/current_generation/0")
    load = w.get_json(f"{TRANSPOWER}/so/data/load_data_graph")
    nz = gen["data"]["New Zealand"]  # type: ignore[index]
    fuels = {k: v for k, v in nz.items() if isinstance(v, dict)}
    d = load.get("data", {})  # type: ignore[union-attr]
    payload = {
        "fetched": w.now(), "source": "Transpower (System Operator) live data, generation sourced from em6",
        "at": gen.get("date"), "timestamp": gen.get("timestamp"), "total_mw": nz.get("total"),  # type: ignore[union-attr]
        "fuels": {k: {"mw": v.get("generation"), "capacity_mw": v.get("capacity")} for k, v in fuels.items()},
        "load": {k: nz_load(d[k])[-288:] for k in ("nzPoints", "niPoints", "siPoints") if k in d},
    }  # fmt: skip
    print(f"  {payload['at']}: {payload['total_mw']} MW; fuels {list(fuels)}", flush=True)
    w.write_json(out / "nz.json", payload)


# ---------------------------------------------------------------- South Africa


def eskom_csv_link(html: str) -> str | None:
    hits = re.findall(r"""["'](https?://[^"']+\.csv)["']""", html)
    return hits[0] if hits else None


def parse_csv(text: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    return rows[0], rows[1:]


def build_za(out: Path) -> None:
    import httpx

    payload: dict = {
        "fetched": w.now(),
        "source": "Eskom data portal; load-shedding status (loadshedding.eskom.co.za)",
    }
    errors = []
    for key, page in ESKOM_PAGES.items():
        try:
            html = httpx.get(page, headers=w.UA, timeout=60, follow_redirects=True).text
            link = eskom_csv_link(html)
            if not link:
                errors.append(f"{key}: no CSV link on {page}")
                continue
            r = httpx.get(
                link, headers={**w.UA, "Referer": page}, timeout=60, follow_redirects=True
            )
            if r.status_code != 200 or r.text.lstrip().startswith("<"):
                errors.append(f"{key}: {link} HTTP {r.status_code}")
                continue
            head, rows = parse_csv(r.text)
            payload[key] = {"url": link, "columns": head, "rows": rows[-168:]}
            print(f"  {key}: {len(rows)} rows, columns {head[:12]}", flush=True)
        except httpx.HTTPError as e:
            errors.append(f"{key}: {type(e).__name__} {e}")
    try:
        st = httpx.get(LOADSHEDDING, headers=w.UA, timeout=30).text.strip()
        payload["loadshedding_stage"] = int(st) - 1 if re.fullmatch(r"-?\d+", st) else None
    except httpx.HTTPError as e:
        errors.append(f"load-shedding: {type(e).__name__} {e}")
    print(f"  stage {payload.get('loadshedding_stage')}; errors {errors}", flush=True)
    if "demand" not in payload and "supply" not in payload:
        raise SystemExit(f"Eskom data portal: {errors}")
    w.write_json(out / "za.json", payload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["fr", "es", "nz", "za"])
    ap.add_argument("--out", type=Path, default=w.EU)
    args = ap.parse_args()
    {"fr": build_fr, "es": build_es, "nz": build_nz, "za": build_za}[args.what](args.out)


if __name__ == "__main__":
    main()
