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
