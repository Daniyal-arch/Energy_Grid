"""Find zoning and land-use plan datasets in the EU open-data portal (data.europa.eu).

data.europa.eu harvests the national open-data and INSPIRE catalogues of every member
state. Its search matches loosely across translations, so each hit is kept only when its
title in a publisher language contains the plan term of that country (case-insensitive),
and only when it offers a geodata distribution (WFS, WMS, GML, GeoJSON, shapefile,
GeoPackage, KML) or a PDF. Writes one row per dataset and a summary per country and
publisher, so the build step can pick sources with evidence.

    uv run python scripts/zoning_discover.py [--pages N] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

API = "https://data.europa.eu/api/hub/search/search"
UA = {"User-Agent": "Europe-InfraAtlas zoning discovery"}

# Plan terms per country, in the country's languages (the legal names of the plans).
TERMS: dict[str, list[str]] = {
    "at": ["Flächenwidmungsplan", "Bebauungsplan", "Widmung"],
    "be": ["plan de secteur", "gewestplan", "ruimtelijk uitvoeringsplan", "RUP", "plan communal"],
    "bg": ["подробен устройствен план", "общ устройствен план"],
    "cy": ["local plan", "development plan", "τοπικό σχέδιο"],
    "cz": ["územní plán", "územního plánu", "regulační plán"],
    "de": ["Bebauungsplan", "Flächennutzungsplan", "Bauleitplan", "XPlanung", "Windenergie"],
    "dk": ["lokalplan", "kommuneplan"],
    "ee": ["detailplaneering", "üldplaneering", "planeering"],
    "es": ["planeamiento", "clasificación del suelo", "calificación", "plan general"],
    "fi": ["asemakaava", "yleiskaava", "maakuntakaava"],
    "fr": ["plan local d'urbanisme", "PLU", "carte communale", "zonage", "zone-urba"],
    "gr": ["χρήσεις γης", "ρυμοτομικό", "πολεοδομικό"],
    "hr": ["prostorni plan", "urbanistički plan", "generalni urbanistički"],
    "hu": ["településrendezési", "szabályozási terv", "településszerkezeti"],
    "ie": ["zoning", "development plan", "local area plan"],
    "it": ["piano regolatore", "PRG", "PGT", "piano di governo", "zonizzazione", "PUC"],
    "lt": ["bendrasis planas", "detalusis planas", "teritorijų planavimo"],
    "lu": ["plan d'aménagement général", "PAG", "plan d'aménagement particulier", "PAP"],
    "lv": ["teritorijas plānojums", "funkcionālais zonējums", "lokālplānojums"],
    "mt": ["local plan", "development plan"],
    "nl": ["bestemmingsplan", "omgevingsplan", "ruimtelijke plannen", "structuurvisie"],
    "pl": ["miejscowy plan", "MPZP", "plan ogólny", "studium uwarunkowań"],
    "pt": ["plano diretor municipal", "PDM", "classificação do solo", "plano de pormenor"],
    "ro": ["plan urbanistic", "PUG", "PUZ"],
    "se": ["detaljplan", "översiktsplan"],
    "si": ["prostorski načrt", "OPN", "prostorski red", "namenska raba"],
    "sk": ["územný plán", "územného plánu"],
    "no": ["reguleringsplan", "kommuneplan", "arealplan"],
    "ch": ["Nutzungsplan", "Zonenplan", "plan d'affectation", "piano di utilizzazione"],
    "gb": ["local plan", "development plan", "green belt", "allocation", "zoning"],
}
GEO = {"WFS", "WMS", "GML", "GEOJSON", "SHP", "GPKG", "KML", "KMZ", "ZIP", "OGC API", "ATOM"}


def fmt(dist: dict[str, Any]) -> str:
    f = dist.get("format") or {}
    return str(f.get("id") or f.get("label") or "").upper()


def urls(dist: dict[str, Any]) -> list[str]:
    return [*(dist.get("download_url") or []), *(dist.get("access_url") or [])]


def title_has(d: dict[str, Any], term: str, langs: set[str]) -> str | None:
    titles = d.get("title") or {}
    # Search only the publisher's own languages, not machine translations.
    own = {k: v for k, v in titles.items() if k in langs} or titles
    # Whole words only: short codes such as "PDM" or "RUP" must not match inside words.
    pat = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.I)
    for v in own.values():
        if pat.search(str(v)):
            return str(v)
    return None


LANGS: dict[str, set[str]] = {
    "at": {"de"}, "be": {"fr", "nl", "de"}, "bg": {"bg"}, "cy": {"el", "en"}, "cz": {"cs"},
    "de": {"de"}, "dk": {"da"}, "ee": {"et"}, "es": {"es", "ca", "gl", "eu"}, "fi": {"fi", "sv"},
    "fr": {"fr"}, "gr": {"el"}, "hr": {"hr"}, "hu": {"hu"}, "ie": {"en", "ga"},
    "it": {"it", "de"}, "lt": {"lt"}, "lu": {"fr", "de", "lb"}, "lv": {"lv"},
    "mt": {"en", "mt"}, "nl": {"nl"}, "pl": {"pl"}, "pt": {"pt"}, "ro": {"ro"},
    "se": {"sv"}, "si": {"sl"}, "sk": {"sk"}, "no": {"no", "nb", "nn"},
    "ch": {"de", "fr", "it"}, "gb": {"en"},
}  # fmt: skip


def search(c: httpx.Client, q: str, country: str, page: int) -> dict[str, Any]:
    params = {
        "q": q,
        "filter": "dataset",
        "limit": 100,
        "page": page,
        "facets": json.dumps({"country": [country]}),
    }
    for attempt in range(4):
        try:
            r = c.get(API, params=params)
            r.raise_for_status()
            return r.json()["result"]
        except (httpx.HTTPError, KeyError):
            time.sleep(2**attempt)
    return {"count": 0, "results": []}


HUB = "https://hub.arcgis.com/api/search/v1/collections/dataset/items"
# Extents (lon/lat) for the ArcGIS Hub sweep: most US counties and cities, and many UK
# councils, publish zoning on ArcGIS Online rather than in a national catalogue.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "us": (-125.0, 24.0, -66.0, 50.0),
    "us_ak_hi": (-170.0, 18.0, -140.0, 72.0),
    "gb": (-8.7, 49.8, 1.9, 60.9),
    "eu": (-10.0, 35.0, 32.0, 71.0),
}
HUB_TERMS = re.compile(
    r"(?i)(?<!\w)(zoning|zone district|land use plan|future land use|local plan|green belt|"
    r"allocations?|development plan|overlay district|comprehensive plan)(?!\w)"
)


def hub(c: httpx.Client, out: Path, step: float, pages: int) -> None:
    """Sweep ArcGIS Hub in tiles of `step` degrees; keep zoning-titled services."""
    rows: dict[str, dict[str, Any]] = {}
    for region, (x0, y0, x1, y1) in REGIONS.items():
        x = x0
        while x < x1:
            y = y0
            while y < y1:
                box = f"{x},{y},{min(x + step, x1)},{min(y + step, y1)}"
                for page in range(pages):
                    params = {
                        "q": "zoning",
                        "bbox": box,
                        "limit": 100,
                        "startindex": 1 + page * 100,
                        "filter": "type IN ('Feature Service','Map Service')",
                    }
                    try:
                        feats = c.get(HUB, params=params).json().get("features") or []
                    except (httpx.HTTPError, ValueError):
                        feats = []
                    for f in feats:
                        p = f["properties"]
                        if not HUB_TERMS.search(str(p.get("title"))):
                            continue
                        ext = p.get("extent") or {}
                        ring = (ext.get("coordinates") or [[[None, None]]])[0]
                        rows[p["id"]] = {
                            "region": region,
                            "title": p.get("title"),
                            "owner": p.get("owner"),
                            "source": p.get("source"),
                            "type": p.get("type"),
                            "url": p.get("url"),
                            "licence": re.sub(r"<[^>]+>", " ", str(p.get("licenseInfo") or ""))[
                                :200
                            ].strip(),
                            "modified": p.get("modified"),
                            "lon": ring[0][0],
                            "lat": ring[0][1],
                            "id": p["id"],
                        }
                    if len(feats) < 100:
                        break
                y += step
            x += step
        print(f"hub {region}: {sum(r['region'] == region for r in rows.values()):,} services")
    out_rows = sorted(rows.values(), key=lambda r: (r["region"], str(r["owner"])))
    with (out / "hub_services.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)


# INSPIRE "Planned Land Use" datasets with a WFS (any country): read by build_zoning_hub.py
# --region wfs. The access URL without its query string is the service; one row per service.
WFS_TERMS = ['"planned land use"', '"geplante Bodennutzung"', "XPlanung"]


def wfs_sweep(c: httpx.Client, out: Path, pages: int) -> None:
    rows: dict[str, dict[str, Any]] = {}
    for term in WFS_TERMS:
        for page in range(pages):
            params = {"q": term, "filter": "dataset", "limit": 100, "page": page}
            try:
                r = c.get(API, params=params)
                r.raise_for_status()
                hits = r.json()["result"]["results"]
            except (httpx.HTTPError, KeyError):
                break
            if not hits:
                break
            for d in hits:
                title = d.get("title") or {}
                title = title.get("en") or next(iter(title.values()), "")
                for x in d.get("distributions") or []:
                    f = fmt(x).upper()
                    for u in x.get("access_url") or []:
                        low = u.lower()
                        if "WFS" in f or "service=wfs" in low or "_wfs" in low or "/wfs" in low:
                            base = u.split("?")[0]
                            rows.setdefault(base, {
                                "url": base, "title": title,
                                "source": (d.get("publisher") or {}).get("name", ""),
                                "licence": ((d.get("license") or {}).get("resource") or ""),
                                "country": (d.get("country") or {}).get("id", ""),
                                "id": d.get("id", ""),
                            })  # fmt: skip
        print(f"  {term}: {len(rows):,} services so far", flush=True)
    path = out / "wfs_services.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["url", "title", "source", "licence", "country", "id"])
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["country"], r["url"])))
    print(f"{len(rows):,} WFS services -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=20, help="pages of 100 per term and country")
    ap.add_argument("--out", type=Path, default=Path("data/zoning_discovery"))
    ap.add_argument("--countries", nargs="*", default=list(TERMS))
    ap.add_argument("--hub", action="store_true", help="sweep ArcGIS Hub instead")
    ap.add_argument("--wfs", action="store_true", help="INSPIRE planned land use WFS instead")
    ap.add_argument("--step", type=float, default=2.0, help="hub tile size in degrees")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.wfs:
        with httpx.Client(timeout=90, headers=UA) as c:
            wfs_sweep(c, a.out, a.pages)
        return
    if a.hub:
        with httpx.Client(timeout=90, headers=UA) as c:
            hub(c, a.out, a.step, a.pages)
        return
    rows: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=90, headers=UA) as c:
        for cc in a.countries:
            for term in TERMS[cc]:
                seen = kept = 0
                for page in range(a.pages):
                    res = search(c, f'"{term}"', cc, page)
                    hits = res.get("results") or []
                    seen += len(hits)
                    for d in hits:
                        t = title_has(d, term, LANGS[cc])
                        if not t:
                            continue
                        dists = d.get("distributions") or []
                        formats = sorted({fmt(x) for x in dists} - {""})
                        geo = [x for x in dists if fmt(x) in GEO]
                        pdf = [x for x in dists if fmt(x) == "PDF"]
                        if not geo and not pdf:
                            continue
                        best = (geo or pdf)[0]
                        lic = next(
                            (
                                str((x.get("license") or {}).get("id"))
                                for x in dists
                                if x.get("license")
                            ),
                            "",
                        )
                        # INSPIRE harvests often carry no publisher: fall back to the contact
                        # point, then to the source catalogue's title.
                        contact = (d.get("contact_point") or [{}])[0]
                        cat = d.get("catalog") or {}
                        cat_title = (cat.get("title") or {}) if isinstance(cat, dict) else {}
                        pub = (
                            (d.get("publisher") or {}).get("name")
                            or contact.get("name")
                            or next(iter(cat_title.values()), "")
                            or ""
                        )
                        rows[d["id"]] = {
                            "country": cc,
                            "term": term,
                            "title": t,
                            "publisher": pub,
                            "formats": " ".join(formats),
                            "geo": bool(geo),
                            "url": (urls(best) or [""])[0],
                            "licence": lic,
                            "modified": d.get("modified") or "",
                            "landing": (d.get("landing_page") or [{}])[0].get("resource", "")
                            if isinstance(d.get("landing_page"), list)
                            else "",
                            "id": d["id"],
                        }
                        kept += 1
                    if len(hits) < 100:
                        break
                print(
                    f"{cc} {term!r}: portal count {res.get('count', 0):,}, read {seen}, kept {kept}"
                )
    out = sorted(rows.values(), key=lambda r: (r["country"], r["publisher"], r["title"]))
    with (a.out / "datasets.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]) if out else ["id"])
        w.writeheader()
        w.writerows(out)
    by_pub = Counter((r["country"], r["publisher"], r["geo"]) for r in out)
    with (a.out / "publishers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "publisher", "geodata", "datasets"])
        for (cc, pub, geo), n in sorted(by_pub.items(), key=lambda kv: (kv[0][0], -kv[1])):
            w.writerow([cc, pub, geo, n])
    per = Counter(r["country"] for r in out)
    print("datasets kept per country:", dict(sorted(per.items())))


if __name__ == "__main__":
    main()
