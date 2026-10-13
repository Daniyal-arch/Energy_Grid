// Emissions per facility worldwide (scripts/fetch_climate_trace.py): Climate TRACE's modelled
// CO2e per asset and year, assets of 0.1 Mt and more.

import type { RGB } from "./theme";

/** [lon, lat, ISO3, name, subsector, t CO2e year, t CO2e year before | null, owner | null] */
export type CtRow = [number, number, string, string, number, number, number | null, string | null];

export interface CtraceFile {
  fetched: string;
  source: string;
  year: number;
  threshold_t: number;
  subsectors: string[];
  groups: string[];
  /** group index per subsector */
  group_of: number[];
  /** largest first */
  rows: CtRow[];
}

export const CT_COLOR: RGB[] = [
  [236, 128, 92], // power and heat
  [120, 170, 232], // steel and metals
  [214, 198, 166], // cement and lime
  [214, 104, 160], // chemicals and refining
  [255, 196, 96], // oil and gas production
  [168, 150, 132], // coal and mining
  [160, 164, 176], // other industry
];

export const subsectorLabel = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/-/g, " ");

/** Oil and gas production is modelled per basin, not per site. */
export const isBasin = (f: CtraceFile, r: CtRow) => f.subsectors[r[4]] === "oil-and-gas-production";

/** Dot radius in pixels (area follows tonnes), capped so basins do not cover regions. */
export function ctRadius(t: number, zoom: number): number {
  const base = 0.9 + Math.sqrt(t / 1e6) * 1.6;
  return Math.min(14, base * (zoom >= 5 ? 1.5 : zoom >= 4 ? 1.2 : 1));
}
