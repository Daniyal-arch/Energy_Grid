"""ENTSO-E TYNDP 2024 projects (brief 17, dataset 10).

tyndp2024.entsoe.eu builds its pages with JavaScript; the project map calls `/api/maps/all` (a
GeoJSON FeatureCollection: one feature per investment of a transmission project, and per storage
project; lines, areas and points) and each project's page `/api/public/Projects/{Transmission|
Storage}/{id}` (no login). Passed through: name, investment, promoter, country, status,
commissioning year (as published, "MM-YYYY" or "YYYY"), onshore/offshore; from the project pages
per investment the capacity (MW), voltage (kV) and element type, and per storage project the
maximum generating and storage power (MW). Computed: lines and areas simplified (shapely, 0.005
degrees, 3 decimals).

-> frontend/public/data/eu/tyndp.json (layer "Planned grid projects"); lake `tyndp/projects`.

    python scripts/build_tyndp.py [--lake lake-out] [--upload]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import wave5_common as w

BASE = "https://tyndp2024.entsoe.eu"
STATUSES = [
    "Under Consideration",
    "Planned But Not Yet Permitting",
    "In Permitting",
    "Under Construction",
    "Commissioned",
    "Completed",
]
TMP = Path("/tmp/wave5")


def year_of(text: str | None) -> int | None:
    """The year of a published commissioning date ("06-2024", "2030")."""
    if not text:
        return None
    tail = str(text).strip()[-4:]
    return int(tail) if tail.isdigit() else None


def details(kind: str, project: dict) -> dict[str, dict]:
    """investment id (or "project") -> the figures shown on hover."""
    if kind == "Storage":
        return {
            "project": {
                "generating_mw": project.get("generatingMaxActivePower"),
                "storage_mw": project.get("storageMaxActivePower"),
            }
        }
    out = {}
    for inv in project.get("investments") or []:
        out[str(inv.get("id"))] = {
            "capacity_mw": inv.get("capacity"),
            "voltage_kv": inv.get("voltageLevelKv"),
            "element": inv.get("typeOfElement"),
            "technology": inv.get("technologyType"),
            "length_km": inv.get("totalRouteLengthKm"),
        }
    return out


def main() -> None:
    from shapely.geometry import shape

    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    feats = w.get_json(f"{BASE}/api/maps/all")["features"]  # type: ignore[index]
    projects: dict[tuple[str, int], dict] = {}
    for f in feats:
        p = f["properties"]
        key = (p.get("type") or "", p.get("id"))
        if key[0] in ("Transmission", "Storage") and key[1] is not None and key not in projects:
            try:
                projects[key] = details(
                    key[0], w.get_json(f"{BASE}/api/public/Projects/{key[0]}/{key[1]}", tries=2)
                )  # type: ignore[arg-type]
            except SystemExit as e:
                print(f"  {key}: {e}", flush=True)
                projects[key] = {}
    out, rows = [], []
    for f in feats:
        p = f["properties"]
        if not f.get("geometry"):
            continue
        d = projects.get((p.get("type") or "", p.get("id")), {})
        fig = d.get(str(p.get("investmentId"))) or d.get("project") or {}
        g = shape(f["geometry"])
        kind = {"LineString": "line", "MultiLineString": "line", "Point": "point"}.get(
            g.geom_type, "area"
        )
        if kind == "line":
            s = g.simplify(0.005)
            parts = [s] if s.geom_type == "LineString" else list(s.geoms)
            geom = [[round(c, 3) for xy in part.coords for c in xy[:2]] for part in parts]
        elif kind == "point":
            geom = [round(g.x, 4), round(g.y, 4)]
        else:
            geom = w.rings(g.simplify(0.005, preserve_topology=True))
        st = p.get("status")
        out.append(
            {
                "project": p.get("name"),
                "investment": p.get("investmentName"),
                "type": p.get("type"),
                "id": p.get("id"),
                "status": STATUSES.index(st) if st in STATUSES else None,
                "year": p.get("commissioningYear"),
                "promoter": p.get("promoter") or p.get("promoters"),
                "country": p.get("countryCode"),
                "offshore": p.get("onshoreOffShore"),
                "kind": kind,
                "geometry": geom,
                **{k: v for k, v in fig.items() if v not in (None, "", 0, 0.0)},
            }
        )
        rows.append({**{k: v for k, v in p.items()}, **fig, "wkt": g.wkt})
    w.write_json(
        w.EU / "tyndp.json",
        {
            "fetched": w.now(),
            "source": "ENTSO-E TYNDP 2024 project collection (tyndp2024.entsoe.eu: /api/maps/all and the project pages)",
            "statuses": STATUSES,
            "features": out,
        },
    )
    print(f"  {len(out)} features of {len(projects)} projects", flush=True)
    import duckdb

    tmp = TMP / "tyndp.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "tyndp", args.lake, "ENTSO-E TYNDP 2024 project collection", "ENTSO-E terms of use (re-use with attribution)",
        "scripts/build_tyndp.py", "TYNDP 2024",
    )  # fmt: skip
    lk.write(
        con,
        "projects",
        f"""SELECT t.* EXCLUDE (wkt), t.countryCode AS iso2, i.iso3, NULL::VARCHAR AS admin1,
                   ST_GeomFromText(t.wkt) AS geometry
            FROM read_json('{tmp}', maximum_object_size = 1000000000, sample_size = -1) t
            LEFT JOIN iso_codes i ON i.iso2 = t.countryCode""",
        sort=["type", "id"],
        geometry="geometry",
    )
    w.lake_done(lk, args.upload)


if __name__ == "__main__":
    main()
