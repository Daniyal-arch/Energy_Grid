"""MaStR adapter transform tests (no file/network I/O — synthetic raw records).

Covers per-unit site creation and wind-turbine clustering into farms.
"""

from app.models import SiteState, Technology
from ingestion.sources.mastr import MaStRSource


def _rec(tech: str, **over: object) -> dict:
    base = {
        "EinheitMastrNummer": "SEE000",
        "Name": "Test",
        "Nettonennleistung": 8000.0,  # kW
        "EinheitBetriebsstatus": "In Betrieb",
        "Bundesland": "Bayern",
        "Landkreis": "Muenchen",
        "Gemeinde": "Pentling",
        "Breitengrad": 48.1,
        "Laengengrad": 11.5,
        "Inbetriebnahmedatum": "2023-05-01",
        "GeplantesInbetriebnahmedatum": None,
        "AnlagenbetreiberMastrNummer": "ABR123",
        "Lage": "Freifläche",
        "_tech": tech,
    }
    base.update(over)
    return base


def test_solar_unit_becomes_site_with_capacity_buffer():
    sites = list(MaStRSource().transform([_rec("solar", EinheitMastrNummer="SEE1")]))
    assert len(sites) == 1
    s = sites[0]
    assert s.mastr_id == "SEE1"
    assert s.technology == Technology.SOLAR
    assert s.capacity_mw == 8.0  # 8000 kW
    assert s.status == SiteState.UNKNOWN  # construction state starts unknown
    assert s.mastr_status == "In Betrieb"
    assert s.aoi_method == "capacity_buffer"
    assert s.geom_wkt.startswith("MULTIPOLYGON")


def test_wind_turbines_cluster_into_farms():
    # three turbines in one farm (~300 m apart), two in another ~5 km away
    near = [
        _rec(
            "wind",
            EinheitMastrNummer=f"W{i}",
            Laengengrad=11.500 + i * 0.004,
            Nettonennleistung=6000.0,
        )
        for i in range(3)
    ]
    far = [
        _rec(
            "wind",
            EinheitMastrNummer=f"F{i}",
            Laengengrad=11.600 + i * 0.004,
            Nettonennleistung=6000.0,
        )
        for i in range(2)
    ]
    sites = list(MaStRSource().transform(near + far))
    assert len(sites) == 2
    by_count = sorted(sites, key=lambda s: s.unit_count)
    assert by_count[0].unit_count == 2
    assert by_count[1].unit_count == 3
    assert by_count[1].capacity_mw == 18.0  # 3 * 6 MW
    assert all(s.technology == Technology.WIND for s in sites)
    assert all(s.mastr_id.startswith("WINDFARM-") for s in sites)


def test_planning_status_propagates_to_wind_farm():
    turbines = [
        _rec("wind", EinheitMastrNummer="W1", EinheitBetriebsstatus="In Betrieb"),
        _rec(
            "wind", EinheitMastrNummer="W2", EinheitBetriebsstatus="In Planung", Laengengrad=11.502
        ),
    ]
    site = next(iter(MaStRSource().transform(turbines)))
    # a farm with any unit still in planning is treated as under construction
    assert site.mastr_status == "In Planung"
