"""Room to connect, the operators brief 23 adds (probes: scripts/probe_connect_<cc>.py).

    python scripts/build_connect_h23.py all|<key> [--lake lake-out] [--upload]

Each operator becomes frontend/public/data/eu/connect/h_<key>.json, already in the harmonised
rows of scripts/build_connect_harmonised.py (which reads every h_*.json): values as published,
the operator's own classes mapped one to one to available | limited | queue | none (the mapping
is in each file and in docs/DATA_SOURCES.md), MW only where published (MVA kept as MVA). A node
without coordinates is matched to an OpenStreetMap substation by name in the harmonised build,
only where the match is unique.

  key            operator                                    what
  de_50hertz     50Hertz (DE)                                JSON behind the grid-capacity map
  de_amprion     Amprion (DE)                                PDF table, potential connection points
  es_edis        e-distribución (ES)                         CNMC CSVs, generation and demand
  es_edp         Viesgo, E-Redes España, Begasa (ES)         Opendatasoft, CC BY 4.0
  gb_nged        NGED (GB)                                   LTDS capacity heatmap JSON
  gb_ssen        SSEN (GB)                                   headroom dashboard CSV, CC BY 4.0
  gb_npg         Northern Powergrid (GB)                     heat map table, Opendatasoft
  hr_hops        HOPS (HR)                                   PDF table, categories
  hu_mavir       MAVIR (HU, with the DSOs' stations)         xlsx, spare bays, injection MVA
  hu_mvm         MVM Démász, MVM Émász (HU)                  PDF tables, free capacity for load
  si_eles        ELES (SI)                                   ArcGIS, injection and withdrawal MW
  sk_zsd         ZSD, VSD (SK)                               the connectability map's CSVs
  fi_elenia      Elenia (FI)                                 ArcGIS, production and consumption MW
  gr_hedno       HEDNO (GR)                                  RES margins web app (JSON)
  us_ica         SCE, PG&E, SDG&E (US)                       ArcGIS ICA / DRP substations
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave5_common as w  # noqa: E402
import wave7_common as w7  # noqa: E402
from build_connect_eu import cnmc_rows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "connect"
MW_RULE = "MW only: more than 0 MW free -> available, 0 MW -> none"


def mw_class(v: float | None) -> str | None:
    if v is None:
        return None
    return "available" if v > 0 else "none"


def num(v: object) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    return w7.number(str(v).strip()) if v not in (None, "", "N/A", "-") else None


def save(key: str, cc: str, operator: str, level: str, rows: list[dict], *, source: str, url: str,
         licence: str, as_of: str | None, mapping: str, note: str = "", match: bool = False) -> None:  # fmt: skip
    if not rows:
        raise SystemExit(f"{key}: no rows")
    data = {"cc": cc, "operator": operator, "level": level, "source": source, "url": url, "licence": licence,
            "as_of": as_of, "mapping": mapping, "note": note, "match": match, "fetched": w.now(), "rows": rows}  # fmt: skip
    w.write_json(OUT / f"h_{key}.json", data)
    placed = sum(1 for r in rows if r.get("lon") is not None)
    print(f"  {key}: {len(rows)} rows, {placed} with a position", flush=True)


def transformer(epsg: int):  # noqa: ANN201
    from pyproj import Transformer

    return Transformer.from_crs(epsg, 4326, always_xy=True)


def pdf_text(raw: bytes) -> list[str]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return [ln for p in pdf.pages for ln in (p.extract_text() or "").splitlines()]


def pdf_tables(raw: bytes) -> list[list]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return [row for p in pdf.pages for t in p.extract_tables() for row in t]


# ---------------------------------------------------------------- Germany

HZ_PAGE = "https://www.50hertz.com/de/Netz/Netzanschluss"
HZ_API = "https://www.50hertz.com/DesktopModules/Lotes/FrequentModules/API/DigitalMap/GetDnbInfo?path=GridLoadMapVersion/map/type/gridcapacity"


def de_50hertz() -> None:
    d = w7.get(HZ_API).json()
    locs = d.get("locations") or (d.get("mapVersion") or {}).get("locations") or []
    if not locs:  # the payload nests the map version; find the list of locations
        stack = [d]
        while stack and not locs:
            x = stack.pop()
            if isinstance(x, dict):
                for k, v in x.items():
                    if k.lower() == "locations" and isinstance(v, list):
                        locs = v
                    elif isinstance(v, dict | list):
                        stack.append(v)
            elif isinstance(x, list):
                stack.extend(i for i in x if isinstance(i, dict | list))
    rows = []
    for loc in locs:
        c = loc.get("coordinate") or {}
        g, ld = (
            num(loc.get("availableGenerationCapacityMw")),
            num(loc.get("availableLoadCapacityMw")),
        )
        kv = num(str(loc.get("voltageLevel") or "").split("/")[0])
        rows.append({"id": str(loc.get("id")), "name": loc.get("name"), "lon": num(c.get("x")), "lat": num(c.get("y")), "kv": kv,
                     "mw_gen": g, "mw_load": ld, "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    save("de_50hertz", "DE", "50Hertz", "transmission", rows, source="50Hertz, grid-capacity map (Netzanschlusskapazität)",
         url=HZ_PAGE, licence="50Hertz website terms (public information under §14e EnWG); reuse with the source named",
         as_of=None, mapping=f"{MW_RULE}; a location without a published MW has no class")  # fmt: skip


AMPRION_PAGE = "https://www.amprion.net/Strommarkt/Netzkunden/Netzanschluss/Darstellung-der-potenziellen-Netzanschlussmoeglichkeiten-und-der-Kundenprojekte.html"


def de_amprion() -> None:
    page = w7.get(AMPRION_PAGE).text
    m = re.search(
        r'href="([^"]*Ergaenzendes-Dokument-zu-potenziellen-Netzanschlussmoeglichkeiten[^"]*\.pdf)"',
        page,
    )
    if not m:
        raise SystemExit("Amprion: no table PDF linked")
    url = m.group(1) if m.group(1).startswith("http") else "https://www.amprion.net" + m.group(1)
    rows = []
    for r in pdf_tables(w7.get(url).content):
        if len(r) < 5 or not r[0] or not re.search(r"\d+\s*kV", r[1] or ""):
            continue
        note = (r[5] or "") if len(r) > 5 else ""
        load_only = "ausschließlich Lastanschlüsse" in note
        rows.append({"name": r[0].strip(), "kv": num(re.findall(r"(\d+)", r[1])[0]),
                     "class": "none" if load_only else "limited", "class_load": "limited"})  # fmt: skip
    as_of = re.search(r"(\d{2})\.(\d{4})\.pdf", url)
    save("de_amprion", "DE", "Amprion", "transmission", rows, source="Amprion, potential connection points (non-binding first assessment), PDF table",
         url=url, licence="Amprion website (information only, without warranty)", as_of=f"{as_of.group(2)}-{as_of.group(1)}" if as_of else None,
         mapping="a potential connection point with an earliest commissioning year (2032-2035) -> limited; 'only load connections possible' -> generation none",
         note="No MW published; no positions: matched to OpenStreetMap by name where unique", match=True)  # fmt: skip


# ---------------------------------------------------------------- Spain

EDIS_GEN = (
    "https://www.edistribucion.com/es/red-electrica/nodos-capacidad-red/capacidad-generacion.html"
)
EDIS_DEM = (
    "https://www.edistribucion.com/es/red-electrica/nodos-capacidad-red/capacidad-demanda.html"
)


def edis_files(page_url: str, kind: str) -> tuple[str, list[str]]:
    page = w7.get(page_url).text
    links = sorted(
        set(re.findall(rf'href="([^"]+/nodos/{kind}/(\d{{6}})/[^"]+\.csv)"', page)),
        key=lambda t: t[1],
    )
    if not links:
        raise SystemExit(f"e-distribución {kind}: no CSV links")
    month = links[-1][1]
    return month, [
        h if h.startswith("http") else "https://www.edistribucion.com" + h
        for h, m in links
        if m == month
    ]


def es_edis() -> None:
    month, gen_urls = edis_files(EDIS_GEN, "generacion")
    _, dem_urls = edis_files(EDIS_DEM, "demanda")
    gen = [
        r
        for u in gen_urls
        for r in cnmc_rows(w7.get(u).content.decode("utf-8-sig", errors="replace"))
    ]
    dem: dict[tuple, float | None] = {}
    for u in dem_urls:
        text = w7.get(u).content.decode("utf-8-sig", errors="replace")
        rd = csv.DictReader(io.StringIO(text), delimiter=";")
        for r in rd:
            key = (r.get("Subestación", "").strip(), num(r.get("Nivel de Tensión (kV)")))
            dem[key] = num(r.get("Capacidad firme disponible (MW)"))
    rows = []
    for r in gen:
        ld = dem.get((r["code"] or "", r["kv"]))
        rows.append({"id": f"{r['code']}-{r['kv']:g}" if r["kv"] else r["code"], "name": r.get("name") or r["code"], "lon": r["lon"],
                     "lat": r["lat"], "kv": r["kv"], "mw_gen": r["available_mw"], "mw_load": ld, "mw_queue": r["pending_mw"],
                     "class": mw_class(r["available_mw"]), "class_load": mw_class(ld)})  # fmt: skip
    save("es_edis", "ES", "e-distribución (Endesa)", "distribution", rows,
         source="e-distribución, access capacity for generation and for demand per node (CNMC format, monthly)", url=EDIS_GEN,
         licence="published under CNMC Circular 1/2024; reuse with the source named", as_of=f"{month[:4]}-{month[4:]}",
         mapping=f"{MW_RULE} (demand: firm capacity available); joined by substation code and voltage")  # fmt: skip


EDP_ODS = "https://redes-spain.opendatasoft.com/api/explore/v2.1/catalog/datasets"
EDP_OPS = {"viesgo": "Viesgo", "e-redes": "E-Redes España", "begasa": "Begasa"}


def es_edp() -> None:
    for slug, name in EDP_OPS.items():
        gen = list(
            csv.DictReader(
                io.StringIO(
                    w7.get(
                        f"{EDP_ODS}/7-capacidad-disponible-generacion-{slug}/exports/csv",
                        params={"delimiter": ";"},
                    ).text.lstrip("﻿")
                ),
                delimiter=";",
            )
        )
        con = list(csv.DictReader(io.StringIO(w7.get(f"{EDP_ODS}/8-capacidad-disponible-consumo-{slug}/exports/csv", params={"delimiter": ";"}).text.lstrip("﻿")), delimiter=";"))  # fmt: skip
        load = {(r["subestacion"], num(r["nt"])): num(r["capacidad_disponible"]) for r in con}
        rows, month = [], None
        for r in gen:
            lat, lon = (
                num(r.get("latitud_fmt") or r.get("latitud")),
                num(r.get("longitud_fmt") or r.get("longitud")),
            )
            kv = num(r["nt"])
            g, ld = num(r["capacidad_disponible"]), load.get((r["subestacion"], kv))
            month = month or (r.get("data") or "")[:7]
            rows.append({"id": f"{r['subestacion']}-{kv:g}" if kv else r["subestacion"], "name": r["subestacion"], "lon": lon, "lat": lat,
                         "kv": kv, "mw_gen": g, "mw_load": ld, "mw_queue": num(r.get("capacidad_admitida")),
                         "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
        save(f"es_edp_{slug.replace('-', '')}", "ES", name, "distribution", rows,
             source=f"{name}, capacidad disponible de generación y de consumo (EDP España open data)",
             url=f"https://redes-spain.opendatasoft.com/explore/dataset/7-capacidad-disponible-generacion-{slug}/",
             licence="CC BY 4.0", as_of=month, mapping=f"{MW_RULE}; generation and consumption joined by substation and voltage")  # fmt: skip


# ---------------------------------------------------------------- Great Britain

NGED_PKG = "https://connecteddata.nationalgrid.co.uk/api/3/action/package_show"
RAG = {"green": "available", "amber": "limited", "red": "none"}


def gb_nged() -> None:
    pkg = w7.get(NGED_PKG, params={"id": "ltds-capacity-heatmap"}).json()["result"]
    rows, as_of = [], pkg.get("metadata_modified", "")[:10]
    for res in pkg["resources"]:
        if (res.get("format") or "").upper() != "JSON":
            continue
        for r in w7.get(res["url"]).json():
            g, ld = num(r.get("generationAvailableCapacity")), num(r.get("demandAvailableCapacity"))
            rows.append({"id": str(r.get("mRID")), "name": r.get("name"), "lon": num(r.get("longitude")), "lat": num(r.get("latitude")),
                         "kv": num(str(r.get("voltages") or "").split("-")[0]), "mw_gen": g, "mw_load": ld,
                         "class": RAG.get(str(r.get("generationConstraint")).strip().lower()),
                         "class_load": RAG.get(str(r.get("demandConstraint")).strip().lower())})  # fmt: skip
    save("gb_nged", "GB", "National Grid Electricity Distribution (NGED)", "distribution", rows,
         source="NGED, LTDS capacity heatmap (BSP and primary substations)",
         url="https://connecteddata.nationalgrid.co.uk/dataset/ltds-capacity-heatmap", licence="WPD Open Data Licence",
         as_of=as_of, mapping="NGED's constraint colour: green -> available, amber -> limited, red -> none (generation and demand each)")  # fmt: skip


SSEN_PKG = "https://data-api.ssen.co.uk/api/3/action/package_show"


def gb_ssen() -> None:
    pkg = w7.get(SSEN_PKG, params={"id": "generation-availability-and-network-capacity"}).json()[
        "result"
    ]
    res = sorted((r for r in pkg["resources"] if (r.get("format") or "").upper() == "CSV" and "headroom dashboard" in (r.get("name") or "").lower()),
                 key=lambda r: r.get("created") or "")  # fmt: skip
    if not res:
        raise SystemExit("SSEN: no headroom dashboard CSV")
    pick = res[-1]
    text = w7.get(pick["url"]).content.decode("utf-8-sig", errors="replace")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        g, mva = (
            num(r.get("Estimated Generation Headroom (MW)")),
            num(r.get("Estimated Demand Headroom (MVA)")),
        )
        rows.append({"id": r.get("AssetID"), "name": r.get("Substation"), "lon": num(r.get("Location Longitude")), "lat": num(r.get("Location Latitude")),
                     "kv": num(str(r.get("Voltage (kV)") or "").split("/")[0]), "mw_gen": g, "mva_load": mva,
                     "class": RAG.get((r.get("Substation Generation RAG Status") or "").strip().lower()),
                     "class_load": RAG.get((r.get("Substation Demand RAG Status") or "").strip().lower())})  # fmt: skip
    save("gb_ssen", "GB", "Scottish and Southern Electricity Networks (SSEN)", "distribution", rows,
         source=f"SSEN, {pick.get('name')}", url=pick["url"], licence="CC BY 4.0", as_of=(pick.get("created") or "")[:10],
         mapping="SSEN's RAG status: Green -> available, Amber -> limited, Red -> none; demand headroom is MVA, kept as MVA")  # fmt: skip


NPG = "https://northernpowergrid.opendatasoft.com/api/explore/v2.1/catalog/datasets/heatmapdatatable/exports/csv"


def gb_npg() -> None:
    text = w7.get(NPG, params={"delimiter": ";"}).content.decode("utf-8-sig", errors="replace")
    t = transformer(27700)
    rows = []
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        e, n = num(r.get("grid_easting")), num(r.get("grid_northing"))
        lon, lat = (round(v, 5) for v in t.transform(e, n)) if e and n else (None, None)
        g, ld = num(r.get("genhr")), num(r.get("demhr"))
        rows.append({"name": r.get("psp_name"), "lon": lon, "lat": lat, "kv": num(r.get("pvoltage")),
                     "mw_gen": g, "mva_load": ld, "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    save("gb_npg", "GB", "Northern Powergrid", "distribution", rows, source="Northern Powergrid, heat map data table",
         url="https://northernpowergrid.opendatasoft.com/explore/dataset/heatmapdatatable/", licence="Northern Powergrid Open Data Licence v1.0",
         as_of=None, mapping=f"{MW_RULE} (generation headroom genhr); demand headroom demhr kept as published (MVA)",
         note="Positions from the file's OSGB eastings and northings (EPSG:27700)")  # fmt: skip


# ---------------------------------------------------------------- Croatia, Hungary, Slovenia, Slovakia

HOPS_PAGE = "https://www.hops.hr/informacije-o-mogucnosti-prikljucenja"
HOPS_CLASS = {"A": "limited", "B": "available", "C": "available", "/": "none"}


def hr_hops() -> None:
    page = w7.get(HOPS_PAGE).text
    files = re.findall(r'href="(/page-file/[^"]+\.pdf)"', page)
    years = sorted(
        ((int(m.group(1)) if (m := re.search(r"_(20\d\d)\.pdf", f)) else 0), f) for f in files
    )
    url = "https://www.hops.hr" + years[-1][1].replace(" ", "%20")
    rows = []
    for row in pdf_tables(w7.get(url).content):
        for name, cat in zip(row[0::2], row[1::2], strict=False):
            if name and cat and cat.strip() in HOPS_CLASS and name.strip() != "TS/RP":
                kv = re.search(r"(\d+)\s*kV", name)
                rows.append(
                    {
                        "name": name.strip(),
                        "kv": num(kv.group(1)) if kv else None,
                        "class": HOPS_CLASS[cat.strip()],
                    }
                )
    save("hr_hops", "HR", "HOPS", "transmission", rows, source="HOPS, information on the possibility of connection to the transmission grid (PDF table)",
         url=url, licence="HOPS website (public information)", as_of=str(years[-1][0]) if years[-1][0] else None,
         mapping="HOPS's categories: A (up to 50 MW) -> limited, B (up to 100 MW) -> available, C (over 100 MW) -> available, / (0 MW or no free bay) -> none",
         note="No MW per substation and no positions: matched to OpenStreetMap by name where unique", match=True)  # fmt: skip


MAVIR_PAGE = "https://www.mavir.hu/web/mavir/halozati-csatlakozas"


def hu_mavir() -> None:
    import openpyxl

    page = w7.get(MAVIR_PAGE).text
    m = re.search(r'href="([^"]+\.xlsx[^"]*)"', page)
    if not m:
        raise SystemExit("MAVIR: no xlsx linked")
    url = m.group(1).replace("&amp;", "&")
    url = url if url.startswith("http") else "https://www.mavir.hu" + url
    ws = openpyxl.load_workbook(
        io.BytesIO(w7.get(url).content), read_only=True, data_only=True
    ).worksheets[0]
    rows = []
    for r in list(ws.iter_rows(values_only=True))[2:]:
        if not r or not r[1]:
            continue
        bays = (num(r[4]) or 0) + (num(r[5]) or 0)
        rows.append({"id": str(r[2]).strip() if r[2] else None, "name": f"{r[1]} ({r[0]})", "lon": num(r[10]), "lat": num(r[9]),
                     "kv": num(r[3]), "mva_gen": num(r[6]), "class": "available" if bays > 0 else "none"})  # fmt: skip
    save("hu_mavir", "HU", "MAVIR and the DSOs (station list)", "transmission", rows,
         source="MAVIR, station list: spare and free bays, injection capacity on MV (MVA)", url=url,
         licence="MAVIR website (disclaimer sheet in the file)", as_of=None,
         mapping="spare bays + free bays/cells offered > 0 -> available, 0 -> none; injection capacity kept as published (MVA)")  # fmt: skip


MVM = {
    "MVM Démász": ("https://mvmhalozat.hu/aram/oldalak/125383", "demasz"),
    "MVM Émász": ("https://mvmemaszhalozat.hu/uzleti-partnerek/uzleti-ugyfelek-onkormanyzatok/elosztoi-szabad-kapacitasok", "emasz"),
}  # fmt: skip


def mvm_rows(lines: list[str], layout: str) -> list[dict]:
    """Text lines of the free-capacity table as printed: Démász 'OP Name CODE n n kv kV load free load5 free5',
    Émász 'CODE Name load load5 cap cap5 free free5'."""
    out = []
    for ln in lines:
        nums = re.findall(r"\d+(?:[.,]\d+)?", ln)
        if layout == "demasz":
            m = re.match(r"^(\S+)\s+(.+?)\s+([A-ZÁÉÍÓÖŐÚÜŰ]{4})\s+[\d.,]+", ln)
            if m and "kV" in ln and len(nums) >= 7:
                out.append(
                    {
                        "name": m.group(2).strip(),
                        "id": m.group(3),
                        "kv": num(nums[2]),
                        "mw_load": num(nums[4]),
                    }
                )
        else:
            m = re.match(r"^([A-ZÁÉÍÓÖŐÚÜŰ]{4})\s+(.+?)\s+[\d.,]+\s", ln)
            if m and len(nums) >= 6:
                out.append({"name": m.group(2).strip(), "id": m.group(1), "mw_load": num(nums[4])})
    return out


def hu_mvm() -> None:
    for operator, (page_url, layout) in MVM.items():
        page = w7.get(page_url).text
        links = re.findall(r'href="([^"]*(?:attachments/\d+|downloadfile\?id=[^"]+))"', page)
        rows: list[dict] = []
        url = None
        for href in links:
            u = href.replace("&amp;", "&")
            u = u if u.startswith("http") else re.match(r"https://[^/]+", page_url).group(0) + u
            raw = w7.get(u).content
            if not raw.startswith(b"%PDF"):
                continue
            lines = pdf_text(raw)
            # the table is titled "... VÉTELEZÉSI CÉLÚ SZABAD KAPACITÁSAI" (a methodology note and
            # product sheets are linked beside it)
            if "VÉTELEZÉSI CÉLÚ" not in " ".join(lines[:3]).upper():
                continue
            found = mvm_rows(lines, layout)
            if len(found) > len(rows):
                rows, url = found, u
        for r in rows:
            r["class_load"] = mw_class(r["mw_load"])
        save(f"hu_{layout}", "HU", operator, "distribution", rows, source=f"{operator}, free capacity for load per substation (PDF table)",
             url=url or page_url, licence="operator website (public information)", as_of=None,
             mapping=f"{MW_RULE}, for load only (the table is 'vételezési célú', for withdrawal); no generation figure published",
             note="No positions: matched to OpenStreetMap by name where unique", match=True)  # fmt: skip


ELES = "https://services9.arcgis.com/xWasUKdSRn1AHmTS/arcgis/rest/services/Switchyard_Eles/FeatureServer/0"


def si_eles() -> None:
    rows = []
    for f in w7.arcgis(ELES):
        g, ld = num(f.get("GEN_MW")), num(f.get("BREM_MW"))
        rows.append({"id": str(f.get("ID_STIKALISCE")), "name": f.get("NAZIV"), "lon": f.get("_lon"), "lat": f.get("_lat"), "kv": num(f.get("NAPETOST")),
                     "mw_gen": g, "mw_load": ld, "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    save("si_eles", "SI", "ELES", "transmission", rows, source="ELES, hosting capacity of the transmission substations (ArcGIS)",
         url="https://www.eles.si/mozni-obseg-in-lokacije-prikljucevanja-ove", licence="ELES public web map (no licence stated)",
         as_of=None, mapping=MW_RULE,
         note="The DSOs' MV substation layer gives upper bounds only ('< 10.000 kW') and is not added")  # fmt: skip


SK_BASE = "https://www.zsdis.sk/dso-mapa-pripojitelnosti/ui/stanice_meta_data"
SK_OPS = {"zsd": "Západoslovenská distribučná (ZSD)", "vsd": "Východoslovenská distribučná (VSD)"}


def sk_zsd() -> None:
    for code, operator in SK_OPS.items():
        bounds = {b["id"]: b for b in w7.get(f"{SK_BASE}/{code}/vn_bounds_recalc.json").json()}
        text = w7.get(f"{SK_BASE}/{code}/VN_METRICS.csv").content.decode(
            "utf-8-sig", errors="replace"
        )
        rows, as_of = [], None
        for r in csv.DictReader(io.StringIO(text), delimiter=";"):
            b = bounds.get(r["GIS_ID"])
            g, ld = num(r.get("ES_AVL_SOURCES")), num(r.get("ES_AVL_CONSUMPTION"))
            as_of = as_of or r.get("DATUM_POSLEDNEJ_AKTUALIZACIE")
            row = {"id": r["GIS_ID"], "name": re.sub(r"^R\d+-", "", r["NAZOV_OBJEKTU"]), "mw_gen": g, "mw_load": ld,
                   "class": mw_class(g), "class_load": mw_class(ld)}  # fmt: skip
            if b:
                x0, x1, y0, y1 = b["minLng"], b["maxLng"], b["minLat"], b["maxLat"]
                row |= {"kind": "area", "lon": round((x0 + x1) / 2, 5), "lat": round((y0 + y1) / 2, 5),
                        "polygon": [[[x0, y0, x1, y0, x1, y1, x0, y1, x0, y0]]]}  # fmt: skip
            rows.append(row)
        save(f"sk_{code}", "SK", operator, "distribution", rows, source=f"{operator}, connectability map (HV/MV substations)",
             url="https://www.zsdis.sk/Uvod/Online-sluzby/Mapa-pripojitelnosti", licence="operator website (public information)",
             as_of=as_of, mapping=MW_RULE,
             note="Positions: the box the map draws around each substation (as published); a substation without one is matched by name",
             match=True)  # fmt: skip


# ---------------------------------------------------------------- Finland, Greece

ELENIA = "https://services-eu1.arcgis.com/sNo97Nomxi3o06sY/arcgis/rest/services"


def fi_elenia() -> None:
    gen = w7.arcgis(f"{ELENIA}/Tuotantokapasiteetti_piste/FeatureServer/16", geometry=False)
    con = {
        (f["Sähköasema"], f.get("Päämuuntaja")): f
        for f in w7.arcgis(f"{ELENIA}/Kulutuskapasiteetti_piste/FeatureServer/14", geometry=False)
    }
    t = transformer(3067)
    rows = []
    for f in gen:
        c = con.get((f["Sähköasema"], f.get("Päämuuntaja")), {})
        lon, lat = (
            (round(v, 5) for v in t.transform(f["X"], f["Y"])) if f.get("X") else (None, None)
        )
        g, ld = (
            num(f.get("Vapaa_tuotantokapasiteetti_MW")),
            num(c.get("Vapaa_kulutuskapasiteetti_MW")),
        )
        rows.append({"id": f.get("Päämuuntaja"), "name": f"{f['Sähköasema']} {f.get('Päämuuntaja') or ''}".strip(), "lon": lon, "lat": lat,
                     "mw_gen": g, "mw_load": ld, "class": mw_class(g), "class_load": mw_class(ld)})  # fmt: skip
    save("fi_elenia", "FI", "Elenia", "distribution", rows, source="Elenia, map of available capacity (production and consumption per main transformer)",
         url="https://www.elenia.fi/en/electricity-consumption-and-production/green-transition/map-of-available-capacity",
         licence="Elenia public web map (no licence stated)", as_of=None, mapping=MW_RULE,
         note="Positions from the layer's ETRS-TM35FIN coordinates (EPSG:3067)")  # fmt: skip


HEDNO = "https://apps.deddie.gr/WebAPE/services/views/margins"
HEDNO_CLASS = {"Green": "available", "Orange": "limited", "Red": "none"}


def gr_hedno() -> None:
    rows = []
    for r in w7.get(
        HEDNO, params={"klpe": "-1", "klno": "-1", "klot": "-1", "status": "111"}
    ).json():
        th, sc = num(r.get("TTHP")), num(r.get("TPBK"))
        rows.append({"name": r.get("PERI_M") or r.get("PERI_Y"), "id": r.get("PERI_M"), "lon": num(r.get("SYNM")), "lat": num(r.get("SYNP")),
                     "kv": 150.0, "mva_gen": min(x for x in (th, sc) if x is not None) if th is not None or sc is not None else None,
                     "class": HEDNO_CLASS.get(r.get("MARGIN_ICON"))})  # fmt: skip
    save("gr_hedno", "GR", "HEDNO", "distribution", rows, source="HEDNO, RES hosting margins per HV/MV transformer (all stations reserving capacity)",
         url="https://apps.deddie.gr/WebAPE/main.html", licence="HEDNO public web application (no licence stated)", as_of=None,
         mapping="HEDNO's availability colour: green (over 2 MVA on both criteria) -> available, orange (about 2 MVA on one) -> limited, red (zero) -> none; "
                 "mva_gen = the smaller of the thermal and the short-circuit margin (both published, the binding one taken)")  # fmt: skip


# ---------------------------------------------------------------- United States (distribution)

US_LAYERS = {
    "SCE": ("https://drpep.sce.com/arcgis_server/rest/services/Hosted/ICA_Layer/FeatureServer/18", "Southern California Edison (DRPEP)"),
    "PGE": ("https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/DRPComplianceRelProd/FeatureServer/0", "Pacific Gas and Electric (GRIP)"),
    "SDGE": ("https://services.arcgis.com/S0EUI1eVapjRPS5e/arcgis/rest/services/ICA_MAP_PROD_Substations_VW/FeatureServer/0", "San Diego Gas & Electric (ICA)"),
}  # fmt: skip


def us_ica() -> None:
    url, name = US_LAYERS["SCE"]
    rows = []
    for f in w7.arcgis(url):
        g = num(f.get("max_remain_cap"))
        rows.append({"name": f.get("sub_name"), "id": str(f.get("subst_id")), "lon": f.get("_lon"), "lat": f.get("_lat"),
                     "kv": num(str(f.get("substation_voltage") or "").split("/")[-1]), "mw_gen": g, "mw_queue": num(f.get("queued_gen")),
                     "class": mw_class(g)})  # fmt: skip
    save("us_sce", "US-SCE", name, "distribution", rows, source="SCE, DRPEP substations: maximum remaining capacity (MW)", url=url,
         licence="SCE DRPEP (information purposes only; no use restriction stated)", as_of=None, mapping=MW_RULE)  # fmt: skip
    url, name = US_LAYERS["PGE"]
    rows = []
    for f in w7.arcgis(url):
        q = num(f.get("Queued_DG"))
        rows.append({"name": f.get("SubstationName"), "id": str(f.get("SubstationID")), "lon": f.get("_lon"), "lat": f.get("_lat"),
                     "kv": num(f.get("Voltage_kV")), "mw_queue": round(q / 1000, 3) if q is not None else None,
                     "class": "queue" if q else None})  # fmt: skip
    save("us_pge", "US-PGE", name, "distribution", rows, source="PG&E, GRIP distribution substations: queued DG (kW, shown in MW)", url=url,
         licence="PG&E: 'available for general public consumption'", as_of=None,
         mapping="a substation with queued distributed generation -> queue; PG&E publishes hosting capacity per line section, not per substation",
         note="ICA per line section (2 million features) is not drawn")  # fmt: skip
    url, name = US_LAYERS["SDGE"]
    rows = []
    for f in w7.arcgis(url):
        polys = f.get("_polys")
        lon, lat = (None, None)
        if polys:
            ring = max((p[0] for p in polys), key=len)
            lon, lat = (
                round((min(ring[0::2]) + max(ring[0::2])) / 2, 5),
                round((min(ring[1::2]) + max(ring[1::2])) / 2, 5),
            )
        q = num(f.get("QUE_GEN"))
        rows.append({"name": f.get("NAME"), "id": f.get("FACILITYID"), "lon": lon, "lat": lat, "mw_queue": q,
                     "class": "queue" if q else None})  # fmt: skip
    save("us_sdge", "US-SDGE", name, "distribution", rows, source="SDG&E, ICA map substations: queued generation (MW)", url=url,
         licence="SDG&E public ICA map (no licence stated)", as_of=None,
         mapping="a substation with queued generation -> queue; SDG&E publishes hosting capacity per grid cell, not per substation",
         note="Positions: the middle of each substation area's bounding box (computed)")  # fmt: skip


BUILDERS: dict[str, Callable[[], None]] = {
    "de_50hertz": de_50hertz, "de_amprion": de_amprion, "es_edis": es_edis, "es_edp": es_edp, "gb_nged": gb_nged,
    "gb_ssen": gb_ssen, "gb_npg": gb_npg, "hr_hops": hr_hops, "hu_mavir": hu_mavir, "hu_mvm": hu_mvm, "si_eles": si_eles,
    "sk_zsd": sk_zsd, "fi_elenia": fi_elenia, "gr_hedno": gr_hedno, "us_ica": us_ica,
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
