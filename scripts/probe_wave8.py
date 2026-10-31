"""Probes for data wave 8 (docs/tasks/27, B3 and B4): licence text as found, size, a few rows.

    python scripts/probe_wave8.py eia|eea|dams|co2stop|hotmaps|effis|firms|nifc|nsta|ukprtr|tri|
                                 natcarb|classvi|eaflood|nwi|nfhl|hrl|co2stored|com|slope|nl_dso|
                                 gem_own|all

Each probe prints one short block: what was asked, the HTTP answer, sizes and counts, and the
licence or terms line it found (quoted). Nothing is written.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections.abc import Callable

import httpx

UA = {"User-Agent": "InfraAtlas data probe (github.com/Daniyal-arch/Energy_Grid)"}
PROBES: dict[str, Callable[[], None]] = {}


def probe(fn: Callable[[], None]) -> Callable[[], None]:
    PROBES[fn.__name__] = fn
    return fn


def get(url: str, **kw: object) -> httpx.Response:
    return httpx.get(url, headers=UA, timeout=120, follow_redirects=True, **kw)  # type: ignore[arg-type]


def head(url: str) -> str:
    try:
        r = httpx.head(url, headers=UA, timeout=60, follow_redirects=True)
        size = r.headers.get("content-length")
        return (
            f"HTTP {r.status_code}, {int(size) / 1e6:,.1f} MB" if size else f"HTTP {r.status_code}"
        )
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {e}"


def text_of(url: str, words: list[str], width: int = 260) -> list[str]:
    """Sentences of a page around the words (licence, terms, commercial ...)."""
    try:
        r = get(url)
    except httpx.HTTPError as e:
        return [f"{type(e).__name__}: {e}"]
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    out = [f"HTTP {r.status_code} {url}"]
    for wd in words:
        for m in list(re.finditer(wd, t, re.I))[:2]:
            out.append(
                "… " + t[max(0, m.start() - width // 2) : m.end() + width // 2].strip() + " …"
            )
    return out


def arcgis_count(layer: str) -> str:
    try:
        r = get(f"{layer}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"})
        return str(r.json().get("count", r.text[:120]))
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        return f"{type(e).__name__}"


def arcgis_find(org: str, words: list[str]) -> list[str]:
    try:
        d = get(f"{org}?f=json").json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        return [f"{type(e).__name__}"]
    return [
        s["name"]
        for s in d.get("services", [])
        if any(w.lower() in s["name"].lower() for w in words)
    ]


def show(title: str, *lines: object) -> None:
    print(f"\n### {title}")
    for ln in lines:
        print(f"- {ln}")


@probe
def eia() -> None:
    """EIA's U.S. Energy Atlas layers on ArcGIS Online (EIA's own organisation)."""
    q = "owner:EIA_GIS OR owner:EIAGIS OR owner:eia_gis"
    r = get(
        "https://www.arcgis.com/sharing/rest/search",
        params={"q": f'({q}) AND type:"Feature Service"', "num": 100, "f": "json"},
    )
    items = r.json().get("results", []) if r.status_code == 200 else []
    keep = [
        i
        for i in items
        if re.search(
            r"refin|processing|storage|terminal|ethanol|biodiesel|hgl|liquids|crude|products|lng",
            i["title"],
            re.I,
        )
    ]
    show(
        "EIA midstream layers (ArcGIS Online search)",
        f"{len(items)} EIA feature services found; {len(keep)} midstream",
    )
    for i in keep[:20]:
        url = i.get("url") or ""
        show(
            i["title"],
            url,
            f"features: {arcgis_count(url + '/0') if url else '?'}",
            f"licence: {(i.get('licenseInfo') or 'public domain (EIA)')[:160]}",
        )


@probe
def eea() -> None:
    """EEA Industrial Reporting database (E-PRTR, LCP, EU Registry)."""
    for ln in text_of(
        "https://www.eea.europa.eu/en/datahub/datahubitem-view/9405f714-8015-4b5b-a63c-280b82861b3d",
        ["licen", "re-use", "reuse", "commercial", "Creative Commons"],
    ):
        print(ln)
    for ln in text_of(
        "https://www.eea.europa.eu/en/legal-notice",
        ["commercial", "re-use", "reuse", "Creative Commons"],
    ):
        print(ln)


@probe
def dams() -> None:
    r = get(
        "https://api.figshare.com/v2/articles/search", params={"search_for": "Global Dam Watch"}
    )
    for a in r.json()[:5]:
        d = get(f"https://api.figshare.com/v2/articles/{a['id']}").json()
        show(
            d["title"][:90],
            f"licence: {d.get('license', {}).get('name')}",
            *[
                f"{f['name']}: {f['size'] / 1e6:,.1f} MB {f['download_url']}"
                for f in d.get("files", [])[:6]
            ],
        )


@probe
def co2stop() -> None:
    for ln in text_of(
        "https://data.jrc.ec.europa.eu/dataset/jrc-co2stop",
        ["licen", "re-use", "reuse", "acknowledg", "download", ".zip", ".csv", ".kml"],
    ):
        print(ln)


@probe
def hotmaps() -> None:
    for repo in (
        "HotMaps%2Fheat%2Fheat_tot_curr_density",
        "HotMaps%2Findustrial_sites%2Findustrial_sites_Industrial_Database",
    ):
        r = get(f"https://gitlab.com/api/v4/projects/{repo}")
        d = r.json() if r.status_code == 200 else {}
        lic = get(
            f"https://gitlab.com/api/v4/projects/{repo}/repository/files/README.md/raw?ref=master"
        )
        lines = [
            ln
            for ln in lic.text.splitlines()
            if re.search(r"licen|CC-BY|Creative|copyright", ln, re.I)
        ][:4]
        tree = get(
            f"https://gitlab.com/api/v4/projects/{repo}/repository/tree?recursive=true&per_page=100"
        ).json()
        files = (
            [t["path"] for t in tree if isinstance(t, dict) and t.get("type") == "blob"][:12]
            if isinstance(tree, list)
            else []
        )
        show(f"Hotmaps {repo}", f"HTTP {r.status_code}: {d.get('name')}", *lines, f"files: {files}")


@probe
def effis() -> None:
    for ln in text_of(
        "https://forest-fire.emergency.copernicus.eu/applications/data-and-services",
        ["licen", "commercial", "terms", "conditions", "burnt area", "download"],
    ):
        print(ln)
    for ln in text_of(
        "https://forest-fire.emergency.copernicus.eu/about-effis/data-license",
        ["licen", "commercial", "terms", "attribution"],
    ):
        print(ln)


@probe
def firms() -> None:
    import os

    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        show(
            "NASA FIRMS",
            "FIRMS_MAP_KEY is not set: the live fire layer is skipped (free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/)",
        )
        return
    r = get(
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/-32,27,45,72/1"
    )
    show(
        "NASA FIRMS VIIRS SNPP NRT, Europe, last 24 h",
        f"HTTP {r.status_code}, {max(0, len(r.text.splitlines()) - 1)} detections",
    )


@probe
def nifc() -> None:
    layer = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0"
    show("NIFC WFIGS current perimeters", layer, f"features: {arcgis_count(layer)}")


@probe
def nsta() -> None:
    org = "https://services-eu1.arcgis.com/3DqPNVTlNH6M4pNB/arcgis/rest/services"
    show(
        "NSTA open data (ArcGIS)",
        org,
        f"services: {arcgis_find(org, ['pipeline', 'wells', 'surface', 'carbon', 'storage', 'licence'])[:20]}",
    )
    for ln in text_of(
        "https://opendata-nstauthority.hub.arcgis.com/", ["Open Government", "licen"]
    ):
        print(ln)


@probe
def ukprtr() -> None:
    for ln in text_of(
        "https://www.data.gov.uk/dataset/cfd94301-a2f2-48a2-9915-e477ca6d8b7e/pollutant-release-and-transfer-register",
        ["licen", "Open Government", ".csv", "download"],
    ):
        print(ln)


@probe
def tri() -> None:
    url = "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/2023_US/csv"
    show("EPA TRI basic data file 2023", url, head(url), "licence: public domain (US EPA)")


@probe
def natcarb() -> None:
    for ln in text_of(
        "https://edx.netl.doe.gov/dataset/natcarb-sink", ["licen", "public", ".zip", "download"]
    ):
        print(ln)


@probe
def classvi() -> None:
    for ln in text_of(
        "https://www.epa.gov/uic/table-epas-class-vi-permit-tracker",
        ["permit", "Class VI", "operat"],
    ):
        print(ln)


@probe
def eaflood() -> None:
    for ln in text_of(
        "https://www.data.gov.uk/dataset/104434b0-5263-4c90-9b1e-e43b1d57c750/flood-map-for-planning-flood-zones1",
        ["licen", "Open Government", "download", "Shapefile", "GeoPackage"],
    ):
        print(ln)


@probe
def nwi() -> None:
    url = "https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads/CONUS_wetlands.zip"
    show("USFWS NWI CONUS", url, head(url), "licence: public domain (USFWS)")


@probe
def nfhl() -> None:
    layer = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    show(
        "FEMA NFHL flood hazard zones (layer 28)",
        layer,
        f"features: {arcgis_count(layer)}",
        "licence: public domain (FEMA)",
    )


@probe
def hrl() -> None:
    for ln in text_of(
        "https://land.copernicus.eu/en/products/high-resolution-layer-water-and-wetness",
        ["licen", "login", "EU Login", "register", "download", "free"],
    ):
        print(ln)


@probe
def co2stored() -> None:
    for ln in text_of(
        "https://www.co2stored.co.uk/",
        ["licen", "register", "terms", "commercial", "login", "subscription"],
    ):
        print(ln)


@probe
def com() -> None:
    for ln in text_of(
        "https://data.jrc.ec.europa.eu/dataset/57a615ff-4a1c-4e9b-9b8a-aa45c5d3a4b0",
        ["licen", "rights", "re-use", "download"],
    ):
        print(ln)
    r = get(
        "https://data.jrc.ec.europa.eu/api/3/action/package_search",
        params={"q": "covenant of mayors emission inventory", "rows": 5},
    )
    try:
        for p in r.json()["result"]["results"]:
            show(
                p["title"][:90],
                f"licence: {p.get('license_title')}",
                f"modified {p.get('metadata_modified', '')[:10]}",
                *[
                    f"{x.get('name', '')[:50]}: {x.get('url', '')[:110]}"
                    for x in p.get("resources", [])[:3]
                ],
            )
    except (ValueError, KeyError) as e:
        show("JRC data catalogue search", f"HTTP {r.status_code}: {type(e).__name__}")


@probe
def slope() -> None:
    for ln in text_of("https://maps.nrel.gov/slope", ["licen", "terms", "disclaimer", "download"]):
        print(ln)
    for ln in text_of("https://data.nrel.gov/submissions/?q=SLOPE", ["SLOPE", "licen"]):
        print(ln)


@probe
def nl_dso() -> None:
    for name, url in (
        ("Liander", "https://www.liander.nl/over-ons/open-data"),
        ("Enexis", "https://www.enexisgroep.nl/over-ons/open-data/"),
        ("Stedin", "https://www.stedin.net/zakelijk/open-data/verbruiksgegevens"),
    ):
        for ln in text_of(
            url, ["licen", "Creative Commons", "CC-BY", "kleinverbruik", "voorwaarden"]
        ):
            print(f"{name}: {ln}")


@probe
def gem_own() -> None:
    for ln in text_of(
        "https://globalenergymonitor.org/projects/global-energy-ownership-tracker/",
        ["licen", "CC BY", "Creative Commons", "download"],
    ):
        print(ln)


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in PROBES.items():
        if which in ("all", name):
            t0 = time.time()
            try:
                fn()
            except Exception as e:  # a probe that fails says so and the next one runs
                show(name, f"probe failed: {type(e).__name__}: {str(e)[:200]}")
            print(f"({name}: {time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
