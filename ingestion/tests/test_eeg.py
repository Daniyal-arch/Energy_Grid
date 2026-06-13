"""EEG deadline-derivation tests (pure parsing/derivation; no I/O)."""

from datetime import date

from ingestion.sources.eeg import EEGSource, _add_months, _gebotstermin


def test_add_months_rolls_over_year():
    assert _add_months(date(2023, 3, 1), 24) == date(2025, 3, 1)
    assert _add_months(date(2023, 12, 1), 1) == date(2024, 1, 1)


def test_gebotstermin_parses_award_number():
    gebot, label = _gebotstermin("SOL23-1/112")
    assert gebot == date(2023, 3, 1)
    assert label == "SOL23-1"
    # FFA series (older ground-mounted pilot auctions)
    g2, l2 = _gebotstermin("FFA15-3/110")
    assert g2 == date(2015, 12, 1) and l2 == "FFA15-3"


def test_gebotstermin_handles_multiple_and_junk():
    # multiple awards: take the first
    assert _gebotstermin("SOL17-2/123; SOL18-2/037")[1] == "SOL17-2"
    assert _gebotstermin("not-an-award") is None


def test_transform_emits_legal_and_planned_deadlines():
    rec = {
        "EinheitMastrNummer": "SEE1",
        "Nettonennleistung": 8000.0,
        "Lage": "Freifläche",
        "EinheitBetriebsstatus": "In Planung",
        "Zuschlagsnummer": "SOL23-1/112",
        "GeplantesInbetriebnahmedatum": "2025-06-30",
    }
    out = list(EEGSource().transform([rec]))
    types = {d["type"]: d for d in out}
    assert types["legal_completion"]["deadline_date"] == date(2025, 3, 1)  # 2023-03 + 24mo
    assert "§55 EEG" in types["legal_completion"]["source"]
    assert types["planned_commissioning"]["deadline_date"] == date(2025, 6, 30)
