"""Room to connect in one schema for the EU-27, the UK and the US (brief 23).

    python scripts/build_connect_harmonised.py [--osm] [--lake lake-out] [--upload]

Reads the per-operator files the app already has (frontend/public/data/eu/connect.json and
connect/<cc>.json, built by fetch_connect_here.py, build_connect_eu.py, build_connect_more.py and
the brief-23 builders that write connect/<cc>.json in the same format) and writes every published
record as one row of frontend/public/data/eu/connect/harmonised.json:

  cc, operator, level           ISO alpha-2 (US: US-<ISO/RTO or utility>), operator, transmission
                                or distribution
  id, name                      the operator's node, substation or area id and name
  kind                          node (a point) or area (an outline; `polygon`, label point lon/lat)
  lon, lat                      as published; a node without coordinates is matched to an
                                OpenStreetMap substation by name only when the match is unique
                                (--osm asks Overpass; `matched` counts them per operator)
  kv                            voltage as published
  mw_gen, mw_load               free capacity for new generation / new demand, MW as published
  mva_gen, mva_load             the same where the operator publishes MVA or kVA (not converted:
                                that would need a power factor)
  mw_queue                      MW waiting (registers and queues), as published or summed per
                                node (computed, said per operator)
  class, class_load             available | limited | queue | none for generation and demand,
                                the operator's own classes mapped one to one (MAPPINGS below); an
                                operator that publishes MW only: more than 0 MW -> available,
                                0 MW -> none (no other threshold)
  as_of, source, url, licence   per operator (the `operators` table; rows point to it)

Nothing is estimated. The file stores rows as arrays (`fields`) with an operator index; the lake
table connect/harmonised (Parquet on R2) has one full row per record.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EU = ROOT / "frontend" / "public" / "data" / "eu"
OUT = EU / "connect" / "harmonised.json"
SCRIPT = "scripts/build_connect_harmonised.py"
CLASSES = ["available", "limited", "queue", "none"]
FIELDS = [
    "op", "id", "name", "kind", "lon", "lat", "kv", "mw_gen", "mw_load", "mva_gen", "mva_load",
    "mw_queue", "class", "class_load", "polygon",
]  # fmt: skip
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OSM_UA = {
    "User-Agent": "InfraAtlas/0.7 (+https://github.com/Daniyal-arch/Energy_Grid)",
    "Accept": "*/*",
}
OSM_CACHE = w7.TMP / "osm_substations"

# the operator's own classes -> ours, per operator (documented in docs/DATA_SOURCES.md)
MAPPINGS: dict[str, dict[str, str]] = {
    "NL": {
        "0 capacity available, no queue": "available", "1 capacity limited, no queue": "limited",
        "2 under study, with a queue": "queue", "3 shortage of capacity, with a queue": "none",
    },
    "CZ": {"suitable": "available", "conditionally suitable": "limited", "not suitable": "none"},
    "DE-TransnetBW": {"medium-term": "limited", "long-term": "none", "not available": "none"},
    "AT": {"MW free > 0": "available", "0 MW, flexible connection possible": "limited", "0 MW, no flexible connection": "none"},
    "BG": {"connection possible": "available", "grid expansion needed first": "none"},
    "EE": {"expandable (type A)": "available", "not expandable (type B)": "none"},
    "GB-TEC": {"projects holding or seeking entry capacity, not all connected": "queue"},
    "IT": {"requests to connect (Econnextion)": "queue"},
    "PL": {"requests in the Art. 7(8l) list": "queue", "switchgear without a free connection bay": "none"},
}  # fmt: skip
MW_RULE = "MW only: more than 0 MW free -> available, 0 MW -> none"


def mw_class(v: float | None) -> str | None:
    """The class of an operator that publishes MW only (no threshold of ours beyond zero)."""
    if v is None:
        return None
    return "available" if v > 0 else "none"


def num(v: object) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else w7.number(v)


def maxed(vals: list[object]) -> float | None:
    xs = [x for x in (num(v) for v in vals) if x is not None]
    return max(xs) if xs else None


# ---------------------------------------------------------------- name matching (OpenStreetMap)

STOP = {
    "uw", "umspannwerk", "umspannanlage", "station", "substation", "subestacion", "subestação",
    "subestacao", "se", "set", "st", "de", "del", "la", "el", "los", "las", "do", "da", "dos",
    "gsp", "kv", "rozdzielnia", "gpz", "sous", "poste", "s", "stn", "unterwerk", "schaltanlage",
    "schaltwerk", "trafostation", "at", "mt", "rnd",
}  # fmt: skip


def norm(name: str) -> str:
    """Lower case, no accents, no voltage or station words: 'UW Mattersburg 220 kV' -> 'mattersburg'."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    words = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in STOP and not t.isdigit()]
    return " ".join(words)


