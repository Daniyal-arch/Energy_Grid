"""What UK consumers pay, in Eurostat's own bands (brief 22, family 6).

    python scripts/fetch_gb_retail.py [--out DIR]

DESNZ "International domestic / non-domestic energy prices" (Quarterly Energy Prices, OGL v3.0):
the UK's price per half-year in the same consumption bands Eurostat uses, with and without taxes,
in pence per kWh. Matched to retail.json's series (scripts/fetch_retail_prices.py):
  elec_household  DC, 2,500-4,999 kWh       table 5.6.2 (medium)   incl. tax -> I_TAX, excl. -> X_TAX
  gas_household   D2, 20-199 GJ             table 5.10.2 (medium)  incl. tax -> I_TAX, excl. -> X_TAX
  gas_business    I3, 10,000-99,999 GJ      table 5.8.2 (medium)   incl. tax (excl. VAT) -> X_VAT, excl. -> X_TAX
  elec_business   IC, 500-1,999 MWh         DESNZ publishes no IC band (its bands are 20-499 and
                                            2,000-19,999 MWh): left empty, not substituted.
Converted from pence to EUR with the ECB's average GBP rate over the half-year (computed); the
pence figures are kept beside them. Ofgem's price cap is a ceiling for default tariffs, not an
average price, so it is not used for the comparison.

Merged into <out>/retail.json as country "GB" (run after fetch_retail_prices.py).
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
from build_gb_prices import ECB, ecb_gbp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
DOMESTIC = (
    "https://www.gov.uk/government/statistical-data-sets/international-domestic-energy-prices"
)
NON_DOMESTIC = (
    "https://www.gov.uk/government/statistical-data-sets/international-industrial-energy-prices"
)
# series -> (page, file pattern, sheet prefix, {incl: field, excl: field})
TABLES = {
    "elec_household": (
        DOMESTIC,
        r"table_561[^\"]*\.xlsx",
        "5.6.2",
        {"incl": "I_TAX", "excl": "X_TAX"},
    ),
    "gas_household": (
        DOMESTIC,
        r"table_5101[^\"]*\.xlsx",
        "5.10.2",
        {"incl": "I_TAX", "excl": "X_TAX"},
    ),
    "gas_business": (
        NON_DOMESTIC,
        r"table_581[^\"]*\.xlsx",
        "5.8.2",
        {"incl": "X_VAT", "excl": "X_TAX"},
    ),
}


def uk_semesters(path_or_bytes: bytes, sheet: str) -> dict[str, float]:
    """{YYYY-S1|S2: pence per kWh} of the United Kingdom column of one DESNZ sheet."""
    import openpyxl

    ws = openpyxl.load_workbook(io.BytesIO(path_or_bytes), read_only=True, data_only=True)[sheet]
    out: dict[str, float] = {}
    col = None
    for r in ws.iter_rows(values_only=True):
        if r and r[0] == "Year":
            col = list(r).index("United Kingdom")
            continue
        if col is None or not r or not isinstance(r[0], int | float) or r[col] is None:
            continue
        period = str(r[1] or "")
        half = "S1" if period.startswith("Jan") else "S2" if period.startswith("Jul") else None
        v = (
            r[col]
            if isinstance(r[col], int | float)
            else w7.number(re.sub(r"[^\d.,-]", "", str(r[col])))
        )
        if half and v is not None:
            out[f"{int(r[0])}-{half}"] = float(v)
    return out


def semester_rate(rates: dict[str, float], semester: str) -> float | None:
    """The average GBP per EUR over the half-year's published days."""
    year, half = semester.split("-")
    months = range(1, 7) if half == "S1" else range(7, 13)
    vals = [v for d, v in rates.items() if d[:4] == year and int(d[5:7]) in months]
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    path = args.out / "retail.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    eu = data["eu"]
    periods: list[str] = eu["periods"]
    rates = ecb_gbp(w7.get(ECB).content)
    pages: dict[str, str] = {}
    pence: dict[str, dict] = {}
    for series, (page, pattern, prefix, fields) in TABLES.items():
        html = pages.setdefault(page, w7.get(page).text)
        m = re.search(
            rf'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*{pattern})"', html
        )
        if not m:
            raise SystemExit(f"{page}: no {pattern}")
        raw = w7.get(m.group(1)).content
        row: dict[str, list] = {f: [None] * len(periods) for f in ("I_TAX", "X_VAT", "X_TAX")}
        kept: dict[str, dict[str, float]] = {}
        for which, field in fields.items():
            sem = uk_semesters(raw, f"{prefix} (Medium {which} tax)")
            kept[field] = {p: sem[p] for p in periods if p in sem}
            for k, p in enumerate(periods):
                r = semester_rate(rates, p)
                if p in sem and r:
                    row[field][k] = round(sem[p] / 100 / r, 4)
        eu["series"][series]["GB"] = {**row, "flags": [None] * len(periods)}
        pence[series] = kept
        print(
            f"  {series}: {sum(v is not None for v in row[fields['incl']])} of {len(periods)} half-years",
            flush=True,
        )
    eu["gb"] = {
        "source": "DESNZ international domestic and non-domestic energy prices (Quarterly Energy Prices), OGL v3.0",
        "conversion": "pence per kWh / 100 / the ECB's average GBP per EUR over the half-year (computed)",
        "pence_per_kwh": pence,
        "not_published": {"elec_business": "DESNZ publishes no 500-1,999 MWh (IC) band for the UK"},
    }
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"-> {path}", flush=True)


if __name__ == "__main__":
    main()
