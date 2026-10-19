"""Room to connect in ten more countries (brief 22, family 1): the operators' own figures.

    python scripts/build_connect_eu.py at|bg|cz|de|dk|ee|lt|lu|mt|se|es-dso|gb-dso|all [--lake lake-out] [--upload]

at  APG, available feed-in and offtake capacity per substation (HTML table, monthly under
    Regulation (EU) 2019/943 Art. 50(4a)); no positions, so a table, not points.
bg  ESO, free capacity per substation for generation and consumption by voltage, and whether the
    connection needs a grid expansion first (the arrays of webapps.eso.bg/capacity).
cz  ČEPS, suitability for connection per transmission substation in 2031 (Y5) and 2036 (Y10) for
    synchronous and non-synchronous generation, storage and consumption (ArcGIS layers).
de  TransnetBW, available feed-in and load capacity per substation (ranges as published, the
    tooltips of its connection map); no positions, so a table.
dk  Energinet and the Danish DSOs' capacity map: available production and consumption capacity
    per transmission station and per distribution station (ArcGIS layers).
ee  Elering e-Gridmap: substations, expandable (type A) or not (type B), and the extra fee for a
    connection (vla.elering.ee/data/mapData.json).
lt  Litgrid: free capacity per substation for solar, wind and storage, per year (ArcGIS).
lu  Creos: available, reserved and waitlisted production capacity per station and voltage for
    2026, 2030 and 2035 (cap_map JSON).
mt  Enemalta: available load capacity (kVA) and RES capacity (kWp) per substation (JSON; the
    page's own conversion of its coordinates, ED50 / UTM 33N, to WGS84).
es-dso  e-distribución (Endesa): available capacity per distribution node and voltage, the CNMC
    monthly format (CSV, UTM coordinates).
gb-dso  the six GB DNOs' embedded capacity registers (1 MW and more): accepted and connected MW
    per site, positions from eastings and northings.
se  Svenska kraftnät: indicative available capacity per county (län) for feed-in and offtake,
    and allocated, reserved and applied capacity 2027-2035 (ArcGIS).

Each writes frontend/public/data/eu/connect/<cc>.json in one format (columns, points or areas or
table rows, and a class per row for the map colour, from the operator's own category or from
the feed-in MW in four classes) and a lake table connect_eu/<cc> (snapshot partition).
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
from pathlib import Path

import wave5_common as w
import wave7_common as w7

OUT = w.EU / "connect"
SCRIPT = "scripts/build_connect_eu.py"
MW_CLASSES = ["50 MW or more", "10 to 50 MW", "under 10 MW", "none"]


def mw_class(v: float | None) -> int:
    """The four classes of the Grid capacity layer (wave 6's ROOM_CLASSES) on a feed-in MW."""
    if v is None:
        return -1
    return 0 if v >= 50 else 1 if v >= 10 else 2 if v > 0 else 3


def payload(
    cc: str, *, source: str, url: str, licence: str, columns: list[list[str]], note: str,
    classes: list[str], class_of: str, points: list | None = None, areas: list | None = None,
    table: list | None = None, updated: str | None = None,
) -> dict:  # fmt: skip
    """The app's file: columns [[key, label, unit]], points [name, lon, lat, kV, values, class],
    areas [name, rings, values, class], table [name, region, values, class]."""
    return {
        "fetched": w.now(),
        "cc": cc,
        "source": source,
        "url": url,
        "licence": licence,
        "updated": updated,
        "note": note,
        "columns": columns,
        "classes": classes,
        "class_of": class_of,
        "points": points or [],
        "areas": areas or [],
        "table": table or [],
    }


def finish(cc: str, data: dict, rows: list[dict], args: argparse.Namespace, geo: bool) -> None:
    """`cc` is the country or a country and grid level (ES-DSO): the file connect/<cc>.json."""
    w.write_json(OUT / f"{cc.lower().replace('-', '_')}.json", data)
    n = len(data["points"]) + len(data["areas"]) + len(data["table"])
    print(f"  {cc}: {n} rows", flush=True)
    for r in rows:
        r.setdefault("iso2", cc[:2])
    w7.lake_rows(
        "connect_eu", [(cc.lower().replace("-", "_"), rows, ["name"], ("lon", "lat") if geo else None)],
        lake_dir=args.lake, upload=args.upload, source=data["source"], licence=data["licence"], script=SCRIPT,
    )  # fmt: skip


def values(row: dict, columns: list[list[str]]) -> list:
    return [row.get(k) for k, _, _ in columns]


# ---------------------------------------------------------------- Austria (APG)

APG = "https://markt.apg.at/netz/netzanschluss/netzanschlusskapazitaeten/"


def apg_rows(page: str) -> tuple[str | None, list[dict]]:
    """The table's rows: substation, federal state (carried down), feed-in MW, offtake MW,
    flexible connection offered, and the state's applications as published."""
    stand = re.search(r"Stand:\s*([^<]+?)\s*<", page)
    body = page[page.find("<table") : page.find("</table>")]
    out, state, apps = [], None, None
    for tr in re.findall(r"<tr.*?</tr>", body, re.S)[1:]:
        cells = [
            htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        ]
        if len(cells) < 4 or not cells[0].startswith("UW"):
            continue
        if (
            len(cells) >= 6
        ):  # the first row of a state carries the state and its applications (rowspan)
            name, state, feed, off, flex, apps = cells[:6]
        else:
            name, feed, off, flex = cells[:4]
        out.append({
            "name": name, "state": state, "feedin_mw": w7.number(feed.replace("MW", "")), "offtake_mw": w7.number(off.replace("MW", "")),
            "flexible": "✓" in flex, "applications": apps,
        })  # fmt: skip
    return (stand.group(1).strip() if stand else None), out


def build_at(args: argparse.Namespace) -> None:
    updated, rows = apg_rows(w7.get(APG).text)
    if not rows:
        raise SystemExit("APG: no rows in the table")
    cols = [
        ["feedin_mw", "Available feed-in", "MW"],
        ["offtake_mw", "Available offtake", "MW"],
        ["flexible", "Flexible connection possible", ""],
        ["applications", "Applications in the state", ""],
    ]
    table = [[r["name"], r["state"], values(r, cols), mw_class(r["feedin_mw"])] for r in rows]
    data = payload("AT", source="Austrian Power Grid (APG), available connection capacities", url=APG, licence="public notice (Regulation (EU) 2019/943 Art. 50(4a)); reuse with the source named",
                   columns=cols, note="Transmission substations of APG; values as published, updated monthly. No positions published.",
                   classes=MW_CLASSES, class_of="feedin_mw", table=table, updated=updated)  # fmt: skip
    finish("AT", data, rows, args, geo=False)


# ---------------------------------------------------------------- Bulgaria (ESO)

ESO = "https://webapps.eso.bg/capacity/"
ESO_ARRAYS = {
    "pinID": "id", "pinLatitude": "lat", "pinLogitude": "lon", "pinName_a": "name",
    "pinSkpgm400": "gen_400kv_mw", "pinSkpgm220": "gen_220kv_mw", "pinSkpgm110": "gen_110kv_mw", "pinSkpgm20": "gen_mv_mw",
    "pinSkpdp400": "load_400kv_mw", "pinSkpdp220": "load_220kv_mw", "pinSkpdp110": "load_110kv_mw", "pinSkpp20": "load_mv_mw",
    "need_extension": "needs_expansion",
}  # fmt: skip


def eso_rows(page: str) -> list[dict]:
    """One row per substation from the page's parallel arrays (index i of every array)."""
    arrays = {}
    for js, key in ESO_ARRAYS.items():
        m = re.search(rf"var {js}\s*=\s*(\[.*?\]);", page, re.S)
        if not m:
            raise SystemExit(f"ESO: array {js} not found")
        arrays[key] = json.loads(m.group(1))
    n = len(arrays["id"])
    out = []
    for i in range(n):
        r = {k: (v[i] if i < len(v) else None) for k, v in arrays.items()}
        kv = re.search(r"(\d+)\s*kV", r["name"] or "")
        row = {"id": r["id"], "name": re.sub(r"\s+", " ", r["name"] or "").strip(), "kv": int(kv.group(1)) if kv else None,
               "lon": w7.number(r["lon"]), "lat": w7.number(r["lat"]), "needs_expansion": r["needs_expansion"] == "1"}  # fmt: skip
        for k in ESO_ARRAYS.values():
            if k.endswith("_mw"):
                row[k] = w7.number(r[k])
        out.append(row)
    return out


def build_bg(args: argparse.Namespace) -> None:
    rows = [r for r in eso_rows(w7.get(ESO).text) if r["lon"] and r["lat"]]
    cols = [[k, lab, "MW"] for k, lab in [
        ("gen_400kv_mw", "Free for generation, 400 kV"), ("gen_220kv_mw", "Free for generation, 220 kV"),
        ("gen_110kv_mw", "Free for generation, 110 kV"), ("gen_mv_mw", "Free for generation, medium voltage"),
        ("load_400kv_mw", "Free for consumption, 400 kV"), ("load_220kv_mw", "Free for consumption, 220 kV"),
        ("load_110kv_mw", "Free for consumption, 110 kV"), ("load_mv_mw", "Free for consumption, medium voltage"),
    ]] + [["needs_expansion", "Connection needs a grid expansion first (ESO)", ""]]  # fmt: skip
    pts = [
        [r["name"], r["lon"], r["lat"], r["kv"], values(r, cols), 1 if r["needs_expansion"] else 0]
        for r in rows
    ]
    data = payload("BG", source="ESO (Electricity System Operator), electronic map of free capacity", url=ESO, licence="public web map; reuse with the source named",
                   columns=cols, note="Free capacity: the most active power in MW that can connect without overloading the grid (ESO's definition); approximate operational data, updated quarterly or more often.",
                   classes=["connection possible", "grid expansion needed first"], class_of="needs_expansion", points=pts)  # fmt: skip
    finish("BG", data, rows, args, geo=True)


# ---------------------------------------------------------------- Czechia (ČEPS)

CEPS = "https://services-eu1.arcgis.com/fCzFkNSJkq74cWT0/arcgis/rest/services"
CEPS_LAYERS = {
    "sync": "PRIPOJ_synchronniVyroba",
    "nonsync": "PRIPOJ_nesynchronniVyroba",
    "storage": "PRIPOJ_zarizeniProUkladaniElektriny",
    "load": "PRIPOJ_elektrickeOdberneZarizeni",
}
CEPS_LABEL = {1: "suitable", 2: "conditionally suitable", 3: "not suitable"}


def ceps_merge(layers: dict[str, list[dict]]) -> list[dict]:
    """One row per substation code with the four kinds' classes for 2031 (Y5) and 2036 (Y10)."""
    out: dict[str, dict] = {}
    for kind, feats in layers.items():
        for f in feats:
            r = out.setdefault(
                f["Rozvodna_kod"],
                {
                    "code": f["Rozvodna_kod"],
                    "name": f["Rozvodna_nazev"],
                    "lon": f.get("_lon") or f.get("Longitude"),
                    "lat": f.get("_lat") or f.get("Latitude"),
                },
            )
            r[f"{kind}_2031"] = CEPS_LABEL.get(f.get("Y5"))
            r[f"{kind}_2036"] = CEPS_LABEL.get(f.get("Y10"))
    return sorted(out.values(), key=lambda r: r["code"])


def build_cz(args: argparse.Namespace) -> None:
    rows = ceps_merge({k: w7.arcgis(f"{CEPS}/{v}/FeatureServer/0") for k, v in CEPS_LAYERS.items()})
    cols = [
        [f"{k}_{y}", f"{lab}, {y}", ""]
        for k, lab in [
            ("nonsync", "Wind, solar (non-synchronous)"),
            ("sync", "Synchronous generation"),
            ("storage", "Storage"),
            ("load", "Consumption"),
        ]
        for y in ("2031", "2036")
    ]
    cls = {"suitable": 0, "conditionally suitable": 1, "not suitable": 2}
    pts = [
        [
            r["name"],
            r["lon"],
            r["lat"],
            None,
            values(r, cols),
            cls.get(r.get("nonsync_2031") or "", -1),
        ]
        for r in rows
    ]
    data = payload("CZ", source="ČEPS, map of available capacity for connection to the transmission system", url="https://www.ceps.cz/cs/mapa-dostupne-kapacity-pro-pripojeni-k-ps",
                   licence="public web map; reuse with the source named", columns=cols,
                   note="Suitability for connection to the transmission system as ČEPS classes it, per substation, for 2031 (Y5) and 2036 (Y10).",
                   classes=["suitable", "conditionally suitable", "not suitable"], class_of="nonsync_2031", points=pts)  # fmt: skip
    finish("CZ", data, rows, args, geo=True)


# ---------------------------------------------------------------- Germany (TransnetBW)

TBW = "https://www.transnetbw.de/de/transparenz/netzzugang-und-entgelt/netzanschlusskarte"
TBW_FIELDS = {"Spannungsebene": "voltage", "Inbetriebnahme Netzanschluss": "earliest", "Anschlussart": "redundancy",
              "Verfügbare Einspeisekapazität": "feedin", "Verfügbare Lastkapazität": "load"}  # fmt: skip


def tbw_rows(page: str) -> list[dict]:
    """The map's tooltips: one per substation, its class (green/yellow/red) and fields as published."""
    out = []
    for m in re.finditer(
        r'class="tooltip[^"]*tooltip-uw-([a-z0-9-]+)[^"]*tooltip-uw-type--(\w+)"[^>]*>', page
    ):
        seg = page[m.end() : m.end() + 3000]
        seg = seg[: seg.find("tooltip-uw-", 10) if "tooltip-uw-" in seg[10:] else len(seg)]
        text = htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", seg)))
        parts = [p.strip() for p in text.split("|") if p.strip()]
        name = next((p for p in parts if p.startswith("Umspannwerk")), m.group(1))
        row = {
            "id": m.group(1),
            "name": name,
            "status": {"green": "medium-term", "yellow": "long-term", "red": "not available"}.get(
                m.group(2), m.group(2)
            ),
        }
        for p in parts:
            k, _, v = p.partition(":")
            if k.strip() in TBW_FIELDS and v.strip():
                row[TBW_FIELDS[k.strip()]] = v.strip()
        out.append(row)
    return out


def build_de(args: argparse.Namespace) -> None:
    rows = tbw_rows(w7.get(TBW).text)
    if not rows:
        raise SystemExit("TransnetBW: no substations found")
    cols = [
        ["status", "Availability", ""],
        ["voltage", "Voltage", ""],
        ["earliest", "Connection from", ""],
        ["redundancy", "Connection type", ""],
        ["feedin", "Available feed-in", ""],
        ["load", "Available load", ""],
    ]
    cls = {"medium-term": 0, "long-term": 1, "not available": 2}
    table = [[r["name"], "TransnetBW", values(r, cols), cls.get(r["status"], -1)] for r in rows]
    data = payload("DE", source="TransnetBW, grid connection map", url=TBW, licence="public web map; reuse with the source named",
                   columns=cols, note="TransnetBW's control area (Baden-Württemberg) only; capacities as ranges, as published. 50Hertz and Amprion publish PDF maps only; TenneT's page refuses scripts.",
                   classes=["available medium-term", "available long-term", "not available"], class_of="status", table=table)  # fmt: skip
    finish("DE", data, rows, args, geo=False)


# ---------------------------------------------------------------- Denmark (Energinet and DSOs)

DK = "https://services7.arcgis.com/an1TuZOdFp9M3PVx/arcgis/rest/services/Kapacitetskortet_V2/FeatureServer"


def dk_rows(tso: list[dict], dso: list[dict]) -> list[dict]:
    out = []
    for f in tso:
        out.append({"name": f.get("TSO_station_name") or f.get("TSO_station_abbreviation"), "level": "transmission", "kv": f.get("voltage_level_kv"),
                    "lon": f.get("_lon"), "lat": f.get("_lat"), "production_mw": f.get("available_capacity_production_MW"),
                    "consumption_mw": f.get("available_capacity_consumption_MW"), "published": f.get("publication_date")})  # fmt: skip
    for f in dso:
        out.append({"name": f.get("DSO_station_name") or f.get("DSO_station_abbreviation"), "level": "distribution", "kv": f.get("voltage_level_kv"),
                    "lon": f.get("_lon"), "lat": f.get("_lat"), "production_mw": f.get("available_capacity_production_MW_DSO_station_without_TSO_transfo"),
                    "consumption_mw": f.get("available_capacity_consumption_MW_DSO_station_without_TSO_transf"), "published": f.get("publication_date")})  # fmt: skip
    for r in out:
        if isinstance(r["published"], int | float):
            r["published"] = (
                w.datetime.fromtimestamp(r["published"] / 1000, w.UTC).date().isoformat()
            )
    return out


def build_dk(args: argparse.Namespace) -> None:
    rows = [r for r in dk_rows(w7.arcgis(f"{DK}/0"), w7.arcgis(f"{DK}/1")) if r["lon"] is not None]
    cols = [
        ["level", "Grid level", ""],
        ["production_mw", "Available for production", "MW"],
        ["consumption_mw", "Available for consumption", "MW"],
        ["published", "Published", ""],
    ]
    pts = [
        [r["name"], r["lon"], r["lat"], r["kv"], values(r, cols), mw_class(r["production_mw"])]
        for r in rows
    ]
    data = payload("DK", source="Energinet and the Danish distribution companies, kapacitetskort.dk", url="http://www.kapacitetskort.dk",
                   licence="public web map; reuse with the source named", columns=cols,
                   note="Transmission stations (Energinet) and distribution stations (the DSOs, without a new TSO transformer); MW as published.",
                   classes=MW_CLASSES, class_of="production_mw", points=pts, updated=max((r["published"] or "" for r in rows), default=None))  # fmt: skip
    finish("DK", data, rows, args, geo=True)


# ---------------------------------------------------------------- Estonia (Elering)

ELERING = "https://vla.elering.ee/data/mapData.json"


def build_ee(args: argparse.Namespace) -> None:
    pts_in = [p for p in w7.get(ELERING).json()["points"] if p.get("status") == "Aktiivne"]
    rows = [{"code": p.get("tähis"), "name": p.get("name"), "lon": p.get("lng"), "lat": p.get("lat"), "kv": p.get("power"),
             "type": p.get("type"), "expandable": p.get("type") == "A", "extra_fee_eur": p.get("lisatasu"),
             "comment": (p.get("comment") or "").strip() or None} for p in pts_in]  # fmt: skip
    cols = [
        ["expandable", "Expandable (type A)", ""],
        ["extra_fee_eur", "Extra connection fee", "EUR"],
        ["comment", "Note", ""],
    ]
    pts = [
        [r["name"], r["lon"], r["lat"], r["kv"], values(r, cols), 0 if r["expandable"] else 1]
        for r in rows
    ]
    data = payload("EE", source="Elering, e-Gridmap", url="https://vla.elering.ee/", licence="public web map; reuse with the source named", columns=cols,
                   note="Type A substations can take a new 110 kV connection point (up to 100 MVA at 110 kV, 300 MVA at 330 kV); type B cannot, and a new substation is built instead (Elering).",
                   classes=["expandable (type A)", "not expandable (type B)"], class_of="expandable", points=pts)  # fmt: skip
    finish("EE", data, rows, args, geo=True)


# ---------------------------------------------------------------- Lithuania (Litgrid)

LITGRID = "https://services-eu1.arcgis.com/NDrrY0T7kE7A7pU0/arcgis/rest/services/Pastotės_View/FeatureServer/0"


def litgrid_rows(feats: list[dict], year: int) -> list[dict]:
    out = []
    for f in feats:
        if f.get("Metai") != year:
            continue
        out.append({"name": f.get("PAS_PAV"), "kv": f.get("PAS_ITAMPA"), "lon": f.get("_lon"), "lat": f.get("_lat"), "zone": f.get("Zona"), "year": year,
                    "solar_mw": f.get("Laisva_prijungimo_galia_SE"), "wind_mw": f.get("Laisva_prijungimo_galia_VE"), "storage_mw": f.get("Laisva_galia_kaupikliams"),
                    "zone_throughput_mw": f.get("Zonos_pralaidumas"), "note": f.get("Papildoma_informacija_1747116922273") or f.get("Papildoma_informacija")})  # fmt: skip
    return out


def build_lt(args: argparse.Namespace) -> None:
    feats = w7.arcgis(LITGRID)
    year = min(int(w7.TODAY[:4]), max(f.get("Metai") or 0 for f in feats))
    rows = [r for r in litgrid_rows(feats, year) if r["lon"] is not None]
    cols = [
        ["solar_mw", "Free for solar", "MW"],
        ["wind_mw", "Free for wind", "MW"],
        ["storage_mw", "Free for storage", "MW"],
        ["zone_throughput_mw", "Zone throughput", "MW"],
        ["note", "Note", ""],
    ]
    pts = [
        [
            r["name"],
            r["lon"],
            r["lat"],
            r["kv"],
            values(r, cols),
            mw_class(
                max((v for v in (r["solar_mw"], r["wind_mw"]) if v is not None), default=None)
            ),
        ]
        for r in rows
    ]
    data = payload("LT", source="Litgrid, transmission network generation capacity map", url="https://experience.arcgis.com/experience/1aa8fb2983c34b7bbc4343d22d9071a5",
                   licence="public web map; reuse with the source named", columns=cols, updated=str(year),
                   note=f"Free connection capacity in Litgrid's grid for {year}, per substation; the map colour uses the larger of solar and wind (computed).",
                   classes=MW_CLASSES, class_of="solar_mw|wind_mw", points=pts)  # fmt: skip
    finish("LT", data, rows, args, geo=True)


# ---------------------------------------------------------------- Luxembourg (Creos)

CREOS = "https://www.creos-net.lu/cap_map/"


def creos_rows(d: dict) -> list[dict]:
    out = []
    for s in d.get("stations", []):
        row = {
            "id": s.get("stationId"),
            "name": s.get("stationName"),
            "lon": s.get("longitude"),
            "lat": s.get("latitude"),
            "year": d.get("year"),
        }
        for part, key in (
            ("availableCapacity", "available"),
            ("reservedCapacity", "reserved"),
            ("waitlistedCapacity", "waitlisted"),
        ):
            for kv, v in (s.get(part) or {}).items():
                row[f"{key}_{kv}kv_mw"] = (v or {}).get("PRODUCTION")
        out.append(row)
    return out


def build_lu(args: argparse.Namespace) -> None:
    years = w7.get(CREOS + "years.php").json()["years"]
    rows = [
        r
        for y in years
        for r in creos_rows(w7.get(CREOS + "map_data.php", params={"year": y}).json())
    ]
    first = min(years)
    keys = sorted(
        {k for r in rows for k in r if k.endswith("_mw")},
        key=lambda k: (k.split("_")[0], int(re.sub(r"\D", "", k))),
    )
    cols = [
        [k, f"{k.split('_')[0].capitalize()} for production, {k.split('_')[1]}", "MW"] for k in keys
    ]
    now = [r for r in rows if r["year"] == first and r["lon"] is not None]

    def avail(r: dict) -> float | None:
        return max(
            (r[k] for k in keys if k.startswith("available") and r.get(k) is not None), default=None
        )

    pts = [[r["name"], r["lon"], r["lat"], None, values(r, cols), mw_class(avail(r))] for r in now]
    data = payload("LU", source="Creos Luxembourg, grid hosting capacity map", url="https://www.creos-net.lu/en/pro-space/products-services/grid-hosting-capacity",
                   licence="public web map; reuse with the source named", columns=cols, updated=str(first),
                   note=f"Production capacity per station and voltage for {first} as published (also {', '.join(str(y) for y in years if y != first)} in the lake); the map colour uses the largest available value (computed).",
                   classes=MW_CLASSES, class_of="available", points=pts)  # fmt: skip
    finish("LU", data, rows, args, geo=True)


# ---------------------------------------------------------------- Malta (Enemalta)

ENEMALTA = "https://enemalta.com.mt/available-capacity/?capacity_json=1"


def enemalta_lonlat(lat_field: float, lng_field: float) -> tuple[float, float]:
    """The page's own conversion: easting = lat + 400000 - 55, northing = lng + 3900000 - 195,
    ED50 / UTM zone 33N (EPSG:23033) to WGS84."""
    from pyproj import Transformer

    t = Transformer.from_crs(23033, 4326, always_xy=True)
    lon, lat = t.transform(lat_field + 400000 - 55, lng_field + 3900000 - 195)
    return round(lon, 5), round(lat, 5)


def build_mt(args: argparse.Namespace) -> None:
    rows = []
    for s in w7.get(ENEMALTA).json()["value"]:
        if s.get("lat") is None or s.get("lng") is None:
            continue
        lon, lat = enemalta_lonlat(float(s["lat"]), float(s["lng"]))
        rows.append({"name": s.get("substationName"), "locality": s.get("locality"), "lon": lon, "lat": lat,
                     "load_kva": s.get("availableCapacity"), "res_kwp": s.get("totalPVCapacity"),
                     "transformers_kva": s.get("sumOfTransformersRating"), "max_demand_kva": s.get("sumOfMaximumDemand")})  # fmt: skip
    cols = [
        ["load_kva", "Available load capacity", "kVA"],
        ["res_kwp", "RES available capacity", "kWp"],
        ["transformers_kva", "Transformer rating", "kVA"],
        ["max_demand_kva", "Maximum demand", "kVA"],
        ["locality", "Locality", ""],
    ]
    pts = [
        [
            r["name"],
            r["lon"],
            r["lat"],
            None,
            values(r, cols),
            mw_class(r["res_kwp"] / 1000 if r["res_kwp"] is not None else None),
        ]
        for r in rows
    ]
    data = payload("MT", source="Enemalta, available capacity map", url="https://enemalta.com.mt/available-capacity/", licence="public notice (Regulation (EU) 2019/943 Art. 57(3)); reuse with the source named",
                   columns=cols, note="Low-voltage distribution substations; spare transformer kVA and RES kWp as published, updated quarterly. Positions converted as the page does.",
                   classes=MW_CLASSES, class_of="res_kwp", points=pts)  # fmt: skip
    finish("MT", data, rows, args, geo=True)


# ---------------------------------------------------------------- Sweden (Svenska kraftnät)

SVK = "https://services2.arcgis.com/L8WLzcxhwLqd80Jx/arcgis/rest/services/kapacitetsdata_vy/FeatureServer/0"
SVK_COLS = [
    ("Indikativt_tillgänglig_kapacitet_inmatning_2026", "feedin_2026_mw", "Indicative available, feed-in 2026"),
    ("Indikativt_tillgänglig_kapacitet_uttag_2026", "offtake_2026_mw", "Indicative available, offtake 2026"),
    ("Tilldelad_kapacitet_inmatning__2027_2035_", "allocated_feedin_mw", "Allocated, feed-in 2027-2035"),
    ("Tilldelad_kapacitet_uttag__2027_2035_", "allocated_offtake_mw", "Allocated, offtake 2027-2035"),
    ("Reserverad_kapacitet_inmatning__2027_2035_", "reserved_feedin_mw", "Reserved, feed-in 2027-2035"),
    ("Reserverad_kapacitet_uttag__2027_2035_", "reserved_offtake_mw", "Reserved, offtake 2027-2035"),
    ("Ansökt_kapacitet_inmatning", "applied_feedin_mw", "Applied for, feed-in"),
    ("Ansökt_kapacitet_uttag", "applied_offtake_mw", "Applied for, offtake"),
]  # fmt: skip


def build_se(args: argparse.Namespace) -> None:
    feats = w7.arcgis(SVK)
    rows = [
        {
            "county": f.get("Län") or f.get("lansnamn"),
            "code": f.get("kod"),
            **{k: f.get(src) for src, k, _ in SVK_COLS},
            "_polys": f.get("_polys"),
        }
        for f in feats
    ]
    cols = [[k, lab, "MW"] for _, k, lab in SVK_COLS]
    areas = [
        [r["county"], r["_polys"], values(r, cols), mw_class(r["feedin_2026_mw"])]
        for r in rows
        if r.get("_polys")
    ]
    data = payload("SE", source="Svenska kraftnät, capacity map of the transmission grid", url="https://karta.svk.se/pages/kapacitetskartan",
                   licence="public web map; reuse with the source named", columns=cols,
                   note="Per county (län), aggregated by Svenska kraftnät from its stations in the county; indicative, updated monthly.",
                   classes=MW_CLASSES, class_of="feedin_2026_mw", areas=areas)  # fmt: skip
    finish(
        "SE",
        data,
        [{k: v for k, v in r.items() if k != "_polys"} | {"name": r["county"]} for r in rows],
        args,
        geo=False,
    )


# ---------------------------------------------------------------- Spain, distribution (CNMC format)

EDIS = (
    "https://www.edistribucion.com/en/red-electrica/nodos-capacidad-red/capacidad-generacion.html"
)
CNMC_COLS = {
    "Gestor de red": "operator", "Coordenada UTM X": "x", "Coordenada UTM Y": "y", "Subestación": "code",
    "Nombre Subestación": "name", "Nivel de Tensión (kV)": "kv", "Capacidad disponible (MW)": "available_mw",
    "Capacidad ocupada (MW)": "occupied_mw", "Capacidad admitida y no resuelta (MW)": "pending_mw",
    "Capacidad comprometida por cuestiones regulatorias": "committed_mw", "Posiciones libres": "free_bays",
    "Nudo Afección RdT": "transmission_node", "Comentarios": "comment", "Comunidad Autónoma": "region",
}  # fmt: skip


def utm_es(x: float, y: float) -> tuple[float, float]:
    """ETRS89 UTM to lon/lat: zone 30 (EPSG:25830), zone 28 (EPSG:25828) for the Canary Islands
    (northings under 3.5 million); the CNMC format gives no zone."""
    from pyproj import Transformer

    t = Transformer.from_crs(25828 if y < 3_500_000 else 25830, 4326, always_xy=True)
    lon, lat = t.transform(x, y)
    return round(lon, 5), round(lat, 5)


def cnmc_rows(text: str) -> list[dict]:
    """One row per substation and voltage of a CNMC-format capacity file (; separated, decimal comma);
    columns named twice (Provincia, Municipio: code then name) keep their first value."""
    import csv
    import io

    reader = csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";")
    head = [h.strip() for h in next(reader)]
    out = []
    for cells in reader:
        rec: dict = {}
        for h, v in zip(head, cells, strict=False):
            if h in CNMC_COLS and CNMC_COLS[h] not in rec:
                rec[CNMC_COLS[h]] = v.strip() or None
        x, y = w7.number(rec.get("x")), w7.number(rec.get("y"))
        if x is None or y is None:
            continue
        rec["lon"], rec["lat"] = utm_es(x, y)
        for k in ("kv", "available_mw", "occupied_mw", "pending_mw", "committed_mw", "free_bays"):
            rec[k] = w7.number(rec.get(k))
        del rec["x"], rec["y"]
        out.append(rec)
    return out


