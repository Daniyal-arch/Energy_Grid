// "Sources & method" texts for the panel (the long form of docs/DATA_SOURCES.md).

export type Sources = [string, string][];

export const LIVE_SOURCES: Sources = [
  ["Load, generation, prices, flows", "ENTSO-E Transparency Platform; values passed through, newest complete 15-min interval per country."],
  [
    "Great Britain",
    "Elexon (BMRS): generation by fuel every 5 minutes (the reading at each quarter-hour), national demand half-hourly, and every interconnector's flow. Transmission-level only.",
  ],
  [
    "Computed from them",
    "Renewable share = renewable types / all generation types reported. Border flow = flow one way minus the other. EU = sum of the member states with data. Net import/export = sum of the measured border flows.",
  ],
  [
    "Plants offline",
    "ENTSO-E unavailability of generating units (A80), newest revision, cancelled ones left out. Offline = nominal power minus available capacity now; totals are sums. Units report from 100 MW; they carry no coordinates, so outages are shown per country.",
  ],
  [
    "Wind and sunshine",
    "Live, whole globe: ECMWF open data (IFS 0.25°, CC BY 4.0), wind at 100 m every 3 h and surface solar radiation as the average of the 3 hours before each step, kept at the 0.25° points that fall on a 2° grid (80° S to 80° N). 24 h archive over Europe: Open-Meteo forecast API, wind at 100 m (turbine hub height) and shortwave radiation (W/m², average of the hour), hourly on a 2° grid: model values, not measurements. Between grid points and hours the drawing is interpolated.",
  ],
];

export const GAS_SOURCES: Sources = [
  ["Gas storage", "GIE AGSI+, daily, fill as % of working gas volume."],
  ["LNG", "GIE ALSI, daily: send-out into the grid and the terminals' declared send-out capacity (GWh/day), LNG in tanks."],
  ["Gas network", "SciGRID_gas (2021): pipelines, LNG terminals and storage sites."],
];

export const PLANT_SOURCES: Sources = [
  ["Plants, grid", "powerplantmatching (plants ≥ 20 MW on the overview, every unit ≥ 1 MW for a selected country); PyPSA-Eur from OpenStreetMap (ODbL)."],
  ["Installed capacity", "Energy-Charts installed power, newest year with values (carried over while Energy-Charts is down)."],
  ["Hydro reservoirs", "ENTSO-E Transparency, weekly stored energy."],
];

export const PRICE_SOURCES = (period: string): Sources => [
  ["Prices", "ENTSO-E day-ahead prices (A44) of the coupled auction, every 15 minutes since 1 Oct 2025 (hourly zones fill all four quarters)."],
  [
    "Computed from them",
    "Average = mean of all 15-min prices. Hours below zero = 15-min intervals with a negative price × 0.25 h. Capture price = Σ price × output / Σ output, with ENTSO-E's actual solar (B16) and wind (B18 + B19) generation of the zone; capture rate = capture price / average.",
  ],
  ["Period", `The twelve full months ${period}. Time of day: the average price per local hour (CET/CEST), per season and per month.`],
  ["Markers", "Zone markers in DK, IT, NO and SE are placed for reading, not at an official zone centre."],
];

export const YEAR_SOURCES: Sources = [
  [
    "Yearly figures",
    "Ember yearly electricity data (CC BY 4.0), as published: shares of generation (renewables, wind and solar, coal), carbon intensity of generation, generation by source (TWh).",
  ],
  ["Coverage", "Countries without a figure for the year are drawn grey. Ember's newest year is not yet out for every country."],
  ["Ranking (world)", "The 30 countries with the largest total generation that year (Ember's published total)."],
  ["Outlines", "Europe: Eurostat GISCO 1:20M; rest of the world simplified from the same dataset. © EuroGeographics."],
];

export const WORLD_SOURCES: Sources = [
  [
    "Power plants",
    "Global Energy Monitor, Global Integrated Power Tracker, September 2026 release (CC BY 4.0). Units summed per location, fuel and status; planned = pre-construction + announced; retired includes mothballed; cancelled and shelved left out.",
  ],
  ["Access to electricity", "World Bank WDI EG.ELC.ACCS.ZS (CC BY 4.0), % of population; each country coloured by its newest year."],
  [
    "Data centres",
    "OpenStreetMap (ODbL): features tagged telecom=data_center or building=data_center. A mapped subset: counts follow mapping effort, not capacity. Countries assigned with Eurostat GISCO outlines.",
  ],
  ["Australia", "AEMO's public NEM summary, 5-minute dispatch: price (AUD/MWh), demand, interconnector flows. Region markers are placed for reading."],
  [
    "United States",
    "EIA-930 hourly data (EIA API v2, public domain) for the 13 EIA regions: demand (about 1 h behind), generation by fuel and net interchange (about a day behind), flows between regions (about two days behind), each with its own hour. Region markers are placed for reading.",
  ],
  [
    "Brazil",
    "ONS Energia Agora: load, generation by source and imports/exports per subsystem, and the flows between subsystems, as published every few minutes. Markers are placed for reading; Imperatriz is ONS's junction node.",
  ],
  [
    "Taiwan",
    "Taipower open data (data.gov.tw dataset 8931), every 10 minutes: net generation and installed capacity of every unit Taipower owns or buys from, with its status note. Type totals are Taipower's subtotals; the island total is their sum (computed). No interconnectors. The marker is placed for reading.",
  ],
  [
    "Ontario",
    "IESO public reports (no key): Ontario demand and the Ontario zonal price every 5 minutes, every generator's hourly output with its fuel, actual intertie flows every 5 minutes (positive = export). Fuel totals = sums of the generators reporting for the newest hour with output from at least 80 % of them; each neighbour's flow = sum of its interties (computed). Eastern Standard Time all year. Markers are placed for reading.",
  ],
  [
    "Installed capacity",
    "IRENA statistics (IRENASTAT): electrical installed capacity (MW) per country and technology, all grid connections, 2000 to the newest year, as published in IRENA's own categories. Wind = onshore + offshore (summed here). The map colours by GW on a logarithmic scale.",
  ],
  ["Renewables", "Ember yearly data (CC BY 4.0), newest year with a figure; by month: Ember monthly data, last 24 months (fewer countries)."],
  [
    "Power grid",
    "OpenStreetMap (ODbL): every power line tagged 220 kV or more, with its voltage; vector tiles served from Cloudflare R2. Well mapped in Europe and North America, patchier elsewhere. Predicted local grid (optional): Gridfinder (Arderne et al. 2020, CC BY 4.0), lines predicted from night-time lights and roads.",
  ],
  [
    "Undersea cables",
    "OpenStreetMap (ODbL): power cables mapped underwater, classed by their tags (HVDC, AC from 110 kV, smaller, untagged), kept whole where at least half of a cable lies at sea. Well mapped around Europe, sparse elsewhere.",
  ],
];

export const CREDITS =
  "ENTSO-E · Elexon · GIE · Ember (CC BY 4.0) · Open-Meteo (CC BY 4.0) · Global Energy Monitor (CC BY 4.0) · World Bank · EIA · ONS · AEMO · © OpenStreetMap contributors (ODbL) · powerplantmatching · SciGRID_gas · © EuroGeographics";
