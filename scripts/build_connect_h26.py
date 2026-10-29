"""Room to connect, the operators brief 26 adds (probe: scripts/probe_connect_h26.py).

    python scripts/build_connect_h26.py all|<key>

Same file format and rules as scripts/build_connect_h23.py: each operator becomes
frontend/public/data/eu/connect/h_<key>.json in the harmonised rows that
scripts/build_connect_harmonised.py reads; values as published, classes mapped one to one,
MW only where published (MVA kept as MVA). A node without coordinates is matched to an
OpenStreetMap substation by name in the harmonised build (`osm_area` names the area to search
where the operator's code is not a country: US-CA for CAISO).

  key            operator                                    what
  hr_hepods      HEP ODS (HR)                                JSON behind the capacity map
  se_vattenfall  Vattenfall Eldistribution (SE)              ArcGIS, regional and local networks
  gb_nie         NIE Networks (Northern Ireland)             JSON behind the capacity map
  tr_teias       TEİAŞ (TR)                                  PDF table, per transformer centre
  at_enetze      Energienetze Steiermark (AT)                HTML table, free feed-in capacity
  cz_pre         PREdistribuce (CZ)                          ArcGIS, connectability map
  fi_helen       Helen Sähköverkko (FI)                      ArcGIS, free MV capacity (MVA)
  ch_swissgrid   Swissgrid (CH)                              PDF tables, generation and load (MVA)
  us_pgn         Portland General Electric (US)              ArcGIS, FERC Order 2023 heatmap
  us_idaho       Idaho Power (US)                            ArcGIS, FERC Order 2023 heatmap
  us_lgeku       LG&E and KU (US)                            ArcGIS, FERC Order 2023 heatmap
  us_avista      Avista (US)                                 ArcGIS, FERC Order 2023 heatmap
  us_caiso       CAISO (US)                                  JSON behind the POI heatmap
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402
from build_connect_h23 import MW_RULE, mw_class, num, pdf_tables  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "connect"
MVA_RULE = "MVA only: more than 0 MVA free -> available, 0 MVA -> none (MVA kept as MVA)"


def save(key: str, cc: str, operator: str, level: str, rows: list[dict], *, source: str, url: str,
         licence: str, as_of: str | None, mapping: str, note: str = "", match: bool = False,
         osm_area: str | None = None, summable: bool = True) -> None:  # fmt: skip
    """`summable`: False where the figures share the grid (a sum would count capacity twice)."""
    if not rows:
        raise SystemExit(f"{key}: no rows")
    data = {"cc": cc, "operator": operator, "level": level, "source": source, "url": url, "licence": licence,
            "as_of": as_of, "mapping": mapping, "note": note, "match": match, "fetched": w.now(), "rows": rows}  # fmt: skip
    if osm_area:
        data["osm_area"] = osm_area
    if not summable:
        data["summable"] = False
    w.write_json(OUT / f"h_{key}.json", data)
    placed = sum(1 for r in rows if r.get("lon") is not None)
    print(f"  {key}: {len(rows)} rows, {placed} with a position", flush=True)


def top_kv(text: str | None) -> float | None:
    """'110/35/10(20) kV' -> 110.0 (the highest voltage of the transformation)."""
    vals = [float(v.replace(",", ".")) for v in re.findall(r"\d+(?:[.,]\d+)?", text or "")]
    return max(vals) if vals else None


def kw_mw(v: object) -> float | None:
    x = num(v)
    return round(x / 1000, 3) if x is not None else None


def centre(polys: list | None) -> tuple[float | None, float | None]:
    """Middle of the bounding box of the largest ring (the label point, computed)."""
    if not polys:
        return None, None
    ring = max((p[0] for p in polys), key=len)
    xs, ys = ring[0::2], ring[1::2]
    return round((min(xs) + max(xs)) / 2, 5), round((min(ys) + max(ys)) / 2, 5)


# ---------------------------------------------------------------- Croatia

HEP = "https://kapaciteti.hep.hr"


def hr_hepods() -> None:
    meta = w7.get(f"{HEP}/api/substation-data/current").json()
    rows = []
    for s in w7.get(f"{HEP}/api/substations/with-data").json():
        lon, lat = ((s.get("coordinateGeoJSONData") or {}).get("coordinates") or [None, None])[:2]
        g = kw_mw(s.get("freeCapacityKw"))
        rows.append({"id": s.get("shorthandLabel") or s.get("id"), "name": s.get("fullyQualifiedName") or s.get("coordinateName"),
                     "lon": round(lon, 5) if lon is not None else None, "lat": round(lat, 5) if lat is not None else None,
                     "kv": top_kv(s.get("transferCoordinator")), "mw_gen": g, "mw_queue": kw_mw(s.get("pendingUsersPowerKw")),
                     "class": mw_class(g)})  # fmt: skip
    save("hr_hepods", "HR", "HEP ODS", "distribution", rows, match=True, source="HEP ODS, map of available distribution network capacity for RES (free capacity and pending applications per substation, kW shown in MW)",
         url=HEP, licence="HEP ODS public web map (no licence stated)", as_of=(meta.get("dataDate") or "")[:10] or None, mapping=MW_RULE,
         note="mw_queue = 'pendingUsersPowerKw' (applications in progress); substations without a free-capacity figure have no class")  # fmt: skip


# ---------------------------------------------------------------- Sweden

VF = "https://services-eu1.arcgis.com/dVRL7HtXQT22fiCW/arcgis/rest/services"
VF_RN = f"{VF}/Kategori_regionnät_260702/FeatureServer"
VF_LN = f"{VF}/Kategori_Lokalnät_260527/FeatureServer"
VF_URL = "https://www.vattenfalleldistribution.se/kapacitetskarta"
VF_NOTE = ("Vattenfall publishes one figure per technology (solar, wind, storage and three consumption types) and the years "
           "to a possible connection ('1-2', '2-3', '3-5'); mw_gen = wind, mw_load = 'medium' consumption, as published for the "
           "earliest horizon each station lists (the horizon is in the name)")  # fmt: skip


def vf_layers(base: str, ids: dict[str, int]) -> dict[str, dict]:
    """One record per station: the figures of the earliest horizon it publishes ('1-2' years
    before '2-3' before '3-5'); a station is listed once per horizon in every layer."""
    out: dict[str, dict] = {}
    for tech, lid in ids.items():
        for f in w7.arcgis(f"{base}/{lid}", extra={"maxAllowableOffset": 0.002}):
            key = f"{f.get('Stationsnamn')}|{f.get('Littera') or ''}"
            years = f.get("Antal_år_till_möjlig_anslutning") or "9"
            have = out.get(key)
            if have is not None and have["_years"] < years:
                continue
            if have is None or have["_years"] > years:
                out[key] = have = dict(f) | {"_years": years}
            have[tech] = num(next((v for k, v in f.items() if k.endswith("__MW_")), None))
    return out


VF_MAPPING = (
    "more than 0 MW within 1-2 years -> available, more than 0 MW only in 2-3 or 3-5 years -> limited, "
    "0 MW -> none"
)


def vf_class(f: dict, side: str) -> str | None:
    c = mw_class(f.get(side))
    return "limited" if c == "available" and f["_years"] != "1-2" else c


def se_vattenfall() -> None:
    rows = []
    for f in vf_layers(VF_RN, {"wind": 6, "load": 3}).values():
        rows.append({"id": f.get("Littera") or None, "name": f"{f.get('Stationsnamn')} ({f['_years']} years)", "lon": f.get("_lon"), "lat": f.get("_lat"),
                     "mw_gen": f.get("wind"), "mw_load": f.get("load"), "class": vf_class(f, "wind"), "class_load": vf_class(f, "load")})  # fmt: skip
    save("se_vattenfall_rn", "SE", "Vattenfall Eldistribution (regional network)", "distribution", rows,
         source="Vattenfall Eldistribution, capacity map of the regional network (indicative MW per station)", url=VF_URL,
         licence="Vattenfall public web map (no licence stated)", as_of="2026-07-02", mapping=VF_MAPPING, note=VF_NOTE)  # fmt: skip
    rows = []
    for f in vf_layers(VF_LN, {"wind": 5, "load": 2}).values():
        lon, lat = centre(f.get("_polys"))
        rows.append({"id": f.get("Driftsmärkning") or f.get("Littera") or None, "name": f"{f.get('Stationsnamn')} ({f['_years']} years)", "kind": "area", "lon": lon, "lat": lat,
                     "polygon": f.get("_polys"), "mw_gen": f.get("wind"), "mw_load": f.get("load"),
                     "class": vf_class(f, "wind"), "class_load": vf_class(f, "load")})  # fmt: skip
    save("se_vattenfall_ln", "SE", "Vattenfall Eldistribution (local networks)", "distribution", rows,
         source="Vattenfall Eldistribution, capacity map of the local networks (indicative MW per supply area)", url=VF_URL,
         licence="Vattenfall public web map (no licence stated)", as_of="2026-05-27", mapping=VF_MAPPING,
         note=VF_NOTE + "; areas simplified to ~200 m for the map; positions: the middle of each area's bounding box (computed)")  # fmt: skip


# ---------------------------------------------------------------- Northern Ireland

NIE = "https://www.nienetworks.co.uk/Connections/Capacity-Map"
NIE_LEVEL = re.compile(
    r"Available (Demand|Generation) Headroom(?:\s*\(([^)]+)\))?:\s*([-\d.]+\s*MVA|Contact for Info)"
)


def nie_rows(markers: list[dict]) -> list[dict]:
    rows = []
    for m in markers:
        text = re.sub(
            r"\s+",
            " ",
            html.unescape(re.sub(r"<[^>]+>", " ", m.get("teaser") or "")).replace("\xa0", " "),
        )
        levels: dict[str, dict] = {}
        for side, level, value in NIE_LEVEL.findall(text):
            levels.setdefault(level, {})[side] = (
                num(value.replace("MVA", "")) if "MVA" in value else None
            )
        vl = re.search(r"Voltage Level:\s*([\d./]+kV)", text)
        lat, lon = (m.get("location") or [None, None])[:2]
        for level, v in levels.items() or {"": {}}.items():
            kv = level or (vl.group(1) if vl else "")
            g, ld = v.get("Generation"), v.get("Demand")
            rows.append({"id": f"{m['id']}{'-' + level if level else ''}", "name": f"{m['name'].title()} {level}".strip(),
                         "lon": round(lon, 5) if lon is not None else None, "lat": round(lat, 5) if lat is not None else None,
                         "kv": top_kv(kv), "mva_gen": g, "mva_load": ld, "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    return rows


def gb_nie() -> None:
    rows = nie_rows(w7.get(NIE, params={"markers": "1"}).json())
    save("gb_nie", "GB", "NIE Networks (Northern Ireland)", "distribution", rows,
         source="NIE Networks, capacity map: available demand and generation headroom (MVA) per bulk supply point and primary",
         url=NIE, licence="NIE Networks capacity map ('information provided subject to terms & conditions')", as_of=None, mapping=MVA_RULE,
         note="Dual primaries publish one figure per transformation (one row each); 'Contact for Info' stays empty")  # fmt: skip


# ---------------------------------------------------------------- Turkey

TEIAS_PAGE = "https://www.teias.gov.tr/duyurular/2026-yili-agustos-ayi-lisanssiz-kapasite-tahsisleri-hakkinda"
TEIAS_TM = "https://webim.teias.gov.tr/file/54e18598-8a7f-48d1-bdd1-a7ee93cee521?download"


def teias_rows(table: list[list]) -> tuple[list[dict], str | None]:
    rows, as_of, last = [], None, {"il": None, "tm": None}
    for r in table:
        cells = [(c or "").replace("\n", " ").strip() for c in r]
        if any("KALAN" in c for c in cells):
            d = re.search(r"(\d\d)\.(\d\d)\.(\d{4})", " ".join(cells))
            as_of = f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else as_of
            continue
        if len(cells) < 5 or cells[0] == "İL" or not re.fullmatch(r"-?\d+(,\d+)?", cells[4]):
            continue
        il, tm, bara, edas, mw = cells[:5]
        if tm:
            last = {"il": il, "tm": tm}
        tm = tm or last["tm"]
        if not tm:
            continue
        g = float(mw.replace(",", "."))
        name = tm + (f" {bara}" if bara and bara != "Tek" else "")
        rows.append(
            {
                "id": f"{il}|{name}|{edas}",
                "name": name,
                "match_name": tm,
                "mw_gen": g,
                "class": mw_class(g),
            }
        )
    return rows, as_of


def tr_teias() -> None:
    rows, as_of = teias_rows(pdf_tables(w7.get(TEIAS_TM).content))
    save("tr_teias", "TR", "TEİAŞ", "transmission", rows,
         source="TEİAŞ, remaining unlicensed solar and wind capacity allocatable from the distribution level, per transformer centre and busbar (MWe)",
         url=TEIAS_PAGE, licence="TEİAŞ public announcement (no licence stated)", as_of=as_of, mapping=MW_RULE,
         note="One row per transformer centre, busbar and distribution company (EDAŞ/OSB) as published; positions matched to OpenStreetMap by the centre's name",
         match=True)  # fmt: skip


# ---------------------------------------------------------------- Austria, Czechia, Finland

ENETZE = "https://www.e-netze.at/Service/FEK/Default.aspx"


def enetze_rows(page: str) -> tuple[list[dict], str | None]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ]
        if len(cells) == 3 and cells[0]:
            g = num(cells[2].replace(",", "."))
            rows.append({"id": cells[0], "name": cells[0], "mw_gen": g, "class": mw_class(g)})
    d = re.search(r"Stand:\s*(\d\d)\.(\d\d)\.(\d{4})", page)
    return rows, f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None


def at_enetze() -> None:
    rows, as_of = enetze_rows(w7.get(ENETZE).text)
    save("at_enetze", "AT", "Energienetze Steiermark", "distribution", rows,
         source="Energienetze Steiermark, free feed-in capacity (FEK) per substation: available MW (booked MW not drawn)",
         url=ENETZE, licence="operator website (public information)", as_of=as_of, mapping=MW_RULE, match=True)  # fmt: skip


PRE = "https://services7.arcgis.com/0NBqUPRkQ8NgorYt/arcgis/rest/services/Mapa_Pripojitelnosti_PREdistribuce/FeatureServer/3"


def cz_pre() -> None:
    areas: dict[str, dict] = {}
    for f in w7.arcgis(PRE, extra={"maxAllowableOffset": 0.0005}):
        a = areas.setdefault(
            f["NAZEV_TR"].replace("  ", " "),
            {"cap": f.get("KAPACITA"), "polys": [], "year": f.get("ROK_UPRS")},
        )
        a["polys"] += f.get("_polys") or []
    rows = []
    for name, a in areas.items():
        lon, lat = centre(a["polys"])
        cap = num(a["cap"])
        rows.append({"id": name, "name": name, "kind": "area", "lon": lon, "lat": lat, "kv": 110.0, "polygon": a["polys"],
                     "class": None if cap is None else "available" if cap > 0 else "none"})  # fmt: skip
    save("cz_pre", "CZ", "PREdistribuce", "distribution", rows,
         source="PREdistribuce, connectability map for generators (free capacity per 110 kV substation supply area)",
         url="https://www.predistribuce.cz/", licence="PREdistribuce public web map (no licence stated)", as_of=None,
         mapping="the layer's 'Volná kapacita' (free capacity): more than 0 -> available, 0 -> none; the layer states no unit, so no figure is drawn",
         note="Prague; positions: the middle of each area's bounding box (computed)")  # fmt: skip


HELEN = "https://services-eu1.arcgis.com/gTUn8bgbbRzjNT5i/arcgis/rest/services/KJ_vapaa_kapasiteetti/FeatureServer/0"


def fi_helen() -> None:
    rows = []
    for f in w7.arcgis(HELEN, extra={"maxAllowableOffset": 0.0005}):
        lon, lat = centre(f.get("_polys"))
        ld = num(f.get("Vapaa_kapasiteetti_MW"))  # the field's alias: 'Vapaa kapasiteetti (MVA)'
        rows.append({"id": str(f.get("Sähköasematunnus")), "name": f.get("Liitosnimi") or f.get("Sähköasema"), "kind": "area",
                     "lon": lon, "lat": lat, "kv": top_kv(f.get("Liitosnimi")), "polygon": f.get("_polys"),
                     "mva_load": ld, "class_load": mw_class(ld)})  # fmt: skip
    save("fi_helen", "FI", "Helen Sähköverkko", "distribution", rows,
         source="Helen Sähköverkko, free capacity of the medium-voltage network per primary substation area (MVA, data 05/2025)",
         url="https://www.helensahkoverkko.fi/", licence="Helen public web map (no licence stated)", as_of="2025-05", mapping=MVA_RULE,
         note="Helsinki; the free capacity is for consumption (the remaining main-transformer capacity over the peak load); positions: the middle of each area's bounding box (computed)")  # fmt: skip


# ---------------------------------------------------------------- Switzerland

SG_PAGE = "https://www.swissgrid.ch/en/home/customers/topics/grid-connection.html"
SG_PROD = "https://www.swissgrid.ch/dam/jcr:35ab9f4a-89d9-4093-8d1d-f4348a0b1aed/Capa-2026-2030-2035-2040-prod.pdf"
SG_LOAD = "https://www.swissgrid.ch/dam/jcr:7e5aaf7b-f85b-46b1-a0ad-d711c0d33d00/Capa-2026-2030-2035-2040-load.pdf"


def swissgrid_table(table: list[list]) -> dict[tuple[str, str], float | None]:
    """(kV, substation) -> the 2026 'Base' figure (no flexibility); a substation without one -> None."""
    out: dict[tuple[str, str], float | None] = {}
    for r in table:
        cells = [(c or "").strip() for c in r]
        if len(cells) < 3 or not re.fullmatch(r"\d+ kV", cells[0]) or not cells[1]:
            continue
        out[(cells[0], cells[1])] = num(cells[2]) if cells[2] else None
    return out


def ch_swissgrid() -> None:
    gen = swissgrid_table(pdf_tables(w7.get(SG_PROD).content))
    load = swissgrid_table(pdf_tables(w7.get(SG_LOAD).content))
    rows = []
    for kv, name in sorted(set(gen) | set(load), key=lambda k: k[1]):
        g, ld = gen.get((kv, name)), load.get((kv, name))
        rows.append({"id": f"{name} {kv}", "name": name, "kv": top_kv(kv), "mva_gen": g, "mva_load": ld,
                     "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    save("ch_swissgrid", "CH", "Swissgrid", "transmission", rows,
         source="Swissgrid, connection capacity maps: additional generation and load per 220/380 kV substation, 2026, base case (MVA, capped at 300)",
         url=SG_PAGE, licence="Swissgrid public PDF (no licence stated)", as_of="2026-06-01", mapping=MVA_RULE,
         note="Swissgrid also publishes 2030, 2035 and 2040 and the cases with 10 % and 20 % flexibility (not drawn); figures are capped at 300 MVA; positions matched to OpenStreetMap by name",
         match=True)  # fmt: skip


# ---------------------------------------------------------------- United States (FERC Order 2023 heatmaps)

PGN = "https://services6.arcgis.com/eqsXlDArbs19VWhn/arcgis/rest/services/TransmissionCapacity_PointsOfInterconnection/FeatureServer/0"
IPC = "https://services1.arcgis.com/A5HVOoaVqcd8etEM/arcgis/rest/services/InterconnectCapacity/FeatureServer/0"
LGEKU = "https://services.arcgis.com/NTSXKyJwdnK9ffCb/arcgis/rest/services/LGE_KU_FERC_Interconnection_HeatMap_MW/FeatureServer/0"
AVISTA = "https://services3.arcgis.com/WlYQgAChrqj0tuQi/arcgis/rest/services/HeatMap_MW_Impact_PRD/FeatureServer/0"
CAISO = "https://www.caiso.com/poi-heatmap/WClusterTrLimSumJson.json"
FERC = "FERC Order 2023 (interconnection heatmap)"
# an Order 2023 heatmap studies each bus alone: two buses' MW share the same lines, so no sum
HEAT = {"summable": False}


def us_pgn() -> None:
    rows = []
    for f in w7.arcgis(PGN, geometry=False):
        g = num(f.get("Available_Capacity"))
        rows.append(
            {
                "id": f.get("POI"),
                "name": f.get("SUB_NAME"),
                "kv": top_kv(f.get("POI")),
                "mw_gen": g,
                "class": mw_class(g),
            }
        )
    pts = {}
    for p in (
        w7.get(
            f"{PGN}/query", params={"where": "1=1", "outFields": "POI", "outSR": 4326, "f": "json"}
        )
        .json()
        .get("features", [])
    ):
        xy = ((p.get("geometry") or {}).get("points") or [[None, None]])[0]
        pts[p["attributes"]["POI"]] = xy
    for r in rows:
        lon, lat = pts.get(r["id"], [None, None])
        r["lon"], r["lat"] = (round(lon, 5), round(lat, 5)) if lon is not None else (None, None)
    save("us_pgn", "US-PGE-OR", "Portland General Electric", "transmission", rows,
         source="Portland General Electric, transmission capacity at points of interconnection (available MW)", url=PGN,
         licence="PGE public heatmap (terms on the item page)", as_of=None, mapping=MW_RULE + f"; {FERC}", **HEAT)  # fmt: skip


def us_idaho() -> None:
    rows = []
    for f in w7.arcgis(IPC):
        g = num(f.get("Max_Injection"))
        rows.append({"id": f.get("Location_Code"), "name": f.get("Station_Name"), "lon": f.get("_lon"), "lat": f.get("_lat"),
                     "mw_gen": g, "class": mw_class(g)})  # fmt: skip
    save("us_idaho", "US-IPC", "Idaho Power", "transmission", rows,
         source="Idaho Power, interconnection capacity per substation (maximum injection, MW)", url=IPC,
         licence="Idaho Power public heatmap (no licence stated)", as_of=None, mapping=MW_RULE + f"; {FERC}", **HEAT)  # fmt: skip


def lgeku_rows(feats: list[dict]) -> list[dict]:
    """One row per bus: the newest study year, the lowest published transfer limit over its seasons."""
    year = max(str(f.get("Year")) for f in feats)
    best: dict[str, dict] = {}
    for f in feats:
        if str(f.get("Year")) != year or f.get("TrLim_min") is None:
            continue
        b = best.get(f["Bus_Number"])
        if b is None or f["TrLim_min"] < b["TrLim_min"]:
            best[f["Bus_Number"]] = f
    rows = []
    for f in best.values():
        g = round(float(f["TrLim_min"]), 1)
        rows.append({"id": str(f["Bus_Number"]), "name": f.get("Station_Name") or f.get("Bus_Name"), "lon": num(f.get("Longitude")),
                     "lat": num(f.get("Latitude")), "kv": num(f.get("Base_kV")), "mw_gen": g, "class": mw_class(g)})  # fmt: skip
    return rows


def us_lgeku() -> None:
    rows = lgeku_rows(w7.arcgis(LGEKU, geometry=False))
    save("us_lgeku", "US-LGEKU", "LG&E and KU", "transmission", rows,
         source="LG&E and KU, interconnection heatmap: transfer limit per bus (MW), the lowest over the seasons of the newest study year (computed)",
         url=LGEKU, licence="LG&E and KU public heatmap (no licence stated)", as_of=None, mapping=MW_RULE + f"; {FERC}", **HEAT)  # fmt: skip


def avista_rows(feats: list[dict]) -> list[dict]:
    """One row per bus: the largest tested injection with no limiting element (MW_Available equal to
    MW_Input on every monitored element); 0 when even the smallest step overloads one."""
    steps: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for f in feats:
        steps[f["Bus_Number"]][float(f["MW_Input"])].append(f)
    rows = []
    for bus, by in steps.items():
        ok = [s for s, fs in by.items() if all(num(f.get("MW_Available")) == s for f in fs)]
        g = max(ok) if ok else 0.0
        f0 = next(iter(by.values()))[0]
        rows.append({"id": str(bus), "name": f0.get("Bus_Name"), "lon": f0.get("_lon"), "lat": f0.get("_lat"),
                     "kv": num(f0.get("Bus_Voltage")), "mw_gen": g, "class": mw_class(g)})  # fmt: skip
    return rows


def us_avista() -> None:
    rows = avista_rows(w7.arcgis(AVISTA, page=2000))
    save("us_avista", "US-AVA", "Avista", "transmission", rows,
         source="Avista, interconnection heatmap: the largest tested injection (20-300 MW steps) with no overloaded element, per bus (computed)",
         url=AVISTA, licence="Avista public heatmap (no licence stated)", as_of=None, mapping=MW_RULE + f"; {FERC}", **HEAT,
         note="A lower bound: the true limit lies between this step and the next one tested")  # fmt: skip


CAISO_STUDY = "2025_TPD"


def us_caiso() -> None:
    res = {r["title"]: r for r in w7.get(CAISO).json()["wcResults"]}
    study = res[CAISO_STUDY]
    rows = []
    for b in study["buses"]:
        g = num(b.get("trlim"))
        name = re.sub(r"\s+\d+(\.\d+)?\s*kV$", "", b["busname"]).strip()
        rows.append(
            {
                "id": str(b["busnum"]),
                "name": name,
                "kv": num(b.get("busvolt")),
                "mw_gen": g,
                "class": mw_class(g),
            }
        )
    save("us_caiso", "US-CAISO", "CAISO", "transmission", rows,
         source=f"CAISO, POI heatmap: transmission capacity per bus (MW), study '{CAISO_STUDY}' (others: {', '.join(t for t in res if t != CAISO_STUDY)})",
         url="https://www.caiso.com/poi-heatmap/", licence="CAISO public heatmap (no licence stated)", as_of=None,
         mapping=MW_RULE + f"; {FERC}", **HEAT,
         note="The heatmap's coordinates are in an undocumented projection; positions matched to OpenStreetMap substations in California by name",
         match=True, osm_area="US-CA")  # fmt: skip


BUILDERS: dict[str, Callable[[], None]] = {
    "hr_hepods": hr_hepods, "se_vattenfall": se_vattenfall, "gb_nie": gb_nie, "tr_teias": tr_teias, "at_enetze": at_enetze,
    "cz_pre": cz_pre, "fi_helen": fi_helen, "ch_swissgrid": ch_swissgrid, "us_pgn": us_pgn, "us_idaho": us_idaho, "us_lgeku": us_lgeku,
    "us_avista": us_avista, "us_caiso": us_caiso,
}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", choices=[*BUILDERS, "all"])
    args = ap.parse_args()
    failed = []
    for key, fn in BUILDERS.items():
        if args.key in (key, "all"):
            try:
                fn()
            except (Exception, SystemExit) as e:  # noqa: BLE001 - one operator down must not stop the others
                print(f"  {key}: failed ({type(e).__name__}: {str(e)[:200]})", flush=True)
                failed.append(key)
    print(json.dumps({"failed": failed}))


if __name__ == "__main__":
    main()
