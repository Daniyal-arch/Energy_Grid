"""Probe ENTSO-E for the series behind docs/tasks/03-entsoe-capacity.md and per-unit output:

- A61 forecasted transfer capacity (day-ahead, contract type A01) per bidding-zone border
- A31 offered transfer capacity (implicit day-ahead auction) per border
- A69 day-ahead wind and solar forecast per country (processType A01)
- A68 installed capacity per production type per country (processType A33, yearly)
- A73 actual generation per generation unit (processType A16) for one country and day

Prints what exists, at what resolution, and a sample value, for one day (default
2026-10-07, CEST).

    uv run python scripts/probe_entsoe_capacity.py [YYYY-MM-DD]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
from entsoe import AREA_EIC, ZONE_EIC, request

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-10-07"
START = datetime.fromisoformat(DAY).replace(tzinfo=UTC) - timedelta(hours=2)  # 00:00 CEST
PERIOD = {
    "periodStart": START.strftime("%Y%m%d%H%M"),
    "periodEnd": (START + timedelta(days=1)).strftime("%Y%m%d%H%M"),
}

# bidding-zone borders to try (both directions)
BORDERS = [
    ("DE-LU", "FR"), ("DE-LU", "NL"), ("DE-LU", "PL"), ("DE-LU", "CZ"), ("DE-LU", "AT"),
    ("DE-LU", "CH"), ("DE-LU", "DK1"), ("DE-LU", "DK2"), ("DE-LU", "SE4"), ("DE-LU", "NO2"),
    ("DE-LU", "BE"), ("FR", "ES"), ("FR", "BE"), ("FR", "CH"), ("FR", "IT-North"),
    ("ES", "PT"), ("NL", "BE"), ("NL", "NO2"), ("NL", "DK1"), ("PL", "CZ"), ("PL", "SK"),
    ("PL", "LT"), ("PL", "SE4"), ("CZ", "SK"), ("CZ", "AT"), ("AT", "HU"), ("AT", "SI"),
    ("AT", "CH"), ("AT", "IT-North"), ("HU", "SK"), ("HU", "RO"), ("HU", "HR"), ("HU", "RS"),
    ("SI", "HR"), ("SI", "IT-North"), ("RO", "BG"), ("BG", "GR"), ("GR", "IT-South"),
    ("NO1", "SE3"), ("SE3", "FI"), ("SE1", "FI"), ("FI", "EE"), ("EE", "LV"), ("LV", "LT"),
    ("LT", "SE4"), ("DK1", "NO2"), ("DK1", "SE3"), ("DK2", "SE4"), ("SE3", "SE4"),
    ("NO1", "NO2"), ("IT-North", "IT-Centre-North"), ("CH", "IT-North"),
]  # fmt: skip


def series(root: ET.Element | None, tag: str) -> list[dict]:
    """Every TimeSeries: its metadata and the points of its first period."""
    if root is None:
        return []
    ns = {"n": root.tag.split("}")[0].strip("{")}
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        meta = {c.tag.split("}")[1]: (c.text or "").strip() for c in ts if not len(c) and c.text}
        psr = ts.find("n:MktPSRType/n:psrType", ns)
        res = ts.find("n:MktPSRType/n:PowerSystemResources", ns)
        if psr is not None:
            meta["psrType"] = psr.text
        if res is not None:
            meta["unit"] = res.findtext("n:mRID", namespaces=ns)
            meta["unit_name"] = res.findtext("n:name", namespaces=ns)
        periods = ts.findall("n:Period", ns)
        pts = [
            float(p.findtext(f"n:{tag}", namespaces=ns) or 0)
            for per in periods
            for p in per.findall("n:Point", ns)
        ]
        meta["resolution"] = periods[0].findtext("n:resolution", namespaces=ns) if periods else ""
        meta["n_points"] = len(pts)
        meta["points"] = pts
        out.append(meta)
    return out


def main() -> None:
    client = httpx.Client(timeout=120)

    def border_doc(doc: str, a: str, b: str) -> tuple[str, str, str, list[dict]]:
        extra = (
            {"contract_MarketAgreement.Type": "A01"}
            if doc == "A61"
            else {"auction.Type": "A01", "contract_MarketAgreement.Type": "A01"}
        )
        root = request(
            client,
            {
                "documentType": doc,
                "in_Domain": ZONE_EIC[b],
                "out_Domain": ZONE_EIC[a],
                **extra,
                **PERIOD,
            },
        )
        return doc, a, b, series(root, "quantity")

    jobs = [(doc, a, b) for doc in ("A61", "A31") for x, y in BORDERS for a, b in ((x, y), (y, x))]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda j: border_doc(*j), jobs))
    print(f"Transfer capacities on {DAY} (MW, first value, resolution, points)")
    for doc in ("A61", "A31"):
        have = [(a, b, s) for d, a, b, s in results if d == doc and s]
        print(f"\n{doc}: {len(have)} of {len(BORDERS) * 2} directions with data")
        for a, b, s in have:
            v = s[0]["points"]
            print(
                f"  {a:>15} -> {b:<15} {v[0] if v else '-':>8} {s[0]['resolution']:>6} {len(v):>3}"
            )
        none = [f"{a}->{b}" for d, a, b, s in results if d == doc and not s]
        print("  none:", " ".join(none))

    print(f"\nA69 wind and solar forecast on {DAY} (MW at 12:00 CEST)")
    for iso in ["DE", "FR", "ES", "IT", "PL", "NL", "BE", "DK", "SE", "GR", "PT", "AT"]:
        root = request(
            client,
            {"documentType": "A69", "processType": "A01", "in_Domain": AREA_EIC[iso], **PERIOD},
        )
        got = series(root, "quantity")
        parts = []
        for s in got:
            pts = s["points"]
            per_h = {"PT15M": 4, "PT30M": 2, "PT60M": 1}.get(s["resolution"], 1)
            noon = pts[12 * per_h] if len(pts) > 12 * per_h else None
            parts.append(f"{s.get('psrType')}={noon} ({s['resolution']})")
        print(f"  {iso}: {', '.join(parts) or 'none'}")

    print("\nA68 installed capacity per production type (newest year, MW)")
    year = START.year
    for iso in ["DE", "FR", "ES", "PL", "IT", "GB"]:
        root = request(
            client,
            {
                "documentType": "A68",
                "processType": "A33",
                "in_Domain": AREA_EIC[iso],
                "periodStart": f"{year}01010000",
                "periodEnd": f"{year}01020000",
            },
        )
        got = series(root, "quantity")
        total = sum(s["points"][0] for s in got if s["points"])
        print(f"  {iso}: {len(got)} types, total {total:,.0f} MW")

    print(f"\nA73 actual generation per unit on {DAY} (DE, FR, PL)")
    for iso in ["DE", "FR", "PL"]:
        root = request(
            client,
            {"documentType": "A73", "processType": "A16", "in_Domain": AREA_EIC[iso], **PERIOD},
        )
        got = series(root, "quantity")
        units = {s.get("unit") for s in got}
        print(
            f"  {iso}: {len(got)} series, {len(units)} units, resolution {got[0]['resolution'] if got else '-'}"
        )
        for s in sorted(got, key=lambda s: -max(s["points"] or [0]))[:3]:
            print(
                f"    {s.get('unit')} {s.get('unit_name')} {s.get('psrType')} max {max(s['points'] or [0]):,.0f} MW"
            )


if __name__ == "__main__":
    main()
