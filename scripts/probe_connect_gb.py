"""Probe the GB distribution network operators' capacity heatmaps (brief 23, "room to connect").

Since 2025 each DNO publishes an "LTDS Capacity Heatmap" in one ENA format (per GSP, BSP and
primary substation: generation/demand available capacity MW, firm capacity, constraint colour,
limiting factor, voltage, lon/lat), next to its older heat map. This checks every endpoint and
prints status, row count, columns and two sample rows.

1. NGED, CKAN connecteddata.nationalgrid.co.uk: ltds-capacity-heatmap (four JSON files, one
   per licence area, public); nged-network-capacity and network-opportunity-map-headroom are
   restricted to registered users (the API answers "Authorization Error").
2. SSEN, CKAN data-api.ssen.co.uk: generation-availability-and-network-capacity ("Headroom
   Dashboard Data" CSV, the December 2024 heat map CSVs). Cloudflare answers this cloud session
   403; the existing ECR build reads the same host from GitHub Actions.
3. Northern Powergrid, Opendatasoft: heatmapdatatable, ltds-capacity-heatmap (open).
4. ENWL, SPEN, UKPN, Opendatasoft: the heatmap datasets exist but answer empty without an
   account key (ENWL_API_KEY, SPEN_API_KEY, UKPN_API_KEY in .env.example); with a key set the
   probe sends it, otherwise it only records the anonymous answer.
Opendatasoft hosts reset this cloud session's connections; they answer from GitHub Actions.

  uv run python scripts/probe_connect_gb.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import time

import httpx

c = httpx.Client(
    timeout=120,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0 (Europe-InfraAtlas probe)"},
)

NGED = "https://connecteddata.nationalgrid.co.uk"
SSEN = "https://data-api.ssen.co.uk"
ODS: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "NPg": (
        "https://northernpowergrid.opendatasoft.com",
        None,
        ("heatmapdatatable", "ltds-capacity-heatmap", "npg_ndp_generation_headroom", "npg_ndp_demand_headroom"),
    ),
    "ENWL": (
        "https://electricitynorthwest.opendatasoft.com",
        "ENWL_API_KEY",
        ("enwl-pry-heatmap", "enwl-bsp-heatmap", "enwl-gsp-heatmap", "ndp-pry-bsp-headroom"),
    ),
    "SPEN": (
        "https://spenergynetworks.opendatasoft.com",
        "SPEN_API_KEY",
        ("distribution-capacity-heatmaps-spd", "distribution-capacity-heatmaps-spm"),
    ),
    "UKPN": (
        "https://ukpowernetworks.opendatasoft.com",
        "UKPN_API_KEY",
        ("ukpn-capacity-heatmap", "ukpn-dfes-network-headroom-report"),
    ),
}  # fmt: skip


def get(url: str, headers: dict[str, str] | None = None, **kw: object) -> httpx.Response | None:
    t0 = time.monotonic()
    try:
        r = c.get(url, headers=headers, **kw)  # type: ignore[arg-type]
    except httpx.HTTPError as err:
        print(f"  {url}\n    {err.__class__.__name__} {err}")
        return None
    print(
        f"  {url}\n    HTTP {r.status_code} {r.headers.get('content-type', '')} "
        f"{len(r.content) / 1e3:.0f} kB {time.monotonic() - t0:.1f}s"
    )
    return r


def show_rows(rows: list[dict]) -> None:
    print(f"    rows {len(rows)}, columns {list(rows[0]) if rows else []}")
    for row in rows[:2]:
        print(f"    {json.dumps(row, ensure_ascii=False)[:900]}")


def ckan_package(base: str, ident: str) -> list[dict]:
    r = get(f"{base}/api/3/action/package_show", params={"id": ident})
    if r is None or r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        return []
    pkg = r.json()["result"]
    print(
        f"    {pkg.get('title')} | {pkg.get('license_title') or pkg.get('rights')} | modified {pkg.get('metadata_modified')}"
    )
    for res in pkg["resources"]:
        print(f"    - {res.get('format')} {res.get('name')} | {res.get('last_modified')} | restricted {res.get('restricted_level', '-')} | {res.get('url')}")  # fmt: skip
    return pkg["resources"]


def nged() -> None:
    print("== NGED (CKAN)")
    for res in ckan_package(NGED, "ltds-capacity-heatmap"):
        if (res.get("format") or "").upper() == "JSON" and res["url"].startswith("http"):
            r = get(res["url"])
            if r is not None and r.status_code == 200:
                show_rows(r.json())
    for ident in ("nged-network-capacity", "network-opportunity-map-headroom"):
        for res in ckan_package(NGED, ident)[:1]:
            r = get(
                f"{NGED}/api/3/action/datastore_search",
                params={"resource_id": res["id"], "limit": 2},
            )
            if r is not None:
                print(f"    datastore: {r.text[:300]}")


def ssen() -> None:
    print("== SSEN (CKAN)")
    resources = ckan_package(SSEN, "generation-availability-and-network-capacity")
    wanted = [
        r
        for r in resources
        if (r.get("format") or "").upper() == "CSV"
        and (
            "headroom" in (r.get("name") or "").lower()
            or "december 2024" in (r.get("name") or "").lower()
        )
        and "contracted" not in (r.get("name") or "").lower()
        and "quoted" not in (r.get("name") or "").lower()
    ]
    for res in wanted:
        r = get(res["url"])
        if r is not None and r.status_code == 200:
            text = r.content.decode("utf-8-sig", errors="replace")
            show_rows(list(csv.DictReader(io.StringIO(text))))
    r = get(f"{SSEN}/api/3/action/package_search", params={"q": "ltds heatmap", "rows": 20})
    if r is not None and r.status_code == 200 and "json" in r.headers.get("content-type", ""):
        print(f"    ltds search: {[p['name'] for p in r.json()['result']['results']]}")


def ods() -> None:
    for dno, (base, key_var, ids) in ODS.items():
        key = os.environ.get(key_var or "", "")
        headers = {"Authorization": f"Apikey {key}"} if key else None
        print(
            f"== {dno} (Opendatasoft{', key ' + key_var + (' set' if key else ' not set') if key_var else ''})"
        )
        for ident in ids:
            api = f"{base}/api/explore/v2.1/catalog/datasets/{ident}"
            r = get(api, headers=headers)
            if r is None or r.status_code != 200:
                continue
            d = r.json()
            meta = d.get("metas", {}).get("default", {})
            print(
                f"    {meta.get('title')} | {meta.get('license')} | modified {meta.get('modified')} | "
                f"records {meta.get('records_count')} | data_visible {d.get('data_visible')}"
            )
            rec = get(f"{api}/records", headers=headers, params={"limit": 2})
            if rec is not None and rec.status_code == 200:
                print(f"    total_count {rec.json().get('total_count')}")
                for row in rec.json().get("results", []):
                    print(f"    {json.dumps(row, ensure_ascii=False)[:900]}")
            elif rec is not None:
                print(f"    {rec.text[:200]}")
            exp = get(f"{api}/exports/csv", headers=headers, params={"delimiter": ";"})
            if exp is not None and exp.status_code == 200:
                lines = exp.text.splitlines()
                print(
                    f"    export rows {max(len(lines) - 1, 0)}, header {lines[0][:400] if lines else ''}"
                )


if __name__ == "__main__":
    nged()
    ssen()
    ods()
