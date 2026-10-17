"""Probe the U.S. Large-Scale Solar Photovoltaic Database (USPVDB, USGS and LBNL).

Prints the data page's links (release, files), then the GeoJSON's size, feature count, property
names, one sample, and capacity and year spreads.

    uv run python scripts/probe_uspvdb.py
"""

from __future__ import annotations

import io
import json
import re
import zipfile

import httpx

PAGE = "https://energy.usgs.gov/uspvdb/data/"


def main() -> None:
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        html = c.get(PAGE).text
        links = sorted(set(re.findall(r'href="([^"]+\.(?:zip|xml|csv|json|geojson))"', html, re.I)))
        print("links:", links)
        geo = next((u for u in links if "geojson" in u.lower()), None) or next(
            (u for u in links if "shp" not in u.lower() and u.lower().endswith(".zip")), None
        )
        if not geo:
            return
        url = geo if geo.startswith("http") else httpx.URL(PAGE).join(geo)
        r = c.get(url)
        print("download", url, r.status_code, f"{len(r.content) / 1e6:.1f} MB")
        data = r.content
        if str(url).endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(data))
            print("zip members", [(i.filename, i.file_size) for i in z.infolist()])
            name = next(
                (n for n in z.namelist() if n.lower().endswith((".geojson", ".json"))), None
            )
            if not name:
                return
            data = z.read(name)
        d = json.loads(data)
        feats = d["features"]
        print("features", len(feats))
        p = feats[0]["properties"]
        print("properties", list(p))
        print("sample", json.dumps(p)[:800])
        print("geometry", feats[0]["geometry"]["type"], json.dumps(feats[0]["geometry"])[:160])
        caps = sorted(x["properties"].get("p_cap_ac") or 0 for x in feats)
        print(
            "p_cap_ac: min",
            caps[0],
            "median",
            caps[len(caps) // 2],
            "max",
            caps[-1],
            "sum",
            round(sum(caps)),
        )
        years = [x["properties"].get("p_year") for x in feats]
        print("years", min(y for y in years if y), max(y for y in years if y))


if __name__ == "__main__":
    main()
