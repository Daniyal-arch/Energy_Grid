"""Probe for docs/tasks/10: US day-ahead prices at every node, each market's live queue, and
which markets publish node positions. Runs in GitHub Actions (.github/workflows/probe-us-nodes.yml:
ERCOT blocks many non-US addresses); every result is printed as a public `::notice` line, one
section per workflow step (GitHub keeps at most 10 notices per step).

    pip install gridstatus httpx && python scripts/probe_us_nodes.py lmp|queue|pos
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from collections.abc import Callable
from datetime import date, timedelta

import httpx

DAY = (date.today() - timedelta(days=2)).isoformat()
SPP_MAP = (
    "https://pricecontourmap.spp.org/arcgis/rest/services/MarketMaps/RTBM_FeatureData/MapServer"
)


def notice(title: str, payload: dict) -> None:
    # the title goes inside the message too: the annotations listing drops it
    text = json.dumps({"t": title, **payload}, default=str)[:3500].replace("\n", " ")
    print(f"::notice title={title}::{text}", flush=True)


def attempt(title: str, fn: Callable[[], dict]) -> None:
    t = time.time()
    try:
        notice(title, {"ok": True, "s": round(time.time() - t), **fn()})
    except Exception as e:  # noqa: BLE001 - a probe reports every failure
        notice(
            title,
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "where": traceback.format_exc()[-500:],
            },
        )


def frame(df) -> dict:  # noqa: ANN001 - a pandas DataFrame
    out: dict = {"rows": len(df), "columns": list(map(str, df.columns))[:40]}
    for col in ("Location", "Location Name", "Settlement Point", "Node", "Pnode Name"):
        if col in df.columns:
            out["locations"] = int(df[col].nunique())
            break
    for col in ("Location Type", "Type"):
        if col in df.columns:
            out["types"] = df[col].value_counts().head(12).to_dict()
    out["sample"] = df.head(2).astype(str).to_dict("records")
    return out


def queue(df) -> dict:  # noqa: ANN001 - a pandas DataFrame
    out: dict = {"rows": len(df), "columns": list(map(str, df.columns))[:45]}
    for col in ("Status", "State", "Generation Type"):
        if col in df.columns:
            out[col] = df[col].astype(str).value_counts().head(8).to_dict()
    return out


def lmp(gs) -> None:  # noqa: ANN001 - the gridstatus module
    ercot = gs.Ercot()
    attempt(
        "lmp ERCOT get_spp ALL",
        lambda: frame(ercot.get_spp(DAY, market="DAY_AHEAD_HOURLY", location_type="ALL")),
    )
    attempt("lmp ERCOT get_spp", lambda: frame(ercot.get_spp(DAY, market="DAY_AHEAD_HOURLY")))
    attempt("lmp ERCOT bus", lambda: frame(ercot.get_lmp_by_bus_dam(DAY)))


def queues(gs) -> None:  # noqa: ANN001 - the gridstatus module
    for name in ("CAISO", "Ercot", "MISO", "SPP", "NYISO", "ISONE"):
        attempt(
            f"queue {name}",
            lambda name=name: queue(getattr(gs, name)().get_interconnection_queue()),
        )


def positions(gs) -> None:  # noqa: ANN001 - the gridstatus module
    attempt("pos NYISO generators", lambda: frame(gs.NYISO().get_generators()))
    c = httpx.Client(
        timeout=120, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 InfraAtlas probe"}
    )

    def arcgis(layer: int) -> dict:
        url = f"{SPP_MAP}/{layer}/query"
        q = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "resultRecordCount": 2,
        }
        d = c.get(url, params=q).json()
        meta = c.get(f"{SPP_MAP}/{layer}", params={"f": "json"}).json()
        cnt = c.get(url, params={"f": "json", "where": "1=1", "returnCountOnly": "true"}).json()
        return {
            "name": meta.get("name"),
            "geometryType": meta.get("geometryType"),
            "count": cnt.get("count"),
            "fields": [f["name"] for f in meta.get("fields", [])][:25],
            "sample": d.get("features", [])[:2],
        }

    for layer in (0, 1, 2, 3):
        attempt(f"pos SPP map layer {layer}", lambda layer=layer: arcgis(layer))

    def get_any(url: str) -> dict:
        r = c.get(url)
        return {
            "http": r.status_code,
            "type": r.headers.get("content-type"),
            "bytes": len(r.content),
            "head": r.text[:600],
        }

    for title, url in (
        (
            "pos CAISO price map",
            "https://wwwmobile.caiso.com/Web.Service.Chart/api/v3/ChartService/PriceContourMap1",
        ),
        ("pos ERCOT LMP points kml", "https://www.ercot.com/content/cdr/contours/rtmLmpPoints.kml"),
        (
            "pos MISO LMP table",
            "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx"
            "?messageType=getLMPConsolidatedTable&returnType=json",
        ),
    ):
        attempt(title, lambda url=url: get_any(url))


def main() -> None:
    import gridstatus

    section = sys.argv[1] if len(sys.argv) > 1 else "pos"
    {"lmp": lmp, "queue": queues, "pos": positions}[section](gridstatus)


if __name__ == "__main__":
    main()
