"""What each large power plant in Europe produced through a day, every 15 minutes.

ENTSO-E Transparency A73 "actual generation per generation unit" (processType A16; units
of 100 MW and more; ENTSOE_API_KEY), one request per country and day (Germany per
control area: 50Hertz, Amprion, TenneT DE, TransnetBW). Germany, the Nordic countries,
Austria and Switzerland publish about five days late; Italy, Denmark, Great Britain and
Croatia publish none (scripts/probe_unit_output.py). Each run therefore rebuilds the
last days so late publications fill in.

Where each unit stands comes from the JRC Open Power Plants Database (JRC-PPDB-OPEN 1.0,
CC BY 4.0, Zenodo 3574566): its `eic_g` (the unit's EIC code, the one ENTSO-E reports)
gives the coordinates, the plant (`eic_p`, `name_p`) and the unit's capacity
(`capacity_g`). Units the JRC file does not list are counted, not placed.

Values are passthrough (MW, aligned to the day's 15-min slots like the day files; hourly
series fill their four slots). Computed: the units of one plant summed per slot, the
plant's capacity as the sum of its units' JRC capacities, the plant's fuel as that of
its largest unit.

Writes frontend/public/data/eu/units/<YYYY-MM-DD>.json and units/index.json:
  {"source", "date", "start", "step_s", "slots", "fuels": [group],
   "plants": [[lon, lat, fuel, "ISO", capacity MW | null, "name", units]],
   "output": [[MW | null per slot] per plant],
   "countries": {ISO: {"units", "placed"}}, "areas_without_data": [area]}

    uv run python scripts/build_eu_units.py 2026-10-01         # one day
    uv run python scripts/build_eu_units.py --recent 8         # the last 8 complete days
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402
from build_eu_day import TZ, day_window  # noqa: E402
from fetch_eu_snapshot import FUEL_GROUP, USER_AGENT  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "units"
RAW = Path(__file__).resolve().parents[1] / "data" / "eu" / "jrc"
JRC_URL = "https://zenodo.org/api/records/3574566/files/JRC-PPDB-OPEN.ver1.0.zip/content"
SOURCE = (
    "ENTSO-E Transparency A73 actual generation per generation unit; "
    "placed with the JRC Open Power Plants Database 1.0 (CC BY 4.0)"
)
DE_AREAS = {
    "DE-50Hertz": "10YDE-VE-------2",
    "DE-Amprion": "10YDE-RWENET---I",
    "DE-TenneT": "10YDE-EON------1",
    "DE-TransnetBW": "10YDE-ENBW-----N",
}
# areas asked: every country area, Germany per control area
AREAS = {**{k: v for k, v in entsoe.AREA_EIC.items() if k != "DE"}, **DE_AREAS}
# a day counts as complete when every one of these has reported
# (the largest producers; smaller ones, e.g. Sweden, skip days now and then)
CORE_AREAS = {*DE_AREAS, "FR", "ES", "PL", "CZ", "NL"}


def jrc_units() -> dict[str, dict[str, str]]:
    """JRC units by their EIC code (only those with coordinates)."""
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / "JRC-PPDB-OPEN.ver1.0.zip"
    if not zpath.exists():
        print("downloading the JRC Open Power Plants Database (1.3 MB)", flush=True)
        zpath.write_bytes(httpx.get(JRC_URL, follow_redirects=True, timeout=120).content)
    with zipfile.ZipFile(zpath) as z:
        rows = csv.DictReader(io.TextIOWrapper(z.open("JRC_OPEN_UNITS.csv"), encoding="utf-8"))
        return {r["eic_g"]: r for r in rows if r.get("eic_g") and r.get("lat") and r.get("lon")}


def day_units(client: httpx.Client, day: date) -> tuple[dict[str, dict], list[str]]:
    """Every unit's output on the day's slots: {unit: {"area", "name", "fuel", "values"}}."""
    start, slots = day_window(day)
    grid = entsoe.Grid(start, start + timedelta(seconds=entsoe.STEP * slots))

    def fetch(item: tuple[str, str]) -> tuple[str, list]:
        area, eic = item
        root = entsoe.request(
            client, {"documentType": "A73", "processType": "A16", "in_Domain": eic, **grid.params()}
        )
        return area, entsoe.series_of(root, "quantity", grid)

    units: dict[str, dict] = {}
    empty: list[str] = []
    results = entsoe.run((a, lambda item=(a, e): fetch(item)) for a, e in AREAS.items())
    for area_name, got in results.values():
        if not got:
            empty.append(area_name)
            continue
        for meta, values in got:
            uid = meta.get("unit")
            group = FUEL_GROUP.get(entsoe.PSR_NAME.get(meta.get("psrType", ""), ""), "other")
            if not uid or not any(v is not None for v in values):
                continue
            row = units.setdefault(
                uid,
                {
                    "area": area_name,
                    "name": meta.get("unit_name", ""),
                    "fuel": group,
                    "values": [None] * slots,
                },
            )
            for k, v in enumerate(values[:slots]):
                if v is not None:
                    row["values"][k] = v
    return units, sorted(empty)


def country_of(area: str) -> str:
    return "DE" if area.startswith("DE-") else area


def build(day: date, units: dict[str, dict], empty: list[str], jrc: dict[str, dict]) -> dict:
    start, slots = day_window(day)
    plants: dict[str, dict] = {}
    counts: dict[str, Counter] = defaultdict(Counter)
    for uid, u in units.items():
        iso = country_of(u["area"])
        counts[iso]["units"] += 1
        j = jrc.get(uid)
        if not j:
            continue
        counts[iso]["placed"] += 1
        key = j.get("eic_p") or uid
        cap = float(j["capacity_g"]) if j.get("capacity_g") else None
        p = plants.setdefault(
            key,
            {
                "lon": round(float(j["lon"]), 4),
                "lat": round(float(j["lat"]), 4),
                "iso": iso,
                "name": j.get("name_p") or u["name"],
                "units": 0,
                "capacity": 0.0,
                "missing_capacity": False,
                "fuel_by_cap": Counter(),
                "values": [None] * slots,
            },
        )
        p["units"] += 1
        if cap is None:
            p["missing_capacity"] = True
        else:
            p["capacity"] += cap
        p["fuel_by_cap"][u["fuel"]] += cap or 0.0
        for k, v in enumerate(u["values"]):
            if v is not None:
                p["values"][k] = (p["values"][k] or 0.0) + v
    fuels = sorted({p["fuel_by_cap"].most_common(1)[0][0] for p in plants.values()})
    rows = sorted(plants.values(), key=lambda p: -p["capacity"])
    return {
        "source": SOURCE,
        "date": day.isoformat(),
        "timezone": "Europe/Berlin",
        "start": start.isoformat(),
        "step_s": entsoe.STEP,
        "slots": slots,
        "fuels": fuels,
        "plants": [
            [
                p["lon"],
                p["lat"],
                fuels.index(p["fuel_by_cap"].most_common(1)[0][0]),
                p["iso"],
                None if p["missing_capacity"] else round(p["capacity"], 1),
                p["name"],
                p["units"],
            ]
            for p in rows
        ],
        # summed first, rounded once (0.1 MW)
        "output": [[None if v is None else round(v, 1) for v in p["values"]] for p in rows],
        "countries": {iso: dict(c) for iso, c in sorted(counts.items())},
        "areas_without_data": empty,
    }


def write_index(out: Path) -> None:
    days = sorted(f.stem for f in out.glob("????-??-??.json"))
    complete = []
    for d in days:
        data = json.loads((out / f"{d}.json").read_text(encoding="utf-8"))
        if not CORE_AREAS & set(data["areas_without_data"]):
            complete.append(d)
    (out / "index.json").write_text(
        json.dumps({"days": days, "complete": complete}), encoding="utf-8"
    )
    print(f"index: {len(days)} days, {len(complete)} complete", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("day", nargs="?", help="YYYY-MM-DD")
    parser.add_argument("--recent", type=int, help="rebuild the last N complete days")
    parser.add_argument("--keep", type=int, default=30, help="days to keep in the folder")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    today = datetime.now(TZ).date()
    if args.day:
        days = [date.fromisoformat(args.day)]
    else:
        days = [today - timedelta(days=n) for n in range(args.recent or 8, 0, -1)]
    args.out.mkdir(parents=True, exist_ok=True)
    jrc = jrc_units()
    with httpx.Client(timeout=300, headers=USER_AGENT) as client:
        for day in days:
            units, empty = day_units(client, day)
            payload = build(day, units, empty, jrc)
            n = sum(c.get("units", 0) for c in payload["countries"].values())
            placed = sum(c.get("placed", 0) for c in payload["countries"].values())
            path = args.out / f"{day.isoformat()}.json"
            path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            print(
                f"{day}: {n} units, {placed} placed in {len(payload['plants'])} plants; "
                f"no data: {' '.join(empty) or '-'}; {path.stat().st_size / 1e3:.0f} kB",
                flush=True,
            )
    # drop days older than the window
    cutoff = (today - timedelta(days=args.keep)).isoformat()
    for f in args.out.glob("????-??-??.json"):
        if f.stem < cutoff:
            f.unlink()
    write_index(args.out)


if __name__ == "__main__":
    main()
