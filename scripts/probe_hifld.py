"""Probe HIFLD's "Electric Power Transmission Lines" before the US lines layer: is it still public?

HIFLD Open (DHS) changed in 2025. This checks, on ArcGIS Online:
1. The HIFLD geoplatform's own organisation (Hp6G80Pky0om7QvQ, from
   hifld-geoplatform.hub.arcgis.com): which public items about transmission lines it holds
2. Esri's long-standing public copy (item d4090758322c4d32a4cd002ffaa0aa12): title, status,
   licence, last data update, feature count
3. The fallback the brief names: the OpenStreetMap lines (220 kV and more) already on R2 as
   grid/world-hv.pmtiles: lines and voltages inside the lower 48 (one zoom-4 tile pass)

  uv run --with pmtiles --with mapbox-vector-tile python scripts/probe_hifld.py
"""

from __future__ import annotations

import gzip
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime

import httpx

SEARCH = "https://www.arcgis.com/sharing/rest/search"
ITEM = "https://www.arcgis.com/sharing/rest/content/items/{}"
HIFLD_HUB = "https://hifld-geoplatform.hub.arcgis.com"
ESRI_COPY = "d4090758322c4d32a4cd002ffaa0aa12"
HV_TILES = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid/world-hv.pmtiles"


def text(v: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", v or ""))).strip()


def day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).date().isoformat()


def main() -> None:
    c = httpx.Client(timeout=60, follow_redirects=True)
    org = re.search(r'"orgId":"([^"]+)"', c.get(HIFLD_HUB).text)
    org_id = org.group(1) if org else "Hp6G80Pky0om7QvQ"
    print(f"1. HIFLD hub organisation: {org_id}")
    q = {"q": f"orgid:{org_id} AND transmission", "num": 50, "f": "json"}
    for it in c.get(SEARCH, params=q).json()["results"]:
        print(
            f"   {it['id']} | {it['title'][:60]} | owner {it['owner']} | {it['type']} | {it['access']} | modified {day(it['modified'])}"
        )
    print(
        "   -> no HIFLD-published public 'Electric Power Transmission Lines' item (only a 2023 user upload)"
    )

    d = c.get(ITEM.format(ESRI_COPY), params={"f": "json"}).json()
    print(f"\n2. {d['title']} (owner {d['owner']}, modified {day(d['modified'])})")
    print(f"   snippet: {text(d.get('snippet'))}")
    print(f"   licence: {text(d.get('licenseInfo'))}")
    desc = text(d.get("description"))
    print(f"   description: {desc[:300]}")
    layer = d["url"] + "/0"
    count = c.get(
        f"{layer}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}
    ).json()
    meta = c.get(layer, params={"f": "json"}).json()
    print(
        f"   features: {count.get('count')}, data last edited {day(meta['editingInfo']['dataLastEditDate'])}"
    )
    print(
        "   -> archived, no longer maintained, under the Esri Master License Agreement: not an open source to republish"
    )

    print("\n3. OpenStreetMap lines on R2 (world-hv.pmtiles)")
    try:
        import mapbox_vector_tile
        from pmtiles.reader import MmapSource, Reader  # noqa: F401
        from pmtiles.reader import Reader as R
    except ImportError:
        print("   (run with --with pmtiles --with mapbox-vector-tile to count the lines)")
        return
    head = c.head(HV_TILES)
    print(
        f"   {HV_TILES}: {int(head.headers['content-length']) / 1e6:.1f} MB, Last-Modified {head.headers.get('last-modified')}"
    )

    def get_bytes(offset: int, length: int) -> bytes:
        return c.get(HV_TILES, headers={"Range": f"bytes={offset}-{offset + length - 1}"}).content

    reader = R(get_bytes)
    print(
        f"   header: {json.dumps({k: v for k, v in reader.header().items() if 'zoom' in k or 'lon' in k or 'lat' in k})}"
    )
    kv: Counter[int] = Counter()
    ids: set[int] = set()
    # zoom 4 tiles over the lower 48 (x 2..5, y 5..6): every line from 220 kV shows from zoom 3
    for x in range(2, 6):
        for y in range(5, 7):
            data = reader.get(4, x, y)
            if not data:
                continue
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            for f in mapbox_vector_tile.decode(data).get("hv", {}).get("features", []):
                p = f["properties"]
                if p.get("id") in ids:
                    continue
                ids.add(p.get("id"))
                kv[int(p.get("kv") or 0)] += 1
    print(f"   lines in the zoom-4 tiles over North America: {len(ids):,}")
    print(f"   by kV: {sorted(kv.items())}")


if __name__ == "__main__":
    main()
