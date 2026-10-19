"""Every generating unit from the national registers (brief 22, family 2), beside MaStR (DE) and
EIA-860M (US).

    python scripts/build_registers.py gb|fr|dk|se|ie|be|fi|pt|cz|all [--lake lake-out] [--upload]

gb  DESNZ Renewable Energy Planning Database (REPD, quarterly CSV: every renewable and storage
    project from 150 kW with its planning status) and DUKES 5.11 (major power producers'
    stations, all fuels); OSGB eastings and northings converted to WGS84.
fr  ODRÉ "Registre national des installations de production et de stockage d'électricité"
    (RTE, Enedis and the local DSOs; Licence Ouverte): every installation, those under 36 kW
    grouped per commune by the source. No positions: summed per region and sector (computed),
    the largest installations listed.
dk  Energistyrelsen, master data of every wind turbine (monthly xlsx; UTM 32, ETRS89).
se  Vindbrukskollen (the county boards and the Energy Agency): every wind turbine built or
    permitted (ArcGIS layers).
ie  SEAI, wind farms connected (June 2022, from EirGrid and ESB Networks reports; CC BY 4.0),
    placed at their 110 kV node's Irish Grid coordinates as published.
be  Elia open data ods179: the contracted technical units (transmission), Pmax and fuel; no
    positions.
fi  Energy Authority (Energiavirasto) power plant register (xlsx).
pt  DGEG, power plants licensed or being licensed: wind, solar, thermal, hydro (ArcGIS, CC BY 4.0).
cz  ERÚ, every licensed generation plant (monthly XML, TEZ group 11); no positions.

Each writes frontend/public/data/eu/registers/<cc>.json (points [name, lon, lat, group, MW,
status, year] and/or a table, totals by group and status, computed) and a lake table
registers/<cc> (snapshot partition).
"""

from __future__ import annotations

import argparse
import csv
import io
import re
from collections import defaultdict
from pathlib import Path

import wave5_common as w
import wave7_common as w7

OUT = w.EU / "registers"
SCRIPT = "scripts/build_registers.py"
# the map's colour groups (the app's FUEL_COLOR keys where they exist)
GROUPS = [
    (r"offshore", "wind_offshore"), (r"wind|vind|éolien|eolien|větrn", "wind"),
    (r"solar|photovolta|pv\b|sol\b|solár|sluneční", "solar"), (r"batter|storage|stockage|lagring|akumul", "storage"),
    (r"pumped|pompage|přečerpávací", "storage"), (r"hydro|water|hydraul|tidal|wave|marine|vattenkraft|vodní", "hydro"),
    (r"nuclear|nucléaire|nucleaire|jadern", "nuclear"), (r"coal|charbon|lignite|uhlí", "coal"),
    (r"bio|landfill|sewage|anaerobic|waste|efw|déchets|dechets|wood|bois|skládkov|kalov|dřevoplyn", "bio"),
    (r"gas|ccgt|ocgt|gaz|chp|plyn", "gas"), (r"oil|diesel|fioul|pétrole|petrole|olej|kapaln|propan", "oil"),
]  # fmt: skip
STATUS = ["operating", "construction", "permitted", "planning"]


def group_of(*texts: str | None) -> str:
    t = " ".join(x for x in texts if x).lower()
    for pat, g in GROUPS:
        if re.search(pat, t):
            return g
    return "other"


def totals(points: list[list]) -> dict[str, dict[str, list[float]]]:
    """{status: {group: [units, MW]}} over the points (computed sums)."""
    out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for p in points:
        t = out[p[5]][p[3]]
        t[0] += 1
        t[1] = round(t[1] + (p[4] or 0), 3)
    return {s: dict(g) for s, g in out.items()}


