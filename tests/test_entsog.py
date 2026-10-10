"""Rules of scripts/fetch_entsog.py on small made-up ENTSOG answers (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_entsog import Reference, build_pairs, newest_complete, select_reports  # noqa: E402

DAYS = ["2026-10-07", "2026-10-08"]


def opd(op, point, direction, own, adj, kind="Cross-Border Transmission IP within EU", pip=""):
    return {
        "operatorKey": op,
        "pointKey": point,
        "directionKey": direction,
        "pointType": kind,
        "tSOCountry": own,
        "adjacentCountry": adj,
        "pipeInPipeWithTsoKey": pip,
        "doubleReportingWithTsoKey": "",
    }


def row(op, point, direction, day, gwh, label=None):
    return {
        "operatorKey": op,
        "operatorLabel": op,
        "pointKey": point,
        "pointLabel": label or point,
        "directionKey": direction,
        "periodFrom": f"{day}T06:00:00+02:00",
        "value": gwh * 1e6,
    }


def ic(point, a_op, a, b_op, b):
    return {
        "pointKey": point,
        "fromOperatorKey": a_op,
        "fromCountryKey": a,
        "toOperatorKey": b_op,
        "toCountryKey": b,
    }


def test_pipe_in_pipe_guest_and_known_duplicate_are_left_out():
    ref = Reference(
        ic=[],
        cp={
            "ITP-00525": {"importFromCountryKey": "NO"},
            "ITP-00126": {"importFromCountryKey": "NO"},
        },
        opd=[
            opd("DE-TSO-0009", "ITP-00126", "entry", "DE", "NO"),
            opd("DE-TSO-0009", "ITP-00525", "entry", "DE", "NO"),
            opd("DE-TSO-0005", "ITP-00188", "entry", "DE", "NO", pip="DE-TSO-0009/ITP-00126"),
        ],
    )
    rows = [
        row(op, p, "entry", d, 700.8)
        for d in DAYS
        for op, p in [
            ("DE-TSO-0009", "ITP-00126"),
            ("DE-TSO-0009", "ITP-00525"),
            ("DE-TSO-0005", "ITP-00188"),
        ]
    ]
    reports = select_reports(rows, ref)
    assert [r.point for r in reports] == ["ITP-00126"]
    pairs = build_pairs(reports, DAYS, DAYS[-1], ref)
    assert pairs[0]["a"] == "NO" and pairs[0]["b"] == "DE" and pairs[0]["kind"] == "entry"
    assert pairs[0]["ab"] == [700.8, 700.8]


def test_vip_replaces_the_operators_physical_points_on_that_border():
    ref = Reference(
        ic=[],
        cp={},
        opd=[
            opd("NL-TSO-0001", "VIP-H", "exit", "NL", "DE"),
            opd("NL-TSO-0001", "BOCHOLTZ", "exit", "NL", "DE"),
        ],
    )
    rows = [row("NL-TSO-0001", "VIP-H", "exit", d, 352.1, "VIP TTF-THE-H") for d in DAYS] + [
        row("NL-TSO-0001", "BOCHOLTZ", "exit", d, 317.9, "Bocholtz") for d in DAYS
    ]
    assert [r.label for r in select_reports(rows, ref)] == ["VIP TTF-THE-H"]


def test_border_is_read_from_the_importing_side_both_directions():
    ref = Reference(
        ic=[ic("P1", "AT-TSO", "AT", "DE-TSO", "DE"), ic("P1", "DE-TSO", "DE", "AT-TSO", "AT")],
        cp={},
        opd=[
            opd("AT-TSO", "P1", "entry", "AT", "DE"),
            opd("AT-TSO", "P1", "exit", "AT", "DE"),
            opd("DE-TSO", "P1", "exit", "DE", "AT"),
        ],
    )
    rows = []
    for d in DAYS:
        rows += [
            row("AT-TSO", "P1", "entry", d, 180.0),
            row("AT-TSO", "P1", "exit", d, 5.0),
            row("DE-TSO", "P1", "exit", d, 140.0),
        ]
    (pair,) = build_pairs(select_reports(rows, ref), DAYS, DAYS[-1], ref)
    # AT reports the larger net import: a=AT, b=DE, so a>b is AT's exit
    assert (pair["a"], pair["b"], pair["read_from"]) == ("AT", "DE", "AT")
    assert pair["ab"] == [5.0, 5.0] and pair["ba"] == [180.0, 180.0]
    assert pair["net"] == [-175.0, -175.0]
    assert pair["other_side_net"] == [-140.0, -140.0]


def test_sources_outside_carry_entsogs_origin_and_tap_sits_in_greece():
    ref = Reference(
        ic=[ic("KIPOI", "TR-TSO", "TR", "AL-TSO-0001", "GR")],
        cp={"KIPOI": {"importFromCountryKey": "AZ"}},
        opd=[
            opd("AL-TSO-0001", "KIPOI", "entry", "CH", "TR"),
            opd("AL-TSO-0001", "NEA", "exit", "CH", "GR"),
        ],
    )
    rows = [row("AL-TSO-0001", "KIPOI", "entry", d, 345.3) for d in DAYS] + [
        row("AL-TSO-0001", "NEA", "exit", d, 10.0) for d in DAYS
    ]
    reports = select_reports(rows, ref)
    # Nea Mesimvria is inside Greece once TAP is placed there: no border
    assert [(r.point, r.country, r.neighbour) for r in reports] == [("KIPOI", "GR", "TR")]
    (pair,) = build_pairs(reports, DAYS, DAYS[-1], ref)
    assert (pair["a"], pair["b"]) == ("AZ-TR", "GR")


def test_newest_complete_waits_for_every_point_of_the_day_before():
    ref = Reference(
        ic=[], cp={}, opd=[opd("A", "P1", "entry", "AT", "DE"), opd("A", "P2", "entry", "AT", "DE")]
    )
    days = ["2026-10-06", "2026-10-07", "2026-10-08"]
    rows = [row("A", p, "entry", d, 1.0) for p in ("P1", "P2") for d in days[:2]] + [
        row("A", "P1", "entry", days[2], 1.0)
    ]
    assert newest_complete(select_reports(rows, ref), days) == "2026-10-07"
