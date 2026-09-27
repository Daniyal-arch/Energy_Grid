"""Live power-system fallback data for the frontend.

The normal path reads cached rows from Supabase. During local development the DB
can be offline, so these helpers fetch public Energy-Charts data directly and
return the same response shape as /grid/latest and /grid/exchange.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.energy-charts.info"

FUEL_MAP = {
    "Fossil brown coal / lignite": "lignite",
    "Fossil hard coal": "hard_coal",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil oil": "oil",
    "Nuclear": "nuclear",
    "Biomass": "biomass",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Solar": "solar",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Geothermal": "geothermal",
    "Waste": "waste",
    "Others": "other",
}

EMISSION_FACTORS = {
    "lignite": 1150.0,
    "hard_coal": 900.0,
    "gas": 410.0,
    "oil": 700.0,
    "nuclear": 12.0,
    "biomass": 230.0,
    "solar": 41.0,
    "wind": 11.0,
    "hydro": 24.0,
    "geothermal": 38.0,
    "waste": 700.0,
    "other": 700.0,
}

RENEWABLE_FUELS = {"solar", "wind", "hydro", "biomass", "geothermal"}
CARBON_FREE_FUELS = RENEWABLE_FUELS | {"nuclear"}


def _get_json(path: str, **params: str) -> dict:
    url = f"{BASE}{path}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "Germany InfraAtlas local dev"})
    with urlopen(req, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def _iso(sec: int) -> str:
    return datetime.fromtimestamp(sec, tz=UTC).isoformat()


def latest_snapshot() -> dict[str, dict[str, object]]:
    """Return latest live DE generation/price metrics in /grid/latest shape."""
    latest: dict[str, dict[str, object]] = {}
    try:
        power_json = _get_json("/public_power", country="de")
        by_ts: dict[int, dict[str, float]] = {}
        seconds = power_json.get("unix_seconds", [])
        for series in power_json.get("production_types", []):
            fuel = FUEL_MAP.get(series.get("name"))
            if fuel is None:
                continue
            for sec, value in zip(seconds, series.get("data", []), strict=False):
                if value is None:
                    continue
                bucket = by_ts.setdefault(int(sec), {})
                bucket[fuel] = bucket.get(fuel, 0.0) + float(value)

        if by_ts:
            # newest interval where every fuel has reported (the newest one is often partial)
            fuel_count = max(len(fuels) for fuels in by_ts.values())
            ts = max(sec for sec, fuels in by_ts.items() if len(fuels) == fuel_count)
            fuels = by_ts[ts]
            ts_iso = _iso(ts)
            for fuel, mw in fuels.items():
                latest[f"gen_{fuel}"] = {
                    "value": round(mw, 1),
                    "ts": ts_iso,
                    "source": "energy-charts:live",
                }
            # Energy-Charts' own published share (passthrough, not our computation)
            for series in power_json.get("production_types", []):
                if series.get("name") != "Renewable share of generation":
                    continue
                share = dict(zip(seconds, series.get("data", []), strict=False)).get(ts)
                if share is not None:
                    latest["renewable_share_of_generation"] = {
                        "value": round(float(share), 1),
                        "ts": ts_iso,
                        "source": "energy-charts:live",
                    }

            total = sum(max(mw, 0.0) for mw in fuels.values())
            if total > 0:
                weighted = sum(max(mw, 0.0) * EMISSION_FACTORS[fuel] for fuel, mw in fuels.items())
                renewable = sum(
                    max(mw, 0.0) for fuel, mw in fuels.items() if fuel in RENEWABLE_FUELS
                )
                carbon_free = sum(
                    max(mw, 0.0) for fuel, mw in fuels.items() if fuel in CARBON_FREE_FUELS
                )
                latest["carbon_intensity"] = {
                    "value": round(weighted / total, 1),
                    "ts": ts_iso,
                    "source": "energy-charts:computed-live",
                }
                latest["renewable_share"] = {
                    "value": round(100 * renewable / total, 1),
                    "ts": ts_iso,
                    "source": "energy-charts:computed-live",
                }
                latest["carbon_free_share"] = {
                    "value": round(100 * carbon_free / total, 1),
                    "ts": ts_iso,
                    "source": "energy-charts:computed-live",
                }
    except (OSError, URLError, ValueError):
        pass

    try:
        price_json = _get_json("/price", bzn="DE-LU")
        for sec, value in reversed(
            list(zip(price_json.get("unix_seconds", []), price_json.get("price", []), strict=False))
        ):
            if value is not None:
                latest["price_eur_mwh"] = {
                    "value": round(float(value), 2),
                    "ts": _iso(int(sec)),
                    "source": "energy-charts:live",
                }
                break
    except (OSError, URLError, ValueError):
        pass

    return latest


def newest_complete_index(columns: list[list[float | None]]) -> int | None:
    """Index of the newest interval that every series has fully reported.

    Energy-Charts publishes its newest 15-minute interval before every TSO has
    reported; a missing neighbour shows up as None or as an exact 0 that replaces
    a non-zero value, and is filled in later. Such intervals are skipped. A zero
    that follows a zero (an idle link) is a real reading and is kept.
    """
    length = max((len(col) for col in columns), default=0)
    for i in range(length - 1, -1, -1):
        complete = True
        for col in columns:
            value = col[i] if i < len(col) else None
            previous = col[i - 1] if 0 < i <= len(col) else None
            if value is None or (value == 0 and previous not in (None, 0)):
                complete = False
                break
        if complete:
            return i
    return None


def exchange() -> list[dict[str, object]]:
    """Latest complete cross-border flow per neighbour, or [] if the upstream API is down."""
    try:
        flow_json = _get_json("/cbpf", country="de")
    except (OSError, URLError, ValueError):
        return []

    seconds = flow_json.get("unix_seconds", [])
    series = [s for s in flow_json.get("countries", []) if s.get("name") and s.get("name") != "sum"]
    i = newest_complete_index([s.get("data", []) for s in series])
    if i is None or i >= len(seconds):
        return []
    return [
        {
            "neighbor_zone": s["name"],
            "ts": _iso(int(seconds[i])),
            "value_mw": round(float(s["data"][i]) * 1000.0, 1),
        }
        for s in series
    ]


def history(metric: str, hours: int = 48) -> list[dict[str, object]]:
    """Generation series (gen_<fuel>) straight from Energy-Charts, in /grid/history shape."""
    fuel = metric.removeprefix("gen_")
    if not metric.startswith("gen_") or fuel not in set(FUEL_MAP.values()):
        return []
    end = datetime.now(UTC)
    start = end - timedelta(hours=hours)
    fmt = "%Y-%m-%dT%H:%MZ"
    try:
        power_json = _get_json(
            "/public_power", country="de", start=start.strftime(fmt), end=end.strftime(fmt)
        )
    except (OSError, URLError, ValueError):
        return []
    totals: dict[int, float] = {}
    seconds = power_json.get("unix_seconds", [])
    for series in power_json.get("production_types", []):
        if FUEL_MAP.get(series.get("name")) != fuel:
            continue
        for sec, value in zip(seconds, series.get("data", []), strict=False):
            if value is not None:
                totals[int(sec)] = totals.get(int(sec), 0.0) + float(value)
    return [{"ts": _iso(sec), "value": round(mw, 1)} for sec, mw in sorted(totals.items())]