def build_es_dso(args: argparse.Namespace) -> None:
    page = w7.get(EDIS).text
    links = sorted(
        set(re.findall(r'href="([^"]+/nodos/generacion/(\d{6})/[^"]+\.csv)"', page)),
        key=lambda t: t[1],
    )
    if not links:
        raise SystemExit("e-distribución: no CSV links")
    month = links[-1][1]
    rows = []
    for href, m in links:
        if m != month:
            continue
        url = href if href.startswith("http") else "https://www.edistribucion.com" + href
        rows += cnmc_rows(w7.get(url).content.decode("utf-8-sig", errors="replace"))
    cols = [["available_mw", "Available capacity", "MW"], ["occupied_mw", "Occupied", "MW"], ["pending_mw", "Admitted, not resolved", "MW"],
            ["kv", "Voltage", "kV"], ["free_bays", "Free bays", ""], ["transmission_node", "Transmission node", ""], ["operator", "Operator", ""], ["comment", "Comment", ""]]  # fmt: skip
    pts = [
        [
            r["name"] or r["code"],
            r["lon"],
            r["lat"],
            r["kv"],
            values(r, cols),
            mw_class(r["available_mw"]),
        ]
        for r in rows
    ]
    data = payload("ES", source="e-distribución (Endesa), access capacity for generation per node", url=EDIS, licence="published under CNMC Circular 1/2024; reuse with the source named",
                   columns=cols, updated=f"{month[:4]}-{month[4:]}",
                   note="Distribution nodes of the Endesa companies (the largest Spanish DSO), monthly, one row per substation and voltage; MW as published. Positions from the file's UTM coordinates (ETRS89, zone 30; 28 in the Canary Islands). i-DE and UFD refuse scripts.",
                   classes=MW_CLASSES, class_of="available_mw", points=pts)  # fmt: skip
    finish("ES-DSO", data, rows, args, geo=True)


