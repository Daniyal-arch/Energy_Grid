"""Probe output per generating unit (ENTSO-E A73) and where each unit stands (JRC Open Power
Plants Database, CC BY 4.0, Zenodo 3574566, 1.3 MB): which countries publish A73 (Germany
per control area), how many of the units' EIC codes the JRC file places, and a sample.

    uv run python scripts/probe_unit_output.py [YYYY-MM-DD]
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from entsoe import AREA_EIC, request
from probe_entsoe_capacity import series

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-10-07"
START = datetime.fromisoformat(DAY).replace(tzinfo=UTC) - timedelta(hours=2)
PERIOD = {
    "periodStart": START.strftime("%Y%m%d%H%M"),
    "periodEnd": (START + timedelta(days=1)).strftime("%Y%m%d%H%M"),
}
JRC_URL = "https://zenodo.org/api/records/3574566/files/JRC-PPDB-OPEN.ver1.0.zip/content"
RAW = Path(__file__).resolve().parents[1] / "data" / "eu" / "jrc"
# Germany publishes per control area
DE_AREAS = {
    "50Hertz": "10YDE-VE-------2",
    "Amprion": "10YDE-RWENET---I",
    "TenneT DE": "10YDE-EON------1",
    "TransnetBW": "10YDE-ENBW-----N",
}


def jrc_units() -> dict[str, dict[str, str]]:
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / "JRC-PPDB-OPEN.ver1.0.zip"
    if not zpath.exists():
        zpath.write_bytes(httpx.get(JRC_URL, follow_redirects=True, timeout=120).content)
    with zipfile.ZipFile(zpath) as z:
        print("JRC files:", [(i.filename, i.file_size) for i in z.infolist()])
        name = next(n for n in z.namelist() if "UNITS" in n.upper() and n.endswith(".csv"))
        rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))
    print(f"{name}: {len(rows)} rows; columns {list(rows[0])}")
    out = {r["eic_g"]: r for r in rows if r.get("eic_g")}
    print(
        f"  {len(out)} units with an eic_g; with coordinates {sum(1 for r in out.values() if r.get('lat'))}"
    )
    return out


def main() -> None:
    jrc = jrc_units()
    client = httpx.Client(timeout=120)
    areas = {
        **{k: v for k, v in AREA_EIC.items() if k != "DE"},
        **{f"DE {k}": v for k, v in DE_AREAS.items()},
    }

    def get(item: tuple[str, str]) -> tuple[str, list[dict]]:
        name, eic = item
        root = request(
            client, {"documentType": "A73", "processType": "A16", "in_Domain": eic, **PERIOD}
        )
        return name, series(root, "quantity")

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(get, areas.items()))
    total_units = placed = 0
    print(f"\nA73 output per unit on {DAY}: units, placed by JRC eic_g, resolution, largest")
    for name, got in sorted(results):
        if not got:
            continue
        units = {s.get("unit") for s in got}
        hit = {u for u in units if u in jrc and jrc[u].get("lat")}
        total_units += len(units)
        placed += len(hit)
        top = max(got, key=lambda s: max(s["points"] or [0]))
        print(
            f"  {name:<15} {len(units):>4} units  {len(hit):>4} placed  {got[0]['resolution']:>6}  "
            f"{top.get('unit_name')} {max(top['points'] or [0]):,.0f} MW"
        )
    print(f"\nall: {total_units} units, {placed} placed ({placed / max(1, total_units):.0%})")
    print("none:", " ".join(n for n, g in sorted(results) if not g))


if __name__ == "__main__":
    main()
