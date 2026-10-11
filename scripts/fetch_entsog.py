"""Europe's gas flows per gas day: across each border and into Europe from outside
(ENTSOG Transparency Platform, no key; scripts/probe_entsog.py).

Indicator "Physical Flow", period type day, in kWh/d per operator, point and direction
(`operationaldatas`). A gas day runs 06:00 to 06:00 Central European time (CET/CEST),
as ENTSOG publishes it. Rules (docs/DATA_SOURCES.md, "Gas flows"):

- Points: cross-border transmission points (borders and pipelines from outside) and LNG
  entry points. Storage, production, distribution, final consumers and trading points
  are left out.
- Sides: each operator's country and the country on the other side come from ENTSOG's
  interconnection list (`interconnections`); where a point is not in it, from the
  operator's own entry (`operatorpointdirections`). ENTSOG's "UK" is GB here.
- Double reports left out: a pipe-in-pipe operator that names the operator whose pipe
  it uses (that one reports the same gas), points flagged as double reporting, the
  physical points of an operator that reports a virtual interconnection point (VIP) for
  the same border (the VIP bundles them), and the points in KNOWN_DUPLICATES.
- A border is read from one side, both directions: the side whose own reports show the
  larger net flow into its country over the window (the importing side). The other
  side's net is kept beside it. Flows from outside Europe are read from the European
  side; LNG is the transmission operators' entry from the terminals.
- Sources outside Europe are named by the neighbouring system, with the origin ENTSOG
  gives an import point (`connectionpoints.importFromCountryKey`) where it differs:
  Kipi and Kipoi carry gas from Azerbaijan through Türkiye, Strandzha 2 Russian gas
  through TurkStream. Norway's gas arrives from the Norwegian shelf (Gassco's pipelines).
- Newest complete gas day: the newest day on which every point that reported the day
  before has reported too.

Values are passthrough (kWh/d / 10^6 = GWh/d, rounded to 1 MWh); per-direction sums,
net flows and the choice of side are computed here.

Writes frontend/public/data/eu/gas_flows.json:
  {"source", "fetched", "unit", "gas_day", "days": [31 dates], "nodes": {key: name},
   "pairs": [{"a", "b", "kind", "read_from", "ab", "ba", "net", "other_side_net",
              "points": [[point, operator, "a>b"|"b>a", GWh/d on gas_day]]}],
   "left_out": {...}}

    uv run python scripts/fetch_entsog.py [--out DIR] [--days 30]
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
API = "https://transparency.entsog.eu/api/v1"
SOURCE = "ENTSOG Transparency Platform: physical flow, daily, per point and direction"

# The countries on the map (frontend/src/app/geo.ts ANCHOR), less Norway: its gas
# arrives from the shelf, so Gassco's points are a source outside.
EUROPE = set(
    [
        "AL",
        "AT",
        "BA",
        "BE",
        "BG",
        "CH",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
        "GR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "ME",
        "MD",
        "MK",
        "NL",
        "PL",
        "PT",
        "RO",
        "RS",
        "SE",
        "SI",
        "SK",
        "UA",
        "XK",
    ]
)
NODES = {
    "NO": "Norwegian shelf",
    "DZ": "Algeria",
    "LY": "Libya",
    "AZ-TR": "Azerbaijan, via Türkiye",
    "RU-TR": "Russia, via TurkStream",
    "TR": "Türkiye",
    "RU": "Russia",
    "RU-BY": "Russia, via Belarus",
    "BY": "Belarus",
    "MA": "Morocco",
    # Tarifa: ENTSOG names Algeria (the pipeline was built for it); the gas now flows to Morocco
    "DZ-MA": "Morocco (Maghreb–Europe pipeline)",
    "SM": "San Marino",
    "LNG": "LNG terminals",
}
# Points that repeat another point of the same operator to the decimal every day
# (probe section 4). Left out; a warning is printed if they ever differ.
KNOWN_DUPLICATES = {
    ("DE-TSO-0009", "ITP-00525", "entry"): ("ITP-00126", "Dornum GASPOOL = Dornum / NETRA (OGE)"),
    ("DE-TSO-0009", "ITP-00525", "exit"): ("ITP-00126", "Dornum GASPOOL = Dornum / NETRA (OGE)"),
}
# Operators registered away from their pipeline (used only for points missing from
# the interconnection list): TAP AG is listed in Switzerland.
OPERATOR_COUNTRY = {"AL-TSO-0001": "GR"}


@dataclass
class Reference:
    ic: list[dict[str, Any]]
    cp: dict[str, dict[str, Any]]
    opd: list[dict[str, Any]]


@dataclass
class Report:
    """One operator's physical flow at one point in one direction."""

    operator: str
    operator_label: str
    point: str
    label: str
    direction: str  # entry | exit, seen from `country`
    country: str
    neighbour: str  # ISO code, a node key, or "LNG"
    vip: bool
    values: dict[str, float] = field(default_factory=dict)  # gas day -> GWh/d


def gb(c: str | None) -> str | None:
    return "GB" if c == "UK" else c