# ---------------------------------------------------------------- Great Britain, the DNOs' embedded capacity registers

ECR_SOURCES = {
    "NGED": ("ckan", "https://connecteddata.nationalgrid.co.uk", "embedded-capacity-register"),
    "SSEN": ("ckan", "https://data-api.ssen.co.uk", "embedded_capacity_register"),
    "NPg": ("ods", "https://northernpowergrid.opendatasoft.com", "embedded-capacity-register"),
    "ENWL": (
        "ods",
        "https://electricitynorthwest.opendatasoft.com",
        "enwl-embedded-capacity-register-2-1mw-and-above",
    ),
    "SPEN": (
        "ods-search",
        "https://spenergynetworks.opendatasoft.com",
        "embedded capacity register",
    ),
    "UKPN": ("ods", "https://ukpowernetworks.opendatasoft.com", "ukpn-embedded-capacity-register"),
}
ECR_FIELDS = {
    "site": ("customersite", "customername", "sitename"), "east": ("eastings",), "north": ("northings",),
    "source": ("energysource1", "energysource"), "tech": ("energyconversiontechnology1",),
    "connected_mw": ("alreadyconnectedregisteredcapacitymw", "alreadyconnectedregisteredcapacity"),
    "accepted_mw": ("acceptedtoconnectregisteredcapacitymw", "acceptedtoconnectregisteredcapacity"),
    "kv": ("pointofconnectionpocvoltagekv", "pocvoltage", "connectionvoltage"), "primary": ("primary",),
    "gsp": ("gridsupplypoint",), "target": ("targetenergisationdate",), "queue": ("inaconnectionqueue",),
}  # fmt: skip


