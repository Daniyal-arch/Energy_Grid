"""Areas (docs/tasks/27, A1): one record for whatever area a question means, kept like a query
result so maps and later turns reuse it.

An area is a country, a group of countries, a region, county, municipality or small area from
the outline sets, a bidding zone, a polygon or circle drawn on the map, the map on screen, a
union, buffer or intersection of these, or the whole world. Its id is a stable hash of its
outline (`a_` + 12 hex). Geometry work runs in DuckDB spatial on the lake's connection
(`geometry_always_xy` is on: lon/lat order, geodesic areas and lengths on the WGS84 ellipsoid).

Outlines come from the app's own files (countries, US states and counties) and from the lake's
outline tables (`shapes.nuts`, `shapes.admin1`, `shapes.bidding_zones` and the `outlines.*`
sets of brief 27 B1, all with the same columns). Nothing is invented: when no outline exists at
the asked level, the search says so and names what exists.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

from data.gazetteer import Gazetteer

log = logging.getLogger(__name__)

# surface of the WGS84 ellipsoid, km² (4π times the authalic radius 6,371,007.2 m, squared)
WGS84_SURFACE_KM2 = 510_065_621.7
AREA_ID = re.compile(r"\ba_[0-9a-f]{12}\b")

# level -> class on the level ladder (0 world/group/country ... 4 small area); drawn shapes 9
LEVEL_CLASS: dict[str, int] = {
    "world": 0,
    "group": 0,
    "country": 0,
    "nuts0": 0,
    "region": 1,
    "nuts1": 1,
    "nuts2": 1,
    "us_state": 1,
    "itl1": 1,
    "itl2": 1,
    "bidding_zone": 1,
    "operator": 1,
    "county": 2,
    "nuts3": 2,
    "us_county": 2,
    "admin2": 2,
    "itl3": 2,
    "lad": 2,
    "locality": 3,
    "lau": 3,
    "us_place": 3,
    "us_cousub": 3,
    "urban_centre": 3,
    "fr_commune": 3,
    "nl_gemeente": 3,
    "neighbourhood": 4,
    "us_tract": 4,
    "lsoa": 4,
    "msoa": 4,
    "iris": 4,
    "nl_wijk": 4,
    "nl_buurt": 4,
    "polygon": 9,
    "circle": 9,
    "bbox": 9,
}
# the words a question uses for a level class
LEVEL_WORDS: dict[str, int] = {
    "country": 0,
    "region": 1,
    "state": 1,
    "province": 1,
    "county": 2,
    "district": 2,
    "department": 2,
    "city": 3,
    "town": 3,
    "municipality": 3,
    "locality": 3,
    "commune": 3,
    "neighbourhood": 4,
    "neighborhood": 4,
    "small_area": 4,
    "small area": 4,
}
# when a name matches at several levels in one country, the first of these wins
LEVEL_PREFERENCE = [
    "group",
    "country",
    "us_state",
    "bidding_zone",
    "nuts1",
    "region",
    "nuts2",
    "itl1",
    "itl2",
    "locality",
    "us_place",
    "fr_commune",
    "nl_gemeente",
    "lau",
    "urban_centre",
    "us_cousub",
    "county",
    "nuts3",
    "us_county",
    "lad",
    "itl3",
    "admin2",
    "neighbourhood",
    "nl_wijk",
    "nl_buurt",
    "iris",
    "msoa",
    "lsoa",
    "us_tract",
    "nuts0",
]

ISO2_TO_ISO3 = {
    "AL": "ALB", "AT": "AUT", "BA": "BIH", "BE": "BEL", "BG": "BGR", "CH": "CHE", "CY": "CYP",
    "CZ": "CZE", "DE": "DEU", "DK": "DNK", "EE": "EST", "ES": "ESP", "FI": "FIN", "FR": "FRA",
    "GB": "GBR", "UK": "GBR", "GR": "GRC", "EL": "GRC", "HR": "HRV", "HU": "HUN", "IE": "IRL",
    "IS": "ISL", "IT": "ITA", "LI": "LIE", "LT": "LTU", "LU": "LUX", "LV": "LVA", "ME": "MNE",
    "MD": "MDA", "MK": "MKD", "MT": "MLT", "NL": "NLD", "NO": "NOR", "PL": "POL", "PT": "PRT",
    "RO": "ROU", "RS": "SRB", "SE": "SWE", "SI": "SVN", "SK": "SVK", "TR": "TUR", "UA": "UKR",
    "XK": "XKX", "US": "USA",
}  # fmt: skip


def norm(s: str) -> str:
    """Lower case, no accents, single spaces: the form names are matched in."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.casefold().replace("-", " ").replace("'", ""))
    return re.sub(r"\s+", " ", s).strip()


