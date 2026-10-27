"""Probe the US utilities' hosting-capacity services (brief 23) and the ISOs' headroom pages.

For every ArcGIS layer behind a utility's public hosting-capacity map: HTTP status, geometry,
feature count, last edit date, the fields, and two sample features (attributes only, no
geometry). Then the licence or terms each utility attaches (item licenceInfo on ArcGIS Online,
or the terms PDF the map links), and whether the ISO/RTO headroom pages answer a script.

  uv run --with pypdf python scripts/probe_connect_us.py
"""

from __future__ import annotations

import html
import io
import json
import re
from datetime import UTC, datetime

import httpx

ITEM = "https://www.arcgis.com/sharing/rest/content/items/{}"
PGE = "https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/DRPComplianceRelProd/FeatureServer"
SCE = "https://drpep.sce.com/arcgis_server/rest/services/Hosted"
SDGE = "https://services.arcgis.com/S0EUI1eVapjRPS5e/arcgis/rest/services"
CONED = "https://services.arcgis.com/ciPnsNFi1JLWVjva/arcgis/rest/services"
NGRID = "https://systemdataportal.nationalgrid.com/arcgis/rest/services"
XCEL = "https://services1.arcgis.com/eM84fwjsSggLQk61/arcgis/rest/services"
DOM = "https://services.arcgis.com/DmE6Z8jKWf8lv84J/arcgis/rest/services"
DUKE = "https://services3.arcgis.com/oX5r75R7mapdoI2F/arcgis/rest/services"

# (utility, layer URL, what it is)
LAYERS: list[tuple[str, str, str]] = [
    ("PG&E GRIP", f"{PGE}/0", "distribution substations"),
    ("PG&E GRIP", f"{PGE}/2", "feeders (existing/queued DG)"),
    ("PG&E GRIP", f"{PGE}/3", "line sections, ICA kW"),
    ("SCE DRPEP", f"{SCE}/ICA_Layer/FeatureServer/18", "substations, max remaining MW"),
    ("SCE DRPEP", f"{SCE}/ICA_Layer/FeatureServer/0", "circuit segments, ICA MW"),
    ("SCE DRPEP", f"{SCE}/ICA_Tables/FeatureServer/0", "extract date"),
    ("SDG&E ICA", f"{SDGE}/ICA_MAP_PROD_Substations_VW/FeatureServer/0", "substation polygons"),
    (
        "SDG&E ICA",
        f"{SDGE}/ICA_MAP_PROD_GenerationCapacityGrids_VW/FeatureServer/0",
        "ICA grid cells",
    ),
    ("ConEd", f"{CONED}/CECONY_NodalHCV_Prod/FeatureServer/0", "3-phase segments, HC MW"),
    ("ConEd", f"{CONED}/CECONY_NodalHCV_Prod/FeatureServer/2", "substation/bank data"),
    ("National Grid NY", f"{NGRID}/NYSDP/Hosting_Capacity_Data/MapServer/0", "feeders, PV HC MW"),
    (
        "National Grid NY",
        f"{NGRID}/NYSDP/Hosting_Capacity_Data/MapServer/1",
        "substation/bank data",
    ),
    ("National Grid NY", f"{NGRID}/NYSDP/Substations/MapServer/0", "substation points"),
    (
        "National Grid MA",
        f"{NGRID}/MASDP/Nodal_Hosting_Capacity_MA/MapServer/0",
        "feeders, PV HC MW",
    ),
    ("National Grid MA", f"{NGRID}/MASDP/Nodal_Hosting_Capacity_MA/MapServer/1", "substation data"),
    (
        "Xcel NSP (MN/ND/SD/WI)",
        f"{XCEL}/NSP_Blurred_Popup_Layer_October_2026/FeatureServer/0",
        "blurred cells, gen HC MW",
    ),
    (
        "Xcel PSCo (CO)",
        f"{XCEL}/PSCO_Blurred_Presentation_GEN_Popup_Layer_September_2026/FeatureServer/0",
        "blurred cells, gen HC MW",
    ),
    (
        "Dominion VA",
        f"{DOM}/Primary_Hosting_Capacity_Available_EB/FeatureServer/6",
        "utility-scale lines by MW class",
    ),
    (
        "Dominion VA",
        f"{DOM}/Residential_Hosting_Capacity_Available_EB/FeatureServer/10",
        "residential transformers",
    ),
    (
        "Duke Carolinas",
        f"{DUKE}/Generation_Map_Publishing/FeatureServer/0",
        "hexagons (the live map's layer)",
    ),
    (
        "Duke Carolinas",
        f"{DUKE}/Carolinas_Generation_August_2026/FeatureServer/0",
        "hexagons, newer release",
    ),
]

# ArcGIS Online items whose licenceInfo carries the utility's terms
ITEMS: dict[str, str] = {
    "PG&E GRIPRelProd": "8d22bd56a8a643d0b52f8510841572c5",
    "SCE ICA_Layer (ArcGIS Online copy)": "86644d27d5014731a20501c63492b03e",
    "SDG&E Substations view": "934d6439fb294af8b7b0eb26bd7f1022",
    "ConEd CECONY_SegmentedHCV_Prod": "ff93c5a5c68f438c97780124597e6018",
    "National Grid NY portal": "5925b8b2fd18444f83c1ff45ec47bafc",
    "Duke Generation Map Publishing": "ddca58dc84cb48b88a3d0ce5b1dc3d3c",
    "Duke DG Locational Guidance 2023": "e9dfa9f323f54bc1a13fbe25670a6880",
    "Dominion Utility Scale app": "d14fa0b4b50445038ab9a4a3dd8d6934",
}