def osm_substations(cc: str, fetch: bool) -> list[dict]:
    """OpenStreetMap substations with a name in the country (cached; Overpass with --osm)."""
    path = OSM_CACHE / f"{cc}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if not fetch:
        return []
    import httpx

    q = (f'[out:json][timeout:400];area["ISO3166-1"="{cc}"][admin_level=2]->.a;'
         'nwr["power"="substation"]["name"](area.a);out center tags;')  # fmt: skip
    for i, url in enumerate(OVERPASS):
        try:
            r = httpx.post(url, data={"data": q}, headers=OSM_UA, timeout=440)
            r.raise_for_status()
            els = r.json().get("elements") or []
            if not els:
                raise ValueError("no elements")
            subs = [
                {"name": e["tags"]["name"], "lon": e.get("lon", e.get("center", {}).get("lon")),
                 "lat": e.get("lat", e.get("center", {}).get("lat")), "osm": f"{e['type']}/{e['id']}"}
                for e in els
            ]  # fmt: skip
            OSM_CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(subs), encoding="utf-8")
            print(f"  OSM {cc}: {len(subs)} named substations", flush=True)
            return subs
        except Exception as e:  # noqa: BLE001 - the next server
            print(f"  OSM {cc} {url}: {type(e).__name__} {str(e)[:100]}", flush=True)
            time.sleep(10 * (i + 1))
    return []


def matcher(cc: str, fetch: bool) -> Callable[[str], tuple[float, float] | None]:
    """name -> (lon, lat) of the one OpenStreetMap substation with that normalised name."""
    index: dict[str, list[tuple[float, float]]] = {}
    for s in osm_substations(cc, fetch):
        if s["lon"] is not None:
            index.setdefault(norm(s["name"]), []).append((round(s["lon"], 5), round(s["lat"], 5)))

    def match(name: str) -> tuple[float, float] | None:
        key = norm(name)
        hits = index.get(key) if key else None
        # unique: one name, or several OSM objects of that name within ~1 km (one site mapped twice)
        if hits and all(
            abs(h[0] - hits[0][0]) < 0.015 and abs(h[1] - hits[0][1]) < 0.01 for h in hits
        ):
            return hits[0]
        return None

    return match


# ---------------------------------------------------------------- the operators


class Build:
    def __init__(self, osm: bool) -> None:
        self.osm = osm
        self.operators: list[dict] = []
        self.rows: list[list] = []
        self.matchers: dict[str, Callable[[str], tuple[float, float] | None]] = {}

    def op(self, cc: str, operator: str, level: str, *, source: str, url: str, licence: str,
           as_of: str | None, mapping: str, note: str = "") -> int:  # fmt: skip
        self.operators.append({"cc": cc, "operator": operator, "level": level, "source": source, "url": url,
                               "licence": licence, "as_of": as_of, "mapping": mapping, "note": note,
                               "rows": 0, "placed": 0, "matched": 0})  # fmt: skip
        return len(self.operators) - 1

    def row(self, k: int, *, id: str | None = None, name: str, kind: str = "node",
            lon: float | None = None, lat: float | None = None, kv: float | None = None,
            mw_gen: float | None = None, mw_load: float | None = None, mva_gen: float | None = None,
            mva_load: float | None = None, mw_queue: float | None = None, cls: str | None = None,
            cls_load: str | None = None, polygon: list | None = None, match: bool = False) -> None:  # fmt: skip
        o = self.operators[k]
        if lon is None and match and kind == "node":
            cc = o["cc"]
            if cc not in self.matchers:
                self.matchers[cc] = matcher(cc, self.osm)
            at = self.matchers[cc](name)
            if at:
                lon, lat = at
                o["matched"] += 1
        for c in (cls, cls_load):
            assert c is None or c in CLASSES, c
        r = {"op": k, "id": id, "name": name, "kind": kind, "lon": lon, "lat": lat, "kv": kv,
             "mw_gen": mw_gen, "mw_load": mw_load, "mva_gen": mva_gen, "mva_load": mva_load,
             "mw_queue": mw_queue, "class": cls, "class_load": cls_load, "polygon": polygon}  # fmt: skip
        self.rows.append([r[f] for f in FIELDS])
        o["rows"] += 1
        o["placed"] += 1 if lon is not None else 0


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def flat_polygons(g: list) -> list[list[list[float]]]:
    """Any of the files' outlines as [polygon][ring] with flat lon/lat rings: NL [poly][ring][[x, y]],
    SE [poly][ring][x, y, ...], IT [ring][x, y, ...]."""

    def depth(x: object) -> int:
        n = 0
        while isinstance(x, list) and x:
            x, n = x[0], n + 1
        return n

    d = depth(g)
    if d == 4:  # [poly][ring][point][xy]
        return [[[c for pt in ring for c in pt] for ring in poly] for poly in g]
    if d == 3:  # [poly][ring][flat]
        return g
    if d == 2:  # [ring][flat]
        return [g]
    raise ValueError(f"outline depth {d}")


