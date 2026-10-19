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
