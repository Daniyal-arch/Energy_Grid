"""Brief 26: the parsers of the new room-to-connect operators (scripts/build_connect_h26.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_connect_h26 as h  # noqa: E402


def test_top_kv_takes_the_highest_voltage() -> None:
    assert h.top_kv("110/35/10(20) kV") == 110.0
    assert h.top_kv("33/6.6kV") == 33.0
    assert h.top_kv(None) is None


def test_teias_rows_carry_the_centre_down_merged_cells() -> None:
    table = [
        ["2026 ... KALAN LİSANSSIZ ÜRETİM KAPASİTELERİ (01.10.2026)", None, None, None, None],
        [
            "İL",
            "TRANSFORMATÖR MERKEZİ",
            "BARA",
            "EDAŞ/OSB",
            "TAHSİS EDİLEBİLECEK GÜNCEL\nKAPASİTE (MWe)",
        ],
        ["ADANA", "ALADAĞ TM", "Tek", "Toroslar EDAŞ", "0,00"],
        ["ADANA", "MİSİS TM", "TR-B", "Toroslar EDAŞ", "2,00"],
        ["ADANA", "", "TR-C", "OSB", "0,65"],  # merged cell: the centre above
    ]
    rows, as_of = h.teias_rows(table)
    assert as_of == "2026-10-01"
    assert [r["name"] for r in rows] == ["ALADAĞ TM", "MİSİS TM TR-B", "MİSİS TM TR-C"]
    assert rows[2]["match_name"] == "MİSİS TM"
    assert [r["class"] for r in rows] == ["none", "available", "available"]
    assert rows[1]["mw_gen"] == 2.0


def test_enetze_rows_read_the_available_column() -> None:
    page = (
        "<p>Stand:\n 01.07.2026</p><table><tr><th>Umspannwerk</th><th>Gebuchte</th><th>Verfügbare</th></tr>"
        "<tr><td>Arnstein</td><td>19,0</td><td>0,0</td></tr><tr><td>Zettling</td><td>22,9</td><td>9,1</td></tr></table>"
    )
    rows, as_of = h.enetze_rows(page)
    assert as_of == "2026-07-01"
    assert [(r["name"], r["mw_gen"], r["class"]) for r in rows] == [
        ("Arnstein", 0.0, "none"),
        ("Zettling", 9.1, "available"),
    ]


def test_nie_rows_one_per_transformation_and_contact_stays_empty() -> None:
    teaser = (
        "<p>Voltage Level 1: 33/11kV</p>Available Demand Headroom (33/11kV): 2.55&nbsp;MVA "
        "Available Generation Headroom (33/11kV): 18.97&nbsp;MVA "
        "Available Demand Headroom (33/6.6kV): Contact for Info Available Generation Headroom (33/6.6kV): 0&nbsp;MVA"
    )
    rows = h.nie_rows(
        [{"id": "7", "name": "EAST CENTRAL", "location": [54.6, -5.9], "teaser": teaser}]
    )
    assert [(r["name"], r["mva_gen"], r["mva_load"], r["class"]) for r in rows] == [
        ("East Central 33/11kV", 18.97, 2.55, "available"),
        ("East Central 33/6.6kV", 0.0, None, "none"),
    ]
    assert rows[0]["lon"] == -5.9 and rows[0]["kv"] == 33.0


def test_lgeku_takes_the_newest_year_and_its_lowest_limit() -> None:
    f = {
        "Bus_Number": "1",
        "Station_Name": "A 138 kV",
        "Base_kV": "138",
        "Latitude": 37.0,
        "Longitude": -85.0,
    }
    rows = h.lgeku_rows([f | {"Year": "2026", "TrLim_min": 50.0}, f | {"Year": "2027", "TrLim_min": 80.0},
                         f | {"Year": "2027", "TrLim_min": 70.0}])  # fmt: skip
    assert len(rows) == 1 and rows[0]["mw_gen"] == 70.0


def test_avista_largest_step_without_an_overload() -> None:
    def f(step: float, avail: float) -> dict:
        return {
            "Bus_Number": "9",
            "Bus_Name": "X",
            "MW_Input": step,
            "MW_Available": avail,
            "Bus_Voltage": 115,
        }

    rows = h.avista_rows([f(20, 20), f(20, 20), f(40, 40), f(40, 0), f(80, 0)])
    assert rows[0]["mw_gen"] == 20 and rows[0]["class"] == "available"
    assert h.avista_rows([f(20, 0)])[0]["class"] == "none"


def test_swissgrid_reads_the_2026_base_and_keeps_blanks() -> None:
    table = [
        ["Substation/UW/Poste", None, "Prod. 2026", None, None],
        ["U", "Name/nom", "Base", "Flex. 10%", "Flex. 20%"],
        ["220 kV", "Aathal", "280", "280", "281"],
        ["380 kV", "Asphard", "", "", ""],
    ]
    assert h.swissgrid_table(table) == {("220 kV", "Aathal"): 280.0, ("380 kV", "Asphard"): None}


def test_vattenfall_later_horizons_are_limited() -> None:
    assert h.vf_class({"wind": 10.0, "_years": "1-2"}, "wind") == "available"
    assert h.vf_class({"wind": 10.0, "_years": "3-5"}, "wind") == "limited"
    assert h.vf_class({"wind": 0.0, "_years": "3-5"}, "wind") == "none"
