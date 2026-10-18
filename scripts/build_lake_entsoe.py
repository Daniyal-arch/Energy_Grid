"""ENTSO-E history in the lake (docs/DATA_LAKE.md section 6): one ordered Parquet file per
table and year under lake/entsoe/, every value at the resolution ENTSO-E publishes.

    python scripts/build_lake_entsoe.py --year 2019 [--tables prices,load] --lake lake-out [--upload]
    python scripts/build_lake_entsoe.py --recent 3 --lake lake-out --upload
    python scripts/build_lake_entsoe.py --dims --lake lake-out --upload     (areas, units)

Runs in GitHub Actions (.github/workflows/lake-entsoe.yml; ENTSOE_API_KEY is a repo secret).
The client is scripts/entsoe.py (requests, retries, the area codes); `entsoe.points_of` reads
each series at its own resolution: no 15-min grid, no resampling, values as published.

Tables (partition `year`): prices (A44, per bidding zone; `sequence` keeps EXAA / intraday
auction series apart), load (A65: actual A16 and day-ahead A01), generation (A75; consumption
of pumps and batteries in its own column), forecast_wind_solar (A69, day-ahead), flows (A11,
per border direction), unit_output (A73), capacity (A68), transfer_capacity (A61 day-ahead
forecast and A31 offered capacity, both as published), outages (A80, every revision, one row
per point of the available-capacity curve; partition = year of the outage's start),
imbalance_price (A85, per zone: the deficit A05 and excess A04 price as published, in the
source's currency; partition `zone` and `year`).
Dimensions: areas, units (A71 per area, positions from JRC-PPDB where it names the unit).

`--recent N` fetches the last N days of the current year again and rewrites that year's
files (the old file is read from R2, the days are replaced).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import time
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import entsoe
import httpx
import lake

SOURCE = "ENTSO-E Transparency Platform (web-api.tp.entsoe.eu)"
LICENCE = "ENTSO-E Transparency Platform terms of use (re-use with attribution)"
# bidding zones before today's split (prices): Germany-Austria-Luxembourg until 2018-09-30
HISTORIC_ZONES = {"DE-AT-LU": "10Y1001A1001A63L"}
EXTRA_ZONES = {"IE-SEM": "10Y1001A1001A59C"}
# areas output per unit is asked for: every country, Germany per control area
DE_CONTROL = {
    "DE-50Hertz": "10YDE-VE-------2",
    "DE-Amprion": "10YDE-RWENET---I",
    "DE-TenneT": "10YDE-EON------1",
    "DE-TransnetBW": "10YDE-ENBW-----N",
}
UNIT_AREAS = {**{k: v for k, v in entsoe.AREA_EIC.items() if k != "DE"}, **DE_CONTROL}
# days per A73 request (scripts/probe_lake_entsoe.py)
A73_DAYS = int(os.environ.get("ENTSOE_A73_DAYS", "1"))
# days per A80 request: pages of 200 documents, at most 5,000 per query
A80_DAYS = 31
WINDOW_DAYS = 92
TABLES = [
    "prices",
    "load",
    "generation",
    "forecast_wind_solar",
    "flows",
    "unit_output",
    "capacity",
    "transfer_capacity",
    "outages",
    "imbalance_price",
]
# tables with one folder per zone and year (`zone=NL/year=2024/`)
ZONE_PARTITIONED = {"imbalance_price"}
# days per A85 request (scripts/build_imbalance.py asks 60 at a time)
A85_DAYS = 60
SEQ = "classificationSequence_AttributeInstanceComponent.position"

COLUMNS: dict[str, dict[str, str]] = {
    "prices": {
        "ts": "TIMESTAMPTZ",
        "area": "VARCHAR",
        "area_eic": "VARCHAR",
        "resolution_min": "INTEGER",
        "price": "DECIMAL(9,2)",
        "currency": "VARCHAR",
        "sequence": "VARCHAR",
    },
    "load": {
        "ts": "TIMESTAMPTZ",
        "area": "VARCHAR",
        "resolution_min": "INTEGER",
        "actual_mw": "FLOAT",
        "day_ahead_mw": "FLOAT",
    },
    "generation": {
        "ts": "TIMESTAMPTZ",
        "area": "VARCHAR",
        "psr_type": "VARCHAR",
        "resolution_min": "INTEGER",
        "generation_mw": "FLOAT",
        "consumption_mw": "FLOAT",
    },
    "forecast_wind_solar": {
        "ts": "TIMESTAMPTZ",
        "area": "VARCHAR",
        "psr_type": "VARCHAR",
        "resolution_min": "INTEGER",
        "forecast_mw": "FLOAT",
    },
    "flows": {
        "ts": "TIMESTAMPTZ",
        "out_area": "VARCHAR",
        "in_area": "VARCHAR",
        "resolution_min": "INTEGER",
        "mw": "FLOAT",
    },
    "unit_output": {
        "ts": "TIMESTAMPTZ",
        "unit_eic": "VARCHAR",
        "area": "VARCHAR",
        "resolution_min": "INTEGER",
        "mw": "FLOAT",
    },
    "capacity": {
        "ts": "TIMESTAMPTZ",
        "area": "VARCHAR",
        "psr_type": "VARCHAR",
        "capacity_mw": "FLOAT",
    },
    "transfer_capacity": {
        "ts": "TIMESTAMPTZ",
        "out_zone": "VARCHAR",
        "in_zone": "VARCHAR",
        "doc": "VARCHAR",
        "resolution_min": "INTEGER",
        "mw": "FLOAT",
    },
    "outages": {
        "mrid": "VARCHAR",
        "revision": "INTEGER",
        "doc_status": "VARCHAR",
        "zone": "VARCHAR",
        "asset_eic": "VARCHAR",
        "asset_name": "VARCHAR",
        "plant_eic": "VARCHAR",
        "plant_name": "VARCHAR",
        "psr_type": "VARCHAR",
        "type": "VARCHAR",
        "reason": "VARCHAR",
        "reason_text": "VARCHAR",
        "start": "TIMESTAMPTZ",
        "end": "TIMESTAMPTZ",
        "point_start": "TIMESTAMPTZ",
        "resolution_min": "INTEGER",
        "available_mw": "FLOAT",
        "nominal_mw": "FLOAT",
    },
    "imbalance_price": {
        "ts": "TIMESTAMPTZ",
        "zone": "VARCHAR",
        "category": "VARCHAR",
        "price": "DECIMAL(12,3)",
        "currency": "VARCHAR",
        "resolution_s": "INTEGER",
    },
}
SORT = {
    "prices": ["area", "ts"],
    "load": ["area", "ts"],
    "generation": ["area", "psr_type", "ts"],
    "forecast_wind_solar": ["area", "psr_type", "ts"],
    "flows": ["out_area", "in_area", "ts"],
    "unit_output": ["unit_eic", "ts"],
    "capacity": ["area", "psr_type", "ts"],
    "transfer_capacity": ["out_zone", "in_zone", "ts"],
    "outages": ["asset_eic", '"start"', "revision"],
    "imbalance_price": ["zone", "category", "ts"],
}
BLOOM = {"unit_output": ["unit_eic"], "outages": ["asset_eic"]}
TS_COL = {"outages": "start"}


# ---------------------------------------------------------------- rows from documents (tested)


def _iso(t: datetime) -> str:
    return t.isoformat()


def price_rows(zone: str, eic: str, found: list) -> list[tuple]:
    return [
        (_iso(t), zone, eic, res, v, meta.get("currency_Unit.name"), meta.get(SEQ))
        for meta, pts in found
        for t, res, v in pts
    ]


def load_rows(area: str, actual: list, day_ahead: list) -> list[tuple]:
    rows: dict[tuple, list] = {}
    for col, found in ((0, actual), (1, day_ahead)):
        for _, pts in found:
            for t, res, v in pts:
                rows.setdefault((_iso(t), res), [None, None])[col] = v
    return [(t, area, res, a, d) for (t, res), (a, d) in sorted(rows.items())]


def generation_rows(area: str, found: list) -> list[tuple]:
    rows: dict[tuple, list] = {}
    for meta, pts in found:
        # pumps and batteries charging come as outBiddingZone series: consumption
        col = 1 if "outBiddingZone_Domain.mRID" in meta else 0
        for t, res, v in pts:
            rows.setdefault((_iso(t), meta.get("psrType", ""), res), [None, None])[col] = v
    return [(t, area, psr, res, g, c) for (t, psr, res), (g, c) in sorted(rows.items())]


def forecast_rows(area: str, found: list) -> list[tuple]:
    return [
        (_iso(t), area, meta.get("psrType", ""), res, v) for meta, pts in found for t, res, v in pts
    ]


def flow_rows(out_area: str, in_area: str, found: list) -> list[tuple]:
    return [(_iso(t), out_area, in_area, res, v) for _, pts in found for t, res, v in pts]


def unit_rows(area: str, found: list, units: dict[str, dict]) -> list[tuple]:
    rows = []
    for meta, pts in found:
        uid = meta.get("unit")
        if not uid:
            continue
        units.setdefault(
            uid, {"name": meta.get("unit_name"), "psr_type": meta.get("psrType"), "area": area}
        )
        rows += [(_iso(t), uid, area, res, v) for t, res, v in pts]
    return rows


def capacity_rows(area: str, found: list) -> list[tuple]:
    return [(_iso(t), area, meta.get("psrType", ""), v) for meta, pts in found for t, _, v in pts]


def transfer_rows(za: str, zb: str, doc: str, found: list) -> list[tuple]:
    return [(_iso(t), za, zb, doc, res, v) for _, pts in found for t, res, v in pts]


def imbalance_rows(zone: str, docs: list[ET_Element]) -> list[tuple]:
    """A85 documents: one row per point and price category (A04 excess, A05 deficit), the
    category read from each Point; A03 curves written out like `entsoe.points_of`."""
    rows = []
    for root in docs:
        ns = {"n": root.tag.split("}")[0].strip("{")}
        for ts in root.findall("n:TimeSeries", ns):
            currency = ts.findtext("n:currency_Unit.name", default=None, namespaces=ns)
            variable = ts.findtext("n:curveType", default="A01", namespaces=ns) == "A03"
            for period in ts.findall("n:Period", ns):
                res = period.findtext("n:resolution", default="", namespaces=ns) or ""
                minutes = entsoe.resolution_minutes(res)
                start = period.findtext("n:timeInterval/n:start", namespaces=ns)
                end = period.findtext("n:timeInterval/n:end", namespaces=ns)
                if not start or not end or not minutes:
                    continue
                t0 = datetime.fromtimestamp(entsoe._ts(start), tz=UTC)
                t1 = datetime.fromtimestamp(entsoe._ts(end), tz=UTC)
                by_cat: dict[str, list[tuple[int, float]]] = {}
                for p in period.findall("n:Point", ns):
                    amount = p.findtext("n:imbalance_Price.amount", namespaces=ns)
                    if amount is None:
                        continue
                    cat = p.findtext("n:imbalance_Price.category", default="", namespaces=ns)
                    pos = int(p.findtext("n:position", namespaces=ns) or 0)
                    by_cat.setdefault(cat, []).append((pos, float(amount)))
                for cat, points in by_cat.items():
                    points.sort()
                    for i, (pos, value) in enumerate(points):
                        last = pos
                        if variable:
                            if i + 1 < len(points):
                                last = points[i + 1][0] - 1
                            else:
                                while entsoe._step(t0, res, last) < t1:
                                    last += 1
                        for k in range(pos, last + 1):
                            t = entsoe._step(t0, res, k - 1)
                            rows.append((_iso(t), zone, cat, value, currency, minutes * 60))
    return rows


def _dt(d: str | None, t: str | None) -> str | None:
    if not d:
        return None
    return f"{d}T{(t or '00:00:00Z')[:5]}:00+00:00"


def outage_rows(zone: str, docs: list[ET_Element]) -> list[tuple]:
    """A80 documents: one row per point of each available-capacity curve, every revision."""
    rows = []
    for root in docs:
        ns = {"n": root.tag.split("}")[0].strip("{")}
        mrid = root.findtext("n:mRID", namespaces=ns)
        rev = int(root.findtext("n:revisionNumber", default="0", namespaces=ns) or 0)
        status = root.findtext("n:docStatus/n:value", namespaces=ns)
        reason = root.find("n:Reason", ns)
        code = reason.findtext("n:code", namespaces=ns) if reason is not None else None
        text = reason.findtext("n:text", namespaces=ns) if reason is not None else None
        for ts in root.findall("n:TimeSeries", ns):
            res_ = "n:production_RegisteredResource"
            start = _dt(
                ts.findtext("n:start_DateAndOrTime.date", namespaces=ns),
                ts.findtext("n:start_DateAndOrTime.time", namespaces=ns),
            )
            end = _dt(
                ts.findtext("n:end_DateAndOrTime.date", namespaces=ns),
                ts.findtext("n:end_DateAndOrTime.time", namespaces=ns),
            )
            nominal = ts.findtext(f"{res_}.pSRType.powerSystemResources.nominalP", namespaces=ns)
            head = (
                mrid,
                rev,
                status,
                zone,
                ts.findtext(f"{res_}.pSRType.powerSystemResources.mRID", namespaces=ns),
                ts.findtext(f"{res_}.pSRType.powerSystemResources.name", namespaces=ns),
                ts.findtext(f"{res_}.mRID", namespaces=ns),
                ts.findtext(f"{res_}.name", namespaces=ns),
                ts.findtext(f"{res_}.pSRType.psrType", namespaces=ns),
                ts.findtext("n:businessType", namespaces=ns),
                code,
                text,
                start,
                end,
            )
            for period in ts.findall("n:Available_Period", ns):
                res = period.findtext("n:resolution", default="", namespaces=ns) or ""
                t0 = datetime.strptime(
                    period.findtext("n:timeInterval/n:start", namespaces=ns) or "",
                    "%Y-%m-%dT%H:%MZ",
                ).replace(tzinfo=UTC)
                for p in period.findall("n:Point", ns):
                    k = int(p.findtext("n:position", namespaces=ns) or 1)
                    rows.append(
                        (
                            *head,
                            _iso(entsoe._step(t0, res, k - 1)),
                            entsoe.resolution_minutes(res),
                            float(p.findtext("n:quantity", namespaces=ns) or 0),
                            float(nominal) if nominal else None,
                        )
                    )
    return rows


ET_Element = entsoe.ET.Element


# ---------------------------------------------------------------- fetching


def windows(start: datetime, end: datetime, days: int) -> list[dict[str, str]]:
    cuts = []
    t = start
    while t < end:
        cuts.append(t)
        t = min(end, t + timedelta(days=days))
    cuts.append(end)

    def stamp(x: datetime) -> str:
        return x.strftime("%Y%m%d%H%M")

    return [
        {"periodStart": stamp(a), "periodEnd": stamp(b)}
        for a, b in zip(cuts, cuts[1:], strict=False)
    ]


def fetch(
    client: httpx.Client, params: dict[str, str], wins: list[dict], tag: str = "quantity"
) -> list:
    found = []
    for w in wins:
        found += entsoe.points_of(entsoe.request(client, {**params, **w}), tag)
    return found


def a80_docs(client: httpx.Client, eic: str, wins: list[dict]) -> list[ET_Element]:
    """Every A80 document of a zone over the windows (zip pages of 200, `offset`)."""
    key = os.environ["ENTSOE_API_KEY"].strip()
    seen: dict[tuple, ET_Element] = {}
    for w in wins:
        for offset in range(0, 5000, 200):
            params = {
                "securityToken": key,
                "documentType": "A80",
                "biddingZone_Domain": eic,
                "offset": str(offset),
                **w,
            }
            r = None
            for attempt in range(5):
                try:
                    r = client.get(entsoe.BASE, params=params)
                except httpx.TransportError:
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    entsoe.OUTCOMES[f"HTTP {r.status_code}"] += 1
                    time.sleep(10 * (attempt + 1))
                    continue
                break
            if r is None or r.status_code != 200 or not r.content.startswith(b"PK"):
                entsoe.OUTCOMES[
                    "no data" if r is not None and r.status_code == 200 else "A80 failed"
                ] += 1
                break
            entsoe.OUTCOMES["200"] += 1
            z = zipfile.ZipFile(io.BytesIO(r.content))
            names = z.namelist()
            for name in names:
                root = entsoe.ET.fromstring(z.read(name))
                ns = {"n": root.tag.split("}")[0].strip("{")}
                k = (
                    root.findtext("n:mRID", namespaces=ns),
                    root.findtext("n:revisionNumber", namespaces=ns),
                )
                seen[k] = root
            if len(names) < 200:
                break
    return list(seen.values())


def a85_docs(client: httpx.Client, eic: str, wins: list[dict]) -> list[ET_Element]:
    """Every A85 document of an area over the windows (ENTSO-E answers a zip of XML documents,
    or an acknowledgement when it has none)."""
    key = os.environ["ENTSOE_API_KEY"].strip()
    docs: list[ET_Element] = []
    for w in wins:
        params = {"securityToken": key, "documentType": "A85", "controlArea_Domain": eic, **w}
        r = None
        for attempt in range(6):
            try:
                r = client.get(entsoe.BASE, params=params)
            except httpx.TransportError:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                entsoe.OUTCOMES[f"HTTP {r.status_code}"] += 1
                time.sleep(float(r.headers.get("retry-after") or 15 * (attempt + 1)))
                continue
            break
        if r is None or r.status_code != 200:
            entsoe.OUTCOMES["A85 failed"] += 1
            # a window left out would be a silent gap: the zone's job fails (counted, logged)
            raise RuntimeError(f"A85 {eic} {w['periodStart'][:8]}: no answer after 6 tries")
        if r.content[:2] == b"PK":
            entsoe.OUTCOMES["200"] += 1
            z = zipfile.ZipFile(io.BytesIO(r.content))
            docs += [entsoe.ET.fromstring(z.read(n)) for n in z.namelist()]
        else:
            root = entsoe.ET.fromstring(r.content)
            if root.tag.endswith("Acknowledgement_MarketDocument"):
                entsoe.OUTCOMES["no data"] += 1
            else:
                entsoe.OUTCOMES["200"] += 1
                docs.append(root)
    return docs


@dataclass
class Job:
    table: str
    label: str
    run: Callable[[], list[tuple]]


def jobs_for(
    client: httpx.Client, tables: list[str], start: datetime, end: datetime, units: dict
) -> Iterable[Job]:
    wins = windows(start, end, WINDOW_DAYS)
    year = start.year
    if "prices" in tables:
        zones = {**entsoe.ZONE_EIC, **EXTRA_ZONES}
        if year <= 2018:
            zones |= HISTORIC_ZONES
        for zone, eic in zones.items():
            p = {"documentType": "A44", "in_Domain": eic, "out_Domain": eic}
            yield Job(
                "prices",
                zone,
                lambda z=zone, e=eic, p=p: price_rows(z, e, fetch(client, p, wins, "price.amount")),
            )
    for area, eic in entsoe.AREA_EIC.items():
        if "load" in tables:
            a16 = {"documentType": "A65", "processType": "A16", "outBiddingZone_Domain": eic}
            a01 = {"documentType": "A65", "processType": "A01", "outBiddingZone_Domain": eic}
            yield Job(
                "load",
                area,
                lambda a=area, x=a16, y=a01: load_rows(
                    a, fetch(client, x, wins), fetch(client, y, wins)
                ),
            )
        if "generation" in tables:
            p = {"documentType": "A75", "processType": "A16", "in_Domain": eic}
            yield Job(
                "generation", area, lambda a=area, p=p: generation_rows(a, fetch(client, p, wins))
            )
        if "forecast_wind_solar" in tables:
            p = {"documentType": "A69", "processType": "A01", "in_Domain": eic}
            yield Job(
                "forecast_wind_solar",
                area,
                lambda a=area, p=p: forecast_rows(a, fetch(client, p, wins)),
            )
        if "capacity" in tables:
            p = {"documentType": "A68", "processType": "A33", "in_Domain": eic}
            one = windows(start, start + timedelta(days=1), 1)
            yield Job(
                "capacity", area, lambda a=area, p=p, w=one: capacity_rows(a, fetch(client, p, w))
            )
    if "flows" in tables:
        for a, b in entsoe.BORDERS:
            for x, y in ((a, b), (b, a)):
                if x in entsoe.AREA_EIC and y in entsoe.AREA_EIC:
                    p = {
                        "documentType": "A11",
                        "out_Domain": entsoe.AREA_EIC[x],
                        "in_Domain": entsoe.AREA_EIC[y],
                    }
                    yield Job(
                        "flows",
                        f"{x}>{y}",
                        lambda x=x, y=y, p=p: flow_rows(x, y, fetch(client, p, wins)),
                    )
    if "transfer_capacity" in tables:
        import fetch_eu_capacity

        pairs = sorted(
            {pair for a, b in entsoe.BORDERS for pair in fetch_eu_capacity.zone_pairs(a, b)}
        )
        for za, zb in pairs:
            for x, y in ((za, zb), (zb, za)):
                for doc, extra in (
                    ("A61", {"contract_MarketAgreement.Type": "A01"}),
                    ("A31", {"auction.Type": "A01", "contract_MarketAgreement.Type": "A01"}),
                ):
                    p = {
                        "documentType": doc,
                        "out_Domain": entsoe.ZONE_EIC[x],
                        "in_Domain": entsoe.ZONE_EIC[y],
                        **extra,
                    }
                    yield Job(
                        "transfer_capacity",
                        f"{doc} {x}>{y}",
                        lambda x=x, y=y, d=doc, p=p: transfer_rows(x, y, d, fetch(client, p, wins)),
                    )
    if "unit_output" in tables:
        uw = windows(start, end, A73_DAYS)
        for area, eic in UNIT_AREAS.items():
            p = {"documentType": "A73", "processType": "A16", "in_Domain": eic}
            for w in uw:
                yield Job(
                    "unit_output",
                    f"{area} {w['periodStart'][:8]}",
                    lambda a=area, p=p, w=w: unit_rows(a, fetch(client, p, [w]), units),
                )
    if "imbalance_price" in tables:
        iw = windows(start, end, A85_DAYS)
        zones = {**entsoe.ZONE_EIC, **(HISTORIC_ZONES if year <= 2018 else {})}
        for zone, eic in zones.items():
            yield Job(
                "imbalance_price",
                zone,
                lambda z=zone, e=eic: imbalance_rows(z, a85_docs(client, e, iw)),
            )
    if "outages" in tables:
        ow = windows(start, end, A80_DAYS)
        zones = {**entsoe.ZONE_EIC, **(HISTORIC_ZONES if year <= 2018 else {})}
        for zone, eic in zones.items():
            yield Job(
                "outages", zone, lambda z=zone, e=eic: outage_rows(z, a80_docs(client, e, ow))
            )


class Sink:
    """One CSV file per table; DuckDB reads them with the table's types."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        tmp.mkdir(parents=True, exist_ok=True)
        self.files: dict[str, tuple] = {}
        self.rows: dict[str, int] = {}

    def add(self, table: str, rows: list[tuple]) -> None:
        if table not in self.files:
            fh = (self.tmp / f"{table}.csv").open("w", encoding="utf-8", newline="")
            self.files[table] = (fh, csv.writer(fh))
            self.rows[table] = 0
        self.files[table][1].writerows(rows)
        self.rows[table] += len(rows)

    def close(self) -> None:
        for fh, _ in self.files.values():
            fh.close()


