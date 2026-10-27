"""Probe Germany's grid-connection capacity publications (brief 23, DE).

    uv run python scripts/probe_connect_de.py

The four TSOs publish a "Netzkarte" before each cycle of the Reifegradverfahren (since April
2026); the large DSOs publish connection checks or PDFs. For each operator this checks the page
and the data behind its map, and prints status, record count and two sample records.

- 50Hertz: the map is the "Digitale Netzbilder" app; its iframe calls the site's proxy
  GetDnbInfo?path=GridLoadMapVersion/map/type/gridcapacity (JSON, a location per substation with
  coordinates, voltage, available load / generation MW, free bays). The app's own API host
  (api-digitale-netzbilder.50hertz.com) gives an empty reply to direct calls.
- Amprion: a PDF map and a PDF table (no MW: connection design n-0 / n-1, earliest year).
- TenneT DE and the E.ON DSOs (Westnetz is westenergie; E.DIS, Bayernwerk, Avacon): Cloudflare
  browser challenge (HTTP 403 with cf-mitigated: challenge); not fetched around.
- TransnetBW: the tooltips in the page HTML (read by build_connect_eu.py), SVG positions only.
- VNBdigital (the joint DSO platform of section 14e EnWG): GraphQL gateway; its services are the
  operator lookup, grid expansion plans, regional scenarios and section 14a control measures, no
  connection capacity.
- Netze BW: Mittelspannungsauskunft (a per-site check, distance to a suitable point, no MW list).
- Saarland DSOs: geoportal app "Kapazitäten der Umspannanlagen" (WMC 7400), a graphic per site.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any

import httpx

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) InfraAtlas (github.com/Daniyal-arch/Energy_Grid)"
}
c = httpx.Client(timeout=60, follow_redirects=True, headers=UA)

HZ_PAGE = "https://www.50hertz.com/de/Netz/Netzanschluss"
HZ_PROXY = (
    "https://www.50hertz.com/DesktopModules/Lotes/FrequentModules/API/DigitalMap/GetDnbInfo?path="
)
HZ_DATA = HZ_PROXY + "GridLoadMapVersion/map/type/gridcapacity"
HZ_API = (
    "https://api-digitale-netzbilder.50hertz.com/api/api/GridLoadMapVersion/map/type/gridcapacity"
)
AMP_PAGE = (
    "https://www.amprion.net/Strommarkt/Netzkunden/Netzanschluss/"
    "Darstellung-der-potenziellen-Netzanschlussmoeglichkeiten-und-der-Kundenprojekte.html"
)
AMP_DOCS = (
    "https://www.amprion.net/Dokumente/Strommarkt/Netzkunden/Netzanschlussregeln/"
    "07_Darstellung-der-Kundenprojekte-sowie-der-Schaltfeldverfuegbarkeit/"
)
AMP_TABLE = (
    AMP_DOCS + "Ergaenzendes-Dokument-zu-potenziellen-Netzanschlussmoeglichkeiten-04.2026.pdf"
)
AMP_MAP = AMP_DOCS + "Karte-ueber-potenzielle-Netzanschlussmoeglichkeiten-04.2026.pdf"
TBW = "https://www.transnetbw.de/de/transparenz/netzzugang-und-entgelt/netzanschlusskarte"
VNB = "https://www.vnbdigital.de/gateway/graphql"
BLOCKED = {
    "TenneT DE": "https://www.tennet.eu/de/strommarkt/kunden-deutschland/netzanschlussanfragen",
    "Westnetz": "https://www.westnetz.de/",
    "E.DIS": "https://www.e-dis-netz.de/",
    "Bayernwerk": "https://www.bayernwerk-netz.de/",
    "Avacon": "https://www.avacon-netz.de/",
}
NETZE_BW = [
    "https://www.netze-bw.de/stromeinspeisung/mittelspannungsauskunft",
    "https://www.netze-bw.de/netzanschluss/vergabe",
]
SAAR_ARTICLE = "https://geoportal.saarland.de/article/Umspannanlagen_Kapazitaeten/"


def get(url: str, **kw: Any) -> httpx.Response | None:
    t0 = time.monotonic()
    try:
        r = c.get(url, **kw)
    except httpx.HTTPError as err:
        print(f"  {url}\n    {err.__class__.__name__}: {err}")
        return None
    cf = " cf-mitigated=" + r.headers["cf-mitigated"] if "cf-mitigated" in r.headers else ""
    print(
        f"  {url}\n    HTTP {r.status_code} {r.headers.get('content-type', '')[:40]} "
        f"{len(r.content) / 1e3:.0f} kB {time.monotonic() - t0:.1f}s "
        f"server={r.headers.get('server', '')}{cf}"
    )
    return r


def head(title: str) -> None:
    print(f"\n=== {title}")


def fifty_hertz() -> None:
    head("50Hertz (Netzkarte, Reifegradverfahren)")
    r = get(HZ_PAGE)
    if r is not None and r.status_code == 200:
        ids = re.findall(r'"dnbMapId":"([^"]+)"', r.text)
        stand = re.search(r"zum (\d\d\.\d\d\.\d{4}) bestmöglichen", r.text)
        print(f"    dnbMapId={ids} Stand={stand.group(1) if stand else None}")
    get(HZ_API)
    r = get(HZ_DATA)
    if r is None or r.status_code != 200:
        return
    d = r.json()
    locs = d["locations"]
    mv = d["configuration"]["mapVersion"]
    print(f"    map version {mv['name']!r} production={mv['isProduction']} {mv['updatedAt']}")
    latest = max(x["updatedAt"] or "" for x in locs)
    print(f"    {len(locs)} locations; latest location update {latest}")
    print(f"    fields: {sorted(k for k in locs[0] if k not in ('settings', 'coordinate'))}")
    print(f"    voltage: {dict(Counter(x['voltageLevel'] for x in locs))}")
    print(f"    free bays: {dict(Counter(x['availableSwitchgearBay'] for x in locs))}")
    n_load = sum(x["availableLoadCapacityMw"] is not None for x in locs)
    n_gen = sum(x["availableGenerationCapacityMw"] is not None for x in locs)
    print(f"    with available load MW: {n_load}, with available generation MW: {n_gen}")
    n_xy = sum(bool(x.get("coordinate")) for x in locs)
    print(f"    coordinates: {n_xy} ({locs[0]['coordinate']['type']})")
    for x in sorted(locs, key=lambda x: -(x["availableLoadCapacityMw"] or 0))[:2]:
        row = {k: v for k, v in x.items() if k != "settings"}
        print("    sample:", json.dumps(row, ensure_ascii=False))


def amprion() -> None:
    head("Amprion (PDF map and PDF table)")
    r = get(AMP_PAGE)
    if r is not None and r.status_code == 200:
        for u in sorted(
            set(re.findall(r'(?:href|src)="([^"]+\.(?:pdf|png|xlsx|csv|json))"', r.text))
        ):
            print("    linked:", u)
    get(AMP_MAP)
    r = get(AMP_TABLE)
    if r is not None and r.status_code == 200:
        print(
            f"    PDF {r.content[:8]!r}; a printed table: substation, voltage, municipality, "
            "n-0/n-1, earliest year"
        )


def transnetbw() -> None:
    head("TransnetBW (tooltips in the page HTML)")
    r = get(TBW)
    if r is None or r.status_code != 200:
        return
    kinds = Counter(re.findall(r"tooltip-uw-type--(\w+)", r.text))
    groups = len(re.findall(r'id="map-uw-', r.text))
    print(f"    substations by class: {dict(kinds)}; SVG map groups (screen positions): {groups}")
    pat = r'class="tooltip[^"]*tooltip-uw-([a-z0-9-]+)[^"]*tooltip-uw-type--(\w+)"'
    for m in list(re.finditer(pat, r.text))[1:3]:
        seg = r.text[m.end() : m.end() + 1500]
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg))
        print(f"    sample: {m.group(1)} {m.group(2)}: {text[:300].strip()}")


def vnbdigital() -> None:
    head("VNBdigital (joint DSO platform, section 14e EnWG)")
    get("https://www.vnbdigital.de/")
    q = "{ vnb_serviceTypes { _id name type } }"
    try:
        r = c.post(VNB, json={"query": q})
        print(f"  POST {VNB} serviceTypes: HTTP {r.status_code}")
        types = r.json()["data"]["vnb_serviceTypes"]
        print(f"    {len(types)} services: {[(t['name'], t['type']) for t in types]}")
        q2 = (
            '{ vnb_coordinates(coordinates: "%s") { vnbs { _id name types voltageTypes '
            "services { type { type } activated } } } }"
        )
        for coord in ("7.0122,51.4556", "51.4556,7.0122"):
            r = c.post(VNB, json={"query": q2 % coord})
            vnbs = (r.json().get("data") or {}).get("vnb_coordinates") or {}
            found = json.dumps(vnbs.get("vnbs"), ensure_ascii=False)[:400]
            print(f"    operators at {coord} (Essen): {found}")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as err:
        print(f"    {err.__class__.__name__}: {err}")


def blocked() -> None:
    head("TenneT DE and E.ON group DSOs (Cloudflare challenge expected)")
    for name, url in BLOCKED.items():
        print(f"  {name}")
        get(url)


def netze_bw() -> None:
    head("Netze BW")
    for url in NETZE_BW:
        r = get(url)
        if r is not None and r.status_code == 200:
            hits = sorted(set(re.findall(r'https?://[^"\' ]+\.(?:pdf|xlsx|csv|json)', r.text)))
            print(f"    files linked: {hits[:6]}")


def saarland() -> None:
    head("Saarland DSOs (geoportal, Kapazitäten der Umspannanlagen)")
    r = get(SAAR_ARTICLE)
    if r is not None and r.status_code == 200:
        apps = sorted(set(re.findall(r'https?://[^"\s]+WMC=\d+', r.text.replace("&amp;", "&"))))
        print(f"    viewer: {apps}; figures per site are a linked graphic (Trafoleistung, Bestand,")
        print("    Geplant, Verfügbar, Anfragen), no table")


if __name__ == "__main__":
    fifty_hertz()
    amprion()
    transnetbw()
    vnbdigital()
    netze_bw()
    saarland()
    blocked()
