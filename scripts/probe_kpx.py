"""Probe KPX's public real-time pages (South Korea, no key): supply and demand, and
generation by source every 5 minutes. robots.txt allows both pages.

The same data is on data.go.kr as an open API (needs DATA_GO_KR_KEY); its dataset page
states the licence scope, printed here.

    uv run python scripts/probe_kpx.py
"""

from __future__ import annotations

import json
import re

import httpx

BASE = "https://new.kpx.or.kr"
DEMAND = f"{BASE}/powerinfoSubmain.es?mid=a10606030000"
SOURCES = f"{BASE}/powerSource.es?mid=a10606030000"
DATASET = "https://www.data.go.kr/data/15106744/openapi.do"  # KPX generation by source


def main() -> None:
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (InfraAtlas probe)"}) as c:
        print("robots:", c.get(f"{BASE}/robots.txt").text.splitlines()[:3])
        r = c.get(DEMAND)
        print(f"demand: HTTP {r.status_code} {len(r.content)} bytes")
        print("  at:", re.search(r'class="info_top">([^<]+)', r.text).group(1).strip())
        for key in ("avil", "load", "supPow", "supPer"):
            print(f"  {key}:", re.search(rf'id="{key}">([^<]+)', r.text).group(1))
        r = c.get(SOURCES)
        print(f"sources: HTTP {r.status_code} {len(r.content)} bytes")
        rows = json.loads(re.search(r"var ictArr\s*=\s*(\[.*?\]);", r.text, re.S).group(1))
        real = [row for row in rows if row["regDate"] != "0"]
        print(f"  {len(rows)} rows, {len(real)} with a regDate (the rest are placeholders)")
        print("  newest:", json.dumps(real[-1], ensure_ascii=False))
        try:
            page = re.sub(r"\s+", " ", c.get(DATASET).text)
        except httpx.HTTPError as err:
            print(f"data.go.kr: {err.__class__.__name__} {err}")
            return
        print("data.go.kr:", re.search(r"<title>([^<]+)", page).group(1).strip())
        print("  licence:", re.search(r"이용허락범위[^\"<]{0,40}", page).group(0))


if __name__ == "__main__":
    main()
