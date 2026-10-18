"""Imbalance prices per zone for the Prices tab (ENTSO-E A85, the last 30 days).

What a balance responsible party pays or receives for the energy it was short or long, per
15-minute settlement period, as each TSO publishes it to ENTSO-E (documentType A85, answered
as a zip of XML documents; scripts/probe_entsoe_imbalance.py). Two series per area: category
A05 (deficit) and A04 (excess); under single pricing they are equal, and some areas fill one
with 0 throughout (Italy's A05, 2026-10-17), flagged `all_zero` and not charted. Germany
(reBAP, published by the four TSOs on netztransparenz.de) and Greece publish none to ENTSO-E
(probe 2026-10-17); Poland publishes in PLN, kept as published.

Passed through: every price, in the source's currency. Computed (docs/DATA_SOURCES.md): per
zone, series and complete day (Europe/Brussels days, the app's day clock) the average, lowest and
highest price and the number of periods below zero, over the periods published; the last 7 days
at 15 minutes for the chart. The excess series is stored only where it differs from the deficit
one.

Writes frontend/public/data/eu/imbalance.json (the daily run puts it on the eu-days branch).

    uv run python scripts/build_imbalance.py [--out DIR] [--days 30]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import entsoe
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
BRUSSELS = ZoneInfo("Europe/Brussels")
CHART_DAYS = 7
SOURCE = "ENTSO-E Transparency Platform, imbalance prices (A85, 17.1.G)"


def fetch(client: httpx.Client, eic: str, grid: entsoe.Grid) -> list[ET.Element]:
    """The documents of one area over the grid (A85 answers a zip; an acknowledgement = none)."""
    docs: list[ET.Element] = []
    for window in grid.windows(days=60):
        q = {
            "securityToken": os.environ["ENTSOE_API_KEY"].strip(),
            "documentType": "A85",
            "controlArea_Domain": eic,
            **window,
        }
        r = None
        for attempt in range(6):
            try:
                r = client.get(entsoe.BASE, params=q)
            except httpx.TransportError as err:
                print(f"  {eic}: {type(err).__name__}, retrying", flush=True)
                r = None
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("retry-after") or 15 * (attempt + 1)))
                continue
            break
        if r is None or r.status_code != 200:
            print(
                f"  {eic}: gave up ({'no answer' if r is None else f'HTTP {r.status_code}'})",
                flush=True,
            )
            continue
        try:
            if r.content[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(r.content))
                docs += [ET.fromstring(z.read(n)) for n in z.namelist()]
            else:
                root = ET.fromstring(r.content)
                if not root.tag.endswith("Acknowledgement_MarketDocument"):
                    docs.append(root)
        except (zipfile.BadZipFile, ET.ParseError) as err:
            print(f"  {eic}: unreadable answer ({err})", flush=True)
    return docs


def series(
    docs: list[ET.Element], grid: entsoe.Grid
) -> tuple[dict[str, list[float | None]], str | None]:
    """The deficit (A05) and excess (A04) price on the grid, and the currency."""
    out: dict[str, list[float | None]] = {}
    currency = None
    for root in docs:
        ns = {"n": root.tag.split("}")[0].strip("{")}
        cats = [
            ts.findtext("n:Period/n:Point/n:imbalance_Price.category", default="", namespaces=ns)
            for ts in root.findall("n:TimeSeries", ns)
        ]
        for cat, (meta, values) in zip(
            cats, entsoe.series_of(root, "imbalance_Price.amount", grid), strict=False
        ):
            key = {"A05": "deficit", "A04": "excess"}.get(cat)
            if not key:
                continue
            currency = currency or meta.get("currency_Unit.name")
            merged = out.setdefault(key, grid.empty())
            for k, v in enumerate(values):
                if v is not None:
                    merged[k] = v
    return out, currency


def daily(
    values: list[float | None], seconds: list[int], days: list[str]
) -> list[list[float | int | None]]:
    """[average, lowest, highest, periods below zero, periods published] per Brussels day."""
    per: dict[str, list[float]] = {d: [] for d in days}
    for t, v in zip(seconds, values, strict=True):
        if v is None:
            continue
        d = datetime.fromtimestamp(t, tz=UTC).astimezone(BRUSSELS).date().isoformat()
        if d in per:
            per[d].append(v)
    rows: list[list[float | int | None]] = []
    for d in days:
        vs = per[d]
        rows.append(
            [round(sum(vs) / len(vs), 2), min(vs), max(vs), sum(v < 0 for v in vs), len(vs)]
            if vs
            else [None, None, None, 0, 0]
        )
    return rows


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    today = datetime.now(BRUSSELS).date()
    first = today - timedelta(days=args.days)
    start = datetime(first.year, first.month, first.day, tzinfo=BRUSSELS).astimezone(UTC)
    grid = entsoe.Grid(start, datetime.now(UTC))
    seconds = grid.seconds()
    # complete days only: the first of the window to yesterday
    days = [(first + timedelta(days=i)).isoformat() for i in range(args.days)]
    chart_from = datetime(today.year, today.month, today.day, tzinfo=BRUSSELS).astimezone(
        UTC
    ) - timedelta(days=CHART_DAYS)
    k0 = max(0, (int(chart_from.timestamp()) - grid.start) // entsoe.STEP)

    with httpx.Client(
        timeout=180, headers={"User-Agent": "InfraAtlas (github.com/Daniyal-arch/Energy_Grid)"}
    ) as client:
        got = entsoe.run(
            [(z, lambda eic=eic: fetch(client, eic, grid)) for z, eic in entsoe.ZONE_EIC.items()]
        )
    zones: dict[str, dict] = {}
    none: list[str] = []
    for zone in entsoe.ZONE_EIC:
        docs = got.get(zone) or []
        s, currency = series(docs, grid) if docs else ({}, None)
        s = {k: v for k, v in s.items() if any(x is not None for x in v)}
        if not s:
            none.append(zone)
            continue
        deficit, excess = s.get("deficit"), s.get("excess")
        if deficit and excess and all(a == b for a, b in zip(deficit, excess, strict=True)):
            excess = None

        def pack(v: list[float | None] | None) -> dict | None:
            if v is None:
                return None
            published = [x for x in v if x is not None]
            return {
                "all_zero": all(x == 0 for x in published),
                "daily": daily(v, seconds, days),
                "chart": v[k0:],
            }

        zones[zone] = {
            "currency": currency,
            "deficit": pack(deficit),
            "excess": pack(excess),
            "same": excess is None and deficit is not None,
        }
    payload = {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "days": days,
        "chart_start": datetime.fromtimestamp(grid.start + k0 * entsoe.STEP, tz=UTC).isoformat(),
        "step_s": entsoe.STEP,
        "zones": zones,
        "none": none,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "imbalance.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(
        f"{len(zones)} zones with imbalance prices, none from {none}; {path.stat().st_size / 1e6:.2f} MB"
    )


if __name__ == "__main__":
    main()
