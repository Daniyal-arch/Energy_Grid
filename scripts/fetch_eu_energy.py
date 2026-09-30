"""Download the static inputs for the Europe grid view into data/eu/ (gitignored).

- PyPSA-Eur prebuilt OSM network (Zenodo 18619025): lines, buses, HVDC links
- powerplantmatching plant list (PyPSA, GitHub)
- Eurostat GISCO country outlines 1:20M
- SciGRID_gas IGGIELGN gas network (Zenodo 4767098)

About 50 MB in total; files already present are skipped.

    uv run python scripts/fetch_eu_energy.py
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "eu"
ZENODO = "https://zenodo.org/records/18619025/files"
FILES = {
    "lines.csv": f"{ZENODO}/lines.csv?download=1",
    "buses.csv": f"{ZENODO}/buses.csv?download=1",
    "links.csv": f"{ZENODO}/links.csv?download=1",
    "powerplants.csv": "https://raw.githubusercontent.com/PyPSA/powerplantmatching/master/powerplants.csv",
    # SciGRID_gas IGGIELGN (2021): pipelines, LNG terminals, storages; CC BY 4.0
    "IGGIELGN.zip": "https://zenodo.org/records/4767098/files/IGGIELGN.zip?download=1",
    "countries.geojson": "https://gisco-services.ec.europa.eu/distribution/v2/countries/geojson/CNTR_RG_20M_2024_4326.geojson",
}


def download(name: str, url: str) -> None:
    path = OUT / name
    if path.exists():
        print(f"{name}: cached")
        return
    started = time.time()
    got = 0
    tmp = path.with_suffix(path.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as r, tmp.open("wb") as f:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            f.write(chunk)
            got += len(chunk)
            print(
                f"\r{name}: {got / 1e6:6.1f} MB  {time.time() - started:4.0f} s", end="", flush=True
            )
    print()
    tmp.replace(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        download(name, url)


if __name__ == "__main__":
    main()
