"""Build one day of German rail movements for the rail-day animation.

Inputs
  data/gtfs/{fv,rv}.zip          gtfs.de long-distance + regional timetables (probe_gtfs_rail.py)
  data/osm_rail/rail.json.gz     OSM mainline track geometry (fetch_rail_osm.py)
  rail-rt/<date>.json.gz         recorded GTFS-Realtime delays (rail-data branch, optional)

Output
  frontend/public/data/rail_day/<date>.json   (gitignored; rebuild with this script)

Every train run of the service day becomes a list of stop events (arrival and
departure, in seconds after local midnight). Where the recorder captured a
real-time update for a stop, the published actual time replaces the timetable
time and the delay is kept; otherwise the timetable time is used and flagged, so
the frontend can say how much is observed. Between stops the train follows the
track: consecutive stops are routed along the OSM rail graph (shortest path,
cached per stop pair); if no track route is found the hop is drawn straight and
counted in the build summary.

    uv run python scripts/build_rail_day.py 20260929
"""

from __future__ import annotations

import csv
import gzip
import heapq
import io
import json
import math
import sys
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "data" / "gtfs"
RT_DIR = ROOT / "data" / "rail-rt"
OSM = ROOT / "data" / "osm_rail" / "rail.json.gz"
OUT_DIR = ROOT / "frontend" / "public" / "data" / "rail_day"
RT_RAW = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/rail-data/rail-rt/{d}.json.gz"
BERLIN = ZoneInfo("Europe/Berlin")

SNAP_M = 1200  # a stop further than this from any track is left unsnapped (straight hops)
SIMPLIFY_M = 25  # output geometry tolerance
M_PER_DEG_LAT = 111_320.0


# ── small geometry helpers (equirectangular metres around Germany) ───────────
def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((b[0] - a[0]) * M_PER_DEG_LAT * k, (b[1] - a[1]) * M_PER_DEG_LAT)


def simplify(pts: list[tuple[float, float]], tol_m: float) -> list[tuple[float, float]]:
    if len(pts) <= 2:
        return pts
    k = math.cos(math.radians(pts[0][1]))
    xy = [(p[0] * M_PER_DEG_LAT * k, p[1] * M_PER_DEG_LAT) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, -1
        for m in range(i + 1, j):
            d = abs(dy * (xy[m][0] - x1) - dx * (xy[m][1] - y1)) / norm
            if d > best:
                best, idx = d, m
        if best > tol_m and idx > 0:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k2 in zip(pts, keep, strict=True) if k2]


# ── timetable ────────────────────────────────────────────────────────────────
def rows(z: zipfile.ZipFile, name: str):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))


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


