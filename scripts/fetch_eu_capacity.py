"""Transfer capacity across Europe's borders (ENTSO-E; ENTSOE_API_KEY), for the flow arrows:
how much of the capacity on offer a flow uses.

Per bidding-zone border and direction: A61 forecasted transfer capacity, day-ahead
(contract type A01); where a border has none, A31 offered capacity of the day-ahead
implicit auction (auction type A01). Borders in the flow-based regions (Central Europe,
the Nordics) publish neither: their limits are set jointly, not per border, and the map
shows no capacity for them (scripts/probe_entsoe_capacity.py lists what exists).

A country border is the sum of its zone borders (e.g. Germany-Denmark = DE-LU>DK1 +
DE-LU>DK2) in each slot where every one of them has a value (computed); otherwise null.

Writes frontend/public/data/eu/capacity.json for today and tomorrow (Central European
time), refreshed with the snapshot's reference figures:
  {"source", "fetched", "start", "step_s", "slots",
   "borders": [{"a", "b", "ab": [MW | null], "ba": [MW | null], "doc": "A61" | "A31" | ...}]}
build_eu_day.py adds the same per day ("capacity_ab", "capacity_ba" on each border).

    uv run python scripts/fetch_eu_capacity.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
TZ = ZoneInfo("Europe/Berlin")
SOURCE = (
    "ENTSO-E Transparency A61 forecasted transfer capacity (day-ahead), else A31 offered "
    "capacity (day-ahead implicit auction), per bidding-zone border; summed per country border"
)
Series = list[float | None]

# country borders made of several zone borders (the zones on each side)
ZONE_PAIRS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("DE", "DK"): [("DE-LU", "DK1"), ("DE-LU", "DK2")],
    ("DE", "NO"): [("DE-LU", "NO2")],
    ("DE", "SE"): [("DE-LU", "SE4")],
    ("DK", "NL"): [("DK1", "NL")],
    ("DK", "NO"): [("DK1", "NO2")],
    ("DK", "SE"): [("DK1", "SE3"), ("DK2", "SE4")],
    ("FI", "NO"): [("FI", "NO4")],
    ("FI", "SE"): [("FI", "SE1"), ("FI", "SE3")],
    ("LT", "SE"): [("LT", "SE4")],
    ("NL", "NO"): [("NL", "NO2")],
    ("NO", "SE"): [("NO1", "SE3"), ("NO3", "SE2"), ("NO4", "SE1"), ("NO4", "SE2")],
    ("PL", "SE"): [("PL", "SE4")],
    ("AT", "IT"): [("AT", "IT-North")],
    ("CH", "IT"): [("CH", "IT-North")],
    ("FR", "IT"): [("FR", "IT-North")],
    ("IT", "SI"): [("IT-North", "SI")],
    ("GR", "IT"): [("GR", "IT-South")],
    ("IT", "ME"): [("IT-Centre-South", "ME")],
}


# Borders inside the Core flow-based region: their day-ahead limits are set jointly, so an
# A61 figure published for one of them (e.g. 0 MW Germany > Netherlands) is not the limit
# the auction used. Left out.
CORE_FLOW_BASED = {
    frozenset(p)
    for p in [
        ("AT", "CZ"), ("AT", "DE"), ("AT", "HU"), ("AT", "SI"), ("BE", "DE"), ("BE", "FR"),
        ("BE", "NL"), ("CZ", "DE"), ("CZ", "PL"), ("CZ", "SK"), ("DE", "FR"), ("DE", "NL"),
        ("DE", "PL"), ("HR", "HU"), ("HR", "SI"), ("HU", "RO"), ("HU", "SI"), ("HU", "SK"),
        ("PL", "SK"),
    ]
}  # fmt: skip


def zone_of(iso: str) -> str | None:
    if iso in ("DE", "LU"):
        return "DE-LU"
    return iso if iso in entsoe.ZONE_EIC else None


def zone_pairs(a: str, b: str) -> list[tuple[str, str]]:
    if (a, b) in ZONE_PAIRS:
        return ZONE_PAIRS[(a, b)]
    if (b, a) in ZONE_PAIRS:
        return [(y, x) for x, y in ZONE_PAIRS[(b, a)]]
    za, zb = zone_of(a), zone_of(b)
    return [(za, zb)] if za and zb and za != zb else []


def one_direction(client: httpx.Client, za: str, zb: str, grid: entsoe.Grid) -> tuple[Series, str]:
    """MW from zone za to zone zb per slot, from A61, else A31 ('' when neither has data)."""
    for doc, extra in (
        ("A61", {"contract_MarketAgreement.Type": "A01"}),
        ("A31", {"auction.Type": "A01", "contract_MarketAgreement.Type": "A01"}),
    ):
        values = grid.empty()
        for window in grid.windows():
            root = entsoe.request(
                client,
                {
                    "documentType": doc,
                    "out_Domain": entsoe.ZONE_EIC[za],
                    "in_Domain": entsoe.ZONE_EIC[zb],
                    **extra,
                    **window,
                },
            )
            for _, got in entsoe.series_of(root, "quantity", grid):
                values = [v if v is not None else old for v, old in zip(got, values, strict=True)]
        if any(v is not None for v in values):
            return values, doc
    return grid.empty(), ""


def country_capacity(client: httpx.Client, grid: entsoe.Grid) -> list[dict]:
    """Every country border with a published capacity: {"a", "b", "ab", "ba", "doc"}."""
    jobs = []
    plan: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for a, b in entsoe.BORDERS:
        if frozenset((a, b)) in CORE_FLOW_BASED:
            continue
        pairs = zone_pairs(a, b)
        if not pairs:
            continue
        plan[(a, b)] = pairs
        for za, zb in pairs:
            jobs.append((f"{za}>{zb}", lambda za=za, zb=zb: one_direction(client, za, zb, grid)))
            jobs.append((f"{zb}>{za}", lambda za=za, zb=zb: one_direction(client, zb, za, grid)))
    got = entsoe.run(jobs)

    def total(keys: list[str]) -> Series:
        cols = [got[k][0] for k in keys]
        return [
            None if any(c[i] is None for c in cols) else round(sum(c[i] for c in cols), 1)  # type: ignore[misc]
            for i in range(grid.slots)
        ]

    out = []
    for (a, b), pairs in plan.items():
        ab = total([f"{za}>{zb}" for za, zb in pairs])
        ba = total([f"{zb}>{za}" for za, zb in pairs])
        if not any(v is not None for v in ab + ba):
            continue
        docs = sorted({got[f"{x}>{y}"][1] for x, y in pairs + [(q, p) for p, q in pairs]} - {""})
        out.append({"a": a, "b": b, "ab": ab, "ba": ba, "doc": "+".join(docs)})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    today = datetime.now(TZ).date()
    start = datetime(today.year, today.month, today.day, tzinfo=TZ).astimezone(UTC)
    grid = entsoe.Grid(start, start + timedelta(days=2))
    with httpx.Client(timeout=300) as client:
        borders = country_capacity(client, grid)
    out.mkdir(parents=True, exist_ok=True)
    (out / "capacity.json").write_text(
        json.dumps(
            {
                "source": SOURCE,
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "start": start.isoformat(),
                "step_s": entsoe.STEP,
                "slots": grid.slots,
                "borders": borders,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"capacity.json: {len(borders)} country borders with a capacity", flush=True)
    print(" ".join(f"{b['a']}-{b['b']}({b['doc']})" for b in borders), flush=True)


if __name__ == "__main__":
    main()
