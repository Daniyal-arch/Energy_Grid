"""US wholesale prices: the hourly day-ahead price at one trading hub per market, matched to
the EIA-930 region the market covers (scripts/probe_us_prices.py shows each source).

  market  hub (benchmark)     EIA region  source (no key unless named)
  CAISO   TH_SP15_GEN-APND    CAL         OASIS PRC_LMP, DAM, zip of CSV
  ERCOT   HB_HUBAVG           TEX         MIS public report 12331 (DAM settlement point prices)
  PJM     WESTERN HUB         MIDA        Data Miner 2 da_hrl_lmps (PJM_API_KEY; skipped on 401)
  MISO    ILLINOIS.HUB        MIDW        market reports, day-ahead ex-post LMP CSV
  SPP     SPPSOUTH_HUB        CENT        portal file browser, DA LMP by settlement location
  NYISO   N.Y.C. (zone J)     NY          damlbmp zone CSV
  ISO-NE  .H.INTERNAL_HUB     NE          day-ahead hourly LMP CSV

Hours. Every market's own hour is turned into the UTC hour it starts:
  CAISO   INTERVALSTARTTIME_GMT (given in UTC)
  SPP     GMTIntervalEnd minus one hour (given in UTC)
  PJM     datetime_beginning_utc (given in UTC)
  ERCOT   hour ending, Central prevailing time; DSTFlag Y marks the repeated autumn hour
  MISO    hour ending 1-24, Eastern Standard Time all year (MISO's market clock)
  NYISO   hour beginning, Eastern prevailing time (the repeated autumn hour appears twice)
  ISO-NE  hour ending, Eastern prevailing time ("02X" is the repeated autumn hour)
For the four local clocks the n-th hour of the market day starts n-1 hours after the
market day's local midnight (that midnight in UTC), which handles 23- and 25-hour days.

Values: $/MWh (USD), the hub's total LMP (SPP: LMP; ERCOT: settlement point price),
rounded to two decimals (CAISO serves five, SPP four, the others two).

Writes frontend/public/data/eu/us_prices.json: today and tomorrow in Eastern Time (the clock
of the US day files); tomorrow appears once the markets have published it (CAISO, ERCOT,
MISO, SPP, NYISO, ISO-NE publish the day-ahead result in the early afternoon the day before).

    uv run python scripts/fetch_us_prices.py
    uv run python scripts/fetch_us_prices.py --out store/eu
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")
EST = timezone(timedelta(hours=-5), "EST")
UA = {"User-Agent": "Europe-InfraAtlas/0.3 (research; contact via GitHub)"}
SOURCE = (
    "Day-ahead LMP at one trading hub per US market (CAISO, ERCOT, PJM, MISO, SPP, NYISO, ISO-NE)"
)

Hours = dict[datetime, float]  # UTC start of the hour -> $/MWh


@dataclass(frozen=True)
class Hub:
    market: str
    hub: str
    name: str
    region: str
    clock: str


HUBS = [
    Hub("CAISO", "TH_SP15_GEN-APND", "SP15", "CAL", "UTC"),
    Hub("ERCOT", "HB_HUBAVG", "Hub Average", "TEX", "CPT hour ending"),
    Hub("PJM", "WESTERN HUB", "Western Hub", "MIDA", "UTC"),
    Hub("MISO", "ILLINOIS.HUB", "Illinois Hub", "MIDW", "EST hour ending"),
    Hub("SPP", "SPPSOUTH_HUB", "SPP South Hub", "CENT", "UTC"),
    Hub("NYISO", "N.Y.C.", "N.Y.C. (zone J)", "NY", "EPT hour beginning"),
    Hub("ISO-NE", ".H.INTERNAL_HUB", "Internal Hub", "NE", "EPT hour ending"),
]


def ordinal_hours(day: date, tz: tzinfo, values: list[float]) -> Hours:
    """The n-th value of a market day starts n-1 hours after that day's local midnight."""
    start = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC)
    return {start + timedelta(hours=i): v for i, v in enumerate(values)}


def price(text: str) -> float:
    return round(float(text), 2)


def _csv_in_zip(content: bytes) -> list[dict[str, str]]:
    z = zipfile.ZipFile(io.BytesIO(content))
    with z.open(z.namelist()[0]) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))


# ---------------------------------------------------------------- parsers (tested offline)


def parse_caiso(rows: list[dict[str, str]]) -> Hours:
    return {
        datetime.fromisoformat(r["INTERVALSTARTTIME_GMT"]).astimezone(UTC): price(r["MW"])
        for r in rows
        if r.get("LMP_TYPE") == "LMP"
    }