def ring_centre(polygons: list[list[list[float]]]) -> tuple[float, float]:
    """Label point of an area: the middle of the bounding box of its largest ring (computed)."""
    ring = max((r[0] for r in polygons), key=len)
    xs, ys = ring[0::2], ring[1::2]
    return round((min(xs) + max(xs)) / 2, 4), round((min(ys) + max(ys)) / 2, 4)


def from_here(b: Build) -> None:
    """connect.json: GB TEC register, NL capacity map, ES REE transmission nodes."""
    d = load(EU / "connect.json")
    if not d:
        return
    g = d.get("gb")
    if g:
        k = b.op("GB", "NESO (TEC register)", "transmission", source=g["source"],
                 url="https://www.neso.energy/data-portal/transmission-entry-capacity-tec-register",
                 licence="NESO Open Data Licence", as_of=g.get("date"),
                 mapping="a site with MW waiting (cumulative capacity - MW connected, summed per site, computed) -> queue",
                 note="A register of projects, not free capacity: sites with nothing waiting are left out")  # fmt: skip
        waiting: dict[int, float] = {}
        for p in g["projects"]:
            waiting[p[1]] = waiting.get(p[1], 0) + max(0.0, (p[2] or 0) - (p[3] or 0))
        for i, mw in waiting.items():
            if mw > 0:
                s = g["sites"][i]
                b.row(k, name=s[0], lon=s[1], lat=s[2], mw_queue=round(mw, 1), cls="queue")
    nl = d.get("nl")
    if nl:
        k = b.op("NL", "Netbeheer Nederland (regional operators)", "distribution", source=nl["source"],
                 url="https://capaciteitskaart.netbeheernederland.nl", licence="Esri Nederland terms of use",
                 as_of=None, mapping="; ".join(f"{a} -> {c}" for a, c in MAPPINGS["NL"].items()))  # fmt: skip
        for a in nl["areas"]:
            poly = flat_polygons(a["polygons"])
            lon, lat = ring_centre(poly)
            b.row(k, id=a["id"], name=f"{a['name']} ({a['operator']})", kind="area", lon=lon, lat=lat,
                  mw_queue=(a.get("queue_feedin_mw") or 0) or None,
                  cls=list(MAPPINGS["NL"].values())[a["feedin"]], cls_load=list(MAPPINGS["NL"].values())[a["offtake"]],
                  polygon=poly)  # fmt: skip
    es = d.get("es")
    if es:
        k = b.op("ES", "Red Eléctrica (transmission nodes)", "transmission", source=es["source"], url=es["url"],
                 licence="REE terms of use (reuse with the source named)", as_of=es.get("date"),
                 mapping=f"{MW_RULE} (demand: CEP with ride-through, the first column)",
                 note="No coordinates published: nodes matched to OpenStreetMap by name where unique")  # fmt: skip
        for n in es["nodes"]:
            kv = (
                num(re.findall(r"(\d{2,3})\s*$", n[0])[0])
                if re.search(r"\d{2,3}\s*$", n[0])
                else None
            )
            b.row(k, id=n[1], name=n[0], kv=kv, mw_load=n[3], cls_load=mw_class(n[3]), match=True)


