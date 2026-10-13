"""Probe the Climate TRACE API (v6, no key): asset fields, coordinates, years, paging, counts.

uv run python scripts/probe_climate_trace.py
"""

from __future__ import annotations

import json
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
API = "https://api.climatetrace.org/v6"
c = httpx.Client(timeout=120)

print("== API description")
for path in ("/swagger/doc.json", "/openapi.json", "/docs"):
    r = c.get(API.replace("/v6", "") + path)
    print(path, r.status_code, r.headers.get("content-type"), len(r.content))
    if r.status_code == 200 and "json" in (r.headers.get("content-type") or ""):
        d = r.json()
        for p, ops in (d.get("paths") or {}).items():
            if "asset" in p or "download" in p:
                params = [x.get("name") for op in ops.values() for x in op.get("parameters", [])]
                print("  ", p, sorted(set(params)))
        break

print("\n== one power asset, every field")
r = c.get(f"{API}/assets", params={"limit": 1, "sectors": "power"})
a = r.json()["assets"][0]
print(json.dumps({k: v for k, v in a.items() if k != "Confidence"}, ensure_ascii=False)[:2500])

print("\n== the same asset by id (does it carry a geometry and a monthly series?)")
r = c.get(f"{API}/assets/{a['Id']}")
print(r.status_code)
d = r.json()
print(sorted(d.keys()) if isinstance(d, dict) else type(d))
print(json.dumps(d, ensure_ascii=False)[:2500])

print("\n== years and paging")
for year in (2023, 2024, 2025):
    t = time.time()
    r = c.get(
        f"{API}/assets", params={"limit": 1000, "offset": 0, "sectors": "power", "year": year}
    )
    d = r.json()
    n = len(d.get("assets", []))
    em = [
        x["EmissionsSummary"][0]["EmissionsQuantity"]
        for x in d.get("assets", [])
        if x.get("EmissionsSummary")
    ]
    print(
        year,
        r.status_code,
        n,
        "assets in",
        f"{time.time() - t:.1f}s",
        "first",
        em[:3],
        "keys",
        list(d.keys()),
    )

print("\n== counts per sector (paging to the end)")
for sector in ("power", "manufacturing", "fossil-fuel-operations", "mineral-extraction"):
    total, off = 0, 0
    while True:
        r = c.get(
            f"{API}/assets", params={"limit": 1000, "offset": off, "sectors": sector, "year": 2024}
        )
        page = r.json().get("assets", [])
        total += len(page)
        if len(page) < 1000 or off > 60000:
            break
        off += 1000
    print(sector, total)