def sides(ref: Reference) -> dict[tuple[str, str], tuple[str, str]]:
    """(operator, point) -> (its country, the other side's country) from the interconnections."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for r in ref.ic:
        a, b = gb(r["fromCountryKey"]), gb(r["toCountryKey"])
        if not a or not b or a == b:
            continue
        if r["fromOperatorKey"]:
            out.setdefault((r["fromOperatorKey"], r["pointKey"]), (a, b))
        if r["toOperatorKey"]:
            out.setdefault((r["toOperatorKey"], r["pointKey"]), (b, a))
    return out


def node_of(neighbour: str, point: str, ref: Reference) -> str:
    """The key of a source outside Europe: the neighbour, with ENTSOG's origin if it differs."""
    origin = gb((ref.cp.get(point) or {}).get("importFromCountryKey"))
    return f"{origin}-{neighbour}" if origin and origin != neighbour else neighbour


def select_reports(rows: list[dict[str, Any]], ref: Reference) -> list[Report]:
    """The rows that count, grouped into reports, with the double reports left out."""
    meta: dict[tuple[str, str, str], dict[str, Any]] = {}
    adjacent: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    for r in ref.opd:
        k = (r["operatorKey"], r["pointKey"], r["directionKey"])
        meta.setdefault(k, r)
        if r["adjacentCountry"]:
            adjacent[k].add(gb(r["adjacentCountry"]) or "")
    side = sides(ref)
    reports: dict[tuple[str, str, str], Report] = {}
    for r in rows:
        if r["value"] in ("", None):
            continue
        k = (r["operatorKey"], r["pointKey"], r["directionKey"])
        m = meta.get(k)
        if m is None or k in KNOWN_DUPLICATES:
            continue
        kind = m["pointType"] or ""
        lng = kind.startswith("LNG Entry")
        if not (lng or kind.startswith("Cross-Border Transmission")):
            continue
        if m["pipeInPipeWithTsoKey"] or m["doubleReportingWithTsoKey"]:
            continue
        if lng:
            # the transmission operator's entry from the terminal (the LNG operator's
            # own rows report the same gas leaving it)
            if "-TSO-" not in r["operatorKey"]:
                continue
            own, nb = gb(m["tSOCountry"]), "LNG"
        elif (r["operatorKey"], r["pointKey"]) in side:
            own, nb = side[(r["operatorKey"], r["pointKey"])]
        else:
            own = OPERATOR_COUNTRY.get(r["operatorKey"]) or gb(m["tSOCountry"])
            others = adjacent[k] - {own}
            if len(others) != 1:
                continue
            nb = next(iter(others))
        if not own or own == nb:
            continue
        rep = reports.get(k)
        if rep is None:
            label = r["pointLabel"].strip()
            vip = (
                label.upper().startswith("VIP")
                or (ref.cp.get(r["pointKey"]) or {}).get("commercialType") == "Virtual"
            )
            rep = reports[k] = Report(
                r["operatorKey"],
                r["operatorLabel"].strip(),
                r["pointKey"],
                label,
                r["directionKey"],
                own,
                nb,
                vip,
            )
        rep.values[r["periodFrom"][:10]] = float(r["value"]) / 1e6
    # an operator's VIP for a border bundles its physical points there
    with_vip = {
        (x.operator, x.country, x.neighbour)
        for x in reports.values()
        if x.vip and any(x.values.values())
    }
    kept = [
        x for x in reports.values() if x.vip or (x.operator, x.country, x.neighbour) not in with_vip
    ]
    for (op, point, direction), (twin, what) in KNOWN_DUPLICATES.items():
        a = next(
            (x for x in kept if (x.operator, x.point, x.direction) == (op, twin, direction)), None
        )
        b = [
            r
            for r in rows
            if (r["operatorKey"], r["pointKey"], r["directionKey"]) == (op, point, direction)
            and r["value"] not in ("", None)
        ]
        if a and any(
            abs(a.values.get(r["periodFrom"][:10], 0) - float(r["value"]) / 1e6) > 1e-6 for r in b
        ):
            print(f"WARNING: {what} no longer holds; check KNOWN_DUPLICATES", file=sys.stderr)
    return kept


def side_nets(reports: list[Report], days: list[str]) -> dict[tuple[str, str], list[float]]:
    """Net flow into `country` from `neighbour` per day, by `country`'s own reports."""
    out: dict[tuple[str, str], list[float]] = {}
    for x in reports:
        if x.neighbour == "LNG":
            continue
        net = out.setdefault((x.country, x.neighbour), [0.0] * len(days))
        for i, d in enumerate(days):
            v = x.values.get(d, 0.0)
            net[i] += v if x.direction == "entry" else -v
    return out


def newest_complete(reports: list[Report], days: list[str]) -> str:
    """The newest gas day on which every report of the day before has a value."""
    for i in range(len(days) - 1, 0, -1):
        before = {id(x) for x in reports if days[i - 1] in x.values}
        if before and all(days[i] in x.values for x in reports if id(x) in before):
            return days[i]
    return days[0]


def r3(v: float | None) -> float | None:
    return None if v is None else round(v, 3)