def from_eu_format(b: Build, cc: str, file: str, operator: str, level: str) -> None:
    """connect/<cc>.json (build_connect_eu.py format): points, areas or a table without positions."""
    d = load(EU / "connect" / f"{file}.json")
    if not d:
        return
    cols = [c[0] for c in d["columns"]]
    idx = {c: i for i, c in enumerate(cols)}
    labels = d.get("classes", [])

    def val(v: list, *names: str) -> float | None:
        return maxed([v[idx[n]] for n in names if n in idx])

    spec: dict[str, Callable[[list], dict]] = {
        "AT": lambda v: {"mw_gen": val(v, "feedin_mw"), "mw_load": val(v, "offtake_mw")},
        "DK": lambda v: {"mw_gen": val(v, "production_mw"), "mw_load": val(v, "consumption_mw")},
        "SE": lambda v: {"mw_gen": val(v, "feedin_2026_mw"), "mw_load": val(v, "offtake_2026_mw")},
        "LT": lambda v: {"mw_gen": val(v, "solar_mw", "wind_mw")},
        "LU": lambda v: {"mw_gen": val(v, *[c for c in cols if c.startswith("available_")])},
        "MT": lambda v: {"mva_gen": round(v[idx["res_kwp"]] / 1000, 3) if num(v[idx["res_kwp"]]) is not None else None,
                         "mva_load": round(v[idx["load_kva"]] / 1000, 3) if num(v[idx["load_kva"]]) is not None else None},
        "ES-DSO": lambda v: {"mw_gen": val(v, "available_mw"), "mw_queue": val(v, "pending_mw")},
        "BG": lambda v: {"mw_gen": val(v, "gen_400kv_mw", "gen_220kv_mw", "gen_110kv_mw", "gen_mv_mw"),
                         "mw_load": val(v, "load_400kv_mw", "load_220kv_mw", "load_110kv_mw", "load_mv_mw")},
    }  # fmt: skip
    mapped = MAPPINGS.get(cc if cc != "DE" else "DE-TransnetBW")
    if cc in ("CZ", "EE", "BG", "DE", "AT"):
        mapping = "; ".join(f"{a} -> {c}" for a, c in (mapped or {}).items())
    elif cc == "LT":
        mapping = f"{MW_RULE}, on the larger of the free MW for solar and for wind (both published)"
    elif cc == "LU":
        mapping = f"{MW_RULE}, on the largest free MW of the station's voltage levels"
    elif cc == "MT":
        mapping = "kWp for renewables and kVA for load as published (shown as MVA/MWp, divided by 1,000); class: more than 0 -> available, 0 -> none"
    else:
        mapping = MW_RULE
    k = b.op(cc if cc != "ES-DSO" else "ES", operator, level, source=d["source"], url=d["url"],
             licence=d["licence"], as_of=d.get("updated"), mapping=mapping, note=d.get("note", ""))  # fmt: skip

    def classes(v: list) -> tuple[str | None, str | None]:
        if cc == "CZ":
            return mapped.get(v[idx["nonsync_2031"]]), mapped.get(v[idx["load_2031"]])
        if cc == "EE":
            return ("available" if v[idx["expandable"]] else "none"), None
        if cc == "BG":
            return ("none" if v[idx["needs_expansion"]] else "available"), None
        if cc == "DE":
            return mapped.get(v[idx["status"]]), None
        if cc == "AT":

            def at(mw: float | None) -> str | None:
                if mw is None:
                    return None
                return "available" if mw > 0 else "limited" if v[idx["flexible"]] else "none"

            return at(num(v[idx["feedin_mw"]])), at(num(v[idx["offtake_mw"]]))
        vals = spec[cc](v)
        g = vals.get("mw_gen", vals.get("mva_gen"))
        ld = vals.get("mw_load", vals.get("mva_load"))
        return mw_class(g), mw_class(ld)

    for p in d.get("points", []):
        name, lon, lat, kv, v = p[0], p[1], p[2], p[3], p[4]
        c, cl = classes(v)
        b.row(
            k,
            name=name,
            lon=lon,
            lat=lat,
            kv=num(kv),
            cls=c,
            cls_load=cl,
            **(spec[cc](v) if cc in spec else {}),
        )
    for a in d.get("areas", []):
        name, poly, v = a[0], flat_polygons(a[1]), a[2] if len(a) > 2 else []
        c, cl = classes(v)
        lon, lat = ring_centre(poly)
        b.row(k, name=name, kind="area", lon=lon, lat=lat, polygon=poly, cls=c, cls_load=cl,
              **(spec[cc](v) if cc in spec else {}))  # fmt: skip
    for t in d.get("table", []):
        name, v = t[0], t[2]
        c, cl = classes(v)
        kv = num(v[idx["voltage"]]) if "voltage" in idx else None
        b.row(
            k,
            name=name,
            kv=kv,
            cls=c,
            cls_load=cl,
            match=True,
            **(spec[cc](v) if cc in spec else {}),
        )
    _ = labels


