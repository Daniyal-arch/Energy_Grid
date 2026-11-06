"""The download centre's index (brief 30, Track 6.7; docs/product/download-centre.md).

Writes frontend/public/data/downloads.json: per dataset of the Layers panel
(frontend/src/app/datasets.json and the registry waves wave9.json, wave10.json) its files as
the app reads them, the lake tables that hold it in full, and per file its licence, attribution
text and "as of" date.

Where each value comes from
  files        CORE below (the files frontend/src/app/data.ts loads for the dataset's layers);
               for the waves, the layer's tiles URL or data/eu/w<N>/<name>.json and the
               colouring's data/eu/w<N>c/<file>.json
  licence      the file's own `licence` field; else LICENCE below (as docs/DATA_SOURCES.md or
               the agent catalogue states it); else the licence named in the file's `source`;
               for the waves, the catalogue table's `licence` (agent/catalog/wave<N>.yaml)
  attribution  the file's `source` field, else the dataset part's `source`
  as of        the file's own `as_of`, `fetched`, `at`, `date`, `release` or `edition` field
  lake         the catalogue's table names (the lake is private: listed, not offered)

Which licences allow a download is decided in the page (frontend/src/ui/Downloads.tsx), from
the licence text. Global Energy Monitor files carry a hold: the project does not republish them.

    uv run python scripts/build_downloads.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "src" / "app"
DATA = ROOT / "frontend" / "public" / "data"
CATALOG = ROOT / "agent" / "catalog"
OUT = DATA / "downloads.json"

SNAPSHOT = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-data/eu"
ARCHIVE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu"
R2 = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev"

# Files per core dataset: "eu/x.json" bundled, "snap:" also on eu-data, "arch:" also on eu-days,
# "r2:" public tiles or grids on R2, "<date>" a file per day (listed, not linked).
CORE: dict[str, list[str]] = {
    "flows": ["snap:eu/flows.json", "snap:eu/us.json"],
    "prices": ["arch:eu/prices.json", "arch:eu/us_prices.json", "arch:eu/us_rt.json"],
    "liveGrids": [
        "snap:eu/us.json",
        "snap:eu/brazil.json",
        "snap:eu/aemo.json",
        "snap:eu/taiwan.json",
        "snap:eu/ontario.json",
        "snap:eu/nz.json",
        "snap:eu/za.json",
    ],
    "towers": ["snap:eu/stats.json", "snap:eu/us.json"],
    "transmission": ["eu/grid.json", "r2:grid/us-lines.pmtiles", "r2:grid/world-hv.pmtiles"],
    "hvdc": ["eu/grid.json"],
    "substations": ["eu/grid.json", "r2:grid/world-substations.pmtiles"],
    "cables": ["eu/cables.json", "eu/sea_cables.json"],
    "predicted": ["r2:grid/world-grid.pmtiles"],
    "tyndp": ["eu/tyndp.json"],
    "capacity": [
        "arch:eu/connect.json",
        "eu/connect/harmonised.json",
        "us/queue.json",
        "us/queues_live.json",
    ],
    "plants": ["eu/plants.json", "eu/plants/<ISO>.json", "us/plants.json", "eu/world_plants.json"],
    "registers": [
        "eu/mastr/units_large.json",
        "eu/registers/gb.json",
        "eu/registers/dk.json",
        "eu/registers/se.json",
        "eu/registers/ie.json",
        "eu/registers/pt.json",
        "eu/registers/fr.json",
        "eu/registers/be.json",
        "eu/registers/cz.json",
        "us/turbines.json",
        "us/solar.json",
    ],
    "offshoreWind": ["eu/offshore_wind.json"],
    "grw": ["eu/grw_countries.json", "r2:grid/grw.pmtiles"],
    "plantOutput": ["arch:eu/units/<date>.json", "arch:eu/usunits/<date>.json"],
    "gasPipes": ["eu/gem/pipelines_gas.json", "us/gas_pipes.json"],
    "oilPipes": ["eu/gem/pipelines_oil.json"],
    "lngTerminals": ["eu/gem/lng.json"],
    "lngSendOut": ["arch:eu/lng_terminals.json"],
    "gasFlows": ["arch:eu/gas_flows.json"],
    "gas": ["eu/gas.json"],
    "gasProjects": ["eu/gas_projects.json"],
    "coalTerminals": ["eu/gem/coal_terminals.json"],
    "oilGasFields": ["eu/gem/fields.json"],
    "coalMines": ["eu/gem/coal_mines.json"],
    "emitters": ["arch:eu/ets.json", "us/ghgrp.json"],
    "ctrace": ["arch:eu/ctrace.json"],
    "methane": ["eu/gem/methane.json"],
    "steel": ["eu/gem/steel.json"],
    "cement": ["eu/gem/cement.json"],
    "chemicals": ["eu/gem/chemicals.json"],
    "ironOre": ["eu/gem/iron_ore.json"],
    "dataCentres": ["arch:eu/datacentres.json"],
    "hydrogen": ["eu/hydrogen.json"],
    "ev": ["eu/ev_eu.json", "us/ev_chargers.json"],
    "water": ["eu/water.json"],
    "flood": ["r2:grid/flood-eu-0.01deg.u8", "r2:grid/flood-world-0.05deg.u8"],
    "protectedAreas": ["eu/protected.json"],
    "usOutages": ["eu/us_outages.json", "us/counties.json"],
    "solarResource": ["eu/atlas.json"],
    "windResource": ["eu/atlas.json"],
    "wind": ["snap:eu/wind.json", "snap:eu/wind_world.json"],
    "sun": ["snap:eu/wind_world.json"],
    "financeCoal": ["eu/gem/finance.json"],
    "financeGas": ["eu/gem/finance.json"],
    "colour-renewable": ["snap:eu/stats.json"],
    "colour-tr_renewables": ["eu/transition.json"],
    "colour-tr_wind_solar": ["eu/transition.json"],
    "colour-tr_coal": ["eu/transition.json"],
    "colour-tr_intensity": ["eu/transition.json"],
    "colour-access": ["arch:eu/world_stats.json"],
    "colour-price": ["snap:eu/stats.json"],
    "colour-pr_negative": ["arch:eu/prices.json"],
    "colour-pr_mean": ["arch:eu/prices.json"],
    "colour-pr_solar": ["arch:eu/prices.json"],
    "colour-pr_wind": ["arch:eu/prices.json"],
    "colour-rt_household": ["arch:eu/retail.json"],
    "colour-offline": ["snap:eu/outages.json"],
    "colour-ir_solar": ["arch:eu/irena.json"],
    "colour-ir_wind": ["arch:eu/irena.json"],
    "industrialFacilities": ["eu/w8/industrial.json"],
    "excessHeat": ["eu/w8/excess_heat.json"],
    "dams": ["eu/w8/dams.json"],
    "co2Storage": ["eu/w8/co2storage.json"],
    "fires": ["eu/w8/fires.json"],
}

ENTSOE = "ENTSO-E Transparency Platform terms (re-use with attribution)"
# Licences of files that carry none, as docs/DATA_SOURCES.md or the agent catalogue states them
LICENCE: dict[str, str] = {
    "eu/flows.json": ENTSOE,
    "eu/stats.json": ENTSOE,
    "eu/prices.json": ENTSOE,
    "eu/outages.json": ENTSOE,
    "eu/units/<date>.json": ENTSOE,
    "eu/tyndp.json": "ENTSO-E terms of use (re-use with attribution)",
    "eu/us_prices.json": "the US markets' public data",
    "eu/us_rt.json": "the US markets' public data",
    "us/queues_live.json": "the US markets' public data",
    "eu/us.json": "public domain (US EIA)",
    "eu/usunits/<date>.json": "public domain (US EPA)",
    "us/plants.json": "public domain (US EIA)",
    "us/ghgrp.json": "public domain (US EPA)",
    "us/counties.json": "public domain (US Census Bureau)",
    "us/turbines.json": "public domain (USGS)",
    "us/solar.json": "public domain (USGS)",
    "us/queue.json": "CC BY 4.0 (Lawrence Berkeley National Laboratory)",
    "eu/nz.json": "Transpower website terms (live page)",
    "eu/za.json": "Eskom data portal terms",
    "eu/grid.json": "ODbL 1.0 (OpenStreetMap contributors)",
    "eu/cables.json": "ODbL 1.0 (OpenStreetMap contributors)",
    "eu/datacentres.json": "ODbL 1.0 (OpenStreetMap contributors)",
    "grid/us-lines.pmtiles": "ODbL 1.0 (OpenStreetMap contributors)",
    "grid/world-hv.pmtiles": "ODbL 1.0 (OpenStreetMap contributors)",
    "grid/world-substations.pmtiles": "ODbL 1.0 (OpenStreetMap contributors)",
    "grid/world-grid.pmtiles": "CC BY 4.0 (Gridfinder, Arderne et al. 2020)",
    "grid/grw.pmtiles": "MIT (Global Renewables Watch)",
    "grid/flood-eu-0.01deg.u8": "CC BY 4.0 (JRC)",
    "grid/flood-world-0.05deg.u8": "CC BY 4.0 (JRC)",
    "eu/mastr/units_large.json": "dl-de/by-2-0 (Bundesnetzagentur)",
    "eu/gas_flows.json": "ENTSOG terms of use (re-use with attribution)",
    "eu/gas_projects.json": "ENTSOG terms of use (re-use with attribution)",
    "eu/hydrogen.json": "European Commission re-use policy (Decision 2011/833/EU)",
    "eu/ev_eu.json": (
        "CC BY 4.0 (EAFO); CC BY 4.0 (BNetzA); Licence Ouverte 2.0 (IRVE); ODbL 1.0 (OpenStreetMap)"
    ),
    "eu/protected.json": "EEA re-use with attribution (Natura 2000); public domain (PAD-US)",
    "eu/atlas.json": "CC BY 4.0 (Global Solar Atlas, World Bank and Solargis; Global Wind Atlas, DTU)",
    "eu/w8/co2storage.json": "reuse authorised with acknowledgement (JRC)",
    "eu/retail.json": (
        "CC BY 4.0 (Eurostat); public domain (US EIA); Open Government Licence v3.0 (GB)"
    ),
}
HOLD_GEM = (
    "the project does not republish Global Energy Monitor files (CLAUDE.md); the owner decides"
)
# licence names recognised in a file's `source` text (the first ones found are kept)
SOURCE_LICENCE = re.compile(
    r"CC BY(?:-[A-Z]{2}(?:-[A-Z]{2})?)? \d\.\d|CC0(?: 1\.0)?|ODbL(?: 1\.0)?|OGL v?\d(?:\.\d)?|"
    r"Open Government Licence v?\d(?:\.\d)?|Licence Ouverte(?: v?\d\.\d)?|dl-de/(?:by|zero)-\d-\d|"
    r"public domain|\bMIT\b"
)
AS_OF = ("as_of", "fetched", "at", "date", "release", "edition", "through")


def read_meta(rel: str) -> dict[str, Any]:
    """Top-level fields of a bundled file (its licence, source and dates), or nothing."""
    path = DATA / rel
    if "<" in rel or not path.exists() or path.suffix != ".json":
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def as_of(meta: dict[str, Any]) -> str | None:
    for k in AS_OF:
        v = meta.get(k)
        if isinstance(v, str) and v:
            return v[:10] if re.match(r"\d{4}-\d\d-\d\dT", v) else v
    return None


def licence_of(rel: str, meta: dict[str, Any], fallback: str | None = None) -> str | None:
    lic = meta.get("licence") or meta.get("license")
    if isinstance(lic, str) and lic:
        return lic
    if rel in LICENCE:
        return LICENCE[rel]
    if fallback:
        return fallback
    found = SOURCE_LICENCE.findall(str(meta.get("source") or ""))
    return "; ".join(dict.fromkeys(found)) or None


def core_file(spec: str, part_source: str) -> dict[str, Any]:
    kind, _, rel = spec.partition(":") if ":" in spec else ("", "", spec)
    if kind == "r2":
        return {
            "path": rel,
            "url": f"{R2}/{rel}",
            "remote": None,
            "licence": LICENCE.get(rel),
            "attribution": part_source,
            "as_of": None,
            "hold": None,
        }
    meta = read_meta(rel)
    name = rel.split("/", 1)[1] if rel.startswith("eu/") else None
    remote = None
    if kind == "snap" and name:
        remote = f"{SNAPSHOT}/{name}"
    elif kind == "arch" and name:
        remote = f"{ARCHIVE}/{name}"
    gem = rel.startswith("eu/gem/") or rel.startswith("eu/world_plant")
    return {
        "path": rel,
        "url": f"/data/{rel}" if "<" not in rel and (DATA / rel).exists() else None,
        "remote": remote,
        "licence": "CC BY 4.0 (Global Energy Monitor)" if gem else licence_of(rel, meta),
        "attribution": str(meta.get("source") or part_source),
        "as_of": as_of(meta),
        "hold": HOLD_GEM if gem else None,
    }


def load_catalog() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(CATALOG.glob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(d, dict) and d.get("dataset"):
            out[str(d["dataset"])] = d
    return out


def wave_entries(wave: int, catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    reg = json.loads((APP / f"wave{wave}.json").read_text(encoding="utf-8"))
    tables = (catalog.get(f"wave{wave}") or {}).get("tables") or {}
    layers = {x["id"]: x for x in reg["layers"]}
    colours = {x["id"]: x for x in reg["colours"]}
    out: dict[str, dict[str, Any]] = {}
    for ds in reg["datasets"]:
        files: list[dict[str, Any]] = []
        lake: list[str] = []
        for part in ds["parts"]:
            lid = part.get("layer") or ds.get("colour")
            if not lid:
                continue
            name = re.sub(r"^w\d+c?_", "", lid)
            table = tables.get(name) or {}
            if table:
                lake.append(f"wave{wave}.{name}")
            src = part["source"]
            if lid in colours:
                rel = f"eu/w{wave}c/{colours[lid].get('file', name)}.json"
                meta = read_meta(rel)
                url: str | None = f"/data/{rel}" if (DATA / rel).exists() else None
            elif lid in layers and layers[lid].get("tiles"):
                url = str(layers[lid]["tiles"]).removeprefix("pmtiles://")
                rel, meta = url.removeprefix(R2 + "/"), {}
            else:
                rel = f"eu/w{wave}/{name}.json"
                meta = read_meta(rel)
                url = f"/data/{rel}" if (DATA / rel).exists() else None
            if not url:
                continue
            files.append(
                {
                    "path": rel,
                    "url": url,
                    "remote": None,
                    "licence": licence_of(rel, meta, table.get("licence"))
                    or licence_of(rel, {"source": src}),
                    "attribution": str(meta.get("source") or src),
                    "as_of": as_of(meta),
                    "hold": None,
                }
            )
        if not files and lake:
            # a lake-only table: no file to offer, the licence still shown
            lic = (tables.get(lake[0].split(".", 1)[1]) or {}).get("licence")
            out[ds["id"]] = {"files": [], "lake": lake, "licence": lic}
        else:
            out[ds["id"]] = {"files": files, "lake": lake}
    return out


def main() -> None:
    catalog = load_catalog()
    registry = json.loads((APP / "datasets.json").read_text(encoding="utf-8"))["datasets"]
    entries: dict[str, dict[str, Any]] = {}
    for ds in registry:
        source = "; ".join(p["source"] for p in ds["parts"])
        files = [core_file(s, source) for s in CORE.get(ds["id"], [])]
        cat = catalog.get(ds["id"]) or {}
        tables = cat.get("tables") or {}
        lake = [f"{ds['id']}/{t}" for t in tables] if isinstance(tables, dict) else []
        entries[ds["id"]] = {"files": files, "lake": lake}
    for wave in (9, 10):
        entries.update(wave_entries(wave, catalog))
    payload = {
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "about": (
            "The download centre's index (scripts/build_downloads.py): per dataset of the Layers "
            "panel its files, licence, attribution and as-of date. The page offers a file only "
            "when its licence allows redistribution."
        ),
        "snapshot_remote": SNAPSHOT,
        "archive_remote": ARCHIVE,
        "datasets": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_files = sum(len(e["files"]) for e in entries.values())
    no_lic = sum(1 for e in entries.values() for f in e["files"] if not f["licence"])
    print(
        f"{OUT.relative_to(ROOT)}: {len(entries)} datasets, {n_files} files, {no_lic} without a licence"
    )


if __name__ == "__main__":
    main()