def write(cc: str, *, source: str, url: str, licence: str, note: str, points: list[list], rows: list[dict],
          args: argparse.Namespace, table: list | None = None, table_columns: list | None = None,
          updated: str | None = None, sum_note: str = "", unit: str = "MW") -> None:  # fmt: skip
    data = {
        "fetched": w.now(), "cc": cc, "source": source, "url": url, "licence": licence, "updated": updated,
        "note": note, "unit": unit, "sum_note": sum_note or "units and MW summed over the register's rows (computed)",
        "totals": totals(points), "points": points, "table_columns": table_columns or [], "table": table or [],
    }  # fmt: skip
    w.write_json(OUT / f"{cc.lower()}.json", data)
    print(
        f"  {cc}: {len(points)} points, {len(table or [])} table rows, {len(rows)} lake rows",
        flush=True,
    )
    for r in rows:
        r.setdefault("iso2", cc)
    geo = ("lon", "lat") if rows and "lon" in rows[0] else None
    w7.lake_rows("registers", [(cc.lower(), rows, ["name"], geo)], lake_dir=args.lake, upload=args.upload,
                 source=source, licence=licence, script=SCRIPT)  # fmt: skip


def transformer(epsg: int):  # noqa: ANN201
    from pyproj import Transformer

    return Transformer.from_crs(epsg, 4326, always_xy=True)


def year_of(text: object) -> int | None:
    m = re.search(r"(19|20)\d\d", str(text or ""))
    return int(m.group(0)) if m else None


# ---------------------------------------------------------------- Great Britain (and Northern Ireland)

REPD_PAGE = "https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract"
DUKES_PAGE = "https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes"
REPD_STATUS = {
    "Operational": "operating", "Under Construction": "construction", "Awaiting Construction": "permitted",
    "Application Submitted": "planning", "Appeal Lodged": "planning", "No Application Required": "permitted",
}  # fmt: skip


