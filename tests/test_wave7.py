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


# ---------------------------------------------------------------- family 4, redispatch and congestion

import xml.etree.ElementTree as ET  # noqa: E402

import build_congestion as bc  # noqa: E402

A63 = """<Redispatching_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:redispatchingdocument:7:0">
<mRID>x</mRID><revisionNumber>1</revisionNumber><type>A63</type>
<TimeSeries><mRID>1</mRID><businessType>A85</businessType><flowDirection.direction>A01</flowDirection.direction>
<Period><timeInterval><start>2026-09-30T22:00Z</start><end>2026-09-30T23:00Z</end></timeInterval><resolution>PT15M</resolution>
<Point><position>1</position><quantity>100</quantity></Point><Point><position>3</position><quantity>40</quantity></Point></Period></TimeSeries>
</Redispatching_MarketDocument>"""


def test_points_and_monthly_mwh() -> None:
    pts = bc.points(ET.fromstring(A63))
    assert [(p["time"], p["quantity"], p["hours"], p["flowDirection.direction"]) for p in pts] == [
        ("2026-09-30T22:00:00+00:00", 100.0, 0.25, "A01"),
        ("2026-09-30T22:30:00+00:00", 40.0, 0.25, "A01"),
    ]
    assert bc.monthly(pts, "quantity", True) == {"2026-09": 35.0}


def test_merge_months_keeps_history() -> None:
    old = {
        "countries": {"DE": {"costs": {"months": {"2026-01": 1.0, "2026-09": 2.0}}}},
        "acks": {"a": 1},
    }
    new = {"countries": {"DE": {"costs": {"months": {"2026-09": 3.0, "2026-10": 4.0}}}}}
    assert bc.merge_months(old, new) == {
        "countries": {
            "DE": {"costs": {"months": {"2026-09": 3.0, "2026-10": 4.0, "2026-01": 1.0}}}
        },
        "acks": {"a": 1},
    }


def test_neso_rows_numbers() -> None:
    rows = bc.neso_rows(
        "Date,Thermal constraints cost,Thermal constraints volume\n2026-04-01,9530229,-59177\n"
    )
    assert rows == [
        {
            "Date": "2026-04-01",
            "Thermal constraints cost": 9530229.0,
            "Thermal constraints volume": -59177.0,
        }
    ]


# ---------------------------------------------------------------- family 5, prices with the same coverage

from datetime import UTC, date, datetime  # noqa: E402

import build_gb_prices as gp  # noqa: E402
import entsoe  # noqa: E402


def test_rate_on_falls_back_to_the_last_published_day() -> None:
    rates = {"2026-10-16": 0.86}  # a Friday
    assert gp.rate_on(rates, date(2026, 10, 18)) == 0.86
    assert gp.rate_on({}, date(2026, 10, 18)) is None


def test_mid_on_grid_fills_both_quarters() -> None:
    grid = entsoe.Grid(datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 1, 1, tzinfo=UTC))
    rows = [
        {"startTime": "2026-10-01T00:30:00Z", "dataProvider": "APXMIDP", "price": 95.5},
        {"startTime": "2026-10-01T00:00:00Z", "dataProvider": "N2EXMIDP", "price": 1.0},
    ]
    assert gp.mid_on_grid(rows, grid) == [None, None, 95.5, 95.5]


def test_ecb_gbp_reads_the_history_file() -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "eurofxref-hist.csv", "Date,USD,GBP,\n2026-10-16,1.08,0.8612,\n2026-10-15,1.09,N/A,\n"
        )
    assert gp.ecb_gbp(buf.getvalue()) == {"2026-10-16": 0.8612}


# ---------------------------------------------------------------- family 6, what UK consumers pay

import fetch_gb_retail as gr  # noqa: E402


def test_semester_rate_averages_the_half_year() -> None:
    rates = {"2026-01-05": 0.84, "2026-06-30": 0.86, "2026-07-01": 0.9}
    assert gr.semester_rate(rates, "2026-S1") == 0.85
    assert gr.semester_rate(rates, "2026-S2") == 0.9
    assert gr.semester_rate(rates, "2025-S1") is None


def test_uk_semesters_reads_the_united_kingdom_column() -> None:
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "5.6.2 (Medium incl tax)"
    ws.append(["Table 5.6.2"])
    ws.append(["Year", "Period", "France", "United Kingdom"])
    ws.append([2025, "Jan to Jun", 25.1, 27.03])
    ws.append([2025, "Jul to Dec", 24.0, "28.5 [x]"])
    ws.append([2026, "Jan to Jun", 24.0, None])
    buf = io.BytesIO()
    wb.save(buf)
    assert gr.uk_semesters(buf.getvalue(), "5.6.2 (Medium incl tax)") == {
        "2025-S1": 27.03,
        "2025-S2": 28.5,
    }


# ---------------------------------------------------------------- family 7, UK ETS emitters

import fetch_uk_ets as uk  # noqa: E402


def test_uk_ets_merge_keeps_eu_rows_and_adds_unplaced_gb() -> None:
    ets = {
        "years": [2024, 2025],
        "groups": ["Combustion (power, heat, industry)", "Other"],
        "countries": {"XI": {"n": 1, "placed": 0, "t": [5, 4], "t_placed": 0}},
        "rows": [["XI", "568", "Ballylumford", 0, [5, 4], None, None]],
    }
    rows = [
        {
            "id": "1000627",
            "permit": "UK-W-IN-12612",
            "name": "Mill",
            "t": {2024: 18475, 2025: None},
        },
        {"id": "1", "permit": "x", "name": "Closed", "t": {2024: None, 2025: None}},
    ]
    out = uk.merge(ets, rows, "2026-10-20")
    assert out["groups"][-1] == uk.GROUP
    assert out["countries"]["GB"] == {"n": 1, "placed": 0, "t": [18475, 0], "t_placed": 0}
    assert ["GB", "1000627", "Mill", 2, [18475, None], None, None] in out["rows"]
    assert len(out["rows"]) == 2


