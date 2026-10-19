# ruff: noqa: E501, SIM905 - fixture lines as the sources publish them
"""Wave-5 builders (brief 17): their pure parsing and shaping functions."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import browser_fetch  # noqa: E402
import build_germany  # noqa: E402
import build_grw  # noqa: E402
import build_markets  # noqa: E402
import build_population  # noqa: E402
import build_profiles  # noqa: E402
import build_shapes  # noqa: E402
import build_smard_catalog  # noqa: E402
import build_transmission_outages as a78  # noqa: E402
import build_tyndp  # noqa: E402
import build_us_perf  # noqa: E402

ZONES = [
    "AT",
    "DE-LU",
    "DK1",
    "DK2",
    "GR",
    "IT-North",
    "IT-Sicily",
    "NO1",
    "NO5",
    "SE3",
    "SE4",
    "FR",
    "ES",
]


def test_nuts_to_zone() -> None:
    assert build_shapes.zone_of("DE300", ZONES) == "DE-LU"
    assert build_shapes.zone_of("LU000", ZONES) == "DE-LU"
    assert build_shapes.zone_of("DK014", ZONES) == "DK2"
    assert build_shapes.zone_of("DK050", ZONES) == "DK1"
    assert build_shapes.zone_of("ITC11", ZONES) == "IT-North"
    assert build_shapes.zone_of("ITG11", ZONES) == "IT-Sicily"
    assert build_shapes.zone_of("NO0A2", ZONES) == "NO5"
    assert build_shapes.zone_of("SE224", ZONES) == "SE4"
    assert build_shapes.zone_of("EL301", ZONES) == "GR"
    assert build_shapes.zone_of("AT130", ZONES) == "AT"
    # outside the synchronous systems: overseas France, the Canaries, Svalbard
    assert build_shapes.zone_of("FRY10", ZONES) is None
    assert build_shapes.zone_of("ES703", ZONES) is None
    assert build_shapes.zone_of("NO0B2", ZONES) is None


def test_geonames_line() -> None:
    row = "3040051\tles Escaldes\tles Escaldes\tx\t42.50729\t1.53414\tP\tPPLA\tAD\t\t08\t\t\t\t15853\t\t1033\tEurope/Andorra\t2008-10-15".split(
        "\t"
    )
    c = build_shapes.parse_city(row)
    assert (
        c["iso2"] == "AD"
        and c["population"] == 15853
        and c["lon"] == 1.53414
        and c["admin1"] == "08"
    )


def test_capacity_factor_and_egrid() -> None:
    assert build_us_perf.capacity_factor(876_000, 100, 2025) == 1.0
    assert build_us_perf.capacity_factor(878_400, 100, 2024) == 1.0  # leap year
    assert build_us_perf.capacity_factor(None, 100, 2025) is None
    assert build_us_perf.sector_of("Power Plants,Suppliers of CO2") == 0
    assert build_us_perf.sector_of("Something new") == build_us_perf.SECTORS.index("Other")
    rows = build_us_perf.egrid_rows(
        [("long",) * 3, ("SEQ", "ORISPL", "PLCO2AN"), (1, 57053, 12.5), (None, None, None)]
    )
    assert rows == [{"SEQ": 1, "ORISPL": 57053, "PLCO2AN": 12.5}]


def test_redispatch() -> None:
    row = {
        "BEGINN_DATUM": "02.04.2013", "BEGINN_UHRZEIT": "11:00", "ZEITZONE_VON": "UTC",
        "ENDE_DATUM": "02.04.2013", "ENDE_UHRZEIT": "14:00", "ZEITZONE_BIS": "UTC",
        "GRUND_DER_MASSNAHME": "Strombedingter Redispatch", "RICHTUNG": "Wirkleistungseinspeisung reduzieren",
        "MITTLERE_LEISTUNG_MW": "267", "MAXIMALE_LEISTUNG_MW": "300", "GESAMTE_ARBEIT_MWH": "1.234,5",
        "ANWEISENDER_UENB": "50Hertz", "ANFORDERNDER_UENB": "PSE", "BETROFFENE_ANLAGE": "Jänschwalde", "PRIMAERENERGIEART": "Konventionell",
    }  # fmt: skip
    r = build_germany.parse(row)
    assert (
        r["start"] == "2013-04-02T11:00:00+00:00"
        and r["direction"] == "reduce"
        and r["mwh"] == 1234.5
    )
    m = build_germany.monthly([r, {**r, "direction": "increase", "mwh": 10.0}])
    assert m["months"] == ["2013-04"] and m["by_direction"] == {"increase": [10], "reduce": [1234]}


def test_smard_newest() -> None:
    assert build_smard_catalog.newest([[1, 5.0], [2, 6.5], [3, None]]) == (2, 6.5)
    assert build_smard_catalog.newest([[1, None]]) is None


def test_tyndp() -> None:
    assert build_tyndp.year_of("06-2024") == 2024 and build_tyndp.year_of("2030") == 2030
    assert build_tyndp.year_of(None) is None
    d = build_tyndp.details(
        "Transmission", {"investments": [{"id": 18, "capacity": 1000.0, "voltageLevelKv": 400}]}
    )
    assert d["18"]["capacity_mw"] == 1000.0 and d["18"]["voltage_kv"] == 400
    assert (
        build_tyndp.details("Storage", {"generatingMaxActivePower": 440.0})["project"][
            "generating_mw"
        ]
        == 440.0
    )


A78 = """<Unavailability_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:outagedocument:3:0">
<mRID>abc</mRID><revisionNumber>2</revisionNumber><docStatus><value>A05</value></docStatus>
<TimeSeries><businessType>A53</businessType>
<start_DateAndOrTime.date>2026-10-01</start_DateAndOrTime.date><start_DateAndOrTime.time>06:00:00Z</start_DateAndOrTime.time>
<end_DateAndOrTime.date>2026-10-03</end_DateAndOrTime.date><end_DateAndOrTime.time>18:00:00Z</end_DateAndOrTime.time>
<Asset_RegisteredResource><mRID>10T-LINE</mRID><name>Line A - B 380 kV</name><asset_PSRType.psrType>B21</asset_PSRType.psrType></Asset_RegisteredResource>
<Available_Period><Point><position>1</position><quantity>800</quantity></Point><Point><position>2</position><quantity>650</quantity></Point></Available_Period>
</TimeSeries><Reason><code>B19</code><text>Maintenance</text></Reason></Unavailability_MarketDocument>"""


def test_a78() -> None:
    rows = a78.parse(ET.fromstring(A78), "NL")
    assert len(rows) == 1
    r = rows[0]
    assert (
        r["element"] == "Line A - B 380 kV"
        and r["kind"] == "planned"
        and r["available_mw_min"] == 650
    )
    assert r["start"] == "2026-10-01T06:00:00+00:00" and r["reason_text"] == "Maintenance"
    old = {**r, "revision": 1}
    gone = {**r, "mrid": "x", "doc_status": "A13"}
    assert a78.newest_revisions([old, r, gone]) == [r]


def test_grw() -> None:
    assert build_grw.quarter_of("2023Q4") == "2023Q4"
    assert build_grw.quarter_of("2023-11-02") == "2023Q4"
    assert build_grw.quarter_of(None) == build_grw.RELEASE_QUARTER
    assert build_grw.quarter_of("2020|3") == "2020Q3"
    assert build_grw.quarter_of("2020|Q3") == "2020Q3"
    assert build_grw.quarter_of("2020|2020Q2") == "2020Q2"
    assert build_grw.find(["fid", "capacity_mw", "geom"], r"capacity") == "capacity_mw"


def test_jsonstat_and_ei_link() -> None:
    d = {
        "id": ["geo", "time"],
        "size": [2, 2],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0, "FR": 1}}},
            "time": {"category": {"index": {"2023": 0, "2024": 1}}},
        },
        "value": {"0": 1.0, "1": 2.0, "3": 4.0},
    }
    assert build_profiles.jsonstat_values(d) == {
        ("DE", "2023"): 1.0,
        ("DE", "2024"): 2.0,
        ("FR", "2024"): 4.0,
    }


def test_ei_panel_and_browser_link() -> None:
    html = '<a href="/__data/assets/file/0001/1/Statistical-Review-Panel-format.csv">x</a> <a href="/x.pdf">'
    pats = browser_fetch.SOURCES["ei"]["links"]
    assert (
        browser_fetch.find_link(html, pats, "https://www.energyinst.org/statistical-review/home")
        == "https://www.energyinst.org/__data/assets/file/0001/1/Statistical-Review-Panel-format.csv"
    )
    assert browser_fetch.find_link("<html>nothing</html>", pats, "https://x.org/") is None
    rows = [
        ("Primary energy consumption", None, None, None),
        ("Exajoules", *range(2000, 2025), "2024 growth"),
        ("Germany", *[float(i) for i in range(25)], 0.01),
        ("US", *[None] * 24, 94.0, None),
        (None,),
    ]
    unit, vals = build_profiles.ei_sheet(rows)
    assert unit == "Exajoules" and len(vals) == 26 and vals[-1] == ("US", 2024, 94.0)
    assert build_profiles.ei_iso3("US") == "USA" and build_profiles.ei_iso3("Germany") == "DEU"
    assert (
        build_profiles.ei_iso3("Total Europe") is None and build_profiles.ei_iso3("Europe1") is None
    )
    assert (
        build_profiles.ei_iso3("South Africa") == "ZAF"
        and build_profiles.ei_iso3("Russia") == "RUS"
    )


def test_markets() -> None:
    text = "受渡日,時刻コード,a,b,c,d\n2026/10/19,48,26826650,24848800,19800350,26.90,28.13,28.13,28.13,28.05,13.82,13.82,13.82,8.31,13.82,9341850\n"
    (r,) = build_markets.jepx_rows(text)
    assert (
        r["date"] == "2026-10-19"
        and r["slot"] == 48
        and r["system_jpy_kwh"] == 26.9
        and r["shikoku_jpy_kwh"] == 8.31
    )
    ans = {
        "Resultados": [
            {
                "clv_nodo": "01PLO-115",
                "Valores": [{"fecha": "2026-10-17", "hora": "1", "pml": "1234.56"}, {"hora": "x"}],
            }
        ]
    }
    assert build_markets.cenace_values(ans) == [("01PLO-115", 1, 1234.56)]
    assert build_markets.spread([3.0, 1.0, 2.0]) == [3, 1.0, 2.0, 3.0]


def test_population_coarsen() -> None:
    import numpy as np

    block = np.ones((24, 36))
    block[0, 0] = -200  # no data
    out = build_population.coarsen(block)
    assert out.shape == (2, 3) and out[0, 0] == 143 and out[1, 2] == 144