def parse_spp(text: str, hub: str) -> Hours:
    out: Hours = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("Settlement Location", "").strip() != hub:
            continue
        end = datetime.strptime(r["GMTIntervalEnd"].strip(), "%m/%d/%Y %H:%M:%S")
        out[end.replace(tzinfo=UTC) - timedelta(hours=1)] = price(r["LMP"])
    return out


def parse_ercot(rows: list[dict[str, str]], day: date, hub: str) -> Hours:
    want = day.strftime("%m/%d/%Y")
    mine = [r for r in rows if r["SettlementPoint"] == hub and r["DeliveryDate"] == want]
    # hour ending "01:00".."24:00"; the repeated autumn hour comes twice, DSTFlag N then Y
    mine.sort(key=lambda r: (int(r["HourEnding"][:2]), r.get("DSTFlag", "N") == "Y"))
    return ordinal_hours(day, CT, [price(r["SettlementPointPrice"]) for r in mine])


def parse_miso(text: str, day: date, hub: str) -> Hours:
    for row in csv.reader(io.StringIO(text)):
        if len(row) > 3 and row[0] == hub and row[2] == "LMP":
            return ordinal_hours(day, EST, [price(v) for v in row[3:27] if v.strip()])
    return {}


def parse_nyiso(text: str, day: date, hub: str) -> Hours:
    rows = [r for r in csv.DictReader(io.StringIO(text)) if r.get("Name") == hub]
    return ordinal_hours(day, ET, [price(r["LBMP ($/MWHr)"]) for r in rows])


def parse_isone(text: str, day: date, hub: str) -> Hours:
    vals: list[float] = []
    for row in csv.reader(io.StringIO(text)):
        # "D", date, hour ending, location id, location name, type, LMP, energy, congestion, loss
        if len(row) > 6 and row[0] == "D" and row[4] == hub:
            vals.append(price(row[6]))
    return ordinal_hours(day, ET, vals)


def parse_pjm(items: list[dict], hub: str) -> Hours:
    return {
        datetime.fromisoformat(i["datetime_beginning_utc"]).replace(tzinfo=UTC): price(
            str(i["total_lmp_da"])
        )
        for i in items
        if str(i.get("pnode_name", "")).upper() == hub
    }


# ---------------------------------------------------------------- fetchers (one market day)


