// World tab: electricity access (World Bank), mapped data centres (OpenStreetMap) and
// Australia's live market (AEMO). Values come from the build scripts; this file picks
// colours and places markers.

import type { RGB } from "./theme";

export interface WorldStatsFile {
  fetched: string;
  years: string[];
  /** ISO alpha-3 (and WLD for the world): % of population per year, null where missing */
  access: Record<string, (number | null)[]>;
}
export interface DataCentresFile {
  fetched: string;
  count: number;
  by_country: Record<string, number>;
  /** [lon, lat, name, operator] */
  points: [number, number, string | null, string | null][];
}
export interface AemoFile {
  fetched: string;
  /** market time, UTC+10 */
  settlement: string;
  regions: Record<
    string,
    { price: number | null; demand: number | null; net_interchange: number | null; scheduled: number | null; semi_scheduled: number | null }
  >;
  interconnectors: { id: string; from: string; to: string; mw: number | null; export_limit: number | null; import_limit: number | null }[];
}

// access to electricity: full access stays calm, gaps glow warm
export const ACCESS_STOPS: Array<[number, RGB]> = [
  [0, [204, 70, 56]],
  [40, [222, 134, 66]],
  [70, [176, 156, 96]],
  [90, [86, 124, 114]],
  [100, [44, 66, 78]],
];
export const ACCESS_TICKS = ["0 %", "50 %", "100 % of people"];

/** Newest value of a yearly series and its year. */
export function latest(series: (number | null)[] | undefined, years: string[]): { value: number; year: string } | null {
  if (!series) return null;
  for (let i = series.length - 1; i >= 0; i--) if (series[i] != null) return { value: series[i] as number, year: years[i] };
  return null;
}

/** Where each NEM region's marker sits (map placement, not an official centre). */
export const NEM_POINT: Record<string, [number, number]> = {
  QLD1: [146.5, -22.0],
  NSW1: [147.6, -32.2],
  VIC1: [144.2, -36.9],
  SA1: [136.2, -30.6],
  TAS1: [146.6, -42.1],
};
export const NEM_NAME: Record<string, string> = {
  QLD1: "Queensland",
  NSW1: "New South Wales",
  VIC1: "Victoria",
  SA1: "South Australia",
  TAS1: "Tasmania",
};
export const DC_COLOR: RGB = [196, 150, 255];

export interface UsRegion {
  name: string;
  /** [hour (UTC), MW] */
  demand: [string, number] | null;
  generation: [string, number] | null;
  /** positive = net export */
  interchange: [string, number] | null;
  mix: { hour: string; mw: Record<string, number> } | null;
}
export interface UsFile {
  fetched: string;
  regions: Record<string, UsRegion>;
  us48_demand: [string, number][];
  flows: { hour: string | null; pairs: { a: string; b: string; mw: number }[] };
}

/** Where each EIA region's marker sits (map placement, not an official centre). */
export const US_POINT: Record<string, [number, number]> = {
  CAL: [-119.6, 37.2],
  NW: [-116.5, 45.6],
  SW: [-111.2, 34.0],
  CENT: [-98.6, 39.2],
  TEX: [-98.8, 31.2],
  MIDW: [-89.6, 42.6],
  TEN: [-86.4, 35.9],
  SE: [-86.2, 32.4],
  FLA: [-81.6, 28.2],
  CAR: [-79.4, 35.4],
  MIDA: [-77.4, 39.9],
  NY: [-75.4, 42.9],
  NE: [-71.6, 44.2],
  CAN: [-96.0, 51.5],
  MEX: [-108.0, 28.5],
};
export const US_COLOR: [number, number, number] = [255, 196, 120];
