"""Probe a sample of the ArcGIS zoning services found by `zoning_discover.py --hub`.

For each sampled service: its layers, their geometry type, feature count, the fields that look
like a zoning code or label, and whether the service answers at all. Prints one line a layer and
a summary, to decide how `build_zoning.py` reads them in bulk.

    uv run python scripts/probe_zoning_hub.py --n 40 --region us
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections import Counter
from pathlib import Path

import httpx

LIST = Path("data/zoning_discovery/hub_services.csv")
UA = {"User-Agent": "InfraAtlas zoning probe (open-data research)"}
NOISE = re.compile(
    r"feedback|survey|comment|form\b|request|petition|notice|hearing|case|application|"
    r"permit|violation|complaint|workshop|story|dashboard|test\b|copy\b|_view\b",
    re.I,
)
CODE = re.compile(r"^(zon(e|ing)?[_ ]?(code|class|dist(rict)?|type|cd|desig)?|zoning|zone|"
                  r"district|zone_?name|zonedesc|zone_?desc(ription)?|zn_?code|zoneclass)$", re.I)  # fmt: skip


def layers(c: httpx.Client, url: str) -> list[dict]:
    r = c.get(url, params={"f": "json"})
    r.raise_for_status()
    d = r.json()
    if "error" in d:
        raise RuntimeError(d["error"].get("message"))
    return d.get("layers") or []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--region", default="us")
    ap.add_argument("--seed", type=int, default=32)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(LIST.open(encoding="utf-8")) if r["region"] == a.region]
    kept = [r for r in rows if not NOISE.search(r["title"])]
    urls = sorted({r["url"] for r in kept})
    print(
        f"{len(rows):,} services listed, {len(kept):,} after the noise filter, {len(urls):,} urls"
    )
    random.seed(a.seed)
    sample = random.sample(urls, min(a.n, len(urls)))
    stats: Counter[str] = Counter()
    total = 0
    with httpx.Client(timeout=40, headers=UA, follow_redirects=True) as c:
        for url in sample:
            try:
                ls = layers(c, url)
            except Exception as e:  # noqa: BLE001 - a probe records every failure
                stats["service fails"] += 1
                print(f"FAIL {url[:90]} {str(e)[:80]}")
                continue
            stats["services answer"] += 1
            for ly in ls:
                lu = f"{url}/{ly['id']}"
                try:
                    meta = c.get(lu, params={"f": "json"}).json()
                    n = c.get(f"{lu}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}).json().get("count")  # fmt: skip
                except Exception as e:  # noqa: BLE001
                    print(f"  layer fail {lu[:90]} {str(e)[:60]}")
                    stats["layer fails"] += 1
                    continue
                geom = meta.get("geometryType", "")
                fields = [f["name"] for f in meta.get("fields") or []]
                code = [f for f in fields if CODE.match(f)]
                poly = geom == "esriGeometryPolygon"
                stats[f"geometry {geom or 'none'}"] += 1
                if poly and code:
                    stats["polygon layers with a zoning field"] += 1
                    total += n or 0
                print(
                    f"  {(n or 0):>8,} {geom[12:]:<9} {ly['name'][:40]:<40} {','.join(code)[:60]}"
                )
    print(dict(stats))
    print(f"features in polygon layers with a zoning field: {total:,}")


if __name__ == "__main__":
    main()
