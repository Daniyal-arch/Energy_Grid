"""Probe Planet Labs' Data API with the education-program API key.

Goal: find out, with real responses (not docs guesses), what this specific key
can actually see — which item-types (PlanetScope/SkySat/RapidEye/etc.) it can
search, how dense the revisit actually is over a real German energy site, and
which assets (visual vs. analytic vs. analytic_8b) are downloadable — before
designing a `planet` ingestion adapter around it.

Auth: Planet's Data API v1 uses HTTP Basic Auth with the API key as the
username and an empty password.

Hits:
  - GET  /data/v1/item-types/                       catalogue this key can use
  - POST /data/v1/quick-search                       PSScene + SkySatScene over
                                                       a real DE solar site, last 90 days
  - GET  /data/v1/item-types/{type}/items/{id}/assets  asset availability for
                                                       one returned item (education
                                                       licenses sometimes cap which
                                                       assets are downloadable)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["PLANET_API_KEY"]
BASE = "https://api.planet.com/data/v1"
AUTH = httpx.BasicAuth(KEY, "")

# a real solar site from our own sites table (Lower Saxony) — small bbox around it
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [9.95, 52.55],
            [10.05, 52.55],
            [10.05, 52.65],
            [9.95, 52.65],
            [9.95, 52.55],
        ]
    ],
}


def show(label: str, r: httpx.Response, max_chars: int = 2500) -> None:
    print(f"\n=== {label} === HTTP {r.status_code}")
    try:
        body = json.dumps(r.json(), indent=2)
    except Exception:
        body = r.text
    print(body[:max_chars] + ("... [truncated]" if len(body) > max_chars else ""))


def main() -> None:
    with httpx.Client(auth=AUTH, timeout=30) as c:
        item_types = c.get(f"{BASE}/item-types/")
        if item_types.status_code == 200:
            ids = [t["id"] for t in item_types.json()["item_types"]]
            print(f"\n=== item-types this key can search ({len(ids)}) ===")
            print(ids)
        else:
            show("item-types", item_types)

        since = (datetime.now(UTC) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        search_body = {
            "item_types": ["PSScene", "SkySatScene"],
            "filter": {
                "type": "AndFilter",
                "config": [
                    {"type": "GeometryFilter", "field_name": "geometry", "config": AOI},
                    {
                        "type": "DateRangeFilter",
                        "field_name": "acquired",
                        "config": {"gte": since},
                    },
                ],
            },
        }
        search = c.post(f"{BASE}/quick-search", json=search_body)
        show("quick-search (PSScene + SkySatScene, last 90d, DE solar site)", search)

        if search.status_code == 200:
            features = search.json().get("features", [])
            print(f"\n{len(features)} items found (first page)")
            by_type: dict[str, list[str]] = {}
            for f in features:
                by_type.setdefault(f["properties"]["item_type"], []).append(f["properties"]["acquired"])
            for item_type, dates in by_type.items():
                distinct_days = len({d[:10] for d in dates})
                print(f"  {item_type}: {len(dates)} scenes across {distinct_days} distinct days")

            with_perms = [f for f in features if f.get("_permissions")]
            without_perms = [f for f in features if not f.get("_permissions")]
            print(f"\nitems with non-empty _permissions: {len(with_perms)} / {len(features)}")
            if with_perms:
                print("example _permissions:", with_perms[0]["_permissions"])
                dates_with = sorted(f["properties"]["acquired"] for f in with_perms)
                print(f"downloadable date range: {dates_with[0][:10]} .. {dates_with[-1][:10]}")
            if without_perms:
                dates_without = sorted(f["properties"]["acquired"] for f in without_perms)
                print(f"non-downloadable date range: {dates_without[0][:10]} .. {dates_without[-1][:10]}")

            for item_type in by_type:
                t_with = [f for f in with_perms if f["properties"]["item_type"] == item_type]
                t_without = [f for f in without_perms if f["properties"]["item_type"] == item_type]
                print(f"\n{item_type}: {len(t_with)} downloadable, {len(t_without)} not")
                if t_with:
                    d = sorted(f["properties"]["acquired"] for f in t_with)
                    print(f"  downloadable: {d[0][:10]} .. {d[-1][:10]}")
                if t_without:
                    d = sorted(f["properties"]["acquired"] for f in t_without)
                    print(f"  not downloadable: {d[0][:10]} .. {d[-1][:10]}")

            if with_perms:
                pick = with_perms[0]
                item_type = pick["properties"]["item_type"]
                item_id = pick["id"]
                assets = c.get(f"{BASE}/item-types/{item_type}/items/{item_id}/assets/")
                show(f"assets for a DOWNLOADABLE {item_type} item ({item_id})", assets)
                if assets.status_code == 200:
                    for name, info in assets.json().items():
                        print(f"  {name}: status={info.get('status')}")


if __name__ == "__main__":
    main()
