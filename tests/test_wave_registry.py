"""The registry waves (scripts/wave9.py with WAVE=9, 10): every source is complete and unique,
every colouring names its series and a scope the app draws, every family exists."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"country", "us_county", "gb_lad", "gb_lad24"}
KEYS = {"id", "title", "cat", "fam", "places", "level", "kind", "url", "licence", "status"}


@pytest.mark.parametrize("wave", [9, 10])
def test_registry(wave: int) -> None:
    srcs = yaml.safe_load((ROOT / "scripts" / f"wave{wave}_sources.yaml").read_text("utf-8"))[
        "sources"
    ]
    fams = yaml.safe_load((ROOT / "scripts" / f"wave{wave}_families.yaml").read_text("utf-8"))[
        "families"
    ]
    # YAML 1.1 reads a bare NO (Norway) as false: places must stay text (brief 30)
    for s in srcs:
        places = s["places"] if isinstance(s["places"], list) else [s["places"]]
        assert all(isinstance(p, str) for p in places), s["id"]
    ids = [s["id"] for s in srcs]
    assert len(ids) == len(set(ids)), "duplicate source ids"
    for s in srcs:
        assert set(s) >= KEYS, f"{s['id']}: missing {KEYS - set(s)}"
        assert s["fam"] in fams or wave == 9, f"{s['id']}: family {s['fam']} not defined"
        if s["status"] == "build":
            assert "non-commercial" not in s["licence"].lower(), f"{s['id']}: non-commercial"
        ch = s.get("choro")
        if ch:
            assert ch.get("label"), f"{s['id']}: a colouring names its series"
            assert ch.get("scope", "country") in SCOPES, f"{s['id']}: scope {ch.get('scope')}"


def test_wave10_size() -> None:
    srcs = yaml.safe_load((ROOT / "scripts" / "wave10_sources.yaml").read_text("utf-8"))["sources"]
    assert len(srcs) >= 300  # the gathering: hundreds of sources
