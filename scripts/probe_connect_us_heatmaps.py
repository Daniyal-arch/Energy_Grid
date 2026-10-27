"""Probe the US sources of room to connect beyond the queues (2026-10-27).

FERC Order No. 2023 requires every jurisdictional transmission provider to publish a heatmap of
the estimated incremental injection capacity (MW) at each bus or point of interconnection under
N-1, updated after each cluster study. Utilities also publish distribution hosting capacity maps
(per feeder or line section). This finds, for each candidate, the page, any data service behind
it (ArcGIS, CartoVista, JSON, CSV, Excel) and the open-data catalogues that index them. The
client names itself; nothing is disguised.

  uv run python scripts/probe_connect_us_heatmaps.py
"""

from __future__ import annotations

import re
from datetime import date

import httpx

c = httpx.Client(
    timeout=40, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
PAGES: dict[str, list[str]] = {
    "CAISO POI heatmap": [
        "https://www.caiso.com/poi-heatmap/",
        "https://www.caiso.com/library/ferc-order-no-2023-points-of-interconnection-heatmap",
    ],
    "MISO GI queue and capacity heat map": [
        "https://www.misoenergy.org/planning/resource-utilization/GI_Queue/",
        "https://www.misoenergy.org/planning/resource-utilization/GI_Queue/gi-interactive-queue/",
    ],
    "ISO-NE heatmap": [
        "https://www.iso-ne.com/system-planning/interconnection-service/interconnection-request-queue",
        "https://www.iso-ne.com/system-planning/interconnection-service",
    ],
    "NYISO interconnections": ["https://www.nyiso.com/interconnections"],
    "SPP hosting capacity tool": [
        "https://opsportal.spp.org/Studies/HostingCapacity",
        "https://www.spp.org/engineering/generator-interconnection/",
    ],
    "PJM planning center (Queue Scope)": [
        "https://www.pjm.com/markets-and-operations/etools/planning-center",
    ],
    "VELCO POI map": ["https://www.velco.com/planning"],
    "Southern Company OASIS": ["https://www.oasis.oati.com/woa/docs/SOCO/SOCOdocs/SOCO.html"],
    "ORNL OpenEnergyHub catalogue (hosting capacity)": [
        "https://openenergyhub.ornl.gov/api/explore/v2.1/catalog/datasets?where=search(%22hosting%22)&limit=100&select=dataset_id",
        "https://openenergyhub.ornl.gov/api/explore/v2.1/catalog/datasets?where=search(%22heat%20map%22)&limit=100&select=dataset_id",
    ],
}
HINT = re.compile(
    r"""["'](https?://[^"'\s<>]*(?:heat|hosting|cartovista|arcgis|FeatureServer|MapServer|"""
    r"""\.json|\.csv|\.xlsx|powerbi)[^"'\s<>]*)["']""",
    re.I,
)
REL = re.compile(r"""["'](/[^"'\s<>]*(?:heat|hosting|poi|capacity)[^"'\s<>]*)["']""", re.I)

print("checked", date.today().isoformat())
for name, urls in PAGES.items():
    print(f"\n== {name}")
    for u in urls:
        try:
            r = c.get(u)
        except httpx.HTTPError as e:
            print(f"   {u}\n      {type(e).__name__}: {str(e)[:120]}")
            continue
        body = r.text[:400_000]
        title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        print(
            f"   {u}\n      HTTP {r.status_code}, {r.headers.get('content-type')}, "
            f"title {(title.group(1).strip()[:70] if title else None)!r}"
        )
        if "json" in (r.headers.get("content-type") or "") and r.status_code == 200:
            print("      datasets:", re.findall(r'"dataset_id"\s*:\s*"([^"]+)"', r.text)[:60])
            continue
        links = sorted(set(HINT.findall(body)))
        rel = sorted({x for x in REL.findall(body) if not x.endswith((".css", ".js", ".png"))})
        if links:
            print("      links:", links[:15])
        if rel:
            print("      paths:", rel[:15])