def iso3_of(code: str | None) -> str | None:
    if not code:
        return None
    c = code.upper()
    return ISO2_TO_ISO3.get(c, c if len(c) == 3 else None)


class AreaError(ValueError):
    """The area could not be built; the message says why (it goes back to the model)."""


# ---------------------------------------------------------------------- the record


@dataclass
class Area:
    area_id: str
    name: str
    level: str
    iso3: list[str]
    parents: list[str]
    geometry: dict[str, Any]  # GeoJSON (Multi)Polygon, EPSG:4326
    bbox: list[float]
    area_km2: float
    source: dict[str, str]
    how: str = ""
    figures: dict[str, Any] = field(default_factory=dict)
    display: dict[str, Any] | None = None  # a simplified outline for maps (large outlines only)

    def summary(self) -> dict[str, Any]:
        return {
            "area_id": self.area_id,
            "name": self.name,
            "level": self.level,
            "iso3": self.iso3,
            "parents": self.parents,
            "bbox": self.bbox,
            "area_km2": round(self.area_km2, 3),
            "how": self.how,
            "figures": self.figures,
            "source": self.source,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.summary(), "geometry": self.geometry, "display": self.display}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Area:
        return cls(
            area_id=d["area_id"],
            name=d["name"],
            level=d["level"],
            iso3=d.get("iso3") or [],
            parents=d.get("parents") or [],
            geometry=d["geometry"],
            bbox=d["bbox"],
            area_km2=d["area_km2"],
            source=d.get("source") or {},
            how=d.get("how", ""),
            figures=d.get("figures") or {},
            display=d.get("display"),
        )


class AreaStore:
    """Areas by id: in the results directory (this container) and in the object store (saved
    maps and later turns in another container)."""

    def __init__(self, root: Path, store: Any | None = None) -> None:
        self.root = root / "areas"
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = store

    def put(self, area: Area) -> None:
        d = area.as_dict()
        (self.root / f"{area.area_id}.json").write_text(json.dumps(d), encoding="utf-8")
        if self.store is not None:
            try:
                self.store.put_json(f"agent/areas/{area.area_id}.json", d)
            except Exception:  # the local copy serves this container
                log.warning("area not saved to the store", extra={"area_id": area.area_id})

    def get(self, area_id: str) -> Area | None:
        if not re.fullmatch(r"a_[0-9a-f]{12}", area_id):
            return None
        p = self.root / f"{area_id}.json"
        if p.exists():
            return Area.from_dict(json.loads(p.read_text(encoding="utf-8")))
        if self.store is not None:
            try:
                d = self.store.get_json(f"agent/areas/{area_id}.json")
            except Exception:
                d = None
            if d:
                p.write_text(json.dumps(d), encoding="utf-8")
                return Area.from_dict(d)
        return None


# ---------------------------------------------------------------------- outline sets


@dataclass(frozen=True)
class OutlineSet:
    """A lake table of outlines and how its columns map to an area. Expressions are SQL over
    the table's columns."""

    key: str
    table: str
    level: str  # SQL expression giving the level name
    id: str
    name: str
    iso: str  # ISO alpha-2 or alpha-3 expression
    parent: str = "NULL"
    population: str = "NULL"
    geometry: str = "geometry"
    dataset: str = ""
    licence: str = ""


# the brief-27 B1 sets share one schema: id, name, level, iso3, parent_name, population,
# geometry (GeoParquet with a bbox column), built by scripts/build_outlines.py
B1_SETS = {
    "divisions": ("Overture Maps divisions (division_area)", "ODbL 1.0 (Overture divisions)"),
    "adm2": ("geoBoundaries ADM2", "CC BY 4.0"),
    "us_places": ("US Census TIGER/Line places", "public domain"),
    "us_cousub": ("US Census TIGER/Line county subdivisions", "public domain"),
    "us_tracts": ("US Census TIGER/Line tracts", "public domain"),
    "uk_ons": ("ONS boundaries (ITL, LAD, MSOA, LSOA 2021)", "OGL v3"),
    "fr_iris": ("IGN / INSEE communes and IRIS", "Licence Ouverte 2.0"),
    "nl_cbs": ("CBS wijk- en buurtkaart (gemeenten, wijken, buurten)", "CC BY 4.0"),
    "small_areas": ("national census small areas (docs/research/small-area-energy.md)", "per row"),
    "urban_centres": ("GHS Urban Centre Database R2024", "CC BY 4.0"),
}

