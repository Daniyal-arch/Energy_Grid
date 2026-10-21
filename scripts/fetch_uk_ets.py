"""Verified CO2 per installation in the UK ETS (brief 22, family 7), beside the EU ETS file.

    python scripts/fetch_uk_ets.py [--out DIR]

The UK ETS registry's public "Compliance Report Emissions and Surrenders" (UK Emissions Trading
Registry, reports.view-emissions-trading-registry.service.gov.uk, OGL v3.0, refreshed by the
registry): recorded (verified) emissions per installation and year, t CO2e. Only operator holding
accounts (installations); aircraft and maritime operators are left out, as in the EU file.
"EXCLUDED" and blanks are no value. Northern Ireland's power stations stay in the EU ETS (registry
XI in ets.json); its other installations are in the UK ETS, so nothing is counted twice.

The report gives no activity and no position, and the EEA's industrial register holds no UK site
since 2020: the installations are listed with their emissions (registry "GB", group "Activity not
published (UK ETS)") and are not placed on the map (no placing by name or address).

Merged into <out>/ets.json (run after fetch_eu_ets.py), on the EU file's years.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
BASE = "https://reports.view-emissions-trading-registry.service.gov.uk"
SECTION = f"{BASE}/ets-reports/section5/section5.html"
GROUP = "Activity not published (UK ETS)"
SOURCE = "UK Emissions Trading Registry, Compliance Report Emissions and Surrenders (OGL v3.0)"


def installations(raw: bytes) -> tuple[dict[int, int], list[dict]]:
    """({year: column}, rows of operator holding accounts) from the report's Data sheet."""
    import openpyxl

    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)["Data"]
    it = ws.iter_rows(values_only=True)
    head = [str(h or "") for h in next(it)]
    years = {
        int(m.group(1)): i
        for i, h in enumerate(head)
        if (m := re.fullmatch(r"Recorded emissions (\d{4})", h))
    }
    col = {h: i for i, h in enumerate(head)}
    rows = []
    for r in it:
        if r[col["Account type"]] != "OPERATOR_HOLDING_ACCOUNT":
            continue
        rows.append(
            {
                "id": str(r[col["Operator ID"]]),
                "permit": r[col["Permit ID or Monitoring plan ID"]],
                "name": str(r[col["Installation name"]] or r[col["Account Holder Name"]]).strip(),
                "t": {y: r[i] if isinstance(r[i], int | float) else None for y, i in years.items()},
            }
        )
    return years, rows


def merge(ets: dict, rows: list[dict], fetched: str) -> dict:
    """The UK rows into the EU file: registry GB, the file's years, unplaced."""
    years: list[int] = ets["years"]
    if GROUP not in ets["groups"]:
        ets["groups"].append(GROUP)
    g = ets["groups"].index(GROUP)
    kept = [r for r in ets["rows"] if r[0] != "GB"]
    c = {"n": 0, "placed": 0, "t": [0] * len(years), "t_placed": 0}
    for r in rows:
        t = [int(r["t"][y]) if r["t"].get(y) is not None else None for y in years]
        if not any(t):
            continue
        kept.append(["GB", r["id"], r["name"], g, t, None, None])
        c["n"] += 1
        for i, v in enumerate(t):
            c["t"][i] += v or 0
    kept.sort(key=lambda r: -(r[4][-1] or 0))
    ets["rows"] = kept
    ets["countries"]["GB"] = c
    ets["countries"] = dict(sorted(ets["countries"].items()))
    ets["uk"] = {"source": SOURCE, "url": SECTION, "fetched": fetched}
    return ets


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    html = w7.get(SECTION).text
    m = re.search(r'href="(/ets-reports/section5/[^"]+\.xlsx)"', html)
    if not m:
        raise SystemExit(f"{SECTION}: no compliance report")
    _, rows = installations(w7.get(BASE + m.group(1).replace("&amp;", "&")).content)
    path = args.out / "ets.json"
    ets = json.loads(path.read_text(encoding="utf-8"))
    ets = merge(ets, rows, w7.TODAY)
    path.write_text(json.dumps(ets, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    c = ets["countries"]["GB"]
    print(f"UK ETS: {c['n']} installations, {ets['newest']}: {c['t'][-1] / 1e6:.1f} Mt -> {path}")


if __name__ == "__main__":
    main()
