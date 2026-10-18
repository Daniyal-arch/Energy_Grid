"""US public EV fast chargers (NREL Alternative Fuels Data Center, station locator API).

`alt-fuel-stations/v1.json` with fuel_type=ELEC, status=E (open), access=public, country=US,
limit=all (scripts/probe_nrel_afdc.py). NREL keys are api.data.gov keys: NREL_API_KEY (in
Actions the repo secret EPA_API_KEY is passed as NREL_API_KEY). developer.nrel.gov is an alias
of developer.nlr.gov since NREL was renamed; the first host that answers is used.

Passed through per DC fast station (ev_dc_fast_num > 0): position, DC fast ports, network,
opening year (from open_date), name. Stations with only level 1/2 ports are counted, not drawn.
Computed per state and in total (sums): stations, DC fast stations, level 2 ports, DC fast
ports; DC fast ports per network.

Writes frontend/public/data/us/ev_chargers.json:
  {"source", "licence", "fetched", "networks": [name], "names": [station name],
   "points": [[lon, lat, DC ports, network index, open year | null]],
   "states": {ST: [stations, DC fast stations, level 2 ports, DC fast ports]},
   "total": [same], "by_network": [[name, DC fast stations, DC fast ports]]}
With --lake DIR: every station with every field as GeoParquet, lake/afdc/stations
(partition snapshot), --upload sends it to R2.

    NREL_API_KEY=... uv run python scripts/fetch_ev_chargers.py [--lake lake-out --upload]
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "us" / "ev_chargers.json"
HOSTS = ["https://developer.nlr.gov", "https://developer.nrel.gov"]
PATH = "/api/alt-fuel-stations/v1.json"
QUERY = {"fuel_type": "ELEC", "status": "E", "access": "public", "country": "US", "limit": "all"}
SOURCE = "NREL Alternative Fuels Data Center, station locator (alt-fuel-stations/v1)"
LICENCE = "U.S. Department of Energy / NREL data, free to use with attribution (AFDC)"


def fetch(key: str) -> list[dict]:
    last = None
    with httpx.Client(timeout=600, follow_redirects=True) as c:
        for host in HOSTS:
            try:
                r = c.get(host + PATH, params={**QUERY, "api_key": key})
            except httpx.HTTPError as err:
                last = f"{host}: {type(err).__name__}"
                continue
            if r.status_code == 200:
                return r.json()["fuel_stations"]
            last = f"{host}: HTTP {r.status_code} {r.text[:200]}"
    raise SystemExit(f"AFDC not answered ({last}); if the key is refused, set NREL_API_KEY")


def build(stations: list[dict]) -> dict:
    networks: list[str] = []
    net_idx: dict[str, int] = {}
    points: list[list] = []
    names: list[str] = []
    states: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    by_net: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for s in stations:
        dc = s.get("ev_dc_fast_num") or 0
        l2 = s.get("ev_level2_evse_num") or 0
        st = states[s.get("state") or "?"]
        st[0] += 1
        st[2] += l2
        st[3] += dc
        if dc <= 0:
            continue
        st[1] += 1
        net = s.get("ev_network") or "Unknown"
        by_net[net][0] += 1
        by_net[net][1] += dc
        if s.get("longitude") is None or s.get("latitude") is None:
            continue
        if net not in net_idx:
            net_idx[net] = len(networks)
            networks.append(net)
        opened = s.get("open_date")
        points.append(
            [
                round(s["longitude"], 5),
                round(s["latitude"], 5),
                dc,
                net_idx[net],
                int(opened[:4]) if opened else None,
            ]
        )
        names.append(s.get("station_name") or "")
    total = [sum(v[i] for v in states.values()) for i in range(4)]
    return {
        "source": SOURCE,
        "licence": LICENCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "networks": networks,
        "names": names,
        "points": points,
        "states": dict(sorted(states.items())),
        "total": total,
        "by_network": sorted(([n, *v] for n, v in by_net.items()), key=lambda r: -r[2]),
    }


def write_lake(stations: list[dict], root: Path, tmp: Path, upload: bool) -> None:
    import duckdb
    import lake

    tmp.mkdir(parents=True, exist_ok=True)
    src = tmp / "afdc_stations.jsonl"
    with src.open("w", encoding="utf-8") as f:
        for s in stations:
            f.write(json.dumps(s) + "\n")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    snap = date.today().isoformat()
    lk = lake.Lake(
        "afdc",
        root,
        source=SOURCE,
        licence=LICENCE,
        script="scripts/fetch_ev_chargers.py",
        source_version=snap,
    )
    lk.write(
        con,
        "stations",
        f"""SELECT t.*, ST_Point(t.longitude, t.latitude) AS geometry, 'US' AS iso2, 'USA' AS iso3,
                   t.state AS admin1
            FROM read_json('{src}', format = 'newline_delimited', sample_size = -1,
                           maximum_object_size = 100000000) t""",
        sort=[lake.hilbert()],
        partition={"snapshot": snap},
        geometry="geometry",
    )
    if upload:
        lk.pull_catalog()
    lk.finish()
    if upload:
        lk.upload()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--lake", type=Path)
    ap.add_argument("--tmp", type=Path, default=Path("/tmp/afdc"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    key = (os.environ.get("NREL_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "set NREL_API_KEY (an api.data.gov key: https://developer.nrel.gov/signup/)"
        )
    stations = fetch(key)
    payload = build(stations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    t = payload["total"]
    print(
        f"{t[0]:,} public stations, {t[1]:,} with DC fast ({len(payload['points']):,} drawn), "
        f"{t[3]:,} DC fast ports, {t[2]:,} level 2 ports; {args.out.stat().st_size / 1e6:.2f} MB"
    )
    if args.lake:
        write_lake(stations, args.lake, args.tmp, args.upload)


if __name__ == "__main__":
    main()
