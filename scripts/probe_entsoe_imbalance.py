"""Probe ENTSO-E imbalance prices (A85) for a few zones: shape, resolution, categories, coverage.

Imbalance prices are published per imbalance area (= bidding zone or control area) under
documentType A85; the TimeSeries carry the price per MWh and, where a market prices long and
short positions differently, an imbalance price category (A04 excess, A05 deficit). Prints for
each zone: answered or not, series count, metadata of the first series, resolution, points over
the last 2 days, and the newest value with its time.

    uv run python scripts/probe_entsoe_imbalance.py [DE-LU NL FR ...]
"""

from __future__ import annotations

import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta

import entsoe
import httpx
from dotenv import load_dotenv

ZONES = ["DE-LU", "NL", "FR", "BE", "ES", "PL", "DK1", "SE3", "FI", "AT", "IT-North", "GR"]
# Germany prices imbalance per control area (one reBAP for all four); try them and the zone
EXTRA = {
    "DE-TenneT": "10YDE-EON------1",
    "DE-50Hertz": "10YDE-VE-------2",
    "DE-Amprion": "10YDE-RWENET---I",
    "DE-TransnetBW": "10YDE-ENBW-----N",
    "DE-control-block": "10YCB-GERMANY--8",
}


def fetch(client: httpx.Client, eic: str, params: dict[str, str]) -> ET.Element | None:
    """A85 answers a zip of XML documents (or an acknowledgement when there is no data)."""
    q = {
        "securityToken": os.environ["ENTSOE_API_KEY"].strip(),
        "documentType": "A85",
        "controlArea_Domain": eic,
        **params,
    }
    r = client.get(entsoe.BASE, params=q)
    if r.status_code != 200:
        print("          HTTP", r.status_code, r.text[:200])
        return None
    data = r.content
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        print("          zip:", names[:4], len(names), "files")
        data = z.read(names[0])
    root = ET.fromstring(data)
    if root.tag.endswith("Acknowledgement_MarketDocument"):
        ns = {"n": root.tag.split("}")[0].strip("{")}
        print("          no data:", root.findtext(".//n:text", namespaces=ns))
        return None
    return root


def main() -> None:
    load_dotenv()
    zones = sys.argv[1:] or ZONES
    now = datetime.now(UTC)
    grid = entsoe.Grid(now - timedelta(days=2), now)
    with httpx.Client(timeout=120, headers={"User-Agent": "InfraAtlas probe"}) as client:
        for z in zones + ([] if sys.argv[1:] else list(EXTRA)):
            eic = EXTRA.get(z) or entsoe.ZONE_EIC.get(z)
            if not eic:
                print(z, "no EIC in entsoe.ZONE_EIC")
                continue
            print(z, eic)
            root = fetch(client, eic, grid.params())
            if root is None:
                continue
            ns = {"n": root.tag.split("}")[0].strip("{")}
            ts = root.findall("n:TimeSeries", ns)
            res = {
                p.findtext("n:resolution", namespaces=ns)
                for t in ts
                for p in t.findall("n:Period", ns)
            }
            found = entsoe.series_of(root, "imbalance_Price.amount", grid)
            meta = found[0][0] if found else {}
            cats = (
                sorted({m.get("imbalance_Price.category", "-") for m, _ in found}) if found else []
            )
            vals = [v for _, s in found[:1] for v in s if v is not None]
            newest = None
            if found:
                s = found[0][1]
                k = max((i for i, v in enumerate(s) if v is not None), default=None)
                if k is not None:
                    newest = (datetime.fromtimestamp(grid.seconds()[k], tz=UTC).isoformat(), s[k])
            print(
                f"{z:9} series {len(ts)} resolution {sorted(r or '' for r in res)} points {len(vals)} newest {newest}"
            )
            print(f"          meta {dict(list(meta.items())[:12])} categories {cats}")
            if not found:
                print("          raw", ET.tostring(ts[0], encoding="unicode")[:600] if ts else "")


if __name__ == "__main__":
    main()
