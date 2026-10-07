"""Probe more open live-grid endpoints (no keys), second round.

Taiwan (Taipower generation per unit), New Zealand (em6), Japan (TEPCO area demand
and supply), Nova Scotia (NS Power mix), Alberta (AESO, parsed later), Uruguay (ADME),
South Africa (Eskom data portal), Mexico (CENACE), Chile (Coordinador, public page)

  uv run python scripts/probe_live_grids_2.py
"""

from __future__ import annotations

import time

import httpx

c = httpx.Client(
    timeout=45,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0 (Europe-InfraAtlas probe)"},
)


def show(label: str, url: str, n: int = 300) -> None:
    t0 = time.monotonic()
    try:
        r = c.get(url)
        body = r.text[:n].replace("\n", " ").replace("\r", "")
        print(
            f"{label}: HTTP {r.status_code} {r.headers.get('content-type', '')[:30]} {len(r.content) / 1e3:.0f} kB {time.monotonic() - t0:.1f}s\n   {body}"
        )
    except httpx.HTTPError as err:
        print(f"{label}: {err.__class__.__name__}")


show("Taiwan genary", "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary.json")
show("NZ em6 generation type", "https://api.em6.co.nz/ords/em6/data_api/current_generation_type")
show("Japan TEPCO demand", "https://www.tepco.co.jp/forecast/html/images/juyo-d1-j.csv")
show("Nova Scotia mix", "https://www.nspower.ca/library/CurrentLoads/CurrentMix.json")
show("Nova Scotia load", "https://www.nspower.ca/library/CurrentLoads/CurrentLoad.json")
show(
    "Uruguay ADME",
    "https://pronos.adme.com.uy/gpf.php?fecha_ini=07%2F10%2F2026&fecha_fin=07%2F10%2F2026&send=MOSTRAR",
)
show("South Africa Eskom", "https://www.eskom.co.za/dataportal/", 200)
show("Mexico CENACE", "https://www.cenace.gob.mx/GraficaDemanda.aspx", 200)
show(
    "Chile Coordinador",
    "https://www.coordinador.cl/operacion/graficos/operacion-real/generacion-real-del-sistema/",
    200,
)
