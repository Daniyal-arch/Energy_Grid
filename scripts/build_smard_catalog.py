"""SMARD (Bundesnetzagentur, CC BY 4.0): the agent's catalogue entry, no lake copy (brief 17, 9).

SMARD's chart API answers without a key: `chart_data/{filter}/{region}/index_{resolution}.json`
lists the weekly files (their first timestamps, ms since 1970 UTC), and
`chart_data/{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json` holds
`series: [[ms, value], ...]`. Under the API-or-Parquet rule it stays an API: this script checks
each series the catalogue names, reads its newest value, and writes agent/catalog/smard.yaml
with those values as the examples.

    python scripts/build_smard_catalog.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import wave5_common as w

BASE = "https://www.smard.de/app/chart_data"
# filter id -> (name, unit); generation in MW per quarter-hour, price in EUR/MWh
SERIES: dict[int, tuple[str, str]] = {
    410: ("Electricity consumption (grid load)", "MWh per interval"),
    4359: ("Residual load", "MWh per interval"),
    1223: ("Generation: lignite", "MWh per interval"),
    1224: ("Generation: nuclear", "MWh per interval"),
    1225: ("Generation: wind offshore", "MWh per interval"),
    1226: ("Generation: hydro", "MWh per interval"),
    1227: ("Generation: other conventional", "MWh per interval"),
    1228: ("Generation: other renewable", "MWh per interval"),
    4066: ("Generation: biomass", "MWh per interval"),
    4067: ("Generation: wind onshore", "MWh per interval"),
    4068: ("Generation: solar", "MWh per interval"),
    4069: ("Generation: hard coal", "MWh per interval"),
    4070: ("Generation: pumped storage", "MWh per interval"),
    4071: ("Generation: natural gas", "MWh per interval"),
    4169: ("Day-ahead price DE/LU", "EUR/MWh"),
}
REGION = "DE"
RESOLUTION = "hour"


def newest(series: list[list[float | None]]) -> tuple[int, float] | None:
    """The newest [ms, value] pair with a value (SMARD pads a week's file with nulls)."""
    for ms, v in reversed(series):
        if v is not None:
            return int(ms), float(v)
    return None


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def main() -> None:
    lines = [
        "dataset: smard",
        "title: SMARD electricity market data, Germany (Bundesnetzagentur)",
        "licence: CC BY 4.0",
        "access: api  # no lake copy (docs/DATA_LAKE.md, the API-or-Parquet rule)",
        f"api: {q(BASE + '/{filter}/{region}/index_{resolution}.json then /{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json')}",
        "notes: weekly files; series = [[ms since 1970 UTC, value], ...]; regions DE, AT, LU, DE-LU, 50Hertz, Amprion, TenneT, TransnetBW; resolutions hour, quarterhour, day, week, month, year",
        "series:",
    ]
    examples = []
    for fid, (name, unit) in SERIES.items():
        try:
            index = w.get_json(f"{BASE}/{fid}/{REGION}/index_{RESOLUTION}.json")
        except SystemExit as e:
            print(f"  {fid} {name}: {e}", flush=True)
            continue
        stamps = index["timestamps"]  # type: ignore[index]
        part = w.get_json(f"{BASE}/{fid}/{REGION}/{fid}_{REGION}_{RESOLUTION}_{stamps[-1]}.json")
        last = newest(part["series"])  # type: ignore[index]
        first = datetime.fromtimestamp(stamps[0] / 1000, UTC).date().isoformat()
        lines.append(
            f"  {fid}: {{name: {q(name)}, unit: {q(unit)}, from: {first}, weekly_files: {len(stamps)}}}"
        )
        if last:
            at = datetime.fromtimestamp(last[0] / 1000, UTC).isoformat(timespec="minutes")
            examples.append((fid, name, unit, at, last[1]))
        print(f"  {fid} {name}: {len(stamps)} weekly files from {first}, newest {last}", flush=True)
    lines.append("examples:")
    for fid, name, unit, at, v in examples[:2]:
        lines += [
            f"  - q: {q(f'{name}, Germany, hour starting {at}')}",
            f"    call: {q(f'GET {BASE}/{fid}/{REGION}/index_{RESOLUTION}.json, then the newest weekly file; the last non-null pair')}",
            f"    answer: {q(f'{v} {unit} (read {w.now()[:10]})')}",
        ]
    out = w.ROOT / "agent" / "catalog" / "smard.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(w.ROOT)}: {len(examples)} series answered", flush=True)


if __name__ == "__main__":
    main()
