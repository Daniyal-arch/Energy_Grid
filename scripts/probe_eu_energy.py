"""Probe candidate sources for a Europe-wide grid + plants + flows view.

Metadata and small samples only (no large downloads):
  1. PyPSA-Eur OSM-based transmission network on Zenodo (file list + sizes)
  2. powerplantmatching European plant list on Zenodo / GitHub (file size, columns)
  3. ENTSO-E Transparency physical cross-border flows [A11] for two borders
  4. Eurostat GISCO country outlines (size of the 1:20M file)

    uv run python scripts/probe_eu_energy.py
"""

from __future__ import annotations

import csv
import io
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
client = httpx.Client(
    timeout=60, follow_redirects=True, headers={"User-Agent": "InfraAtlas-probe/0.1"}
)


def zenodo(query: str) -> None:
    r = client.get(
        "https://zenodo.org/api/records", params={"q": query, "size": 4, "sort": "mostrecent"}
    )
    r.raise_for_status()
    for hit in r.json()["hits"]["hits"]:
        md = hit["metadata"]
        print(f"- {md['title'][:90]} | {md.get('publication_date')} | {hit['links']['self_html']}")
        for f in hit.get("files", [])[:12]:
            print(f"    {f['key']:<45} {f['size'] / 1e6:8.1f} MB")


print("== 1. PyPSA-Eur OSM network (Zenodo)")
zenodo('"PyPSA-Eur" OSM network')

print("\n== 2. powerplantmatching")
url = "https://raw.githubusercontent.com/PyPSA/powerplantmatching/master/powerplants.csv"
head = client.head(url)
print(url, head.status_code, head.headers.get("content-length"), "bytes")
with client.stream("GET", url) as r:
    text = ""
    for chunk in r.iter_text():
        text += chunk
        if len(text) > 20000:
            break
rows = list(csv.reader(io.StringIO(text)))
print("columns:", rows[0])
for row in rows[1:4]:
    print("  ", row[:12])

print("\n== 3. ENTSO-E physical flows [A11]")
key = os.environ.get("ENTSOE_API_KEY")
zones = {"DE_LU": "10Y1001A1001A82H", "FR": "10YFR-RTE------C", "ES": "10YES-REE------0"}
end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
start = end - timedelta(hours=6)
for a, b in [("DE_LU", "FR"), ("FR", "ES")]:
    params = {
        "securityToken": key,
        "documentType": "A11",
        "in_Domain": zones[b],
        "out_Domain": zones[a],
        "periodStart": start.strftime("%Y%m%d%H%M"),
        "periodEnd": end.strftime("%Y%m%d%H%M"),
    }
    r = client.get("https://web-api.tp.entsoe.eu/api", params=params)
    print(f"{a}->{b}: HTTP {r.status_code}, {len(r.content)} bytes")
    if r.status_code == 200:
        ns = {"n": r.text.split('xmlns="')[1].split('"')[0]}
        pts = ET.fromstring(r.content).findall(".//n:Point", ns)
        vals = [p.find("n:quantity", ns).text for p in pts]
        res = ET.fromstring(r.content).find(".//n:resolution", ns)
        print(f"   resolution {res.text if res is not None else '?'}, last values MW: {vals[-4:]}")
    else:
        print("  ", r.text[:300])

print("\n== 4. GISCO country outlines")
url = "https://gisco-services.ec.europa.eu/distribution/v2/countries/geojson/CNTR_RG_20M_2024_4326.geojson"
h = client.head(url)
print(url, h.status_code, h.headers.get("content-length"), "bytes")
