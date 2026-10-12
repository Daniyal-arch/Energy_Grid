"""Probe EU ETS installations: verified CO2 from the Union Registry and their location from
the EEA's industrial register, joined on official identifiers only.

1. Union Registry public extracts (daily; union-registry-data.ec.europa.eu "Data download"):
   operators_daily (installation, permit, activity, address; no coordinates) and
   operators_yearly_activity_daily (verified emissions per installation and year).
2. EEA Industrial Reporting (EU Registry on industrial sites) on Discodata SQL:
   [IED].[latest].[ProductionInstallation] (coordinates) and
   [IED].[latest].[ProductionInstallationETSIdentifier] (the ETS identifier each country
   reported for an installation: "AT000000000000001" style or the permit number).
3. How many installations and how many tonnes of 2025 verified CO2 can be placed.

    uv run python scripts/probe_eu_ets.py
"""

from __future__ import annotations

import csv
import gzip
import io
import re
import sys
from collections import Counter, defaultdict

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
c = httpx.Client(timeout=180, follow_redirects=True)
EXTRACTS = (
    "https://dlsclimabi.blob.core.windows.net/public-data/eutlpublic_prod/extracts/_all_extracts"
)
DISCO = "https://discodata.eea.europa.eu/sql"


def extract(path: str) -> list[dict]:
    r = c.get(f"{EXTRACTS}/{path}")
    print(f"  {path}: HTTP {r.status_code}, {len(r.content) / 1e6:.1f} MB")
    text = gzip.decompress(r.content).decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def sql(query: str, page_size: int = 20000) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        r = c.get(DISCO, params={"query": query, "p": page, "nrOfHits": page_size})
        d = r.json()
        if "errors" in d:
            raise SystemExit(d)
        out += d["results"]
        if len(d["results"]) < page_size:
            return out
        page += 1


print("== 1. Union Registry extracts")
ops = extract("operator/operators_daily.csv.gz")
yearly = extract("operators_yearly_activity/operators_yearly_activity_daily.csv.gz")
print("  snapshot", ops[0]["SNAPSHOT_DATE"], "|", len(ops), "accounts,", len(yearly), "rows")
v25: dict[tuple[str, str], float] = {}
for r in yearly:
    if r["PERIOD_YEAR"] == "2025" and r["VERIFIED_EMISSIONS"].isdigit():
        v25[(r["REGISTRY_CODE"], r["INSTALLATION_IDENTIFIER"])] = float(r["VERIFIED_EMISSIONS"])
stationary = {
    (o["REGISTRY_CODE"], o["INSTALLATION_IDENTIFIER"]): o
    for o in ops
    if o["ACTIVITY_TYPE_CODE"] != "10"
    and v25.get((o["REGISTRY_CODE"], o["INSTALLATION_IDENTIFIER"]), 0) > 0
}
total = sum(v25[k] for k in stationary)
print(
    f"  stationary installations with 2025 verified CO2 > 0: {len(stationary)}, {total / 1e6:.1f} Mt"
)
by_permit: dict[tuple[str, str], tuple[str, str]] = {}
for k, o in stationary.items():
    by_permit[(k[0], o["PERMIT_IDENTIFIER"].strip().upper())] = k

print("\n== 2. EEA Industrial Reporting on Discodata")
ids = sql(
    "SELECT e.ETSIdentifier AS ets, p.id, p.countryCode AS cc, p.reportingYear AS y, "
    "p.x_4326 AS lon, p.y_4326 AS lat, p.installationName AS name, p.IEDAnnexIMainActivity AS act "
    "FROM [IED].[latest].[ProductionInstallationETSIdentifier] e "
    "JOIN [IED].[latest].[ProductionInstallation] p ON p.id = e.installationId"
)
print(
    "  rows (installation x reporting year):",
    len(ids),
    "years",
    Counter(r["y"] for r in ids).most_common(),
)
print("  countries:", sorted(Counter(r["cc"] for r in ids).items()))

EUTL_ID = re.compile(r"^([A-Z]{2})0*(\d+)$")
placed: dict[tuple[str, str], dict] = {}
how = Counter()
for r in sorted(ids, key=lambda r: r["y"]):  # newest report wins
    raw = (r["ets"] or "").strip().upper()
    cc = "GB" if r["cc"] == "UK" else r["cc"]
    key = None
    m = EUTL_ID.match(raw)
    if m and (m.group(1), m.group(2)) in stationary:
        key, kind = (m.group(1), m.group(2)), "eutl id"
    elif (cc, raw) in by_permit:
        key, kind = by_permit[(cc, raw)], "permit"
    if key and r["lon"] is not None:
        placed[key] = r
        how[kind] += 1
print("  matched rows by", dict(how))
t_placed = sum(v25[k] for k in placed)
print(
    f"  placed: {len(placed)} of {len(stationary)} installations, {t_placed / 1e6:.1f} of {total / 1e6:.1f} Mt"
)
per = defaultdict(lambda: [0, 0, 0.0, 0.0])
for k in stationary:
    p = per[k[0]]
    p[1] += 1
    p[3] += v25[k]
    if k in placed:
        p[0] += 1
        p[2] += v25[k]
for cc, (n, of, t, tt) in sorted(per.items(), key=lambda x: -x[1][3]):
    print(
        f"   {cc}: {n:5d}/{of:5d} installations, {t / 1e6:6.1f}/{tt / 1e6:6.1f} Mt ({100 * t / tt:3.0f} %)"
    )
top = sorted(stationary, key=lambda k: -v25[k])[:15]
print("\n  15 largest emitters 2025:")
for k in top:
    p = placed.get(k)
    where = f"{p['lon']:.3f},{p['lat']:.3f} '{p['name']}'" if p else "NOT PLACED"
    print(
        f"   {k[0]} {k[1]:>7} {v25[k] / 1e6:5.1f} Mt  {stationary[k]['INSTALLATION_NAME'][:40]:40}  {where}"
    )
