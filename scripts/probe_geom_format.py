"""Probe: how does PostgREST return the PostGIS geom column? (GeoJSON dict, WKB hex, ...)

Determines how the GEE adapter must fetch site polygons for Earth Engine.
Run: uv run python scripts/probe_geom_format.py
"""

from app.db import get_db


def main() -> None:
    db = get_db()
    row = db.table("sites").select("id, geom").limit(1).execute().data[0]
    geom = row["geom"]
    print("type:", type(geom).__name__)
    print("value (first 160 chars):", str(geom)[:160])


if __name__ == "__main__":
    main()