def build_pairs(
    reports: list[Report], days: list[str], gas_day: str, ref: Reference
) -> list[dict[str, Any]]:
    """One record per border, source and LNG country, both directions as read."""
    groups: dict[tuple[str, str], list[Report]] = collections.defaultdict(list)
    for x in reports:
        if x.country not in EUROPE:
            continue
        if x.neighbour == "LNG":
            groups[("LNG", x.country)].append(x)
        elif x.neighbour in EUROPE:
            groups[tuple(sorted((x.country, x.neighbour)))].append(x)  # type: ignore[arg-type]
        else:
            groups[(node_of(x.neighbour, x.point, ref), x.country)].append(x)
    nets = side_nets(reports, days)
    pairs: list[dict[str, Any]] = []
    for (a, b), reps in sorted(groups.items()):
        kind = "lng" if a == "LNG" else "border" if a in EUROPE else "entry"
        other: list[float] | None = None
        if kind == "border":
            na, nb = nets.get((a, b)), nets.get((b, a))
            # the importing side: the larger mean net flow into its own country
            if na and nb:
                read = a if statistics.mean(na) >= statistics.mean(nb) else b
            else:
                read = a if na else b
            # the other side's net flow a>b (= into b), by its own reports
            if na and nb:
                other = nb if read == a else [-v for v in na]
            reps = [x for x in reps if x.country == read]
        else:
            read = b

        # a>b: into b when b reads (entries), out of a when a reads (exits)
        def into_b(x: Report) -> bool:
            return (x.country == b) == (x.direction == "entry")

        def total(pick: list[Report], d: str) -> float | None:
            vals = [x.values[d] for x in pick if d in x.values]
            return sum(vals) if vals else None

        fwd = [x for x in reps if into_b(x)]
        rev = [x for x in reps if not into_b(x)]
        ab = [total(fwd, d) for d in days]
        ba = [total(rev, d) for d in days]
        net = [
            None if p is None and q is None else (p or 0) - (q or 0)
            for p, q in zip(ab, ba, strict=True)
        ]
        pairs.append(
            {
                "a": a,
                "b": b,
                "kind": kind,
                "read_from": read,
                "ab": [r3(v) for v in ab],
                "ba": [r3(v) for v in ba],
                "net": [r3(v) for v in net],
                "other_side_net": None if other is None else [r3(v) for v in other],
                "points": [
                    [
                        x.label,
                        x.operator_label,
                        "a>b" if into_b(x) else "b>a",
                        r3(x.values.get(gas_day)),
                    ]
                    for x in sorted(reps, key=lambda x: -abs(x.values.get(gas_day, 0)))
                ],
            }
        )
    return pairs


def get(client: httpx.Client, endpoint: str, **params: str) -> dict[str, Any]:
    for attempt in range(4):
        try:
            r = client.get(f"{API}/{endpoint}", params={"limit": "-1", **params})
            if r.status_code == 200:
                return r.json()
        except httpx.TransportError:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"ENTSOG {endpoint} failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--days", type=int, default=30, help="days before the newest complete one")
    args = parser.parse_args()
    today = datetime.now(UTC).date()
    with httpx.Client(timeout=300, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        ref = Reference(
            ic=get(client, "interconnections")["interconnections"],
            cp={r["pointKey"]: r for r in get(client, "connectionpoints")["connectionpoints"]},
            opd=get(client, "operatorpointdirections")["operatorpointdirections"],
        )
        start = today - timedelta(days=args.days + 6)
        # the newest gas day that has ended started yesterday at 06:00
        last = today - timedelta(days=1)
        rows = get(
            client,
            "operationaldatas",
            indicator="Physical Flow",
            periodType="day",
            timezone="CET",
            **{"from": start.isoformat(), "to": last.isoformat()},
        )["operationaldatas"]
    print(f"{len(rows)} rows, gas days {start}..{last}")
    reports = select_reports(rows, ref)
    every = [(start + timedelta(days=i)).isoformat() for i in range((last - start).days + 1)]
    gas_day = newest_complete(reports, every)
    k = every.index(gas_day)
    days = every[max(0, k - args.days) : k + 1]
    pairs = build_pairs(reports, days, gas_day, ref)
    out = {
        "source": SOURCE,
        "fetched": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unit": "GWh/d",
        "gas_day": gas_day,
        "gas_day_note": "06:00 to 06:00 Central European time (CET/CEST), as ENTSOG publishes it",
        "days": days,
        "nodes": NODES,
        "pairs": pairs,
        "left_out": {"known_duplicates": sorted({v[1] for v in KNOWN_DUPLICATES.values()})},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "gas_flows.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    )
    big = sorted(pairs, key=lambda p: -abs(p["net"][-1] or 0))[:12]
    print(f"newest complete gas day {gas_day}; {len(pairs)} pairs")
    for p in big:
        print(
            f"  {p['a']:>6} > {p['b']:<3} net {p['net'][-1]:8.1f} GWh/d  (read from {p['read_from']}, {len(p['points'])} points)"
        )


if __name__ == "__main__":
    main()
