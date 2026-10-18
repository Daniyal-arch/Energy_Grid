"""Great Britain's carbon intensity now and the next 48 hours (NESO Carbon Intensity API).

api.carbonintensity.org.uk, no key, CC BY 4.0 (scripts/probe_gb_carbon.py). Half-hour periods.

  /intensity/{t}/pt24h   national intensity, the last 24 h: forecast and actual (gCO2/kWh)
  /intensity/{t}/fw48h   national forecast, the next 48 h
  /generation            the national generation mix of the current period (% per fuel)
  /regional              the forecast intensity of the 14 DNO regions (and England, Scotland,
                         Wales, GB) for the current period: the API publishes no regional actual

Values are passthrough. "Now" is the newest period with an actual value; when none is published
yet it is the current period's forecast, labelled so.

Writes frontend/public/data/eu/gb_carbon.json:
  {"source", "licence", "fetched",
   "now": {"from", "to", "gco2_kwh", "kind": "actual"|"forecast", "index"},
   "past": [[from, forecast, actual]], "ahead": [[from, forecast, index]],
   "mix": {"from", "to", "pct": {FUEL: %}},
   "regions": {"from", "to", "rows": [[id, name, dno, forecast, index]]}}

    uv run python scripts/fetch_gb_carbon.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
API = "https://api.carbonintensity.org.uk"
SOURCE = "NESO Carbon Intensity API (carbonintensity.org.uk)"
LICENCE = "CC BY 4.0"


def build(past: list[dict], ahead: list[dict], mix: dict, regional: dict) -> dict:
    """The file from the four answers (their `data` fields)."""
    actual = [p for p in past if p["intensity"].get("actual") is not None]
    if actual:
        p = actual[-1]
        now = {
            "from": p["from"],
            "to": p["to"],
            "gco2_kwh": p["intensity"]["actual"],
            "kind": "actual",
            "index": p["intensity"].get("index"),
        }
    else:
        p = (past or ahead)[-1 if past else 0]
        now = {
            "from": p["from"],
            "to": p["to"],
            "gco2_kwh": p["intensity"]["forecast"],
            "kind": "forecast",
            "index": p["intensity"].get("index"),
        }
    region = regional[0] if isinstance(regional, list) else regional
    return {
        "source": SOURCE,
        "licence": LICENCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "now": now,
        "past": [[p["from"], p["intensity"]["forecast"], p["intensity"]["actual"]] for p in past],
        "ahead": [
            [p["from"], p["intensity"]["forecast"], p["intensity"].get("index")] for p in ahead
        ],
        "mix": {
            "from": mix["from"],
            "to": mix["to"],
            "pct": {m["fuel"]: m["perc"] for m in mix["generationmix"]},
        },
        "regions": {
            "from": region["from"],
            "to": region["to"],
            "rows": [
                [
                    r["regionid"],
                    r["shortname"],
                    r.get("dnoregion"),
                    r["intensity"].get("forecast"),
                    r["intensity"].get("index"),
                ]
                for r in region["regions"]
            ],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
    with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as c:

        def get(path: str) -> dict | list:
            r = c.get(API + path)
            r.raise_for_status()
            return r.json()["data"]

        past = get(f"/intensity/{stamp}/pt24h")
        ahead = get(f"/intensity/{stamp}/fw48h")
        mix = get("/generation")
        regional = get("/regional")
    payload = build(past, ahead, mix, regional)  # type: ignore[arg-type]
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "gb_carbon.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    now = payload["now"]
    print(
        f"GB carbon intensity {now['gco2_kwh']} g/kWh ({now['kind']}, {now['from']}); "
        f"{len(payload['ahead'])} periods ahead, {len(payload['regions']['rows'])} regions"
    )


if __name__ == "__main__":
    main()
