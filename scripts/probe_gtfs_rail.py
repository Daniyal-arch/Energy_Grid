"""Probe gtfs.de free rail feeds (long-distance + regional) for the rail-day animation.

Downloads both feeds to data/gtfs/ (gitignored) and reports what a one-day
animation would have to work with: route types, operators, whether S-Bahn is in
the regional feed, whether shapes.txt exists, and how many trips run on a weekday.

    uv run python scripts/probe_gtfs_rail.py [YYYYMMDD]
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import httpx

FEEDS = {
    "fv": "https://download.gtfs.de/germany/fv_free/latest.zip",  # long-distance
    "rv": "https://download.gtfs.de/germany/rv_free/latest.zip",  # regional incl. S-Bahn?
}
OUT = Path(__file__).resolve().parents[1] / "data" / "gtfs"


def rows(z: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    if name not in z.namelist():
        return []
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))


def active_services(z: zipfile.ZipFile, day: date) -> set[str]:
    weekday = day.strftime("%A").lower()
    ymd = day.strftime("%Y%m%d")
    active = {
        r["service_id"]
        for r in rows(z, "calendar.txt")
        if r[weekday] == "1" and r["start_date"] <= ymd <= r["end_date"]
    }
    for r in rows(z, "calendar_dates.txt"):
        if r["date"] == ymd:
            (active.add if r["exception_type"] == "1" else active.discard)(r["service_id"])
    return active


def main() -> None:
    day = datetime.strptime(sys.argv[1], "%Y%m%d").date() if len(sys.argv) > 1 else date.today()
    OUT.mkdir(parents=True, exist_ok=True)
    for key, url in FEEDS.items():
        path = OUT / f"{key}.zip"
        if not path.exists():
            print(f"downloading {url}")
            path.write_bytes(httpx.get(url, follow_redirects=True, timeout=120).content)
        z = zipfile.ZipFile(path)
        routes = rows(z, "routes.txt")
        trips = rows(z, "trips.txt")
        services = active_services(z, day)
        route_by_id = {r["route_id"]: r for r in routes}
        day_trips = [t for t in trips if t["service_id"] in services]
        names = Counter(
            (route_by_id[t["route_id"]].get("route_short_name") or "?").split(" ")[0][:4]
            for t in day_trips
        )
        print(f"\n== {key} ({path.stat().st_size / 1e6:.1f} MB) files: {sorted(z.namelist())}")
        print(f"routes {len(routes)} · trips total {len(trips)} · trips on {day} {len(day_trips)}")
        print("route_type:", Counter(r["route_type"] for r in routes).most_common())
        print("agencies:", [a["agency_name"] for a in rows(z, "agency.txt")][:15])
        print("line prefixes that day:", names.most_common(15))
        print("shapes.txt present:", "shapes.txt" in z.namelist())


if __name__ == "__main__":
    main()
