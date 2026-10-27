"""Probe Belgium's and Slovakia's free grid capacity pages (brief 23, "room to connect").

These sites answer scripts with a Cloudflare browser check (or similar); this records, for each
page, the HTTP status from here, whether the answer is a challenge, and any data-file link or
map service visible in the HTML, so an entry for scripts/browser_fetch.py can be proposed.
The client names itself; nothing is disguised.

  uv run python scripts/probe_connect_be_sk.py
"""

from __future__ import annotations

import re
from datetime import date

import httpx

c = httpx.Client(
    timeout=45, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
PAGES: dict[str, list[str]] = {
    "BE Elia": [
        "https://www.elia.be/en/customers/connection/grid-hosting-capacity",
        "https://www.elia.be/en/infrastructure-and-projects/our-infrastructure/capacity-of-decentralized-production",
        "https://opendata.elia.be/api/explore/v2.1/catalog/datasets?where=search(%22hosting%22)&limit=20",
        "https://opendata.elia.be/api/explore/v2.1/catalog/datasets?where=search(%22capacity%22)&limit=50",
    ],
    "BE Fluvius": [
        "https://www.fluvius.be/nl/thema/aansluitingen/capaciteitskaart",
        "https://opendata.fluvius.be/api/explore/v2.1/catalog/datasets?where=search(%22capaciteit%22)&limit=50",
    ],
    "BE ORES": [
        "https://www.ores.be/professionnels/carte-capacite-reseau",
        "https://opendata.ores.eu/api/explore/v2.1/catalog/datasets?where=search(%22capacit%22)&limit=50",
    ],
    "BE Sibelga": ["https://www.sibelga.be/fr/raccordements/capacite-reseau"],
    "SK SEPS": [
        "https://installedpower.sepsas.sk/",
        "https://www.sepsas.sk/pripojenie-do-prenosovej-sustavy/",
    ],
    "SK ZSD": [
        "https://www.zsdis.sk/Uvod/Vyrobcovia/Pred-pripojenim/Volna-kapacita",
        "https://www.zsdis.sk/Uvod/Online-sluzby/Mapa-pripojitelnosti",
    ],
    "SK SSD": [
        "https://www.ssd.sk/vyrobcovia-elektriny/prehlad-cerpania-pridelenych-vykonov?page_id=6335",
        "https://www.ssd.sk/mapa-pripojitelnosti",
    ],
    "SK VSD": [
        "https://www.vsds.sk/edso/domov/aplikacie/ostatne/mapa-pripojitelnosti",
        "https://www.vsds.sk/edso/domov/vyrobcovia-elektriny/pripojenie-zdroja/fotovolticka-poradna",
        "https://www.vsds.sk/mdoc/dso.B6000.A/doc/Volna-kapacita-vykonu-2019.pdf",
    ],
}
FILES = re.compile(
    r"""["']([^"'\s]+\.(?:xlsx|xls|csv|zip|pdf|json|geojson)(?:\?[^"'\s]*)?)["']""", re.I
)
SERVICES = re.compile(
    r"""["'](https?://[^"'\s]*(?:arcgis|FeatureServer|MapServer|powerbi|app\.powerbi|"""
    r"""geoserver|wms|wfs|/api/)[^"'\s]*)["']""",
    re.I,
)

print("checked", date.today().isoformat())
for op, urls in PAGES.items():
    print(f"\n== {op}")
    for u in urls:
        try:
            r = c.get(u)
        except httpx.HTTPError as e:
            print(f"   {u}\n      {type(e).__name__}: {str(e)[:120]}")
            continue
        body = r.text[:200_000]
        title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        challenge = (
            "just a moment" in body.lower()
            or "cf-chl" in body
            or r.headers.get("cf-mitigated") == "challenge"
        )
        print(
            f"   {u}\n      HTTP {r.status_code}, {r.headers.get('content-type')}, "
            f"server {r.headers.get('server')}, challenge {challenge}, "
            f"title {(title.group(1).strip()[:70] if title else None)!r}"
        )
        if "json" in (r.headers.get("content-type") or "") and r.status_code == 200:
            ids = re.findall(r'"dataset_id"\s*:\s*"([^"]+)"', r.text)
            print("      datasets:", ids[:30])
            continue
        files = sorted({f for f in FILES.findall(body) if not re.search(r"\.(?:css|js)\b", f)})
        services = sorted(set(SERVICES.findall(body)))
        if files:
            print("      file links:", files[:15])
        if services:
            print("      services:", services[:10])
