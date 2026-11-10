"""Probe: ArcGIS Online items titled with each country's own planning terms.

The Hub sweep (zoning_discover.py --hub) searched the English word "zoning" only; this
lists Feature and Map Services whose titles use the local words, per country, in the
columns of hub_services.csv (region `local`); the term must be a whole word of the title and
the title free of the NOT words, for `build_zoning_hub.py --region local`.
Tiled (raster) services and items already in hub_services.csv are left out; the country of
each layer is set later from its first zone, not from the search term.

    uv run python scripts/probe_zoning_local.py > data/zoning_discovery/local_services.csv
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import httpx

HUB = Path(__file__).resolve().parents[1] / "data" / "zoning_discovery" / "hub_services.csv"
SEARCH = "https://www.arcgis.com/sharing/rest/search"
TERMS: dict[str, list[str]] = {
    "pl": [
        "MPZP",
        "miejscowy plan zagospodarowania",
        "studium uwarunkowan",
        "plany miejscowe",
        "plan ogólny",
    ],
    "cz": ["územní plán", "uzemni plan"],
    "pt": ["PDM ordenamento", "Plano Diretor Municipal", "classificacao do solo"],
    "it": ["PGT", "PRG zonizzazione", "piano regolatore", "piano urbanistico"],
    "fi": ["asemakaava", "yleiskaava"],
    "hr": ["prostorni plan", "GUP namjena"],
    "sk": ["uzemny plan", "územný plán"],
    "gr": ["ΓΠΣ", "χρήσεις γης", "ζώνες χρήσεων"],
    "hu": ["rendezési terv", "szabályozási terv", "településrendezési"],
    "ro": ["PUG", "plan urbanistic general"],
    "bg": ["ОУП", "устройствен план"],
    "lt": ["bendrasis planas", "teritorijų planavimas"],
    "si": ["občinski prostorski načrt", "namenska raba"],
    "se": ["detaljplan", "översiktsplan"],
    "gb_wales": ["Local Development Plan allocations", "LDP proposals"],
    "gb_ni": ["area plan zoning", "development plan zonings"],
    "cy": ["development plan zones Cyprus"],
    "mt": ["local plan Malta"],
}

# titles that use a plan word but hold something else: tests and drafts, programmes and
# reviews, surveys, forest and flood layers, base maps, other countries' namesakes
NOT = re.compile(
    r"test|draft|\bmap ?\d|web ?map|osm|forest|leso|flood|risk|opname|opnieuw|program|"
    r"katsaus|ohjelma|survey|monitor|bathymetr|watershed|hillshade|topo|turyst|geolog|"
    r"hipsometr|catasto|monument|sighting|\bua ?20\d\d|pobud|krčitv|analiz|feedback|"
    r"comment|consultation|active.?travel|rastr|raster|symbol|label",
    re.I,
)


def whole(term: str, title: str) -> bool:
    """The term as a whole word (letters or digits on neither side; `_` separates)."""
    return bool(re.search(rf"(?<![^\W_]){re.escape(term)}(?![^\W_])", title, re.I))


def main() -> None:
    w = csv.writer(sys.stdout)
    cols = ["region", "title", "owner", "source", "type", "url", "licence", "modified", "lon",
            "lat", "id", "term"]  # fmt: skip
    w.writerow(cols)
    known = {r["url"].rstrip("/") for r in csv.DictReader(HUB.open(encoding="utf-8"))}
    seen: set[str] = set()
    with httpx.Client(timeout=60) as c:
        for cc, terms in TERMS.items():
            n = 0
            for t in terms:
                q = f'title:"{t}" AND (type:"Feature Service" OR type:"Map Service")'
                for start in (1, 101):
                    d = c.get(SEARCH, params={"q": q, "num": 100, "start": start,
                                              "f": "json"}).json()  # fmt: skip
                    for r in d.get("results") or []:
                        url = (r.get("url") or "").rstrip("/")
                        title = r.get("title") or ""
                        if (r["id"] in seen or not url or "/tiles" in url or url in known
                                or not whole(t, title) or NOT.search(title)):  # fmt: skip
                            continue
                        seen.add(r["id"])
                        ext = r.get("extent") or [[None, None], [None, None]]
                        lon = (ext[0][0] + ext[1][0]) / 2 if ext and ext[0][0] is not None else ""
                        lat = (ext[0][1] + ext[1][1]) / 2 if ext and ext[0][1] is not None else ""
                        # Europe only (the same words name plans elsewhere; the US is in us_hub)
                        if lon == "" or not (-25 <= lon <= 45 and 34 <= lat <= 72):
                            continue
                        w.writerow(["local", r.get("title"), r.get("owner"), r.get("owner"),
                                    r.get("type"), url, (r.get("licenseInfo") or "")[:200],
                                    r.get("modified"), lon, lat, r["id"], f"{cc}:{t}"])  # fmt: skip
                        n += 1
                    if d.get("nextStart", -1) < 0:
                        break
            print(f"{cc}: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
