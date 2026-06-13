"""Probe: confirm a Site row (with EWKT geometry) inserts through PostgREST into PostGIS.

Inserts one throwaway site, reads it back via the centroid view, then deletes it.
Run: uv run python scripts/probe_insert.py
"""

from app.db import get_db
from app.models import Site, Technology

from ingestion import geo

TEST_ID = "PROBE-INSERT-TEST"


def main() -> None:
    db = get_db()
    site = Site(
        mastr_id=TEST_ID,
        name="probe insert test",
        geom_wkt=geo.square_wkt(11.5, 48.1, 300),
        capacity_mw=5.0,
        state="Bayern",
        technology=Technology.SOLAR,
        mastr_status="In Planung",
        aoi_method="capacity_buffer",
    )
    db.table("sites").upsert(site.to_row(), on_conflict="mastr_id").execute()
    back = db.table("sites_with_centroid").select("*").eq("mastr_id", TEST_ID).execute().data
    print(
        "inserted + read back:", back[0]["name"], "| lat", back[0]["lat"], "| lon", back[0]["lon"]
    )
    db.table("sites").delete().eq("mastr_id", TEST_ID).execute()
    print("cleaned up. geometry text cast works.")


if __name__ == "__main__":
    main()
