# Dark-cell pass 4 (2026-11-06): congestion and connect

Cells checked: 19. That is 7 congestion cells (BG, HR, CY, LU, MT, RO, SI) and 12 connect cells
(CY, LV, RO, IS, RS, BA, ME, MK, AL, XK, MD, UA; BE and NO were done in the earlier pass).
Per-cell notes are in `cells.yaml` and registry entries in `sources.yaml`.

## New sources that can be built
- **lv_st_free_capacity** (connect LV): the JSON behind Sadales tīkls' free-capacity map
  (`https://karte.sadalestikls.lv/lv/briva-jauda/all`). It lists 132 substations with
  `power_consumption` and `power_generation` (free MW), `name`, `number` and `update_date`.
  The coordinates are EPSG:3059 with swapped names: lon = `y_coord` (easting), lat = `x_coord`.
  The earlier pass got HTTP 451 here; this time the URL answered 200 to an honest UA.
  **The licence is not quoted yet**: the sadalestikls.lv terms page did not answer.
- **ro_transelectrica_zone_capacity** (connect RO): HTML tables on the Transelectrica
  capacity-allocation page give available MW and the auction starting price (lei/MW) for each
  zone A–J and each year 2028–2037. Anexa 4 (PDF) defines the zones by county, so zone outlines
  can be built from the county outlines. Needs an HTML-table kind in wave9.py.
- **rs_ems_connection_queue** (connect RS): the EMS PDF list of every grid-connection request
  (2026-11-04). It gives type, kV, requested and approved MW, location name and phase.
  Needs a PDF-table kind (`pdftotext -layout` reads it cleanly).

## Blocked
- **cy_eac_pv_curtailment** (congestion CY): EAC's DSO publishes daily PV curtailment
  reports (PDFs with curtailed MWh and %). The EAC terms say "own use" only, with no
  reproduction without written consent.
- **cy_eac_hosting_capacity** (connect CY): the substation hosting-capacity ArcGIS dashboard.
  Its layers sit behind utility.arcgis.com secured proxies that answer 403, and no licence is stated.

## Licence caveat
RO and RS state no reuse licence. Each is a list the law requires the operator to publish
(ANRE Order 53/2024; the Serbian RES law). They are marked `build` on the same "public notice"
basis as the AT/BG connect cards. The owner should confirm that basis before using them
commercially, or ask the operators.

## Still dark (nothing published as data)
- congestion: BG, HR, LU, MT, RO, SI
- connect: IS, BA, ME, MK
- connect, behind Cloudflare or a TLS failure (not bypassed): AL, XK, MD, UA. UA DSO data is
  also limited under martial law.

## Probe artefacts
Files are in `dl_*` and `probe/` in this folder (all under 30 MB): the RO PDFs and PNG,
the CY curtailment PDFs, the RS queue PDFs, the LV `all.json` and the HR 2025 basic-data PDF.
