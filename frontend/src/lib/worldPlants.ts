// World tab: GEM's power plants (world_plants.json, scripts/build_world_plants.py) and the
// colours of the world grid layer. Values come from the build scripts.

import { FUEL_COLOR } from "./energy";
import type { RGB } from "./theme";

export interface WorldPlantsFile {
  fetched: string;
  types: string[];
  statuses: string[];
  /** [lon, lat, type index, status index, MW, year (start, or retired for retired)] */
  points: [number, number, number, number, number, number | null][];
  countries: Record<string, Record<string, Record<string, number>>>;
  world: Record<string, Record<string, number>>;
}

export const PLANT_TYPE_COLOR: Record<string, RGB> = {
  solar: FUEL_COLOR.solar,
  wind: FUEL_COLOR.wind,
  gas: FUEL_COLOR.gas,
  coal: FUEL_COLOR.coal,
  hydro: FUEL_COLOR.hydro,
  bio: FUEL_COLOR.bio,
  nuclear: FUEL_COLOR.nuclear,
  geothermal: [255, 140, 110],
};
export const PLANT_TYPE_LABEL: Record<string, string> = {
  solar: "Solar",
  wind: "Wind",
  gas: "Oil & gas",
  coal: "Coal",
  hydro: "Hydro",
  bio: "Bioenergy",
  nuclear: "Nuclear",
  geothermal: "Geothermal",
};
export const STATUS_LABEL: Record<string, string> = {
  operating: "Operating",
  construction: "Under construction",
  planned: "Planned",
  retired: "Retired",
};

// world high-voltage lines (OpenStreetMap), by voltage: the backbone brightest
export const HV_STEPS: Array<[number, string]> = [
  [0, "rgba(96,140,200,0.55)"],
  [300, "rgba(120,180,240,0.75)"],
  [380, "rgba(160,210,255,0.9)"],
  [500, "rgba(214,240,255,1)"],
];
export const HV_TILES = "pmtiles://https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid/world-hv.pmtiles";
export const PREDICTED_TILES = "pmtiles://https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid/world-grid.pmtiles";

/** Unit vector of a lon/lat point, to test which side of the globe faces the camera. */
export function unitVector(lon: number, lat: number): [number, number, number] {
  const r = Math.PI / 180;
  const c = Math.cos(lat * r);
  return [c * Math.cos(lon * r), c * Math.sin(lon * r), Math.sin(lat * r)];
}
