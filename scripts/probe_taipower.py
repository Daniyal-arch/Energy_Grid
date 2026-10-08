"""Probe Taipower's open data (data.gov.tw dataset 8931): generation of every unit,
updated every 10 minutes. What does one answer look like, and how is it grouped?"""

from __future__ import annotations

import json
from collections import Counter

import httpx

URLS = {
    "units": "https://service.taipower.com.tw/data/opendata/apply/file/d006001/001.json",
    "units_past": "https://service.taipower.com.tw/data/opendata/apply/file/d006010/001.json",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (InfraAtlas probe)"}


def main() -> None:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        for name, url in URLS.items():
            r = client.get(url)
            print(
                f"== {name}: HTTP {r.status_code}, {len(r.content)} bytes, {r.headers.get('content-type')}"
            )
            if r.status_code != 200:
                continue
            data = r.json() if r.text.strip() else None
            if isinstance(data, dict):
                print("keys:", list(data)[:10])
                for k, v in data.items():
                    if isinstance(v, list):
                        print(f"{k}: {len(v)} rows; first 3:")
                        for row in v[:3]:
                            print("  ", json.dumps(row, ensure_ascii=False)[:300])
                        if v and isinstance(v[0], dict):
                            for field in v[0]:
                                vals = Counter(str(row.get(field))[:30] for row in v)
                                print(
                                    f"   field {field!r}: {len(vals)} distinct, e.g. {vals.most_common(6)}"
                                )
                    else:
                        print(f"{k}: {str(v)[:200]}")
            elif isinstance(data, list):
                print(f"list of {len(data)}; first:", json.dumps(data[0], ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