OUTLINE_SETS: list[OutlineSet] = [
    OutlineSet(
        "nuts",
        "shapes.nuts",
        "'nuts' || CAST(level AS VARCHAR)",
        "nuts_id",
        "name",
        "iso2",
        dataset="Eurostat GISCO NUTS 2024 (1:20M)",
        licence="© EuroGeographics for the administrative boundaries",
    ),
    OutlineSet(
        "admin1",
        "shapes.admin1",
        "'region'",
        "admin1_id",
        "name",
        "iso3",
        dataset="geoBoundaries CGAZ ADM1",
        licence="CC BY 4.0",
    ),
    OutlineSet(
        "zones",
        "shapes.bidding_zones",
        "'bidding_zone'",
        "zone",
        "zone",
        "iso2",
        dataset="bidding zones built from NUTS 3 regions (scripts/build_shapes.py)",
        licence="© EuroGeographics for the administrative boundaries",
    ),
    *(
        OutlineSet(
            key,
            f"outlines.{key}",
            "level",
            "id",
            "name",
            "iso3",
            parent="parent_name",
            population="population",
            dataset=ds,
            licence=lic,
        )
        for key, (ds, lic) in B1_SETS.items()
    ),
]
SET_BY_KEY = {s.key: s for s in OUTLINE_SETS}


@dataclass
class Candidate:
    ref: str  # "<set>:<id>"
    name: str
    level: str
    iso3: list[str]
    parent: str | None
    population: float | None
    bbox: list[float] | None
    source: dict[str, str]
    match: int = 0  # 0 exact, 1 code, 2 prefix
    point: list[float] | None = None  # point-only places (GeoNames cities)
    outline: bool = True

    def as_dict(self) -> dict[str, Any]:
        d = {
            "ref": self.ref,
            "name": self.name,
            "level": self.level,
            "iso3": self.iso3,
            "parent": self.parent,
            "population": self.population,
            "bbox": self.bbox,
            "outline": self.outline,
            "source": self.source["dataset"],
        }
        if self.point:
            d["point"] = self.point
        return d


def _bbox_of_flat(polys: list[list[list[float]]]) -> list[float]:
    xs = [v for p in polys for v in p[0][0::2]]
    ys = [v for p in polys for v in p[0][1::2]]
    return [min(xs), min(ys), max(xs), max(ys)]


def flat_to_geojson(polys: list[list[list[float]]]) -> dict[str, Any]:
    def ring(r: list[float]) -> list[list[float]]:
        pts = [[r[i], r[i + 1]] for i in range(0, len(r) - 1, 2)]
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return pts

    return {
        "type": "MultiPolygon",
        "coordinates": [[ring(r) for r in p if len(r) >= 6] for p in polys if p and len(p[0]) >= 6],
    }


