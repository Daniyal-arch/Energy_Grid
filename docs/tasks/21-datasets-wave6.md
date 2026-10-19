# 21. Datasets wave 6: 24 datasets in one session

Start after brief 17 (wave 5) is merged: this wave uses its NUTS regions, admin-1 shapes, catalogue
files and `scripts/wave5_common.py`. Read CLAUDE.md, then this file, then only the templates named in
brief 17's token rules (same templates, same helper, same file standard).

Theme: what a developer screening a site asks next — **can I connect here, what stops me building
here, what is being built, what does it cost** — plus regional detail the agent can map.

## Run to the end (owner's standing approval, 2026-10-19)

1. **Probe once, then build without stopping.** Step 1 is `scripts/probe_wave6.py` run once in
   Actions (one step per group, ≤ 10 `::notice` lines each). From its output, decide per dataset:
   build as specified, a documented fallback, or ⛔. Write the decisions as a table at the top of
   the PR and carry on; do not wait for the owner.
2. **Allowed reasons for ⛔:** a login or key the environment lacks (name the env var and the
   sign-up URL), a licence that forbids reuse or is non-commercial, or a source that fails twice in
   Actions (quote the error). A source that only offers PDFs is ⛔ too (no PDF scraping).
3. **Downloads:** files up to 1 GB each are approved in Actions; larger ones are ⛔ with their size
   (the owner decides).
4. **Done means** (same as brief 17): built in Actions, output present (repo ≤ 5 MB, else R2 / lake),
   the UI piece below, a refresh step, docs/DATA_SOURCES.md section (≤ 10 lines), docs/DATA_LAKE.md
   row, `agent/catalog/<name>.yaml`, one pytest. Partial work stays ☐.
5. **Token rules:** brief 17's, unchanged (one helper, one `wave6.yml` build workflow with one job per
   group and `continue-on-error`, one polling command per run, last 40 log lines of a failure, no
   exploring, no screenshots, one commit per dataset, one PR with the checklist).

## The datasets (in this order)

### A. Room to connect (cards in the country panel, "Grid capacity" layer extended; feeds the site analysis)

1. **France: capacity per substation** — Capareseau / ODRÉ "capacités d'accueil" (RTE and Enedis,
   Licence Ouverte). Substations with reserved and available capacity → the `connect` layer and the
   site analysis "Room to connect" card.
2. **Italy: connection requests** — Terna Econnexion open data (requests by region/province and source).
   Card per region; NUTS-2 shading in the `connect` layer.
3. **Belgium: hosting capacity** — Elia (transmission) and Fluvius/ORES (distribution) capacity maps.
4. **Portugal: reception capacity** — E-REDES open data and REN (capacity per substation/area).
5. **Ireland: capacity heat maps** — EirGrid and ESB Networks.
6. **Poland: available connection capacity** — PSE and the DSOs' published lists (machine-readable
   only).

### B. Grid and networks

7. **Substations worldwide** — from our own lake (`lake/overture_power/` sites, Overture/OSM, ODbL; no
   new download): PMTiles on R2 by voltage, read by the site analysis outside Europe (nearest
   substation, substations in the area) like the line tiles in `frontend/src/lib/site.ts`.
8. **Germany: grid operator per municipality** — from MaStR in the lake (the operator each unit is
   connected to), the operator with most units per municipality and the count of operators; a row in
   the site analysis.
9. **US utility service territories** — EIA-861 service territory per county (PUDL, in place);
   "which utility serves here" in the site analysis and the US state card.
10. **Sea cables and pipelines** — EMODnet Human Activities (CC BY 4.0, WFS like the wind farms):
    the "Undersea power cables" layer gains EMODnet's European cables; a "Gas and oil pipelines at
    sea" addition to the pipelines layer.

### C. What stops a build (the site analysis "Constraints" card + map layers, group "Risk")

11. **Protected areas** — Natura 2000 (EEA) and the US PAD-US (USGS, public domain): PMTiles,
    layer "Protected areas"; the site analysis lists the protected areas in its area and the share
    of the area they cover (computed).
12. **River flood hazard** — JRC flood hazard maps (100-year return period depth, Europe and global,
    CC BY 4.0): raster tiles + a lookup grid like the atlases; flood depth class at the site.
13. **Major roads and railways** — Overture transportation (motorway, trunk, primary; rail), Europe and
    US first: PMTiles; distances to the nearest major road and rail line in the site analysis.

### D. What is coming and what it costs (cards; agent catalogue)

14. **Hydrogen projects** — IEA Hydrogen Production Projects database (check licence) or the EU
    Hydrogen Observatory: electrolyser projects with status and capacity; layer in "Industry & demand".
15. **Renewable auction results** — AURES II auction database (Europe): rounds, awarded MW, prices; a
    card in the country panel's Prices tab.
16. **Technology costs** — NREL Annual Technology Baseline (CC BY 4.0) and IRENA's renewable cost
    database: agent catalogue + a "What new capacity costs" card (world and US).
17. **Gas infrastructure coming** — ENTSOG TYNDP projects: layer "Planned gas projects" next to the
    TYNDP power projects of wave 5.
18. **National greenhouse-gas inventories** — EEA (EU) / UNFCCC data: emissions by sector per country
    in the country report.

### E. United States: reliability and demand

19. **DOE OE-417 electric disturbance events** (public domain): events by state and cause; a card in
    the US panel and points in the "US power outages" layer's card.
20. **FERC Form 714 hourly demand per planning area** (PUDL, in place): the agent catalogue; a
    planning-area demand line in the US region card.

### F. More regional and live grids

21. **France regional mix** — ODRÉ éCO2mix régional (12 regions, 15 min, Etalab; no key): region
    cards and NUTS-1 shading for the agent.
22. **Spain regional mix** — REE REData (no key): generation by region.
23. **New Zealand live** — Electricity Market Information (EMI, Electricity Authority, CC BY 4.0)
    and Transpower: live grid card + "Live grids" layer entry.
24. **South Africa** — Eskom data portal (demand, generation by type, load-shedding stage): live
    grid card.

## Out of scope

The backend and the agent (briefs 18–20), alerts, keyed sources still waiting (PJM, AESO, KPX,
EPİAŞ, Fingrid, netztransparenz API, NASA Earthdata), redesigns of existing layers.
