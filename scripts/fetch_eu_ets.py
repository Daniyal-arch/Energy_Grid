"""Verified CO2 per installation in the EU Emissions Trading System, placed by official id.

Emissions: the Union Registry's public extracts (union-registry-data.ec.europa.eu, "Data
download", refreshed daily, no key):
  operators_daily                   installation, registry (country), activity, permit
  operators_yearly_activity_daily   verified emissions per installation and year (t CO2e)
Only stationary installations: aircraft (activity 10), maritime (50) and the fuel suppliers
of the new ETS2 (70) are left out. Verified emissions are passed through (tonnes).

Places: the EEA's register of industrial sites (EU Registry, CC BY 4.0) on Discodata SQL:
the ETS identifier each country reported for an installation
([IED].[latest].[ProductionInstallationETSIdentifier]) and that installation's coordinates
([IED].[latest].[ProductionInstallation]). An identifier joins when it is the registry's own
id ("AT000000000000001": country + installation id) or exactly the permit number. The newest
report wins. An installation without such a match is listed with its emissions but not placed
(no geocoding of names or addresses): scripts/probe_eu_ets.py counts them per country.

Writes frontend/public/data/eu/ets.json:
  {"fetched", "source", "snapshot", "years": [y...], "groups": [label...],
   "countries": {ISO: {"n", "placed", "t": [sum per year], "t_placed": newest-year sum placed}},
   "rows": [[ISO, registry id, name, group, [t per year | null], lon | null, lat | null]]}

    uv run python scripts/fetch_eu_ets.py [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
EXTRACTS = (
    "https://dlsclimabi.blob.core.windows.net/public-data/eutlpublic_prod/extracts/_all_extracts"
)
DISCO = "https://discodata.eea.europa.eu/sql"
SOURCE = (
    "Verified emissions: EU Union Registry public extracts (European Commission); "
    "locations: EEA industrial sites register (EU Registry, CC BY 4.0), joined by ETS id"
)
YEARS = 5  # the newest years shown per installation
LEFT_OUT = {"10", "50", "70"}  # aircraft, maritime, ETS2 regulated entities

# activity code (Annex I of the ETS Directive, phase 2 and phase 3+ codes) -> group
GROUPS = [
    "Combustion (power, heat, industry)",
    "Refineries",
    "Iron and steel",
    "Aluminium and other metals",
    "Cement and lime",
    "Glass, ceramics, minerals",
    "Pulp and paper",
    "Chemicals",
    "Other",
]
GROUP_OF = {
    **dict.fromkeys(["1", "20"], 0),
    **dict.fromkeys(["2", "21"], 1),
    **dict.fromkeys(["3", "4", "5", "22", "23", "24", "25"], 2),
    **dict.fromkeys(["26", "27", "28"], 3),
    **dict.fromkeys(["6", "29", "30"], 4),
    **dict.fromkeys(["7", "8", "31", "32", "33", "34"], 5),
    **dict.fromkeys(["9", "35", "36"], 6),
    **dict.fromkeys([str(c) for c in range(37, 45)], 7),
}
EUTL_ID = re.compile(r"^([A-Z]{2})0*(\d+)$")

Key = tuple[str, str]  # (registry, installation id)


def get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    for attempt in range(4):
        try:
            r = client.get(url, params=params)
            if r.status_code == 200:
                return r
        except httpx.TransportError:
            pass
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"{url}: no answer")


def extract(client: httpx.Client, path: str) -> list[dict]:
    text = gzip.decompress(get(client, f"{EXTRACTS}/{path}").content).decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text)))


def sql(client: httpx.Client, query: str, page_size: int = 20000) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        d = get(client, DISCO, {"query": query, "p": page, "nrOfHits": page_size}).json()
        if "errors" in d:
            raise SystemExit(f"Discodata: {d['errors']}")
        out += d["results"]
        if len(d["results"]) < page_size:
            return out
        page += 1


def tonnes(v: str) -> int | None:
    """Verified emissions as published (whole tonnes); "Excluded" and blanks are no value."""
    return int(float(v)) if v and v.replace(".", "", 1).isdigit() else None


def emissions(yearly: list[dict]) -> tuple[list[int], dict[Key, dict[int, int]]]:
    """Verified tonnes per installation and year; the newest years with reported values."""
    per: dict[Key, dict[int, int]] = {}
    for r in yearly:
        t = tonnes(r["VERIFIED_EMISSIONS"])
        if t is not None and r["PERIOD_YEAR"].isdigit():
            per.setdefault((r["REGISTRY_CODE"], r["INSTALLATION_IDENTIFIER"]), {})[
                int(r["PERIOD_YEAR"])
            ] = t
    # the extract carries rows for the years ahead (allocations) with zero emissions
    counts: dict[int, int] = {}
    for ys in per.values():
        for y, t in ys.items():
            if t > 0:
                counts[y] = counts.get(y, 0) + 1
    # a year counts once most installations have reported it (verified figures arrive in April)
    full = [y for y, n in counts.items() if n >= 0.5 * max(counts.values())]
    newest = max(full)
    return list(range(newest - YEARS + 1, newest + 1)), per


def match(
    ids: list[dict], stationary: dict[Key, dict], by_permit: dict[tuple[str, str], Key]
) -> dict[Key, tuple[float, float]]:
    """Installation -> (lon, lat) from the EEA register, by ETS id or permit number."""
    placed: dict[Key, tuple[float, float]] = {}
    for r in sorted(ids, key=lambda r: (r["y"], -r["id"])):  # newest report wins
        if r["lon"] is None or r["lat"] is None:
            continue
        raw = (r["ets"] or "").strip().upper()
        cc = "GB" if r["cc"] == "UK" else r["cc"]
        m = EUTL_ID.match(raw)
        key: Key | None = None
        if m and (m.group(1), m.group(2)) in stationary:
            key = (m.group(1), m.group(2))
        elif (cc, raw) in by_permit:
            key = by_permit[(cc, raw)]
        if key:
            placed[key] = (round(r["lon"], 5), round(r["lat"], 5))
    return placed


def build(ops: list[dict], yearly: list[dict], ids: list[dict]) -> dict:
    years, per = emissions(yearly)
    newest = years[-1]
    stationary = {
        (o["REGISTRY_CODE"], o["INSTALLATION_IDENTIFIER"]): o
        for o in ops
        if o["ACTIVITY_TYPE_CODE"] not in LEFT_OUT
        and any(
            per.get((o["REGISTRY_CODE"], o["INSTALLATION_IDENTIFIER"]), {}).get(y) for y in years
        )
    }
    by_permit = {(k[0], o["PERMIT_IDENTIFIER"].strip().upper()): k for k, o in stationary.items()}
    placed = match(ids, stationary, by_permit)
    rows: list[list] = []
    countries: dict[str, dict] = {}
    for k, o in stationary.items():
        t = [per.get(k, {}).get(y) for y in years]
        at = placed.get(k)
        rows.append(
            [
                k[0],
                k[1],
                o["INSTALLATION_NAME"].strip(),
                GROUP_OF.get(o["ACTIVITY_TYPE_CODE"], len(GROUPS) - 1),
                t,
                at[0] if at else None,
                at[1] if at else None,
            ]
        )
        c = countries.setdefault(k[0], {"n": 0, "placed": 0, "t": [0] * len(years), "t_placed": 0})
        c["n"] += 1
        c["placed"] += 1 if at else 0
        for i, v in enumerate(t):
            c["t"][i] += v or 0
        c["t_placed"] += (t[-1] or 0) if at else 0
    rows.sort(key=lambda r: -(r[4][-1] or 0))
    return {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "snapshot": ops[0]["SNAPSHOT_DATE"] if ops else None,
        "years": years,
        "newest": newest,
        "groups": GROUPS,
        "countries": dict(sorted(countries.items())),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out_dir: Path = parser.parse_args().out
    client = httpx.Client(timeout=180, follow_redirects=True)
    ops = extract(client, "operator/operators_daily.csv.gz")
    yearly = extract(client, "operators_yearly_activity/operators_yearly_activity_daily.csv.gz")
    ids = sql(
        client,
        "SELECT e.ETSIdentifier AS ets, p.id, p.countryCode AS cc, p.reportingYear AS y, "
        "p.x_4326 AS lon, p.y_4326 AS lat "
        "FROM [IED].[latest].[ProductionInstallationETSIdentifier] e "
        "JOIN [IED].[latest].[ProductionInstallation] p ON p.id = e.installationId",
    )
    out = build(ops, yearly, ids)
    n = len(out["rows"])
    placed = sum(1 for r in out["rows"] if r[5] is not None)
    t = sum(c["t"][-1] for c in out["countries"].values())
    tp = sum(c["t_placed"] for c in out["countries"].values())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ets.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"{n} installations ({out['years'][0]}-{out['newest']}), {placed} placed; "
        f"{out['newest']}: {t / 1e6:.1f} Mt, {tp / 1e6:.1f} Mt placed -> {path}"
    )


if __name__ == "__main__":
    main()
