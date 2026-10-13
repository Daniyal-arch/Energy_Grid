"""Where can a new plant, battery or data centre connect? The grid operators' own figures for
Great Britain, the Netherlands and Spain (no keys).

GB  NESO TEC register (CKAN resource 17becbab-e3e8-473f-b303-3806f43a6a10, NESO Open Data
    Licence, twice weekly): every project holding or seeking transmission entry capacity, with
    its connection site (free text), MW, plant type, status, effective date and transmission
    owner. Placed only where the connection site's name, without voltage and words like
    "GSP" or "substation", equals a region name in NESO's "GSP - Gnode - Direct Connect -
    Region Lookup" (the GSP's latitude/longitude there); the rest are counted, not placed.
NL  Netbeheer Nederland, landelijke capaciteitskaart, regional operators' supply areas
    (voedingsgebieden), published as an ArcGIS feature service (Esri Nederland for Netbeheer
    Nederland): per area the offtake (afname) and feed-in (opwek) status 0-3 as the map's own
    legend reads them, and the queue (wachtrij, MW) and number of requests on each side.
    Outlines simplified to about 150 m (shapely, 0.0015 degrees).
ES  Red Eléctrica, "Capacidad de acceso de demanda disponible y ocupada en los nudos de la red
    de transporte" (xlsx, monthly): per node the access capacity available for new requests
    (MW) for demand and storage. The file gives no coordinates: Spain is a card, not drawn.

Writes frontend/public/data/eu/connect.json; see docs/DATA_SOURCES.md.

    uv run python scripts/fetch_connect_here.py [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import openpyxl
import shapely.geometry

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
UA = {"User-Agent": "Mozilla/5.0 (Europe-InfraAtlas; research)"}
CKAN = "https://api.neso.energy/api/3/action/resource_show"
TEC = "17becbab-e3e8-473f-b303-3806f43a6a10"
GSP_LOOKUP = "bbe2cc72-a6c6-46e6-8f4e-48b879467368"
NL = (
    "https://services.arcgis.com/nSZVuSZjHpEZZbRo/arcgis/rest/services/"
    "Capaciteitskaart_elektriciteitsnet_v2_afname/FeatureServer/0/query"
)
REE_PAGE = "https://www.ree.es/es/clientes/consumidor/acceso-conexion/conoce-la-capacidad-de-acceso"
SIMPLIFY_DEG = 0.0015
NL_STATUS = [
    "capacity available, no queue",
    "capacity limited, no queue",
    "under study, with a queue",
    "shortage of capacity, with a queue",
]
# technology groups for the TEC register's "Plant Type" (a project may list several)
GB_TYPES = [
    ("Storage", ("Energy Storage",)),
    ("Solar", ("PV Array",)),
    ("Wind onshore", ("Wind Onshore",)),
    ("Wind offshore", ("Wind Offshore",)),
    ("Gas", ("CCGT", "OCGT", "Gas Reciprocating", "CHP")),
    ("Demand", ("Demand",)),
    ("Nuclear", ("Nuclear",)),
    ("Interconnector", ("Interconnector",)),
]


def get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    for attempt in range(4):
        try:
            r = client.get(url, params=params)
            if r.status_code == 200:
                return r
        except httpx.TransportError:
            pass
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"{url}: no answer")


def site_key(name: str) -> str:
    """A connection site or GSP region name without voltage and generic words."""
    s = name.lower()
    s = re.sub(r"\b\d+(\.\d+)?\s*kv\b", " ", s)
    s = re.sub(r"\b(gsp|grid supply point|substation|sub station|s/s)\b", " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def gb_type(plant: str) -> str:
    """The first listed technology's group ("Energy Storage System;PV Array" -> Storage)."""
    for part in plant.split(";"):
        for label, keys in GB_TYPES:
            if any(part.strip().startswith(k) for k in keys):
                return label
    return "Other"


def num(v: object) -> float | None:
    try:
        return float(v) if v not in (None, "", "NA", "N/A", "-") else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def gb(client: httpx.Client) -> dict:
    res = get(client, CKAN, {"id": TEC}).json()["result"]
    tec = list(csv.DictReader(io.StringIO(get(client, res["url"]).content.decode("utf-8-sig"))))
    lres = get(client, CKAN, {"id": GSP_LOOKUP}).json()["result"]
    lookup = csv.DictReader(io.StringIO(get(client, lres["url"]).content.decode("utf-8-sig")))
    at: dict[str, tuple[float, float]] = {}
    for r in lookup:
        lat, lon = (
            num(r.get("gsp_lat")) or num(r.get("gnode_lat")),
            num(r.get("gsp_lon")) or num(r.get("gnode_lon")),
        )
        if r.get("region_name") and lat is not None and lon is not None:
            at.setdefault(site_key(r["region_name"]), (round(lon, 5), round(lat, 5)))
    types = [t for t, _ in GB_TYPES] + ["Other"]
    statuses: list[str] = []
    sites: dict[str, dict] = {}
    projects: list[list] = []
    for r in tec:
        site = r["Connection Site"].strip()
        status = r["Project Status"].strip()
        if status not in statuses:
            statuses.append(status)
        s = sites.setdefault(site, {"name": site, "at": at.get(site_key(site)), "to": r["HOST TO"]})
        projects.append(
            [
                r["Project Name"].strip(),
                list(sites).index(site),
                num(r["Cumulative Total Capacity (MW)"]) or 0,
                num(r["MW Connected"]) or 0,
                types.index(gb_type(r["Plant Type"])),
                statuses.index(status),
                (r["MW Effective From"] or "")[:10] or None,
                r["Agreement Type"].strip() or None,
            ]
        )
        s.setdefault("n", 0)
        s["n"] += 1
    m = re.search(r"tec-register-(.+)\.csv", res["url"])
    return {
        "source": "NESO TEC register (NESO Open Data Licence); positions: NESO GSP region lookup",
        "date": m.group(1).replace("-", " ") if m else res.get("last_modified", "")[:10],
        "types": types,
        "statuses": statuses,
        "sites": [[s["name"], *(s["at"] or (None, None)), s["to"]] for s in sites.values()],
        "projects": projects,
    }