def hms(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def service_class(name: str, feed: str) -> int:
    """0 long-distance, 1 regional (RE/RB/…), 2 S-Bahn."""
    if feed == "fv":
        return 0
    n = name.strip().upper()
    if n.startswith("S") and (len(n) == 1 or n[1].isdigit() or n[1] == " "):
        return 2
    return 1


def load_timetable(day: date):
    stops: dict[str, tuple[float, float]] = {}
    trips: dict[str, dict] = {}
    for feed in ("fv", "rv"):
        z = zipfile.ZipFile(GTFS / f"{feed}.zip")
        for r in rows(z, "stops.txt"):
            stops[r["stop_id"]] = (float(r["stop_lon"]), float(r["stop_lat"]))
        routes = {r["route_id"]: r for r in rows(z, "routes.txt")}
        services = active_services(z, day)
        for t in rows(z, "trips.txt"):
            if t["service_id"] in services:
                route = routes[t["route_id"]]
                name = route.get("route_short_name") or route.get("route_long_name") or ""
                trips[t["trip_id"]] = {"cls": service_class(name, feed), "name": name, "stops": []}
        for st in rows(z, "stop_times.txt"):
            trip = trips.get(st["trip_id"])
            if trip is not None:
                trip["stops"].append(
                    (
                        int(st["stop_sequence"]),
                        st["stop_id"],
                        hms(st["arrival_time"]),
                        hms(st["departure_time"]),
                    )
                )
    for trip in trips.values():
        trip["stops"].sort()
    return stops, {k: v for k, v in trips.items() if len(v["stops"]) >= 2}


def load_realtime(ymd: str) -> dict:
    path = RT_DIR / f"{ymd}.json.gz"
    if not path.exists():
        r = httpx.get(RT_RAW.format(d=ymd), timeout=120, follow_redirects=True)
        if r.status_code != 200:
            print(f"no real-time file for {ymd}: timetable only")
            return {"trips": {}, "snapshots": []}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return json.loads(gzip.decompress(path.read_bytes()))


# ── track graph ──────────────────────────────────────────────────────────────
class TrackGraph:
    def __init__(self, stop_coords: dict[str, tuple[float, float]]) -> None:
        raw = json.loads(gzip.decompress(OSM.read_bytes()))
        coords = {int(k): tuple(v) for k, v in raw["nodes"].items()}
        adj: dict[int, set[int]] = defaultdict(set)
        for way in raw["ways"]:
            for a, b in zip(way, way[1:], strict=False):
                if a in coords and b in coords and a != b:
                    adj[a].add(b)
                    adj[b].add(a)
        self.coords = coords
        # grid index of track nodes for snapping
        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        for n in adj:
            x, y = coords[n]
            grid[(int(x * 50), int(y * 50))].append(n)
        self.snap: dict[str, int] = {}
        for sid, (x, y) in stop_coords.items():
            gx, gy = int(x * 50), int(y * 50)
            best, best_d = None, SNAP_M
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for n in grid.get((gx + dx, gy + dy), ()):
                        d = dist_m((x, y), coords[n])
                        if d < best_d:
                            best, best_d = n, d
            if best is not None:
                self.snap[sid] = best
        # contract degree-2 chains, keeping junctions and snapped nodes
        keep = {n for n, nb in adj.items() if len(nb) != 2} | set(self.snap.values())
        self.edges: dict[int, list[tuple[int, float, list[int]]]] = defaultdict(list)
        for start in keep:
            for nxt in adj[start]:
                chain = [start, nxt]
                length = dist_m(coords[start], coords[nxt])
                prev, cur = start, nxt
                while cur not in keep:
                    nb = [m for m in adj[cur] if m != prev]
                    if not nb:
                        break
                    prev, cur = cur, nb[0]
                    length += dist_m(coords[prev], coords[cur])
                    chain.append(cur)
                    if cur == start:
                        break
                if cur in keep and cur != start:
                    self.edges[start].append((cur, length, chain))
        print(
            f"track graph: {len(adj):,} nodes -> {len(self.edges):,} routing nodes; "
            f"{len(self.snap):,}/{len(stop_coords):,} stops snapped"
        )

    def routes_from(self, source: int, targets: set[int], limit_m: float) -> dict[int, list[int]]:
        """Dijkstra from one snapped stop to several; returns node chains per reached target."""
        dist = {source: 0.0}
        prev: dict[int, tuple[int, list[int]]] = {}
        heap = [(0.0, source)]
        left = set(targets)
        while heap and left:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, math.inf) or d > limit_m:
                continue
            left.discard(n)
            for m, length, chain in self.edges.get(n, ()):
                nd = d + length
                if nd < dist.get(m, math.inf):
                    dist[m] = nd
                    prev[m] = (n, chain)
                    heapq.heappush(heap, (nd, m))
        out = {}
        for t in targets:
            if t == source or t not in prev:
                continue
            chains = []
            cur = t
            while cur != source:
                p, chain = prev[cur]
                chains.append(chain)
                cur = p
            nodes = [source]
            for chain in reversed(chains):
                nodes.extend(chain[1:])
            out[t] = nodes
        return out


