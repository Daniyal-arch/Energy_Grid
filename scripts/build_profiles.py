"""Country and state profiles (brief 17, group F): rows for the country report, no new layers.

    python scripts/build_profiles.py eurostat|seds|steo|ei|edgar [--lake lake-out] [--upload]

eurostat  Eurostat energy balances `nrg_bal_c` (API, no key, CC BY 4.0): final energy consumption
          by sector and by fuel, newest year, ktoe as published. API only (no lake copy).
seds      EIA SEDS (API v2, EIA_API_KEY): per state consumption and production by source, newest
          year, billion Btu as published. API only.
steo      EIA STEO (API v2): US electricity generation and residential price, monthly, the months
          from the release month on labelled "forecast". API only.
ei        Energy Institute Statistical Review (consolidated panel, free with attribution): energy
          by fuel, electricity and CO2 per country, newest year each, as published -> lake
          `ei_review/panel` (every row and column). Its site answers scripts with a Cloudflare
          challenge: scripts/browser_fetch.py fetches the file with a browser and passes --file.
edgar     EDGAR 2025 (JRC, CC BY 4.0), the GHG booklet: GHG per country and sector, Mt CO2e
          (GWP-100 AR5) -> lake `edgar/*`.

Each writes frontend/public/data/eu/profiles/<name>.json:
  {"title", "source", "year", "rows": {ISO3 or state: [[item, value, unit, note], ...]}}
(the US file keys states by their postal code and the US total as "USA").
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import wave5_common as w

OUT = w.EU / "profiles"
TMP = Path("/tmp/wave5")
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_bal_c"
EIA = "https://api.eia.gov/v2"
EDGAR_URL = "https://edgar.jrc.ec.europa.eu/booklet/EDGAR_2025_GHG_booklet_2025.xlsx"
SECTORS = {
    "FC_IND_E": "Industry",
    "FC_TRA_E": "Transport",
    "FC_OTH_HH_E": "Households",
    "FC_OTH_CP_E": "Commerce and public services",
    "FC_OTH_AF_E": "Agriculture and forestry",
}
FUELS = {
    "C0000X0350-0370": "Solid fossil fuels",
    "O4000XBIO": "Oil and petroleum products",
    "G3000": "Natural gas",
    "E7000": "Electricity",
    "H8000": "Heat",
    "RA000": "Renewables and biofuels",
}
SEDS = {
    "TETCB": ("Total energy consumption", "consumption"),
    "CLTCB": ("Coal consumption", "consumption"),
    "NGTCB": ("Natural gas consumption", "consumption"),
    "PATCB": ("Petroleum consumption", "consumption"),
    "NUETB": ("Nuclear electricity", "consumption"),
    "RETCB": ("Renewable energy consumption", "consumption"),
    "TEPRB": ("Total primary energy production", "production"),
    "CLPRB": ("Coal production", "production"),
    "NGMPB": ("Natural gas marketed production", "production"),
    "PAPRB": ("Crude oil production", "production"),
    "REPRB": ("Renewable energy production", "production"),
}
STEO = ["EPEOPUS", "ESRCUUS"]
ISO2_EUROSTAT = {"EL": "GR", "UK": "GB", "XK": "XK"}


def write_profile(name: str, payload: dict) -> None:
    w.write_json(OUT / f"{name}.json", {"fetched": w.now(), **payload})


def jsonstat_values(d: dict) -> dict[tuple[str, ...], float]:
    """A Eurostat JSON-stat answer as {(code of each dimension in order): value}."""
    ids = d["id"]
    sizes = d["size"]
    cats = []
    for dim in ids:
        index = d["dimension"][dim]["category"]["index"]
        cats.append(sorted(index, key=lambda c: index[c]))
    out = {}
    for k, v in d["value"].items():
        k = int(k)
        key = []
        for size, cat in zip(reversed(sizes), reversed(cats), strict=True):
            key.append(cat[k % size])
            k //= size
        out[tuple(reversed(key))] = v
    return out


def eurostat(args: argparse.Namespace) -> None:
    import pycountry

    q = "&".join(
        ["format=JSON", "lang=EN", "unit=KTOE", "lastTimePeriod=1"]
        + [f"nrg_bal={b}" for b in ["FC_E", *SECTORS]]
        + [f"siec={s}" for s in ["TOTAL", *FUELS]]
    )
    d = w.get_json(f"{EUROSTAT}?{q}", timeout=300)
    vals = jsonstat_values(d)  # type: ignore[arg-type]
    year = list(d["dimension"]["time"]["category"]["index"])[0]  # type: ignore[index]
    rows: dict[str, list] = {}
    for geo in d["dimension"]["geo"]["category"]["index"]:  # type: ignore[index]
        iso2 = ISO2_EUROSTAT.get(geo, geo)
        try:
            iso3 = "XKX" if iso2 == "XK" else pycountry.countries.get(alpha_2=iso2).alpha_3  # type: ignore[union-attr]
        except AttributeError:
            continue  # EU27_2020, EA20: aggregates

        def key(b: str, s: str, geo: str = geo) -> float | None:
            return vals.get(("A", b, s, "KTOE", geo, year))  # freq, nrg_bal, siec, unit, geo, time

        r = []
        total = key("FC_E", "TOTAL")
        if total is not None:
            r.append(["Final energy consumption", total, "ktoe", f"{year}, all sectors"])
        r += [
            [f"Final energy, {label.lower()}", key(b, "TOTAL"), "ktoe", year]
            for b, label in SECTORS.items()
            if key(b, "TOTAL") is not None
        ]
        r += [
            [f"Final energy from {label.lower()}", key("FC_E", s), "ktoe", year]
            for s, label in FUELS.items()
            if key("FC_E", s) is not None
        ]
        if r:
            rows[iso3] = r
    print(f"  dimensions {d['id']}; {len(rows)} countries, {year}", flush=True)  # type: ignore[index]
    write_profile(
        "eurostat_balances",
        {
            "title": f"Final energy use, {year}",
            "source": "Eurostat energy balances nrg_bal_c (CC BY 4.0), ktoe as published",
            "year": year,
            "rows": rows,
        },
    )


def eia(route: str, params: dict[str, object]) -> list[dict]:
    """Every row of an EIA API v2 query (5,000 per request, offset)."""
    out: list[dict] = []
    while True:
        r = w.get_json(
            f"{EIA}/{route}/data/",
            params={**params, "api_key": w.env("EIA_API_KEY"), "offset": len(out), "length": 5000},
        )  # type: ignore[arg-type]
        data = r["response"]["data"]  # type: ignore[index]
        out += data
        if len(data) < 5000:
            return out


def seds(args: argparse.Namespace) -> None:
    newest = eia(
        "seds",
        {
            "frequency": "annual",
            "data[]": "value",
            "facets[seriesId][]": "TETCB",
            "facets[stateId][]": "US",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 1,
        },
    )
    year = newest[0]["period"]
    data = eia(
        "seds",
        {
            "frequency": "annual",
            "data[]": "value",
            "facets[seriesId][]": list(SEDS),
            "start": year,
            "end": year,
        },
    )
    rows: dict[str, list] = {}
    for d in data:
        if d.get("value") in (None, "") or d["seriesId"] not in SEDS:
            continue
        label, _ = SEDS[d["seriesId"]]
        state = "USA" if d["stateId"] == "US" else d["stateId"]
        rows.setdefault(state, []).append(
            [label, float(d["value"]), d.get("unit") or "billion Btu", year]
        )
    order = list(SEDS)
    for r in rows.values():
        r.sort(key=lambda x: next(i for i, k in enumerate(order) if SEDS[k][0] == x[0]))
    print(f"  SEDS {year}: {len(data)} values, {len(rows)} states and the US", flush=True)
    write_profile(
        "us_seds",
        {
            "title": f"Energy consumption and production, {year}",
            "source": "EIA State Energy Data System (SEDS), API v2, as published",
            "year": year,
            "rows": rows,
        },
    )


def steo(args: argparse.Namespace) -> None:
    today = datetime.now(UTC)
    start = f"{today.year - 2}-01"
    data = eia(
        "steo",
        {"frequency": "monthly", "data[]": "value", "facets[seriesId][]": STEO, "start": start},
    )
    series: dict[str, dict] = {}
    for d in data:
        s = series.setdefault(
            d["seriesId"], {"name": d.get("seriesDescription"), "unit": d.get("unit"), "values": {}}
        )
        if d.get("value") not in (None, ""):
            s["values"][d["period"]] = float(d["value"])
    first_forecast = f"{today.year}-{today.month:02d}"
    out = {
        k: {
            **v,
            "months": sorted(v["values"]),
            "values": [v["values"][m] for m in sorted(v["values"])],
        }
        for k, v in series.items()
    }
    print(f"  STEO: {[(k, v['name'], len(v['months'])) for k, v in out.items()]}", flush=True)
    w.write_json(
        w.US / "steo.json",
        {
            "fetched": w.now(),
            "source": "EIA Short-Term Energy Outlook (STEO), API v2",
            "forecast_from": first_forecast,
            "series": out,
        },
    )


def edgar(args: argparse.Namespace) -> None:
    import duckdb
    import openpyxl

    src = w.download(EDGAR_URL, TMP / "edgar_booklet.xlsx")
    wb = openpyxl.load_workbook(src, read_only=True)
    sheet = list(wb["GHG_by_sector_and_country"].iter_rows(values_only=True))
    head = [str(h) for h in sheet[0]]
    years = [h for h in head[4:] if h.isdigit()]
    long = []
    for r in sheet[1:]:
        if not r or r[2] is None:
            continue
        for k, y in enumerate(years):
            v = r[4 + k]
            if v is not None:
                long.append(
                    {
                        "substance": r[0],
                        "sector": r[1],
                        "iso3": r[2],
                        "country": r[3],
                        "year": int(y),
                        "mt_co2e": float(v),
                    }
                )
    newest = max(int(y) for y in years)
    rows: dict[str, list] = {}
    sums: dict[tuple[str, str], float] = {}
    for x in long:
        if x["year"] == newest:
            sums[(x["iso3"], x["sector"])] = sums.get((x["iso3"], x["sector"]), 0.0) + x["mt_co2e"]
    for (iso3, sector), v in sorted(sums.items(), key=lambda kv: -kv[1]):
        rows.setdefault(iso3, []).append(
            [
                f"GHG, {sector}",
                round(v, 3),
                "Mt CO2e",
                f"{newest}; CO2, CH4, N2O and F-gases summed (computed)",
            ]
        )
    write_profile(
        "edgar",
        {
            "title": f"Greenhouse gas emissions by sector, {newest}",
            "source": "EDGAR 2025 GHG booklet (JRC, CC BY 4.0), GWP-100 AR5",
            "year": newest,
            "rows": rows,
        },
    )
    tmp = TMP / "edgar.json"
    tmp.write_text(json.dumps(long), encoding="utf-8")
    con = duckdb.connect()
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "edgar",
        args.lake,
        "EDGAR 2025 GHG booklet (JRC)",
        "CC BY 4.0",
        "scripts/build_profiles.py",
        "EDGAR_2025_GHG",
    )
    lk.write(
        con,
        "ghg_by_sector",
        f"""SELECT t.*, i.iso2, NULL::VARCHAR AS admin1 FROM read_json('{tmp}', maximum_object_size = 1000000000) t
            LEFT JOIN iso_codes i ON i.iso3 = t.iso3""",
        sort=["iso3", "sector", "substance", "year"],
    )
    print(f"  EDGAR: {len(long):,} values, {len(rows)} countries, newest {newest}", flush=True)
    w.lake_done(lk, args.upload)


# EI panel columns (name pattern, label, unit): the review's energy and emissions per country
EI_ITEMS = [
    (r"^primary_ej$", "Primary energy", "EJ"),
    (r"^oilcons_ej$", "Oil consumption", "EJ"),
    (r"^gascons_ej$", "Gas consumption", "EJ"),
    (r"^coalcons_ej$", "Coal consumption", "EJ"),
    (r"^nuclear_ej$", "Nuclear", "EJ"),
    (r"^hydro_ej$", "Hydro", "EJ"),
    (r"^ren_power_ej$", "Renewables in power", "EJ"),
    (r"^elect_twh$", "Electricity generation", "TWh"),
    (r"^co2_combust_mtco2$|^co2_mtco2$", "CO2 from energy", "Mt CO2"),
]


def ei_rows(records: list[dict], cols: list[str]) -> tuple[dict[str, list], int | None]:
    """Profile rows from the EI panel (one record per country and year): per ISO3, each item's
    value in the newest year that has it, as published."""
    iso = next((c for c in cols if re.search(r"iso3166_alpha3|^iso3?$", c, re.I)), None)
    year = next((c for c in cols if c.lower() == "year"), None)
    if not iso or not year:
        raise SystemExit(f"EI panel: no ISO3 or year column in {cols[:20]}")
    found = [
        (next((c for c in cols if re.match(p, c, re.I)), None), lab, u) for p, lab, u in EI_ITEMS
    ]
    print(f"  EI columns used: {[(lab, c) for c, lab, _ in found]}", flush=True)
    best: dict[tuple[str, str], tuple[int, float]] = {}
    for r in records:
        code = str(r.get(iso) or "").strip()
        if not re.fullmatch(r"[A-Z]{3}", code):  # regions and totals carry no ISO3
            continue
        for col, lab, _ in found:
            v = r.get(col) if col else None
            if v in (None, "") or not str(r.get(year) or "").isdigit():
                continue
            y = int(r[year])
            if (code, lab) not in best or y > best[(code, lab)][0]:
                best[(code, lab)] = (y, float(v))
    rows: dict[str, list] = {}
    for _col, lab, unit in found:
        for (code, item), (y, v) in sorted(best.items()):
            if item == lab:
                rows.setdefault(code, []).append([lab, round(v, 4), unit, f"{y}, as published"])
    years = [y for y, _ in best.values()]
    return rows, max(years) if years else None


def ei(args: argparse.Namespace) -> None:
    """From the file scripts/browser_fetch.py fetched (the page answers scripts with a
    Cloudflare challenge): python scripts/build_profiles.py ei --file PATH [--upload]."""
    import duckdb

    if not args.file:
        raise SystemExit("ei needs --file (scripts/browser_fetch.py ei fetches it)")
    src = Path(args.file)
    con = duckdb.connect()
    if src.suffix == ".csv":
        con.execute(f"CREATE TABLE ei AS SELECT * FROM read_csv('{src}', sample_size = -1)")
    else:
        con.execute("INSTALL excel; LOAD excel")
        con.execute(f"CREATE TABLE ei AS SELECT * FROM read_xlsx('{src}', all_varchar = true)")
    cols = [c[0] for c in con.execute("DESCRIBE ei").fetchall()]
    print(
        f"  {src.name}: {con.execute('SELECT count(*) FROM ei').fetchone()[0]:,} rows; columns {cols[:40]}",
        flush=True,
    )  # type: ignore[index]
    cur = con.execute("SELECT * FROM ei")
    records = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    rows, newest = ei_rows(records, cols)
    if not rows:
        raise SystemExit("EI panel: no country rows parsed")
    write_profile(
        "ei_review",
        {
            "title": "Energy and emissions, Statistical Review",
            "source": f"Energy Institute Statistical Review of World Energy ({src.name}), free with attribution",
            "year": newest,
            "rows": rows,
        },
    )
    print(f"  EI: {len(rows)} countries, newest year {newest}", flush=True)
    import lake

    lake.iso_codes(con)
    iso = next(c for c in cols if re.search(r"iso3166_alpha3|^iso3?$", c, re.I))
    lk = w.lake_for(
        "ei_review",
        args.lake,
        "Energy Institute Statistical Review of World Energy, consolidated dataset",
        "free with attribution (Energy Institute)",
        "scripts/build_profiles.py",
        src.stem,
    )
    lk.write(
        con,
        "panel",
        f"""SELECT e.*, e."{iso}" AS iso3, i.iso2, NULL::VARCHAR AS admin1 FROM ei e
            LEFT JOIN iso_codes i ON i.iso3 = e."{iso}" """,
        sort=["iso3"],
    )
    w.lake_done(lk, args.upload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["eurostat", "seds", "steo", "ei", "edgar"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--file", help="ei: the fetched file (scripts/browser_fetch.py)")
    args = ap.parse_args()
    {"eurostat": eurostat, "seds": seds, "steo": steo, "ei": ei, "edgar": edgar}[args.what](args)


if __name__ == "__main__":
    main()