def from_more(b: Build) -> None:
    """connect/fr|it|ie|pt|pl.json (build_connect_more.py)."""
    fr = load(EU / "connect" / "fr.json")
    if fr:
        i_na = fr["codes"].index("INFO_NA")
        k = b.op("FR", "RTE and the distribution operators (Capareseau)", "transmission", source=fr["source"],
                 url="https://www.capareseau.fr", licence="Capareseau: reuse allowed with the source named",
                 as_of=None, mapping=f"{MW_RULE}, on 'capacité réservée au titre du S3REnR qui reste à affecter' (INFO_NA)")  # fmt: skip
        for s in fr["sites"]:
            mw = num(s[7][i_na])
            b.row(k, id=s[0], name=s[1], lon=s[3], lat=s[4], mw_gen=mw, cls=mw_class(mw))
    it = load(EU / "connect" / "it.json")
    if it:
        k = b.op("IT", "Terna (Econnextion)", "transmission", source=it["source"], url=it["url"],
                 licence="dati.terna.it (terms of use not found; figures shown with the source named)", as_of=None,
                 mapping="requests to connect renewables per region -> queue (MW requested, summed per region, computed)",
                 note="Requests, not free capacity")  # fmt: skip
        for reg, srcs in it["renewables"]["regions"].items():
            mw = round(sum(v[0] for v in srcs.values()), 1)
            for code in it["nuts2"].get(reg, []):
                poly = flat_polygons(it["shapes"][code]) if code in it["shapes"] else None
                if poly:
                    lon, lat = ring_centre(poly)
                    b.row(
                        k,
                        id=code,
                        name=reg.title(),
                        kind="area",
                        lon=lon,
                        lat=lat,
                        mw_queue=mw,
                        cls="queue",
                        polygon=poly,
                    )
    ie = load(EU / "connect" / "ie.json")
    if ie:
        ci = {c: i for i, c in enumerate(ie["columns"])}
        k = b.op("IE", "ESB Networks", "distribution", source=ie["source"], url=ie["url"],
                 licence="ESB Networks website terms", as_of=ie.get("file"),
                 mapping=f"{MW_RULE}, on firm generation available (MW); demand available is MVA, kept as published")  # fmt: skip
        for s in ie["stations"]:
            v = s[5]
            g = num(v[ci["gen_available_firm_mw"]])
            dm = num(v[ci["demand_available_mva"]])
            b.row(k, name=s[0], lon=s[3], lat=s[4], kv=num(re.sub(r"[^\d.]", "", s[1]) or None),
                  mw_gen=g, mva_load=dm, cls=mw_class(g), cls_load=mw_class(dm))  # fmt: skip
    pt = load(EU / "connect" / "pt.json")
    if pt:
        ci = {c: i for i, c in enumerate(pt["columns"])}
        k = b.op("PT", "E-REDES", "distribution", source=pt["source"],
                 url="https://e-redes.opendatasoft.com/explore/dataset/capacidade-rececao-rnd/", licence="CC BY 4.0",
                 as_of=pt.get("date"), mapping="MVA only (reception capacity, HV): more than 0 -> available, 0 -> none",
                 note="No positions published: substations matched to OpenStreetMap by name where unique")  # fmt: skip
        for s in pt["substations"]:
            mva = num(s[7][ci["capacidade_de_recepcao_at_mva_ultimo_trimestre"]])
            b.row(
                k,
                id=s[0],
                name=s[1].replace("(*)", "").strip(),
                mva_gen=mva,
                cls=mw_class(mva),
                match=True,
            )
    pl = load(EU / "connect" / "pl.json")
    if pl:
        k = b.op("PL", "PSE", "transmission", source=pl["source"], url=pl["url"], licence="PSE website (public information under the Energy Law)",
                 as_of=pl.get("date"), mapping="; ".join(f"{a} -> {c}" for a, c in MAPPINGS["PL"].items()),
                 note="No positions published: switchgears matched to OpenStreetMap by name where unique; MW waiting summed per node (computed)")  # fmt: skip
        full = {f[0] for f in pl["full"]}
        waiting: dict[str, float] = {}
        for r in pl["requests"]:
            node = r[6]
            if node:
                waiting[node] = waiting.get(node, 0) + (num(r[5]) or 0)
        for node, mw in waiting.items():
            if node not in full:
                b.row(
                    k, name=node, mw_queue=round(mw, 1), cls="queue", cls_load="queue", match=True
                )
        for f in pl["full"]:
            b.row(k, id=f[1], name=f[0], kv=num(re.findall(r"(\d+)\s*kV", f[2])[0]) if "kV" in f[2] else None,
                  cls="none", cls_load="none", match=True)  # fmt: skip


