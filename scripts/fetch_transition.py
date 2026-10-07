"""25 years of the world's electricity, per country, for the Transition tab.

Ember yearly electricity data (CC BY 4.0, EMBER_API_KEY), two bulk requests
(scripts/probe_ember_world.py):
  /electricity-generation/yearly  generation by source (TWh) and Ember's published
                                  shares of generation: renewables, wind and solar,
                                  coal (all entities, 2000 onwards)
  /carbon-intensity/yearly        published carbon intensity of generation (gCO2/kWh)
  /electricity-generation/monthly the same published shares per month, last 24 months
                                  (Ember covers fewer countries monthly)

Values are passthrough. "Net imports" is trade, not generation, and is left out of the
sources. Countries are keyed by ISO 3166-1 alpha-3 (Ember's entity code); aggregates
(World, EU, Europe, ...) by Ember's name.

Writes frontend/public/data/eu/transition.json:
  {"source", "fetched", "years": [...],
   "entities": {ISO3 | name: {"name", "aggregate", "series": {source: [TWh]},
                "renewables": [%], "wind_solar": [%], "coal": [%], "intensity": [g/kWh],
                "total_twh": [TWh]}}}
  (every list runs over "years"; null where Ember has no value)
and frontend/public/data/eu/monthly.json:
  {"source", "fetched", "months": [YYYY-MM], "entities": {ISO3 | name: {"renewables",
   "wind_solar", "coal": [% per month]}}}

    uv run python scripts/fetch_transition.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://api.ember-energy.org/v1"
SOURCES = [
    "Bioenergy",
    "Coal",
    "Gas",
    "Hydro",
    "Nuclear",
    "Other fossil",
    "Other renewables",
    "Solar",
    "Wind",
]
SHARES = {"Renewables": "renewables", "Wind and solar": "wind_solar", "Coal": "coal"}
TOTAL = "Total generation"  # published total (TWh), picks the largest power systems
AGGREGATES = {
    "World",
    "EU",
    "Europe",
    "Asia",
    "Africa",
    "North America",
    "Latin America and Caribbean",
    "Oceania",
}


def get(client: httpx.Client, path: str, key: str, start: str = "2000") -> list[dict]:
    for attempt in range(4):
        try:
            r = client.get(f"{URL}{path}", params={"start_date": start, "api_key": key})
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json().get("data", [])
    raise RuntimeError(f"Ember {path}: no answer")


def write_monthly(out: Path, rows: list[dict]) -> None:
    """Ember's published monthly shares of generation, per entity (passthrough)."""
    months = sorted({r["date"][:7] for r in rows})
    at = {m: i for i, m in enumerate(months)}
    entities: dict[str, dict] = {}
    for r in rows:
        if r["series"] not in SHARES or r.get("share_of_generation_pct") is None:
            continue
        if r["is_aggregate_entity"]:
            if r["entity"] not in AGGREGATES:
                continue
            k = r["entity"]
        else:
            k = r.get("entity_code") or ""
        if not k:
            continue
        e = entities.setdefault(k, {v: [None] * len(months) for v in SHARES.values()})
        e[SHARES[r["series"]]][at[r["date"][:7]]] = round(r["share_of_generation_pct"], 1)
    path = out / "monthly.json"
    path.write_text(
        json.dumps(
            {
                "source": "Ember monthly electricity data (CC BY 4.0), as published",
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "months": months,
                "entities": dict(sorted(entities.items())),
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(
        f"monthly.json: {len(entities)} entities, {months[0] if months else '-'}..{months[-1] if months else '-'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    key = os.environ["EMBER_API_KEY"]
    with httpx.Client(timeout=180, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        gen = get(client, "/electricity-generation/yearly", key)
        ci = get(client, "/carbon-intensity/yearly", key)
        now = datetime.now(UTC)
        since = f"{now.year - 2}-{now.month:02d}"
        monthly = get(client, "/electricity-generation/monthly", key, since)
    print(f"Ember rows: generation {len(gen):,}, carbon intensity {len(ci):,}")
    years = sorted({r["date"] for r in gen})
    at = {y: i for i, y in enumerate(years)}

    def ident(r: dict) -> str | None:
        if r["is_aggregate_entity"]:
            return r["entity"] if r["entity"] in AGGREGATES else None
        return r.get("entity_code")

    entities: dict[str, dict] = {}

    def entity(r: dict) -> dict | None:
        k = ident(r)
        if not k:
            return None
        if k not in entities:
            entities[k] = {
                "name": r["entity"],
                "aggregate": bool(r["is_aggregate_entity"]),
                "series": {},
                **{v: [None] * len(years) for v in [*SHARES.values(), "intensity", "total_twh"]},
            }
        return entities[k]

    for r in gen:
        e = entity(r)
        if e is None or r["date"] not in at:
            continue
        i = at[r["date"]]
        if r["series"] in SOURCES and r.get("generation_twh") is not None:
            e["series"].setdefault(r["series"], [None] * len(years))[i] = round(
                r["generation_twh"], 3
            )
        if r["series"] == TOTAL and r.get("generation_twh") is not None:
            e["total_twh"][i] = round(r["generation_twh"], 2)
        if r["series"] in SHARES and r.get("share_of_generation_pct") is not None:
            e[SHARES[r["series"]]][i] = round(r["share_of_generation_pct"], 1)
    for r in ci:
        e = entity(r)
        if (
            e is not None
            and r["date"] in at
            and r.get("emissions_intensity_gco2_per_kwh") is not None
        ):
            e["intensity"][at[r["date"]]] = round(r["emissions_intensity_gco2_per_kwh"], 1)

    out.mkdir(parents=True, exist_ok=True)
    write_monthly(out, monthly)
    payload = {
        "source": "Ember yearly electricity data (CC BY 4.0), as published",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "years": years,
        "entities": dict(sorted(entities.items())),
    }
    path = out / "transition.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    countries = sum(not e["aggregate"] for e in entities.values())
    print(
        f"transition.json: {path.stat().st_size / 1e6:.2f} MB, {countries} countries, "
        f"aggregates {sorted(k for k, e in entities.items() if e['aggregate'])}, years {years[0]}-{years[-1]}"
    )


if __name__ == "__main__":
    main()
