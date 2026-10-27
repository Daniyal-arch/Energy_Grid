"""Probe Slovenia's free grid capacity (brief 23, "room to connect"): ELES and the DSOs.

1. ELES page "Priključne zmogljivosti elektroenergetskega omrežja": links an ArcGIS Online
   atlas; its web map holds two public feature layers (ELES switchyards with available
   injection / withdrawal MW, and DSO MV substations with an injection-capacity class in kW).
   We read the web map's JSON and query the layers (attributes and points), no map images.
2. The 2021 ELES PDF "Hosting capacity ELESovih RTP" (the earlier evidence): does its text extract?
3. The DSO development plan (RNDS 2027-2036, consultation, April 2026): tables per RTP 110/SN
   with rated power, peak load and free N-1 capacity (MVA); pdfplumber test on the first table.

  uv run python scripts/probe_connect_si.py
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime

import httpx
import pdfplumber

c = httpx.Client(
    timeout=120, follow_redirects=True, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"}
)
PAGE = "https://www.eles.si/mozni-obseg-in-lokacije-prikljucevanja-ove"
OLD_PDF = "https://www.eles.si/Portals/0/Documents/Hosting%20capacity%20ELESovih%20RTP.pdf"
RNDS = "https://www.eles.si/Portals/0/Novice/DOKUMENTI/RNDS_2027_2036_posvetovalni_dokument.pdf"


def ms_date(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).date().isoformat() if ms else "?"


print(f"== 1. ELES page {PAGE}")
r = c.get(PAGE)
print("HTTP", r.status_code)
apps = sorted(set(re.findall(r"https://elesgis\.maps\.arcgis\.com/apps/[^\"'&]+[^\"']*", r.text)))
print("atlas links:", [a.replace("&amp;", "&") for a in apps[:2]])
webmap = re.search(r"webmap=([0-9a-f]{32})", r.text)
assert webmap, "no web map id on the page"
wid = webmap.group(1)
item = c.get(f"https://www.arcgis.com/sharing/rest/content/items/{wid}", params={"f": "json"})
it = item.json()
print(
    f"web map {wid}: {it.get('title')!r}, access {it.get('access')}, modified "
    f"{ms_date(it.get('modified'))}, licence {it.get('licenseInfo')!r}, "
    f"terms {it.get('accessInformation')!r}"
)
data = c.get(
    f"https://www.arcgis.com/sharing/rest/content/items/{wid}/data", params={"f": "json"}
).json()
for lyr in data.get("operationalLayers", []):
    url = lyr["url"]
    meta = c.get(url, params={"f": "json"}).json()
    n = c.get(
        url + "/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}
    ).json()
    print(f"\n-- layer {lyr.get('title')!r}: {url}")
    print(
        f"   {n.get('count')} features, data last edited "
        f"{ms_date((meta.get('editingInfo') or {}).get('dataLastEditDate'))}"
    )
    print("   fields:", [(f["name"], f.get("alias")) for f in meta.get("fields", [])])
    q = c.get(
        url + "/query",
        params={
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "resultRecordCount": 4,
            "f": "json",
        },
    ).json()
    for f in q.get("features", []):
        g = f.get("geometry") or {}
        print("  ", f["attributes"], (round(g.get("x", 0), 4), round(g.get("y", 0), 4)))
    # the distribution of values per field that is a class
    for fld in ("Obseg", "GEN_MW"):
        if any(f["name"] == fld for f in meta.get("fields", [])):
            s = c.get(
                url + "/query",
                params={
                    "where": "1=1",
                    "groupByFieldsForStatistics": fld,
                    "outStatistics": '[{"statisticType":"count","onStatisticField":"OBJECTID",'
                    '"outStatisticFieldName":"n"}]',
                    "f": "json",
                },
            ).json()
            vals = sorted((f["attributes"][fld], f["attributes"]["n"]) for f in s["features"])
            print(f"   values of {fld}:", vals[:30])

print(f"\n== 2. ELES 2021 PDF {OLD_PDF}")
r = c.get(OLD_PDF)
print("HTTP", r.status_code, len(r.content), "bytes, last-modified", r.headers.get("last-modified"))
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    for i, pg in enumerate(pdf.pages):
        print(f"   page {i + 1}: text {len(pg.extract_text() or '')} chars")

print(f"\n== 3. DSO development plan (RNDS 2027-2036) {RNDS}")
r = c.get(RNDS)
print("HTTP", r.status_code, len(r.content), "bytes, last-modified", r.headers.get("last-modified"))
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print("pages", len(pdf.pages))
    shown = 0
    rows_total = 0
    for i, pg in enumerate(pdf.pages):
        txt = pg.extract_text() or ""
        if "Prosta" not in txt or "MVA" not in txt:
            continue
        rows = [ln for ln in txt.splitlines() if re.match(r"^RTP .*MVA", ln)]
        rows_total += len(rows)
        if shown < 2 and rows:
            shown += 1
            k = txt.find("Dosežena")
            print(f"-- page {i + 1} header as printed:", txt[k : k + 160].replace("\n", " | "))
            for t in pg.extract_tables()[:1]:
                for row in t[:4]:
                    print("   table row:", row)
            for ln in rows[:3]:
                print("   text row:", ln)
    print("RTP rows (text lines 'RTP ... MVA') in the plan:", rows_total)
