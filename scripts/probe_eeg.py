"""Probe: what EEG-auction data does MaStR give us, and can we derive a legal deadline?

EEG auctions (Bundesnetzagentur) award a subsidy + a statutory realization deadline
(Realisierungsfrist) — the legal date by which a project must be commissioned. We need
to attach that deadline to our sites. MaStR carries `Zuschlagsnummer` (award number) and
related auction fields; this probe shows their format/coverage so we can design the
deadline derivation.

Run: uv run python scripts/probe_eeg.py
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

ZIP = Path(__file__).resolve().parent.parent / "data" / "bnetza_open_mastr_2025-02-09.zip"
SOLAR = "bnetza_mastr_solar_raw.csv"

AUCTION_COLS = [
    "Nettonennleistung",
    "Lage",
    "EinheitBetriebsstatus",
    "Zuschlagsnummer",
    "ZugeordneteGebotsmenge",
    "AusschreibungZuschlag",
    "AnlagenkennzifferAnlagenregister",
    "EegInbetriebnahmedatum",
    "Inbetriebnahmedatum",
    "GeplantesInbetriebnahmedatum",
    "AnlagenschluesselEeg",
]


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    member = next(n for n in z.namelist() if n.endswith(SOLAR))

    n_total = n_ground_big = n_awarded = 0
    award_samples: list[str] = []
    award_prefix: Counter[str] = Counter()
    bool_auction: Counter[str] = Counter()
    has_planned = has_eeg_comm = 0

    with z.open(member) as f:
        reader = pd.read_csv(
            io.TextIOWrapper(f, encoding="utf-8"),
            usecols=lambda c: c in AUCTION_COLS,
            chunksize=200_000,
            low_memory=False,
        )
        for chunk in reader:
            n_total += len(chunk)
            cap = pd.to_numeric(chunk["Nettonennleistung"], errors="coerce")
            big = chunk[(cap >= 5000) & (chunk["Lage"] == "Freifläche")]
            n_ground_big += len(big)
            awarded = big[big["Zuschlagsnummer"].notna()]
            n_awarded += len(awarded)
            for v in awarded["Zuschlagsnummer"].astype(str):
                if len(award_samples) < 25:
                    award_samples.append(v)
                # prefix up to first digit-group to reveal the encoding scheme
                award_prefix[v[:8]] += 1
            if "AusschreibungZuschlag" in big:
                bool_auction.update(big["AusschreibungZuschlag"].dropna().astype(str))
            has_planned += big["GeplantesInbetriebnahmedatum"].notna().sum()
            has_eeg_comm += big["EegInbetriebnahmedatum"].notna().sum()

    print(f"solar units total: {n_total:,}")
    print(f"ground-mounted >=5MW: {n_ground_big:,}")
    print(f"  with Zuschlagsnummer (auction-awarded): {n_awarded:,}")
    print(f"  with GeplantesInbetriebnahmedatum (planned): {has_planned:,}")
    print(f"  with EegInbetriebnahmedatum: {has_eeg_comm:,}")
    print(f"\nAusschreibungZuschlag values: {dict(bool_auction)}")
    print("\nsample Zuschlagsnummer values:")
    for v in award_samples:
        print(f"  {v}")
    print("\nZuschlagsnummer 8-char prefixes (encoding scheme):")
    for p, n in award_prefix.most_common(15):
        print(f"  {p!r:14} {n}")


if __name__ == "__main__":
    main()
