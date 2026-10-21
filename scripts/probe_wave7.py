"""Probe wave 7 (brief 22): the candidate sources per dataset family, one step per family.

    python scripts/probe_wave7.py connect|units|live|congestion|prices|retail|emitters|offline|ev|gas|reliability

Each check fetches one page or endpoint and reports its HTTP status, type and size, and on HTML
pages the links that look like data (csv, xlsx, json, geojson, zip, ArcGIS or WFS services, APIs).
In Actions each family prints at most 10 `::notice` lines; the full lines go to the log.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urljoin

import httpx

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) InfraAtlas probe (github.com/Daniyal-arch/Energy_Grid)"
}
DATA_LINK = re.compile(
    r"""(?:href|src|url)\s*[=:]\s*["']([^"']+?(?:\.csv|\.xlsx?|\.json|\.geojson|\.zip|\.gpkg|\.ods)"""
    r"""(?:\?[^"']*)?|[^"']*(?:/arcgis/rest/services|/FeatureServer|/MapServer|service=WFS|/api/|/explore/v2|/ows\?)[^"']*)["']""",
    re.I,
)

# family -> [(cell, url, what to look for)]
CHECKS: dict[str, list[tuple[str, str, str]]] = {
    "connect": [
        (
            "FI",
            "https://karttapalaute.fingrid.fi/?setlanguage=en",
            "Fingrid Grid Scope map (resets from the session)",
        ),
        (
            "CY",
            "https://www.eac.com.cy/EN/RegulatedActivities/Distribution/renewableenergy/Pages/hosting-capacity.aspx",
            "EAC hosting capacity",
        ),
        (
            "RO",
            "https://www.transelectrica.ro/web/tel/racordare",
            "Transelectrica connection capacity map",
        ),
        (
            "GR",
            "https://www.admie.gr/en/grid/connection-to-the-system",
            "IPTO available capacity (403 from the session)",
        ),
        ("GR", "https://www.deddie.gr/en/", "HEDNO capacity margins"),
        (
            "HR",
            "https://www.hops.hr/informacije-o-mogucnosti-prikljucenja",
            "HOPS connection possibilities (PDF yearly)",
        ),
        (
            "DE",
            "https://www.tennet.eu/de/strommarkt/kunden-deutschland/netzanschlussanfragen",
            "TenneT DE (403 from the session)",
        ),
        (
            "LV",
            "https://www.ast.lv/lv/content/pieslegumi",
            "AST free capacity (403 from the session)",
        ),
        (
            "BE",
            "https://www.elia.be/en/customers/connection/grid-hosting-capacity",
            "Elia hosting capacity (wave 6, browser)",
        ),
        (
            "US",
            "https://www.nyiso.com/documents/20142/1407078/NYISO-Interconnection-Queue.xlsx",
            "NYISO queue file",
        ),
    ],
    "units": [
        (
            "GB",
            "https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract",
            "REPD quarterly extract",
        ),
        (
            "DK",
            "https://ens.dk/en/our-services/statistics-data-key-figures-and-energy-maps/overview-wind-turbines-denmark",
            "ENS wind turbine register",
        ),
        ("SE", "https://vbk.lansstyrelsen.se/", "Vindbrukskollen"),
        (
            "FI",
            "https://www.energiavirasto.fi/en/web/energy-authority/power-plant-register",
            "Energy Authority plant register (403 seen)",
        ),
        ("CZ", "https://www.eru.cz/", "ERÚ licensed plants (TEZ XML)"),
        ("PT", "https://www.dgeg.gov.pt/", "DGEG ArcGIS registers"),
        ("NL", "https://www.rvo.nl/", "RVO SDE++ (no unit register as data)"),
    ],
    "live": [
        (
            "FR",
            "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records?limit=1",
            "RTE eCO2mix national, taux_co2",
        ),
        (
            "ES",
            "https://apidatos.ree.es/es/datos/generacion/no-renovables-detalle-emisiones-CO2?time_trunc=day&start_date=2026-10-01T00:00&end_date=2026-10-02T00:00",
            "REE CO2 factor",
        ),
        (
            "IE",
            "https://www.smartgriddashboard.com/api/chart/?region=ROI&chartType=co2&dateRange=day&areas=co2intensity",
            "EirGrid CO2 intensity",
        ),
        ("GB", "https://api.carbonintensity.org.uk/intensity", "NESO carbon intensity"),
        ("US", "https://www.eia.gov/electricity/gridmonitor/", "EIA grid monitor xlsx"),
    ],
    "congestion": [
        (
            "GB",
            "https://api.neso.energy/api/3/action/package_show?id=constraint-breakdown",
            "NESO constraint breakdown",
        ),
        (
            "US",
            "https://www.caiso.com/library/production-curtailments-data",
            "CAISO curtailment xlsx",
        ),
        ("US", "https://www.ercot.com/gridinfo/generation", "ERCOT curtailment (no file found)"),
        (
            "EU",
            "https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html",
            "ENTSO-E A63/A91/A92 (key)",
        ),
    ],
    "prices": [
        (
            "GB",
            "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index?from=2026-10-01T00:00Z&to=2026-10-01T01:00Z&dataProviders=APXMIDP",
            "Elexon market index",
        ),
        (
            "GB",
            "https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/2026-10-01",
            "Elexon system prices",
        ),
        (
            "EU",
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
            "ECB reference rates",
        ),
        ("CY", "https://tsoc.org.cy/", "TSO Cyprus market (no day-ahead file)"),
        ("MT", "https://www.enemalta.com.mt/", "Enemalta (no wholesale market)"),
    ],
    "retail": [
        (
            "GB",
            "https://www.gov.uk/government/statistical-data-sets/international-domestic-energy-prices",
            "DESNZ international domestic prices",
        ),
        (
            "GB",
            "https://www.gov.uk/government/statistical-data-sets/international-industrial-energy-prices",
            "DESNZ international non-domestic prices",
        ),
        (
            "EU",
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_204?format=JSON&lang=en&geo=DE&time=2025-S1",
            "Eurostat nrg_pc_204",
        ),
    ],
    "emitters": [
        (
            "GB",
            "https://reports.view-emissions-trading-registry.service.gov.uk/ets-reports/section5/section5.html",
            "UK ETS compliance report",
        ),
        (
            "EU",
            "https://union-registry-data.ec.europa.eu/report/welcome",
            "EU Union Registry extracts",
        ),
    ],
    "offline": [
        (
            "GB",
            "https://data.elexon.co.uk/bmrs/api/v1/remit/list/by-event?from=2026-10-20T00:00Z&to=2026-10-20T00:01Z&latestRevisionOnly=true",
            "Elexon REMIT events",
        ),
        ("CY", "https://tsoc.org.cy/", "TSO Cyprus (no unit outage list)"),
        ("MT", "https://www.enemalta.com.mt/", "Enemalta (no unit outage list)"),
    ],
    "ev": [
        (
            "EU",
            "https://alternative-fuels-observatory.ec.europa.eu/sites/default/files/csv/european-union-eu27/countries_overview_of_recharging_stations.csv",
            "EAFO points per power class",
        ),
        (
            "GB",
            "https://alternative-fuels-observatory.ec.europa.eu/sites/default/files/csv/united-kingdom/recharging_points.csv",
            "EAFO UK",
        ),
        (
            "DE",
            "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenkarte/start.html",
            "BNetzA Ladesäulenregister",
        ),
        (
            "FR",
            "https://www.data.gouv.fr/api/1/datasets/fichier-consolide-des-bornes-de-recharge-pour-vehicules-electriques/",
            "IRVE consolidated",
        ),
        ("NL", "https://opendata.ndw.nu/", "NDW charge points (DATEX II)"),
        (
            "GB",
            "https://www.gov.uk/guidance/find-and-use-data-on-public-electric-vehicle-chargepoints",
            "UK chargepoint open data (per operator)",
        ),
        ("EU", "https://overpass-api.de/api/status", "Overpass API status"),
    ],
    "gas": [
        (
            "US",
            "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Natural_Gas_Interstate_and_Intrastate_Pipelines_1/FeatureServer/0?f=json",
            "EIA pipelines",
        ),
        ("US", "https://www.eia.gov/naturalgas/storage/", "EIA weekly storage (API with key)"),
        ("EU", "https://transparency.entsog.eu/api/v1/operators?limit=1", "ENTSOG"),
    ],
    "reliability": [
        (
            "EU",
            "https://api.worldbank.org/v2/country/DEU/indicator/IC.ELC.SAID.XD.DB1619?format=json",
            "World Bank SAIDI",
        ),
        (
            "EU",
            "https://www.ceer.eu/publication/7th-ceer-ecrb-benchmarking-report-on-the-quality-of-electricity-and-gas-supply/",
            "CEER 7th benchmarking (PDF only)",
        ),
        (
            "DE",
            "https://www.bundesnetzagentur.de/SharedDocs/Pressemitteilungen/DE/2025/20251009_Saidi_Strom.html",
            "BNetzA SAIDI (press release)",
        ),
        (
            "GB",
            "https://www.ofgem.gov.uk/sites/default/files/2023-03/RIIO-ED1%20Network%20Performance%20Summary%202021-22.pdf",
            "Ofgem RIIO-ED1 performance (PDF)",
        ),
    ],
}


def check(cell: str, url: str, want: str) -> str:
    try:
        r = httpx.get(url, timeout=45, follow_redirects=True, headers=UA)
    except httpx.HTTPError as e:
        return f"{cell}: {type(e).__name__} {str(e)[:80]} ({url})"
    kind = r.headers.get("content-type", "").split(";")[0]
    line = f"{cell}: HTTP {r.status_code} {kind} {len(r.content):,} B"
    if "html" in kind and r.status_code == 200:
        links = sorted({urljoin(str(r.url), m) for m in DATA_LINK.findall(r.text)})[:6]
        line += f"; data links {len(links)}: " + " ".join(links) if links else "; no data links"
    elif r.status_code == 200:
        line += (
            f"; starts {r.text[:120]!r}"
            if "json" in kind or "csv" in kind or "text" in kind
            else ""
        )
    return f"{line} [{want}] ({url})"


def run(family: str) -> None:
    lines = [check(*c) for c in CHECKS[family]]
    ci = bool(os.environ.get("GITHUB_ACTIONS"))
    for i, line in enumerate(lines):
        print(f"::notice title={family}::{line}" if ci and i < 10 else line, flush=True)


if __name__ == "__main__":
    for fam in sys.argv[1:] or list(CHECKS):
        run(fam)
