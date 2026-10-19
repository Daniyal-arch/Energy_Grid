"""Wave 7 (brief 22): the pure parsing and shaping functions of the builders."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_connect_eu as ce  # noqa: E402
import wave7_common as w7  # noqa: E402

# ---------------------------------------------------------------- family 1, room to connect


def test_mw_class() -> None:
    assert [ce.mw_class(v) for v in (None, 0, 5, 10, 49.9, 50)] == [-1, 3, 2, 1, 1, 0]


def test_numbers_as_published() -> None:
    assert w7.number("1 234,5") == 1234.5
    assert w7.number("12.5") == 12.5
    assert w7.number("n/a") is None
    assert w7.number(True) is None


def test_esri_polygons_holes_and_islands() -> None:
    outer = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]  # clockwise: a polygon
    hole = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]]  # counter-clockwise
    island = [[2, 0], [2, 1], [3, 1], [3, 0], [2, 0]]
    polys = w7.esri_polygons([outer, hole, island])
    assert len(polys) == 2 and len(polys[0]) == 2 and len(polys[1]) == 1


def test_eso_arrays() -> None:
    page = "".join(
        f'var {js} = ["{a}","{b}"];'
        for js, (a, b) in {
            "pinID": ("4", "5"), "pinLatitude": ("42.6", "42.7"), "pinLogitude": ("23.3", "23.4"),
            "pinName_a": ("Подстанция 110kV  София", "Подстанция 220kV  Казичене"),
            "pinSkpgm400": ("0,000", "0,000"), "pinSkpgm220": ("0,000", "12,500"), "pinSkpgm110": ("305,000", "0,000"),
            "pinSkpgm20": ("0,000", "1,000"), "pinSkpdp400": ("0,000", "0,000"), "pinSkpdp220": ("0,000", "0,000"),
            "pinSkpdp110": ("22,000", "0,000"), "pinSkpp20": ("0,000", "0,000"), "need_extension": ("1", ""),
        }.items()
    )  # fmt: skip
    rows = ce.eso_rows(page)
    assert rows[0]["kv"] == 110 and rows[0]["gen_110kv_mw"] == 305.0 and rows[0]["needs_expansion"]
    assert rows[1]["gen_220kv_mw"] == 12.5 and not rows[1]["needs_expansion"]


def test_apg_table_carries_the_state_down() -> None:
    page = (
        "<p>Stand: 1. Oktober 2026 </p><table><tr><td>Umspannwerk</td></tr>"
        "<tr><td>UW Mattersburg</td><td rowspan=2>Burgenland</td><td>0 MW</td><td>10 MW</td><td>✓</td><td rowspan=2>Einspeisung: 2525 MW</td></tr>"
        "<tr><td>UW Parndorf</td><td>5 MW</td><td>0 MW</td><td></td></tr></table>"
    )
    stand, rows = ce.apg_rows(page)
    assert stand == "1. Oktober 2026"
    assert rows[1] == {
        "name": "UW Parndorf",
        "state": "Burgenland",
        "feedin_mw": 5.0,
        "offtake_mw": 0.0,
        "flexible": False,
        "applications": "Einspeisung: 2525 MW",
    }


def test_ceps_merge_kinds() -> None:
    a = {
        "Rozvodna_kod": "ALB4",
        "Rozvodna_nazev": "Albrechtice",
        "Y5": 3,
        "Y10": 1,
        "_lon": 18.5,
        "_lat": 49.8,
    }
    rows = ce.ceps_merge({"nonsync": [a], "load": [{**a, "Y5": 2}]})
    assert rows == [
        {
            "code": "ALB4",
            "name": "Albrechtice",
            "lon": 18.5,
            "lat": 49.8,
            "nonsync_2031": "not suitable",
            "nonsync_2036": "suitable",
            "load_2031": "conditionally suitable",
            "load_2036": "suitable",
        }
    ]


def test_cnmc_rows_utm_and_decimal_comma() -> None:
    text = (
        "﻿Gestor de red;Provincia;Municipio;Coordenada UTM X;Coordenada UTM Y;Subestación;Nivel de Tensión (kV);"
        "Capacidad disponible (MW);Capacidad ocupada (MW);Nombre Subestación;Provincia\n"
        "R1-299;04;04006;575906,01;4135997,40;510032846;25;1,50;16,55;ALBOX;Almería\n"
    )
    (r,) = ce.cnmc_rows(text)
    assert r["name"] == "ALBOX" and r["available_mw"] == 1.5 and r["kv"] == 25
    assert abs(r["lon"] - -2.15) < 0.02 and abs(r["lat"] - 37.38) < 0.02


def test_ecr_pick_matches_published_names() -> None:
    rec = {"Customer Site": "Solar farm", "Location (X-coordinate): Eastings (where data is held)": "400000",
           "Location (y-coordinate): Northings (where data is held)": "300000", "Energy Source 1": "Solar",
           "Already connected Registered Capacity (MW)": "0", "Accepted to Connect Registered Capacity (MW)": "49.9"}  # fmt: skip
    r = ce.ecr_pick(rec)
    assert (r["site"], r["east"], r["north"], r["source"], r["accepted_mw"]) == (
        "Solar farm",
        "400000",
        "300000",
        "Solar",
        "49.9",
    )


def test_tbw_tooltips() -> None:
    page = (
        '<div class="tooltip is-hidden tooltip-uw-engslatt tooltip-uw-type--yellow"><p>🟡 langfristig verfügbar</p>'
        "<p>Umspannwerk Engslatt</p><p>Spannungsebene: 380 kV</p><p>Verfügbare Einspeisekapazität: 500 – 1.000 MW</p></div>"
    )
    (r,) = ce.tbw_rows(page)
    assert (
        r["name"] == "Umspannwerk Engslatt"
        and r["status"] == "long-term"
        and r["feedin"] == "500 – 1.000 MW"
        and r["voltage"] == "380 kV"
    )