def ecr_pick(rec: dict) -> dict:
    """The register's fields under its own column names (normalised to letters and digits)."""
    norm = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in rec.items()}
    out = {}
    for key, names in ECR_FIELDS.items():
        out[key] = next(
            (
                norm[k]
                for n in names
                for k in norm
                if k.startswith(n) or (n in k and key in ("east", "north"))
            ),
            None,
        )
    return out


def ecr_records(kind: str, base: str, ident: str) -> tuple[str, list[dict]]:
    import csv
    import io

    if kind == "ckan":
        pkg = w7.get(f"{base}/api/3/action/package_show", params={"id": ident}).json()["result"]
        csvs = [
            r
            for r in pkg["resources"]
            if (r.get("format") or "").upper() == "CSV" and r.get("url", "").startswith("http")
        ]
        csvs.sort(key=lambda r: r.get("last_modified") or r.get("created") or "")
        part1 = [r for r in csvs if "1mw" in (r.get("name") or "").lower().replace(" ", "")] or csvs
        res = part1[-1]
        text = w7.get(res["url"]).content.decode("utf-8-sig", errors="replace")
        return res["url"], list(csv.DictReader(io.StringIO(text)))
    if kind == "ods-search":
        d = w7.get(
            f"{base}/api/explore/v2.1/catalog/datasets",
            params={"where": f'search("{ident}")', "limit": 20},
        ).json()
        ids = [
            r["dataset_id"]
            for r in d.get("results", [])
            if "ecr" in r["dataset_id"] or "embedded-capacity" in r["dataset_id"]
        ]
        ids = [i for i in ids if "quality" not in i and "under" not in i] or ids
        if not ids:
            raise SystemExit(f"{base}: no embedded capacity register found")
        ident = ids[0]
    url = f"{base}/api/explore/v2.1/catalog/datasets/{ident}/exports/json"
    return url, w7.get(url, timeout=300).json()


