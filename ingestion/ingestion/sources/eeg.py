"""EEG auction deadlines -> deadlines table.

German renewable auctions (Bundesnetzagentur) award a subsidy plus a statutory
realization deadline: a solar award is forfeited if the plant is not commissioned
within 24 months of the award announcement (§ 55 EEG 2023). We derive each awarded
site's legal completion deadline from its MaStR `Zuschlagsnummer`, which encodes the
auction series + year + round (e.g. SOL23-1 = Solar first-segment, 2023, round 1).

Two deadline types are written:
  * legal_completion     auction bid date (Gebotstermin) + 24 months  [from Zuschlagsnummer]
  * planned_commissioning GeplantesInbetriebnahmedatum                 [registry planned date]

Gebotstermine are anchored to the published solar first-segment cadence (round 1 ≈ 1 Mar,
2 ≈ 1 Jul, 3 ≈ 1 Dec); the legal deadline is therefore a derived, month-precision estimate
(the source string records the basis). Exact per-round Gebotstermine can replace the
cadence table without changing anything downstream.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from app.config import get_settings
from app.models import Deadline

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

SOLAR_CSV = "bnetza_mastr_solar_raw.csv"
REALIZATION_MONTHS = 24  # § 55 EEG 2023: forfeited if not commissioned within 24 months

# Solar first-segment auction cadence: round number -> Gebotstermin month (day 1).
# Anchored to the published schedule (recent years: 1 Mar / 1 Jul / 1 Dec).
_ROUND_MONTH = {1: 3, 2: 7, 3: 12, 4: 12, 5: 12, 6: 12}
_ZN = re.compile(r"^\s*([A-Za-z]+)(\d{2})-(\d+)")

C_ID = "EinheitMastrNummer"
C_CAP = "Nettonennleistung"
C_LAGE = "Lage"
C_STATUS = "EinheitBetriebsstatus"
C_ZN = "Zuschlagsnummer"
C_PLANNED = "GeplantesInbetriebnahmedatum"


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _gebotstermin(zuschlagsnummer: str) -> tuple[date, str] | None:
    """Parse a Zuschlagsnummer -> (auction bid date, round label), or None."""
    first = zuschlagsnummer.split(";")[0].strip()
    m = _ZN.match(first)
    if not m:
        return None
    series, yy, rnd = m.group(1), int(m.group(2)), int(m.group(3))
    year = 2000 + yy
    if year < 2014 or year > date.today().year + 1:
        return None
    month = _ROUND_MONTH.get(rnd, 12)
    return date(year, month, 1), f"{series}{yy}-{rnd}"


def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@register
class EEGSource(BaseSource):
    meta = SourceMeta(
        name="eeg",
        description="EEG auction legal completion deadlines (Zuschlagsnummer + 24mo realization)",
        cadence="monthly",
        requires_credentials=(),
        phase=2,
        site_scoped=False,
    )

    def _zip(self) -> zipfile.ZipFile:
        path = Path(get_settings().mastr_zip_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        return zipfile.ZipFile(path)

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        z = self._zip()
        member = next(n for n in z.namelist() if n.endswith(SOLAR_CSV))
        usecols = [C_ID, C_CAP, C_LAGE, C_STATUS, C_ZN, C_PLANNED]
        with z.open(member) as f:
            reader = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                usecols=lambda c: c in usecols,
                chunksize=200_000,
                low_memory=False,
            )
            for chunk in reader:
                cap = pd.to_numeric(chunk[C_CAP], errors="coerce")
                sel = chunk[(cap >= 5000) & (chunk[C_LAGE] == "Freifläche")]
                sel = sel[sel[C_ZN].notna() | sel[C_PLANNED].notna()]
                yield from sel.to_dict("records")

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[dict[str, Any]]:
        # site_id is resolved in load(); carry mastr_id + the two candidate deadlines
        for rec in raw:
            mastr_id = str(rec[C_ID])
            zn = rec.get(C_ZN)
            if zn is not None and not (isinstance(zn, float) and pd.isna(zn)):
                parsed = _gebotstermin(str(zn))
                if parsed:
                    gebot, label = parsed
                    src = f"EEG auction {label} (Gebotstermin {gebot.isoformat()} + 24mo, §55 EEG)"
                    yield {
                        "mastr_id": mastr_id,
                        "type": "legal_completion",
                        "deadline_date": _add_months(gebot, REALIZATION_MONTHS),
                        "source": src,
                    }
            planned = _parse_date(rec.get(C_PLANNED))
            if planned:
                yield {
                    "mastr_id": mastr_id,
                    "type": "planned_commissioning",
                    "deadline_date": planned,
                    "source": "MaStR planned commissioning date",
                }

    def load(self, records: Iterable[dict[str, Any]], db: Client) -> LoadStats:
        records = list(records)
        wanted = {r["mastr_id"] for r in records}
        # resolve mastr_id -> site_id (paginate past the 1000-row cap)
        id_map: dict[str, str] = {}
        page = 0
        while True:
            batch = (
                db.table("sites")
                .select("id, mastr_id")
                .eq("technology", "solar")
                .range(page * 1000, page * 1000 + 999)
                .execute()
                .data
                or []
            )
            for row in batch:
                if row["mastr_id"] in wanted:
                    id_map[row["mastr_id"]] = row["id"]
            if len(batch) < 1000:
                break
            page += 1

        rows = [
            Deadline(
                site_id=id_map[r["mastr_id"]],
                source=r["source"],
                deadline_date=r["deadline_date"],
                type=r["type"],
            ).model_dump(mode="json", exclude_none=True)
            for r in records
            if r["mastr_id"] in id_map
        ]
        for i in range(0, len(rows), 500):
            db.table("deadlines").upsert(
                rows[i : i + 500], on_conflict="site_id,source,type"
            ).execute()
        return LoadStats(loaded=len(rows), skipped=len(records) - len(rows))
