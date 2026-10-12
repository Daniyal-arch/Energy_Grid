"""EU ETS installations placed by official id (scripts/fetch_eu_ets.py) and LNG terminals
(scripts/fetch_alsi.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_alsi import in_operation, terminal  # noqa: E402
from fetch_eu_ets import build  # noqa: E402


def op(reg: str, iid: str, name: str, activity: str, permit: str) -> dict:
    return {
        "REGISTRY_CODE": reg,
        "INSTALLATION_IDENTIFIER": iid,
        "INSTALLATION_NAME": name,
        "ACTIVITY_TYPE_CODE": activity,
        "PERMIT_IDENTIFIER": permit,
        "SNAPSHOT_DATE": "2026-10-12",
    }


def yr(reg: str, iid: str, year: int, t: str) -> dict:
    return {
        "REGISTRY_CODE": reg,
        "INSTALLATION_IDENTIFIER": iid,
        "PERIOD_YEAR": str(year),
        "VERIFIED_EMISSIONS": t,
    }


def test_ets_places_by_registry_id_or_permit_only() -> None:
    ops = [
        op("AT", "16", "Steel works", "24", "P-16"),
        op("DE", "1606", "Lignite plant", "20", "14310-1093"),
        op("PL", "9", "Unreported", "29", "PL-9"),
        op("AT", "900", "Airline", "10", "A-1"),
    ]
    yearly = [
        yr(r, i, y, "1000")
        for r, i in [("AT", "16"), ("DE", "1606"), ("PL", "9"), ("AT", "900")]
        for y in range(2021, 2026)
    ]
    yearly += [yr("AT", "16", 2026, "0"), yr("AT", "16", 2030, "0")]  # rows for years ahead
    ids = [
        {"ets": "AT000000000000016", "id": 1, "cc": "AT", "y": 2023, "lon": 14.3, "lat": 48.3},
        {"ets": "14310-1093", "id": 2, "cc": "DE", "y": 2024, "lon": 6.6, "lat": 51.0},
        {
            "ets": "14310-1093",
            "id": 3,
            "cc": "DE",
            "y": 2020,
            "lon": 0.0,
            "lat": 0.0,
        },  # older report
        {"ets": "PL-OTHER", "id": 4, "cc": "PL", "y": 2024, "lon": 19.0, "lat": 51.0},
    ]
    out = build(ops, yearly, ids)
    assert out["years"] == [2021, 2022, 2023, 2024, 2025]
    rows = {r[1]: r for r in out["rows"]}
    assert set(rows) == {"16", "1606", "9"}  # the airline is left out
    assert (rows["16"][5], rows["16"][6]) == (14.3, 48.3)
    assert (rows["1606"][5], rows["1606"][6]) == (6.6, 51.0)  # the newest report wins
    assert rows["9"][5] is None  # no id match: listed, not placed
    assert rows["16"][3] == 2 and rows["1606"][3] == 0 and rows["9"][3] == 4
    assert out["countries"]["PL"] == {"n": 1, "placed": 0, "t": [1000] * 5, "t_placed": 0}


def test_alsi_terminal_rows_and_operation() -> None:
    assert in_operation(
        {"operational_start_date": "2011-01-01", "operational_end_date": None, "country": "BE"},
        "2026-10-12",
    )
    assert not in_operation({"operational_start_date": "3000-02-01", "country": "DE"}, "2026-10-12")
    assert not in_operation(
        {
            "operational_start_date": "2011-01-01",
            "operational_end_date": "2025-03-01",
            "country": "IT",
        },
        "2026-10-12",
    )
    assert not in_operation(
        {"operational_start_date": "2011-01-01", "country": "ES*"}, "2026-10-12"
    )
    f = {"eic": "21W1", "name": "Zeebrugge LNG Terminal", "type": "LAND", "country": "BE"}
    rows = [
        {
            "gasDayStart": "2026-10-10",
            "sendOut": "24.2",
            "inventory": {"gwh": "1500.25"},
            "dtrs": "390",
            "status": "E",
            "longitude": "3.1819",
            "latitude": "51.3529",
        },
        {
            "gasDayStart": "2026-10-09",
            "sendOut": "-",
            "inventory": {"gwh": "-"},
            "dtrs": "390",
            "status": "N",
            "longitude": "3.1819",
            "latitude": "51.3529",
        },
    ]
    t = terminal(f, "Fluxys LNG", rows)
    assert t is not None
    assert (t["lon"], t["lat"]) == (3.1819, 51.3529)
    assert t["series"] == [
        ["2026-10-09", None, None, 390.0, "N"],
        ["2026-10-10", 24.2, 1500.25, 390.0, "E"],
    ]
    assert terminal(f, "Fluxys LNG", rows[1:]) is None  # no send-out at all: left out
