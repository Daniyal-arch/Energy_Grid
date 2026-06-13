"""Probe: inspect the downloaded open-mastr Zenodo snapshot before writing the adapter.

Verifies per-technology CSV columns + runs the candidate filter (>=5 MW, ground-mounted/
open-area, all generation technologies, nationwide). Writes a full report to
data/mastr_probe_report.txt so nothing is truncated.

Run: uv run python scripts/probe_mastr_csv.py
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
ZIP = DATA / "bnetza_open_mastr_2025-02-09.zip"
REPORT = DATA / "mastr_probe_report.txt"

# Generation technologies we monitor (rooftop excluded via the Lage/siting filter).
TECH_FILES = {
    "solar": "bnetza_mastr_solar_raw.csv",
    "wind": "bnetza_mastr_wind_raw.csv",
    "biomass": "bnetza_mastr_biomass_raw.csv",
    "hydro": "bnetza_mastr_hydro_raw.csv",
    "gsgk": "bnetza_mastr_gsgk_raw.csv",  # geothermal / mine gas
    "combustion": "bnetza_mastr_combustion_raw.csv",
    "storage": "bnetza_mastr_storage_raw.csv",
}
MIN_KW = 5000  # >= 5 MW

# Ground-mounted / open-area markers in the `Lage` field (rest, e.g. rooftop, excluded).
GROUND_MARKERS = ("Freifläche", "Freiflaeche", "sonstige", "baulichen Anlagen")


def _member(z: zipfile.ZipFile, filename: str) -> str | None:
    return next((n for n in z.namelist() if n.endswith(filename)), None)


def _detect_sep(z: zipfile.ZipFile, member: str) -> str:
    with z.open(member) as f:
        first = io.TextIOWrapper(f, encoding="utf-8").readline()
    return ";" if first.count(";") > first.count(",") else ","


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    out = REPORT.open("w", encoding="utf-8")

    def log(*a: object) -> None:
        line = " ".join(str(x) for x in a)
        print(line)
        out.write(line + "\n")

    # 1) Full solar schema + key-column samples
    solar = _member(z, TECH_FILES["solar"])
    sep = _detect_sep(z, solar)
    log(f"separator detected: {sep!r}\n")
    with z.open(solar) as f:
        head = pd.read_csv(
            io.TextIOWrapper(f, encoding="utf-8"), sep=sep, nrows=300, low_memory=False
        )
    log(f"=== solar columns ({len(head.columns)}) ===")
    for c in head.columns:
        log("  ", c)

    log("\n=== key column samples (solar) ===")
    wanted = (
        "lage",
        "leistung",
        "bundesland",
        "betriebsstatus",
        "breiten",
        "laengen",
        "koordinat",
        "inbetrieb",
        "artderflaeche",
        "gemeinde",
    )
    keycols = [c for c in head.columns if any(k in c.lower() for k in wanted)]
    for c in keycols:
        vals = head[c].dropna().unique()[:6]
        log(f"  [{c}] -> {list(vals)}")

    # Identify the net-capacity, siting, status, coordinate columns by best match
    def find(*subs: str) -> str | None:
        for c in head.columns:
            if all(s in c.lower() for s in subs):
                return c
        return None

    cap_col = find("nettonennleistung") or find("brutto", "leistung") or "Bruttoleistung"
    lage_col = find("lage")
    status_col = find("betriebsstatus")
    lat_col = find("breiten") or find("koordinat", "n")
    lon_col = find("laengen") or find("koordinat", "e")
    bl_col = find("bundesland")
    log(
        f"\nchosen -> capacity={cap_col} siting={lage_col} status={status_col} "
        f"lat={lat_col} lon={lon_col} bundesland={bl_col}"
    )

    # 2) Candidate counts per technology (chunked; solar is 3.7 GB)
    log("\n=== candidate counts: net capacity >= 5 MW, ground-mounted/open-area, nationwide ===")
    total = 0
    for tech, fname in TECH_FILES.items():
        member = _member(z, fname)
        if not member:
            log(f"  {tech:12} file missing")
            continue
        tsep = _detect_sep(z, member)
        n_units = n_big = n_ground = n_coord = 0
        # read only the columns we need, in chunks
        usecols = [c for c in (cap_col, lage_col, status_col, lat_col, lon_col, bl_col) if c]
        with z.open(member) as f:
            reader = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                sep=tsep,
                usecols=lambda c: c in usecols,
                chunksize=200_000,
                low_memory=False,
            )
            for chunk in reader:
                n_units += len(chunk)
                if cap_col not in chunk:
                    continue
                cap = pd.to_numeric(chunk[cap_col], errors="coerce")
                big = chunk[cap >= MIN_KW]
                n_big += len(big)
                if lage_col and lage_col in big:
                    ground = big[
                        big[lage_col]
                        .astype(str)
                        .str.contains("|".join(GROUND_MARKERS), na=False, case=False)
                    ]
                else:
                    ground = big
                n_ground += len(ground)
                if lat_col and lat_col in ground:
                    n_coord += ground[lat_col].notna().sum()
        log(
            f"  {tech:12} units={n_units:>9,}  >=5MW={n_big:>7,}  ground/open={n_ground:>6,}  with_coords={n_coord:>6,}"
        )
        total += n_ground
    log(f"\n  TOTAL candidate sites (>=5 MW, ground/open, all tech): {total:,}")
    out.close()
    print(f"\nfull report written to {REPORT}")


if __name__ == "__main__":
    main()