class Areas:
    """Builds areas: searches outlines, unions, buffers and intersections in DuckDB spatial."""

    def __init__(self, lake: Any, gazetteer: Gazetteer, agent_dir: Path, store: AreaStore) -> None:
        self.lake = lake
        self.gaz = gazetteer
        self.agent_dir = agent_dir
        self.store = store

    # ---------------------------------------------------------------- local outlines
    @cached_property
    def groups(self) -> dict[str, dict[str, Any]]:
        p = self.agent_dir / "areas" / "groups.yaml"
        if not p.exists():
            return {}
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("groups") or {}

    @cached_property
    def us_counties(self) -> list[dict[str, Any]]:
        p = self.gaz.public / "us" / "counties.json"
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8"))["counties"]

    @cached_property
    def country_names(self) -> dict[str, str]:
        """ISO alpha-3 -> name (Europe's outlines, then the world's)."""
        out = {p.codes["iso3"]: p.name for p in self.gaz.world}
        for p in self.gaz.europe:
            i3 = iso3_of(p.codes["iso2"])
            if i3:
                out[i3] = p.name
        out.setdefault("USA", "United States")
        return out

    @cached_property
    def us_state_names(self) -> dict[str, str]:
        return {p.codes["state"]: p.name for p in self.gaz.us_states}

    def tables(self) -> set[str]:
        try:
            return set(self.lake.tables())
        except Exception:
            return set()

    # ---------------------------------------------------------------- search
    def search(
        self,
        text: str,
        *,
        level: str | None = None,
        view: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[Candidate]:
        """Candidates for a name, best first. 'Name, qualifier' filters by country or parent."""
        raw = text.strip()
        qual = None
        m = re.match(r"^(.*?)\s*(?:,|\(|\bin\b)\s*([^,()]+?)\)?\s*$", raw)
        if m and m.group(1).strip():
            raw, qual = m.group(1).strip(), norm(m.group(2))
        q = norm(raw)
        if not q:
            return []
        out = self._local(q) + self._lake(q)
        if qual:
            out = [c for c in out if self._qualifies(c, qual)]
        want = LEVEL_WORDS.get(level or "", LEVEL_CLASS.get(level or "", -1))
        exact_level = level if level in LEVEL_CLASS else None
        in_view = self._in_view(view)

        def rank(c: Candidate) -> tuple:
            lv = (
                0
                if (exact_level and c.level == exact_level)
                or (want >= 0 and LEVEL_CLASS.get(c.level, 5) == want)
                else 1
            )
            pref = (
                LEVEL_PREFERENCE.index(c.level)
                if c.level in LEVEL_PREFERENCE
                else len(LEVEL_PREFERENCE)
            )
            seen = 0 if in_view(c) else 1
            return (
                c.match,
                lv if (want >= 0 or exact_level) else 0,
                0 if c.outline else 1,  # an outline before a point-only place of the same name
                seen,
                -(c.population or 0),
                pref,
            )

        out.sort(key=rank)
        # one candidate per (name, country, parent): the preferred level among equal outlines
        best: dict[tuple, Candidate] = {}
        for c in out:
            k = (norm(c.name), tuple(c.iso3), norm(c.parent or ""))
            if k in best:
                b = best[k]
                if LEVEL_CLASS.get(b.level) == LEVEL_CLASS.get(c.level) or not (want >= 0):
                    continue
            best.setdefault(k, c)
        # a point-only place where the same name has an outline in the same country is that place
        outlined = {(norm(c.name), tuple(c.iso3)) for c in best.values() if c.outline}
        ranked = sorted(
            (
                c
                for c in best.values()
                if c.outline or (norm(c.name), tuple(c.iso3)) not in outlined
            ),
            key=rank,
        )
        return ranked[:limit]

    def _qualifies(self, c: Candidate, qual: str) -> bool:
        """'Paris, Texas', 'Limburg (NL)', 'Springfield in Illinois': the qualifier names the
        candidate's parent, country (name or code) or US state (name or code)."""
        words = {norm(c.parent or "")}
        for i3 in c.iso3:
            words |= {i3.lower(), norm(self.country_names.get(i3, ""))}
            words |= {k.lower() for k, v in ISO2_TO_ISO3.items() if v == i3}
        for code, n in self.us_state_names.items():
            if c.parent and norm(n) == norm(c.parent):
                words.add(code.lower())
        return qual in words or any(qual and qual in w for w in words if len(qual) > 3)

    @staticmethod
    def _in_view(view: dict[str, Any] | None):  # noqa: ANN205
        view = view or {}
        countries = {iso3_of(c) for c in (view.get("area") or [])}
        bounds = (view.get("camera") or {}).get("bounds")

        def test(c: Candidate) -> bool:
            if countries and set(c.iso3) & countries:
                return True
            if bounds and c.bbox:
                cx, cy = (c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2
                return bounds[0] <= cx <= bounds[2] and bounds[1] <= cy <= bounds[3]
            return False

        return test

    def _local(self, q: str) -> list[Candidate]:
        out: list[Candidate] = []

        def match(name: str, codes: list[str] = ()) -> int | None:  # type: ignore[assignment]
            n = norm(name)
            if q == n:
                return 0
            if q in {c.lower() for c in codes if c}:
                return 1
            return None

        if q in ("world", "the world", "global", "whole world", "earth"):
            out.append(
                Candidate(
                    "world:world",
                    "World",
                    "world",
                    [],
                    None,
                    None,
                    [-180, -90, 180, 90],
                    {"dataset": "the whole globe", "licence": "none"},
                )
            )
        for key, g in self.groups.items():
            names = [norm(a) for a in g.get("aliases", [])] + [norm(g["name"]), key]
            if q in names:
                out.append(
                    Candidate(
                        f"group:{key}",
                        g["name"],
                        "group",
                        list(g["members"]),
                        None,
                        None,
                        None,
                        {"dataset": f"group membership: {g.get('source', '')}", "licence": "facts"},
                    )
                )
        for p in self.gaz.europe:
            i3 = iso3_of(p.codes["iso2"]) or p.codes["iso2"]
            r = match(p.name, [p.codes["iso2"], i3])
            if r is not None:
                out.append(
                    Candidate(
                        f"europe:{p.codes['iso2']}",
                        p.name,
                        "country",
                        [i3],
                        None,
                        None,
                        p.bbox,
                        {"dataset": p.source, "licence": "see source"},
                        r,
                    )
                )
        eu3 = {iso3_of(p.codes["iso2"]) for p in self.gaz.europe}
        for p in self.gaz.world:
            i3 = p.codes["iso3"]
            if i3 in eu3:
                continue
            r = match(p.name, [i3])
            if (
                r is None
                and i3 == "USA"
                and q in ("us", "usa", "united states of america", "america")
            ):
                r = 1
            if r is not None:
                out.append(
                    Candidate(
                        f"country:{i3}",
                        p.name,
                        "country",
                        [i3],
                        None,
                        None,
                        p.bbox,
                        {
                            "dataset": "world outlines (frontend/public/data/eu/world.json)",
                            "licence": "see source",
                        },
                        r,
                    )
                )
        for p in self.gaz.us_states:
            r = match(p.name, [p.codes["state"]])
            if r is not None:
                out.append(
                    Candidate(
                        f"us_state:{p.codes['state']}",
                        p.name,
                        "us_state",
                        ["USA"],
                        "United States",
                        None,
                        p.bbox,
                        {"dataset": p.source, "licence": "public domain"},
                        r,
                    )
                )
        qc = re.sub(r" (county|parish|borough|census area)$", "", q)
        for c in self.us_counties:
            if norm(c["name"]) == qc:
                st = self.us_state_names.get(c["state"], c["state"])
                out.append(
                    Candidate(
                        f"us_county:{c['code']}",
                        f"{c['name']} County",
                        "us_county",
                        ["USA"],
                        st,
                        None,
                        _bbox_of_flat(c["polygons"]),
                        {
                            "dataset": "US Census cartographic boundary file, counties 1:20m, 2020",
                            "licence": "public domain",
                        },
                        0 if qc != q else 2,  # "Texas" is the state; "Texas County" the county
                    )
                )
        for p in self.gaz.zones:
            r = match(p.name, [p.codes["zone"]])
            if r is not None:
                out.append(
                    Candidate(
                        f"zones:{p.codes['zone']}",
                        p.name,
                        "bidding_zone",
                        [iso3_of(p.codes["iso2"]) or p.codes["iso2"]],
                        None,
                        None,
                        p.bbox,
                        {
                            "dataset": SET_BY_KEY["zones"].dataset,
                            "licence": SET_BY_KEY["zones"].licence,
                        },
                        r,
                        outline="shapes.bidding_zones" in self.tables(),
                    )
                )
        for p in self.gaz.cities:
            if norm(p.name) == q:
                pop = re.search(r"population (\d+)", p.source)
                i3 = iso3_of(p.codes.get("iso2"))
                out.append(
                    Candidate(
                        f"city:{p.name}|{p.codes.get('iso2')}|{p.centre[0]},{p.centre[1]}",
                        p.name,
                        "city",
                        [i3] if i3 else [],
                        self.country_names.get(i3 or "", None),
                        float(pop.group(1)) if pop else None,
                        None,
                        {
                            "dataset": "GeoNames cities15000 (CC BY 4.0): a point, no outline",
                            "licence": "CC BY 4.0",
                        },
                        point=p.centre,
                        outline=False,
                    )
                )
        return out

    def _lake(self, q: str) -> list[Candidate]:
        tables = self.tables()
        out: list[Candidate] = []
        sets = [s for s in OUTLINE_SETS if s.table in tables and s.key != "zones"]
        if not sets:
            return out
        cur = self.lake.cursor()
        for s in sets:
            # the same normal form as norm(): no accents or apostrophes, other signs as spaces
            nn = (
                f"trim(regexp_replace(replace(lower(strip_accents({s.name})), chr(39), ''), "
                "'[^a-z0-9]+', ' ', 'g'))"
            )
            sql = f"""
                SELECT CAST({s.id} AS VARCHAR), {s.name}, {s.level}, {s.iso}, {s.parent},
                       {s.population}, ST_XMin({s.geometry}), ST_YMin({s.geometry}),
                       ST_XMax({s.geometry}), ST_YMax({s.geometry}),
                       CASE WHEN {nn} = $q THEN 0
                            WHEN lower(CAST({s.id} AS VARCHAR)) = $q THEN 1 ELSE 2 END AS r
                FROM {s.table}
                WHERE {nn} = $q OR lower(CAST({s.id} AS VARCHAR)) = $q
                LIMIT 200"""
            try:
                rows = cur.execute(sql, {"q": q}).fetchall()
            except Exception as e:
                log.warning("outline search failed", extra={"set": s.key, "error": str(e)[:200]})
                continue
            for rid, name, lv, iso, parent, pop, x0, y0, x1, y1, r in rows:
                i3 = iso3_of(iso)
                out.append(
                    Candidate(
                        f"{s.key}:{rid}",
                        name,
                        lv,
                        [i3] if i3 else [],
                        parent or self.country_names.get(i3 or ""),
                        float(pop) if pop is not None else None,
                        [x0, y0, x1, y1],
                        {"dataset": s.dataset, "licence": s.licence},
                        r,
                    )
                )
        return out

    # ---------------------------------------------------------------- geometry
    def _cur(self) -> Any:
        cur = self.lake.cursor()
        try:
            cur.execute("SELECT ST_Point(0, 0)")
        except Exception as e:
            raise AreaError("the spatial extension is not loaded in this service") from e
        return cur

    def geometry_of(self, ref: str) -> str:
        """GeoJSON text of a candidate's outline (by its ref)."""
        kind, _, key = ref.partition(":")
        if kind == "world":
            ring = [[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]
            return json.dumps({"type": "Polygon", "coordinates": [ring]})
        if kind == "europe":
            p = next(p for p in self.gaz.europe if p.codes["iso2"] == key)
            return json.dumps(flat_to_geojson(p.polygons))
        if kind == "country":
            p = next(p for p in self.gaz.world if p.codes["iso3"] == key)
            return json.dumps(flat_to_geojson(p.polygons))
        if kind == "us_state":
            p = next(p for p in self.gaz.us_states if p.codes["state"] == key)
            return json.dumps(flat_to_geojson(p.polygons))
        if kind == "us_county":
            c = next(c for c in self.us_counties if c["code"] == key)
            return json.dumps(flat_to_geojson(c["polygons"]))
        if kind in SET_BY_KEY:
            s = SET_BY_KEY[kind]
            if s.table not in self.tables():
                raise AreaError(f"the outline table {s.table} is not in this service's lake")
            row = (
                self._cur()
                .execute(
                    f"SELECT ST_AsGeoJSON({s.geometry}) FROM {s.table} "
                    f"WHERE CAST({s.id} AS VARCHAR) = ? LIMIT 1",
                    [key],
                )
                .fetchone()
            )
            if not row:
                raise AreaError(f"no outline {ref}")
            return row[0]
        raise AreaError(f"unknown outline reference {ref!r}")

    def make(
        self,
        geojson: str,
        *,
        name: str,
        level: str,
        iso3: list[str],
        parents: list[str],
        source: dict[str, str],
        how: str,
    ) -> Area:
        """Validate an outline, compute its id, bbox and geodesic area, and keep it."""
        cur = self._cur()
        row = cur.execute(
            """
            WITH g AS (SELECT ST_CollectionExtract(ST_MakeValid(ST_GeomFromGeoJSON($g)), 3) AS g)
            SELECT ST_AsGeoJSON(g), sha256(ST_AsHEXWKB(ST_Normalize(g))), ST_XMin(g), ST_YMin(g),
                   ST_XMax(g), ST_YMax(g), ST_Area_Spheroid(g) / 1e6, ST_NPoints(g),
                   ST_IsEmpty(g)
            FROM g""",
            {"g": geojson},
        ).fetchone()
        if row is None or row[8]:
            raise AreaError(f"the outline of {name} is empty")
        gj, digest, x0, y0, x1, y1, km2, npts, _ = row
        if level == "world":  # the spheroid formula does not take the whole globe as one ring
            km2 = WGS84_SURFACE_KM2
        display = None
        if npts > 20_000:
            tol = max(x1 - x0, y1 - y0) / 4000
            d = cur.execute(
                "SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(ST_GeomFromGeoJSON($g), $t))",
                {"g": gj, "t": tol},
            ).fetchone()
            display = json.loads(d[0]) if d else None
        area = Area(
            area_id="a_" + digest[:12],
            name=name,
            level=level,
            iso3=sorted({i for i in iso3 if i}),
            parents=parents,
            geometry=json.loads(gj),
            bbox=[round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
            area_km2=float(km2),
            source=source,
            how=how,
            figures={
                "area_km2": {
                    "value": round(float(km2), 3),
                    "unit": "km²",
                    "how": "geodesic area of the outline on the WGS84 ellipsoid (computed)",
                }
            },
            display=display,
        )
        self.store.put(area)
        return area

    def from_candidate(self, c: Candidate) -> Area:
        if c.level == "group":
            key = c.ref.split(":", 1)[1]
            g = self.groups[key]
            return self.union(
                [self.country(i3) for i3 in g["members"]],
                name=g["name"],
                level="group",
                source={
                    "dataset": f"union of member outlines; membership: {g.get('source', '')}",
                    "licence": "see members",
                },
            )
        if not c.outline:
            raise AreaError(f"{c.name} has no outline here ({c.source['dataset']})")
        gj = self.geometry_of(c.ref)
        parents = [p for p in [c.parent] if p]
        for i3 in c.iso3:
            n = self.country_names.get(i3)
            if n and n not in parents and c.level not in ("country", "nuts0"):
                parents.append(n)
        return self.make(
            gj,
            name=c.name,
            level=c.level,
            iso3=c.iso3,
            parents=parents,
            source=c.source,
            how=f"outline {c.ref} from {c.source['dataset']}",
        )

    def country(self, iso3: str) -> Area:
        i2 = next((k for k, v in ISO2_TO_ISO3.items() if v == iso3 and k not in ("UK", "EL")), None)
        p = next((p for p in self.gaz.europe if p.codes["iso2"] == i2), None) if i2 else None
        if p is not None:
            c = Candidate(
                f"europe:{i2}",
                p.name,
                "country",
                [iso3],
                None,
                None,
                p.bbox,
                {"dataset": p.source, "licence": "see source"},
            )
            return self.from_candidate(c)
        if "shapes.nuts" in self.tables() and i2:
            row = (
                self._cur()
                .execute("SELECT name FROM shapes.nuts WHERE level = 0 AND iso2 = ?", [i2])
                .fetchone()
            )
            if row:
                s = SET_BY_KEY["nuts"]
                return self.from_candidate(
                    Candidate(
                        f"nuts:{'EL' if i2 == 'GR' else 'UK' if i2 == 'GB' else i2}",
                        row[0],
                        "country",
                        [iso3],
                        None,
                        None,
                        None,
                        {"dataset": s.dataset, "licence": s.licence},
                    )
                )
        w = next((p for p in self.gaz.world if p.codes["iso3"] == iso3), None)
        if w is None:
            raise AreaError(f"no outline for country {iso3}")
        return self.from_candidate(
            Candidate(
                f"country:{iso3}",
                w.name,
                "country",
                [iso3],
                None,
                None,
                w.bbox,
                {
                    "dataset": "world outlines (frontend/public/data/eu/world.json)",
                    "licence": "see source",
                },
            )
        )

    def union(
        self, areas: list[Area], *, name: str, level: str = "group", source: dict | None = None
    ) -> Area:
        if len(areas) == 1:
            return areas[0]
        cur = self._cur()
        gj = cur.execute(
            "SELECT ST_AsGeoJSON(ST_Union_Agg(ST_GeomFromGeoJSON(g))) FROM unnest($gs) t(g)",
            {"gs": [json.dumps(a.geometry) for a in areas]},
        ).fetchone()[0]
        return self.make(
            gj,
            name=name,
            level=level,
            iso3=[i for a in areas for i in a.iso3],
            parents=sorted({p for a in areas for p in a.parents}),
            source=source
            or {
                "dataset": "union of: " + "; ".join(a.source.get("dataset", "") for a in areas),
                "licence": "see each part",
            },
            how="union of " + ", ".join(f"{a.name} ({a.area_id})" for a in areas),
        )

    def buffer(self, geojson: str, km: float, *, centre: tuple[float, float] | None = None) -> str:
        """The outline grown by `km`, computed in an azimuthal equidistant projection centred on
        the shape (distances from the centre are true; a circle is exact)."""
        cur = self._cur()
        if centre is None:
            c = cur.execute(
                "SELECT ST_X(ST_Centroid(ST_GeomFromGeoJSON($g))), "
                "ST_Y(ST_Centroid(ST_GeomFromGeoJSON($g)))",
                {"g": geojson},
            ).fetchone()
            centre = (c[0], c[1])
        proj = f"+proj=aeqd +lat_0={centre[1]:.6f} +lon_0={centre[0]:.6f} +datum=WGS84 +units=m"
        return cur.execute(
            "SELECT ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform(ST_GeomFromGeoJSON($g), "
            "'EPSG:4326', $p), $m, 24), $p, 'EPSG:4326'))",
            {"g": geojson, "p": proj, "m": km * 1000.0},
        ).fetchone()[0]

    def intersect(self, a: Area, b: Area) -> Area:
        gj = (
            self._cur()
            .execute(
                "SELECT ST_AsGeoJSON(ST_Intersection(ST_GeomFromGeoJSON($a), "
                "ST_GeomFromGeoJSON($b)))",
                {"a": json.dumps(a.geometry), "b": json.dumps(b.geometry)},
            )
            .fetchone()[0]
        )
        return self.make(
            gj,
            name=f"{a.name} ∩ {b.name}",
            level="polygon",
            iso3=sorted(set(a.iso3) & set(b.iso3)) or a.iso3,
            parents=[a.name, b.name],
            source={
                "dataset": f"{a.source.get('dataset')}; {b.source.get('dataset')}",
                "licence": "see each part",
            },
            how=f"intersection of {a.name} ({a.area_id}) and {b.name} ({b.area_id})",
        )

    def circle(self, lon: float, lat: float, km: float, name: str | None = None) -> Area:
        gj = self.buffer(
            json.dumps({"type": "Point", "coordinates": [lon, lat]}), km, centre=(lon, lat)
        )
        where = self.gaz.locate(lon, lat)
        iso = where["codes"].get("iso3") or iso3_of(where["codes"].get("iso2"))
        return self.make(
            gj,
            name=f"{km:g} km around {name or f'{lat:.3f}, {lon:.3f}'}",
            level="circle",
            iso3=[iso] if iso else [],
            parents=[where["name"]] if where["name"] else [],
            source={"dataset": "a circle around a point (computed)", "licence": "none"},
            how=f"circle of radius {km:g} km around [{lon:.5f}, {lat:.5f}] (geodesic, 96 segments)",
        )

    def polygon(self, rings: list[list[list[float]]], name: str, level: str = "polygon") -> Area:
        polys = rings if rings and isinstance(rings[0][0][0], list) else [rings]
        gj = json.dumps({"type": "MultiPolygon", "coordinates": polys})
        lon = sum(p[0] for p in polys[0][0]) / len(polys[0][0])
        lat = sum(p[1] for p in polys[0][0]) / len(polys[0][0])
        where = self.gaz.locate(lon, lat)
        iso = where["codes"].get("iso3") or iso3_of(where["codes"].get("iso2"))
        return self.make(
            gj,
            name=name,
            level=level,
            iso3=[iso] if iso else [],
            parents=[where["name"]] if where["name"] else [],
            source={
                "dataset": "drawn on the map" if level == "polygon" else "the map on screen",
                "licence": "none",
            },
            how="outline as drawn" if level == "polygon" else "the camera's bounds",
        )


def area_ids_in(sql: str) -> list[str]:
    return sorted(set(AREA_ID.findall(sql)))
