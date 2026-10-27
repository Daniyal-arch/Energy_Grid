---
name: prices
description: Day-ahead and retail electricity prices - zones, precision, averages, negative hours. Use for any question about a price level, a price spread, hours below zero or capture prices.
---
# Prices

Relies on: `app.eu_prices` (ENTSO-E A44, 12 months), `prices_gb_us_rt`, `jepx`, `smard`,
`gb_retail`, the live snapshot (`live` with `eu_snapshot`).

1. Zones, not countries: day-ahead prices belong to bidding zones (DE-LU, DK1, DK2, NO1-NO5,
   SE1-SE4, IT-*). A country with several zones gets one figure per zone; never average zones
   into a country figure.
2. Precision: keep the source's precision (EUR/MWh to the cent). Averages are computed (say
   "mean of the hourly prices"); `app.eu_prices.mean_eur_mwh` is already that mean.
3. Negative hours: `negative_hours` counts hours with a price below zero; 15-minute intervals
   count as quarter hours, so the figure can have .25, .5 and .75.
4. Period: always state the period (`period_start` to `period_end`). Compare periods only when
   both come from the same source and resolution.
5. Retail prices (Eurostat bands, EIA states) are a different thing: name the band and the taxes.
6. Units: EUR/MWh for wholesale, EUR/kWh or cents/kWh for retail; US prices in USD/MWh.
