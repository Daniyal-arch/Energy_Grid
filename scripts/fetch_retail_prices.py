"""What consumers pay for electricity and gas: Eurostat (Europe, half-yearly) and EIA (US
states, monthly). scripts/probe_retail_prices.py shows both sources.

Europe, Eurostat API (CC BY 4.0, no key), EUR per kWh at Eurostat's precision (4 decimals),
one standard consumption band per series (Eurostat's own band names):
  elec_household     nrg_pc_204  band DC, 2,500-4,999 kWh a year
  elec_business      nrg_pc_205  band IC, 500-1,999 MWh a year
  gas_household      nrg_pc_202  band D2, 20-199 GJ a year (price per kWh, GCV)
  gas_business       nrg_pc_203  band I3, 10,000-99,999 GJ a year (price per kWh, GCV)
each with three tax levels: I_TAX (all taxes and levies), X_VAT (without VAT and other
recoverable taxes), X_TAX (without taxes and levies), plus Eurostat's flag per value
(p provisional, e estimated, b break in series, d definition differs, c confidential...).
Geo codes as the map's: EL -> GR, UK -> GB, EU27_2020 -> EU; the euro-area aggregates are left
out.

US, EIA API v2 electricity/retail-sales (EIA_API_KEY; Forms EIA-861 and EIA-861M): average
retail price per state and sector (residential, commercial, industrial, all sectors), cents
per kWh as EIA publishes it (2 decimals), the newest 25 months; "US" is EIA's national figure
(census divisions left out).

Writes frontend/public/data/eu/retail.json:
  {"fetched", "eu": {"source", "periods": [half-years], "updated": {dataset: date},
                     "series": {name: {GEO: {"I_TAX": [...], "X_VAT": [...], "X_TAX": [...],
                                             "flags": [...]}}}},
   "us": {"source", "months": [...], "names": {ST: name},
          "price": {ST: {"RES": [...], "COM": [...], "IND": [...], "ALL": [...]}}}}

    uv run python scripts/fetch_retail_prices.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
ES = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
EIA = "https://api.eia.gov/v2/electricity/retail-sales/data/"
HALF_YEARS = 8
MONTHS = 25
TAXES = ["I_TAX", "X_VAT", "X_TAX"]
SERIES = {
    "elec_household": ("nrg_pc_204", "KWH2500-4999"),
    "elec_business": ("nrg_pc_205", "MWH500-1999"),
    "gas_household": ("nrg_pc_202", "GJ20-199"),
    "gas_business": ("nrg_pc_203", "GJ10000-99999"),
}
GEO = {"EL": "GR", "UK": "GB", "EU27_2020": "EU"}
SECTORS = ["RES", "COM", "IND", "ALL"]


def get(client: httpx.Client, url: str, params: dict | list) -> dict:
    for attempt in range(4):
        try:
            r = client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
        except httpx.TransportError:
            pass
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"{url}: no answer")


def cells(d: dict) -> dict[tuple[str, ...], tuple[float | None, str | None]]:
    """JSON-stat 2.0 -> {(category per dimension): (value, flag)}; values are row-major."""
    dims = d["id"]
    index = [
        sorted(d["dimension"][k]["category"]["index"].items(), key=lambda x: x[1]) for k in dims
    ]
    out: dict[tuple[str, ...], tuple[float | None, str | None]] = {}
    sizes = d["size"]
    for flat in set(d.get("value", {})) | set(d.get("status", {})):
        n = int(flat)
        key: list[str] = []
        for size, cats in zip(reversed(sizes), reversed(index), strict=True):
            key.append(cats[n % size][0])
            n //= size
        out[tuple(reversed(key))] = (d["value"].get(flat), d.get("status", {}).get(flat))
    return out


def eurostat(client: httpx.Client) -> dict:
    series: dict[str, dict] = {}
    updated: dict[str, str] = {}
    periods: set[str] = set()
    raw: dict[str, dict] = {}
    for name, (code, band) in SERIES.items():
        params = [
            ("format", "JSON"),
            ("lang", "EN"),
            ("nrg_cons", band),
            ("unit", "KWH"),
            ("currency", "EUR"),
            ("lastTimePeriod", str(HALF_YEARS)),
            *[("tax", t) for t in TAXES],
        ]
        d = get(client, f"{ES}/{code}", params)
        updated[code] = d.get("updated", "")
        raw[name] = d
        periods |= set(d["dimension"]["time"]["category"]["index"])
    times = sorted(periods)[-HALF_YEARS:]
    for name, d in raw.items():
        dims = d["id"]
        g, t, tm = dims.index("geo"), dims.index("tax"), dims.index("time")
        out: dict[str, dict] = {}
        for key, (v, flag) in cells(d).items():
            geo = GEO.get(key[g], key[g])
            if len(geo) != 2 or geo == "EA" or key[tm] not in times:
                continue
            row = out.setdefault(
                geo, {**{x: [None] * len(times) for x in TAXES}, "flags": [None] * len(times)}
            )
            i = times.index(key[tm])
            row[key[t]][i] = v
            if flag and key[t] == "I_TAX":
                row["flags"][i] = flag
        series[name] = {
            k: v for k, v in sorted(out.items()) if any(x is not None for x in v["I_TAX"])
        }
    return {
        "source": "Eurostat nrg_pc_202, nrg_pc_203, nrg_pc_204, nrg_pc_205 (half-yearly, CC BY 4.0)",
        "periods": times,
        "updated": updated,
        "series": series,
    }


def eia(client: httpx.Client, key: str) -> dict:
    rows: list[dict] = []
    offset = 0
    while True:
        params = [
            ("api_key", key),
            ("frequency", "monthly"),
            ("data[0]", "price"),
            *[("facets[sectorid][]", s) for s in SECTORS],
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "desc"),
            ("offset", str(offset)),
            ("length", "5000"),
        ]
        d = get(client, EIA, params)["response"]
        rows += d["data"]
        offset += len(d["data"])
        months = {r["period"] for r in rows}
        if not d["data"] or len(months) > MONTHS or offset >= int(d["total"]):
            break
    months_kept = sorted({r["period"] for r in rows})[-MONTHS:]
    price: dict[str, dict] = {}
    names: dict[str, str] = {}
    for r in rows:
        if r["period"] not in months_kept or r["price"] in (None, ""):
            continue
        st = r["stateid"]
        if len(st) != 2:  # census divisions and regions
            continue
        names[st] = r["stateDescription"]
        p = price.setdefault(st, {s: [None] * len(months_kept) for s in SECTORS})
        p[r["sectorid"]][months_kept.index(r["period"])] = float(r["price"])
    return {
        "source": "EIA, electricity retail sales (Forms EIA-861, EIA-861M), average price",
        "months": months_kept,
        "names": dict(sorted(names.items())),
        "price": dict(sorted(price.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out_dir: Path = parser.parse_args().out
    client = httpx.Client(timeout=120)
    out: dict = {"fetched": datetime.now(UTC).isoformat(timespec="seconds"), "eu": eurostat(client)}
    key = os.environ.get("EIA_API_KEY", "").strip()
    if key:
        out["us"] = eia(client, key)
    else:
        print("EIA_API_KEY not set: US retail prices skipped")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "retail.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    eu = out["eu"]
    print(
        f"Eurostat {eu['periods'][0]}..{eu['periods'][-1]}: "
        + ", ".join(f"{k} {len(v)}" for k, v in eu["series"].items())
        + (
            f"; EIA {out['us']['months'][-1]}, {len(out['us']['price'])} states"
            if "us" in out
            else ""
        )
        + f" -> {path}"
    )


if __name__ == "__main__":
    main()
