"""Corrected candidate-site count using the verified MaStR column names.

Solar: ground-mounted (Lage == 'Freifläche') AND Nettonennleistung >= 5 MW.
Other generation tech: Nettonennleistung >= 5 MW (inherently ground-based facilities).
Reports a status breakdown (In Betrieb / In Planung / stillgelegt) — 'In Planung' and
recently commissioned units are the construction-monitoring targets.

Run: uv run python scripts/probe_mastr_count.py
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

ZIP = Path(__file__).resolve().parent.parent / "data" / "bnetza_open_mastr_2025-02-09.zip"
MIN_KW = 5000

TECH_FILES = {
    "solar": "bnetza_mastr_solar_raw.csv",
    "wind": "bnetza_mastr_wind_raw.csv",
    "biomass": "bnetza_mastr_biomass_raw.csv",
    "hydro": "bnetza_mastr_hydro_raw.csv",
    "gsgk": "bnetza_mastr_gsgk_raw.csv",
    "combustion": "bnetza_mastr_combustion_raw.csv",
    "storage": "bnetza_mastr_storage_raw.csv",
}

CAP = "Nettonennleistung"
STATUS = "EinheitBetriebsstatus"
LAT = "Breitengrad"
STATE = "Bundesland"
LAGE = "Lage"  # solar siting; 'Freifläche' == ground-mounted


def _member(z: zipfile.ZipFile, filename: str) -> str:
    return next(n for n in z.namelist() if n.endswith(filename))


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    print(
        f"{'tech':12} {'>=5MW':>7} {'monitorable':>11} {'w/coords':>9}   status breakdown (monitorable)"
    )
    grand = 0
    for tech, fname in TECH_FILES.items():
        member = _member(z, fname)
        n_big = n_site = n_coord = 0
        status_counts: Counter[str] = Counter()
        usecols = [CAP, STATUS, LAT, STATE] + ([LAGE] if tech == "solar" else [])
        with z.open(member) as f:
            reader = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                usecols=lambda c: c in usecols,
                chunksize=200_000,
                low_memory=False,
            )
            for chunk in reader:
                cap = pd.to_numeric(chunk.get(CAP), errors="coerce")
                big = chunk[cap >= MIN_KW]
                n_big += len(big)
                site = big[big[LAGE] == "Freifläche"] if tech == "solar" else big
                n_site += len(site)
                if LAT in site:
                    n_coord += site[LAT].notna().sum()
                if STATUS in site:
                    status_counts.update(site[STATUS].dropna().astype(str))
        grand += n_site
        top = ", ".join(f"{k}={v}" for k, v in status_counts.most_common(4))
        print(f"{tech:12} {n_big:>7,} {n_site:>11,} {n_coord:>9,}   {top}")
    print(f"\nTOTAL monitorable sites (>=5 MW, ground-mounted, all tech, nationwide): {grand:,}")


if __name__ == "__main__":
    main()
