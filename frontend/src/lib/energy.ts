// Shared energy vocabulary: source groups, their colours and labels, and formatting.

import type { RGB } from "./theme";

export const FUEL_ORDER = ["solar", "wind", "nuclear", "gas", "coal", "hydro", "bio", "oil", "other"];
/** stacking order for charts and towers: steady sources at the bottom, weather on top */
export const STACK_ORDER = ["nuclear", "coal", "gas", "oil", "hydro", "bio", "other", "wind", "solar"];

export const FUEL_COLOR: Record<string, RGB> = {
  nuclear: [255, 96, 150],
  coal: [160, 146, 132],
  gas: [255, 128, 72],
  oil: [214, 96, 64],
  hydro: [84, 156, 255],
  wind: [72, 222, 184],
  solar: [255, 214, 72],
  bio: [150, 196, 92],
  storage: [196, 196, 214],
  other: [168, 146, 210],
};

export const FUEL_LABEL: Record<string, string> = {
  nuclear: "Nuclear",
  coal: "Coal & lignite",
  gas: "Gas",
  oil: "Oil",
  hydro: "Hydro",
  wind: "Wind",
  solar: "Solar",
  bio: "Bioenergy & waste",
  storage: "Storage",
  other: "Other",
};

/** Ember's own source names (yearly data) and the colour of the closest group */
export const EMBER_COLOR: Record<string, RGB> = {
  Nuclear: FUEL_COLOR.nuclear,
  Coal: FUEL_COLOR.coal,
  Gas: FUEL_COLOR.gas,
  "Other fossil": FUEL_COLOR.oil,
  Hydro: FUEL_COLOR.hydro,
  Bioenergy: FUEL_COLOR.bio,
  "Other renewables": FUEL_COLOR.other,
  Wind: FUEL_COLOR.wind,
  Solar: FUEL_COLOR.solar,
};
export const EMBER_ORDER = ["Nuclear", "Coal", "Gas", "Other fossil", "Hydro", "Bioenergy", "Other renewables", "Wind", "Solar"];

export const gw = (mw: number) => `${(Math.abs(mw) / 1000).toFixed(1)} GW`;
export const power = (mw: number) => (Math.abs(mw) >= 1000 ? gw(mw) : `${Math.round(Math.abs(mw))} MW`);