def nl(client: httpx.Client) -> dict:
    params = {
        "where": "voedingsgebied_naam <> '0'",
        "outFields": "*",
        "outSR": 4326,
        "geometryPrecision": 4,
        "f": "geojson",
        "resultRecordCount": 1000,
    }
    feats: list[dict] = []
    offset = 0
    while True:
        d = get(client, NL, {**params, "resultOffset": offset}).json()
        feats += d.get("features", [])
        if (
            not d.get("properties", {}).get("exceededTransferLimit")
            and len(d.get("features", [])) < 1000
        ):
            break
        offset += 1000
    areas = []
    for f in feats:
        p, g = f["properties"], f.get("geometry")
        if not g:
            continue
        # outlines simplified to ~150 m (the service returns them at full detail)
        shape = shapely.geometry.shape(g)
        shape = (shape if shape.is_valid else shape.buffer(0)).simplify(SIMPLIFY_DEG)
        parts = getattr(shape, "geoms", [shape])
        polys = [
            [list(poly.exterior.coords)]
            + [list(h.coords) for h in poly.interiors if h.area > SIMPLIFY_DEG**2 * 4]
            for poly in parts
            if poly.geom_type == "Polygon" and not poly.is_empty
        ]
        areas.append(
            {
                "id": p["voedingsgebied_id"],
                "name": p["voedingsgebied_naam"],
                "operator": p.get("RNB"),
                "offtake": p["afname"],
                "feedin": p["opwek"],
                "queue_offtake_mw": p.get("wachtrij_afname"),
                "queue_feedin_mw": p.get("wachtrij_invoeding"),
                "requests_offtake": p.get("unieke_verzoeken_afname"),
                "requests_feedin": p.get("unieke_verzoeken_invoeding"),
                "polygons": [
                    [[[round(x, 4), round(y, 4)] for x, y in ring] for ring in poly]
                    for poly in polys
                ],
            }
        )
    return {
        "source": "Netbeheer Nederland, landelijke capaciteitskaart (regional operators), via Esri Nederland",
        "status": NL_STATUS,
        "areas": areas,
    }


def es(client: httpx.Client) -> dict:
    page = get(client, REE_PAGE).text
    m = re.search(r'href="([^"]+?(\d{4}_\d{2}_\d{2})_GRT_demanda\.xlsx)"', page)
    if not m:
        raise SystemExit("REE: no GRT_demanda.xlsx on the page")
    url = "https://www.ree.es" + m.group(1) if m.group(1).startswith("/") else m.group(1)
    wb = openpyxl.load_workbook(
        io.BytesIO(get(client, url).content), read_only=True, data_only=True
    )
    rows = list(wb["Ficha Capacidades"].iter_rows(values_only=True))
    head = " ".join(str(x) for x in rows[0] if x)
    assert "Nombre y tensión del nudo" in head and "CAPACIDAD DE ACCESO DISPONIBLE" in head, (
        "REE layout changed"
    )
    nodes = []
    for r in rows[4:]:
        if not r or not r[0]:
            continue
        # 85-89: available for new requests at the transmission node: demand CEP with and
        # without voltage-dip ride-through, demand not CEP, storage MPE, storage MGES
        nodes.append(
            [
                str(r[0]).strip(),
                str(r[1]),
                r[2],
                num(r[85]),
                num(r[86]),
                num(r[87]),
                num(r[88]),
                num(r[89]),
                bool(r[100]),
            ]
        )
    return {
        "source": "Red Eléctrica, capacidad de acceso de demanda en los nudos de la red de transporte",
        "date": m.group(2).replace("_", "-"),
        "url": url,
        "columns": [
            "demand CEP CH",
            "demand CEP SH",
            "demand not CEP",
            "storage MPE",
            "storage MGES",
        ],
        "nodes": nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out_dir: Path = parser.parse_args().out
    client = httpx.Client(timeout=180, follow_redirects=True, headers=UA)
    out = {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "gb": gb(client),
        "nl": nl(client),
        "es": es(client),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "connect.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    g = out["gb"]
    placed = sum(p[2] for p in g["projects"] if g["sites"][p[1]][1] is not None)
    total = sum(p[2] for p in g["projects"])
    print(
        f"GB {len(g['projects'])} projects, {total / 1000:.1f} GW ({placed / 1000:.1f} GW placed); "
        f"NL {len(out['nl']['areas'])} areas; ES {len(out['es']['nodes'])} nodes ({out['es']['date']}) -> {path}"
    )


if __name__ == "__main__":
    main()
