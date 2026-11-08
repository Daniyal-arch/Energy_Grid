"""Probe the zoning sources listed in docs/research/zoning.md (no keys).

For each source: HTTP status, format, feature count where the service reports one, the
fields of one feature and its zone label. Small requests only (one feature or the
service's capabilities); bulk downloads run in GitHub Actions.

    uv run python scripts/probe_zoning.py [name ...]
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable

import httpx

UA = {"User-Agent": "Europe-InfraAtlas zoning probe"}


def show(name: str, r: httpx.Response, extra: str = "") -> None:
    ctype = r.headers.get("content-type", "").split(";")[0]
    print(f"{name}: HTTP {r.status_code} {ctype} {len(r.content):,} bytes {extra}".rstrip())


def france(c: httpx.Client) -> None:
    # Géoportail de l'Urbanisme, API Carto module GPU: zones of the Paris PLU.
    r = c.get(
        "https://apicarto.ign.fr/api/gpu/zone-urba",
        params={"partition": "DU_75056", "_limit": 1},
    )
    j = r.json()
    f = j["features"][0]
    show("france gpu zone-urba", r, f"totalFeatures={j.get('totalFeatures')}")
    print("  fields:", sorted(f["properties"]))
    p = f["properties"]
    print("  sample:", {k: p.get(k) for k in ("libelle", "libelong", "typezone", "urlfic")})


def denmark(c: httpx.Client) -> None:
    base = "https://geoserver.plandata.dk/geoserver/wfs"
    r = c.get(base, params={"service": "WFS", "request": "GetCapabilities"})
    names = re.findall(r"<Name>([^<]+)</Name>", r.text)
    show("denmark plandata capabilities", r, f"{len(names)} feature types")
    print("  types:", [n for n in names if re.search(r"lokalplan|kommuneplan|ramme", n)][:12])
    for t in ("pdk:theme_pdk_lokalplan_vedtaget_v", "pdk:theme_pdk_kommuneplanramme_vedtaget_v"):
        if t not in names:
            continue
        q = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": t,
            "count": 1,
            "outputFormat": "application/json",
        }
        f = c.get(base, params=q)
        hits = c.get(base, params={**q, "resultType": "hits", "outputFormat": None})
        n = re.search(r'numberMatched="(\d+)"', hits.text)
        show(f"  {t}", f, f"numberMatched={n.group(1) if n else '?'}")
        if f.headers.get("content-type", "").startswith("application/json"):
            print("   fields:", sorted(f.json()["features"][0]["properties"]))


def helsinki(c: httpx.Client) -> None:
    base = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
    r = c.get(base, params={"service": "WFS", "request": "GetCapabilities"})
    names = re.findall(r"<Name>([^<]+)</Name>", r.text)
    show("helsinki capabilities", r, f"{len(names)} feature types")
    print("  plan types:", [n for n in names if re.search(r"(?i)kaava", n)][:12])


def england(c: httpx.Client) -> None:
    for d in ("green-belt", "conservation-area", "article-4-direction-area", "brownfield-land"):
        url = f"https://files.planning.data.gov.uk/dataset/{d}.csv"
        r = c.get(url, headers={"Range": "bytes=0-2047"})
        head = r.text.splitlines()[0] if r.status_code in (200, 206) else ""
        size = r.headers.get("content-range", "").split("/")[-1]
        show(f"england {d}", r, f"size={size}")
        print("  columns:", head[:200])


def california(c: httpx.Client) -> None:
    # Statewide compilation of local zoning (Office of Land Use and Climate Innovation).
    base = "https://services8.arcgis.com/Xr1lDrwMv89PhjD9/arcgis/rest/services"
    for name, layer in (("South", 0), ("North", 1)):
        url = f"{base}/California_Statewide_Zoning_{name}/FeatureServer/{layer}"
        n = c.get(f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"})
        meta = c.get(url, params={"f": "json"}).json()
        show(f"california {name}", n, f"count={n.json().get('count')}")
        print("  fields:", [f["name"] for f in meta.get("fields", [])])


PROBES: dict[str, Callable[[httpx.Client], None]] = {
    "france": france,
    "denmark": denmark,
    "helsinki": helsinki,
    "england": england,
    "california": california,
}


def main() -> None:
    names = sys.argv[1:] or list(PROBES)
    with httpx.Client(timeout=60, headers=UA, follow_redirects=True) as c:
        for n in names:
            try:
                PROBES[n](c)
            except Exception as e:  # noqa: BLE001 - a probe reports and moves on
                print(f"{n}: failed: {type(e).__name__}: {e}"[:300])


if __name__ == "__main__":
    main()