class Markets:
    """Downloads market days, each once per run (adjacent Eastern days share market days)."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.cache: dict[tuple[str, date], Hours] = {}
        self.ercot_docs: list[dict] | None = None
        self.pjm_off = False
        self.last_caiso = 0.0

    def day(self, h: Hub, d: date) -> Hours:
        key = (h.market, d)
        if key not in self.cache:
            fn: Callable[[Hub, date], Hours] = getattr(self, h.market.lower().replace("-", ""))
            try:
                self.cache[key] = fn(h, d)
            except Exception as err:  # noqa: BLE001 - one market failing leaves its hub empty
                print(
                    f"  {h.market} {d}: FAILED {err.__class__.__name__}: {str(err).splitlines()[0][:160]}"
                )
                self.cache[key] = {}
        return self.cache[key]

    def get(self, url: str, **kw: object) -> httpx.Response:
        r = self.client.get(url, **kw)  # type: ignore[arg-type]
        r.raise_for_status()
        return r

    def caiso(self, h: Hub, d: date) -> Hours:
        # OASIS asks for at most one request every 5 seconds
        time.sleep(max(0.0, 5.5 - (time.monotonic() - self.last_caiso)))
        start = datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("America/Los_Angeles"))
        end = start + timedelta(days=1)
        fmt = "%Y%m%dT%H:%M-0000"
        r = self.get(
            "https://oasis.caiso.com/oasisapi/SingleZip",
            params={
                "queryname": "PRC_LMP",
                "market_run_id": "DAM",
                "startdatetime": start.astimezone(UTC).strftime(fmt),
                "enddatetime": end.astimezone(UTC).strftime(fmt),
                "version": "12",
                "node": h.hub,
                "resultformat": "6",
            },
        )
        self.last_caiso = time.monotonic()
        return parse_caiso(_csv_in_zip(r.content))

    def spp(self, h: Hub, d: date) -> Hours:
        path = f"/{d.year}/{d.month:02d}/By_Day/DA-LMP-SL-{d:%Y%m%d}0100.csv"
        r = self.get(
            "https://portal.spp.org/file-browser-api/download/da-lmp-by-settlement-location",
            params={"path": path},
        )
        return parse_spp(r.text, h.hub)

    def ercot(self, h: Hub, d: date) -> Hours:
        if self.ercot_docs is None:
            r = self.get(
                "https://www.ercot.com/misapp/servlets/IceDocListJsonWS",
                params={"reportTypeId": "12331"},
            )
            docs = r.json()["ListDocsByRptTypeRes"]["DocumentList"]
            self.ercot_docs = [
                x["Document"] for x in docs if "_csv" in x["Document"]["ConstructedName"]
            ]
        # the day-ahead market for delivery day d clears on d-1; newest posting first
        posted = (d - timedelta(days=1)).strftime("%Y%m%d")
        for doc in sorted(self.ercot_docs, key=lambda x: x["ConstructedName"], reverse=True):
            if f".{posted}." not in doc["ConstructedName"]:
                continue
            z = self.get(
                "https://www.ercot.com/misdownload/servlets/mirDownload",
                params={"doclookupId": doc["DocID"]},
            )
            got = parse_ercot(_csv_in_zip(z.content), d, h.hub)
            if got:
                return got
        return {}

    def miso(self, h: Hub, d: date) -> Hours:
        r = self.get(f"https://docs.misoenergy.org/marketreports/{d:%Y%m%d}_da_expost_lmp.csv")
        return parse_miso(r.text, d, h.hub)

    def nyiso(self, h: Hub, d: date) -> Hours:
        r = self.get(f"https://mis.nyiso.com/public/csv/damlbmp/{d:%Y%m%d}damlbmp_zone.csv")
        return parse_nyiso(r.text, d, h.hub)

    def isone(self, h: Hub, d: date) -> Hours:
        r = self.get(
            f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/WW_DALMP_ISO_{d:%Y%m%d}.csv"
        )
        return parse_isone(r.text, d, h.hub)

    def pjm(self, h: Hub, d: date) -> Hours:
        if self.pjm_off:
            return {}
        key = os.environ.get("PJM_API_KEY")
        r = self.client.get(
            "https://api.pjm.com/api/v1/da_hrl_lmps",
            params={
                "rowCount": "100",
                "startRow": "1",
                "pnode_id": "51288",  # WESTERN HUB
                "datetime_beginning_ept": f"{d:%m/%d/%Y} 00:00to{d:%m/%d/%Y} 23:59",
                "fields": "datetime_beginning_utc,pnode_name,total_lmp_da",
            },
            headers={"Ocp-Apim-Subscription-Key": key} if key else {},
        )
        if r.status_code == 401:
            print("  PJM: 401 (no PJM_API_KEY / subscription key); skipping PJM")
            self.pjm_off = True
            return {}
        r.raise_for_status()
        return parse_pjm(r.json().get("items", []), h.hub)


def market_days(h: Hub, start: datetime, slots: int) -> list[date]:
    """The market's own days that overlap the window (UTC start, hourly slots)."""
    tz = {"CAISO": ZoneInfo("America/Los_Angeles"), "MISO": EST}.get(h.market)
    tz = tz or (CT if h.market in ("ERCOT", "SPP") else ET)
    first = start.astimezone(tz).date()
    last = (start + timedelta(hours=slots - 1)).astimezone(tz).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def window_prices(m: Markets, start: datetime, slots: int) -> dict[str, dict]:
    """{hub: {country: region, market, name, values: [$/MWh per hour of the window]}}."""
    out: dict[str, dict] = {}
    for h in HUBS:
        hours: Hours = {}
        for d in market_days(h, start, slots):
            hours.update(m.day(h, d))
        values = [hours.get(start + timedelta(hours=k)) for k in range(slots)]
        if any(v is not None for v in values):
            out[h.hub] = {"country": h.region, "market": h.market, "name": h.name, "values": values}
    return out


def et_window(day: date) -> tuple[datetime, int]:
    start = datetime(day.year, day.month, day.day, tzinfo=ET).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=ET).astimezone(UTC)
    return start, int((end - start).total_seconds()) // 3600


def client() -> httpx.Client:
    return httpx.Client(timeout=180, headers=UA, follow_redirects=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    today = datetime.now(ET).date()
    days = []
    with client() as c:
        m = Markets(c)
        for d in (today, today + timedelta(days=1)):
            start, slots = et_window(d)
            prices = window_prices(m, start, slots)
            print(
                f"{d}: {len(prices)} hubs {sorted(v['market'] for v in prices.values())}",
                flush=True,
            )
            if prices:
                days.append(
                    {
                        "date": d.isoformat(),
                        "start": start.isoformat(),
                        "slots": slots,
                        "prices": prices,
                    }
                )
    if not days:
        raise SystemExit("no market answered; keeping the last file")
    payload = {
        "source": SOURCE,
        "unit": "USD/MWh",
        "timezone": "America/New_York",
        "step_s": 3600,
        "fetched": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "hubs": {
            h.hub: {"market": h.market, "name": h.name, "region": h.region, "clock": h.clock}
            for h in HUBS
        },
        "days": days,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "us_prices.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