# ── build ────────────────────────────────────────────────────────────────────
def main() -> None:
    ymd = (
        sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    )
    day = datetime.strptime(ymd, "%Y%m%d").date()
    midnight = int(datetime(day.year, day.month, day.day, tzinfo=BERLIN).timestamp())
    started = time.time()

    stops, trips = load_timetable(day)
    print(f"{ymd}: {len(trips):,} train runs, {len(stops):,} stops ({time.time() - started:.0f} s)")
    rt = load_realtime(ymd)
    graph = TrackGraph(
        {sid: stops[sid] for t in trips.values() for _, sid, _, _ in t["stops"] if sid in stops}
    )

    # which stop pairs need a route, grouped by origin (one Dijkstra per origin)
    wanted: dict[int, set[int]] = defaultdict(set)
    reach: dict[tuple[int, int], float] = {}
    for trip in trips.values():
        for (_, a, _, _), (_, b, _, _) in zip(trip["stops"], trip["stops"][1:], strict=False):
            na, nb = graph.snap.get(a), graph.snap.get(b)
            if na is not None and nb is not None and na != nb:
                wanted[na].add(nb)
                straight = dist_m(stops[a], stops[b])
                reach[(na, nb)] = max(reach.get((na, nb), 0.0), straight * 2.5 + 5000)
    routed: dict[tuple[int, int], list[int]] = {}
    for i, (origin, targets) in enumerate(wanted.items()):
        limit = max(reach[(origin, t)] for t in targets)
        for t, nodes in graph.routes_from(origin, targets, limit).items():
            routed[(origin, t)] = nodes
        if i % 2000 == 0:
            print(f"  routing origins {i:,}/{len(wanted):,}", flush=True)

    # segments: one simplified geometry per (from stop, to stop) pair, shared by trips
    seg_index: dict[tuple[str, str], int] = {}
    segments: list[list[float]] = []
    straight_segments: list[int] = []  # hops drawn without track geometry
    straight_hops = total_hops = 0

    def segment(a: str, b: str) -> int:
        nonlocal straight_hops
        key = (a, b)
        if key in seg_index:
            return seg_index[key]
        na, nb = graph.snap.get(a), graph.snap.get(b)
        nodes = routed.get((na, nb)) if na is not None and nb is not None else None
        if nodes:
            pts = [stops[a], *(graph.coords[n] for n in nodes), stops[b]]
        else:
            pts = [stops[a], stops[b]]
            straight_hops += 1
            straight_segments.append(len(segments))
        flat: list[float] = []
        for x, y in simplify(pts, SIMPLIFY_M):
            flat += [round(x, 5), round(y, 5)]
        seg_index[key] = len(segments)
        segments.append(flat)
        return seg_index[key]

    out_trips = []
    observed_events = total_events = 0
    rt_trips = rt.get("trips", {})
    for trip_id, trip in trips.items():
        rtt = rt_trips.get(trip_id, {}).get("stops", {})
        times: list[int] = []  # arr0, dep0, arr1, dep1, ...
        delays: list[int] = []  # minutes per stop, -1 = no real-time report
        for seq, _sid, arr, dep in trip["stops"]:
            upd = rtt.get(str(seq))
            stop_delay = -1
            pair = []
            for sched, key in ((arr, "arr"), (dep, "dep")):
                total_events += 1
                ev = upd.get(key) if upd else None
                if ev and ev[1] is not None:
                    actual = ev[1] - midnight
                    stop_delay = max(stop_delay, round((actual - sched) / 60))
                    observed_events += 1
                elif ev and ev[0] is not None:
                    actual = sched + ev[0]
                    stop_delay = max(stop_delay, round(ev[0] / 60))
                    observed_events += 1
                else:
                    actual = sched
                pair.append(actual)
            pair[1] = max(pair[1], pair[0])
            times += pair
            delays.append(stop_delay)
        # keep time monotonic even if a report is inconsistent
        for k in range(1, len(times)):
            times[k] = max(times[k], times[k - 1])
        segs = []
        for (_, a, _, _), (_, b, _, _) in zip(trip["stops"], trip["stops"][1:], strict=False):
            total_hops += 1
            segs.append(segment(a, b) if a in stops and b in stops else -1)
        out_trips.append([trip["cls"], trip["name"], segs, times, delays])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{ymd}.json"
    out.write_text(
        json.dumps(
            {
                "date": ymd,
                "generated_at": datetime.now(BERLIN).isoformat(timespec="minutes"),
                "sources": {
                    "timetable": "gtfs.de long-distance + regional (DELFI), GTFS",
                    "realtime": "gtfs.de GTFS-Realtime, recorded every 15 min",
                    "track": "OpenStreetMap contributors (ODbL)",
                },
                "coverage": {
                    "train_runs": len(out_trips),
                    "runs_with_realtime": sum(1 for t in out_trips if any(d >= 0 for d in t[4])),
                    "events_observed": observed_events,
                    "events_total": total_events,
                    "hops_straight": straight_hops,
                    "hops_total": total_hops,
                    "realtime_snapshots": len(rt.get("snapshots", [])),
                },
                "classes": ["long-distance", "regional", "S-Bahn"],
                "segments": segments,
                "straight_segments": straight_segments,
                "trips": out_trips,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    size = out.stat().st_size / 1e6
    print(
        f"wrote {out} ({size:.1f} MB) · {len(segments):,} segments · straight hops "
        f"{straight_hops:,}/{len(seg_index):,} unique · observed events {observed_events:,}/{total_events:,} "
        f"· {time.time() - started:.0f} s"
    )


if __name__ == "__main__":
    sys.exit(main())
