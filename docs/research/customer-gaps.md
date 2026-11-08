# Wave 9 gap topics: sources checked (2026-11-05)

Probed from the cloud sandbox (proxy). Entries are in `gaps.yaml`, new families in `families.yaml`.
Rules applied: commercial reuse allowed, no login-only data, no estimates, no bypassing of 403, WAF or
logins. No download was over 2.2 MB.

## 1. Data-centre electricity per country

| Candidate | Evidence | Decision |
|---|---|---|
| Ireland CSO MEC02 / MEC03 | Already in the registry (`ie_cso_datacentres`, `ie_cso_dc_consumption`, CC BY 4.0). MEC02 answered 200 again. | have |
| **Netherlands CBS maatwerk 2025/51** | `datacenters_elektriciteitsleveringen_2017_2024.xlsx` (33,566 B). Sheet `Tabel 1` holds GWh delivered to data centres via the public grid in 2017-2024* (total 1,652 rising to 5,093 GWh in 2024*), split < / >= 10 GWh. It also has the share of national consumption (4.58 % in 2024*), connections >= 10 GWh, and from 2023 connections >= 10 MW. The method is register-based (TenneT and DSO customer files, matched to the RVO EED Art. 12 reports). Licence, from [cbs.nl copyright](https://www.cbs.nl/nl-nl/over-ons/website/copyright): "(CC BY 4.0) van toepassing. Dit houdt in dat hergebruik van de inhoud van deze site is toegestaan, mits CBS als bron wordt vermeld." | **build** `nl_cbs_datacentres` |
| EU database of data centres (EED Art. 12) | The [Commission page](https://energy.ec.europa.eu/topics/energy-efficiency/energy-efficiency-targets-directive-and-rules/energy-efficiency-directive/energy-performance-data-centres_en) links the aggregated results only as a Qlik Sense dashboard (`link.europa.eu/q7x39t` redirects 307 to `dashboard.tech.ec.europa.eu`) and as PDF reports (the July 2025 study and COM(2026) 500). There is no CSV or XLSX. The directive allows publication only in aggregated form. | blocked `eu_eed_datacentres_dashboard` (request: per-country aggregates as CSV) |
| Germany Rechenzentrumsregister (EnEfG) | The public register at `rechenzentrumsregister.bund.de` (published 14 Aug 2026, 319 DCs according to [UBA](https://www.umweltbundesamt.de/themen/rechenzentrumsregister-daten-widerlegen-hohe)) failed curl TLS verification even with the proxy CA bundle, and returned 503 to a fetch. The operator portal `rzreg.bundeswirtschaftsministerium.de` is a Keycloak login. No licence or file was found. | blocked `de_rzreg_datacentres` |
| Norway SSB table 14489 | The table answers and is CC BY 4.0, but it has no data-centre group (nearest is "Informasjon og kommunikasjon", NACE J). NVE's data-centre TWh are estimates. | left_out `no_ssb_14489_ict` |
| Denmark (Energistyrelsen, DST) | Only projections (AF22-AF25, COWI) were found, which are estimates. Statbank search for data centres found nothing. | not_published `dk_ens_datacentres` |
| Sweden Energimyndigheten | The EED reporting page has no aggregated file. | not listed |

## 2. Clean-tech factories

| Candidate | Evidence | Decision |
|---|---|---|
| Clean Investment Monitor | Already blocked in the registry (needs a ClimateDeck account). | (existing) |
| **Clean Hydrogen Observatory, electrolyser manufacturing capacity** | `Electrolyser manufacturing capacity May2026.xlsx` (138,025 B): Year, Technology, Capacity unit (GW), Status, 10 rows for EU27+EFTA+UK as one total. No sites. [Legal notice](https://observatory.clean-hydrogen.europa.eu/legal-notice): "©Clean Hydrogen JU, Reproduction is authorised, provided the source is acknowledged, save where otherwise stated." | **build** `eu_cleanh2_electrolyser_mfg` (partial: total, not sites) |
| Bruegel European Clean Tech Tracker | The [dataset page](https://www.bruegel.org/dataset/european-clean-tech-tracker) moved to `european-clean-tech-tracker.bruegel.org`, which has charts only (capacity by company and HQ country) and no file. Footer: "© BRUEGEL. All rights reserved." | left_out |
| SolarPower Europe Solar Manufacturing Map | An interactive page with no file. SPE claims copyright over its market data. | left_out |
| T&E gigafactory analyses | Reports only (2021, 2023, 2025), with no dataset or licence. | not_published |
| New AutoMotive European Battery Tracker | An interactive tool with no download or licence. | left_out |
| IEA | No factory list. Free datasets are CC BY-NC-SA 4.0 IGO ([WEO 2025 free dataset](https://www.iea.org/data-and-statistics/data-product/world-energy-outlook-2025-free-dataset)), and commercial use needs a paid licence. | left_out |
| BNEF, Benchmark, Fastmarkets | Paid. | excluded |
| Wikidata | The API answered 429 (shared-IP rate limit). It was not retried. | not probed |

There is no open, commercially reusable site-level clean-tech factory list for Europe. The cell stays partial (Clean Hydrogen total only).

## 3. Fibre and long-haul telecom routes

| Candidate | Evidence | Decision |
|---|---|---|
| **EMODnet Human Activities, telecom cables (national layers)** | The WFS answers GeoJSON per layer: DE BSH-CONTIS 28 cables, ES CICA 29, FR SHOM 603 segments, FR SIGCables 60, MT 6. Metadata (`EMODnet_HA_Cables_20210126`, [Sextant](https://sextant.ifremer.fr/geonetwork/srv/api/records/EMODnet_HA_Cables_20210126)): "Re-use of content for commercial or non-commercial purposes is permitted free of charge, provided that the sources (both EMODnet - Human Activities, and primary sources) are acknowledged." | **build** `de_emodnet_telecom_bsh`, `es_emodnet_telecom_cica`, `fr_emodnet_telecom_shom`, `fr_emodnet_telecom_sigcables`, `mt_emodnet_telecom` |
| EMODnet UK OGA layer | Answers with 30 cables, but the primary source is NSTA (non-commercial Open User Licence; see `gb_nsta_pipelines`). | left_out `gb_emodnet_telecom_oga` |
| **OpenStreetMap via Overture** (`base/infrastructure`, class `communication_line`) | DuckDB probe on release 2026-09-23.1, Europe box: 6,973 ways and 88,828 km. By medium: 3,833 fibre, 493 copper. By location: 4,005 underground, 132 underwater. Operators are mostly local FTTH networks. Germany box alone: 4,182 lines, plus 25k communication towers. ODbL allows commercial use. It is a mapped subset, not a long-haul network. Probe scripts: `scratchpad/probes/probe_overture_comm*.py`. | **build** `eur_overture_comm_lines` (custom) |
| Overpass (OSM) | overpass-api.de reset the connection, and kumi.systems timed out. This matches `scripts/probe_us_lines.py`. | use Overture |
| TeleGeography Submarine Cable Map | The JSON answers (754,659 B), but [TeleGeography](https://www2.telegeography.com/license-telegeography-map) grants CC BY-SA 4.0 only for "Any reference to a TeleGeography map, URL, or any related screen capture", and states "Access to the underlying databases remains restricted to paying subscribers." The old GitHub copy was CC BY-NC-SA 3.0. | left_out |
| BNetzA Infrastrukturatlas | "Der Infrastrukturatlas ist nicht öffentlich zugänglich": registration plus an approved application (fact sheet). | left_out |
| EU broadband atlas / coverage study | Coverage per area only, with no routes. Already in the `broadband` family. | (existing) |

## 4. Industrial heat demand per site

| Candidate | Evidence | Decision |
|---|---|---|
| Hotmaps industrial database | Already in the lake (`agent/catalog/hotmaps.yaml`, CC BY 4.0). Its excess heat is modelled. | have `have_hotmaps_industry` |
| EEA Industrial Reporting, LCP | Already in the lake (`industrial.lcp`: reported fuel input per large combustion plant). A reported proxy. | have `have_eea_lcp` |
| **BfEE Plattform für Abwärme (EnEfG §17)** | [BfEE page](https://www.bfee-online.de/BfEE/DE/Effizienzpolitik/Plattform_fuer_Abwaerme/plattform_fuer_abwaerme_node.html): "Alle öffentlichen Meldungen bis zum 30. September 2026 stehen ... als Download zur Verfügung ... über 3.000 Firmen ... über 24.000 Abwärmepotentiale ... 209 TWh"; "Eine Registrierung oder ähnliches ist nicht erforderlich"; "Der Datensatz darf gemäß der Lizenz CC BY 4.0 verwendet werden"; FAQ "Dürfen die Daten für wissenschaftliche oder kommerzielle Zwecke verwendet werden? Ja." The app's public list endpoint gave `total: 24355` and a two-row page with the fields listed in the entry: address, kWh/a, kW, temperature, monthly profile, and the company's own "geschätzt" flag. There are no coordinates. | **build** `de_bfee_abwaerme` (custom; use the platform's Excel export, URL still to locate; show the "geschätzt" flag; excess heat, not demand) |
| sEEnergies D5.1 (Zenodo 4785411, CC BY 4.0) | The record holds only the report PDF. Site potentials are modelled, so they are estimates. | left_out |
| National heat atlases (NRW Wärmekataster, NL WarmteAtlas, IE National Heat Study) | Modelled building or industrial heat demand, so estimates. Not probed further. | not listed |

## 5. Corporate PPAs

| Candidate | Evidence | Decision |
|---|---|---|
| RE-Source Platform | resource-platform.eu answered 503. Its PPA figures come from paid data partners (BNEF; the Pexapark tracker, per [pv magazine 2020](https://www.pv-magazine.com/2020/02/18/an-open-access-online-european-ppa-tracker/), is freemium software). No open deal list. | left_out `eu_resource_ppa` |
| GME Bacheca PPA (Italy) | Publishes only daily ad summaries and a monthly aggregate count and quantity of contracts, "in forma aggregata e anonima". [Copyright page](https://www.mercatoelettrico.org/it-it/Home/Copyright/): use is subject to the site conditions, with no open licence. | left_out |
| FERC EQR (US, public domain) | www.ferc.gov returned a Cloudflare challenge (403), which was not bypassed. EQR does not flag corporate buyers. | blocked `us_ferc_eqr` (try from GitHub Actions) |
| Pexapark, LevelTen, BNEF | Paid. | excluded |

There is no open, licensed corporate-PPA deal dataset for Europe. The family stays empty, with this evidence recorded.
