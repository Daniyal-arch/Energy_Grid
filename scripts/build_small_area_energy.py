"""Energy figures per small area (docs/tasks/27, B3) -> lake `small_area_energy/*`.

    python scripts/build_small_area_energy.py fr|gb|nl|dk|pt|se|ie|es|us|eu|all
        [--lake lake-out] [--upload]

One schema per table, the same in every country (docs/DATA_LAKE.md):

consumption   iso3, level, code, name, year, carrier, sector, value, unit, measure, meters,
              source. Totals in MWh a year per area as published (or summed from the
              published rows: `measure` says which); averages per dwelling or per meter only as
              published, never multiplied out. A country that publishes only a coarser level
              has that level, named.
heating       iso3, level, code, name, year, category, value, unit, source: how dwellings or
              households are heated, as published (counts or shares).
poverty       iso3, level, code, name, year, indicator, value, unit, source.
renewables    GB local authorities: sites, MW and MWh per technology (DESNZ).

Sources (licence; level): Agence ORE (Licence Ouverte 2.0; IRIS, commune), DESNZ subnational
electricity and gas (OGL v3; LSOA domestic, MSOA, local authority), DESNZ renewable electricity
by local authority (OGL v3), DESNZ sub-regional fuel poverty (OGL v3; LSOA, modelled by DESNZ),
ONS Census 2021 TS046 central heating (OGL v3; LSOA), CBS Kerncijfers wijken en buurten (CC BY
4.0; buurt, wijk, gemeente; averages per dwelling), Energi Data Service (CC BY 4.0; municipality,
households), E-REDES (CC BY 4.0; municipality), SCB/Energimyndigheten TAB3654 (CC0; kommun), CSO
MEC03 (CC BY 4.0; county and Dublin postal district), ICAEN
(Catalonia municipalities), DOE LEAD 2022 (tract, modelled by DOE from the ACS), Census ACS
B25040 house heating fuel (tract; CENSUS_API_KEY optional), Eurostat ilc_mdes01 (country).
Every source is tried on its own: one that fails is named and the others still build.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import wave5_common as w

TMP = Path("/tmp/wave8/energy")
SCRIPT = "scripts/build_small_area_energy.py"
CONS = [
    ("iso3", "VARCHAR"), ("level", "VARCHAR"), ("code", "VARCHAR"), ("name", "VARCHAR"),
    ("year", "INTEGER"), ("carrier", "VARCHAR"), ("sector", "VARCHAR"), ("value", "DOUBLE"),
    ("unit", "VARCHAR"), ("measure", "VARCHAR"), ("meters", "DOUBLE"), ("source", "VARCHAR"),
]  # fmt: skip
HEAT = [
    ("iso3", "VARCHAR"), ("level", "VARCHAR"), ("code", "VARCHAR"), ("name", "VARCHAR"),
    ("year", "INTEGER"), ("category", "VARCHAR"), ("value", "DOUBLE"), ("unit", "VARCHAR"),
    ("source", "VARCHAR"),
]  # fmt: skip
POV = [
    ("iso3", "VARCHAR"), ("level", "VARCHAR"), ("code", "VARCHAR"), ("name", "VARCHAR"),
    ("year", "INTEGER"), ("indicator", "VARCHAR"), ("value", "DOUBLE"), ("unit", "VARCHAR"),
    ("source", "VARCHAR"),
]  # fmt: skip


class Rows:
    """Rows of one table, written as CSV and loaded into DuckDB with the table's types."""

    def __init__(self, name: str, cols: list[tuple[str, str]]) -> None:
        self.name, self.cols = name, cols
        TMP.mkdir(parents=True, exist_ok=True)
        self.path = TMP / f"{name}.csv"
        self.f = self.path.open("w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.n = 0

    def add(self, *row: Any) -> None:
        self.w.writerow(["" if v is None else v for v in row])
        self.n += 1

    def load(self, con: duckdb.DuckDBPyConnection) -> str:
        self.f.close()
        spec = ", ".join(f"'{c}': '{t}'" for c, t in self.cols)
        con.execute(
            f"CREATE OR REPLACE TABLE {self.name} AS SELECT * FROM read_csv('{self.path}', header = false, "
            f"columns = {{{spec}}}, nullstr = '', quote = '\"', escape = '\"')"
        )
        return self.name


def num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, int | float):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "..", ":", "x", "c", "*", "z"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------- France: Agence ORE

ORE = "https://opendata.agenceore.fr/data-fair/api/v1/datasets/{}/raw"