def collect(jobs: list[Job], sink: Sink, workers: int) -> dict[str, int]:
    """Run the jobs a few at a time; rows go to the sink as they arrive."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    t0 = time.time()
    done = 0
    failed: dict[str, int] = {}
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(j.run): j for j in jobs}
        for f in as_completed(futures):
            j = futures[f]
            try:
                sink.add(j.table, f.result())
            except Exception as err:  # noqa: BLE001 (a failed series is counted, not fatal)
                failed[j.table] = failed.get(j.table, 0) + 1
                print(f"  {j.table} {j.label}: {err!r}", flush=True)
            done += 1
            if done % 200 == 0 or done == len(jobs):
                n = sum(entsoe.OUTCOMES.values())
                rate = 60 * n / max(1, time.time() - t0)
                print(
                    f"  {done}/{len(jobs)} jobs, {n:,} requests ({rate:.0f}/min), {dict(entsoe.OUTCOMES)}",
                    flush=True,
                )
    return failed


def year_bounds(year: int, today: date) -> tuple[datetime, datetime]:
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = min(
        datetime(year + 1, 1, 1, tzinfo=UTC), datetime.combine(today, datetime.min.time(), UTC)
    )
    return start, end


def iso_of(code_col: str) -> str:
    """iso2 from an area or zone code (DE-LU -> DE, NO1 -> NO, DE-TenneT -> DE, IE-SEM -> IE)."""
    return f"left({code_col}, 2)"


def write_tables(
    con: duckdb.DuckDBPyConnection,
    lk: lake.Lake,
    sink: Sink,
    year: int,
    replace: tuple[datetime, datetime] | None = None,
    old: dict[str, list[Path]] | None = None,
) -> list[str]:
    """Write each table's year file; a table that fails is reported and the others still
    written (a year's fetch takes hours). Returns the tables that failed."""
    lake.iso_codes(con)
    failed = []
    for table, n in sink.rows.items():
        try:
            write_table(con, lk, sink, table, n, year, replace, old)
        except duckdb.Error as e:
            print(f"  {table}: NOT WRITTEN: {str(e)[:500]}", flush=True)
            failed.append(table)
    return failed


def write_table(
    con: duckdb.DuckDBPyConnection,
    lk: lake.Lake,
    sink: Sink,
    table: str,
    n: int,
    year: int,
    replace: tuple[datetime, datetime] | None,
    old: dict[str, list[Path]] | None,
) -> None:
    cols = COLUMNS[table]
    path = sink.tmp / f"{table}.csv"
    types = "{" + ", ".join(f"'{c}': '{t}'" for c, t in cols.items()) + "}"
    # Python's csv module doubles quotes inside values (outage reasons hold quotes and line
    # breaks): say so, rather than leave it to DuckDB's sniffer
    src = (
        f"read_csv('{path}', header = false, columns = {types}, delim = ',', "
        "quote = '\"', escape = '\"', new_line = '\\r\\n', max_line_size = 100000000)"
    )
    tcol = TS_COL.get(table, "ts")
    key = {
        "flows": "out_area",
        "transfer_capacity": "out_zone",
        "outages": "zone",
        "unit_output": "area",
        "imbalance_price": "zone",
    }.get(table, "area")
    # a year's file holds the points starting in it (UTC); installed capacity is asked once
    # per year and its period starts at local midnight (2023-12-31T23:00Z for 2024): all kept
    where = "TRUE" if table == "capacity" else f"year(\"{tcol}\" AT TIME ZONE 'UTC') = {year}"
    query = f"SELECT DISTINCT * FROM {src} WHERE {where}"
    if replace and old and old.get(table):
        files = ", ".join(f"'{p}'" for p in old[table])
        keep = ", ".join(f'"{c}"' for c in cols)
        if table == "outages":  # every revision: the new documents replace the same ones
            cond = "(mrid, revision) NOT IN (SELECT mrid, revision FROM new_rows)"
        else:
            cond = f"NOT (\"{tcol}\" >= '{replace[0].isoformat()}' AND \"{tcol}\" < '{replace[1].isoformat()}')"
        con.execute(f"CREATE OR REPLACE TEMP TABLE new_rows AS {query}")
        query = (
            f"SELECT {keep} FROM read_parquet([{files}], hive_partitioning = false) "
            f"WHERE {cond} UNION ALL SELECT * FROM new_rows"
        )
    if table in ZONE_PARTITIONED:
        con.execute(f"CREATE OR REPLACE TEMP TABLE zone_rows AS {query}")
        for (zone,) in con.execute("SELECT DISTINCT zone FROM zone_rows ORDER BY 1").fetchall():
            lk.write(
                con,
                table,
                f"""SELECT r.*, {iso_of("r.zone")} AS iso2, i.iso3, NULL::VARCHAR AS admin1
                    FROM zone_rows r LEFT JOIN iso_codes i ON i.iso2 = {iso_of("r.zone")}
                    WHERE r.zone = '{zone}'""",
                sort=SORT[table],
                bloom=BLOOM.get(table, []),
                partition={"zone": zone, "year": str(year)},
            )
        print(f"  {table}: {n:,} rows fetched", flush=True)
        return
    lk.write(
        con,
        table,
        f"""SELECT r.*, {iso_of("r." + key)} AS iso2, i.iso3, NULL::VARCHAR AS admin1
            FROM ({query}) r LEFT JOIN iso_codes i ON i.iso2 = {iso_of("r." + key)}""",
        sort=SORT[table],
        bloom=BLOOM.get(table, []),
        partition={"year": str(year)},
    )
    print(f"  {table}: {n:,} rows fetched", flush=True)


def lake_of(root: Path) -> lake.Lake:
    return lake.Lake(
        "entsoe", root, source=SOURCE, licence=LICENCE, script="scripts/build_lake_entsoe.py"
    )


def run_year(
    year: int, tables: list[str], root: Path, tmp: Path, workers: int, upload: bool
) -> Path:
    start, end = year_bounds(year, date.today())
    client = httpx.Client(timeout=300)
    units: dict[str, dict] = {}
    sink = Sink(tmp)
    jobs = list(jobs_for(client, tables, start, end, units))
    print(f"{year}: {len(jobs)} jobs over {start:%Y-%m-%d} .. {end:%Y-%m-%d}", flush=True)
    failed = collect(jobs, sink, workers)
    sink.close()
    con = duckdb.connect(str(tmp / "lake.duckdb"))
    lk = lake_of(root)
    failed_tables = write_tables(con, lk, sink, year)
    (tmp / "units_seen.json").write_text(json.dumps(units), encoding="utf-8")
    print(f"{year}: failed jobs {failed}; outcomes {dict(entsoe.OUTCOMES)}", flush=True)
    path = lk.finish()
    if upload:
        lk.upload(catalog=False)
    if failed_tables:
        raise SystemExit(f"{year}: tables not written: {failed_tables}")
    return path


def run_recent(days: int, root: Path, tmp: Path, workers: int, upload: bool) -> Path:
    """Fetch the last `days` days again and rewrite the current year's files."""
    today = date.today()
    end = datetime.combine(today, datetime.min.time(), UTC)
    start = max(end - timedelta(days=days), datetime(end.year, 1, 1, tzinfo=UTC))
    if end.month == 1 and end.day <= days:
        print("the year has just begun: run --year for last year too", flush=True)
    year = start.year
    tables = [t for t in TABLES if t != "capacity"]
    lk = lake_of(root)
    lk.pull_catalog()
    cat_path = root / "entsoe" / "_catalog.json"
    old: dict[str, list[Path]] = {}
    if cat_path.exists():
        cat = json.loads(cat_path.read_text(encoding="utf-8"))
        for table, t in cat["tables"].items():
            for f in t["files"]:
                if f"/year={year}/" in f:
                    local = tmp / "old" / f
                    local.parent.mkdir(parents=True, exist_ok=True)
                    key = f"{lake.BUCKET}/{lake.PREFIX}/entsoe/{f}"
                    if not lake.wrangler(
                        "r2", "object", "get", key, "--file", str(local), "--remote"
                    ):
                        raise SystemExit(f"could not read {key}")
                    old.setdefault(table, []).append(local)
    client = httpx.Client(timeout=300)
    units: dict[str, dict] = {}
    sink = Sink(tmp)
    collect(list(jobs_for(client, tables, start, end, units)), sink, workers)
    sink.close()
    con = duckdb.connect(str(tmp / "lake.duckdb"))
    failed_tables = write_tables(con, lk, sink, year, (start, end), old)
    path = lk.finish()
    if upload:
        lk.upload()
    if failed_tables:
        raise SystemExit(f"tables not written: {failed_tables}")
    return path


def a71_units(root: ET_Element | None, area: str) -> list[tuple]:
    """A71 (installed capacity per production unit): unit EIC, name, area, type and the
    first capacity point of each TimeSeries, wherever the document puts its Point."""
    if root is None:
        return []
    ns = {"n": root.tag.split("}")[0].strip("{")}
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        uid = ts.findtext("n:registeredResource.mRID", namespaces=ns)
        if not uid:
            continue
        q = ts.find(".//n:Point/n:quantity", ns)
        out.append(
            (
                uid,
                ts.findtext("n:registeredResource.name", namespaces=ns),
                area,
                ts.findtext("n:MktPSRType/n:psrType", namespaces=ns),
                float(q.text) if q is not None and q.text else None,
            )
        )
    return out


def build_dims(root: Path, tmp: Path, upload: bool) -> Path:
    """areas, and units: A71 (installed capacity per production unit) per area for the
    current year, positions from JRC-PPDB (build_eu_units.jrc_units) where it names the unit."""
    import build_eu_units

    con = duckdb.connect()
    lk = lake_of(root)
    rows = [
        (eic, code, "BZN", code)
        for code, eic in {**entsoe.ZONE_EIC, **EXTRA_ZONES, **HISTORIC_ZONES}.items()
    ]
    rows += [(eic, code, "CTY", code) for code, eic in entsoe.AREA_EIC.items()]
    rows += [(eic, code, "CTA", code) for code, eic in DE_CONTROL.items()]
    con.execute("CREATE TABLE a (area VARCHAR, code VARCHAR, kind VARCHAR, name VARCHAR)")
    con.executemany("INSERT INTO a VALUES (?, ?, ?, ?)", rows)
    lake.iso_codes(con)
    lk.write(
        con,
        "areas",
        "SELECT a.*, left(code, 2) AS country, left(code, 2) AS iso2, i.iso3 FROM a LEFT JOIN iso_codes i ON i.iso2 = left(code, 2)",
        sort=["code", "kind"],
    )
    client = httpx.Client(timeout=300)
    year = date.today().year
    w = windows(datetime(year, 1, 1, tzinfo=UTC), datetime(year, 1, 2, tzinfo=UTC), 1)
    units: list[tuple] = []
    for area, eic in UNIT_AREAS.items():
        root = entsoe.request(
            client, {"documentType": "A71", "processType": "A33", "in_Domain": eic, **w[0]}
        )
        units += a71_units(root, area)
    jrc = build_eu_units.jrc_units()
    con.execute(
        "CREATE TABLE u (unit_eic VARCHAR, name VARCHAR, area VARCHAR, psr_type VARCHAR, capacity_mw FLOAT)"
    )
    con.executemany("INSERT INTO u VALUES (?, ?, ?, ?, ?)", units)
    con.execute("CREATE TABLE j (unit_eic VARCHAR, plant_eic VARCHAR, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO j VALUES (?, ?, ?, ?)",
        [(k, r.get("eic_p") or None, float(r["lon"]), float(r["lat"])) for k, r in jrc.items()],
    )
    lk.write(
        con,
        "units",
        """SELECT DISTINCT u.unit_eic, j.plant_eic, u.name, u.area, u.psr_type, u.capacity_mw, j.lon, j.lat,
                  left(u.area, 2) AS iso2, i.iso3, NULL::VARCHAR AS admin1
           FROM u LEFT JOIN j USING (unit_eic) LEFT JOIN iso_codes i ON i.iso2 = left(u.area, 2)""",
        sort=["unit_eic"],
        bloom=["unit_eic"],
    )
    print(f"  units: {len(units):,} from A71, {len(jrc):,} JRC positions", flush=True)
    path = lk.finish()
    if upload:
        lk.upload(catalog=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int)
    parser.add_argument("--recent", type=int)
    parser.add_argument("--dims", action="store_true")
    parser.add_argument("--tables", default=",".join(TABLES))
    parser.add_argument("--lake", type=Path, default=Path("lake-out"))
    parser.add_argument("--tmp", type=Path, default=Path("entsoe-tmp"))
    parser.add_argument("--workers", type=int, default=entsoe.WORKERS)
    parser.add_argument("--merge", nargs="*", type=Path, help="merge partial catalogues, upload")
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    if args.merge is not None:
        lk = lake_of(args.lake)
        lk.pull_catalog()
        path = lk.finish(partials=args.merge)
        if args.upload:
            lk.upload(catalog_only=True)
        cat = json.loads(path.read_text(encoding="utf-8"))
        print("| table | rows | bytes |\n|---|---:|---:|")
        for name, t in sorted(cat["tables"].items()):
            print(f"| {name} | {t['rows']:,} | {t['bytes']:,} |")
        return
    if args.dims:
        build_dims(args.lake, args.tmp, args.upload)
    elif args.recent:
        run_recent(args.recent, args.lake, args.tmp, args.workers, args.upload)
    elif args.year:
        tables = [t for t in args.tables.split(",") if t]
        run_year(args.year, tables, args.lake, args.tmp, args.workers, args.upload)


if __name__ == "__main__":
    main()
