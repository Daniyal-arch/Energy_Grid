"""US day-ahead hub prices (scripts/fetch_us_prices.py): hub-to-region rows and each
market's hour convention turned into the Eastern-Time hours of the US day files."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_us_day import build  # noqa: E402
from fetch_us import REGIONS  # noqa: E402
from fetch_us_prices import (  # noqa: E402
    HUBS,
    Hub,
    et_window,
    market_days,
    parse_caiso,
    parse_ercot,
    parse_isone,
    parse_miso,
    parse_nyiso,
    parse_spp,
    window_prices,
)


def test_one_hub_per_market_matched_to_its_region() -> None:
    rows = {(h.market, h.hub, h.region) for h in HUBS}
    assert rows == {
        ("CAISO", "TH_SP15_GEN-APND", "CAL"),
        ("ERCOT", "HB_HUBAVG", "TEX"),
        ("PJM", "WESTERN HUB", "MIDA"),
        ("MISO", "ILLINOIS.HUB", "MIDW"),
        ("SPP", "SPPSOUTH_HUB", "CENT"),
        ("NYISO", "N.Y.C.", "NY"),
        ("ISO-NE", ".H.INTERNAL_HUB", "NE"),
    }
    assert all(h.region in REGIONS for h in HUBS)
    assert len({h.region for h in HUBS}) == len(HUBS)


def utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)


def test_utc_markets() -> None:
    caiso = parse_caiso(
        [
            {
                "INTERVALSTARTTIME_GMT": "2026-10-09T07:00:00-00:00",
                "LMP_TYPE": "LMP",
                "MW": "50.63409",
            },
            {"INTERVALSTARTTIME_GMT": "2026-10-09T07:00:00-00:00", "LMP_TYPE": "MCE", "MW": "48"},
        ]
    )
    assert caiso == {utc(2026, 10, 9, 7): 50.63}
    spp = parse_spp(
        "Interval,GMTIntervalEnd,BAA,Settlement Location,Pnode,LMP,MLC,MCC,MEC\n"
        "10/09/2026 01:00:00,10/09/2026 06:00:00,SPP,SPPSOUTH_HUB,SPPSOUTH_H,6.0369,0,0,0\n"
        "10/09/2026 01:00:00,10/09/2026 06:00:00,SPP,AEC,SOUC,20.1619,0,0,0\n",
        "SPPSOUTH_HUB",
    )
    assert spp == {utc(2026, 10, 9, 5): 6.04}


def test_local_clocks() -> None:
    # MISO: hour ending 1 in EST = 05:00-06:00 UTC, also in summer
    line = "ILLINOIS.HUB,Hub,LMP," + ",".join(str(20 + i) for i in range(24))
    miso = parse_miso("Node,Type,Value,HE 1\n" + line, date(2026, 10, 9), "ILLINOIS.HUB")
    assert miso[utc(2026, 10, 9, 5)] == 20.0 and len(miso) == 24
    # NYISO: hour beginning 00:00 EDT = 04:00 UTC
    ny = parse_nyiso(
        "Time Stamp,Name,PTID,LBMP ($/MWHr)\n"
        "10/09/2026 00:00,N.Y.C.,61761,36.22\n10/09/2026 00:00,WEST,1,9\n",
        date(2026, 10, 9),
        "N.Y.C.",
    )
    assert ny == {utc(2026, 10, 9, 4): 36.22}
    # ISO-NE: hour ending 01 EDT = 04:00 UTC
    ne = parse_isone(
        '"D","10/09/2026","01","4000",".H.INTERNAL_HUB","HUB",25.03,25,0,0\n',
        date(2026, 10, 9),
        ".H.INTERNAL_HUB",
    )
    assert ne == {utc(2026, 10, 9, 4): 25.03}


def test_ercot_repeated_autumn_hour() -> None:
    # 2026-11-01: Central time falls back; HE 02:00 comes twice (CDT, then CST)
    rows = [
        {
            "DeliveryDate": "11/01/2026",
            "HourEnding": f"{h:02d}:00",
            "SettlementPoint": "HB_HUBAVG",
            "SettlementPointPrice": str(h),
            "DSTFlag": "N",
        }
        for h in range(1, 25)
    ]
    rows.append(
        {
            "DeliveryDate": "11/01/2026",
            "HourEnding": "02:00",
            "SettlementPoint": "HB_HUBAVG",
            "SettlementPointPrice": "99",
            "DSTFlag": "Y",
        }
    )
    got = parse_ercot(rows, date(2026, 11, 1), "HB_HUBAVG")
    assert len(got) == 25
    assert got[utc(2026, 11, 1, 5)] == 1.0  # 00:00 CDT
    assert got[utc(2026, 11, 1, 6)] == 2.0  # 01:00 CDT
    assert got[utc(2026, 11, 1, 7)] == 99.0  # 01:00 CST, the repeated hour
    assert got[utc(2026, 11, 1, 8)] == 3.0


class FakeMarkets:
    def __init__(self, data: dict[tuple[str, date], dict[datetime, float]]) -> None:
        self.data = data

    def day(self, h: Hub, d: date) -> dict[datetime, float]:
        return self.data.get((h.market, d), {})


def test_window_and_day_file() -> None:
    start, slots = et_window(date(2026, 10, 7))
    caiso = next(h for h in HUBS if h.market == "CAISO")
    # an Eastern day takes the end of the Pacific day before
    assert market_days(caiso, start, slots) == [date(2026, 10, 6), date(2026, 10, 7)]
    fake = FakeMarkets(
        {
            ("CAISO", date(2026, 10, 6)): {utc(2026, 10, 7, 4): 41.5},
            ("CAISO", date(2026, 10, 7)): {utc(2026, 10, 8, 3): -2.0},
        }
    )
    prices = window_prices(fake, start, slots)  # type: ignore[arg-type]
    assert list(prices) == ["TH_SP15_GEN-APND"]
    p = prices["TH_SP15_GEN-APND"]
    assert p["country"] == "CAL" and p["values"][0] == 41.5 and p["values"][23] == -2.0
    day = build(date(2026, 10, 7), [], [], [], prices)
    assert day["prices"] == prices
    lo = next(h for h in day["highlights"] if h["kind"] == "price_low")
    assert lo == {
        "slot": 23,
        "kind": "price_low",
        "zone": "TH_SP15_GEN-APND",
        "country": "CAL",
        "usd": -2.0,
        "name": "SP15",
    }
