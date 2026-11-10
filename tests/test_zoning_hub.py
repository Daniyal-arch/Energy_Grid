"""Zoning hub classes (scripts/build_zoning_hub.py): local planning words map to the vocabulary."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_zoning_hub as bh  # noqa: E402


def test_local_words() -> None:
    cases = {
        "Tereny zabudowy mieszkaniowej jednorodzinnej": "residential",
        "Asuinkerrostalojen korttelialue": "residential",
        "zona industriale": "industrial",
        "Plochy lesní": "natural",
        "Teren wód powierzchniowych": "water",
        "Single family residential": "residential",
    }
    for label, cls in cases.items():
        assert bh.classify(label)[0] == cls, label


def test_english_unchanged() -> None:
    for label in ("sales", "tables", "Wholesale store"):
        assert bh.classify(label)[0] == "other", label
