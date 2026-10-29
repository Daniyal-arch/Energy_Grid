"""The coverage registry (scripts/coverage.py): every family x country cell is filled."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import coverage  # noqa: E402


def test_every_cell_is_filled() -> None:
    reg = coverage.load()
    assert len(coverage.COUNTRIES) == 29
    assert coverage.problems(reg) == []


def test_glyphs() -> None:
    assert coverage.glyph({"status": "built"}) == "✅"
    assert coverage.glyph({"status": "have", "partial": True}) == "◐"
    assert coverage.glyph({"status": "have", "parts": [{"status": "blocked"}]}) == "◐"
    assert coverage.glyph({"status": "not_published"}) == "—"
    assert coverage.glyph({"status": "blocked"}) == "⛔"


def test_problems_name_missing_evidence() -> None:
    cell = {"status": "not_published", "url": "https://example.org"}
    reg = {"families": {"x": {"name": "X", "shows": "x", "cells": {"AT": cell}}}}
    out = coverage.problems(reg)
    assert "x/AT: not_published needs checked" in out
    assert "x/DE: missing" in out


def test_json_has_every_country() -> None:
    j = coverage.to_json(coverage.load())
    assert set(j["countries"]) == set(coverage.COUNTRIES) | set(coverage.NEIGHBOURS)
    assert all(len(j["countries"][cc]) == len(j["families"]) for cc in coverage.COUNTRIES)
    # a neighbour holds only the families that cover the neighbours (room to connect)
    assert all(set(j["countries"][cc]) == {"connect"} for cc in coverage.NEIGHBOURS)


def test_neighbours_only_where_a_family_lists_them() -> None:
    cell = {
        "status": "not_published",
        "url": "https://example.org",
        "note": "n",
        "checked": "2026-10-28",
    }
    cells = dict.fromkeys(coverage.COUNTRIES, cell)
    reg = {"families": {"x": {"name": "X", "shows": "x", "cells": dict(cells)},
                        "y": {"name": "Y", "shows": "y", "regions": ["neighbours"], "cells": dict(cells)}}}  # fmt: skip
    out = coverage.problems(reg)
    assert "y/NO: missing" in out and "x/NO: missing" not in out
    reg["families"]["x"]["cells"]["TR"] = cell
    assert "x/TR: not a registry country" in coverage.problems(reg)