# ---------------------------------------------------------------- family 8, GB plants offline

import fetch_gb_outages as go  # noqa: E402


def test_gb_outages_keep_active_production_and_drop_closures() -> None:
    now = datetime(2026, 10, 20, 4, tzinfo=UTC)
    base = {
        "eventType": "Production unavailability",
        "eventStatus": "Active",
        "fuelType": "Fossil Gas",
        "normalCapacity": 780.0,
        "availableCapacity": 0.0,
        "unavailabilityType": "Unplanned",
        "assetId": "T_DIDCB5",
    }
    msgs = [
        base
        | {
            "unavailableCapacity": 740.0,
            "eventStartTime": "2026-10-19T22:07:12Z",
            "eventEndTime": "2026-10-20T05:35:31Z",
        },
        base
        | {
            "unavailableCapacity": 505.0,
            "eventStartTime": "2024-09-30T22:00:00Z",
            "eventEndTime": "2050-09-30T23:00:00Z",
        },
        base
        | {
            "unavailableCapacity": 50.0,
            "eventStatus": "Dismissed",
            "eventStartTime": "2026-10-19T00:00:00Z",
            "eventEndTime": "2026-10-21T00:00:00Z",
        },
        base
        | {
            "unavailableCapacity": 50.0,
            "eventStartTime": "2026-10-21T00:00:00Z",
            "eventEndTime": "2026-10-22T00:00:00Z",
        },
    ]
    units, left_out, long_term = go.units(msgs, now)
    assert [(u["offline_mw"], u["fuel"], u["type"]) for u in units] == [(740.0, "gas", "forced")]
    assert left_out == 0 and long_term == {"n": 1, "mw": 505.0}
    f = {
        "countries": {
            "FR": {"offline_mw": 10.0, "planned_mw": 10.0, "forced_mw": 0.0, "left_out": 0}
        },
        "zones": {},
        "units": [],
    }
    out = go.merge(f, units, 0, "2026-10-20T04:00:00+00:00", long_term)
    assert out["total"]["offline_mw"] == 750.0 and out["countries"]["GB"]["forced_mw"] == 740.0


# ---------------------------------------------------------------- family 9, EV charging

import build_ev_eu as ev  # noqa: E402


def test_ev_cells_sum_points_per_tenth_degree() -> None:
    cells = ev.cells([(13.41, 52.52, 4), (13.44, 52.58, 2), (2.35, 48.85, 1)])
    assert cells == [[13.45, 52.55, 6], [2.35, 48.85, 1]]


def test_eafo_series_and_classes() -> None:
    s = ev.eafo_series("YEAR,AC,DC\n2025,82083,21497\n2026,88616,24973\n")
    assert s == {"years": [2025, 2026], "ac": [82083, 88616], "dc": [21497, 24973]}
    labels, classes = ev.eafo_classes(
        'Country,"Slow AC",Fast DC\n"Czech Republic",5,1444\nMalta,,4\n'
    )
    assert labels == ["Slow AC", "Fast DC"] and classes == {"CZ": [5, 1444], "MT": [None, 4]}


def test_de_register_reads_points_per_facility() -> None:
    text = "Ladesäulenregister\nLadeeinrichtungs-ID;Status;Anzahl Ladepunkte;Breitengrad;Längengrad;Betreiber\n1;In Betrieb;2;52,52;13,41;X\n2;Außer Betrieb;2;52,5;13,4;Y\n"
    pts, rows = ev.de_points(text)
    assert pts == [(13.41, 52.52, 2)] and rows[0]["points"] == 2


# ---------------------------------------------------------------- family 10, gas on the US side

import fetch_us_gas as ug  # noqa: E402


def test_five_year_range_uses_the_same_week_of_five_years() -> None:
    pts = [[f"{y}-01-0{d}", float(v)] for y, d, v in [
        (2021, 8, 1), (2022, 7, 2), (2023, 6, 3), (2024, 5, 4), (2025, 3, 5), (2026, 9, 9)
    ]]  # fmt: skip
    # ISO week 1 of each year; 2026-01-09 is in week 2, so it has no full five-year range
    assert ug.five_year_range(pts) == {}
    pts[-1] = ["2026-01-02", 9.0]
    assert ug.five_year_range(pts) == {"2026-01-02": [1.0, 5.0]}


def test_eia_series_groups_and_sorts() -> None:
    rows = [
        {
            "period": "2026-10-10",
            "series": "S",
            "series-description": "Lower 48",
            "units": "BCF",
            "value": "3800",
        },
        {
            "period": "2026-10-03",
            "series": "S",
            "series-description": "Lower 48",
            "units": "BCF",
            "value": "3720",
        },
        {
            "period": "2026-10-03",
            "series": "T",
            "series-description": "East",
            "units": "BCF",
            "value": None,
        },
    ]
    assert ug.series(rows, "series") == {
        "S": {
            "name": "Lower 48",
            "unit": "BCF",
            "points": [["2026-10-03", 3720.0], ["2026-10-10", 3800.0]],
        }
    }
