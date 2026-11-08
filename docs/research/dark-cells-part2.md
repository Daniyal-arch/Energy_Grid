# Dark cells, second pass (brief 30 track 2.3)

The sources probed and their licences are in `sources.yaml`, and one note per cell checked is in `cells.yaml`. Probes ran from the sandbox through the proxy with no ENTSO-E key; nothing behind a WAF or login was bypassed.

## Balancing and reserves (`balancing`, 26 dark cells checked)
- **New sources to build:** `be_elia_balancing` (Elia ods166/ods207/ods206; quote the licence page first, it was down), `fr_odre_balancing_volumes` (Licence Ouverte 2.0, annual), `ie_semo_imbalance` (EirGrid Group Open Data Licence, custom XML kind).
- **Quick win:** ENTSO-E A85 imbalance prices are already in `eu/imbalance.json` for AT BE CZ EE ES FI FR GR HR HU IT LV NL PL PT RO SI SK SE. Those cells can be marked `partial` now. Reserves need the planned ENTSO-E XML kind: A81/A89 (B95; A52/A51/A47; type_MarketAgreement A01), A84/A83 (A16) and A15, run in Actions. A85 answers nothing for BG, DE-LU, IE-SEM and LT.
- **Not dark, only blocked by config:** FI needs the `FINGRID_API_KEY` secret. For SE, the CC BY 4.0 CSV is clean and the DuckDB sniff failed, so read it with `sample_size=-1` or explicit columns.
- **Blocked:** PL PSE API (works, no licence stated), GR IPTO files (works, terms grant no reuse), CZ ČEPS (no licence), ES e·sios (token: `ESIOS_TOKEN`; REData markets behind Incapsula), Baltic dashboard (Cloudflare; Elering `/api/balance` is all null). DE/NL/FR alternatives need free registrations: netztransparenz OAuth, TenneT API key, RTE OAuth.
- **Not re-probed nationally (time):** BG HR HU PT RO SK SI LU. ENTSO-E is the route for these. CY and MT are isolated systems.

## Redispatch and curtailment (`congestion`, 7 of 14 checked)
- **New sources to build:** `dk_energinet_countertrade` (CC BY 4.0, 15-min), `fi_fingrid_special_regulation` (dataset 391, CC BY 4.0, key; find the down dataset id with the key), `ie_eirgrid_dispatch_down` (monthly dispatch-down MWh/% by cause and region; two-row header, needs a reshape).
- **Still not published:** SE (SVK data service has no such set), SK (PDF decisions only), EE (no endpoint), GR (no file, no licence).
- **Not reached:** BG HR CY LU MT RO SI.

## Room to connect (`connect`, 2 of 14 checked)
- **BE:** Elia ods183 congestion-risk indicator per zone exists but is not connection capacity (`be_elia_congestion_risk`, left_out). It could serve the congestion card instead.
- **NO:** still nothing as data (Power BI only).
- **Not re-checked:** CY, LV, RO and the non-EU neighbours. The first pass (2026-10-28, browser discovery) stands.

## Rooftop and small solar (`rooftop_solar`, 1 of 1)
- **US:** `us_eia861m_small_solar` (EIA-861M small-scale PV capacity and generation per state and month, public domain, 64 KB) is ready to build. LBNL Tracking the Sun stays blocked.
