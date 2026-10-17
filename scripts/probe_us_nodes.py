"""Probe for docs/tasks/10: US day-ahead prices at every node, each market's live queue, and
which markets publish node positions. Runs in GitHub Actions (.github/workflows/probe-us-nodes.yml:
ERCOT blocks many non-US addresses); every result is printed as a public `::notice` line.

    pip install gridstatus httpx && python scripts/probe_us_nodes.py
"""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import Callable
from datetime import date, timedelta

import httpx

DAY = (date.today() - timedelta(days=2)).isoformat()


def notice(title: str, payload: object) -> None:
    text = json.dumps(payload, default=str)[:3500].replace("\n", " ")
    print(f"::notice title={title}::{text}", flush=True)


def attempt(title: str, fn: Callable[[], object]) -> None:
    t = time.time()
    try:
        notice(title, {"ok": True, "s": round(time.time() - t), **fn()})  # type: ignore[dict-item]
    except Exception as e:  # noqa: BLE001 - a probe reports every failure
        notice(
            title,
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "where": traceback.format_exc()[-600:],
            },
        )


def frame(df) -> dict:  # noqa: ANN001 - a pandas DataFrame
    out = {"rows": len(df), "columns": list(map(str, df.columns))[:40]}
    for col in ("Location", "Location Name", "Settlement Point", "Node", "Pnode Name"):
        if col in df.columns:
            out["locations"] = int(df[col].nunique())
            out["location_col"] = col
            break
    for col in ("Location Type", "Type"):
        if col in df.columns:
            out["types"] = df[col].value_counts().head(12).to_dict()
    out["sample"] = df.head(2).astype(str).to_dict("records")
    return out


def main() -> None:
    import gridstatus

    # ------------------------------------------------------------ day-ahead LMP, every node
    attempt(
        "lmp CAISO",
        lambda: frame(
            gridstatus.CAISO().get_lmp(DAY, market="DAY_AHEAD_HOURLY", locations="ALL_AP_NODES")
        ),
    )
    attempt(
        "lmp ERCOT",
        lambda: frame(
            gridstatus.Ercot().get_spp(DAY, market="DAY_AHEAD_HOURLY", location_type="ALL")
        ),
    )
    attempt(
        "lmp MISO",
        lambda: frame(gridstatus.MISO().get_lmp(DAY, market="DAY_AHEAD_HOURLY", locations="ALL")),
    )
    attempt("lmp SPP", lambda: frame(gridstatus.SPP().get_lmp_day_ahead_hourly(DAY)))
    attempt(
        "lmp NYISO",
        lambda: frame(
            gridstatus.NYISO().get_lmp(
                DAY, market="DAY_AHEAD_HOURLY", locations="ALL", location_type="generator"
            )
        ),
    )
    attempt(
        "lmp ISONE",
        lambda: frame(gridstatus.ISONE().get_lmp(DAY, market="DAY_AHEAD_HOURLY", locations="ALL")),
    )

    # ------------------------------------------------------------ live interconnection queues
    for name in ("CAISO", "Ercot", "MISO", "SPP", "NYISO", "ISONE"):
        attempt(
            f"queue {name}",
            lambda name=name: frame(getattr(gridstatus, name)().get_interconnection_queue()),
        )

    # ------------------------------------------------------------ node positions
    attempt("pos NYISO generators", lambda: frame(gridstatus.NYISO().get_generators()))
    c = httpx.Client(
        timeout=120, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 InfraAtlas probe"}
    )

    def arcgis(url: str) -> dict:
        r = c.get(
            url,
            params={
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "resultRecordCount": 3,
            },
        )
        d = r.json()
        meta = c.get(url.rsplit("/query", 1)[0], params={"f": "json"}).json()
        cnt = c.get(url, params={"f": "json", "where": "1=1", "returnCountOnly": "true"}).json()
        return {
            "http": r.status_code,
            "name": meta.get("name"),
            "geometryType": meta.get("geometryType"),
            "count": cnt.get("count"),
            "fields": [f["name"] for f in meta.get("fields", [])][:30],
            "sample": d.get("features", [])[:2],
        }

    for layer in (0, 1, 2, 3):
        attempt(
            f"pos SPP map layer {layer}",
            lambda layer=layer: arcgis(
                f"https://pricecontourmap.spp.org/arcgis/rest/services/MarketMaps/RTBM_FeatureData/MapServer/{layer}/query"
            ),
        )

    def get_any(url: str) -> dict:
        r = c.get(url)
        return {
            "http": r.status_code,
            "type": r.headers.get("content-type"),
            "bytes": len(r.content),
            "head": r.text[:700],
        }

    for title, url in (
        (
            "pos CAISO price map",
            "https://wwwmobile.caiso.com/Web.Service.Chart/api/v3/ChartService/PriceContourMap1",
        ),
        ("pos ERCOT LMP points kml", "https://www.ercot.com/content/cdr/contours/rtmLmpPoints.kml"),
        ("pos ERCOT LMP map", "https://www.ercot.com/content/cdr/html/real_time_spp.html"),
        (
            "pos MISO LMP map",
            "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx?messageType=getLMPConsolidatedTable&returnType=json",
        ),
    ):
        attempt(title, lambda url=url: get_any(url))


if __name__ == "__main__":
    main()
