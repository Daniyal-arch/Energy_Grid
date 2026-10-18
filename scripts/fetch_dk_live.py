"""Denmark every 5 minutes (Energinet, Energi Data Service; no key, CC BY 4.0).

scripts/probe_dk_live.py found the datasets (2026-10-18):

  CO2Emis                        CO2 per kWh consumed, DK1 and DK2, every 5 min (g/kWh;
                                 Energinet's initial values, from upscaled real-time measurements)
  ElectricityProdex5MinRealtime  production and exchange per area, every 5 min (MW): plants
                                 >= 100 MW, plants < 100 MW, offshore wind, onshore wind, solar,
                                 exchange per neighbour

Values as published; the API returns them as 32-bit floats (87.129997), kept to 2 decimals.
Nothing is computed. "Now" per area is the newest 5 minutes with a production record.

Writes frontend/public/data/eu/dk_live.json:
  {"source", "licence", "fetched",
   "co2": {"start", "step_s": 300, "DK1": [g/kWh | null], "DK2": [...]},   (the last 24 h)
   "production": {"DK1": {"at", "mw": {COLUMN: MW}}, "DK2": {...}}}

    uv run python scripts/fetch_dk_live.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
API = "https://api.energidataservice.dk/dataset"
SOURCE = "Energinet, Energi Data Service (CO2Emis, ElectricityProdex5MinRealtime)"
LICENCE = "CC BY 4.0"
AREAS = ("DK1", "DK2")
STEP = 300
PRODUCTION = [
    "ProductionGe100MW",
    "ProductionLt100MW",
    "OffshoreWindPower",
    "OnshoreWindPower",
    "SolarPower",
    "ExchangeGermany",
    "ExchangeNetherlands",
    "ExchangeGreatBritain",
    "ExchangeNorway",
    "ExchangeSweden",
    "ExchangeGreatBelt",
    "BornholmSE4",
]


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _v(x: float | None) -> float | None:
    return None if x is None else round(float(x), 2)


def build(co2: list[dict], prod: list[dict], end: datetime) -> dict:
    """The file from the two datasets' records (any order); the CO2 series on a 5-min grid
    of the 24 h before `end` (floored to 5 min)."""
    end = end.replace(second=0, microsecond=0) - timedelta(minutes=end.minute % 5)
    start = end - timedelta(days=1)
    n = int((end - start).total_seconds()) // STEP
    series: dict[str, list[float | None]] = {a: [None] * n for a in AREAS}
    for r in co2:
        a = r.get("PriceArea")
        if a not in series:
            continue
        k = int((_t(r["Minutes5UTC"]) - start).total_seconds()) // STEP
        if 0 <= k < n:
            series[a][k] = _v(r.get("CO2Emission"))
    production: dict[str, dict] = {}
    for r in sorted(prod, key=lambda r: r["Minutes5UTC"], reverse=True):
        a = r.get("PriceArea")
        if a in AREAS and a not in production:
            production[a] = {
                "at": _t(r["Minutes5UTC"]).isoformat(),
                "mw": {c: _v(r.get(c)) for c in PRODUCTION},
            }
    return {
        "source": SOURCE,
        "licence": LICENCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "co2": {"start": start.isoformat(), "step_s": STEP, **series},
        "production": production,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    with httpx.Client(timeout=60) as c:

        def records(name: str, start: str) -> list[dict]:
            r = c.get(f"{API}/{name}", params={"start": start, "limit": "0"})
            r.raise_for_status()
            return r.json()["records"]

        co2 = records("CO2Emis", "now-P1D")
        prod = records("ElectricityProdex5MinRealtime", "now-PT1H")
    payload = build(co2, prod, datetime.now(UTC) + timedelta(minutes=5))
    if not payload["production"] and not any(payload["co2"][a] for a in AREAS):
        raise SystemExit("Energi Data Service answered no records")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "dk_live.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    newest = {
        a: next((v for v in reversed(payload["co2"][a]) if v is not None), None) for a in AREAS
    }
    print(
        f"Denmark CO2 now {newest} g/kWh; production at {[p['at'] for p in payload['production'].values()]}"
    )


if __name__ == "__main__":
    main()
