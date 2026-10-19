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


# ---------------------------------------------------------------- family 2, every unit

import build_registers as br  # noqa: E402


def test_group_of() -> None:
    assert br.group_of("Wind Offshore") == "wind_offshore"
    assert br.group_of("Battery") == "storage"
    assert br.group_of("Solar Photovoltaics") == "solar"
    assert br.group_of("Hydraulique", "Fil de l'eau") == "hydro"
    assert br.group_of("CCGT (Natural Gas)") == "gas"
    assert br.group_of("Something else") == "other"


def test_repd_points_keeps_live_projects() -> None:
    from pyproj import Transformer

    tr = Transformer.from_crs(27700, 4326, always_xy=True)
    text = (
        "Ref ID,Site Name,Operator (or Applicant),Technology Type,Storage Type,Installed Capacity (MWelec),Development Status (short),X-coordinate,Y-coordinate,Operational,Country\n"
        "1,Farm A,Op,Wind Onshore,,49.9,Operational,302219,166320,01/05/2007,Wales\n"
        "2,Farm B,Op,Solar Photovoltaics,,20,Application Refused,302219,166320,,Wales\n"
        "3,Store C,Op,Battery,Battery,100,Awaiting Construction,302219,166320,,Wales\n"
    )
    rows = br.repd_points(text, tr)
    assert [(r["name"], r["status"], r["group"], r["year"]) for r in rows] == [
        ("Farm A", "operating", "wind", 2007),
        ("Store C", "permitted", "storage", None),
    ]
    assert abs(rows[0]["lon"] - -3.40) < 0.02 and abs(rows[0]["lat"] - 51.39) < 0.02


def test_totals_by_status_and_group() -> None:
    pts = [
        ["a", 0, 0, "wind", 2.0, "operating", None, "x"],
        ["b", 0, 0, "wind", 3.0, "operating", None, "x"],
        ["c", 0, 0, "solar", None, "planning", None, "x"],
    ]
    assert br.totals(pts) == {"operating": {"wind": [2, 5.0]}, "planning": {"solar": [1, 0.0]}}


# ---------------------------------------------------------------- family 3, live mix and CO₂

import fetch_live_co2 as lc  # noqa: E402


def test_fr_series_keeps_co2_rows_in_order() -> None:
    recs = [
        {
            "date_heure": "2026-10-19T10:15:00+00:00",
            "taux_co2": 21,
            "nucleaire": 40000,
            "gaz": 1500,
            "eolien": None,
        },
        {"date_heure": "2026-10-19T10:00:00+00:00", "taux_co2": 20, "nucleaire": 40100},
        {"date_heure": "2026-10-19T10:30:00+00:00", "taux_co2": None, "nucleaire": 40200},
    ]
    assert lc.fr_series(recs) == [
        ["2026-10-19T10:00:00+00:00", 20, {"nucleaire": 40100}],
        ["2026-10-19T10:15:00+00:00", 21, {"nucleaire": 40000, "gaz": 1500}],
    ]


def test_es_parts_factor_and_technologies() -> None:
    d = {"included": [
        {"type": "Ciclo combinado", "attributes": {"values": [{"value": 46023.9, "datetime": "2026-10-19T00:00:00.000+02:00"}]}},
        {"type": "Total tCO2 eq.", "attributes": {"values": [{"value": 1.0, "datetime": "2026-10-19T00:00:00.000+02:00"}]}},
        {"type": "tCO2 eq./MWh", "attributes": {"values": [{"value": 0.1025, "datetime": "2026-10-18T00:00:00.000+02:00"}]}},
    ]}  # fmt: skip
    factor, tech = lc.es_parts(d)
    assert factor == [["2026-10-18", 0.1025]] and tech == {
        "Ciclo combinado": [["2026-10-19", 46023.9]]
    }
