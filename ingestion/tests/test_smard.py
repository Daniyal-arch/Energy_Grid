"""SMARD adapter smoke test with the two-step HTTP API mocked (respx)."""

from datetime import UTC, date, datetime

import respx
from httpx import Response
from ingestion.base import RunContext
from ingestion.sources.smard import FILTERS, SmardSource, _to_date

FILE_TS = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)
MAY_MS = int(datetime(2026, 5, 1, tzinfo=UTC).timestamp() * 1000)


def test_to_date_lands_on_correct_calendar_day():
    assert _to_date(MAY_MS) == date(2026, 5, 1)


@respx.mock
def test_fetch_and_transform_yields_power_rows():
    respx.get(url__regex=r".*/index_day\.json").mock(
        return_value=Response(200, json={"timestamps": [FILE_TS]})
    )
    respx.get(url__regex=r".*_DE_day_\d+\.json").mock(
        return_value=Response(200, json={"series": [[MAY_MS, 1234.5], [MAY_MS + 86_400_000, None]]})
    )
    source = SmardSource()
    ctx = RunContext(db=None, since=date(2026, 4, 1), until=date(2026, 6, 1))

    raw = list(source.fetch(ctx))
    # one non-null point per technology filter
    assert len(raw) == len(FILTERS)

    rows = list(source.transform(raw))
    labels = {r.plant_id for r in rows}
    assert "DE-solar" in labels
    assert all(r.source == "smard" and r.date == date(2026, 5, 1) for r in rows)
    assert rows[0].mwh == 1234.5
