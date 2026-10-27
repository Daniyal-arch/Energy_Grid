"""live: allow-listed reads where the API-or-Parquet rule says API (docs/DATA_LAKE.md section 1).

Sources:
- `eu_snapshot`: a file of the live snapshot (branch eu-data, refreshed by eu-snapshot.yml from
  ENTSO-E, the newest complete interval): flows, stats, outages, capacity, us, live_co2, ...
- `eu_days`: a file of the day archive (branch eu-days): prices, monthly, ...
- `eia930`: EIA-930 hourly demand, generation and interchange per US balancing authority (EIA
  API v2; `EIA_API_KEY`).
Per-source rate limits (requests per minute) and a 10-minute cache.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from tools.context import ToolContext, result

CACHE_S = 600
LIMITS = {"eu_snapshot": 30, "eu_days": 30, "eia930": 20}
SNAPSHOT_FILES = {
    "flows",
    "stats",
    "outages",
    "capacity",
    "us",
    "live_co2",
    "gb_carbon",
    "dk_live",
    "wind",
    "health",
    "reference",
}
DAYS_FILES = {"prices", "monthly", "retail", "transmission_outages", "imbalance"}
MAX_CHARS = 24_000

_cache: dict[str, tuple[float, Any]] = {}
_calls: dict[str, list[float]] = {}
_lock = threading.Lock()


class LiveArgs(BaseModel):
    source: Literal["eu_snapshot", "eu_days", "eia930"]
    params: dict[str, str] = Field(
        default_factory=dict,
        description="eu_snapshot/eu_days: {file, key?} (key picks one entry, e.g. a country code); "
        "eia930: {respondent, type (D demand, NG net generation, TI interchange), start, end "
        "(YYYY-MM-DDTHH)}",
    )


def _allow(source: str) -> bool:
    now = time.time()
    with _lock:
        calls = [t for t in _calls.get(source, []) if now - t < 60]
        if len(calls) >= LIMITS[source]:
            _calls[source] = calls
            return False
        calls.append(now)
        _calls[source] = calls
        return True


def _pick(doc: Any, key: str | None) -> Any:
    if not key or not isinstance(doc, dict):
        return doc
    for container in ("countries", "zones", "regions", "pairs"):
        sub = doc.get(container)
        if isinstance(sub, dict) and key in sub:
            return {
                "fetched": doc.get("fetched"),
                "source": doc.get("source"),
                container: {key: sub[key]},
            }
        if isinstance(sub, list):
            hits = [x for x in sub if key in str(x)[:80]]
            if hits:
                return {
                    "fetched": doc.get("fetched"),
                    "source": doc.get("source"),
                    container: hits[:200],
                }
    return {"error": f"no entry {key!r}", "keys": list(doc.keys())[:40]}


def _trim(v: Any) -> Any:
    import json

    text = json.dumps(v, default=str)
    if len(text) <= MAX_CHARS:
        return v
    if isinstance(v, dict):
        return {
            "note": "too large to return whole; pass params.key to pick an entry",
            "keys": list(v.keys())[:60],
            "fetched": v.get("fetched"),
            "source": v.get("source"),
        }
    return {
        "note": "too large; first items",
        "items": v[:50] if isinstance(v, list) else str(v)[:MAX_CHARS],
    }


def live(ctx: ToolContext, source: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    params = params or {}
    s = ctx.settings
    key = f"{source}:{sorted(params.items())}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    if not _allow(source):
        return result({"error": f"rate limit for {source} reached; try again in a minute"}, [])
    try:
        if source in ("eu_snapshot", "eu_days"):
            files = SNAPSHOT_FILES if source == "eu_snapshot" else DAYS_FILES
            f = params.get("file", "")
            if f not in files:
                return result({"error": f"file must be one of {sorted(files)}"}, [])
            base = s.snapshot_remote if source == "eu_snapshot" else s.public_data_remote
            r = httpx.get(f"{base}{f}.json", timeout=15)
            r.raise_for_status()
            doc = r.json()
            data = _trim(_pick(doc, params.get("key")))
            out = result(
                data,
                [
                    {
                        "dataset": source,
                        "table": f"{f}.json",
                        "licence": "per source (docs/DATA_SOURCES.md)",
                        "retrieved": str(
                            doc.get("fetched") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        ),
                    }
                ],
            )
        else:
            if not s.eia_api_key:
                return result({"error": "eia930 is not configured (EIA_API_KEY missing)"}, [])
            q = {
                "api_key": s.eia_api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[respondent][]": params.get("respondent", "ERCO"),
                "facets[type][]": params.get("type", "D"),
                "start": params.get("start", ""),
                "end": params.get("end", ""),
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": "200",
            }
            r = httpx.get(
                "https://api.eia.gov/v2/electricity/rto/region-data/data/", params=q, timeout=20
            )
            r.raise_for_status()
            rows = r.json().get("response", {}).get("data", [])
            out = result(
                {"rows": rows, "unit": "MWh per hour"},
                [
                    {
                        "dataset": "eia930",
                        "table": "electricity/rto/region-data",
                        "licence": "public domain (EIA)",
                        "retrieved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                ],
            )
    except httpx.HTTPError as e:
        return result({"error": f"{source}: {type(e).__name__}: {str(e)[:200]}"}, [])
    _cache[key] = (time.time(), out)
    return out
