"""Probe the ENTSOG Transparency Platform before the gas-flow map (no key).

1. Physical flows per point and direction (`operationaldatas`, "Physical Flow", day):
   units, the gas day's clock, how late the newest gas day is.
2. Paging (`limit`, `offset`) and how quickly the API answers several requests.
3. The point lists (`interconnections`, `connectionpoints`, `operatorpointdirections`):
   coordinates, countries on each side, point types.
4. Double reporting: pipe-in-pipe and double-reporting flags, VIPs next to their
   physical points, points with identical values every day.
5. `aggregatedData` (per country, operator and neighbour): does it match the points?
6. Both sides of each border: does the net flow agree, after the rules?
7. LNG entries per country against GIE ALSI send-out (`dossier.json`).

    uv run python scripts/probe_entsog.py

About 15 requests, ~40 MB (31 days of every point), ~30 s.
"""

from __future__ import annotations

import collections
import json
import statistics
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

API = "https://transparency.entsog.eu/api/v1"
client = httpx.Client(timeout=300)


def get(endpoint: str, **params: str) -> tuple[dict, float]:
    t0 = time.monotonic()
    r = client.get(f"{API}/{endpoint}", params={"limit": "-1", **params})
    r.raise_for_status()
    return r.json(), time.monotonic() - t0


def flows(start: date, end: date) -> list[dict]:
    d, s = get(
        "operationaldatas",
        indicator="Physical Flow",
        periodType="day",
        timezone="CET",
        **{"from": start.isoformat(), "to": end.isoformat()},
    )
    print(f"   operationaldatas {start}..{end}: {len(d['operationaldatas'])} rows in {s:.1f}s")
    return d["operationaldatas"]


today = datetime.now(UTC).date()
print(f"probe run {datetime.now(UTC):%Y-%m-%d %H:%M} UTC")

print("\n== 1. Physical flow rows")
recent = flows(today - timedelta(days=5), today + timedelta(days=1))
row = next(r for r in recent if r["value"] not in ("", None))
for k in (
    "pointKey",
    "pointLabel",
    "operatorLabel",
    "directionKey",
    "unit",
    "periodFrom",
    "periodTo",
    "value",
    "flowStatus",
    "lastUpdateDateTime",
):
    print(f"   {k}: {row[k]}")
print("   units:", collections.Counter(r["unit"] for r in recent))
valued = [r for r in recent if r["value"] not in ("", None)]
print(
    "   gas-day starts of rows with a value:",
    sorted(collections.Counter(r["periodFrom"] for r in valued).items()),
)
print(
    "   rows without a value (isNA) start at odd hours:",
    collections.Counter(
        r["periodFrom"][11:] for r in recent if r["value"] in ("", None)
    ).most_common(4),
)
for day, n in sorted(collections.Counter(r["periodFrom"][:10] for r in valued).items()):
    st = collections.Counter(r["flowStatus"] for r in valued if r["periodFrom"].startswith(day))
    print(f"   gas day {day}: {n} point-directions with a value {dict(st)}")

print("\n== 2. Paging and pace")
for lim in ("500", "2000", "-1"):
    d, s = get(
        "operationaldatas",
        indicator="Physical Flow",
        periodType="day",
        timezone="CET",
        limit=lim,
        **{"from": str(today - timedelta(days=2)), "to": str(today - timedelta(days=2))},
    )
    print(
        f"   limit={lim:>4}: meta.count={d['meta']['count']} meta.total={d['meta']['total']} rows={len(d['operationaldatas'])} ({s:.1f}s)"
    )
d, s = get(
    "operationaldatas",
    indicator="Physical Flow",
    periodType="day",
    timezone="CET",
    limit="500",
    offset="500",
    **{"from": str(today - timedelta(days=2)), "to": str(today - timedelta(days=2))},
)
print(
    f"   limit=500 offset=500: rows={len(d['operationaldatas'])} (limit counts rows before the server drops empty ones)"
)
codes = []
t0 = time.monotonic()
for _ in range(8):
    codes.append(client.get(f"{API}/balancingzones", params={"limit": "-1"}).status_code)
print(
    f"   8 requests back to back: HTTP {collections.Counter(codes)} in {time.monotonic() - t0:.1f}s"
)

print("\n== 3. Point lists")
ic = get("interconnections")[0]["interconnections"]
cp = {r["pointKey"]: r for r in get("connectionpoints")[0]["connectionpoints"]}
opd = get("operatorpointdirections")[0]["operatorpointdirections"]
print(
    f"   interconnections {len(ic)}, connectionpoints {len(cp)}, operatorpointdirections {len(opd)}"
)
print(
    "   coordinates: only tpMapX/tpMapY, e.g.",
    [(r["pointLabel"], r["tpMapX"], r["tpMapY"]) for r in list(cp.values())[:2]],
    "(the schematic map's pixels, not lon/lat)",
)
print(
    "   connectionpoints point types:",
    collections.Counter(r["infrastructureLabel"] for r in cp.values()).most_common(),
)
print(
    "   interconnection sides:",
    collections.Counter(
        (r["fromInfrastructureTypeLabel"], r["toInfrastructureTypeLabel"]) for r in ic
    ).most_common(8),
)
imports = sorted(
    {
        (r["importFromCountryKey"], r["pointLabel"])
        for r in cp.values()
        if r["isImport"] and r["hasData"]
    }
)
print("   points ENTSOG marks as imports, with the origin it names:", imports)
tap = sorted(
    {
        (r["pointLabel"], r["fromCountryKey"], r["toCountryKey"])
        for r in ic
        if "TAP" in (r["fromOperatorLabel"] or "") + (r["toOperatorLabel"] or "")
    }
)
print("   TAP sides in interconnections:", tap)
print(
    "   TAP in operatorpointdirections:",
    sorted(
        {
            (r["pointLabel"], r["tSOCountry"], r["adjacentCountry"])
            for r in opd
            if r["operatorKey"] == "AL-TSO-0001"
        }
    ),
)

