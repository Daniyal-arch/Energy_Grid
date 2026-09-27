"""Fetch the German planned-transmission-corridor layers from netzausbau.de's ArcGIS
FeatureServer and save as a GeoJSON layer asset for the frontend (geometry = layer,
not DB — same pattern as fetch_grid.py for the existing backbone).

The original `grid_planned.geojson` (committed directly, no saved fetch script) only
ever covered layer 0 (Vorhaben_BBPlG, 159 segments — the 2013-on grid expansion law).
The same FeatureServer also hosts layer 1, Vorhaben_EnLAG (the earlier 2009 law, 27
segments) — verified via `FeatureServer?f=json`, never previously ingested. Both share
the same property schema (Vorhaben/Vorhabenst/Vorhabennu/Technik/Spannung), which is
why `lib/grid.ts`'s phaseOf()/loadPlanned() needs no changes to consume both.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

BASE = "https://services-eu1.arcgis.com/TJm8oSvOdJUQvQT5/arcgis/rest/services/Monitoring_gdb/FeatureServer"
LAYERS = {0: "BBPlG", 1: "EnLAG"}
OUT = Path("frontend/public/grid_planned.geojson")


def main() -> None:
    feats = []
    for layer_id, law in LAYERS.items():
        url = f"{BASE}/{layer_id}/query"
        r = httpx.get(url, params={"where": "1=1", "outFields": "*", "f": "geojson"}, timeout=60)
        r.raise_for_status()
        layer_feats = r.json()["features"]
        for f in layer_feats:
            f["properties"]["law"] = law
        feats.extend(layer_feats)
        print(f"{law} (layer {layer_id}): {len(layer_feats)} features")

    fc = {"type": "FeatureCollection", "features": feats}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    print(f"total: {len(feats)} features -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
