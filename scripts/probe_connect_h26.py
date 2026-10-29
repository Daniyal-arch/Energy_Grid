"""Probe for brief 26: every room-to-connect candidate in Europe, its neighbours and the US.

    python scripts/probe_connect_h26.py [--only CODE,CODE] > docs/research/probe_connect_h26.txt

One line per candidate: the operator code, the HTTP status (or the error), what answered
(Cloudflare challenge, HTTP 451, a login page, a Power BI report, a PDF, JSON...) and, for data
endpoints, what they hold (ArcGIS layers with their feature counts, JSON lengths, PDF pages).
The client names itself (wave7_common.UA); nothing is retried around a refusal.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wave7_common import UA  # noqa: E402

# (code, kind, url): kind "page" (status, title, refusal markers), "arcgis" (layers and counts),
# "json" (length of the payload), "pdf" (pages and the first line)
CANDIDATES: list[tuple[str, str, str]] = [
    # ---- EU gaps and operators missing inside covered countries
    ("AT-NETZNOE", "page", "https://netz-noe.at/strom/versorgungsgebiete-und-kapazitaeten/trafokarte-fuer-einspeiser"),
    ("AT-NETZNOE-WMS", "page", "https://webgis.evn.at/cgi-bin/qgis_mapserv.fcgi.exe?SERVICE=WMS&REQUEST=GetCapabilities"),
    ("AT-ENETZE", "page", "https://www.e-netze.at/Service/FEK/Default.aspx"),
    ("AT-WIENERNETZE", "page", "https://www.wienernetze.at/"),
    ("AT-NETZOOE", "page", "https://www.netzooe.at/"),
    ("AT-KNG", "page", "https://kaerntennetz.at/"),
    ("BE-ELIA", "page", "https://www.elia.be/en/customers/connection/grid-hosting-capacity"),
    ("BE-FLUVIUS", "page", "https://www.fluvius.be/nl/aansluitingen"),
    ("BE-ORES", "page", "https://www.ores.be/"),
    ("BE-SIBELGA", "page", "https://www.sibelga.be/"),
    ("BE-RESA", "page", "https://www.resa.be/"),
    ("BG-ERP", "page", "https://www.erpsever.bg/bg/prisyedinjavane-kym-mrejata/proverka-na-kapaciteta-na-elektrorazpredelitelnata-mreja"),
    ("BG-ERMZ", "page", "https://ermzapad.bg/bg/za-klienta/uslugi/prisedinyavaniya/proverka-za-nalichie-na-kapacitet-na-erm-zapad-za-vei-proizvoditeli/"),
    ("BG-EVN", "page", "https://www.elektrorazpredelenie.bg/"),
    ("CY-TSO", "page", "https://www.tsoc.org.cy/"),
    ("CY-EAC", "page", "https://www.eac.com.cy/EN/RegulatedActivities/Distribution/renewableenergy/Pages/hosting-capacity.aspx"),
    ("CZ-CEZ", "page", "https://www.cezdistribuce.cz/cs/o-spolecnosti/informace-ze-sveta-cez-distribuce/kapacita-distribucni-site-v-mape-231626"),
    ("CZ-EGD", "page", "https://www.egd.cz/"),
    ("CZ-PRE", "arcgis", "https://services7.arcgis.com/0NBqUPRkQ8NgorYt/arcgis/rest/services/Mapa_Pripojitelnosti_PREdistribuce/FeatureServer"),
    ("DE-TENNET", "page", "https://www.tennet.eu/de/"),
    ("DE-WESTNETZ", "page", "https://www.westnetz.de/"),
    ("DE-BAYERNWERK", "page", "https://www.bayernwerk-netz.de/"),
    ("DE-EDIS", "page", "https://www.e-dis-netz.de/"),
    ("DE-AVACON", "page", "https://www.avacon-netz.de/"),
    ("DE-SHNETZ", "page", "https://www.sh-netz.com/"),
    ("DE-NETZEBW", "page", "https://www.netze-bw.de/stromeinspeisung/mittelspannungsauskunft"),
    ("DE-MITNETZ", "page", "https://www.mitnetz-strom.de/energie-einspeisen/anlage-anmelden/reservierung"),
    ("DE-RHEINNETZ", "page", "https://www.rheinnetz.de/netzauslastung"),
    ("DE-STROMNETZBERLIN", "page", "https://www.stromnetz.berlin/einspeisen/erzeugungsanlagen-einspeisung/"),
    ("DE-STROMNETZHH", "page", "https://www.stromnetz-hamburg.de/"),
    ("DE-EWE", "page", "https://www.ewe-netz.de/einspeiser"),
    ("DE-LEW", "page", "https://www.lew-verteilnetz.de/lew-verteilnetz/fuer-einspeiser/in-das-oeffentliche-netz-einspeisen/netzvoranfrage"),
    ("DK-RADIUS", "page", "https://radiuselnet.dk/ny-tilslutning/store-tilslutninger/status-paa-kapacitet-i-transmissionsnettet/"),
    ("EE-ELEKTRILEVI", "page", "https://elektrilevi.ee/et"),
    ("ES-IDE", "page", "https://www.i-de.es/"),
    ("ES-UFD", "page", "https://www.ufd.es/"),
    ("FI-FINGRID", "page", "https://www.fingrid.fi/kantaverkko/liitynta-kantaverkkoon/verkkokiikari/"),
    ("FI-CARUNA", "page", "https://caruna.fi/"),
    ("FI-HELEN", "arcgis", "https://services-eu1.arcgis.com/gTUn8bgbbRzjNT5i/arcgis/rest/services/KJ_vapaa_kapasiteetti/FeatureServer"),
    ("FI-KSAT", "arcgis", "https://services7.arcgis.com/KGuWrKWD3xbnD3gd/arcgis/rest/services/K_Sat_Kapasiteetti_2026_WFL1/FeatureServer"),
    ("FI-NIVOS", "arcgis", "https://services7.arcgis.com/KGuWrKWD3xbnD3gd/arcgis/rest/services/Nivos_kapasiteetti_2026_WFL1/FeatureServer"),
    ("FI-NAANTALI", "arcgis", "https://services7.arcgis.com/KGuWrKWD3xbnD3gd/arcgis/rest/services/Naantali_kapasiteetti_2026_WFL1/FeatureServer"),
    ("FI-ELENIA-STORAGE", "arcgis", "https://services-eu1.arcgis.com/sNo97Nomxi3o06sY/arcgis/rest/services/Akustokapasiteetti/FeatureServer"),
    ("FR-ENEDIS", "page", "https://www.enedis.fr/"),
    ("GR-ADMIE", "page", "https://www.admie.gr/"),
    ("HR-HEPODS", "json", "https://kapaciteti.hep.hr/api/substations/with-data"),
    ("HU-OPUS", "page", "https://www.opusttitasz.hu/"),
    ("HU-EON", "page", "https://www.eon.hu/hu/lakossagi.html"),
    ("IE-ESBN", "page", "https://www.esbnetworks.ie/"),
    ("IT-TERNA", "page", "https://www.terna.it/it/sistema-elettrico/programmazione-territoriale-efficiente/connessione-rete"),
    ("IT-EDIS", "page", "https://www.e-distribuzione.it/a-chi-ci-rivolgiamo/produttori.html"),
    ("IT-ARETI", "page", "https://www.areti.it/servizi/connessione-impianti-produzione"),
    ("IT-UNARETI", "page", "https://www.unareti.it/it/chi-siamo/informazioni-servizio/connessioni-reti-elettriche"),
    ("LT-ESO", "page", "https://www.eso.lt/"),
    ("LV-AST", "page", "https://www.ast.lv/"),
    ("LV-ST", "page", "https://sadalestikls.lv/"),
    ("NL-TENNET", "page", "https://www.tennet.eu/nl/"),
    ("PL-ENEA", "page", "https://www.operator.enea.pl/przylaczone-i-dostepne-moce-oze"),
    ("PL-ENERGA", "page", "https://mocnestrefy.pl/"),
    ("PL-TAURON", "page", "https://dostepnemoce.tauron-dystrybucja.pl/"),
    ("PL-PGE", "page", "https://pgedystrybucja.pl/"),
    ("PL-STOEN", "page", "https://www.stoen.pl/pl/strona/chce-przylaczyc-sie-do-sieci"),
    ("PT-REN", "page", "https://www.ren.pt/"),
    ("RO-TEL", "page", "https://www.transelectrica.ro/procesul-de-alocare-a-capacitatii-retelei-electrice"),
    ("RO-DELGAZ", "page", "https://www.delgaz.ro/"),
    ("RO-EDIS", "page", "https://www.e-distributie.com/"),
    ("RO-DEER", "page", "https://www.distributie-energie.ro/"),
    ("RO-RETELE", "page", "https://www.reteleelectrice.ro/"),
    ("SE-VATTENFALL", "arcgis", "https://services-eu1.arcgis.com/dVRL7HtXQT22fiCW/arcgis/rest/services/Kategori_regionnät_260702/FeatureServer"),
    ("SE-ELLEVIO", "page", "https://www.ellevio.se/"),
    ("SE-EON", "page", "https://www.eon.se/"),
    ("SI-ELEKTRO", "page", "https://www.elektro-ljubljana.si/"),
    ("SK-SEPS", "page", "https://www.sepsas.sk/"),
    ("SK-SSD", "page", "https://www.ssd.sk/"),
    # ---- the EU's neighbours and Northern Ireland
    ("NI-NIE", "json", "https://www.nienetworks.co.uk/Connections/Capacity-Map?markers=1"),
    ("NI-SONI", "page", "https://www.soni.ltd.uk/"),
    ("NO-STATNETT", "page", "https://www.statnett.no/nettkapasitet-til-produksjon-og-forbruk/foresporsler-og-reservasjon-i-nettet/"),
    ("NO-ELVIA", "page", "https://www.elvia.no/"),
    ("NO-NVE", "page", "https://www.nve.no/"),
    ("CH-SWISSGRID", "pdf", "https://www.swissgrid.ch/dam/jcr:35ab9f4a-89d9-4093-8d1d-f4348a0b1aed/Capa-2026-2030-2035-2040-prod.pdf"),
    ("CH-EKZ", "page", "https://www.ekz.ch/"),
    ("CH-BKW", "page", "https://www.bkw.ch/"),
    ("CH-ELCOM", "page", "https://www.elcom.admin.ch/"),
    ("IS-LANDSNET", "page", "https://www.landsnet.is/"),
    ("IS-RARIK", "page", "https://www.rarik.is/"),
    ("RS-EMS", "page", "https://ems.rs/opis-i-kapaciteti/"),
    ("RS-EDS", "page", "https://elektrodistribucija.rs/"),
    ("BA-NOSBIH", "page", "https://www.nosbih.ba/"),
    ("BA-ELPRENOS", "page", "https://www.elprenos.ba/"),
    ("ME-CGES", "page", "https://cges.me/o-nama/karta-prenosnog-sistema/prikljucenje-na-prenosnu-mrezu/"),
    ("ME-CEDIS", "page", "https://cedis.me/prikljucenje-na-distributivni-sistem/"),
    ("MK-MEPSO", "page", "https://www.mepso.com.mk/index.php/mk/doma/za-nas/prikluchoci"),
    ("MK-EVN", "page", "https://www.elektrodistribucija.mk/Services.aspx"),
    ("AL-OST", "page", "https://www.ost.al/"),
    ("AL-OSHEE", "page", "https://oshee.al/lidhje-te-re/"),
    ("XK-KOSTT", "page", "https://www.kostt.com/"),
    ("XK-KEDS", "page", "https://www.keds-energy.com/"),
    ("MD-MOLDELECTRICA", "page", "https://moldelectrica.md/"),
    ("MD-PREMIER", "page", "https://premierenergy.md/"),
    ("UA-UKRENERGO", "page", "https://ua.energy/"),
    ("UA-NEURC", "page", "https://www.nerc.gov.ua/"),
    ("TR-TEIAS", "pdf", "https://webim.teias.gov.tr/file/54e18598-8a7f-48d1-bdd1-a7ee93cee521?download"),
    ("TR-EPDK", "page", "https://www.epdk.gov.tr/"),
    # ---- US: ISOs and transmission providers (FERC Order 2023 heatmaps)
    ("US-CAISO", "json", "https://www.caiso.com/poi-heatmap/WClusterTrLimSumJson.json"),
    ("US-MISO", "json", "https://cloud.cartovista.com/miso/api/v2/maps/maps"),
    ("US-PNM", "json", "https://cloud.cartovista.com/pnm/api/v2/maps/maps"),
    ("US-SOCO", "json", "https://cloud.cartovista.com/southerncompany/api/v2/maps/maps"),
    ("US-ISONE", "page", "https://www.iso-ne.com/system-planning/interconnection-service/interconnection-heatmap"),
    ("US-NYISO", "page", "https://www.nyiso.com/interconnections"),
    ("US-SPP", "page", "https://www.spp.org/engineering/generator-interconnection/"),
    ("US-PJM", "page", "https://www.pjm.com/planning/service-requests"),
    ("US-ERCOT", "page", "https://www.ercot.com/gridinfo/resource"),
    ("US-BPA", "page", "https://www.bpa.gov/energy-and-services/transmission/interconnection"),
    ("US-VELCO", "page", "https://www.velco.com/our-work/interconnection"),
    ("US-PGE-OR", "arcgis", "https://services6.arcgis.com/eqsXlDArbs19VWhn/arcgis/rest/services/TransmissionCapacity_PointsOfInterconnection/FeatureServer"),
    ("US-IPC", "arcgis", "https://services1.arcgis.com/A5HVOoaVqcd8etEM/arcgis/rest/services/InterconnectCapacity/FeatureServer"),
    ("US-LGEKU", "arcgis", "https://services.arcgis.com/NTSXKyJwdnK9ffCb/arcgis/rest/services/LGE_KU_FERC_Interconnection_HeatMap_MW/FeatureServer"),
    ("US-AVA", "arcgis", "https://services3.arcgis.com/WlYQgAChrqj0tuQi/arcgis/rest/services/HeatMap_MW_Impact_PRD/FeatureServer"),
    ("US-NVE", "arcgis", "https://services7.arcgis.com/Bq5yvxFKGREICK7t/arcgis/rest/services/NV_Energy_Interconnection_Queue/FeatureServer"),
    ("US-TVA", "page", "https://www.oasis.oati.com/woa/docs/TVA/TVAdocs/"),
    ("US-PACIFICORP", "page", "https://www.oasis.oati.com/woa/docs/PPW/PPWdocs/"),
    ("US-APS", "page", "https://www.oasis.oati.com/woa/docs/AZPS/AZPSdocs/"),
    ("US-XCEL", "page", "https://www.oasis.oati.com/woa/docs/PSCO/PSCOdocs/"),
    ("US-DUKE", "page", "https://www.oasis.oati.com/woa/docs/DUK/DUKdocs/"),
    # ---- US: distribution hosting capacity (state mandates, DOE atlas, aggregators)
    ("US-NG-NY", "arcgis", "https://systemdataportal.nationalgrid.com/arcgis/rest/services/NYSDP/Hosting_Capacity_Data/MapServer"),
    ("US-EVERSOURCE-MA", "arcgis", "https://services7.arcgis.com/TlTHaqj12dc3XKZt/arcgis/rest/services/MA_HostingCapacity/FeatureServer"),
    ("US-EVERSOURCE-NH", "arcgis", "https://services7.arcgis.com/TlTHaqj12dc3XKZt/arcgis/rest/services/NH_Hosting_Capacity/FeatureServer"),
    ("US-ORU", "arcgis", "https://services.arcgis.com/ciPnsNFi1JLWVjva/arcgis/rest/services/IEDR_ORU/FeatureServer"),
    ("US-ORNL-OEH", "json", "https://openenergyhub.ornl.gov/api/explore/v2.1/catalog/datasets?limit=100&where=search(%22hosting%22)"),
    ("US-IEDR", "page", "https://iedr.nyserda.ny.gov/"),
    ("US-DOE-ATLAS", "page", "https://www.energy.gov/eere/us-atlas-electric-distribution-system-hosting-capacity-maps"),
]  # fmt: skip

REFUSALS = [
    (re.compile(r"Just a moment|cf-chl|challenge-platform|Attention Required", re.I), "Cloudflare challenge"),
    (re.compile(r"<input[^>]+type=\"password\"|sign in|log ?in to continue", re.I), "login"),
    (re.compile(r"app\.powerbi\.com/view", re.I), "Power BI report"),
    (re.compile(r"cloud\.cartovista\.com", re.I), "CartoVista map"),
    (re.compile(r"arcgis\.com/apps|experience\.arcgis\.com|/FeatureServer", re.I), "ArcGIS app"),
]  # fmt: skip


def page(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    t = r.text if "text" in r.headers.get("content-type", "") else ""
    title = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
    seen = [label for rx, label in REFUSALS if rx.search(t)]
    files = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx?|csv|zip|kmz?))"', t, re.I)))[:3]
    head = (title.group(1).strip()[:60] if title else "").replace("\n", " ")
    return (
        f"{r.status_code} {head!r}"
        + (f" [{', '.join(seen)}]" if seen else "")
        + (f" files: {' '.join(files)}" if files else "")
    )


def arcgis(client: httpx.Client, url: str) -> str:
    d = client.get(url, params={"f": "json"}).json()
    if "error" in d:
        return f"error {d['error'].get('code')} {d['error'].get('message')}"
    out = []
    for lyr in (d.get("layers") or []) + (d.get("tables") or []):
        n = client.get(
            f"{url}/{lyr['id']}/query",
            params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        ).json()
        out.append(f"[{lyr['id']}] {lyr['name']} n={n.get('count')}")
    return "200 " + "; ".join(out[:8])


def as_json(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    if r.status_code != 200:
        return f"{r.status_code}"
    d = r.json()
    if isinstance(d, dict):
        k = next((k for k in ("wcResults", "results", "maps", "data") if k in d), None)
        size = len(d[k]) if k else len(d)
        return f"200 {len(r.content):,} B, keys {list(d)[:5]}, {k or 'items'}={size}"
    return f"200 {len(r.content):,} B, {len(d)} records"


def pdf(client: httpx.Client, url: str) -> str:
    import pdfplumber

    r = client.get(url)
    if r.status_code != 200:
        return f"{r.status_code}"
    with pdfplumber.open(io.BytesIO(r.content)) as p:
        first = ((p.pages[0].extract_text() or "").splitlines() or [""])[0]
        return f"200 PDF {len(p.pages)} pages, {len(r.content):,} B: {first[:90]!r}"


KINDS = {"page": page, "arcgis": arcgis, "json": as_json, "pdf": pdf}


def probe(c: tuple[str, str, str]) -> str:
    code, kind, url = c
    try:
        with httpx.Client(headers=UA, timeout=45, follow_redirects=True) as client:
            return f"{code:20} {kind:6} {KINDS[kind](client, url)}  <{url}>"
    except Exception as e:  # noqa: BLE001 - every answer, also a failure, is a finding
        return f"{code:20} {kind:6} ERR {type(e).__name__}: {str(e)[:80]}  <{url}>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    todo = [c for c in CANDIDATES if not only or c[0] in only]
    with ThreadPoolExecutor(6) as ex:
        for line in ex.map(probe, todo):
            print(line, flush=True)


if __name__ == "__main__":
    main()
