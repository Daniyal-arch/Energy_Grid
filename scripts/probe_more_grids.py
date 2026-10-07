"""Probe open live-grid sources outside Europe, the US and Australia (no keys).

1. Ontario, IESO public reports: generator output by fuel (hourly XML), Ontario demand
2. Quebec, Hydro-Quebec open data: production by source (JSON)
3. Alberta, AESO current supply and demand report
4. Brazil, ONS "Energia Agora": balance per subsystem (generation by source, load,
   interchange)
5. India, Vidyut Pravah (national dashboard)

  uv run python scripts/probe_more_grids.py
"""

from __future__ import annotations

import time

import httpx

c = httpx.Client(
    timeout=60,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0 (Europe-InfraAtlas probe)"},
)


def show(label: str, url: str, n: int = 400) -> None:
    t0 = time.monotonic()
    try:
        r = c.get(url)
        body = r.text[:n].replace("\n", " ").replace("\r", "")
        print(
            f"{label}: HTTP {r.status_code} {r.headers.get('content-type', '')} {len(r.content) / 1e3:.0f} kB {time.monotonic() - t0:.1f}s\n   {body}"
        )
    except httpx.HTTPError as err:
        print(f"{label}: {err.__class__.__name__} {err}")


show(
    "IESO generator output by fuel",
    "https://reports.ieso.ca/public/GenOutputbyFuelHourly/PUB_GenOutputbyFuelHourly.xml",
)
show("IESO realtime totals", "https://reports.ieso.ca/public/RealtimeTotals/PUB_RealtimeTotals.xml")
show(
    "IESO zonal demand",
    "https://reports.ieso.ca/public/RealtimeZonalEnergyPrices/PUB_RealtimeZonalEnergyPrices.xml",
    200,
)
show(
    "Hydro-Quebec production",
    "https://www.hydroquebec.com/data/documents-donnees/donnees-ouvertes/json/production.json",
)
show(
    "Hydro-Quebec demand",
    "https://www.hydroquebec.com/data/documents-donnees/donnees-ouvertes/json/demande.json",
)
show(
    "AESO current supply demand",
    "http://ets.aeso.ca/ets_web/ip/Market/Reports/CSDReportServlet",
    300,
)
show(
    "ONS balanco energetico",
    "https://integra.ons.org.br/api/energiaagora/GetBalancoEnergetico/null",
)
show("ONS intercambio", "https://integra.ons.org.br/api/energiaagora/Get/Intercambio_SIN_GE")
show("Vidyut Pravah", "https://vidyutpravah.in/", 300)
