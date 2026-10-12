// EU ETS verified emissions per installation (scripts/fetch_eu_ets.py): Union Registry
// figures, placed where the EEA's industrial register gives the installation's ETS id.

import type { RGB } from "./theme";

/** [ISO, registry id, name, group, t CO2 per year (null: none verified), lon | null, lat | null] */
export type EtsRow = [string, string, string, number, (number | null)[], number | null, number | null];

export interface EtsFile {
  fetched: string;
  source: string;
  /** the Union Registry extract's date */
  snapshot: string;
  years: number[];
  newest: number;
  groups: string[];
  countries: Record<string, { n: number; placed: number; t: number[]; t_placed: number }>;
  /** largest newest-year emitter first */
  rows: EtsRow[];
}

/** One colour per activity group, in the file's order. */
export const ETS_COLOR: RGB[] = [
  [236, 128, 92], // combustion (power, heat, industry)
  [214, 104, 160], // refineries
  [120, 170, 232], // iron and steel
  [150, 214, 222], // aluminium and other metals
  [214, 198, 166], // cement and lime
  [186, 160, 226], // glass, ceramics, minerals
  [140, 200, 124], // pulp and paper
  [255, 206, 96], // chemicals
  [160, 164, 176], // other
];

/** The Union Registry's registry codes that are not a map country of their own. */
export const ETS_REGISTRY_NAME: Record<string, string> = { XI: "Northern Ireland" };

/** Registries shown under a country: Great Britain's card includes Northern Ireland (XI). */
export const etsIn = (iso2: string, registry: string) => registry === iso2 || (iso2 === "GB" && registry === "XI");

export const newestT = (r: EtsRow) => r[4][r[4].length - 1];

export function mt(t: number): string {
  if (t >= 1e6) return `${(t / 1e6).toFixed(t >= 1e7 ? 1 : 2)} Mt`;
  if (t >= 1e3) return `${Math.round(t / 1e3).toLocaleString("en-US")} kt`;
  return `${Math.round(t).toLocaleString("en-US")} t`;
}

/** Dot radius in pixels for a newest-year figure (area follows tonnes). */
export function etsRadius(t: number, zoom: number): number {
  const base = 1.3 + Math.sqrt(t / 1e6) * 3.2;
  return Math.min(22, base * (zoom >= 6 ? 1.5 : zoom >= 5 ? 1.2 : 1));
}
