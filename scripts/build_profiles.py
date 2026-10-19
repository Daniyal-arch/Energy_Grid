"""Country and state profiles (brief 17, group F): rows for the country report, no new layers.

    python scripts/build_profiles.py eurostat|seds|steo|ei|edgar [--lake lake-out] [--upload]

eurostat  Eurostat energy balances `nrg_bal_c` (API, no key, CC BY 4.0): final energy consumption
          by sector and by fuel, newest year, ktoe as published. API only (no lake copy).
seds      EIA SEDS (API v2, EIA_API_KEY): per state consumption and production by source, newest
          year, billion Btu as published. API only.
steo      EIA STEO (API v2): US electricity generation and residential price, monthly, the months
          from the release month on labelled "forecast". API only.
ei        Energy Institute Statistical Review (all-data workbook, free with attribution): energy
          by fuel, electricity and CO2 per country, newest year each, as published; country names
          matched to ISO3 (pycountry and a short alias list) -> lake `ei_review/series` (every
          sheet's values, long). Its site answers scripts with a Cloudflare
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


# EI workbook sheets (name pattern, profile label): the report rows, values as published
EI_SHEETS = [
    (r"^Total Energy Supply \(TES\)|^Primary Energy Cons", "Total energy supply"),
    (r"^Oil Consumption - EJ", "Oil consumption"),
    (r"^Gas Consumption - EJ", "Gas consumption"),
    (r"^Coal Consumption - EJ", "Coal consumption"),
    (r"^Nuclear Consumption - EJ", "Nuclear"),
    (r"^Hydro Consumption - EJ", "Hydro"),
    (r"^Renewables? (Energy )?Consumption", "Renewables"),
    (r"^Electricity Generation", "Electricity generation"),
    (r"^CO2 from Energy|^CO2 Emissions from Energy", "CO2 from energy"),
]
# EI country names that pycountry does not find by name (regions and totals stay unmatched)
EI_NAMES = {
    "US": "USA", "Russian Federation": "RUS", "Iran": "IRN", "South Korea": "KOR",
    "Vietnam": "VNM", "Venezuela": "VEN", "Trinidad & Tobago": "TTO", "Turkey": "TUR",
    "Turkiye": "TUR", "Türkiye": "TUR", "Czech Republic": "CZE", "Taiwan": "TWN",
    "China Hong Kong SAR": "HKG", "Bolivia": "BOL", "Syria": "SYR", "Laos": "LAO",
    "Moldova": "MDA", "North Macedonia": "MKD", "Tanzania": "TZA", "Congo": "COG",
    "Democratic Republic of Congo": "COD", "Brunei": "BRN", "Kosovo": "XKX", "Russia": "RUS",
    "DR Congo": "COD", "Republic of Congo": "COG", "Curacao": "CUW",
    "The Dominican Republic": "DOM",
}  # fmt: skip


def ei_iso3(name: str) -> str | None:
    import pycountry

    n = re.sub(r"[#*\u00b9\u00b2\u00b3^\d]+$", "", str(name)).strip()
    if n in EI_NAMES:
        return EI_NAMES[n]
    if re.search(r"^Total|^Other|^of which|^Non-|^OECD|^European Union|^CIS", n):
        return None
    try:
        return pycountry.countries.lookup(n).alpha_3
    except LookupError:
        return None


def ei_sheet(rows: list[tuple]) -> tuple[str, list[tuple[str, int, float]]]:
    """(unit, [(name, year, value)]) from one EI sheet: the header row is the first with 20 or
    more year cells, its first cell names the unit; country names in the first column."""
    head_i = next(
        i for i, r in enumerate(rows)
        if sum(1 for c in r if isinstance(c, int | float | str) and re.fullmatch(r"(19|20)\d\d", str(c).split(".")[0])) >= 20
    )  # fmt: skip
    head = rows[head_i]
    years = {
        j: int(str(c).split(".")[0])
        for j, c in enumerate(head)
        if c is not None and re.fullmatch(r"(19|20)\d\d(\.0)?", str(c))
    }
    unit = str(head[0] or "").strip()
    out = []
    for r in rows[head_i + 1 :]:
        if not r or not isinstance(r[0], str) or not r[0].strip():
            continue
        for j, y in years.items():
            v = r[j] if j < len(r) else None
            if isinstance(v, int | float):
                out.append((r[0].strip(), y, float(v)))
    return unit, out


def ei(args: argparse.Namespace) -> None:
    """From the workbook scripts/browser_fetch.py fetched (the site answers scripts with a
    Cloudflare challenge): python scripts/build_profiles.py ei --file PATH [--upload]."""
    import duckdb
    import openpyxl

    if not args.file:
        raise SystemExit("ei needs --file (scripts/browser_fetch.py ei fetches it)")
    src = Path(args.file)
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    print(f"  {src.name}: sheets {wb.sheetnames}", flush=True)
    long: list[dict] = []
    best: dict[tuple[str, str], tuple[int, float, str]] = {}
    unmatched: set[str] = set()
    for ws in wb.worksheets:
        label = next((lab for pat, lab in EI_SHEETS if re.match(pat, ws.title.strip(), re.I)), None)
        try:
            unit, vals = ei_sheet(list(ws.iter_rows(values_only=True)))
        except StopIteration:  # notes, contents, definitions: no year header
            continue
        for name, y, v in vals:
            iso3 = ei_iso3(name)
            long.append(
                {"sheet": ws.title, "name": name, "iso3": iso3, "year": y, "value": v, "unit": unit}
            )
            if not iso3:
                unmatched.add(name)
            elif label and ((iso3, label) not in best or y > best[(iso3, label)][0]):
                best[(iso3, label)] = (y, v, unit)
        if label:
            print(f"  {ws.title!r} -> {label}: unit {unit!r}, {len(vals):,} values", flush=True)
    print(f"  names without ISO3 (regions, totals): {sorted(unmatched)[:80]}", flush=True)
    rows: dict[str, list] = {}
    for _pat, lab in EI_SHEETS:
        for (iso3, item), (y, v, unit) in sorted(best.items()):
            if item == lab:
                rows.setdefault(iso3, []).append([lab, round(v, 4), unit, f"{y}, as published"])
    if not rows:
        raise SystemExit("EI workbook: no country rows parsed")
    newest = max(y for y, _, _ in best.values())
    write_profile(
        "ei_review",
        {
            "title": "Energy and emissions, Statistical Review",
            "source": f"Energy Institute Statistical Review of World Energy ({src.name}), free with attribution",
            "year": newest,
            "rows": rows,
        },
    )
    print(f"  EI: {len(long):,} values, {len(rows)} countries, newest year {newest}", flush=True)
    tmp = TMP / "ei_review.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(long), encoding="utf-8")
    con = duckdb.connect()
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "ei_review",
        args.lake,
        "Energy Institute Statistical Review of World Energy, all data workbook",
        "free with attribution (Energy Institute)",
        "scripts/build_profiles.py",
        src.stem,
    )
    lk.write(
        con,
        "series",
        f"""SELECT t.*, i.iso2, NULL::VARCHAR AS admin1 FROM read_json('{tmp}', maximum_object_size = 1000000000) t
            LEFT JOIN iso_codes i ON i.iso3 = t.iso3""",
        sort=["sheet", "iso3", "year"],
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
