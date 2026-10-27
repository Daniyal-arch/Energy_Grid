"""Probe the Spanish distribution operators' access-capacity files (brief 23, "room to connect").

Under RD 1183/2020 and CNMC Circular 1/2021 every DSO publishes, monthly, the access capacity
for generation (and since 2025 for demand) per substation and voltage. This checks each
operator's page or data portal and prints status, row count, columns and two sample rows.

1. e-distribución (Endesa): monthly CSV/xlsx in the CNMC format, linked from two pages
   (generation, demand); the CSV is ';'-separated, decimal comma, ETRS89 UTM coordinates.
2. Viesgo, E-Redes España (ex Hidrocantábrico / EDP) and Begasa (Barras Eléctricas): the EDP
   Spain Opendatasoft portal redes-spain.opendatasoft.com, datasets
   7-capacidad-disponible-generacion-<dso> and 8-capacidad-disponible-consumo-<dso>
   (WGS84 lat/lon, CC BY 4.0). Opendatasoft resets this cloud session's connections; the
   probe works from GitHub Actions.
3. i-DE (Iberdrola) and UFD (Naturgy): their sites refuse scripts (Akamai 503, Azure
   Application Gateway 403); only the status is recorded, nothing is worked around.
4. CIDE (association of the small distributors): no shared file; members publish their own.

  uv run python scripts/probe_connect_es.py
"""

from __future__ import annotations

import csv
import io
import re
import time

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
c = httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": UA})

EDIS = "https://www.edistribucion.com/es/red-electrica/nodos-capacidad-red"
EDP = "https://redes-spain.opendatasoft.com/api/explore/v2.1/catalog/datasets"
EDP_DSOS = ("viesgo", "e-redes", "begasa")


def get(url: str, **kw: object) -> httpx.Response | None:
    t0 = time.monotonic()
    try:
        r = c.get(url, **kw)  # type: ignore[arg-type]
    except httpx.HTTPError as err:
        print(f"  {url}\n    {err.__class__.__name__} {err}")
        return None
    print(
        f"  {url}\n    HTTP {r.status_code} {r.headers.get('content-type', '')} "
        f"{len(r.content) / 1e3:.0f} kB {time.monotonic() - t0:.1f}s"
    )
    return r


def show_csv(text: str, delimiter: str = ";") -> None:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter))
    if not rows:
        print("    empty")
        return
    print(f"    rows {len(rows) - 1}, columns {rows[0]}")
    for row in rows[1:3]:
        print(f"    {row}")


def edistribucion() -> None:
    print("== e-distribución (Endesa)")
    for page in ("capacidad-generacion", "capacidad-demanda"):
        r = get(f"{EDIS}/{page}.html")
        if r is None or r.status_code != 200:
            continue
        links = sorted(set(re.findall(r'href="([^"]+\.(?:csv|xlsx))"', r.text)))
        print(f"    {len(links)} csv/xlsx links; newest: {links[-4:]}")
        csvs = [u for u in links if u.endswith(".csv")]
        months = sorted({m for u in csvs for m in re.findall(r"/(\d{6})/", u)})
        newest = [u for u in csvs if months and f"/{months[-1]}/" in u] or csvs[-1:]
        for href in newest[:3]:
            url = href if href.startswith("http") else "https://www.edistribucion.com" + href
            f = get(url)
            if f is not None and f.status_code == 200:
                show_csv(f.content.decode("utf-8-sig", errors="replace"))


def edp_spain() -> None:
    print("== EDP Spain portal (Viesgo, E-Redes, Begasa)")
    for dso in EDP_DSOS:
        for ds in (
            f"7-capacidad-disponible-generacion-{dso}",
            f"8-capacidad-disponible-consumo-{dso}",
        ):
            r = get(f"{EDP}/{ds}")
            if r is None or r.status_code != 200:
                continue
            meta = r.json().get("metas", {}).get("default", {})
            print(
                f"    {meta.get('title')} | modified {meta.get('modified')} | processed "
                f"{meta.get('data_processed')} | {meta.get('license')} | records {meta.get('records_count')}"
            )
            print(f"    fields {[f['name'] for f in r.json().get('fields', [])]}")
            rec = get(f"{EDP}/{ds}/records", params={"limit": 2, "order_by": "data desc"})
            if rec is not None and rec.status_code == 200:
                d = rec.json()
                print(f"    total_count {d.get('total_count')}")
                for row in d.get("results", []):
                    print(f"    {row}")
            months = get(
                f"{EDP}/{ds}/records",
                params={"select": "data, count(*) as n", "group_by": "data", "limit": 100},
            )
            if months is not None and months.status_code == 200:
                print(f"    months {months.json().get('results')}")
            exp = get(f"{EDP}/{ds}/exports/csv", params={"delimiter": ";"})
            if exp is not None and exp.status_code == 200:
                print(f"    export rows {max(exp.text.count(chr(10)) - 1, 0)}")


def refused() -> None:
    print("== i-DE (Iberdrola), UFD (Naturgy), CIDE: status only")
    for url in (
        "https://www.i-de.es/conexion-red-electrica/produccion-energia/mapa-capacidad-acceso",
        "https://www.ufd.es/capacidad-de-acceso/",
        "https://cide.net/",
    ):
        r = get(url)
        if r is not None:
            title = re.search(r"<title>([^<]*)</title>", r.text, re.I)
            print(f"    title: {title.group(1).strip() if title else '-'}")


if __name__ == "__main__":
    edistribucion()
    edp_spain()
    refused()
