"""Probe EMODnet Human Activities: offshore wind farms (polygons and points) over WFS.

Prints the layers whose name mentions wind, then for each wind-farm layer: feature count,
property names, the values of the status field, and one sample feature.

    uv run python scripts/probe_emodnet.py
"""

from __future__ import annotations

import collections
import json
import re

import httpx

WFS = "https://ows.emodnet-humanactivities.eu/wfs"


def main() -> None:
    caps = httpx.get(
        WFS,
        params={"service": "WFS", "request": "GetCapabilities", "version": "2.0.0"},
        timeout=120,
    )
    print("capabilities", caps.status_code, len(caps.content), "bytes")
    names = re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", caps.text)
    wind = [n for n in names if "wind" in n.lower()]
    print("layers with wind:", wind)
    for layer in wind:
        r = httpx.get(
            WFS,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
            },
            timeout=300,
        )
        print(f"\n== {layer}: HTTP {r.status_code}, {len(r.content) / 1e6:.1f} MB")
        if r.status_code != 200:
            print(r.text[:300])
            continue
        d = r.json()
        feats = d.get("features", [])
        print("features", len(feats))
        if not feats:
            continue
        props = feats[0]["properties"]
        print("properties", list(props))
        for key in props:
            if key.lower() in ("status", "country", "year", "power_mw", "n_turbines"):
                c = collections.Counter(str(f["properties"].get(key)) for f in feats)
                print(f"  {key}: {len(c)} values, top {c.most_common(12)}")
        print(
            "geometry types",
            collections.Counter(
                f["geometry"]["type"] if f.get("geometry") else None for f in feats
            ),
        )
        sample = dict(feats[0])
        geom = sample.pop("geometry", None)
        print("sample", json.dumps(sample)[:600])
        print("sample geometry", json.dumps(geom)[:200])


if __name__ == "__main__":
    main()
