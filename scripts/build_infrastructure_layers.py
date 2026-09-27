"""Build browser-ready infrastructure layers from researched source datasets.

Inputs are downloaded into ``data/source_downloads`` and stay gitignored. Outputs are
small, normalized GeoJSON files in ``frontend/public/data`` with source metadata kept
on every feature. Run with ``--fetch-industry`` to refresh EEA industrial sites.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import io
import json
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import shapefile
from shapely import line_merge, unary_union, wkt
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source_downloads"
OUTPUT = ROOT / "frontend" / "public" / "data"

DB_ARCHIVE = SOURCE / "db_infrago.zip"
PORT_ARCHIVE = SOURCE / "eurostat_ports.zip"
AIRPORT_ARCHIVE = SOURCE / "eurostat_airports_2024.zip"
GAS_ARCHIVE = SOURCE / "scigrid_gas.zip"
INDUSTRY_CACHE = SOURCE / "eea_industry_de.geojson"
STATE_BOUNDARIES_CACHE = SOURCE / "nuts1_2024.geojson"
MASTR_ARCHIVE = ROOT / "data" / "bnetza_open_mastr_2025-02-09.zip"

INDUSTRY_URL = (
    "https://air.discomap.eea.europa.eu/arcgis/rest/services/"
    "Air/IED_SiteMap/MapServer/0/query"
)

SOURCES = {
    "rail": {
        "name": "DB InfraGO infrastructure data",
        "url": "https://data.gov.de/suche/daten/infrastrukturdaten-der-db-infrago",
        "published": "2026-05",
        "coverage": "DB InfraGO railway routes in Germany",
        "caveat": "Route geometry is simplified for browser rendering.",
    },
    "ports": {
        "name": "Eurostat GISCO ports",
        "url": "https://ec.europa.eu/eurostat/en/web/gisco/geodata/transport-networks",
        "published": "2013",
        "coverage": "German ports in the GISCO world ports layer",
        "caveat": "Official reference geometry; the ports release is not a live operations feed.",
    },
    "airports": {
        "name": "Eurostat GISCO airports",
        "url": "https://ec.europa.eu/eurostat/en/web/gisco/geodata/transport-networks",
        "published": "2026-06",
        "coverage": "German airport reference points from GISCO Airports 2024",
        "caveat": "Reference geography, not live flight operations.",
    },
    "boundaries": {
        "name": "Eurostat GISCO NUTS 2024",
        "url": "https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-files.html",
        "published": "2024",
        "coverage": "German NUTS-1 / federal-state boundaries",
        "caveat": "Cartographic boundaries for thematic mapping.",
    },
    "industry": {
        "name": "European Industrial Emissions Portal",
        "url": "https://industry.eea.europa.eu/industrial-emissions/dataset",
        "published": "2026-02",
        "coverage": "Large German industrial sites reported under IED/E-PRTR",
        "caveat": "Reporting thresholds exclude smaller facilities; reporting years vary by site.",
    },
    "gas": {
        "name": "SciGRID_gas IGGIELGNC-3",
        "url": "https://github.com/Netizine/SciGRID_gas-IGGIELGNC-3",
        "published": "2021",
        "coverage": "Open model of gas pipelines, storage, LNG, and border points",
        "caveat": "Research network model, not a live operational or safety map.",
    },
    "energy": {
        "name": "MaStR bulk electricity units",
        "url": "https://www.marktstammdatenregister.de/MaStR/Datendownload",
        "published": "2025-02-09",
        "coverage": "Largest coordinate-backed German electricity units by technology",
        "caveat": "Browser layer is capacity-filtered and does not include every small rooftop/storage unit.",
    },
}


def feature(geometry: dict[str, Any], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def write_geojson(name: str, features: list[dict[str, Any]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {"type": "FeatureCollection", "features": features}
    (OUTPUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def db_csv(archive: zipfile.ZipFile, marker: str) -> csv.DictReader:
    filename = next(name for name in archive.namelist() if marker in name)
    stream = io.TextIOWrapper(archive.open(filename), encoding="utf-8-sig")
    return csv.DictReader(stream, delimiter=";")


def build_rail() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[Any]] = defaultdict(list)
    nodes: list[dict[str, Any]] = []
    structures: list[dict[str, Any]] = []
    with zipfile.ZipFile(DB_ARCHIVE) as archive:
        for row in db_csv(archive, "Streckennetz"):
            if row["Richtung"] != "Streckenachse":
                continue
            geometry_text = row.get("WKT WGS84 (EPSG 4326)")
            if not geometry_text:
                continue
            route = row.get("Streckennummer", "")
            key = (
                route,
                row.get("Streckenkurzname", ""),
                row.get("Elektrifizierung", ""),
                row.get("Gleisanzahl", ""),
                row.get("Bundesland", ""),
            )
            grouped[key].append(wkt.loads(geometry_text))

        seen_points: set[tuple[str, str]] = set()
        for row in db_csv(archive, "Betriebsstellen"):
            geometry_text = row.get("WKT WGS84 (EPSG 4326)")
            if not geometry_text or row.get("Betriebszustand") != "in Betrieb":
                continue
            key = (row.get("Bezeichnung") or "", geometry_text)
            if key in seen_points:
                continue
            seen_points.add(key)
            nodes.append(
                feature(
                    mapping(wkt.loads(geometry_text)),
                    {
                        "kind": "rail_station",
                        "name": row.get("Bezeichnung") or row.get("Kürzel") or "Rail operating point",
                        "code": row.get("Kürzel"),
                        "type": row.get("Art lang") or row.get("Art"),
                        "route": row.get("Streckennummer"),
                        "state": row.get("Bundesland"),
                        "district": row.get("Kreis"),
                        "source": SOURCES["rail"]["name"],
                        "source_url": SOURCES["rail"]["url"],
                    },
                )
            )

        seen_crossings: set[str] = set()
        for row in db_csv(archive, "Bahn"):
            geometry_text = row.get("WKT WGS84 (EPSG 4326)")
            if not geometry_text or geometry_text in seen_crossings:
                continue
            seen_crossings.add(geometry_text)
            nodes.append(
                feature(
                    mapping(wkt.loads(geometry_text)),
                    {
                        "kind": "rail_crossing",
                        "name": row.get("Bezeichnung") or "Level crossing",
                        "road_type": row.get("Straßenart"),
                        "protection": row.get("Technische Sicherung"),
                        "route": row.get("Streckennummer"),
                        "state": row.get("Bundesland"),
                        "source": SOURCES["rail"]["name"],
                        "source_url": SOURCES["rail"]["url"],
                    },
                )
            )

        for marker, kind, min_length in (
            ("Tunnel", "rail_tunnel", 0),
            ("Eisenbahnbr", "rail_bridge", 80),
        ):
            for row in db_csv(archive, marker):
                if row.get("Richtung") != "Streckenachse":
                    continue
                length = parse_number(row.get("Länge")) or 0
                if length < min_length:
                    continue
                geometry_text = row.get("WKT WGS84 (EPSG 4326)")
                if not geometry_text:
                    continue
                geometry = wkt.loads(geometry_text).simplify(0.00003, preserve_topology=True)
                structures.append(
                    feature(
                        mapping(geometry),
                        {
                            "kind": kind,
                            "name": row.get("Bezeichnung") or ("Tunnel" if kind == "rail_tunnel" else "Rail bridge"),
                            "length_m": length,
                            "route": row.get("Streckennummer"),
                            "state": row.get("Bundesland"),
                            "crossing_type": row.get("Kreuzungsart"),
                            "source": SOURCES["rail"]["name"],
                            "source_url": SOURCES["rail"]["url"],
                        },
                    )
                )

    routes: list[dict[str, Any]] = []
    for key, lines in grouped.items():
        route, name, electrification, tracks, state = key
        geometry = line_merge(unary_union(lines)).simplify(0.00015, preserve_topology=True)
        routes.append(
            feature(
                mapping(geometry),
                {
                    "kind": "rail",
                    "name": name or f"Route {route}",
                    "route": route,
                    "electrification": electrification,
                    "tracks": tracks,
                    "state": state,
                    "source": SOURCES["rail"]["name"],
                    "source_url": SOURCES["rail"]["url"],
                },
            )
        )
    return routes, nodes, structures


def _zip_member(archive: zipfile.ZipFile, suffix: str) -> str:
    return next(name for name in archive.namelist() if name.endswith(suffix))


def build_ports() -> list[dict[str, Any]]:
    with zipfile.ZipFile(PORT_ARCHIVE) as archive:
        shp_name = _zip_member(archive, "PORT_PT_2013.shp")
        shx_name = _zip_member(archive, "PORT_PT_2013.shx")
        dbf_name = _zip_member(archive, "PORT_PT_2013.dbf")
        attr_name = _zip_member(archive, "PORT_AT_2013.dbf")
        points = shapefile.Reader(
            shp=io.BytesIO(archive.read(shp_name)),
            shx=io.BytesIO(archive.read(shx_name)),
            dbf=io.BytesIO(archive.read(dbf_name)),
            encoding="latin1",
        )
        attributes = shapefile.Reader(
            dbf=io.BytesIO(archive.read(attr_name)), encoding="latin1"
        )
        by_id = {record["PORT_ID"]: record.as_dict() for record in attributes.records()}

        features = []
        for item in points.iterShapeRecords():
            port_id = item.record["PORT_ID"]
            attrs = by_id.get(port_id, {})
            if attrs.get("CNTR_CODE") != "DE":
                continue
            features.append(
                feature(
                    item.shape.__geo_interface__,
                    {
                        "kind": "port",
                        "name": attrs.get("PORT_NAME") or port_id,
                        "port_id": port_id,
                        "nuts_code": attrs.get("NUTS_CODE"),
                        "ten_code": attrs.get("TEN_CODE"),
                        "source": SOURCES["ports"]["name"],
                        "source_url": SOURCES["ports"]["url"],
                    },
                )
            )
        return features


def build_airports() -> list[dict[str, Any]]:
    with zipfile.ZipFile(AIRPORT_ARCHIVE) as archive:
        shp_name = _zip_member(archive, "AIRP_PT_2024_SH.shp")
        shx_name = _zip_member(archive, "AIRP_PT_2024_SH.shx")
        dbf_name = _zip_member(archive, "AIRP_PT_2024_SH.dbf")
        points = shapefile.Reader(
            shp=io.BytesIO(archive.read(shp_name)),
            shx=io.BytesIO(archive.read(shx_name)),
            dbf=io.BytesIO(archive.read(dbf_name)),
            encoding="utf-8",
        )

        features = []
        for item in points.iterShapeRecords():
            attrs = item.record.as_dict()
            if attrs.get("CNTR_CODE") != "DE":
                continue
            features.append(
                feature(
                    item.shape.__geo_interface__,
                    {
                        "kind": "airport",
                        "name": attrs.get("NAME") or attrs.get("ICAO_CODE") or "Airport",
                        "icao": attrs.get("ICAO_CODE"),
                        "tentec": attrs.get("TENTEC") == "Y",
                        "passenger_class": attrs.get("PASS_2024"),
                        "source": SOURCES["airports"]["name"],
                        "source_url": SOURCES["airports"]["url"],
                    },
                )
            )
        return features


def _has_country(value: Any, country: str = "DE") -> bool:
    if isinstance(value, list):
        return country in value
    return value == country or country in str(value)


def _near_germany(geometry: dict[str, Any]) -> bool:
    min_lon, min_lat, max_lon, max_lat = shape(geometry).bounds
    return max_lon >= 5.0 and min_lon <= 16.0 and max_lat >= 47.0 and min_lat <= 56.0


def build_gas() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    with zipfile.ZipFile(GAS_ARCHIVE) as archive:
        pipe_name = _zip_member(archive, "IGGIELGNC3_PipeSegments.geojson")
        pipes = json.load(archive.open(pipe_name))["features"]
        for item in pipes:
            props = item["properties"]
            # The published IGGIELGNC-3 GeoJSON repeats a malformed country-code value
            # across pipe records, so geography is the reliable filter for this layer.
            if not _near_germany(item["geometry"]):
                continue
            params = props.get("param") or {}
            lines.append(
                feature(
                    item["geometry"],
                    {
                        "kind": "gas_pipeline",
                        "name": props.get("name") or props.get("id"),
                        "diameter_mm": params.get("diameter_mm"),
                        "pressure_bar": params.get("max_pressure_bar"),
                        "capacity_mcmd": params.get("max_cap_M_m3_per_d"),
                        "length_km": params.get("length_km"),
                        "source": SOURCES["gas"]["name"],
                        "source_url": SOURCES["gas"]["url"],
                    },
                )
            )

        node_specs = (
            ("IGGIELGNC3_Storages.geojson", "gas_storage"),
            ("IGGIELGNC3_LNGs.geojson", "lng_terminal"),
            ("IGGIELGNC3_BorderPoints.geojson", "gas_border"),
            ("IGGIELGNC3_Compressors.geojson", "gas_compressor"),
            ("IGGIELGNC3_Consumers.geojson", "gas_consumer"),
            ("IGGIELGNC3_Productions.geojson", "gas_production"),
            ("IGGIELGNC3_PowerPlants.geojson", "gas_powerplant"),
        )
        for suffix, kind in node_specs:
            data = json.load(archive.open(_zip_member(archive, suffix)))["features"]
            for item in data:
                props = item["properties"]
                params = props.get("param") or {}
                countries = params.get("List_country_code") or props.get("country_code")
                if not _has_country(countries) and not _near_germany(item["geometry"]):
                    continue
                nodes.append(
                    feature(
                        item["geometry"],
                        {
                            "kind": kind,
                            "name": props.get("name") or props.get("id"),
                            "working_gas_mcm": params.get("max_workingGas_M_m3"),
                            "sendout_mcmd": params.get("max_cap_store2pipe_M_m3_per_d"),
                            "capacity_mcmd": params.get("max_cap_M_m3_per_d"),
                            "gas_power_mw": params.get("power_MW"),
                            "from_country": params.get("from_country"),
                            "to_country": params.get("to_country"),
                            "source": SOURCES["gas"]["name"],
                            "source_url": SOURCES["gas"]["url"],
                        },
                    )
                )
    return lines, nodes


def build_states() -> list[dict[str, Any]]:
    raw = json.loads(STATE_BOUNDARIES_CACHE.read_text(encoding="utf-8"))["features"]
    features = []
    for item in raw:
        props = item["properties"]
        if props.get("CNTR_CODE") != "DE" or props.get("LEVL_CODE") != 1:
            continue
        geometry = shape(item["geometry"]).simplify(0.002, preserve_topology=True)
        features.append(
            feature(
                mapping(geometry),
                {
                    "kind": "state_boundary",
                    "name": props.get("NUTS_NAME") or props.get("NAME_LATN"),
                    "nuts_id": props.get("NUTS_ID"),
                    "source": SOURCES["boundaries"]["name"],
                    "source_url": SOURCES["boundaries"]["url"],
                },
            )
        )
    return features


def build_energy_sites() -> list[dict[str, Any]]:
    specs = (
        ("bnetza_mastr_solar_raw.csv", "solar", 1000.0, 8_000, 250_000),
        ("bnetza_mastr_wind_raw.csv", "wind", 0.0, 40_000, None),
        ("bnetza_mastr_biomass_raw.csv", "biomass", 500.0, 8_000, None),
        ("bnetza_mastr_hydro_raw.csv", "hydro", 500.0, 6_000, None),
        ("bnetza_mastr_combustion_raw.csv", "combustion", 500.0, 8_000, None),
        ("bnetza_mastr_storage_raw.csv", "storage", 500.0, 8_000, 250_000),
    )
    heaps: dict[str, list[tuple[float, int, dict[str, Any]]]] = {tech: [] for _, tech, _, _, _ in specs}
    sequence = 0

    def text(row: dict[str, str], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value:
                return value
        return None

    with zipfile.ZipFile(MASTR_ARCHIVE) as archive:
        for suffix, technology, min_kw, limit, scan_limit in specs:
            filename = _zip_member(archive, suffix)
            stream = io.TextIOWrapper(archive.open(filename), encoding="utf-8-sig", newline="")
            for index, row in enumerate(csv.DictReader(stream)):
                if scan_limit is not None and index >= scan_limit:
                    break
                if row.get("Land") != "Deutschland":
                    continue
                lon = parse_number(row.get("Laengengrad"))
                lat = parse_number(row.get("Breitengrad"))
                if lon is None or lat is None or not (5.0 <= lon <= 16.0 and 47.0 <= lat <= 56.0):
                    continue
                capacity_kw = (
                    parse_number(row.get("Bruttoleistung_extended"))
                    or parse_number(row.get("Bruttoleistung"))
                    or parse_number(row.get("Nettonennleistung"))
                    or 0.0
                )
                if capacity_kw < min_kw:
                    continue
                site = {
                    "id": row.get("EinheitMastrNummer") or f"{technology}-{sequence}",
                    "name": text(row, "NameStromerzeugungseinheit", "NameWindpark", "NameKraftwerk", "Name")
                    or f"{technology.title()} unit",
                    "technology": technology,
                    "status": "unknown",
                    "mastr_status": text(row, "EinheitBetriebsstatus_extended", "EinheitBetriebsstatus"),
                    "capacity_mw": round(capacity_kw / 1000.0, 3),
                    "unit_count": 1,
                    "state": row.get("Bundesland") or "",
                    "district": row.get("Landkreis"),
                    "municipality": row.get("Gemeinde"),
                    "owner": row.get("Anlagenbetreiber"),
                    "commissioning_date": row.get("Inbetriebnahmedatum") or row.get("EegInbetriebnahmedatum"),
                    "planned_commissioning_date": row.get("GeplantesInbetriebnahmedatum"),
                    "lat": lat,
                    "lon": lon,
                }
                item = (capacity_kw, sequence, site)
                heap = heaps[technology]
                if len(heap) < limit:
                    heapq.heappush(heap, item)
                elif item[0] > heap[0][0]:
                    heapq.heapreplace(heap, item)
                sequence += 1

    sites = [site for heap in heaps.values() for _, _, site in heap]
    sites.sort(key=lambda item: (str(item["technology"]), -float(item["capacity_mw"])))
    return sites


def fetch_industry() -> None:
    features: list[dict[str, Any]] = []
    offset = 0
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        while True:
            response = client.get(
                INDUSTRY_URL,
                params={
                    "where": "countryCode='DE'",
                    "outFields": (
                        "siteName,countryCode,eprtr_sectors,eea_activities,activity_details,"
                        "Site_reporting_year,nFacilities,nInstallations,nLCP,has_seveso"
                    ),
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "resultOffset": offset,
                    "resultRecordCount": 1000,
                    "f": "geojson",
                },
            )
            response.raise_for_status()
            batch = response.json().get("features", [])
            features.extend(batch)
            if len(batch) < 1000:
                break
            offset += len(batch)
    INDUSTRY_CACHE.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )


def build_industry() -> list[dict[str, Any]]:
    raw = json.loads(INDUSTRY_CACHE.read_text(encoding="utf-8"))["features"]
    strategic_sectors = {"ENERGY", "METALS", "MINERALS", "CHEMICALS", "PAPER AND WOOD"}
    features = []
    unique: dict[tuple[str, tuple[float, float]], dict[str, Any]] = {}
    for item in raw:
        props = item["properties"]
        sector = props.get("eprtr_sectors") or ""
        if not strategic_sectors.intersection(sector.split(",")):
            continue
        coordinates = tuple(item["geometry"]["coordinates"])
        unique[(props.get("siteName") or "Industrial site", coordinates)] = item

    for item in unique.values():
        props = item["properties"]
        features.append(
            feature(
                item["geometry"],
                {
                    "kind": "industry",
                    "name": props.get("siteName") or "Industrial site",
                    "sector": props.get("eprtr_sectors") or "Other industry",
                    "activity": props.get("eea_activities") or props.get("activity_details"),
                    "reporting_year": props.get("Site_reporting_year"),
                    "facilities": props.get("nFacilities") or 1,
                    "installations": props.get("nInstallations") or 0,
                    "large_combustion_plants": props.get("nLCP") or 0,
                    "seveso": bool(props.get("has_seveso")),
                    "source": SOURCES["industry"]["name"],
                    "source_url": SOURCES["industry"]["url"],
                },
            )
        )
    return features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-industry", action="store_true")
    args = parser.parse_args()

    if args.fetch_industry:
        fetch_industry()
    if not INDUSTRY_CACHE.exists():
        raise SystemExit("EEA industry cache missing; rerun with --fetch-industry")
    if not AIRPORT_ARCHIVE.exists():
        raise SystemExit("Eurostat airports cache missing: data/source_downloads/eurostat_airports_2024.zip")
    if not STATE_BOUNDARIES_CACHE.exists():
        raise SystemExit("GISCO NUTS cache missing: data/source_downloads/nuts1_2024.geojson")
    if not MASTR_ARCHIVE.exists():
        raise SystemExit("MaStR cache missing: data/bnetza_open_mastr_2025-02-09.zip")

    rail, rail_nodes, rail_structures = build_rail()
    ports = build_ports()
    airports = build_airports()
    gas_lines, gas_nodes = build_gas()
    industry = build_industry()
    states = build_states()
    energy_sites = build_energy_sites()

    write_geojson("rail_network.geojson", rail)
    write_geojson("rail_structures.geojson", rail_structures)
    write_geojson("gas_network.geojson", gas_lines)
    write_geojson("state_boundaries.geojson", states)
    write_geojson("infrastructure_nodes.geojson", [*rail_nodes, *ports, *airports, *gas_nodes, *industry])
    (OUTPUT / "energy_sites.json").write_text(
        json.dumps(energy_sites, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    manifest = {
        "generated_at": date.today().isoformat(),
        "counts": {
            "rail_routes": len(rail),
            "rail_nodes": len(rail_nodes),
            "rail_structures": len(rail_structures),
            "gas_pipeline_segments": len(gas_lines),
            "ports": len(ports),
            "airports": len(airports),
            "gas_nodes": len(gas_nodes),
            "industrial_sites": len(industry),
            "state_boundaries": len(states),
            "energy_sites": len(energy_sites),
        },
        "sources": SOURCES,
        "hydrogen_context": {
            "name": "Approved German hydrogen core network",
            "url": "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Wasserstoff/Kernnetz/start.html",
            "approved_length_km": 9040,
            "conversion_share_percent": 60,
            "target_year": 2032,
            "investment_eur_billion": 18.9,
            "map_note": (
                "The official map is schematic. Exact routes are decided in later planning "
                "and permitting, so InfraAtlas does not draw false-precision line geometry."
            ),
        },
    }
    (OUTPUT / "infrastructure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
