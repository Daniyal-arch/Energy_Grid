---
name: emissions
description: Emissions - reported (verified) versus modelled figures, which installations are placed on the map, units and GWP versions. Use for CO2 or greenhouse-gas questions about installations, sectors or countries.
---
# Emissions

Relies on: `uk_ets`, the EU ETS (map file `ets.json`), `ghgrp` (US EPA), `edgar` (JRC),
`ghg_inventory`, `live_co2`.

1. Reported versus modelled: ETS and GHGRP figures are reported (verified) per installation;
   EDGAR and Climate TRACE are modelled. Never mix the two in one total; say which kind a figure is.
2. Placed installations: in the EU ETS only some installations have a published position (2,234
   of 9,668; Germany 78 of 1,818); UK ETS installations are not placed. A map of emitters shows
   only placed ones: say how many are left out.
3. Units and GWP: t CO2e or Mt CO2e; EDGAR uses GWP-100 AR5, GHGRP AR4. Name the GWP when
   comparing sources.
4. Years: ETS compliance years; EDGAR covers 1970-2024. State the year of every figure.
5. Totals are sums of the recorded emissions (computed): say so.
