"""Probe: do MaStR wind units carry hub-height, rotor-diameter, and per-turbine
coordinates we can use for real 3D turbine models? Show columns + a sample."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

ZIP = Path("data/bnetza_open_mastr_2025-02-09.zip")
WIND = "bnetza_mastr_wind_raw.csv"

CANDIDATES = ["Nabenhoehe", "Rotordurchmesser", "Breitengrad", "Laengengrad", "Nettonennleistung"]

with zipfile.ZipFile(ZIP) as z:
    member = next(n for n in z.namelist() if n.split("/")[-1] == WIND)
    with z.open(member) as f:
        head = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"), nrows=0)
    cols = list(head.columns)
    print(f"{WIND}: {len(cols)} columns")
    hits = [c for c in cols if any(k.lower() in c.lower() for k in ["nabe", "rotor", "breiten", "laengen", "nennleistung", "hoehe"])]
    print("relevant columns:", hits)

    use = [c for c in CANDIDATES if c in cols] + ["EinheitMastrNummer", "EinheitBetriebsstatus"]
    with z.open(member) as f:
        df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"), usecols=lambda c: c in use, nrows=400_000, low_memory=False)

cap = pd.to_numeric(df.get("Nettonennleistung"), errors="coerce")
ground = df[cap >= 1000]  # turbines >= 1 MW, onshore-ish sample
print(f"\nrows sampled: {len(df)}  | >=1MW units: {len(ground)}")
for c in ["Nabenhoehe", "Rotordurchmesser", "Breitengrad", "Laengengrad"]:
    if c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        print(f"  {c:18} non-null={s.notna().mean():.0%}  min={s.min():.1f}  median={s.median():.1f}  max={s.max():.1f}")
    else:
        print(f"  {c:18} MISSING")

print("\nsample turbines:")
show = [c for c in ["EinheitMastrNummer", "Breitengrad", "Laengengrad", "Nabenhoehe", "Rotordurchmesser", "Nettonennleistung"] if c in df.columns]
print(ground[show].dropna(subset=[c for c in ["Nabenhoehe", "Rotordurchmesser"] if c in df.columns]).head(6).to_string())