def fr(cons: Rows, heat: Rows, pov: Rows) -> None:
    con = duckdb.connect()
    src = "Agence ORE, consommation annuelle d'électricité et gaz (Licence Ouverte 2.0)"
    for ds, level, code, name in (
        ("consommation-annuelle-d-electricite-et-gaz-par-iris", "iris", "Code IRIS", "Nom IRIS"),
        (
            "consommation-annuelle-d-electricite-et-gaz-par-commune",
            "fr_commune",
            "code_commune",
            "nom_commune",
        ),
    ):
        f = w.download(ORE.format(ds), TMP / f"{ds}.csv", timeout=1800)
        cols = [
            c[0]
            for c in con.execute(
                f"DESCRIBE SELECT * FROM read_csv('{f}', all_varchar = true)"
            ).fetchall()
        ]
        pick = lambda *xs: next(c for c in cols if c.lower() in [x.lower() for x in xs])  # noqa: E731
        c_code, c_name = (
            pick(code, code.lower().replace(" ", "_")),
            pick(name, name.lower().replace(" ", "_")),
        )
        c_year, c_fil = pick("Année", "annee"), pick("FILIERE", "filiere")
        c_sec = pick("CODE GRAND SECTEUR", "code_grand_secteur")
        c_mwh, c_sites = (
            pick("Conso totale (MWh)", "conso_totale_mwh"),
            pick("Nb sites", "nb_sites"),
        )
        rows = con.execute(
            f"""SELECT "{c_code}", any_value("{c_name}"), TRY_CAST("{c_year}" AS INTEGER), "{c_fil}", "{c_sec}",
                       sum(TRY_CAST(replace("{c_mwh}", ',', '.') AS DOUBLE)), sum(TRY_CAST("{c_sites}" AS DOUBLE))
                FROM read_csv('{f}', all_varchar = true) GROUP BY ALL"""
        ).fetchall()
        for c, n, y, fil, sec, mwh, sites in rows:
            carrier = (
                "electricity"
                if str(fil).lower().startswith("é") or "lec" in str(fil).lower()
                else "gas"
            )
            cons.add(
                "FRA",
                level,
                c,
                n,
                y,
                carrier,
                str(sec).lower(),
                mwh,
                "MWh",
                "sum of the published rows (operators, sectors); cells under the confidentiality rule are left out by the source",
                sites,
                src,
            )
        print(f"  FR {level}: {len(rows):,} rows", flush=True)
        if level == "iris":
            c_heat = next((c for c in cols if "chauffage" in c.lower()), None)
            if c_heat:
                hrows = con.execute(
                    f"""SELECT "{c_code}", any_value("{c_name}"), TRY_CAST("{c_year}" AS INTEGER),
                               max(TRY_CAST(replace("{c_heat}", ',', '.') AS DOUBLE))
                        FROM read_csv('{f}', all_varchar = true) WHERE "{c_heat}" IS NOT NULL AND "{c_heat}" <> '' GROUP BY ALL"""
                ).fetchall()
                for c, n, y, v in hrows:
                    heat.add(
                        "FRA",
                        "iris",
                        c,
                        n,
                        y,
                        "electric heating",
                        v,
                        "% of dwellings",
                        f"{src}; '{c_heat}' (INSEE census, as published with the IRIS rows)",
                    )
                print(f"  FR heating: {len(hrows):,} IRIS-years", flush=True)


# ---------------------------------------------------------------------- Great Britain: DESNZ, ONS

GOVUK = "https://www.gov.uk/api/content/government/statistics/"


def attachments(slug: str) -> list[dict[str, str]]:
    d = w.get_json(GOVUK + slug)
    return [
        a for a in d.get("details", {}).get("attachments", []) if a.get("url", "").endswith(".xlsx")
    ]  # type: ignore[union-attr]


