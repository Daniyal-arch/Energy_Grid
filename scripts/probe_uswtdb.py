"""Probe the U.S. Wind Turbine Database (USWTDB; USGS, LBNL, American Clean Power) before
the turbines layer.

1. The release named by the metadata file on https://energy.usgs.gov/uswtdb/data/
2. The CSV download (~2 MB zipped): columns, rows, offshore turbines, missing values
3. The API (PostgREST, https://energy.usgs.gov/api/uswtdb/v1/turbines): row count, so a
   fetch can check it got everything
4. The size of a compact file (lon, lat, kW, hub height, year) for the map

  uv run python scripts/probe_uswtdb.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter

import httpx

DATA = "https://energy.usgs.gov/uswtdb/data/"
CSV_ZIP = "https://energy.usgs.gov/uswtdb/assets/data/uswtdbCSV.zip"
API = "https://energy.usgs.gov/api/uswtdb/v1/turbines"


def main() -> None:
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        page = c.get(DATA).text
        releases = re.findall(r"uswtdb_V[\w.]+\.xml", page)
        print(f"metadata files: {releases}")
        r = c.head(
            API, params={"select": "case_id"}, headers={"Prefer": "count=exact", "Range": "0-0"}
        )
        print(f"API count (Content-Range): {r.headers.get('content-range')}")
        r = c.get(CSV_ZIP)
        r.raise_for_status()
        print(
            f"CSV zip: {len(r.content) / 1e6:.1f} MB, Last-Modified {r.headers.get('last-modified')}"
        )
    z = zipfile.ZipFile(io.BytesIO(r.content))
    print(f"zip entries: {[(i.filename, i.file_size) for i in z.infolist()]}")
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig")))
    print(f"{name}: {len(rows):,} turbines; columns {list(rows[0])}")
    print(f"first row: {rows[0]}")
    for col in ("t_offshore", "t_retrofit", "t_conf_loc", "t_conf_atr", "t_state"):
        if col in rows[0]:
            print(f"  {col}: {Counter(x[col] for x in rows).most_common(12)}")
    for col in ("t_cap", "t_hh", "p_year", "t_rd", "xlong", "ylat"):
        vals = [x[col] for x in rows]
        missing = sum(v in ("", "NA", "-9999") for v in vals)
        print(f"  {col}: missing {missing:,}, e.g. {Counter(vals).most_common(4)}")
    caps = [float(x["t_cap"]) for x in rows if x["t_cap"] not in ("", "NA", "-9999")]
    print(f"sum t_cap: {sum(caps) / 1e6:,.1f} GW over {len(caps):,} turbines with a capacity")
    proj = {(x["p_name"], x["t_state"]): x["p_cap"] for x in rows}
    pcap = [float(v) for v in proj.values() if v not in ("", "NA", "-9999")]
    print(f"projects: {len(proj):,}; sum p_cap: {sum(pcap) / 1000:,.1f} GW")
    compact = [
        [
            round(float(x["xlong"]), 4),
            round(float(x["ylat"]), 4),
            x["t_cap"],
            x["t_hh"],
            x["p_year"],
        ]
        for x in rows
    ]
    size = len(json.dumps(compact, separators=(",", ":")))
    print(f"compact [lon,lat,kW,hh,year] JSON: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