def build_gb_dso(args: argparse.Namespace) -> None:
    from pyproj import Transformer

    osgb = Transformer.from_crs(27700, 4326, always_xy=True)
    rows, used, failed = [], [], []
    for dno, (kind, base, ident) in ECR_SOURCES.items():
        try:
            url, recs = ecr_records(kind, base, ident)
        except (SystemExit, Exception) as e:
            print(f"  {dno}: {type(e).__name__} {str(e)[:200]}", flush=True)
            failed.append(f"{dno} ({type(e).__name__})")
            continue
        n0 = len(rows)
        for rec in recs:
            r = ecr_pick(rec)
            e, n = w7.number(r["east"]), w7.number(r["north"])
            if e is None or n is None or e <= 0 or n <= 0:
                continue
            lon, lat = osgb.transform(e, n)
            con, acc = w7.number(r["connected_mw"]), w7.number(r["accepted_mw"])
            rows.append({"dno": dno, "name": r["site"], "lon": round(lon, 4), "lat": round(lat, 4), "source": r["source"], "tech": r["tech"],
                         "connected_mw": con, "accepted_mw": acc, "kv": w7.number(r["kv"]), "primary": r["primary"], "gsp": r["gsp"], "target": r["target"]})  # fmt: skip
        print(f"  {dno}: {len(recs)} records, {len(rows) - n0} placed ({url})", flush=True)
        if len(rows) == n0 and recs:
            print(f"  {dno} columns: {list(recs[0])[:40]}", flush=True)
        used.append(dno)
    if not rows:
        raise SystemExit("no register answered")
    cols = [["accepted_mw", "Accepted to connect", "MW"], ["connected_mw", "Connected", "MW"], ["source", "Energy source", ""], ["tech", "Technology", ""],
            ["kv", "Connection voltage", "kV"], ["primary", "Primary substation", ""], ["gsp", "Grid supply point", ""], ["target", "Target energisation", ""], ["dno", "Operator", ""]]  # fmt: skip
    pts = [
        [
            r["name"] or "–",
            r["lon"],
            r["lat"],
            r["kv"],
            values(r, cols),
            0 if (r["accepted_mw"] or 0) > 0 else 1,
        ]
        for r in rows
    ]
    data = payload("GB", source=f"The DNOs' embedded capacity registers ({', '.join(used)})", url="https://www.energynetworks.org/work/futures/embedded-capacity-register",
                   licence="the DNOs' open data licences (attribution)", columns=cols,
                   note=f"Generation and storage of 1 MW and more connected or accepted to connect to the distribution grids, as each DNO publishes it; positions from the registers' eastings and northings. Not read: {', '.join(failed) or 'none'}.",
                   classes=["accepted, not yet connected", "connected"], class_of="accepted_mw", points=pts)  # fmt: skip
    finish("GB-DSO", data, rows, args, geo=True)


BUILDERS = {"at": build_at, "bg": build_bg, "cz": build_cz, "de": build_de, "dk": build_dk, "ee": build_ee,
            "lt": build_lt, "lu": build_lu, "mt": build_mt, "se": build_se, "es-dso": build_es_dso, "gb-dso": build_gb_dso}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("country", choices=[*BUILDERS, "all"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    failed = []
    for cc in BUILDERS if args.country == "all" else [args.country]:
        print(f"== {cc}", flush=True)
        try:
            BUILDERS[cc](args)
        except (SystemExit, Exception) as e:  # one country failing must not stop the others
            print(f"  {cc} failed: {type(e).__name__} {e}", flush=True)
            failed.append(cc)
    if failed:
        raise SystemExit(f"failed: {' '.join(failed)}")


if __name__ == "__main__":
    main()
