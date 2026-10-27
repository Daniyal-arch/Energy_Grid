"""Probe the countries the room-to-connect map has no data for (2026-10-27): Belgium, Latvia,
Romania, Norway, Switzerland and the Western Balkans, Moldova and Ukraine.

For each operator's connection or capacity page: the HTTP status from here, whether the answer is
a browser challenge, the page title, and any data-file link or map service visible in the HTML,
so each country can be built (harmonised rows, scripts/build_connect_harmonised.py), fetched with
a browser (scripts/browser_fetch.py) or recorded as not published. The client names itself;
nothing is disguised.

  uv run python scripts/probe_connect_gaps.py
"""

from __future__ import annotations

import re
from datetime import date

import httpx

c = httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"})
PAGES: dict[str, list[str]] = {
    "BE Elia (Wallonia substations, hosting capacity map)": [
        "https://www.elia.be/en/infrastructure-and-projects/our-infrastructure/capacity-of-decentralized-production",
        "https://www.elia.be/en/customers/connection/grid-hosting-capacity",
    ],
    "BE ORES / Fluvius / Sibelga": [
        "https://www.ores.be/professionnels/carte-capacite-reseau",
        "https://www.fluvius.be/nl/thema/aansluitingen/capaciteitskaart",
        "https://www.sibelga.be/fr/raccordements/capacite-reseau",
    ],
    "LV AST / Sadales tikls": [
        "https://www.ast.lv/lv/content/pieslegumi",
        "https://karte.sadalestikls.lv/lv/briva-jauda",
        "https://sadalestikls.lv/lv/elektrostacijas-pieslegums",
    ],
    "RO Transelectrica / DSOs (ANRE: 110 kV available capacity published by the DSOs)": [
        "https://www.transelectrica.ro/web/tel/racordare",
        "https://www.transelectrica.ro/web/tel/harta-capacitatii",
        "https://www.delgaz.ro/distributie-energie-electrica/racordare",
        "https://www.distributieoltenia.ro/",
        "https://www.reteleelectrice.ro/",
        "https://www.e-distributie.com/ro/",
    ],
    "NO Statnett / Elvia": [
        "https://www.statnett.no/for-aktorer-i-kraftbransjen/nettilknytning/",
        "https://www.statnett.no/for-aktorer-i-kraftbransjen/nettilknytning/ledig-kapasitet/",
        "https://www.elvia.no/nettleie/kapasitet-i-stromnettet/",
    ],
    "CH Swissgrid": ["https://www.swissgrid.ch/de/home/customers/topics/grid-connection.html"],
    "RS EMS / BA NOS BiH / ME CGES / MK MEPSO / AL OST": [
        "https://www.ems.rs/",
        "https://www.nosbih.ba/",
        "https://www.cges.me/",
        "https://www.mepso.com.mk/",
        "https://www.ost.al/",
    ],
    "MD Moldelectrica / UA Ukrenergo": ["https://moldelectrica.md/", "https://ua.energy/"],
}
FILES = re.compile(r"""["']([^"'\s]+\.(?:xlsx|xls|csv|zip|pdf|json|geojson)(?:\?[^"'\s]*)?)["']""", re.I)
SERVICES = re.compile(
    r"""["'](https?://[^"'\s]*(?:arcgis|FeatureServer|MapServer|powerbi|geoserver|wms|wfs|/api/)[^"'\s]*)["']""",
    re.I,
)
WORDS = re.compile(r"(capacit|kapasitet|kapacit|jauda|capacitate|connection|racordare|tilknytning|anschluss|priklju|прикључ|приклуч)", re.I)

print("checked", date.today().isoformat())
for op, urls in PAGES.items():
    print(f"\n== {op}")
    for u in urls:
        try:
            r = c.get(u)
        except httpx.HTTPError as e:
            print(f"   {u}\n      {type(e).__name__}: {str(e)[:120]}")
            continue
        body = r.text[:300_000]
        title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        challenge = "just a moment" in body.lower() or "cf-chl" in body or r.headers.get("cf-mitigated") == "challenge"
        print(
            f"   {u}\n      HTTP {r.status_code}, {r.headers.get('content-type')}, server {r.headers.get('server')}, "
            f"challenge {challenge}, title {(title.group(1).strip()[:70] if title else None)!r}"
        )
        files = sorted({f for f in FILES.findall(body) if WORDS.search(f) and not re.search(r"\.(?:css|js)\b", f)})
        services = sorted(set(SERVICES.findall(body)))
        if files:
            print("      file links:", files[:12])
        if services:
            print("      services:", services[:8])
