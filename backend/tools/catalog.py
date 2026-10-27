"""The semantic catalogue: `agent/catalog/*.yaml` (lake tables and APIs, with meaning, units,
keys and example questions), the map's datasets (`frontend/src/app/datasets.json`) and the app
tables the service loads from the map files (`app.*`). `search_catalog` ranks them for a
question; `describe_table` gives one table's columns, units, sample rows and examples.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

STOP = set(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "many",
        "much",
        "of",
        "on",
        "or",
        "per",
        "the",
        "this",
        "to",
        "was",
        "what",
        "which",
        "with",
        "where",
        "who",
        "does",
        "do",
        "did",
        "than",
        "vs",
    ]
)

# the tables data/duck.py builds from the app's map files
APP_TABLES: dict[str, dict[str, Any]] = {
    "app.eu_plants": {
        "title": "Europe's operating power plants of 20 MW and more (the map's Plants layer)",
        "grain": "one row per plant (powerplantmatching)",
        "columns": {
            "fuel": "nuclear, coal, gas, hydro, wind, solar, bio, storage, other",
            "mw": "MW, capacity as published",
            "lon": "degrees",
            "lat": "degrees",
            "country": "ISO alpha-2",
            "name": "plant name",
            "year": "commissioning year",
        },
        "layer": "plants",
    },
    "app.eu_substations": {
        "title": "Europe's transmission substations, 220 kV and more (PyPSA-Eur, OpenStreetMap)",
        "grain": "one row per substation",
        "columns": {
            "kv": "kV, highest voltage",
            "lon": "degrees",
            "lat": "degrees",
            "country": "ISO alpha-2",
        },
        "layer": "gridEU",
    },
    "app.eu_prices": {
        "title": "Day-ahead prices per European bidding zone, 12-month average and hours below "
        "zero (ENTSO-E A44)",
        "grain": "one row per bidding zone for the 12 months in period_start..period_end",
        "columns": {
            "zone": "bidding zone (DE-LU, NL, DK1, ...)",
            "country": "ISO alpha-2",
            "mean_eur_mwh": "EUR/MWh, mean of the hourly prices (computed in scripts)",
            "negative_hours": "hours below zero (15-minute intervals count as quarter hours)",
            "min_eur_mwh": "EUR/MWh",
            "min_at_utc": "UTC",
            "max_eur_mwh": "EUR/MWh",
            "max_at_utc": "UTC",
            "period_start": "date",
            "period_end": "date",
        },
        "layer": "prices",
    },
    "app.world_plants": {
        "title": "The world's power plants by type and status (Global Energy Monitor, "
        "Integrated Power Tracker, map points)",
        "grain": "one row per map point (unit or plant), no names",
        "columns": {
            "type": "solar, wind, gas, coal, hydro, bio, nuclear, geothermal",
            "status": "operating, construction, planned, retired",
            "mw": "MW",
            "lon": "degrees",
            "lat": "degrees",
            "year": "start year",
        },
        "layer": "worldPlants",
    },
    "app.us_plants": {
        "title": "US generators of 1 MW and more per plant, type and status (EIA-860M)",
        "grain": "one row per plant, type and status",
        "columns": {
            "name": "plant name",
            "state": "US state code",
            "type": "technology group",
            "status": "operating, construction, planned, retired",
            "mw": "MW, net summer capacity",
            "year": "operating year",
            "lon": "degrees",
            "lat": "degrees",
        },
        "layer": "usPlants",
    },
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOP]


def _flat(v: Any) -> str:
    if isinstance(v, dict):
        return " ".join(f"{k} {_flat(x)}" for k, x in v.items())
    if isinstance(v, list):
        return " ".join(_flat(x) for x in v)
    return str(v)


class Catalogue:
    def __init__(self, agent_dir: Path, datasets_json: Path) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        for p in sorted((agent_dir / "catalog").glob("*.yaml")):
            d = yaml.safe_load(p.read_text())
            if isinstance(d, dict) and d.get("dataset"):
                self.entries[d["dataset"]] = d
        self.map_datasets: list[dict[str, Any]] = []
        if datasets_json.exists():
            self.map_datasets = json.loads(datasets_json.read_text()).get("datasets", [])
        self.docs: list[dict[str, Any]] = []
        for name, t in APP_TABLES.items():
            self.docs.append(
                {
                    "kind": "app table",
                    "name": name,
                    "title": t["title"],
                    "text": _flat(t),
                    "layer": t["layer"],
                }
            )
        for ds, e in self.entries.items():
            tables = e.get("tables") or {}
            base = f"{e.get('title', '')} {e.get('notes', '')}"
            if not tables:
                self.docs.append(
                    {
                        "kind": e.get("access", "dataset"),
                        "name": ds,
                        "title": e.get("title", ds),
                        "text": base + " " + _flat(e.get("series", "")),
                    }
                )
            for tn, t in tables.items():
                self.docs.append(
                    {
                        "kind": "lake table",
                        "name": f"{ds}.{tn}",
                        "title": f"{e.get('title', ds)}: {tn}",
                        "text": f"{base} {tn} {_flat(t)}",
                    }
                )
            for ex in e.get("examples") or []:
                self.docs[-1]["text"] += " " + str(ex.get("q", ""))
        for d in self.map_datasets:
            self.docs.append(
                {
                    "kind": "map dataset",
                    "name": d["id"],
                    "title": d.get("name", d["id"]),
                    "text": _flat(
                        {k: d.get(k) for k in ("name", "description", "category", "parts")}
                    ),
                    "layers": [p.get("layer") for p in d.get("parts", [])],
                }
            )
        self._tf = [
            Counter(_tokens(doc["title"] + " " + doc["title"] + " " + doc["text"]))
            for doc in self.docs
        ]
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(self.docs)
        self._idf = {t: math.log(1 + n / c) for t, c in df.items()}

    def dataset_list(self) -> list[tuple[str, str]]:
        """(name, title) of every catalogue dataset and app table: the system prompt's list."""
        out = [(n, t["title"]) for n, t in APP_TABLES.items()]
        out += [(ds, str(e.get("title", ds))) for ds, e in sorted(self.entries.items())]
        return out

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q = _tokens(query)
        scored = []
        for doc, tf in zip(self.docs, self._tf, strict=True):
            s = sum(self._idf.get(t, 0) * (1 + math.log(tf[t])) for t in q if tf[t])
            if s > 0:
                scored.append((s, doc))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, doc in scored[:limit]:
            hit = {k: v for k, v in doc.items() if k != "text"}
            hit["score"] = round(s, 2)
            out.append(hit)
        return out

    def table_entry(self, name: str) -> dict[str, Any] | None:
        if name in APP_TABLES:
            return APP_TABLES[name]
        ds, _, tn = name.partition(".")
        e = self.entries.get(ds)
        if not e:
            return None
        t = (e.get("tables") or {}).get(tn)
        if tn and t is None:
            return None
        out = {k: v for k, v in e.items() if k not in ("tables", "examples")}
        if t is not None:
            out["table"] = t if isinstance(t, dict) else {"about": t}
        else:
            out["tables"] = list((e.get("tables") or {}).keys())
        out["examples"] = e.get("examples") or []
        return out

    def licence(self, dataset: str) -> str:
        return str(self.entries.get(dataset, {}).get("licence", "see agent/catalog"))
