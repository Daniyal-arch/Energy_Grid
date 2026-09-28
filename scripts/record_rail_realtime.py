"""Record German rail real-time delays (gtfs.de GTFS-Realtime) into one file per day.

Runs every 15 min from .github/workflows/rail-realtime.yml. Each run downloads the
full GTFS-RT feed (all public transport, ~60 MB), keeps only trips that belong to
the gtfs.de long-distance + regional rail timetables, and merges them into
`rail-rt/<service date>.json.gz` in Supabase Storage: the latest reported delay per
trip and stop wins, and every snapshot time is logged so coverage gaps are visible.

The recorded values are passed through unchanged (delay seconds and absolute times
as published); combining them with the timetable happens later, in the animation build.

    uv run --with gtfs-realtime-bindings python scripts/record_rail_realtime.py --out data/rail-rt
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import httpx
from google.transit import gtfs_realtime_pb2

RT_URL = "https://realtime.gtfs.de/realtime-free.pb"
STATIC_FEEDS = {
    "fv": "https://download.gtfs.de/germany/fv_free/latest.zip",  # long-distance
    "rv": "https://download.gtfs.de/germany/rv_free/latest.zip",  # regional incl. S-Bahn
}
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "gtfs"


def rail_trip_ids() -> set[str]:
    """trip_ids of the rail timetables; the zips are cached (Actions cache / data/gtfs)."""
    ids: set[str] = set()
    CACHE.mkdir(parents=True, exist_ok=True)
    for key, url in STATIC_FEEDS.items():
        path = CACHE / f"{key}.zip"
        if not path.exists() or time.time() - path.stat().st_mtime > 24 * 3600:
            path.write_bytes(httpx.get(url, follow_redirects=True, timeout=180).content)
        with zipfile.ZipFile(path) as z, z.open("trips.txt") as f:
            ids |= {r["trip_id"] for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))}
    return ids


def fetch_feed() -> gtfs_realtime_pb2.FeedMessage:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(httpx.get(RT_URL, timeout=300).content)
    return feed


def event(ev: gtfs_realtime_pb2.TripUpdate.StopTimeEvent) -> list[int | None]:
    return [ev.delay if ev.HasField("delay") else None, ev.time if ev.HasField("time") else None]


def extract(feed: gtfs_realtime_pb2.FeedMessage, rail: set[str]) -> dict[str, dict[str, dict]]:
    """{service_date: {trip_id: {stop_sequence: {...}}}} for rail trips in this snapshot."""
    days: dict[str, dict[str, dict]] = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        if tu.trip.trip_id not in rail:
            continue
        stops = {}
        for u in tu.stop_time_update:
            stops[str(u.stop_sequence)] = {
                "stop_id": u.stop_id,
                "arr": event(u.arrival) if u.HasField("arrival") else None,
                "dep": event(u.departure) if u.HasField("departure") else None,
                "rel": gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.ScheduleRelationship.Name(
                    u.schedule_relationship
                ),
            }
        days.setdefault(tu.trip.start_date or "unknown", {})[tu.trip.trip_id] = {
            "rel": gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.Name(
                tu.trip.schedule_relationship
            ),
            "stops": stops,
        }
    return days


def merge(state: dict, trips: dict[str, dict], snapshot_ts: int) -> dict:
    state.setdefault("snapshots", []).append(snapshot_ts)
    all_trips = state.setdefault("trips", {})
    for trip_id, trip in trips.items():
        kept = all_trips.setdefault(trip_id, {"rel": trip["rel"], "stops": {}})
        kept["rel"] = trip["rel"]
        kept["stops"].update(trip["stops"])  # newer report for a stop replaces the older one
        kept["last_seen"] = snapshot_ts
    return state


def load(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {}


def save(path: Path, state: dict) -> int:
    blob = gzip.compress(json.dumps(state, separators=(",", ":")).encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return len(blob)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=ROOT / "data" / "rail-rt", help="folder for day files"
    )
    args = parser.parse_args()

    started = time.time()
    rail = rail_trip_ids()
    feed = fetch_feed()
    snapshot_ts = feed.header.timestamp
    days = extract(feed, rail)
    for service_date, trips in sorted(days.items()):
        path = args.out / f"{service_date}.json.gz"
        state = merge(load(path), trips, snapshot_ts)
        size = save(path, state)
        print(
            f"{path.name}: +{len(trips)} trips this snapshot, {len(state['trips'])} total, {size / 1e6:.2f} MB"
        )
    print(f"snapshot {snapshot_ts} · {len(feed.entity)} entities · {time.time() - started:.0f} s")


if __name__ == "__main__":
    sys.exit(main())
