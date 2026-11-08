from agent.grounding import check, numbers_in_text


def test_numbers_extracted_and_skipped():
    nums = [
        n[0]
        for n in numbers_in_text(
            "In 2025, DK1 had 436.25 hours; top 5 zones; 1,234 MW on 2026-10-01 in table x.y2"
        )
    ]
    assert nums == ["436.25", "1,234"]


def test_precision_and_scales():
    results = [{"rows": [["NL", 103.03, 436.25, 15507.6, 0.423]]}]
    ok = check(
        "NL averaged 103.03 EUR/MWh with 436.25 hours below zero; 15,508 MW (15.5 GW); 42.3 %.",
        results,
    )
    assert ok["ungrounded"] == [] and ok["score"] == 1.0
    bad = check("NL averaged 104.10 EUR/MWh.", results)
    assert bad["ungrounded"] == ["104.10"] and bad["score"] == 0.0


def test_question_numbers_allowed():
    r = check("Plants within 50 km: 12,345 MW", [{"v": 12345}], question="within 50 km")
    assert r["ungrounded"] == []


def test_dates_and_percentages_are_grounded():
    """Brief 30 Track 4.7: an ISO date must be in the results; shares match as per cent."""
    from agent.grounding import check

    res = [
        {
            "data": {"rows": [[0.237, "2026-10-05"]]},
            "sources": [{"retrieved": "fetched 2026-11-01"}],
        }
    ]
    ok = check("Share 23.7 % as of 2026-11-01, period from 2026-10-05.", res)
    assert ok["ungrounded"] == [] and ok["grounded"] == 3
    bad = check("As of 2025-01-01 the share was 23.7 %.", res)
    assert bad["ungrounded"] == ["2025-01-01"]