EU_FILES = [
    ("AT", "at", "Austrian Power Grid (APG)", "transmission"),
    ("BG", "bg", "Elektroenergien Sistemen Operator (ESO)", "transmission"),
    ("CZ", "cz", "ČEPS", "transmission"),
    ("DE", "de", "TransnetBW", "transmission"),
    ("DK", "dk", "Energinet and the Danish DSOs", "transmission"),
    ("EE", "ee", "Elering", "transmission"),
    ("LT", "lt", "Litgrid", "transmission"),
    ("LU", "lu", "Creos", "transmission"),
    ("MT", "mt", "Enemalta", "distribution"),
    ("SE", "se", "Svenska kraftnät", "transmission"),
    ("ES-DSO", "es_dso", "e-distribución (Endesa)", "distribution"),
]


def extra_files(b: Build) -> None:
    """connect/h_<key>.json: operators added by brief 23, already in harmonised rows."""
    for path in sorted((EU / "connect").glob("h_*.json")):
        d = load(path)
        if not d:
            continue
        k = b.op(d["cc"], d["operator"], d["level"], source=d["source"], url=d["url"], licence=d["licence"],
                 as_of=d.get("as_of"), mapping=d["mapping"], note=d.get("note", ""))  # fmt: skip
        for r in d["rows"]:
            b.row(k, **{"cls" if f == "class" else "cls_load" if f == "class_load" else f: v for f, v in r.items()},
                  match=d.get("match", False))  # fmt: skip


def build(osm: bool) -> dict:
    b = Build(osm)
    from_here(b)
    for cc, file, operator, level in EU_FILES:
        from_eu_format(b, cc, file, operator, level)
    from_more(b)
    extra_files(b)
    return {
        "fetched": w.now(),
        "fields": FIELDS,
        "classes": CLASSES,
        "note": "One row per published record; MW and classes as each operator publishes them (mappings per operator)",
        "operators": b.operators,
        "rows": b.rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", action="store_true", help="ask Overpass for substation names to match")
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    data = build(args.osm)
    w.write_json(OUT, data)
    for o in data["operators"]:
        print(
            f"  {o['cc']:2} {o['operator'][:44]:44} {o['rows']:6} rows, {o['placed']:6} placed ({o['matched']} matched by name)",
            flush=True,
        )
    ops = data["operators"]
    rows = [
        {**{f: (json.dumps(v) if f == "polygon" and v else v) for f, v in zip(FIELDS, r, strict=True) if f != "op"},
         **{k: ops[r[0]][k] for k in ("cc", "operator", "level", "as_of", "source", "url", "licence")}}
        for r in data["rows"]
    ]  # fmt: skip
    if args.upload or args.lake != Path("lake-out"):
        w7.lake_rows("connect", [("harmonised", rows, ["cc", "operator", "name"], ("lon", "lat"))], lake_dir=args.lake,
                     upload=args.upload, source="the operators' published files (per row)", licence="per row",
                     script=SCRIPT)  # fmt: skip


if __name__ == "__main__":
    main()
