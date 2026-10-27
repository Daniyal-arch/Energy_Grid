"""Probe free grid capacity in FI, GR, LV, RO and CY (brief 23, "room to connect"): retry.

For each operator page: HTTP status from here, title, data-file links and map / API services
visible in the HTML. Where a page is an ArcGIS Online app, the item's JSON (title, modified,
licence) and its feature layers are listed (attributes only, no map images). The client names
itself; a refusal (403 / 451 / reset) is recorded, not worked around.

  uv run python scripts/probe_connect_others.py
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx

c = httpx.Client(
    timeout=45, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
PAGES: dict[str, list[str]] = {
    "FI Fingrid": [
        "https://www.fingrid.fi/en/grid/grid-connection-agreement-phases/grid-scope/",
        "https://www.fingrid.fi/kantaverkko/liittyminen-kantaverkkoon/liittymiskapasiteetti/",
        "https://karttapalaute.fingrid.fi/",
    ],
    "FI Caruna": [
        "https://caruna.fi/ajankohtaista/carunan-kapasiteettikartta-uudistuu-sahkoverkon-vapaa-kapasiteetti-nakyvissa-koko",
        "https://plus.caruna.fi/capacities-map",
    ],
    "FI Elenia": [
        "https://www.elenia.fi/en/electricity-consumption-and-production/green-transition/map-of-available-capacity",
        "https://experience.arcgis.com/experience/4c3f68b70a574a0e9ec0f9837a187542",
    ],
    "GR IPTO": [
        "https://www.admie.gr/en/grid/connection-to-the-system",
        "https://www.admie.gr/en/grid/user-connection/res-connection-statistics",
    ],
    "GR HEDNO": [
        "https://apps.deddie.gr/WebAPE/main.html",
        "https://www.deddie.gr/el/",
    ],
    "LV AST": ["https://www.ast.lv/lv/content/pieejama-jauda", "https://www.ast.lv/"],
    "LV Sadales tikls": [
        "https://karte.sadalestikls.lv/lv/briva-jauda",
        "https://sadalestikls.lv/lv/pieslegumi",
    ],
    "RO Transelectrica": [
        "https://www.transelectrica.ro/web/tel/racordare",
        "https://www.transelectrica.ro/web/tel/capacitati-disponibile",
        "https://www.transelectrica.ro/web/tel/harta-capacitatilor",
    ],
    "RO Electrica (Distributie Energie Electrica Romania)": [
        "https://www.distributie-energie.ro/",
        "https://www.distributie-energie.ro/capacitati-disponibile/",
    ],
    "RO Delgaz Grid": ["https://www.delgaz.ro/", "https://www.delgaz.ro/capacitati-disponibile"],
    "RO E-Distributie": [
        "https://www.e-distributie.com/ro.html",
        "https://www.e-distributie.com/ro/racordare/capacitate-disponibila.html",
    ],
    "RO PPC Retele": [
        "https://www.ppcretele.ro/",
        "https://www.ppcretele.ro/capacitate-disponibila",
    ],
    "CY TSO Cyprus": ["https://tsoc.org.cy/", "https://tsoc.org.cy/electrical-system/"],
    "CY EAC": [
        "https://www.eac.com.cy/EN/RegulatedActivities/Distribution/renewableenergy/Pages/hosting-capacity.aspx",
    ],
}
FILES = re.compile(
    r"""["']([^"'\s]+\.(?:xlsx|xls|csv|zip|pdf|json|geojson)(?:\?[^"'\s]*)?)["']""", re.I
)
SERVICES = re.compile(
    r"""["'](https?://[^"'\s]*(?:arcgis|FeatureServer|MapServer|powerbi|geoserver|wms|wfs|"""
    r"""/api/|\.ashx|\.asmx)[^"'\s]*)["']""",
    re.I,
)
KEYS = re.compile(r"capacit|kapasiteet|jauda|περιθώρ|hosting|disponibil|liittym|racord", re.I)


def arcgis_item(item_id: str) -> None:
    """An ArcGIS Online item (app or web map): metadata and, for a map, its layers."""
    base = f"https://www.arcgis.com/sharing/rest/content/items/{item_id}"
    it = c.get(base, params={"f": "json"}).json()
    mod = it.get("modified")
    print(
        f"      arcgis item {item_id}: {it.get('title')!r} type {it.get('type')} access "
        f"{it.get('access')} modified "
        f"{datetime.fromtimestamp(mod / 1000, UTC).date() if mod else None} "
        f"licence {it.get('licenseInfo')!r}"[:300]
    )
    if it.get("error"):
        print("      ", it["error"])
        return
    data = c.get(base + "/data", params={"f": "json"}).json()
    maps = set(re.findall(r'"(?:webmap|itemId|id)"\s*:\s*"([0-9a-f]{32})"', str(data)))
    for lyr in data.get("operationalLayers", []) if isinstance(data, dict) else []:
        print(f"      layer {lyr.get('title')!r}: {lyr.get('url')}")
    if maps - {item_id}:
        print("      referenced items:", sorted(maps - {item_id})[:8])


print("checked", date.today().isoformat())
for op, urls in PAGES.items():
    print(f"\n== {op}")
    for u in urls:
        try:
            r = c.get(u)
        except httpx.HTTPError as e:
            print(f"   {u}\n      {type(e).__name__}: {str(e)[:140]}")
            continue
        body = r.text[:300_000]
        title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        print(
            f"   {u}\n      HTTP {r.status_code}, {r.headers.get('content-type')}, final "
            f"{str(r.url)[:90]}, title {(title.group(1).strip()[:70] if title else None)!r}"
        )
        if r.status_code != 200:
            continue
        files = sorted({f for f in FILES.findall(body) if KEYS.search(f)})
        services = sorted(set(SERVICES.findall(body)))
        anchors = [
            re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()[:60] + " -> " + m.group(1)[:110]
            for m in re.finditer(r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", body, re.S)
            if KEYS.search(m.group(1) + m.group(2))
        ]
        if files:
            print("      file links:", files[:12])
        if services:
            print("      services:", services[:8])
        for a in list(dict.fromkeys(anchors))[:8]:
            print("      link:", a)
        for item in sorted(
            set(re.findall(r"(?:appid=|experience/|webmap=)([0-9a-f]{32})", u + body))
        ):
            arcgis_item(item)
