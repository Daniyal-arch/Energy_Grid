# ruff: noqa: E501 - fixture lines as the sources publish them
"""Wave-6 builders (brief 21): their pure parsing and shaping functions, one test per dataset."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_connect_more as cm  # noqa: E402
import build_constraints as bc  # noqa: E402
import build_grid_more as gm  # noqa: E402

# ---------------------------------------------------------------- A. room to connect


def test_fr_capareseau_labels_and_site() -> None:
    csv = '﻿Code;Nom;INFO_NA;INFO_QP\nCode;Nom;"Capacité d\'accueil réservée au titre du S3REnR qui reste à affecter";"Quote-Part unitaire actualisée "\nA.LIG;ACHILLE;12.5;"42.40  k€/MW"\n'
    labels = cm.capareseau_labels(csv)
    assert labels["INFO_NA"].startswith("Capacité d'accueil réservée")
    site = cm.capareseau_site({"code": "P.MAU", "name": "Pays Mauriacois", "territory_name": "Auvergne-Rhône-Alpes", "X": 2.396, "Y": 45.238, "u_max": 6,
                               "updated": "02/03/2026", "grd1": {"name": None}, "values": {"INFO_NA": "0", "INFO_TX": "", "INFO_QP": "42.40  k€/MW"}})  # fmt: skip
    assert site["lon"] == 2.396 and site["values"] == {"INFO_NA": "0", "INFO_QP": "42.40  k€/MW"}
    assert (
        cm.number("12.5") == 12.5
        and cm.number("1 234,5") == 1234.5
        and cm.number("42.40  k€/MW") is None
        and cm.number("-") is None
    )


def test_it_regions() -> None:
    cols = ["Regione", "Fonte", "Tipo Impianto", "Potenza (MW)", "Numero Pratiche"]
    rows = [
        ["SICILIA", "Solare", "FER", 40696.244, 816],
        ["SICILIA", "Eolico on-shore", "FER", 16755.511, 328],
        ["PUGLIA", "Solare", "FER", 39191.818, 917],
    ]
    out = cm.it_regions(rows, cols)
    assert out["SICILIA"]["Solare"] == [40696.244, 816] and len(out["SICILIA"]) == 2
    assert set(cm.NUTS2) >= {"SICILIA", "PUGLIA"} and cm.NUTS2["TRENTINO-ALTO ADIGE"] == [
        "ITH1",
        "ITH2",
    ]


def test_be_needs_the_browser_file() -> None:
    import argparse

    try:
        cm.build_be(argparse.Namespace(file=None))
    except SystemExit as e:
        assert "browser_fetch" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_pt_row() -> None:
    r = {"codigo": "0809S5060500", "instalacao": "MONCHIQUE", "tipo_de_instalacao": "SE AT", "distrito": "Faro", "concelho": "Monchique", "nut3": "Algarve",
         "ligacao_rnt_barramento_60kv_rari": "Portimão", "potencia_de_ligacao_ligado_mva_ultimo_trimestre": "11.58244",
         "capacidade_de_recepcao_at_mva_ultimo_trimestre": "-", "capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre": "0"}  # fmt: skip
    row = cm.pt_row(r)
    assert row[:7] == [
        "0809S5060500",
        "MONCHIQUE",
        "SE AT",
        "Faro",
        "Monchique",
        "Algarve",
        "Portimão",
    ]
    vals = dict(zip(cm.PT_KEEP, row[7], strict=True))
    assert vals["potencia_de_ligacao_ligado_mva_ultimo_trimestre"] == 11.58244
    assert (
        vals["capacidade_de_recepcao_at_mva_ultimo_trimestre"] is None
        and vals["capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre"] == 0.0
    )


def test_ie_esb_rows() -> None:
    head = ("Station Name", "Transformer GroupID", "Primary kV", "Secondary voltage(s)", "Voltage Class", "Transformer Configuration", "Installed Capacity MVA",
            "Demand Data", "Demand FirmCapacity MVA", "Demand Available MVA", "Parent Available MVA", "Demand Parent Constraint", "Generation Data",
            "Generation Firm Capacity MW", "Generation NonFirm Capacity MW", "Generation Total Committed MW", "Gen Available Firm MW", "Gen Available NonFirm MW",
            "Generation Parent Constraint", "General Data", "Parent Feeder", "Parent Station", "TSO Interface Station", "Comment", "Latitude", "Longitude")  # fmt: skip
    row = ("GARRYOWEN (067000) 38 kV STATION", None, "38 kV", "_", "MV", "x", 30, " -->", 30, 0, "0", None, " -->", 20, 0, 2.7, 18.6, 7.187, None, " -->", "", "", "", "", 52.66307, -8.61737)  # fmt: skip
    out = cm.esb_rows([(None, None, "Transformer Available Capacity"), head, row])
    assert len(out) == 1
    assert (
        out[0]["name"].startswith("GARRYOWEN")
        and out[0]["gen_available_firm_mw"] == 18.6
        and out[0]["lon"] == -8.61737
        and out[0]["voltage_class"] == "MV"
    )


def test_pl_pse_lists() -> None:
    rows = [("Informacje publikowane ...",), (None,) * 3, ("ID Obiektu", "Nazwa Obiektu", "Nazwa OSD/OSP"),
            ("-", "MEE Środa", "PSE S.A.", "FCB Bess", "Kromolice\nKromolice", "110; \n400", "TAK", "MEE", "129;\n240", "129; \n240", "-", "-", "129;\n240", "129; \n240", "-", "-",
             "WARUNKI PRZYŁĄCZENIA wydane", datetime(2025, 3, 1), "-")]  # fmt: skip
    reqs = cm.pse_requests(rows)
    assert (
        reqs[0]["name"] == "MEE Środa"
        and reqs[0]["voltage_kv"] == "110; 400"
        and reqs[0]["pv_mw"] is None
        and reqs[0]["applied"] == "2025-03-01"
    )
    full = cm.pse_full(
        [
            ("Lista ...",),
            ("ZKO PSE", "Symbol stacji", "Nazwa stacji", "Rozdzielnia", "Liczba"),
            ("Katowice", "ANI", "Aniołów", "Rozdzielnia 220 kV", 0),
        ]
    )
    assert full == [
        {
            "area": "Katowice",
            "symbol": "ANI",
            "station": "Aniołów",
            "switchgear": "Rozdzielnia 220 kV",
            "free_bays": 0,
        }
    ]


# ---------------------------------------------------------------- B. grid and networks


def test_substation_feature() -> None:
    f = gm.substation_feature(13.123456, 52.5, 380, "Umspannwerk", None, "DEU")
    assert f["tippecanoe"]["minzoom"] == 4 and f["properties"] == {
        "kv": 380,
        "name": "Umspannwerk",
        "iso3": "DEU",
    }
    assert f["geometry"]["coordinates"] == [13.12346, 52.5]
    assert gm.minzoom(110) == 6 and gm.minzoom(None) == 8


def test_top_operator() -> None:
    assert gm.top_operator({"SNB1": 40, "SNB2": 55, "SNB3": 5}) == ("SNB2", 55, 3, 100)
    # a tie goes to the lower MaStR number, so a rebuild picks the same one
    assert gm.top_operator({"SNB9": 3, "SNB1": 3})[0] == "SNB1"
    assert (
        gm.find(
            ["NetzanschlusspunktMastrNummer", "LokationMaStRNummer", "NetzbetreiberMaStRNummer"],
            r"NetzbetreiberMa[Ss]t[Rr]Nummer",
        )
        == "NetzbetreiberMaStRNummer"
    )


def test_utilities_fips() -> None:
    # county_id_fips is published as the 5-digit county code: kept as is (no state prefix added)
    assert "lpad(CAST(county_id_fips AS VARCHAR), 5, '0')" in Path(gm.__file__).read_text(
        encoding="utf-8"
    )


def test_emodnet_lines() -> None:
    parts = gm.lines_of(
        {
            "type": "MultiLineString",
            "coordinates": [
                [[4.0, 52.0], [4.00001, 52.00001], [4.5, 52.5]],
                [[5.0, 53.0], [5.1, 53.1]],
            ],
        }
    )
    assert parts == [[4.0, 52.0, 4.5, 52.5], [5.0, 53.0, 5.1, 53.1]]
    assert gm.clean(" n/a ") is None and gm.clean("Gas") == "Gas"


# ---------------------------------------------------------------- C. what stops a build


def test_protected_props() -> None:
    n = bc.n2k_props(
        {
            "SITECODE": "DE1234567",
            "SITENAME": "Wattenmeer",
            "SITETYPE": "C",
            "MS": "DE",
            "Area_km2": 4410.5,
        }
    )
    assert n == {
        "src": "n2k",
        "id": "DE1234567",
        "name": "Wattenmeer",
        "kind": "SPA and SCI/SAC",
        "iso2": "DE",
        "km2": 4410.5,
    }
    p = bc.padus_props(
        {
            "Unit_Nm": "Yellowstone",
            "Des_Tp": "NP",
            "Mang_Name": "NPS",
            "State_Nm": "WY",
            "GIS_Acres": 2219790.71,
            "GAP_Sts": "1",
        }
    )
    assert p["gap"] == "1" and p["acres"] == 2219790.7 and p["kind"] == "NP"


def test_flood_depth_class() -> None:
    assert [bc.depth_class(v) for v in (0.0, -9999.0, 0.2, 0.5, 1.0, 1.99, 2.0, 4.0, 12.0)] == [
        0,
        0,
        1,
        2,
        3,
        3,
        4,
        5,
        5,
    ]
    assert len(bc.DEPTH) == len(bc.DEPTH_COLORS) == 5


def test_roads_classes() -> None:
    assert bc.ROAD_CLASSES == ["motorway", "trunk", "primary"]
    x0, y0, x1, y1 = bc.BOXES["europe"]
    assert x0 < 0 < x1 and y0 < 50 < y1


# ---------------------------------------------------------------- D. what is coming and what it costs

import build_coming as bk  # noqa: E402


def test_hydrogen_row() -> None:
    procs: list[str] = []
    uses: list[str] = []
    stages: list[str] = []
    r = {"Name": "H2 Green Steel (Phase 1) ", "City": "Boden", "Country": "Sweden", "Start year": 2026, "Production capacity MW/MWel": 740,
         "Production process": "Water electrolysis", "End-use": "Steel", "Consumption capacity (tonnes/year)": 122309.4339, "Latitude": 65.86769, "Longitude": 21.72567,
         "Project stage": "Construction"}  # fmt: skip
    row = bk.h2_row(r, procs, uses, stages)
    assert row == [
        "H2 Green Steel (Phase 1)",
        "Boden",
        "SWE",
        2026,
        740,
        0,
        0,
        122309,
        21.7257,
        65.8677,
        0,
    ]
    assert (
        stages == ["Construction"]
        and bk.h2_row({**r, "Latitude": None}, procs, uses, stages) is None
    )


def test_aures_round() -> None:
    r = {"Country": "Croatia", "Year": 2020, "Auction date (deadline) [MM/YEAR]": datetime(2020, 12, 11), "Eligible Technologies": "PV", "Status of the auction": "concluded",
         "Average awarded price [ct/ kWh]": 7.81, "Awarded capacity [kW]": 50000, "Number of submitted bids": "n/a"}  # fmt: skip
    x = bk.aures_round(r)
    assert (
        x["date"] == "2020-12"
        and x["awarded_mw"] == 50.0
        and x["avg_ct_kwh"] == 7.81
        and x["bids"] is None
        and x["iso3"] == "HRV"
    )


def test_atb_pick_and_irena_table() -> None:
    from collections import Counter

    assert bk.atb_pick(Counter({("Market", "None"): 5, ("R&D", ""): 9})) == ("Market", "None")
    assert bk.atb_pick(Counter({("R&D", ""): 9})) == ("R&D", "")
    rows = [
        ("Figure 1.1 Global weighted average LCOE (USD/kWh)",),
        (None, 2010, 2015, 2020, 2023, 2024),
        ("Solar PV", 0.46, 0.13, 0.06, 0.044, 0.043),
        ("Onshore wind", 0.11, 0.07, 0.04, 0.033, 0.034),
    ]
    t = bk.irena_table(rows)
    assert t["Solar PV"]["2024"] == 0.043 and len(t["Onshore wind"]) == 5


def test_gas_category() -> None:
    assert (
        bk.gas_category("TRA-F-7") == "TRA"
        and bk.gas_category("H2T-F-642") == "H2T"
        and bk.gas_category("") == ""
    )
    assert bk.iso3("Czech Republic") == "CZE" and bk.iso3("Croatia") == "HRV"


def test_ghg_rows() -> None:
    v = {
        ("DE", "TOTX4_MEMO", "2023"): 673.0,
        ("DE", "TOTX4_MEMO", "2024"): 649.76952,
        ("DE", "CRF1", "2024"): 543.29497,
        ("DE", "CRF4", "2023"): 50.0,
    }
    year, rows = bk.ghg_rows(v, "DE", ["2023", "2024"])
    assert year == "2024" and rows == [
        ["Total, excluding LULUCF", 649.77, "Mt CO2e", "2024"],
        ["Energy", 543.295, "Mt CO2e", "2024"],
    ]


# ---------------------------------------------------------------- E. United States

import build_us_reliability as ur  # noqa: E402


def test_oe417_events() -> None:
    rows = [("Major Disturbances and Unusual Occurrences, Year-to-Date 2024",), ("Month", "Date Event Began", "Time Event Began", "Date of Restoration", "Time of Restoration",
            "Area Affected", "NERC Region", "Alert Criteria", "Event Type", "Demand Loss (MW)", "Number of Customers Affected"),
            ("January", datetime(2024, 1, 9), "14:30", datetime(2024, 1, 10), "08:00", "Georgia: Fulton County; South Carolina;", "SERC", "Loss of electric service", "Severe Weather", 300, 120000),
            ("January", datetime(2024, 1, 12), "01:00", None, None, "West Virginia:", "RF", "x", "Vandalism", "Unknown", None)]  # fmt: skip
    ev = ur.oe417_events(rows)
    assert (
        ev[0]["began_date"] == "2024-01-09"
        and ev[0]["states"] == ["SC", "GA"]
        and ev[0]["mw"] == 300
        and ev[0]["customers"] == 120000
    )
    assert ev[1]["states"] == ["WV"] and ev[1]["mw"] is None


def test_ferc714_threshold() -> None:
    # the newest year with demand from 80 planning areas or more (2025: 89; 2014 had 100+)
    assert "WHERE n >= 80" in Path(ur.__file__).read_text(encoding="utf-8")
    assert ur.states_in("Washington, DC; Maryland") == ["MD"]


# ---------------------------------------------------------------- F. regional and live

import build_regional_live as rl  # noqa: E402


def test_fr_newest() -> None:
    recs = [{"code_insee_region": "53", "libelle_region": "Bretagne", "date_heure": f"2026-10-19T08:{m:02d}:00+00:00", "consommation": c, "eolien": 173, "pompage": "0"}
            for m, c in ((15, 2500), (30, 2563), (45, None))]  # fmt: skip
    out = rl.fr_newest(recs)
    assert (
        out["53"]["ts"].endswith("08:30:00+00:00")
        and out["53"]["mw"]["consommation"] == 2563.0
        and out["53"]["mw"]["pompage"] == 0.0
    )
    assert out["53"]["nuts1"] == "FRH" and len(out["53"]["consumption_24h"]) == 2


def test_es_series() -> None:
    a = {
        "included": [
            {
                "type": "Eólica",
                "attributes": {
                    "title": "Eólica",
                    "values": [{"value": 1234.5678, "datetime": "2026-09-01T00:00:00.000+02:00"}],
                },
            }
        ]
    }
    assert rl.es_series(a) == {"Eólica": {"2026-09": 1234.568}}
    assert rl.ES_CCAA[13] == ("Comunidad de Madrid", "ES30")


def test_nz_load() -> None:
    # Transpower's months are 0-based (JavaScript dates)
    assert rl.nz_load(
        [[{"day": 19, "month": 9, "year": 2026, "hour": 22, "minute": 40}, 4463]]
    ) == [["2026-10-19T22:40", 4463]]


def test_eskom_csv_link() -> None:
    html = '<a href="https://www.eskom.co.za/dataportal/wp-content/uploads/2026/07/Station_Build_Up.csv">Download</a>'
    assert rl.eskom_csv_link(html).endswith("Station_Build_Up.csv")
    assert rl.parse_csv("﻿Date,Residual Demand\n2026-10-18 01:00,21000\n") == (
        ["Date", "Residual Demand"],
        [["2026-10-18 01:00", "21000"]],
    )