def repd_points(text: str, tr) -> list[dict]:  # noqa: ANN001 - a pyproj Transformer
    """REPD rows still alive (operational, being built, permitted, in planning)."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        st = REPD_STATUS.get((r.get("Development Status (short)") or "").strip())
        x, y = w7.number(r.get("X-coordinate")), w7.number(r.get("Y-coordinate"))
        if not st or x is None or y is None:
            continue
        lon, lat = tr.transform(x, y)
        tech = r.get("Technology Type")
        out.append({"id": r.get("Ref ID"), "name": r.get("Site Name"), "operator": r.get("Operator (or Applicant)"), "tech": tech,
                    "group": group_of(tech, r.get("Storage Type")), "mw": w7.number(r.get("Installed Capacity (MWelec)")), "status": st,
                    "year": year_of(r.get("Operational")), "country": r.get("Country"), "lon": round(lon, 4), "lat": round(lat, 4), "register": "REPD"})  # fmt: skip
    return out


def dukes_points(path: Path, tr) -> list[dict]:  # noqa: ANN001
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["5.11 Full list"]
    rows = ws.iter_rows(values_only=True)
    head: list = []
    for r in rows:
        if r and r[0] and str(r[0]).startswith("Company Name"):
            head = [str(h or "") for h in r]
            break
    idx = {h.split(" [")[0].replace("\n", " "): i for i, h in enumerate(head)}
    out = []
    for r in rows:
        if not r or not r[idx["Site Name"]]:
            continue
        x, y = w7.number(r[idx["X-Coordinate"]]), w7.number(r[idx["Y-Coordinate"]])
        if x is None or y is None:
            continue
        lon, lat = tr.transform(x, y)
        tech, fuel = r[idx["Technology"]], r[idx["Primary Fuel"]]
        out.append({"id": r[idx.get("DESNZ site code", 0)], "name": r[idx["Site Name"]], "operator": r[idx["Company Name"]], "tech": f"{tech} ({fuel})",
                    "group": group_of(str(fuel or ""), str(tech or "")), "mw": w7.number(r[idx["InstalledCapacity (MW)"]]), "status": "operating",
                    "year": year_of(r[idx["Year Commissioned"]]), "country": r[idx["Country"]], "lon": round(lon, 4), "lat": round(lat, 4), "register": "DUKES 5.11"})  # fmt: skip
    return out


def link(page: str, pattern: str) -> str:
    links = re.findall(
        rf'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*{pattern})"', w7.get(page).text
    )
    if not links:
        raise SystemExit(f"{page}: no link matching {pattern}")
    return links[0]


def build_gb(args: argparse.Namespace) -> None:
    tr = transformer(27700)
    repd_url = link(REPD_PAGE, r"REPD[^\"]*\.csv")
    rows = repd_points(w7.get(repd_url).content.decode("latin-1"), tr)
    dukes_url = link(DUKES_PAGE, r"DUKES_5\.11\.xlsx")
    w7.TMP.mkdir(parents=True, exist_ok=True)
    path = w7.TMP / "dukes_5_11.xlsx"
    path.write_bytes(w7.get(dukes_url).content)
    # DUKES lists renewables REPD already holds: only the fuels REPD does not cover are taken from it
    rows += [
        r
        for r in dukes_points(path, tr)
        if r["group"] in ("gas", "coal", "nuclear", "oil", "other")
    ]
    pts = [
        [r["name"], r["lon"], r["lat"], r["group"], r["mw"], r["status"], r["year"], r["register"]]
        for r in rows
    ]
    write("GB", source="DESNZ Renewable Energy Planning Database (REPD) and DUKES 5.11 power stations", url=REPD_PAGE,
          licence="Open Government Licence v3.0", updated=re.search(r"REPD[^/]*\.csv", repd_url).group(0) if repd_url else None,  # type: ignore[union-attr]
          note="Every renewable and storage project of 150 kW or more in the planning system (REPD: operational, being built, permitted, in planning; refused, withdrawn and expired left out) and the major power producers' stations of the fuels REPD does not cover: gas, coal, nuclear, oil and other (DUKES 5.11). The UK, Northern Ireland included.",
          points=pts, rows=rows, args=args)  # fmt: skip


# ---------------------------------------------------------------- France

ODRE = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/registre-national-installation-production-stockage-electricite-agrege/exports/json"


def fr_rows(recs: list[dict]) -> list[dict]:
    out = []
    for r in recs:
        kw = w7.number(r.get("puismaxinstallee"))
        out.append({"name": r.get("nominstallation") or "", "commune": r.get("commune"), "insee": r.get("codeinseecommune"), "departement": r.get("departement"),
                    "region": r.get("region"), "sector": r.get("filiere"), "fuel": r.get("combustible"), "technology": r.get("technologie"),
                    "group": group_of(r.get("filiere"), r.get("technologie"), r.get("combustible")), "mw": round(kw / 1000, 4) if kw is not None else None,
                    "installations": w7.number(r.get("nbinstallations")), "connected": r.get("dateraccordement"), "operator": r.get("gestionnaire"), "regime": r.get("regime")})  # fmt: skip
    return out


def build_fr(args: argparse.Namespace) -> None:
    rows = fr_rows(w7.get(ODRE, timeout=600).json())
    by: dict[tuple, list[float]] = defaultdict(lambda: [0, 0.0])
    for r in rows:
        t = by[(r["region"] or "–", r["group"])]
        t[0] += int(r["installations"] or 1)
        t[1] += r["mw"] or 0
    table = [
        [reg, g, int(n), round(mw, 1)]
        for (reg, g), (n, mw) in sorted(by.items(), key=lambda kv: -kv[1][1])
    ]
    big = sorted((r for r in rows if (r["mw"] or 0) >= 50), key=lambda r: -(r["mw"] or 0))
    write("FR", source="ODRÉ, Registre national des installations de production et de stockage d'électricité", url="https://odre.opendatasoft.com/explore/dataset/registre-national-installation-production-stockage-electricite-agrege/",
          licence="Licence Ouverte (Etalab) v2.0", points=[], rows=rows, args=args, table_columns=["Region", "Group", "Installations", "MW"], table=table,
          note=f"Every installation connected to the public grids (installations under 36 kW grouped per commune by the source); no positions published, so no map points. {len(big)} installations of 50 MW or more in the lake.",
          sum_note="installations and MW summed per region and group (computed); MW = maximum installed power as published (kW / 1000)")  # fmt: skip


# ---------------------------------------------------------------- Denmark

ENS_PAGE = "https://ens.dk/analyser-og-statistik/data-oversigt-over-energisektoren"


def dk_rows(path: Path) -> list[dict]:
    """The 'Vinddata' sheet: one row per turbine (GSRN), header on the third line; turbines with a
    decommissioning date are kept as 'decommissioned' in the lake and left off the map."""
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    for r in it:
        if r and r[0] and str(r[0]).startswith("Møllenummer"):
            break
    tr = transformer(25832)
    out = []
    for r in it:
        if not r or not r[0]:
            continue
        x, y = w7.number(r[13]), w7.number(r[14])
        if x is None or y is None:
            continue
        lon, lat = tr.transform(x, y)
        kw = w7.number(r[4])
        place = " ".join(str(v or "") for v in r[9:11])
        out.append({"id": str(r[0]), "name": f"{r[7] or ''} {r[8] or ''}".strip() or str(r[0]), "maker": r[7], "model": r[8], "mw": round(kw / 1000, 4) if kw is not None else None,
                    "connected": str(r[2] or "")[:10] or None, "decommissioned": str(r[3] or "")[:10] or None, "offshore": "HAV" in place.upper(),
                    "municipality": r[10] if "-" in str(r[10] or "") else r[9], "rotor_m": w7.number(r[5]), "hub_m": w7.number(r[6]), "lon": round(lon, 5), "lat": round(lat, 5)})  # fmt: skip
    return out


def build_dk(args: argparse.Namespace) -> None:
    page = w7.get(ENS_PAGE).text
    m = re.search(
        r'<a[^>]+href="(/media/\d+/download)"[^>]*>\s*(?:<[^>]+>\s*)*Vinddata \(ultimo ([^)]+)\)',
        page,
    )
    if not m:
        raise SystemExit("ENS: no 'Vinddata' link")
    w7.TMP.mkdir(parents=True, exist_ok=True)
    path = w7.TMP / "dk_wind.xlsx"
    path.write_bytes(w7.get("https://ens.dk" + m.group(1)).content)
    rows = dk_rows(path)
    live = [r for r in rows if not r["decommissioned"]]
    pts = [
        [
            r["name"],
            r["lon"],
            r["lat"],
            "wind_offshore" if r["offshore"] else "wind",
            r["mw"],
            "operating",
            year_of(r["connected"]),
            "ENS",
        ]
        for r in live
    ]
    write("DK", source="Energistyrelsen, master data of wind turbines (Vinddata)", url=ENS_PAGE, licence="Danish public sector data, free reuse with the source named",
          updated=m.group(2), points=pts, rows=rows, args=args,
          note="Every wind turbine connected in Denmark, on land and at sea, with its GSRN, capacity, model and position (UTM 32, as published); turbines taken down are kept in the lake only. Other technologies: no unit register published as data.")  # fmt: skip


# ---------------------------------------------------------------- Sweden

VBK = "https://ext-geodata-nationella-visning.lansstyrelsen.se/arcgis/rest/services/LST/LST_Vindbrukskollen_vindkraftverk_och_projekteringsomraden_EXT/FeatureServer"
VBK_LAYERS = {0: "operating", 1: "permitted", 5: "planning", 3: "planning"}


def build_se(args: argparse.Namespace) -> None:
    rows = []
    for layer, st in VBK_LAYERS.items():
        for f in w7.arcgis(f"{VBK}/{layer}"):
            if f.get("_lon") is None:
                continue
            rows.append({"id": f.get("VERKID"), "name": f.get("PROJNAMN") or f.get("VERKID"), "status": st, "status_source": f.get("STATUS"),
                         "mw": f.get("MAXEFFEKT"), "height_m": f.get("TOTALHOJD"), "maker": f.get("FABRIKAT"), "model": f.get("MODELL"),
                         "owner": f.get("ORGNAMN"), "offshore": (f.get("PLACERING") or "").lower().startswith("vatten"), "municipality": f.get("KOMNAMN"),
                         "built": w.datetime.fromtimestamp(f["UPPFORT"] / 1000, w.UTC).date().isoformat() if isinstance(f.get("UPPFORT"), int | float) else None,
                         "lon": f["_lon"], "lat": f["_lat"]})  # fmt: skip
    pts = [
        [
            r["name"],
            r["lon"],
            r["lat"],
            "wind_offshore" if r["offshore"] else "wind",
            r["mw"],
            r["status"],
            year_of(r["built"]),
            "Vindbrukskollen",
        ]
        for r in rows
    ]
    write("SE", source="Vindbrukskollen (Länsstyrelserna and Energimyndigheten)", url="https://vbk.lansstyrelsen.se/", licence="public geodata of the county administrative boards; reuse with the source named",
          points=pts, rows=rows, args=args,
          note="Every wind turbine built, permitted, being handled or appealed, as the county boards record it (MW = the turbine's maximum power as given). Other technologies: no unit register published as data.")  # fmt: skip


# ---------------------------------------------------------------- Ireland

SEAI = "https://seaiopendata.blob.core.windows.net/wind/WindFarmsConnectedJune2022.csv"


def build_ie(args: argparse.Namespace) -> None:
    tr = transformer(29903)  # Irish Grid (TM75), the "Nat Grid" eastings and northings
    rows = []
    for r in csv.DictReader(io.StringIO(w7.get(SEAI).content.decode("utf-8-sig"))):
        x, y = (
            w7.number(r.get("Nat_Grid_E__substation_")),
            w7.number(r.get("Nat_Grid_N__substation_")),
        )
        if x is None or y is None:
            continue
        lon, lat = tr.transform(x, y)
        mw = w7.number(r.get("Installed_Capacity__MW_"))
        rows.append({"name": r.get("Windfarm_Name"), "grid": r.get("DSO_TSO"), "county": r.get("County"), "status_source": r.get("Present_Status"),
                     "mw": mw if mw is not None else w7.number(r.get("MEC__MW_")), "mw_is_mec": mw is None, "node": r.get("F110kV_Node_Name"),
                     "year": year_of(r.get("Year_of_Connection")), "lon": round(lon, 5), "lat": round(lat, 5)})  # fmt: skip
    pts = [
        [r["name"], r["lon"], r["lat"], "wind", r["mw"], "operating", r["year"], "SEAI"]
        for r in rows
    ]
    write("IE", source="SEAI, wind farms connected in Ireland (June 2022)", url="https://data.gov.ie/dataset/wind-farms-in-ireland", licence="CC BY 4.0",
          updated="2022-06", points=pts, rows=rows, args=args,
          note="Wind farms connected by June 2022 (SEAI from EirGrid and ESB Networks reports), placed at their substation's coordinates as published; installed MW, or the export capacity (MEC) where no installed MW is given. Ireland publishes no current unit register as data.")  # fmt: skip


# ---------------------------------------------------------------- Belgium

ELIA = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods179/exports/json"


def build_be(args: argparse.Namespace) -> None:
    recs = w7.get(ELIA, timeout=300).json()
    if not recs:
        raise SystemExit("Elia ods179: empty")
    print(f"  ods179 columns: {list(recs[0])}", flush=True)
    key = lambda r, *names: next((r[k] for k in r for n in names if n in k.lower()), None)  # noqa: E731
    rows = [
        {
            "name": key(r, "name", "unit"),
            "fuel": key(r, "fuel"),
            "type": key(r, "type"),
            "mw": w7.number(key(r, "pmax", "capacity")),
            **{k: v for k, v in r.items()},
        }
        for r in recs
    ]
    seen: dict[str, dict] = {}
    for r in rows:  # the dataset is daily: keep each unit's newest row
        seen[str(r["name"])] = r
    units = sorted(seen.values(), key=lambda r: -(r["mw"] or 0))
    table = [
        [r["name"], group_of(str(r["fuel"] or ""), str(r["type"] or "")), r["fuel"], r["mw"]]
        for r in units
    ]
    write("BE", source="Elia open data ods179, individual data of contracted technical units", url="https://opendata.elia.be/explore/dataset/ods179/", licence="Elia open data terms (reuse with the source named)",
          points=[], rows=units, args=args, table_columns=["Unit", "Group", "Fuel", "MW"], table=table,
          note="Units under a scheduling-agent and outage-planning contract with Elia (the large, transmission-connected ones), technical Pmax as published; no positions. Belgium publishes no register of every unit as data.")  # fmt: skip


# ---------------------------------------------------------------- Finland

FI_PAGE = "https://energiavirasto.fi/voimalaitosrekisteri"


def build_fi(args: argparse.Namespace) -> None:
    import openpyxl

    page = w7.get(FI_PAGE).text
    links = re.findall(r'href="([^"]+\.xlsx)"', page)
    if not links:
        raise SystemExit("Energiavirasto: no xlsx link")
    url = links[0] if links[0].startswith("http") else "https://energiavirasto.fi" + links[0]
    w7.TMP.mkdir(parents=True, exist_ok=True)
    path = w7.TMP / "fi_plants.xlsx"
    path.write_bytes(w7.get(url).content)
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    head = next(r for r in it if r and sum(1 for c in r if c) >= 5)
    print(f"  columns: {head}", flush=True)
    rows = [{str(h): v for h, v in zip(head, r, strict=False) if h} for r in it if r and any(r)]
    name_k = next(k for k in rows[0] if re.search(r"nimi|name", k, re.I))
    mw_k = next(
        (k for k in rows[0] if re.search(r"maksimiteho|max.*mw|kapasiteetti|teho", k, re.I)), None
    )
    type_k = next(
        (k for k in rows[0] if re.search(r"tyyppi|type|energialähde|fuel", k, re.I)), None
    )
    table = sorted(
        (
            [
                r[name_k],
                group_of(str(r.get(type_k) or "")),
                r.get(type_k),
                w7.number(r.get(mw_k)) if mw_k else None,
            ]
            for r in rows
        ),
        key=lambda t: -(t[3] or 0),
    )
    write("FI", source="Energiavirasto (Energy Authority), power plant register", url=FI_PAGE, licence="Energy Authority open data (CC BY 4.0)",
          points=[], rows=[{"name": r[name_k], **{k: (str(v) if v is not None else None) for k, v in r.items()}} for r in rows], args=args,
          table_columns=["Plant", "Group", "Type", "MW"], table=table, note="Every power plant in the Energy Authority's register; no positions published.")  # fmt: skip


# ---------------------------------------------------------------- Portugal (DGEG)

DGEG = "https://servergeo.dgeg.gov.pt/arcgis/rest/services/Visualizadores"
DGEG_LAYERS = {"CE": "wind", "CS": "solar", "CT": "bio", "CH": "hydro"}


def dgeg_rows(code: str, feats: list[dict]) -> list[dict]:
    """One row per park (and sub-park): the layers have one polygon per block (a turbine or a
    field), so blocks are merged (first block's values, centroid of all). Wind: capacity = the
    blocks' generator kW summed (the park kVA field repeats or disagrees); other layers: the park's
    installed kVA."""
    parks: dict[tuple, dict] = {}
    for f in feats:
        key = (
            (f.get("processo"), f.get("subparque"))
            if code == "CE"
            else (f.get("processo"), f.get("subparque"), f.get("potencia_instaladakva"))
        )
        polys = f.get("_polys") or []
        xs = [c for poly in polys for ring in poly[:1] for c in ring[0::2]]
        ys = [c for poly in polys for ring in poly[:1] for c in ring[1::2]]
        if not xs:
            continue
        p = parks.setdefault(key, {"xs": [], "ys": [], "f": f, "kw": 0.0})
        p["kw"] += w7.number(f.get("potencia_geradorkw")) or 0
        p["xs"] += xs
        p["ys"] += ys
    out = []
    for p in parks.values():
        f = p["f"]
        kva = w7.number(f.get("potencia_instaladakva"))
        if (
            code == "CE"
        ):  # wind: the blocks' generator kW summed (the park's kVA field is not consistent)
            kva = p["kw"]
        operating = bool(f.get("lic_exploracao"))
        out.append({"id": f.get("inspireid"), "name": " / ".join(x for x in (f.get("nome"), f.get("subparque")) if x), "owner": f.get("proprietario"),
                    "type": code, "subtype": f.get("subtipo_instalacao"), "group": DGEG_LAYERS[code] if code != "CT" else group_of(f.get("subtipo_instalacao")),
                    "mw": round(kva / 1000, 3) if kva is not None else None, "status": "operating" if operating else "permitted",
                    "licence_operation": f.get("lic_exploracao"), "licence_production": f.get("lic_producao"), "municipality": f.get("concelho"), "district": f.get("distrito"),
                    "lon": round(sum(p["xs"]) / len(p["xs"]), 5), "lat": round(sum(p["ys"]) / len(p["ys"]), 5)})  # fmt: skip
    return out


def build_pt(args: argparse.Namespace) -> None:
    rows = []
    for code in DGEG_LAYERS:
        rows += dgeg_rows(code, w7.arcgis(f"{DGEG}/{code}/FeatureServer/0"))
    pts = [
        [r["name"], r["lon"], r["lat"], r["group"], r["mw"], r["status"], None, "DGEG"]
        for r in rows
    ]
    write("PT", source="DGEG, power plants licensed or being licensed (wind, solar, thermal, hydro)", url="https://dados.gov.pt/pt/datasets/?organization=dgeg",
          licence="CC BY 4.0 (dados.gov.pt, High Value Dataset)", points=pts, rows=rows, args=args,
          note="Mainland Portugal's power plants in DGEG's licensing (production licence, and operation licence when operating), placed at the centre of their area; wind: the turbines' generator kW summed per park (computed), others: installed kVA as published, shown as MVA.",
          unit="MVA", sum_note="parks summed per status and group (computed); capacity in MVA (installed kVA / 1000)")  # fmt: skip


# ---------------------------------------------------------------- Czechia (ERÚ)

ERU_PAGE = "https://data.gov.cz/datová-sada?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatové-sady%2F70894451%2F1713221853"
ERU_XML = "https://eru.gov.cz/sites/default/files/obsah/prilohy/tez-sk-11-{date}.xml"


def eru_rows(path: Path) -> list[dict]:
    """One row per licensed generating plant (PremiseElec) of the active licence versions: MW
    summed over its sources as published (OutputElec, MW)."""
    import xml.etree.ElementTree as ET

    out = []
    for _, lic in ET.iterparse(path, events=("end",)):
        if lic.tag != "LicTable":
            continue
        if (lic.findtext("VersionStatusDes") or "").startswith("Aktivní"):
            for pr in lic.iter("PremiseElec"):
                outs = pr.findall("PremiseElecOutputsGroup/PremiseElecOutput")
                mw = sum(w7.number(o.findtext("OutputElec")) or 0 for o in outs)
                fuels = sorted({o.findtext("FuelTypeDes") or "" for o in outs} - {""})
                kind = pr.findtext("TechnicalData/ElecPremiseTypeDes")
                out.append({"licence": lic.findtext("LicId"), "id": pr.findtext("PremiseElecId"), "name": pr.findtext("Name"), "type": kind,
                            "fuels": ", ".join(fuels), "group": group_of(kind, " ".join(fuels)), "mw": round(mw, 5), "sources": len(outs),
                            "city": pr.findtext("City"), "district": pr.findtext("County"), "region": pr.findtext("State"), "since": pr.findtext("DateBegin")})  # fmt: skip
        lic.clear()
    return out


def build_cz(args: argparse.Namespace) -> None:
    from datetime import date, timedelta

    w7.TMP.mkdir(parents=True, exist_ok=True)
    path = w7.TMP / "cz_tez.xml"
    day, url = date.today(), None
    for _ in range(62):  # the newest monthly file (published on the 1st)
        candidate = ERU_XML.format(date=day.replace(day=1).isoformat())
        try:
            path.write_bytes(w7.get(candidate, tries=1, timeout=300).content)
            url = candidate
            break
        except SystemExit:
            day = day.replace(day=1) - timedelta(days=1)
    if not url:
        raise SystemExit("ERÚ: no monthly file found")
    rows = eru_rows(path)
    by: dict[tuple, list[float]] = defaultdict(lambda: [0, 0.0])
    for r in rows:
        t = by[(r["region"] or "–", r["group"])]
        t[0] += 1
        t[1] += r["mw"] or 0
    table = [
        [reg, g, int(n), round(mw, 1)]
        for (reg, g), (n, mw) in sorted(by.items(), key=lambda kv: -kv[1][1])
    ]
    write("CZ", source="ERÚ (Energy Regulatory Office), licensed electricity generation plants (TEZ group 11)", url=url,
          licence="Czech open data (data.gov.cz), reuse with the source named", points=[], rows=rows, args=args, updated=url.rsplit("-11-", 1)[-1][:10],
          table_columns=["Region", "Group", "Plants", "MW"], table=table,
          note="Every plant under an active generation licence, with its sources' electrical output as published; no positions (municipality and cadastre only), so no map points. Plants under 50 kW without a licence are not in it.",
          sum_note="plants and MW summed per region and group (computed)")  # fmt: skip


BUILDERS = {
    "gb": build_gb,
    "fr": build_fr,
    "dk": build_dk,
    "se": build_se,
    "ie": build_ie,
    "be": build_be,
    "fi": build_fi,
    "pt": build_pt,
    "cz": build_cz,
}


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