# terms documents the maps link to, and the sentence that decides reuse
TERMS_PDFS: list[tuple[str, str, str]] = [
    (
        "National Grid MA",
        "https://systemdataportal.nationalgrid.com/MA/documents/MA_Terms_of_Use.pdf",
        r"Any other use of the Portal Content[^.]*\.[^.]*\.",
    ),
    (
        "Dominion",
        "https://cdn-dominionenergy-prd-001.azureedge.net/-/media/content/about/energy-grid-transformation/"
        "hosting-capacity-tool/pdfs/hosting-capacity-disclaimer.pdf",
        r"Any disclosure, copying, publication or distribution[^.]*\.",
    ),
]

# pages that answer (or not) for the ISO headroom maps and for the gated utility maps
PAGES: list[tuple[str, str]] = [
    ("MISO PoI analysis (Order 2023 heatmap)", "https://giqueue.misoenergy.org/PoiAnalysis"),
    (
        "SPP Hosting Capacity Tool FAQ",
        "https://opsportal.spp.org/documents/studies/Hosting%20Capacity%20Tool%20FAQ.pdf",
    ),
    ("PG&E GRIP portal", "https://grip.pge.com/"),
    ("SDG&E ICA map", "https://interconnectionmapsdge.extweb.sempra.com/"),
]


def text(v: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", v or ""))).strip()


def day(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).date().isoformat() if ms else "-"


def get_json(c: httpx.Client, url: str, **params: str | int) -> tuple[int, dict]:
    try:
        r = c.get(url, params={"f": "json", **params})
    except httpx.HTTPError as e:
        return 0, {"error": str(e)}
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"error": f"not JSON: {r.text[:120]!r}"}


def probe_layer(c: httpx.Client, utility: str, url: str, what: str) -> None:
    print(f"\n== {utility}: {what}\n   {url}")
    status, meta = get_json(c, url)
    if "error" in meta:
        print(f"   HTTP {status} error: {meta['error']}")
        return
    edit = (meta.get("editingInfo") or {}).get("lastEditDate")
    _, cnt = get_json(c, f"{url}/query", where="1=1", returnCountOnly="true")
    print(
        f"   HTTP {status} | {meta.get('name')} | {meta.get('geometryType')} | count {cnt.get('count')}"
        f" | last edit {day(edit)} | maxRecordCount {meta.get('maxRecordCount')}"
    )
    fields = [
        f["name"] if f["name"] == f.get("alias") else f"{f['name']} ({f['alias']})"
        for f in meta["fields"]
    ]
    print(f"   fields: {', '.join(fields)}")
    _, q = get_json(
        c, f"{url}/query", where="1=1", outFields="*", returnGeometry="false", resultRecordCount=2
    )
    for feat in q.get("features", []):
        print(f"   sample: {json.dumps(feat['attributes'], ensure_ascii=False)[:900]}")
    if "error" in q:
        print(f"   sample error: {q['error']}")


def probe_items(c: httpx.Client) -> None:
    print("\n\n#### Licence / terms on ArcGIS Online items")
    for label, item in ITEMS.items():
        _, d = get_json(c, ITEM.format(item))
        if "error" in d:
            print(f"\n{label} ({item}): {d['error']}")
            continue
        print(
            f"\n{label} ({item}) owner {d.get('owner')} | access {d.get('access')} | modified {day(d.get('modified'))}"
        )
        print(f"   licenceInfo: {text(d.get('licenseInfo'))[:500] or '(empty)'}")
        print(f"   accessInformation: {text(d.get('accessInformation')) or '(empty)'}")


def probe_terms(c: httpx.Client) -> None:
    print("\n\n#### Terms documents the maps link")
    try:
        import pypdf  # only this section needs it (uv run --with pypdf)
    except ImportError:
        print("   pypdf not installed: run with `uv run --with pypdf` to read the terms PDFs")
        return
    for label, url, pattern in TERMS_PDFS:
        r = c.get(url)
        print(
            f"\n{label}: HTTP {r.status_code} {r.headers.get('content-type')} {len(r.content)} bytes"
        )
        if r.status_code != 200:
            continue
        body = " ".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(r.content)).pages)
        hit = re.search(pattern, re.sub(r"\s+", " ", body))
        print(f"   {hit.group(0) if hit else '(sentence not found)'}")


def probe_pages(c: httpx.Client) -> None:
    print("\n\n#### Pages (ISO headroom maps, gated utility maps)")
    for label, url in PAGES:
        try:
            r = c.get(url)
        except httpx.HTTPError as e:
            print(f"{label}: {e}")
            continue
        body = r.text if "text" in (r.headers.get("content-type") or "") else ""
        login = sorted({m.lower() for m in re.findall(r"(?i)sign in|log ?in|register|CEII", body)})
        print(
            f"{label}: HTTP {r.status_code} {r.headers.get('content-type')} {len(r.content)} bytes"
            f" -> {r.url} | login words: {login or '-'}"
        )


def main() -> None:
    c = httpx.Client(
        timeout=90, follow_redirects=True, headers={"User-Agent": "InfraAtlas probe (research)"}
    )
    print("#### Utility hosting-capacity layers")
    for utility, url, what in LAYERS:
        probe_layer(c, utility, url, what)
    probe_items(c)
    probe_terms(c)
    probe_pages(c)


if __name__ == "__main__":
    main()
