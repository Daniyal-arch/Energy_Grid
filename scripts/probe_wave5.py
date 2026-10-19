"""Probe the 22 sources of brief 17 (docs/tasks/17-datasets-wave5.md) before building.

One function per dataset; each prints at most 10 lines (status, size, rows, fields, licence
text found, a sample) as GitHub `::notice` annotations, so the run is read from its annotations
(.github/workflows/probe-wave5.yml, one step per group).

    python scripts/probe_wave5.py A1     # group A1: NUTS and bidding zones
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys
import zipfile
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

UA = {"User-Agent": "Europe-InfraAtlas/0.3 (probe; github.com/Daniyal-arch/Energy_Grid)"}
CLIENT = httpx.Client(headers=UA, timeout=90, follow_redirects=True)


def note(ds: str, text: str) -> None:
    print(f"::notice title={ds}::{text[:900]}".replace("\n", " "), flush=True)


def size_of(url: str) -> str:
    """Status and content-length of a URL without downloading it."""
    try:
        with CLIENT.stream("GET", url) as r:
            n = int(r.headers.get("content-length") or 0)
            return f"HTTP {r.status_code}, {n / 1e6:.1f} MB, {r.headers.get('content-type', '')}"
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {e}"


def links(url: str, pattern: str, limit: int = 6) -> list[str]:
    """Hrefs on a page matching a pattern (case-insensitive)."""
    r = CLIENT.get(url)
    found = re.findall(r'href="([^"]+)"', r.text)
    hits = [h for h in found if re.search(pattern, h, re.I)]
    return list(dict.fromkeys(hits))[:limit]


def gh_licence(repo: str) -> str:
    r = CLIENT.get(f"https://api.github.com/repos/{repo}/license")
    if r.status_code != 200:
        return f"licence: HTTP {r.status_code}"
    return f"licence: {r.json()['license']['spdx_id']}"


# A. Shapes and names


def nuts() -> None:
    url = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326.geojson"
    r = CLIENT.get(url)
    d = r.json()
    feats = d["features"]
    note("nuts", f"HTTP {r.status_code}, {len(r.content) / 1e6:.1f} MB, {len(feats)} features")
    note(
        "nuts",
        f"levels {dict(sorted(Counter(f['properties']['LEVL_CODE'] for f in feats).items()))}",
    )
    note("nuts", f"fields {list(feats[0]['properties'])}")
    note("nuts", f"sample {feats[0]['properties']}")


def zones() -> None:
    for repo, path in (
        ("EnergieID/entsoe-py", "entsoe/geo/geojson"),
        ("electricitymaps/electricitymaps-contrib", "geo"),
    ):
        r = CLIENT.get(f"https://api.github.com/repos/{repo}/contents/{path}")
        names = [i["name"] for i in r.json()] if r.status_code == 200 else []
        note(
            "zones",
            f"{repo}/{path}: HTTP {r.status_code}, {len(names)} files {names[:8]}; {gh_licence(repo)}",
        )
    r = CLIENT.get(
        "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/master/geo/README.md"
    )
    note("zones", f"electricitymaps geo README: HTTP {r.status_code} {r.text[:300]}")
    r = CLIENT.get(
        "https://raw.githubusercontent.com/EnergieID/entsoe-py/master/entsoe/geo/geojson/NO_1.geojson"
    )
    note("zones", f"entsoe-py NO_1: HTTP {r.status_code}, {len(r.content)} bytes {r.text[:150]}")


def cgaz() -> None:
    url = "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM1.geojson"
    note("cgaz", f"{url}: {size_of(url)}")
    note(
        "cgaz",
        gh_licence("wmgeolab/geoBoundaries") + " (data: CGAZ is CC BY 4.0 per geoboundaries.org)",
    )


def geonames() -> None:
    url = "https://download.geonames.org/export/dump/cities15000.zip"
    r = CLIENT.get(url)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read("cities15000.txt").decode()
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    note(
        "geonames",
        f"HTTP {r.status_code}, {len(r.content) / 1e6:.1f} MB zip, {len(rows)} rows, {len(rows[0])} columns",
    )
    note("geonames", f"sample {rows[0][:2] + rows[0][4:6] + rows[0][8:11] + rows[0][14:15]}")
    note("geonames", f">=100k people: {sum(int(x[14] or 0) >= 100_000 for x in rows)}")
    readme = CLIENT.get("https://download.geonames.org/export/dump/readme.txt").text
    m = re.search(r"[^\n]*Creative Commons[^\n]*", readme)
    note("geonames", f"licence text: {m.group(0) if m else 'not found'}")


# B. United States


PUDL = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable"


def pudl() -> None:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs")
    for table in (
        "out_eia__yearly_plants",
        "out_eia__yearly_generators",
        "core_eia923__monthly_generation_fuel",
    ):
        url = f"{PUDL}/{table}.parquet"
        try:
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{url}'").fetchall()]
            n = con.execute(f"SELECT count(*), max(report_date) FROM '{url}'").fetchone()
            note(
                "eia923",
                f"{table}: {n[0]:,} rows, newest {n[1]}; {len(cols)} cols {[c for c in cols if re.search('gen|capac|factor|plant_id|date|mw', c)][:14]}",
            )
        except duckdb.Error as e:
            note("eia923", f"{table}: {str(e)[:200]}")


def egrid() -> None:
    hits = links("https://www.epa.gov/egrid/download-data", r"\.xlsx|\.zip")
    note("egrid", f"download links {hits}")
    for h in hits[:2]:
        u = h if h.startswith("http") else "https://www.epa.gov" + h
        note("egrid", f"{u}: {size_of(u)}")


def ghgrp() -> None:
    hits = links("https://www.epa.gov/ghgreporting/data-sets", r"ghgp_data|\.zip|\.xlsx")
    note("ghgrp", f"download links {hits}")
    for h in hits[:2]:
        u = h if h.startswith("http") else "https://www.epa.gov" + h
        note("ghgrp", f"{u}: {size_of(u)}")
    r = CLIENT.get("https://data.epa.gov/efservice/PUB_DIM_FACILITY/ROWS/0:2/JSON")
    note("ghgrp", f"Envirofacts PUB_DIM_FACILITY: HTTP {r.status_code} {r.text[:300]}")


# C. Germany


def netztransparenz() -> None:
    for u in (
        "https://www.netztransparenz.de/de-de/Systemdienstleistungen/Betriebsf%C3%BChrung/Redispatch",
        "https://www.netztransparenz.de/de-de/Systemdienstleistungen/Betriebsf%C3%BChrung/Redispatch/Redispatch-Zahlen",
    ):
        r = CLIENT.get(u)
        files = re.findall(r'href="([^"]+\.(?:csv|xlsx|zip))"', r.text, re.I)
        note("netztransparenz", f"{u[-40:]}: HTTP {r.status_code}, files {files[:5]}")
    r = CLIENT.get(
        "https://ds.netztransparenz.de/api/v1/data/redispatch/2024-01-01T00:00:00/2024-01-02T00:00:00"
    )
    note("netztransparenz", f"API without token: HTTP {r.status_code} {r.text[:150]}")
    r = CLIENT.get("https://api-portal.netztransparenz.de/")
    note(
        "netztransparenz",
        f"API portal: HTTP {r.status_code} {'registr' in r.text.lower()} (registration mentioned)",
    )


def smard() -> None:
    r = CLIENT.get("https://www.smard.de/app/chart_data/410/DE/index_hour.json")
    ts = r.json()["timestamps"]
    note(
        "smard",
        f"index 410 (load) DE hour: HTTP {r.status_code}, {len(ts)} weekly files, newest {datetime.fromtimestamp(ts[-1] / 1000, UTC)}",
    )
    r = CLIENT.get(f"https://www.smard.de/app/chart_data/410/DE/410_DE_hour_{ts[-1]}.json")
    s = [p for p in r.json()["series"] if p[1] is not None]
    note(
        "smard", f"newest file: HTTP {r.status_code}, {len(s)} values, last {s[-1] if s else None}"
    )


# D. Planned grid, outages


def tyndp() -> None:
    for u in (
        "https://tyndp2024.entsoe.eu/",
        "https://tyndp2024.entsoe.eu/projects-map",
        "https://tyndp2024.entsoe.eu/resources",
    ):
        try:
            hits = links(u, r"xlsx|csv|geojson|kml|zip|api", 8)
            note("tyndp", f"{u}: {hits}")
        except httpx.HTTPError as e:
            note("tyndp", f"{u}: {type(e).__name__}")


def a78() -> None:
    key = os.environ.get("ENTSOE_API_KEY", "").strip()
    if not key:
        note("a78", "no ENTSOE_API_KEY")
        return
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    for btype in ("A53", "A54"):  # planned, forced
        q = {
            "securityToken": key, "documentType": "A78", "BusinessType": btype,
            "In_Domain": "10Y1001A1001A83F", "Out_Domain": "10Y1001A1001A83F",
            "periodStart": (now - timedelta(days=30)).strftime("%Y%m%d%H00"),
            "periodEnd": (now + timedelta(days=30)).strftime("%Y%m%d%H00"),
        }  # fmt: skip
        r = CLIENT.get("https://web-api.tp.entsoe.eu/api", params=q)
        kind = "zip" if r.content[:2] == b"PK" else "xml"
        msg = f"DE {btype}: HTTP {r.status_code}, {len(r.content) / 1e3:.0f} kB {kind}"
        if kind == "zip":
            z = zipfile.ZipFile(io.BytesIO(r.content))
            first = z.read(z.namelist()[0]).decode()
            tags = sorted(set(re.findall(r"<([A-Za-z_.]+)>", first)))
            msg += f", {len(z.namelist())} docs; tags {tags[:40]}"
        else:
            msg += " " + r.text[:300]
        note("a78", msg)


# E. Global Renewables Watch


def grw() -> None:
    repo = "microsoft/global-renewables-watch"
    r = CLIENT.get(f"https://api.github.com/repos/{repo}/releases")
    note("grw", f"releases: HTTP {r.status_code}; {gh_licence(repo)}")
    if r.status_code == 200:
        for rel in r.json()[:3]:
            assets = [(a["name"], round(a["size"] / 1e6)) for a in rel["assets"]]
            note("grw", f"{rel['tag_name']} {rel['published_at'][:10]}: {assets[:8]}")
    r = CLIENT.get(f"https://raw.githubusercontent.com/{repo}/main/README.md")
    m = re.findall(r"[^\n]*(?:licen[sc]e|CC[- ]BY|ODbL|CDLA)[^\n]*", r.text, re.I)
    note("grw", f"README licence lines: {m[:3]}")


# F. Profiles


def eurostat() -> None:
    u = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_bal_c?geo=DE&unit=KTOE&nrg_bal=FC_E&siec=TOTAL&lastTimePeriod=2"
    r = CLIENT.get(u)
    d = r.json()
    note(
        "eurostat",
        f"nrg_bal_c DE FC_E: HTTP {r.status_code}, values {d.get('value')}, time {list(d['dimension']['time']['category']['index'])}",
    )
    u = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_bal_c?geo=DE&unit=KTOE&siec=TOTAL&lastTimePeriod=1&nrg_bal=FC_IND_E&nrg_bal=FC_TRA_E&nrg_bal=FC_OTH_HH_E&nrg_bal=FC_OTH_CP_E"
    r = CLIENT.get(u)
    note("eurostat", f"by sector: HTTP {r.status_code}, {r.json().get('value')}")
    note("eurostat", f"licence: {r.json().get('extension', {}).get('annotation', [{}])[:1]}")


def eia(route: str, params: dict[str, str]) -> httpx.Response:
    key = os.environ.get("EIA_API_KEY", "").strip()
    return CLIENT.get(f"https://api.eia.gov/v2/{route}", params={"api_key": key, **params})


def seds() -> None:
    r = eia(
        "seds/data/",
        {
            "frequency": "annual",
            "data[0]": "value",
            "facets[stateId][]": "TX",
            "facets[seriesId][]": "TETCB",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "2",
        },
    )
    note("seds", f"TX TETCB: HTTP {r.status_code} {r.text[:400]}")
    r = eia("seds/", {})
    note("seds", f"route meta: HTTP {r.status_code} {r.text[:300]}")


def steo() -> None:
    r = eia(
        "steo/data/",
        {
            "frequency": "monthly",
            "data[0]": "value",
            "facets[seriesId][]": "ESRCUUS",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "3",
        },
    )
    note("steo", f"ESRCUUS (residential price): HTTP {r.status_code} {r.text[:400]}")
    r = eia(
        "steo/data/",
        {
            "frequency": "monthly",
            "data[0]": "value",
            "facets[seriesId][]": "EPEOPUS",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "3",
        },
    )
    note("steo", f"EPEOPUS (generation): HTTP {r.status_code} {r.text[:400]}")


def ei_review() -> None:
    u = "https://www.energyinst.org/statistical-review/resources-and-data-downloads"
    try:
        hits = links(u, r"\.csv|\.xlsx|Consolidated", 8)
        note("ei_review", f"{u}: {hits}")
        for h in hits:
            if "onsolidated" in h and h.endswith(".csv"):
                full = h if h.startswith("http") else "https://www.energyinst.org" + h
                note("ei_review", f"{full}: {size_of(full)}")
                break
    except httpx.HTTPError as e:
        note("ei_review", f"{u}: {type(e).__name__}")


def edgar() -> None:
    for u in (
        "https://edgar.jrc.ec.europa.eu/report_2025",
        "https://edgar.jrc.ec.europa.eu/dataset_ghg2025",
    ):
        try:
            hits = links(u, r"\.xlsx|\.zip|\.csv", 8)
            note("edgar", f"{u}: HTTP ok, {hits}")
        except httpx.HTTPError as e:
            note("edgar", f"{u}: {type(e).__name__}")


# G. Live markets


def jepx() -> None:
    year = datetime.now(UTC).year
    u = f"https://www.jepx.jp/js/csv_read.php?dir=spot_summary&file=spot_summary_{year}.csv"
    r = CLIENT.get(u, headers={"Referer": "https://www.jepx.jp/electricpower/market-data/spot/"})
    text = r.content.decode("shift_jis", errors="replace")
    lines = text.splitlines()
    note(
        "jepx",
        f"{u}: HTTP {r.status_code}, {len(lines)} lines; header {lines[0][:200] if lines else ''}",
    )
    note("jepx", f"last {lines[-1][:200] if lines else ''}")
    r = CLIENT.get("https://www.jepx.jp/sitepolicy/")
    m = re.findall(r"[^<>]{0,80}(?:転載|二次利用|著作権)[^<>]{0,120}", r.text)
    note("jepx", f"site policy HTTP {r.status_code}: {m[:3]}")


def cenace() -> None:
    d = datetime.now(UTC) - timedelta(days=1)
    ymd = f"{d.year}/{d.month:02d}/{d.day:02d}"
    u = f"https://ws01.cenace.gob.mx:8082/SWPML/SIM/SIN/MDA/01PLO-115/{ymd}/{ymd}/JSON"
    try:
        r = CLIENT.get(u)
        note("cenace", f"{u}: HTTP {r.status_code} {r.text[:400]}")
    except httpx.HTTPError as e:
        note("cenace", f"{u}: {type(e).__name__}: {e}")
    try:
        hits = links(
            "https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreciosEnergiaSisMEM.aspx",
            r"\.csv|\.zip|Nodos",
            6,
        )
        note("cenace", f"report page links {hits}")
    except httpx.HTTPError as e:
        note("cenace", f"report page: {type(e).__name__}")


def grid_india() -> None:
    for u in (
        "https://grid-india.in/en/reports/daily-psp-report",
        "https://webapi.grid-india.in/api/v1/file",
    ):
        try:
            r = CLIENT.get(u)
            files = re.findall(
                r'(?:href|"FilePath")[=:]\s*"([^"]+\.(?:pdf|xls|xlsx|csv|json))"', r.text, re.I
            )
            note(
                "grid_india",
                f"{u}: HTTP {r.status_code}, {len(r.content)} bytes, files {files[:5]}",
            )
        except httpx.HTTPError as e:
            note("grid_india", f"{u}: {type(e).__name__}")
    try:
        r = CLIENT.post(
            "https://webapi.grid-india.in/api/v1/file",
            json={
                "_source": "GRDW",
                "_type": "DAILY_PSP_REPORT",
                "_fileDate": "2026-27",
                "_month": "10",
            },
        )
        note("grid_india", f"file API POST: HTTP {r.status_code} {r.text[:400]}")
    except httpx.HTTPError as e:
        note("grid_india", f"file API: {type(e).__name__}")


# H. People and lights


def ghsl() -> None:
    u = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_30ss/V1-0/GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.zip"
    note("ghsl", f"{u.rsplit('/', 1)[1]}: {size_of(u)}")


def black_marble() -> None:
    u = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP46A3/2025/001.json"
    r = CLIENT.get(u)
    note("black_marble", f"listing: HTTP {r.status_code} {r.text[:200]}")
    try:
        name = r.json()["content"][0]["name"]
        f = CLIENT.get(
            f"https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP46A3/2025/001/{name}"
        )
        note(
            "black_marble",
            f"file without token: HTTP {f.status_code} {f.headers.get('content-type')} {f.text[:120]}",
        )
    except (ValueError, KeyError, IndexError) as e:
        note("black_marble", f"no file listed ({type(e).__name__})")


GROUPS: dict[str, list[Callable[[], None]]] = {
    "A1": [nuts, zones],
    "A2": [cgaz, geonames],
    "B": [pudl, egrid, ghgrp],
    "C": [netztransparenz, smard],
    "D": [tyndp, a78],
    "E": [grw],
    "F1": [eurostat, seds, steo],
    "F2": [ei_review, edgar],
    "G": [jepx, cenace, grid_india],
    "H": [ghsl, black_marble],
}


def main() -> None:
    for fn in GROUPS[sys.argv[1]]:
        try:
            fn()
        except Exception as e:  # a probe reports, never stops the others
            note(fn.__name__, f"failed: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
