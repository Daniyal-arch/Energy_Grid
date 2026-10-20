"""Power cuts per country (brief 22, family 11): SAIDI and SAIFI where published as data.

    python scripts/fetch_reliability.py [--out DIR]

World Bank, Doing Business "Getting electricity" (API, CC BY 4.0), the one series published as
data for every EU country, the UK and the US:
  IC.ELC.SAID.XD.DB1619   system average interruption duration (SAIDI), hours per customer a year
  IC.ELC.SAIF.XD.DB1619   system average interruption frequency (SAIFI), interruptions a customer a year
measured in the economy's largest business city (two cities for the US: New York and Los
Angeles, weighted by population by the World Bank), data years 2014 to 2019; Doing Business was
discontinued in 2021. Values passed through. CEER's benchmarking reports carry national SAIDI
and SAIFI as PDF tables only and BNetzA publishes Germany's SAIDI in a press release, so neither
is read here (docs/COVERAGE.md).

Writes frontend/public/data/eu/reliability.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
API = "https://api.worldbank.org/v2/country/{codes}/indicator/{ind}"
INDICATORS = {"saidi": "IC.ELC.SAID.XD.DB1619", "saifi": "IC.ELC.SAIF.XD.DB1619"}
ISO3 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE", "DK": "DNK", "EE": "EST",
    "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC", "HU": "HUN", "IE": "IRL", "IT": "ITA", "LV": "LVA",
    "LT": "LTU", "LU": "LUX", "MT": "MLT", "NL": "NLD", "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK",
    "SI": "SVN", "ES": "ESP", "SE": "SWE", "GB": "GBR", "US": "USA",
}  # fmt: skip


def rows_to_series(rows: list[dict]) -> dict[str, list[list]]:
    """{ISO2: [[year, value]] oldest first} from World Bank API rows (nulls left out)."""
    by3 = {v: k for k, v in ISO3.items()}
    out: dict[str, list[list]] = {}
    for r in rows:
        cc = by3.get(r.get("countryiso3code") or "")
        if cc and r.get("value") is not None:
            out.setdefault(cc, []).append([int(r["date"]), r["value"]])
    return {cc: sorted(v) for cc, v in sorted(out.items())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    codes = ";".join(ISO3.values())
    series: dict[str, dict] = {}
    names: dict[str, str] = {}
    for key, ind in INDICATORS.items():
        meta, rows = w7.get(
            API.format(codes=codes, ind=ind), params={"format": "json", "per_page": 2000}
        ).json()
        names[key] = rows[0]["indicator"]["value"] if rows else ind
        for cc, pts in rows_to_series(rows).items():
            series.setdefault(cc, {})[key] = pts
        print(f"  {key}: {len(rows)} rows, last updated {meta.get('lastupdated')}", flush=True)
    data = {
        "source": "World Bank, Doing Business: Getting electricity (SAIDI, SAIFI), CC BY 4.0",
        "url": "https://data.worldbank.org/indicator/IC.ELC.SAID.XD.DB1619",
        "fetched": w.now(),
        "names": names,
        "units": {
            "saidi": "hours per customer a year",
            "saifi": "interruptions per customer a year",
        },
        "note": "Measured in the largest business city (US: New York and Los Angeles), data years 2014-2019; the series ended with Doing Business in 2021",
        "countries": series,
    }
    w.write_json(args.out / "reliability.json", data)
    print(f"{len(series)} countries with values", flush=True)


if __name__ == "__main__":
    main()
