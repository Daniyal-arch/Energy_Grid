"""Australia's National Electricity Market, live (5-minute dispatch), for the World tab.

AEMO's public NEM summary (no key; scripts/probe_world_open.py): per region the
dispatch price (AUD/MWh), total demand, net interchange, scheduled and semi-scheduled
generation, and the flow on each interconnector. Values are passthrough.

Interconnector flows: AEMO's sign convention, positive = from the first region in the
interconnector's name to the second (e.g. VIC1-NSW1 positive = Victoria to New South
Wales). The short names map to regions as AEMO defines them.

Writes frontend/public/data/eu/aemo.json:
  {"source", "fetched", "settlement" (market time, UTC+10), "regions": {REGION: {"price",
   "demand", "net_interchange", "scheduled", "semi_scheduled"}},
   "interconnectors": [{"id", "from", "to", "mw", "export_limit", "import_limit"}]}

    uv run python scripts/fetch_aemo.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://visualisations.aemo.com.au/aemo/apps/api/report/ELEC_NEM_SUMMARY"
# interconnector -> (from, to) as named by AEMO
ENDS = {
    "NSW1-QLD1": ("NSW1", "QLD1"),
    "N-Q-MNSP1": ("NSW1", "QLD1"),  # Terranora
    "VIC1-NSW1": ("VIC1", "NSW1"),
    "V-SA": ("VIC1", "SA1"),  # Heywood
    "V-S-MNSP1": ("VIC1", "SA1"),  # Murraylink
    "T-V-MNSP1": ("TAS1", "VIC1"),  # Basslink
}


def num(v: object) -> float | None:
    try:
        return round(float(v), 1)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    r = httpx.get(URL, timeout=60, headers={"User-Agent": "Europe-InfraAtlas/0.3"})
    r.raise_for_status()
    rows = r.json()["ELEC_NEM_SUMMARY"]
    regions: dict[str, dict] = {}
    links: dict[str, dict] = {}
    settlement = ""
    for row in rows:
        settlement = row["SETTLEMENTDATE"]
        regions[row["REGIONID"]] = {
            "price": num(row.get("PRICE")),
            "demand": num(row.get("TOTALDEMAND")),
            "net_interchange": num(row.get("NETINTERCHANGE")),
            "scheduled": num(row.get("SCHEDULEDGENERATION")),
            "semi_scheduled": num(row.get("SEMISCHEDULEDGENERATION")),
        }
        flows = row.get("INTERCONNECTORFLOWS") or "[]"
        for f in json.loads(flows) if isinstance(flows, str) else flows:
            if f["name"] in ENDS:
                a, b = ENDS[f["name"]]
                links[f["name"]] = {
                    "id": f["name"],
                    "from": a,
                    "to": b,
                    "mw": num(f.get("value")),
                    "export_limit": num(f.get("exportlimit")),
                    "import_limit": num(f.get("importlimit")),
                }
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "AEMO NEM summary (5-minute dispatch), visualisations.aemo.com.au",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "settlement": f"{settlement}+10:00",
        "regions": regions,
        "interconnectors": list(links.values()),
    }
    (out / "aemo.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(
        f"aemo.json: {len(regions)} regions, {len(links)} interconnectors, {payload['settlement']}"
    )


if __name__ == "__main__":
    main()
