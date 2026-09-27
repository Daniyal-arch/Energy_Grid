"""Curated strategy context for the broader Germany infrastructure pivot.

This is intentionally a small static catalog first: it lets the agent discuss scope,
source coverage, and ingestion priorities without inventing facts from memory. Pipelines
can promote these catalog entries into real adapters over time.
"""

from __future__ import annotations

from typing import Any

ASPECTS: list[dict[str, Any]] = [
    {
        "id": "energy_security",
        "label": "Energy security",
        "questions": [
            "How exposed is Germany to gas, electricity, LNG, hydrogen, and fuel shocks?",
            "Which regions and sectors carry the highest supply-security sensitivity?",
            "Where do storage, imports, grid expansion, and demand reduction offset risk?",
        ],
        "dataset_ids": [
            "bnetza_gas_status",
            "entso_e_transparency",
            "energy_charts",
            "entsog_capacity",
            "h2_core_network",
            "mastr_download",
            "netzausbau",
        ],
    },
    {
        "id": "dependencies",
        "label": "Dependency exposure",
        "questions": [
            "Which suppliers, fuels, minerals, and intermediate goods are hard to replace?",
            "Where are dependencies concentrated by country, commodity, or infrastructure route?",
            "Which dependencies affect energy transition build-out and industrial production?",
        ],
        "dataset_ids": [
            "destatis_foreign_trade",
            "eurostat_energy_dependency",
            "eurostat_material_flows",
            "uba_raw_material_footprint",
            "dera_raw_material_list",
        ],
    },
    {
        "id": "infrastructure_topology",
        "label": "Infrastructure topology",
        "questions": [
            "Which nodes and corridors connect energy, rail, port, road, and industrial systems?",
            "Where do electricity, gas, hydrogen, and transport corridors overlap?",
            "Which assets are chokepoints, substitutes, or resilience buffers?",
        ],
        "dataset_ids": [
            "netzausbau",
            "db_infrago",
            "gisco_transport",
            "entsog_capacity",
            "h2_core_network",
            "openstreetmap",
        ],
    },
    {
        "id": "economic_resilience",
        "label": "Economic resilience",
        "questions": [
            "How do power prices, gas prices, trade flows, and industrial demand move together?",
            "Which regions combine high infrastructure dependency with high economic exposure?",
            "Where do import, export, and supply-chain signals point to stress?",
        ],
        "dataset_ids": [
            "destatis_foreign_trade",
            "genesis_transport_trade",
            "energy_charts",
            "bnetza_gas_status",
            "eurostat_figaro",
        ],
    },
    {
        "id": "transition_execution",
        "label": "Transition execution",
        "questions": [
            "Is build-out of renewables, storage, grid, hydrogen, and EV infrastructure aligned?",
            "Where are permitting, grid connection, and corridor build-out bottlenecks?",
            "Which planned assets change dependency or resilience risk once operational?",
        ],
        "dataset_ids": [
            "mastr_download",
            "netzausbau",
            "h2_core_network",
            "bnetza_charging",
            "energy_charts",
        ],
    },
    {
        "id": "geopolitical_events",
        "label": "Geopolitical event exposure",
        "questions": [
            "Which conflicts, sanctions, route disruptions, or supplier shifts matter to Germany?",
            "Which infrastructure layers would be affected by a supplier or corridor shock?",
            "What facts are confirmed by official data versus only reported in news?",
        ],
        "dataset_ids": [
            "destatis_foreign_trade",
            "eurostat_energy_dependency",
            "entsog_capacity",
            "bnetza_gas_status",
        ],
    },
]