print("\n== 4. Double reporting")
win = flows(today - timedelta(days=33), today)
meta: dict[tuple[str, str, str], dict] = {}
for r in opd:
    meta.setdefault((r["operatorKey"], r["pointKey"], r["directionKey"]), r)
pip = [m for m in meta.values() if m["pipeInPipeWithTsoKey"] and m["hasData"]]
dr = [m for m in meta.values() if m["doubleReportingWithTsoKey"] and m["hasData"]]
print(f"   pipe-in-pipe guests naming their host: {len(pip)}, double reporting flagged: {len(dr)}")
series: dict[tuple[str, str, str], dict[str, float]] = collections.defaultdict(dict)
for r in win:
    if r["value"] not in ("", None):
        series[(r["operatorKey"], r["pointKey"], r["directionKey"])][r["periodFrom"][:10]] = (
            float(r["value"]) / 1e6
        )
day0 = max(d for s in series.values() for d in s if sum(1 for x in series.values() if d in x) > 600)
for label in ("Dornum", "Emden (EPT1)"):
    print(f"   {label}, {day0}, entry, GWh/d:")
    for k, s in series.items():
        m = meta.get(k)
        if m and label in m["pointLabel"] and k[2] == "entry" and day0 in s:
            print(
                f"      {m['pointLabel']:<34} {m['operatorLabel']:<22} {s[day0]:8.1f}  pipe-in-pipe guest of: {m['pipeInPipeWithTsoKey'] or '-'}"
            )
groups = collections.defaultdict(list)
for k, m in meta.items():
    if (
        k in series
        and (m["pointType"] or "").startswith("Cross-Border Transmission")
        and not m["pipeInPipeWithTsoKey"]
    ):
        groups[(k[0], k[2], m["adjacentCountry"])].append(k)
for ks in groups.values():
    for i, a in enumerate(ks):
        for b in ks[i + 1 :]:
            if series[a] == series[b] and sum(series[a].values()) > 0:
                print(
                    f"   identical every day: {meta[a]['pointLabel']} = {meta[b]['pointLabel']} ({meta[a]['operatorLabel']}, {a[2]}, {len(series[a])} days)"
                )
gts = {
    meta[k]["pointLabel"]: series[k].get(day0)
    for k in series
    if k[0] == "NL-TSO-0001" and k[2] == "exit" and meta.get(k, {}).get("adjacentCountry") == "DE"
}
print(f"   GTS exits to Germany {day0}:", {k: round(v, 1) for k, v in gts.items() if v})
print(
    "   -> the VIPs bundle physical points of the same border (VIP TTF-THE-H = Bocholtz + Bunde - Bunde entries, net)"
)

print("\n== 5. aggregatedData")
agg = get(
    "aggregatedData", indicator="Physical Flow", timezone="CET", **{"from": day0, "to": day0}
)[0]["aggregatedData"]
print(
    f"   {len(agg)} rows, adjacent systems e.g. {collections.Counter(r['adjacentSystemsKey'] for r in agg).most_common(5)}"
)
for r in agg:
    if (
        r["operatorLabel"].startswith("Open Grid Europe")
        and r["directionKey"] == "entry"
        and r["adjacentSystemsKey"] == "Transmission"
    ):
        print(f"   OGE entry from Norway: {r['value'] / 1e6:.1f} GWh/d = sum of {r['pointsNames']}")
print(
    "   -> aggregatedData sums an operator's points as listed, Dornum twice: not usable as a country total"
)

print(
    "\n== 6. Both sides of each border (the rules of scripts/fetch_entsog.py), mean of the window"
)
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import fetch_entsog  # noqa: E402

ref = fetch_entsog.Reference(ic=ic, cp=cp, opd=opd)
reports = fetch_entsog.select_reports(win, ref)
days = sorted({d for rep in reports for d in rep.values})
sides = fetch_entsog.side_nets(reports, days)
for a, b in sorted({tuple(sorted(p)) for p in sides}):
    na, nb = sides.get((a, b)), sides.get((b, a))
    if na and nb:
        diff = statistics.mean(abs(x + y) for x, y in zip(na, nb, strict=True))
        print(
            f"   {a}-{b}: into {a} by {a}'s operators {statistics.mean(na):7.1f}, by {b}'s {-statistics.mean(nb):7.1f}  mean daily difference {diff:5.1f}"
        )

print("\n== 7. LNG entries per country (TSO entry at LNG points) against GIE ALSI send-out")
dossier = Path(__file__).parent.parent / "frontend/public/data/eu/dossier.json"
lng = json.loads(dossier.read_text()).get("lng", {}) if dossier.exists() else {}
common = [d for d in days if any(d == p[0] for p in lng.get("EU", {}).get("series", []))]
when = common[-1] if common else day0
by = collections.defaultdict(float)
for rep in reports:
    if rep.neighbour == "LNG" and when in rep.values:
        by[rep.country] += rep.values[when]
print(f"   gas day {when} (the newest in the bundled ALSI copy), GWh/d")
for iso in sorted(set(by) | (set(lng) - {"EU"})):
    alsi = dict(map(tuple, lng.get(iso, {}).get("series", [])))
    print(f"   {iso}: ENTSOG {by.get(iso, 0):7.1f}   ALSI send-out {alsi.get(when)}")
