"""Installed electricity capacity per country and technology, 2000 to the newest year
(IRENA statistics, IRENASTAT PxWeb API, no key; scripts/probe_irena.py).

Table "Electricity statistics by Country/area, Technology, Data Type, Grid connection and
Year": data type "Electrical Installed Capacity (MW)", grid connection "All". Values are
passthrough, per IRENA technology (its own categories, e.g. onshore and offshore wind,
solar PV, renewable hydropower, coal, natural gas, nuclear). Series without any value are
left out. Nothing is summed here; the app sums groups where it says so.

IRENA's certificate chains to GoDaddy's 2025 root (scripts/certs/godaddy-tls-root-r1.pem),
which Python's certifi bundle does not include yet; it is added to the trusted roots.

Writes frontend/public/data/eu/irena.json:
  {"source", "fetched", "table", "years": [...], "techs": {code: label},
   "capacity_mw": {ISO3: {code: [MW per year, null where missing]}}}

    uv run python scripts/fetch_irena.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
from datetime import UTC, datetime
from pathlib import Path

import certifi
import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
FOLDER = "https://pxweb.irena.org/api/v1/en/IRENASTAT/Power%20Capacity%20and%20Generation"
SOURCE = "IRENA, IRENASTAT: electrical installed capacity (MW) by country and technology"
BATCH = 40  # countries per query (PxWeb caps the cells of one answer)


def tls() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(
        cafile=str(Path(__file__).parent / "certs" / "godaddy-tls-root-r1.pem")
    )
    return ctx


def country_table(client: httpx.Client) -> str:
    """The newest country table (its name carries the release, e.g. 2026_H2)."""
    tables = [
        t["id"] for t in client.get(f"{FOLDER}/").json() if t["id"].startswith("Country_ELECSTAT")
    ]
    return sorted(tables)[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    with httpx.Client(
        timeout=180, verify=tls(), headers={"User-Agent": "Europe-InfraAtlas/0.3"}
    ) as client:
        table = country_table(client)
        url = f"{FOLDER}/{table}"
        meta = {v["code"]: v for v in client.get(url).json()["variables"]}
        countries = meta["Country/area"]["values"]
        dtype = meta["Data Type"]["values"][
            meta["Data Type"]["valueTexts"].index("Electrical Installed Capacity (MW)")
        ]
        grid = meta["Grid connection"]["values"][meta["Grid connection"]["valueTexts"].index("All")]
        years = meta["Year"]["valueTexts"]
        techs = dict(
            zip(meta["Technology"]["values"], meta["Technology"]["valueTexts"], strict=True)
        )
        capacity: dict[str, dict[str, list]] = {}
        for i in range(0, len(countries), BATCH):
            batch = countries[i : i + BATCH]
            q = {
                "query": [
                    {"code": "Country/area", "selection": {"filter": "item", "values": batch}},
                    {"code": "Data Type", "selection": {"filter": "item", "values": [dtype]}},
                    {"code": "Grid connection", "selection": {"filter": "item", "values": [grid]}},
                ],
                "response": {"format": "json-stat2"},
            }
            r = client.post(url, json=q)
            r.raise_for_status()
            d = r.json()
            ids, sizes, values = d["id"], d["size"], d["value"]
            cat = {k: list(d["dimension"][k]["category"]["index"]) for k in ids}
            # json-stat2: values in row-major order over the dimensions
            strides = [1] * len(sizes)
            for k in range(len(sizes) - 2, -1, -1):
                strides[k] = strides[k + 1] * sizes[k + 1]
            ci, ti, yi = ids.index("Country/area"), ids.index("Technology"), ids.index("Year")
            for c, iso in enumerate(cat["Country/area"]):
                for t, code in enumerate(cat["Technology"]):
                    series = []
                    for y in range(sizes[yi]):
                        pos = c * strides[ci] + t * strides[ti] + y * strides[yi]
                        v = values[pos]
                        series.append(None if v is None else round(float(v), 1))
                    if any(v is not None for v in series):
                        capacity.setdefault(iso, {})[code] = series
            print(
                f"  countries {i + 1}-{i + len(batch)}: {len(capacity)} with values so far",
                flush=True,
            )
    data = {
        "source": SOURCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "table": re.sub(r"_PX\.px$", "", table),
        "years": years,
        "techs": techs,
        "capacity_mw": capacity,
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / "irena.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"{path.name}: {path.stat().st_size / 1e3:.0f} kB, {len(capacity)} countries, years {years[0]}-{years[-1]}"
    )


if __name__ == "__main__":
    main()