DATASETS: list[dict[str, Any]] = [
    {
        "id": "mastr_download",
        "name": "MaStR public data download",
        "source": "Bundesnetzagentur",
        "url": "https://www.marktstammdatenregister.de/MaStR/Datendownload",
        "access": "Daily XML bulk download",
        "cadence": "daily",
        "status": "implemented",
        "why": "Official electricity and gas asset registry: generation, storage, units, actors.",
        "adapter": "mastr",
    },
    {
        "id": "energy_charts",
        "name": "Energy-Charts API",
        "source": "Fraunhofer ISE",
        "url": "https://www.energy-charts.info/api.html",
        "access": "Free API, no key",
        "cadence": "hourly / quarter-hourly",
        "status": "implemented",
        "why": "Power mix, prices, installed capacity, and cross-border electricity flows.",
        "adapter": "energycharts",
    },
    {
        "id": "entso_e_transparency",
        "name": "ENTSO-E Transparency Platform",
        "source": "ENTSO-E",
        "url": "https://www.entsoe.eu/data/transparency-platform/",
        "access": "REST API with free registered token",
        "cadence": "hourly / daily",
        "status": "planned",
        "why": "Electricity load, generation, transmission, balancing, outages, and flows.",
        "adapter": "entsoe",
    },
    {
        "id": "netzausbau",
        "name": "Netzausbau and BBPlG/EnLAG project data",
        "source": "Bundesnetzagentur",
        "url": "https://www.netzausbau.de/",
        "access": "Project pages, downloads, GIS packages where published",
        "cadence": "quarterly / event driven",
        "status": "partial",
        "why": "Transmission expansion corridors, phase status, voltage, project owner.",
        "adapter": "grid files",
    },
    {
        "id": "bnetza_gas_status",
        "name": "Current gas supply status",
        "source": "Bundesnetzagentur",
        "url": "https://www.bundesnetzagentur.de/DE/Gasversorgung/aktuelle_gasversorgung/start.html",
        "access": "Interactive charts with CSV downloads",
        "cadence": "daily / weekly / monthly",
        "status": "candidate",
        "why": "Gas flows, storage fill, consumption, wholesale prices, and domestic production.",
        "adapter": None,
    },
    {
        "id": "entsog_capacity",
        "name": "ENTSOG system capacity and gas maps",
        "source": "ENTSOG / Gas Infrastructure Europe",
        "url": "https://www.entsog.eu/maps",
        "access": "Excel capacity datasets and transparency dashboards",
        "cadence": "annual maps plus frequent transparency updates",
        "status": "candidate",
        "why": "European gas infrastructure, cross-border capacity, storage and LNG context.",
        "adapter": None,
    },
    {
        "id": "h2_core_network",
        "name": "Hydrogen core network",
        "source": "Bundesnetzagentur / FNB Gas",
        "url": "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Wasserstoff/Kernnetz/start.html",
        "access": "Official approval page with annex spreadsheets and map files",
        "cadence": "event driven / biennial planning cycle",
        "status": "candidate",
        "why": "Approved hydrogen pipelines, conversions, operators, costs, and 2032 targets.",
        "adapter": None,
    },
    {
        "id": "db_infrago",
        "name": "DB InfraGO infrastructure data",
        "source": "Deutsche Bahn AG / Mobilithek / GovData",
        "url": "https://data.gov.de/suche/daten/infrastrukturdaten-der-db-infrago",
        "access": "GeoPackage and CSV downloads",
        "cadence": "periodic",
        "status": "candidate",
        "why": "Rail network, stations, crossings, bridges, tunnels, and operating locations.",
        "adapter": None,
    },
    {
        "id": "gisco_transport",
        "name": "GISCO transport networks",
        "source": "Eurostat GISCO",
        "url": "https://ec.europa.eu/eurostat/en/web/gisco/geodata/transport-networks",
        "access": "GDB, SHP, and GeoPackage downloads",
        "cadence": "periodic",
        "status": "candidate",
        "why": "European airports, ports, and transport geodata for corridor context.",
        "adapter": None,
    },
    {
        "id": "destatis_foreign_trade",
        "name": "German foreign trade statistics",
        "source": "Destatis / GENESIS-Online",
        "url": "https://www.destatis.de/DE/Themen/Wirtschaft/Aussenhandel/_inhalt.html",
        "access": "GENESIS tables, reports, and downloads",
        "cadence": "monthly / annual",
        "status": "candidate",
        "why": "Imports and exports by partner, commodity, raw gas, crude oil, and goods group.",
        "adapter": None,
    },
    {
        "id": "genesis_transport_trade",
        "name": "GENESIS transport and logistics tables",
        "source": "Destatis GENESIS-Online",
        "url": "https://genesis.destatis.de/datenbank/online/statistics",
        "access": "GENESIS API / table downloads",
        "cadence": "monthly / annual",
        "status": "candidate",
        "why": "Sea freight, inland waterways, road freight, pipeline transport, and ports.",
        "adapter": None,
    },
    {
        "id": "eurostat_energy_dependency",
        "name": "Energy import dependency",
        "source": "Eurostat / Destatis",
        "url": "https://www.destatis.de/Europa/DE/Thema/Umwelt-Energie/Energieabhaengigkeit.html",
        "access": "Eurostat database",
        "cadence": "annual",
        "status": "candidate",
        "why": "Net-import dependency by country and energy product.",
        "adapter": None,
    },
    {
        "id": "eurostat_material_flows",
        "name": "Material flow accounts",
        "source": "Eurostat",
        "url": "https://ec.europa.eu/eurostat/en/web/environment/information-data/material-flows-resource-productivity",
        "access": "Eurostat database",
        "cadence": "annual",
        "status": "candidate",
        "why": "Domestic extraction, imports, exports, and material consumption indicators.",
        "adapter": None,
    },
    {
        "id": "uba_raw_material_footprint",
        "name": "Raw material footprint",
        "source": "Umweltbundesamt / Destatis",
        "url": "https://www.umweltbundesamt.de/en/indicator-raw-material-footprint",
        "access": "Excel and PDF downloads",
        "cadence": "annual",
        "status": "candidate",
        "why": "Raw material equivalents embedded in German consumption and investment.",
        "adapter": None,
    },
    {
        "id": "dera_raw_material_list",
        "name": "DERA raw material risk list",
        "source": "BGR / Deutsche Rohstoffagentur",
        "url": "https://www.bgr.bund.de/DE/Gemeinsames/Nachrichten/Aktuelles/2023/2023-07-26_dera_veroeffentlicht_rohstoffliste_2023.html",
        "access": "Report and tables",
        "cadence": "biennial",
        "status": "candidate",
        "why": "Supply concentration and country-risk signals for critical raw materials.",
        "adapter": None,
    },
    {
        "id": "bnetza_charging",
        "name": "Public EV charging infrastructure register",
        "source": "Bundesnetzagentur",
        "url": "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html",
        "access": "CSV / API via public register services",
        "cadence": "daily / monthly",
        "status": "planned",
        "why": "EV charging build-out, grid demand pressure, regional transition readiness.",
        "adapter": "ladestationen",
    },
    {
        "id": "openstreetmap",
        "name": "OpenStreetMap infrastructure layers",
        "source": "OpenStreetMap contributors",
        "url": "https://www.openstreetmap.org/",
        "access": "Overpass API / extracts",
        "cadence": "community updated",
        "status": "implemented",
        "why": "Fallback geospatial layer for power, substations, solar footprints, ports.",
        "adapter": "osm",
    },
    {
        "id": "eurostat_figaro",
        "name": "FIGARO inter-country input-output tables",
        "source": "Eurostat",
        "url": "https://ec.europa.eu/eurostat/en/web/esa-supply-use-input-tables/database",
        "access": "CSV and Excel downloads",
        "cadence": "annual",
        "status": "candidate",
        "why": "Value-chain exposure and imported value added across industries and countries.",
        "adapter": None,
    },
]


def get_context(aspect: str | None = None, limit: int = 40) -> dict[str, Any]:
    """Return aspects and datasets relevant to an optional aspect id or label."""

    key = (aspect or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key:
        aspects = [
            a
            for a in ASPECTS
            if key in {a["id"], a["label"].lower().replace(" ", "_").replace("-", "_")}
        ]
    else:
        aspects = ASPECTS

    if not key:
        datasets = DATASETS
    elif aspects:
        dataset_ids = {dataset_id for item in aspects for dataset_id in item["dataset_ids"]}
        datasets = [dataset for dataset in DATASETS if dataset["id"] in dataset_ids]
    else:
        datasets = [
            dataset
            for dataset in DATASETS
            if any(
                key in str(dataset[field]).lower().replace(" ", "_").replace("-", "_")
                for field in ("id", "name", "source", "why")
            )
        ]
    datasets = datasets[: max(1, min(limit, 100))]

    return {
        "aspects": aspects,
        "datasets": datasets,
        "note": (
            "Implemented status means this repo already has code or local assets for that "
            "source. Candidate status means it is a researched source ready for an adapter."
        ),
    }
