"""Probe: is MaStR's InAnspruchGenommeneFlaeche (area used, m2) populated for our sites?

It's the AOI-buffer fallback where OSM has no polygon. Run: uv run python scripts/probe_area.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

ZIP = Path(__file__).resolve().parent.parent / "data" / "bnetza_open_mastr_2025-02-09.zip"
COL = "InAnspruchGenommeneFlaeche"


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    member = next(n for n in z.namelist() if n.endswith("bnetza_mastr_solar_raw.csv"))
    usecols = ["Nettonennleistung", "Lage", COL]
    n = have = 0
    samples = []
    with z.open(member) as f:
        for chunk in pd.read_csv(
            io.TextIOWrapper(f, encoding="utf-8"),
            usecols=lambda c: c in usecols,
            chunksize=200_000,
            low_memory=False,
        ):
            cap = pd.to_numeric(chunk["Nettonennleistung"], errors="coerce")
            sel = chunk[(cap >= 5000) & (chunk["Lage"] == "Freifläche")]
            n += len(sel)
            area = pd.to_numeric(sel[COL], errors="coerce")
            have += area.notna().sum()
            samples.extend(area.dropna().tolist()[: max(0, 8 - len(samples))])
    print(f"ground-mounted >=5MW solar: {n}")
    print(f"  with area (InAnspruchGenommeneFlaeche): {have} ({100 * have / n:.0f}%)")
    print(f"  sample areas (m2 -> implied side m): {[(round(a), round(a**0.5)) for a in samples]}")


if __name__ == "__main__":
    main()
