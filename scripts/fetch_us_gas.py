"""Gas on the US side (brief 22, family 10): storage, prices and pipelines, as Europe has them.

    python scripts/fetch_us_gas.py [prices|pipes|all] [--out DIR]

EIA API v2 (EIA_API_KEY, public domain):
  natural-gas/stor/wkly    weekly working gas in underground storage per region (Bcf), the
                           Lower 48 and EIA's five storage regions, last 5 years
  natural-gas/pri/fut      Henry Hub natural gas spot price, daily (USD/MMBtu), last 400 days
  natural-gas/pri/sum      citygate price per state, monthly (USD/Mcf), last 24 months: the price
                           distribution companies pay at the gate (EIA publishes no other regional
                           spot price as open data; hub prices other than Henry Hub are licensed)
Computed: the five-year range per week of the year (min and max of the five years before), as
EIA's own storage report shows it.
Pipelines: EIA's "Natural Gas Interstate and Intrastate Pipelines" (U.S. Energy Atlas, via the
federal ArcGIS org), lines generalised by ArcGIS to 0.01° (maxAllowableOffset) and rounded to
3 decimals so the file stays small; type, operator, status passed through.

Writes frontend/public/data/us/gas.json and us/gas_pipes.json.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "us"
API = "https://api.eia.gov/v2"
PIPES = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Natural_Gas_Interstate_and_Intrastate_Pipelines_1/FeatureServer/0"


def eia(
    route: str, key: str, frequency: str, facets: dict[str, list[str]], start: str
) -> list[dict]:
    """Every row of one EIA v2 data route since `start`, newest first."""
    rows: list[dict] = []
    offset = 0
    while True:
        params = [
            ("api_key", key), ("frequency", frequency), ("data[0]", "value"), ("start", start),
            *[(f"facets[{k}][]", v) for k, vs in facets.items() for v in vs],
            ("sort[0][column]", "period"), ("sort[0][direction]", "desc"),
            ("offset", str(offset)), ("length", "5000"),
        ]  # fmt: skip
        d = w7.get(f"{API}/{route}/data/", params=params).json()["response"]
        rows += d["data"]
        offset += len(d["data"])
        if not d["data"] or offset >= int(d["total"]):
            return rows


def series(rows: list[dict], key: str) -> dict[str, dict]:
    """{key value: {name, unit, points: [[period, value]] oldest first}}."""
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("value") in (None, ""):
            continue
        s = out.setdefault(
            r[key],
            {
                "name": r.get("series-description") or r.get("area-name"),
                "unit": r.get("units"),
                "points": [],
            },
        )
        s["points"].append([r["period"], float(r["value"])])
    for s in out.values():
        s["points"].sort()
    return out


def five_year_range(points: list[list]) -> dict[str, list]:
    """Per point of the newest year: [min, max] of the same week in the five years before (computed)."""
    by_week: dict[tuple[int, int], float] = {}
    for p, v in points:
        y, wk, _ = date.fromisoformat(p).isocalendar()
        by_week[(y, wk)] = v
    newest = max(y for y, _ in by_week)
    out = {}
    for p, _ in points:
        y, wk, _ = date.fromisoformat(p).isocalendar()
        if y != newest:
            continue
        past = [by_week[(y - k, wk)] for k in range(1, 6) if (y - k, wk) in by_week]
        if len(past) == 5:
            out[p] = [min(past), max(past)]
    return out


def prices(out: Path) -> None:
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "EIA_API_KEY not set (register at https://www.eia.gov/opendata/register.php)"
        )
    today = datetime.now(UTC).date()
    storage = series(eia("natural-gas/stor/wkly", key, "weekly", {}, str(today.year - 6)), "series")
    for s in storage.values():
        s["range_5y"] = five_year_range(s["points"])
    hh = series(eia("natural-gas/pri/fut", key, "daily", {"series": ["RNGWHHD"]}, (today - timedelta(days=400)).isoformat()), "series")  # fmt: skip
    gate = series(eia("natural-gas/pri/sum", key, "monthly", {"process": ["PG1"]}, (today - timedelta(days=760)).strftime("%Y-%m")), "duoarea")  # fmt: skip
    data = {
        "source": "EIA API v2: weekly natural gas storage report, Henry Hub spot price, citygate price per state",
        "licence": "public domain (EIA)",
        "fetched": w.now(),
        "storage": storage,
        "henry_hub": hh.get("RNGWHHD"),
        "citygate": gate,
        "range_note": "five-year range: min and max of the same ISO week in the five years before (computed)",
    }
    w.write_json(out / "gas.json", data)
    print(
        f"storage {len(storage)} series, Henry Hub {len((hh.get('RNGWHHD') or {}).get('points', []))} days, citygate {len(gate)} areas",
        flush=True,
    )


def pipes(out: Path) -> None:
    rows = w7.arcgis(PIPES, page=2000, extra={"maxAllowableOffset": 0.01})
    lines = [
        [r["_paths"], r.get("TYPEPIPE"), r.get("Operator"), r.get("Status")]
        for r in rows
        if r.get("_paths")
    ]
    data = {
        "source": "EIA, Natural Gas Interstate and Intrastate Pipelines (U.S. Energy Atlas)",
        "licence": "public domain (EIA)",
        "url": PIPES,  # no fetch time: the file changes only when EIA's lines do
        "note": "lines generalised to 0.01° by ArcGIS and rounded to 3 decimals",
        "columns": ["paths", "type", "operator", "status"],
        "lines": lines,
    }
    w.write_json(out / "gas_pipes.json", data)
    print(f"pipelines: {len(lines)} lines", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", nargs="?", default="all", choices=["prices", "pipes", "all"])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if args.part in ("pipes", "all"):
        pipes(args.out)
    if args.part in ("prices", "all"):
        prices(args.out)


if __name__ == "__main__":
    main()
