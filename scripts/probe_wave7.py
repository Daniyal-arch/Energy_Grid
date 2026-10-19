"""Probe wave 7 (brief 22): the candidate sources per dataset family, one step per family.

    python scripts/probe_wave7.py connect|units|live|congestion|prices|retail|emitters|offline|ev|gas|reliability

Each check fetches one page or endpoint and reports its HTTP status, type and size, and on HTML
pages the links that look like data (csv, xlsx, json, geojson, zip, ArcGIS or WFS services, APIs).
In Actions each family prints at most 10 `::notice` lines; the full lines go to the log.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urljoin

import httpx

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) InfraAtlas probe (github.com/Daniyal-arch/Energy_Grid)"
}
DATA_LINK = re.compile(
    r"""(?:href|src|url)\s*[=:]\s*["']([^"']+?(?:\.csv|\.xlsx?|\.json|\.geojson|\.zip|\.gpkg|\.ods)"""
    r"""(?:\?[^"']*)?|[^"']*(?:/arcgis/rest/services|/FeatureServer|/MapServer|service=WFS|/api/|/explore/v2|/ows\?)[^"']*)["']""",
    re.I,
)

# family -> [(cell, url, what to look for)]
CHECKS: dict[str, list[tuple[str, str, str]]] = {
    "connect": [
        (
            "FI",
            "https://karttapalaute.fingrid.fi/?setlanguage=en",
            "Fingrid Grid Scope map (resets from the session)",
        ),
        (
            "CY",
            "https://www.eac.com.cy/EN/RegulatedActivities/Distribution/renewableenergy/Pages/hosting-capacity.aspx",
            "EAC hosting capacity",
        ),
        (
            "RO",
            "https://www.transelectrica.ro/web/tel/racordare",
            "Transelectrica connection capacity map",
        ),
        (
            "GR",
            "https://www.admie.gr/en/grid/connection-to-the-system",
            "IPTO available capacity (403 from the session)",
        ),
        ("GR", "https://www.deddie.gr/en/", "HEDNO capacity margins"),
        (
            "HR",
            "https://www.hops.hr/informacije-o-mogucnosti-prikljucenja",
            "HOPS connection possibilities (PDF yearly)",
        ),
        (
            "DE",
            "https://www.tennet.eu/de/strommarkt/kunden-deutschland/netzanschlussanfragen",
            "TenneT DE (403 from the session)",
        ),
        (
            "LV",
            "https://www.ast.lv/lv/content/pieslegumi",
            "AST free capacity (403 from the session)",
        ),
        (
            "BE",
            "https://www.elia.be/en/customers/connection/grid-hosting-capacity",
            "Elia hosting capacity (wave 6, browser)",
        ),
        (
            "US",
            "https://www.nyiso.com/documents/20142/1407078/NYISO-Interconnection-Queue.xlsx",
            "NYISO queue file",
        ),
    ],
}


def check(cell: str, url: str, want: str) -> str:
    try:
        r = httpx.get(url, timeout=45, follow_redirects=True, headers=UA)
    except httpx.HTTPError as e:
        return f"{cell}: {type(e).__name__} {str(e)[:80]} ({url})"
    kind = r.headers.get("content-type", "").split(";")[0]
    line = f"{cell}: HTTP {r.status_code} {kind} {len(r.content):,} B"
    if "html" in kind and r.status_code == 200:
        links = sorted({urljoin(str(r.url), m) for m in DATA_LINK.findall(r.text)})[:6]
        line += f"; data links {len(links)}: " + " ".join(links) if links else "; no data links"
    elif r.status_code == 200:
        line += (
            f"; starts {r.text[:120]!r}"
            if "json" in kind or "csv" in kind or "text" in kind
            else ""
        )
    return f"{line} [{want}] ({url})"


def run(family: str) -> None:
    lines = [check(*c) for c in CHECKS[family]]
    ci = bool(os.environ.get("GITHUB_ACTIONS"))
    for i, line in enumerate(lines):
        print(f"::notice title={family}::{line}" if ci and i < 10 else line, flush=True)


if __name__ == "__main__":
    for fam in sys.argv[1:] or list(CHECKS):
        run(fam)
