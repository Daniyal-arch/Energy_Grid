"""Rules of scripts/build_us_units.py on small made-up CAMPD answers (no network)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_us_units import build, fuel_of, generators, quarter_end_before  # noqa: E402

DAY = date(2026, 6, 30)  # EDT: the Eastern-Time day starts 04:00 UTC


def attr(fid, uid, lon, lat, gens, fuel="Pipeline Natural Gas", name="Plant", state="TX"):
    return {
        "facilityId": fid,
        "unitId": uid,
        "facilityName": name,
        "stateCode": state,
        "longitude": lon,
        "latitude": lat,
        "primaryFuelInfo": fuel,
        "associatedGeneratorsAndNameplateCapacity": gens,
    }


def row(fid, uid, day, hour, load, co2, op=1.0):
    return {
        "facilityId": fid,
        "unitId": uid,
        "date": day,
        "hour": hour,
        "opTime": op,
        "grossLoad": load,
        "co2Mass": co2,
    }


def test_generators_and_fuels():
    assert generators("A1ST (191.8), A1CT (170.1)") == {"A1ST": 191.8, "A1CT": 170.1}
    assert generators(None) == {}
    assert fuel_of("Coal, Natural Gas") == "coal"
    assert fuel_of("Pipeline Natural Gas") == "gas"
    assert fuel_of("Diesel Oil") == "oil"
    assert fuel_of(None) == "other"


def test_quarter_end_before():
    assert quarter_end_before(date(2026, 9, 30)) == date(2026, 6, 30)
    assert quarter_end_before(date(2026, 3, 31)) == date(2025, 12, 31)


def test_standard_time_hours_land_on_the_eastern_day():
    # Houston (CST, UTC-6 all year in CAMPD): 2026-06-29 hour 22 = 04:00 UTC = slot 0
    attrs = [attr(1, "1", -95.4, 29.8, "1 (100)"), attr(1, "2", -95.4, 29.8, "ST (50), 1 (100)")]
    rows = [
        row(1, "1", "2026-06-29", 22, 80, 40.0),
        row(1, "2", "2026-06-29", 22, 30, 10.0),
        row(1, "1", "2026-06-29", 23, None, None, op=0.0),  # reported, not running
        row(1, "1", "2026-06-29", 21, 99, 99.0),  # 03:00 UTC: the day before
    ]
    f = build(DAY, rows, attrs, {1: "TEX"})
    assert f["slots"] == 24 and f["start"] == "2026-06-30T04:00:00+00:00"
    (plant,) = f["plants"]
    # capacity: distinct generators 1 and ST; fuel of the largest unit; region from EIA
    assert plant[2] == f["fuels"].index("gas") and plant[3] == "TEX" and plant[4] == 150.0
    assert f["output"][0][:3] == [110.0, 0.0, None]
    assert f["co2_t"][0][0] == round(50 * 0.90718474, 1)
