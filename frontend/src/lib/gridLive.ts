// Display helpers for the Live Grid card + cross-border flow arcs. All numbers
// (carbon intensity, mix, price, flow) come from the backend — this file only
// maps them to colors/labels/coordinates, never computes anything (CLAUDE.md
// rule 1: the frontend never computes facts).

import type { RGB } from "./theme";

// green/amber/red ramp reusing the project's own state tokens, not Electricity
// Maps' literal palette. Thresholds: clean grid <150 gCO2/kWh, dirty >400.
export function colorForIntensity(g: number): RGB {
  if (g < 150) return [88, 182, 140]; // positive (matches STATE_COLOR.complete)
  if (g < 400) return [216, 170, 86]; // warn (matches STATE_COLOR.clearing)
  return [212, 92, 78]; // alert
}

export type Fuel =
  | "lignite"
  | "hard_coal"
  | "gas"
  | "oil"
  | "nuclear"
  | "biomass"
  | "hydro"
  | "solar"
  | "wind"
  | "geothermal"
  | "waste"
  | "other";

// reuse TECH_COLOR where the fuel maps 1:1 to a monitored technology; the
// fossil fuels energy-charts splits out get their own muted tones, distinct
// from the existing single "combustion" tech color.
export const FUEL_COLOR: Record<Fuel, RGB> = {
  solar: [224, 176, 72],
  wind: [108, 158, 216],
  biomass: [142, 186, 86],
  hydro: [78, 182, 196],
  geothermal: [206, 124, 168],
  nuclear: [156, 138, 208],
  lignite: [120, 84, 76],
  hard_coal: [90, 90, 96],
  gas: [196, 130, 96],
  oil: [150, 96, 84],
  waste: [128, 132, 110],
  other: [110, 116, 128],
};

export const FUEL_LABEL: Record<Fuel, string> = {
  solar: "Solar",
  wind: "Wind",
  biomass: "Biomass",
  hydro: "Hydro",
  geothermal: "Geothermal",
  nuclear: "Nuclear",
  lignite: "Lignite",
  hard_coal: "Hard coal",
  gas: "Gas",
  oil: "Oil",
  waste: "Waste",
  other: "Other",
};

// order mix bars: renewables first, then fossil, then other
export const FUEL_ORDER: Fuel[] = [
  "solar",
  "wind",
  "hydro",
  "biomass",
  "geothermal",
  "nuclear",
  "gas",
  "hard_coal",
  "lignite",
  "oil",
  "waste",
  "other",
];

// DE neighbor zones reported by /cbpf, for cross-border flow arcs. Includes two
// non-land-border DC interconnects (NordLink to Norway, the Baltic Cable to
// Sweden) — coordinates are the approximate landing point, not a country centroid.
export const EXCHANGE_COUNTRY_COORDS: Record<string, [number, number]> = {
  Austria: [14.5, 47.6],
  Belgium: [4.5, 50.6],
  "Czech Republic": [15.3, 49.8],
  Denmark: [9.5, 56.0],
  France: [2.5, 47.0],
  Luxembourg: [6.1, 49.6],
  Netherlands: [5.5, 52.2],
  Poland: [19.0, 52.0],
  Switzerland: [8.2, 46.8],
  Norway: [8.0, 59.9],
  Sweden: [13.0, 55.5],
};

// short codes for compact cross-border electricity labels
export const EXCHANGE_COUNTRY_CODE: Record<string, string> = {
  Austria: "AT",
  Belgium: "BE",
  "Czech Republic": "CZ",
  Denmark: "DK",
  France: "FR",
  Luxembourg: "LU",
  Netherlands: "NL",
  Poland: "PL",
  Switzerland: "CH",
  Norway: "NO",
  Sweden: "SE",
};

// import (flow into DE) vs export — reuses the app's existing positive/warn tokens
// rather than inventing a new color pair
export const FLOW_COLOR: { import: RGB; export: RGB } = {
  import: [87, 179, 137],
  export: [210, 162, 74],
};