def xlsx_tables(path: Path, header_words: tuple[str, ...]):  # noqa: ANN201
    """(sheet, header, rows) of every sheet whose header row holds all the words."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = None
        for _ in range(40):
            r = next(rows, None)
            if r is None:
                break
            cells = [str(c or "").strip() for c in r]
            low = " | ".join(cells).lower()
            if all(h in low for h in header_words):
                header = cells
                break
        if header:
            yield ws.title, header, rows


def col(header: list[str], *words: str) -> int:
    for i, h in enumerate(header):
        if all(x in h.lower() for x in words):
            return i
    raise KeyError(words)


def gb(cons: Rows, heat: Rows, pov: Rows) -> None:
    src_c = "DESNZ subnational electricity and gas consumption statistics (OGL v3)"
    for slug, carrier in (
        ("lower-and-middle-super-output-areas-electricity-consumption", "electricity"),
        ("lower-and-middle-super-output-areas-gas-consumption", "gas"),
    ):
        for a in attachments(slug):
            t = a["title"].lower()
            level = "lsoa" if t.startswith("lsoa") else "msoa" if t.startswith("msoa") else None
            if not level:
                continue
            sector = "non_domestic" if "non" in t else "domestic"
            f = w.download(a["url"], TMP / Path(a["url"]).name)
            n = 0
            for sheet, header, rows in xlsx_tables(f, (f"{level} code", "consumption")):
                year = int(m.group(0)) if (m := re.search(r"(19|20)\d\d", sheet)) else None
                ic, iname = col(header, f"{level} code"), col(header, f"{level} name")
                it, im = col(header, "total consumption"), col(header, "number of meters")
                for r in rows:
                    if r is None or r[ic] is None:
                        continue
                    kwh = num(r[it])
                    cons.add(
                        "GBR",
                        level,
                        r[ic],
                        r[iname],
                        year,
                        carrier,
                        sector,
                        kwh / 1000 if kwh is not None else None,
                        "MWh",
                        "total as published (kWh / 1000)",
                        num(r[im]),
                        src_c,
                    )
                    n += 1
            print(f"  GB {level} {carrier} {sector}: {n:,} rows", flush=True)
    for slug, carrier in (
        ("regional-and-local-authority-electricity-consumption-statistics", "electricity"),
        ("regional-and-local-authority-gas-consumption-statistics", "gas"),
    ):
        a = next(a for a in attachments(slug) if a["title"].lower().startswith("subnational"))
        f = w.download(a["url"], TMP / Path(a["url"]).name)
        n = 0
        for sheet, header, rows in xlsx_tables(f, ("code", "total")):
            year = int(m.group(0)) if (m := re.search(r"(19|20)\d\d", sheet)) else None
            if year is None:
                continue
            try:
                ic = col(header, "code")
                iname = next(
                    i
                    for i, h in enumerate(header)
                    if "local authority" in h.lower()
                    or h.lower() in ("area", "la name", "local authority name")
                )
                tot = [
                    (i, h)
                    for i, h in enumerate(header)
                    if "total" in h.lower() and ("gwh" in h.lower() or "consumption" in h.lower())
                ]
            except (KeyError, StopIteration):
                continue
            for r in rows:
                if r is None or not r[ic] or not re.match(r"^[ENSWK]\d{8}$", str(r[ic])):
                    continue
                for i, h in tot:
                    v = num(r[i])
                    sector = (
                        "domestic"
                        if "domestic" in h.lower() and "non" not in h.lower()
                        else "non_domestic"
                        if "non" in h.lower()
                        else "all"
                    )
                    cons.add(
                        "GBR",
                        "lad",
                        r[ic],
                        r[iname],
                        year,
                        carrier,
                        sector,
                        v * 1000 if v is not None else None,
                        "MWh",
                        f"total as published ({h.strip()}, GWh x 1000)",
                        None,
                        src_c,
                    )
                    n += 1
        print(f"  GB local authorities {carrier}: {n:,} rows", flush=True)
    try:
        fp = attachments("sub-regional-fuel-poverty-report-2025-2023-data")
        f = w.download(fp[0]["url"], TMP / "fuel_poverty_2023.xlsx")
        n = 0
        for _sheet, header, rows in xlsx_tables(f, ("lsoa code", "fuel poor")):
            ic, iname = col(header, "lsoa code"), col(header, "lsoa name")
            ih, ip = (
                col(header, "number of households"),
                next(i for i, h in enumerate(header) if "proportion" in h.lower()),
            )
            ifp = next(
                i
                for i, h in enumerate(header)
                if "fuel poor" in h.lower() and "number" in h.lower()
            )
            for r in rows:
                if r is None or not r[ic]:
                    continue
                pov.add(
                    "GBR",
                    "lsoa",
                    r[ic],
                    r[iname],
                    2023,
                    "households in fuel poverty (LILEE, modelled by DESNZ)",
                    num(r[ifp]),
                    "households",
                    "DESNZ sub-regional fuel poverty 2025 report, 2023 data (OGL v3; official statistics in development)",
                )
                pov.add(
                    "GBR",
                    "lsoa",
                    r[ic],
                    r[iname],
                    2023,
                    "share of households in fuel poverty (LILEE, modelled by DESNZ)",
                    num(r[ip]),
                    "%",
                    "DESNZ sub-regional fuel poverty 2025 report, 2023 data (OGL v3)",
                )
                pov.add(
                    "GBR",
                    "lsoa",
                    r[ic],
                    r[iname],
                    2023,
                    "households",
                    num(r[ih]),
                    "households",
                    "DESNZ sub-regional fuel poverty 2025 report, 2023 data (OGL v3)",
                )
                n += 1
        print(f"  GB fuel poverty: {n:,} LSOA", flush=True)
    except (SystemExit, StopIteration, KeyError, IndexError) as e:
        print(f"  GB fuel poverty: not built ({type(e).__name__}: {e})", flush=True)
    # ONS Census 2021 TS046 central heating, per LSOA (Nomis)
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2064_1.data.csv?date=latest&geography=TYPE151&measures=20100&select=geography_code,geography_name,c2021_heating_13_name,obs_value"
    f = w.download(url, TMP / "ts046_lsoa.csv", timeout=1200)
    n = 0
    with f.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            heat.add(
                "GBR",
                "lsoa",
                r["GEOGRAPHY_CODE"],
                r["GEOGRAPHY_NAME"],
                2021,
                r["C2021_HEATING_13_NAME"],
                num(r["OBS_VALUE"]),
                "households",
                "ONS Census 2021 TS046 central heating (OGL v3), via Nomis",
            )
            n += 1
    print(f"  GB TS046: {n:,} rows", flush=True)


def gb_renewables(ren: Rows) -> None:
    a = next(
        a
        for a in attachments("regional-renewable-statistics")
        if "local authority" in a["title"].lower()
    )
    f = w.download(a["url"], TMP / Path(a["url"]).name)
    n = 0
    for sheet, header, rows in xlsx_tables(f, ("code",)):
        kind = (
            "sites"
            if "site" in sheet.lower()
            else "mw"
            if "capacity" in sheet.lower()
            else "mwh"
            if "generation" in sheet.lower()
            else None
        )
        year = int(m.group(0)) if (m := re.search(r"20\d\d", sheet)) else None
        if not kind or not year:
            continue
        ic = col(header, "code")
        iname = next(
            i for i, h in enumerate(header) if "name" in h.lower() or "local authority" in h.lower()
        )
        techs = [
            (i, h)
            for i, h in enumerate(header)
            if i not in (ic, iname)
            and h
            and "region" not in h.lower()
            and "country" not in h.lower()
        ]
        for r in rows:
            if r is None or not r[ic] or not re.match(r"^[ENSWK]\d{8}$", str(r[ic])):
                continue
            for i, h in techs:
                ren.add(
                    "GBR",
                    "lad",
                    r[ic],
                    r[iname],
                    year,
                    h.strip(),
                    kind,
                    num(r[i]),
                    "DESNZ renewable electricity by local authority (OGL v3)",
                )
                n += 1
    print(f"  GB renewables by local authority: {n:,} values", flush=True)


# ---------------------------------------------------------------------- Netherlands: CBS

CBS = "https://datasets.cbs.nl/odata/v1/CBS/{}"
# Kerncijfers wijken en buurten: measure codes of the CBS OData v1 API
CBS_CONS = {
    "M000221_2": ("electricity", "kWh per dwelling"),
    "M000219_2": ("gas", "m³ per dwelling"),
}
CBS_HEAT = {
    "M000369": "dwellings with district heating",
    "M008295": "dwellings without natural gas",
    "M008296": "dwellings with natural gas",
    "M008298": "dwellings heated mainly by electricity",
}


def cbs_values(table: str, measure: str) -> list[dict]:
    out: list[dict] = []
    url: str | None = (
        CBS.format(table)
        + f"/Observations?$filter=Measure%20eq%20'{measure}'&$select=WijkenEnBuurten,Value"
    )
    while url:
        page = w.get_json(url, timeout=300)
        out += page["value"]  # type: ignore[index]
        url = page.get("@odata.nextLink")  # type: ignore[union-attr]
    return out


def nl(cons: Rows, heat: Rows, pov: Rows) -> None:
    for table, year in (("85984NED", 2024), ("85618NED", 2023)):
        src = f"CBS Kerncijfers wijken en buurten {year}, table {table} (CC BY 4.0)"
        names: dict[str, str] = {}
        url: str | None = CBS.format(table) + "/WijkenEnBuurtenCodes"
        while url:
            page = w.get_json(url, timeout=300)
            names.update({r["Identifier"]: r["Title"] for r in page["value"]})  # type: ignore[index]
            url = page.get("@odata.nextLink")  # type: ignore[union-attr]
        filled = 0
        for m, (carrier, unit) in CBS_CONS.items():
            for r in cbs_values(table, m):
                code = r["WijkenEnBuurten"].strip()
                level = {"GM": "nl_gemeente", "WK": "nl_wijk", "BU": "nl_buurt"}.get(code[:2])
                if level and r["Value"] is not None:
                    cons.add(
                        "NLD",
                        level,
                        code,
                        names.get(code),
                        year,
                        carrier,
                        "dwellings",
                        r["Value"],
                        unit,
                        "average per dwelling as published",
                        None,
                        src,
                    )
                    filled += 1
        for m, label in CBS_HEAT.items():
            for r in cbs_values(table, m):
                code = r["WijkenEnBuurten"].strip()
                level = {"GM": "nl_gemeente", "WK": "nl_wijk", "BU": "nl_buurt"}.get(code[:2])
                if level and r["Value"] is not None:
                    heat.add(
                        "NLD",
                        level,
                        code,
                        names.get(code),
                        year,
                        label,
                        r["Value"],
                        "% of dwellings",
                        src,
                    )
        print(f"  NL {table}: {len(names):,} regions, {filled:,} consumption values", flush=True)
        if filled:
            break


# ---------------------------------------------------------------------- Denmark: Energi Data Service


def dk(cons: Rows, heat: Rows, pov: Rows) -> None:
    url = "https://api.energidataservice.dk/dataset/PrivateConsumptionHeatingMonth?limit=0"
    recs = w.get_json(url, timeout=600)["records"]  # type: ignore[index]
    agg: dict[tuple, float] = {}
    months: dict[tuple, set] = {}
    for r in recs:
        y = int(r["Month"][:4])
        k = (str(r["MunicipalityCode"]), r["Municipality"], y, r["HeatingCategory"])
        agg[k] = agg.get(k, 0.0) + (r["ConsumptionkWh"] or 0.0)
        months.setdefault((k[0], y), set()).add(r["Month"][:7])
    src = "Energi Data Service, PrivateConsumptionHeatingMonth (Energinet, CC BY 4.0)"
    n = 0
    for (code, name, y, hc), kwh in agg.items():
        if len(months[(code, y)]) < 12:
            continue  # whole years only
        cons.add(
            "DNK",
            "municipality",
            code,
            name,
            y,
            "electricity",
            f"households ({hc})",
            kwh / 1000,
            "MWh",
            "sum of the 12 monthly values as published",
            None,
            src,
        )
        n += 1
    print(
        f"  DK: {len(recs):,} monthly rows -> {n:,} municipality-years per heating category",
        flush=True,
    )


# ---------------------------------------------------------------------- Portugal: E-REDES


def pt(cons: Rows, heat: Rows, pov: Rows) -> None:
    ds = "3-consumos-faturados-por-municipio-ultimos-10-anos"
    f = w.download(
        f"https://e-redes.opendatasoft.com/api/explore/v2.1/catalog/datasets/{ds}/exports/csv?delimiter=%3B",
        TMP / f"{ds}.csv",
        timeout=1200,
    )
    with f.open(encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh, delimiter=";")
        cols = rd.fieldnames or []
        print(f"  PT columns: {cols}", flush=True)
        pick = lambda *xs: next(c for c in cols if any(x in c.lower() for x in xs))  # noqa: E731
        c_date, c_mun, c_kwh = (
            pick("ano", "data", "date"),
            pick("concelho", "munic"),
            pick("kwh", "energia"),
        )
        c_code = next(
            (
                c
                for c in cols
                if "código" in c.lower()
                or "codigo" in c.lower()
                or c.lower() in ("dicofre", "cod_concelho")
            ),
            None,
        )
        c_lvl = next(
            (
                c
                for c in cols
                if "tensão" in c.lower() or "tensao" in c.lower() or "voltage" in c.lower()
            ),
            None,
        )
        agg: dict[tuple, float] = {}
        for r in rd:
            y = int(str(r[c_date])[:4])
            k = (r[c_code] if c_code else r[c_mun], r[c_mun], y, r[c_lvl] if c_lvl else "all")
            agg[k] = agg.get(k, 0.0) + (num(r[c_kwh]) or 0.0)
    src = "E-REDES open data, consumos faturados por município (CC BY 4.0)"
    for (code, name, y, lvl), kwh in agg.items():
        cons.add(
            "PRT",
            "municipality",
            code,
            name,
            y,
            "electricity",
            f"voltage {lvl}",
            kwh / 1000,
            "MWh",
            "sum of the monthly billed values as published",
            None,
            src,
        )
    print(f"  PT: {len(agg):,} municipality-years", flush=True)


# ---------------------------------------------------------------------- Sweden: SCB / Energimyndigheten


def se(cons: Rows, heat: Rows, pov: Rows) -> None:
    base = "https://statistikdatabasen.scb.se/api/v2/tables/TAB3654"
    meta = w.get_json(base + "/metadata?lang=sv")
    dims = meta["dimension"]  # type: ignore[index]
    lab = {k: v["category"]["label"] for k, v in dims.items()}
    src = "SCB / Energimyndigheten, kommunal och regional energistatistik TAB3654 (CC0)"
    n = 0
    for year in sorted(lab["Tid"]):
        q = "&".join(f"valueCodes%5B{k}%5D=*" for k in dims if k != "Tid")
        f = w.download(
            f"{base}/data?lang=sv&outputFormat=csv&{q}&valueCodes%5BTid%5D={year}",
            TMP / f"scb_tab3654_{year}.csv",
            timeout=600,
        )
        with f.open(encoding="utf-8-sig") as fh:
            rd = csv.reader(fh)
            next(rd)
            for region, cat, fuel, value in rd:
                v = num(value)
                if v is None:
                    continue
                level = (
                    "country"
                    if region == "00"
                    else "county"
                    if len(region) == 2
                    else "municipality"
                )
                cons.add(
                    "SWE",
                    level,
                    region,
                    lab["Region"].get(region, region),
                    int(year),
                    lab["Bransle"].get(fuel, fuel),
                    lab["Forbrukningskategri"].get(cat, cat),
                    v,
                    "MWh",
                    "as published",
                    None,
                    src,
                )
                n += 1
    print(f"  SE: {n:,} values", flush=True)


# ---------------------------------------------------------------------- Ireland: CSO


def ie(cons: Rows, heat: Rows, pov: Rows) -> None:
    d = w.get_json(
        "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/MEC03/JSON-stat/2.0/en"
    )
    ids, sizes, dims = d["id"], d["size"], d["dimension"]  # type: ignore[index]
    labels = [list(dims[i]["category"]["label"].items()) for i in ids]
    idx = [
        list(dims[i]["category"]["index"])
        if isinstance(dims[i]["category"]["index"], list)
        else sorted(dims[i]["category"]["index"], key=dims[i]["category"]["index"].get)
        for i in ids
    ]
    vals = d["value"]  # type: ignore[index]
    unit = next(iter(dims["STATISTIC"]["category"].get("unit", {}).values()), {}).get(
        "label", "GWh"
    )
    import itertools

    n = 0
    for k, combo in enumerate(itertools.product(*[range(s) for s in sizes])):
        v = vals[k] if isinstance(vals, list) else vals.get(str(k))
        if v is None:
            continue
        cats = {ids[j]: (idx[j][c], dict(labels[j])[idx[j][c]]) for j, c in enumerate(combo)}
        year = int(cats[next(i for i in ids if i.startswith("TLIST"))][1][:4])
        area = cats[ids[2]]
        sector = cats[ids[3]][1] if len(ids) > 3 else "all"
        level = (
            "dublin_postal_district"
            if "Dublin" in area[1] and any(ch.isdigit() for ch in area[1])
            else "county"
        )
        mwh = v * 1000 if "gwh" in str(unit).lower() else v
        cons.add(
            "IRL",
            level,
            area[0],
            area[1],
            year,
            "electricity",
            sector,
            mwh,
            "MWh",
            f"as published ({unit}; x 1000 for MWh)",
            None,
            "CSO MEC03 metered electricity consumption (CC BY 4.0)",
        )
        n += 1
    print(f"  IE: {n:,} values", flush=True)


# ---------------------------------------------------------------------- Spain (Catalonia)


def es(cons: Rows, heat: Rows, pov: Rows) -> None:
    """Catalonia only (Idescat): electricity consumption per municipality and sector."""
    url = "https://analisi.transparenciacatalunya.cat/api/views/8idm-becu/rows.csv?accessType=DOWNLOAD"
    f = w.download(url, TMP / "catalunya_consum_elec.csv", timeout=600)
    with f.open(encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames or []
        print(f"  ES Catalonia columns: {cols}", flush=True)
        n = 0
        for r in rd:
            low = {k.lower(): v for k, v in r.items()}
            y = next((int(v[:4]) for k, v in low.items() if k.startswith("any") and v), None)
            code = next((v for k, v in low.items() if "cdmun" in k or "codi" in k), None)
            name = next((v for k, v in low.items() if "municipi" in k and "codi" not in k), code)
            sector = next((v for k, v in low.items() if "sector" in k), "all")
            kwh = next((num(v) for k, v in low.items() if "consum" in k), None)
            if y and code and kwh is not None:
                cons.add(
                    "ESP",
                    "municipality",
                    code,
                    name,
                    y,
                    "electricity",
                    sector,
                    kwh / 1000,
                    "MWh",
                    "as published (kWh / 1000)",
                    None,
                    "Generalitat de Catalunya open data (ICAEN), consum d'energia elèctrica per municipis i sectors",
                )
                n += 1
    print(f"  ES (Catalonia): {n:,} rows", flush=True)


# ---------------------------------------------------------------------- United States: LEAD, ACS

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]  # fmt: skip
FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
    "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}  # fmt: skip


def us(cons: Rows, heat: Rows, pov: Rows) -> None:
    lead = "DOE LEAD Tool 2022 update (OpenEI submission 6219; ACS 2018-2022 PUMS, modelled by DOE)"
    for st in STATES:
        try:
            z = w.download(
                f"https://data.openei.org/files/6219/{st}-2022-LEAD-data.zip",
                TMP / f"lead_{st}.zip",
                timeout=1200,
            )
        except SystemExit as e:
            print(f"  LEAD {st}: {e}", flush=True)
            continue
        with zipfile.ZipFile(z) as zf:
            name = next(
                (
                    n
                    for n in zf.namelist()
                    if "census tract" in n.lower() and "ami" in n.lower() and n.endswith(".csv")
                ),
                None,
            )
            if not name:
                print(f"  LEAD {st}: no tract AMI file in {zf.namelist()[:6]}", flush=True)
                continue
            con = duckdb.connect()
            tmp = TMP / f"lead_{st}.csv"
            tmp.write_bytes(zf.read(name))
            cols = [
                c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_csv('{tmp}')").fetchall()
            ]
            fip = next(c for c in cols if c.upper() in ("FIP", "GEOID", "FIPS"))
            units = next(c for c in cols if c.upper() == "UNITS")
            inc = next(c for c in cols if c.upper().startswith("HINCP"))
            exp = [c for c in cols if c.upper().startswith(("ELEP", "GASP", "FULP"))]
            q = f"""SELECT CAST("{fip}" AS VARCHAR) AS t, sum("{units}") AS units, sum("{inc}") AS inc,
                           {", ".join(f'sum("{c}") AS "{c}"' for c in exp)}
                    FROM read_csv('{tmp}') GROUP BY 1"""
            for row in con.execute(q).fetchall():
                t, units_v, inc_v, *exps = row
                code = str(t).zfill(11)
                total = sum(e or 0 for e in exps)
                if inc_v:
                    pov.add(
                        "USA",
                        "us_tract",
                        code,
                        None,
                        2022,
                        "energy burden (DOE LEAD; energy expenditure / income, summed over the tract's cohorts)",
                        round(100 * total / inc_v, 3),
                        "%",
                        lead,
                    )
                if units_v:
                    for c, e in zip(exp, exps, strict=True):
                        pov.add(
                            "USA",
                            "us_tract",
                            code,
                            None,
                            2022,
                            f"average yearly {c.split('*')[0].lower()} expenditure per household (computed: sum over cohorts / households)",
                            round((e or 0) / units_v, 2),
                            "USD",
                            lead,
                        )
            tmp.unlink()
        z.unlink()
        print(f"  LEAD {st}: done", flush=True)
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not key:
        print(
            "  ACS B25040: CENSUS_API_KEY not set; requests run without a key (limited to 500 a day)",
            flush=True,
        )
    labels = {
        "B25040_002E": "utility gas", "B25040_003E": "bottled, tank, or LP gas", "B25040_004E": "electricity",
        "B25040_005E": "fuel oil, kerosene, etc.", "B25040_006E": "coal or coke", "B25040_007E": "wood",
        "B25040_008E": "solar energy", "B25040_009E": "other fuel", "B25040_010E": "no fuel used",
    }  # fmt: skip
    for st, fp in FIPS.items():
        url = (
            f"https://api.census.gov/data/2023/acs/acs5?get=NAME,{','.join(labels)}&for=tract:*&in=state:{fp}"
            + (f"&key={key}" if key else "")
        )
        try:
            data = w.get_json(url, timeout=300)
        except SystemExit as e:
            print(f"  ACS {st}: {e}", flush=True)
            continue
        head, *rows = data  # type: ignore[misc]
        for r in rows:
            rec = dict(zip(head, r, strict=True))
            code = rec["state"] + rec["county"] + rec["tract"]
            for k, lab in labels.items():
                heat.add(
                    "USA",
                    "us_tract",
                    code,
                    rec["NAME"],
                    2023,
                    lab,
                    num(rec[k]),
                    "occupied housing units",
                    "US Census Bureau ACS 2019-2023 5-year, table B25040 house heating fuel (public domain)",
                )
    print("  ACS B25040: done", flush=True)


# ---------------------------------------------------------------------- Eurostat (country level)


def eu(cons: Rows, heat: Rows, pov: Rows) -> None:
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ilc_mdes01?format=JSON&lang=EN&hhcomp=TOTAL&rskpovth=TOTAL&unit=PC"
    d = w.get_json(url, timeout=300)
    dims, ids, sizes = d["dimension"], d["id"], d["size"]  # type: ignore[index]
    geo = dims["geo"]["category"]
    t = dims["time"]["category"]
    gi, ti = ids.index("geo"), ids.index("time")
    stride = [1] * len(sizes)
    for k in range(len(sizes) - 2, -1, -1):
        stride[k] = stride[k + 1] * sizes[k + 1]
    n = 0
    for key, v in d["value"].items():  # type: ignore[union-attr]
        k = int(key)
        g = (k // stride[gi]) % sizes[gi]
        y = (k // stride[ti]) % sizes[ti]
        gcode = next(c for c, i in geo["index"].items() if i == g)
        ycode = next(c for c, i in t["index"].items() if i == y)
        if len(gcode) != 2:
            continue
        iso3 = {"EL": "GRC", "UK": "GBR"}.get(gcode)
        pov.add(
            iso3 or gcode,
            "country",
            gcode,
            geo["label"][gcode],
            int(ycode),
            "inability to keep home adequately warm",
            v,
            "% of population",
            "Eurostat ilc_mdes01 (EU-SILC)",
        )
        n += 1
    print(f"  Eurostat ilc_mdes01: {n:,} country-years", flush=True)


SOURCES = {
    "fr": fr,
    "gb": gb,
    "nl": nl,
    "dk": dk,
    "pt": pt,
    "se": se,
    "ie": ie,
    "es": es,
    "us": us,
    "eu": eu,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=[*SOURCES, "all"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    cons, heat, pov = Rows("consumption", CONS), Rows("heating", HEAT), Rows("poverty", POV)
    ren = Rows("renewables", [
        ("iso3", "VARCHAR"), ("level", "VARCHAR"), ("code", "VARCHAR"), ("name", "VARCHAR"),
        ("year", "INTEGER"), ("technology", "VARCHAR"), ("measure", "VARCHAR"), ("value", "DOUBLE"),
        ("source", "VARCHAR"),
    ])  # fmt: skip
    status = {}
    for name in SOURCES if args.what == "all" else [args.what]:
        t0 = time.time()
        print(f"== {name}", flush=True)
        try:
            SOURCES[name](cons, heat, pov)
            if name == "gb":
                gb_renewables(ren)
            status[name] = f"built in {time.time() - t0:.0f} s"
        except (SystemExit, Exception) as e:  # one source failing does not stop the others
            status[name] = f"failed: {type(e).__name__}: {str(e)[:300]}"
            print(f"  {name}: {status[name]}", flush=True)
    con = duckdb.connect()
    lk = w.lake_for(
        "small_area_energy",
        args.lake,
        "national statistics offices, regulators and operators (see each row's source)",
        "per row (docs/DATA_SOURCES.md)",
        SCRIPT,
    )
    for rows, sort in (
        (cons, ["iso3", "level", "code", "year"]),
        (heat, ["iso3", "level", "code", "year"]),
        (pov, ["iso3", "level", "code", "year"]),
        (ren, ["code", "year"]),
    ):
        if rows.n:
            table = rows.load(con)
            for (iso3,) in con.execute(f"SELECT DISTINCT iso3 FROM {table} ORDER BY 1").fetchall():
                lk.write(
                    con,
                    table,
                    f"SELECT * FROM {table} WHERE iso3 = '{iso3}'",
                    sort=sort,
                    bloom=["code"],
                    partition={"iso3": iso3},
                )
    w.lake_done(lk, args.upload)
    print(json.dumps(status, indent=1), flush=True)
    (TMP / "status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
