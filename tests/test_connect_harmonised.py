"""Brief 23: the harmonised room-to-connect schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_connect_harmonised as h  # noqa: E402


def test_mw_class_has_no_threshold_but_zero() -> None:
    assert h.mw_class(None) is None
    assert h.mw_class(0) == "none"
    assert h.mw_class(0.1) == "available"


def test_norm_drops_station_words_voltage_and_accents() -> None:
    assert h.norm("UW Mattersburg 220 kV") == "mattersburg"
    assert h.norm("Subestación de Abadés 400") == "abades"
    assert h.norm("SÃO BRÁS DE ALPORTEL (*)") == "sao bras alportel"
    assert h.norm("TS Beli Manastir") == h.norm("BELI MANASTIR") == "beli manastir"
    assert h.norm("Stacja elektroenergetyczna Mikułowa") == "mikulowa"
    assert h.norm("Baja alállomás") == "baja"


def test_matcher_places_only_unique_names(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr(h, "OSM_CACHE", tmp_path)  # type: ignore[attr-defined]
    subs = [
        {"name": "Umspannwerk Ernsthofen", "lon": 14.47, "lat": 48.13, "osm": "way/1"},
        {"name": "UW Ernsthofen", "lon": 14.471, "lat": 48.131, "osm": "node/2"},  # same site twice
        {"name": "Umspannwerk Neusiedl", "lon": 16.84, "lat": 47.95, "osm": "way/3"},
        {"name": "Neusiedl", "lon": 15.20, "lat": 48.00, "osm": "way/4"},  # same name, elsewhere
    ]
    (tmp_path / "AT.json").write_text(json.dumps(subs))
    match = h.matcher("AT", fetch=False)
    assert match("UW Ernsthofen") == (14.47, 48.13)
    assert match("UW Neusiedl") is None
    assert match("UW Nowhere") is None


def test_flat_polygons_reads_every_file_format() -> None:
    nl = [[[[4.0, 51.0], [4.1, 51.0], [4.1, 51.1]]]]
    se = [[[16.0, 60.0, 16.5, 60.0, 16.5, 60.4]]]
    it = [[10.0, 46.0, 11.0, 46.0, 11.0, 45.0]]
    assert h.flat_polygons(nl) == [[[4.0, 51.0, 4.1, 51.0, 4.1, 51.1]]]
    assert h.flat_polygons(se) == se
    assert h.flat_polygons(it) == [it]
    assert h.ring_centre(h.flat_polygons(it)) == (10.5, 45.5)


def test_every_row_has_a_known_class_and_operator() -> None:
    d = h.build(osm=False)
    f = {k: i for i, k in enumerate(d["fields"])}
    assert d["rows"] and len(d["operators"]) >= 19
    for r in d["rows"]:
        assert r[f["class"]] in (None, *h.CLASSES) and r[f["class_load"]] in (None, *h.CLASSES)
        assert 0 <= r[f["op"]] < len(d["operators"])
        assert r[f["kind"]] in ("node", "area")


# ---------------------------------------------------------------- brief-23 operators

import build_connect_h23 as h23  # noqa: E402


def test_mvm_rows_read_both_printed_layouts() -> None:
    demasz = [
        "DÉMÁSZ Baja BAJA 40 40 132 kV 28.60 11.40 31.58 8.42",
        "Hálózati Állomás header line",
    ]
    emasz = ["BABR Bükkábrány 10.5 10.5 25 25 14.5 14.5", "(MW)"]
    assert h23.mvm_rows(demasz, "demasz") == [
        {"name": "Baja", "id": "BAJA", "kv": 132.0, "mw_load": 11.4}
    ]
    assert h23.mvm_rows(emasz, "emasz") == [{"name": "Bükkábrány", "id": "BABR", "mw_load": 14.5}]


def test_operator_classes_map_one_to_one() -> None:
    assert set(h23.HOPS_CLASS.values()) <= set(h.CLASSES)
    assert h23.HOPS_CLASS["/"] == "none" and h23.HOPS_CLASS["A"] == "limited"
    assert h23.RAG == {"green": "available", "amber": "limited", "red": "none"}
    assert set(h23.HEDNO_CLASS.values()) == {"available", "limited", "none"}
    assert h23.mw_class(0.0) == "none" and h23.mw_class(None) is None


def test_extra_files_join_the_harmonised_rows() -> None:
    d = h.build(osm=False)
    ops = {o["operator"] for o in d["operators"]}
    assert {"50Hertz", "HOPS", "Elenia", "HEDNO"} <= ops


def test_row_matches_by_match_name_in_the_osm_area(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr(h, "OSM_CACHE", tmp_path)  # type: ignore[attr-defined]
    (tmp_path / "US-CA.json").write_text(
        json.dumps([{"name": "Larkin Substation", "lon": -122.42, "lat": 37.78, "osm": "way/1"}])
    )
    (tmp_path / "TR.json").write_text(
        json.dumps([{"name": "Misis TM", "lon": 35.6, "lat": 36.96, "osm": "way/2"}])
    )
    b = h.Build(osm=False)
    k = b.op(
        "US-CAISO",
        "CAISO",
        "transmission",
        source="s",
        url="u",
        licence="l",
        as_of=None,
        mapping="m",
    )
    b.row(k, name="LARKIN", match=True, osm_area="US-CA")
    t = b.op(
        "TR", "TEİAŞ", "transmission", source="s", url="u", licence="l", as_of=None, mapping="m"
    )
    b.row(t, name="MİSİS TM TR-B", match=True, match_name="MİSİS TM")
    assert [b.operators[k]["matched"], b.operators[t]["matched"]] == [1, 1]
    assert b.rows[0][h.FIELDS.index("lon")] == -122.42
    assert b.rows[1][h.FIELDS.index("name")] == "MİSİS TM TR-B"
