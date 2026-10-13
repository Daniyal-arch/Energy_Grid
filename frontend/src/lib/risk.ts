// Risk layers: US power outages per county (EAGLE-I, scripts/build_us_outages.py) and water
// risk per river basin (WRI Aqueduct 4.0, scripts/build_aqueduct.py).

import type { ColorStops } from "../app/types";
import type { RGB } from "./theme";

export interface UsOutagesFile {
  fetched: string;
  source: string;
  years: number[];
  partial: Record<string, string>;
  step_min: number;
  event_rule: { min_customers: number; gap_min: number };
  /** ORNL's modelled customers per county (MCC.csv) */
  customers: Record<string, number>;
  /** customer-hours without power per year (index of `years`) */
  counties: Record<string, (number | null)[]>;
  names: Record<string, string>;
  national: number[];
  /** [date, national peak, at, state with most out then, its peak] */
  top_days: [string, number, string, string, number][];
  /** [state, start, end, peak customers out, peak at] */
  events: [string, string, string, number, string][];
  month: { month: string; start: string; step_min: number; values: number[] } | null;
}

export interface UsCountiesFile {
  source: string;
  counties: { code: string; name: string; state: string; label: [number, number]; polygons: number[][][] }[];
}

export interface WaterFile {
  fetched: string;
  source: string;
  version: string;
  indicators: Record<string, { name: string; labels: Record<string, string> }>;
  order: string[];
  /** basins whose units carry different categories (the map shows the highest) */
  mixed: Record<string, number>;
  tolerance: number;
  basins: { id: number; c: (number | null)[]; polygons: number[][][] }[];
}

export type WaterIndicator = "bws" | "rfr" | "cfr" | "drr";
export const WATER_INDICATORS: { id: WaterIndicator; short: string }[] = [
  { id: "bws", short: "water stress" },
  { id: "rfr", short: "river flood" },
  { id: "cfr", short: "coastal flood" },
  { id: "drr", short: "drought" },
];

/** WRI's own scale, low (0) to extremely high (4); -1 = arid and low water use. */
export const WATER_COLOR: Record<string, RGB> = {
  "-1": [128, 128, 128],
  "0": [255, 255, 153],
  "1": [255, 230, 0],
  "2": [255, 153, 0],
  "3": [255, 25, 0],
  "4": [153, 0, 19],
};

/** Customer-hours without power in a year, log scale (computed from EAGLE-I). */
export const OUTAGE_STOPS: ColorStops = [
  [3, [36, 44, 60]],
  [4, [72, 70, 110]],
  [5, [150, 80, 120]],
  [6, [230, 120, 80]],
  [7, [255, 214, 120]],
];
export const OUTAGE_TICKS = ["≤ 1,000", "100,000", "≥ 10 M customer-hours"];

export const hoursText = (v: number) =>
  v >= 1e6 ? `${(v / 1e6).toFixed(1)} M` : v >= 1e4 ? `${Math.round(v / 1e3).toLocaleString("en-US")} k` : Math.round(v).toLocaleString("en-US");

/** The newest year in the file and its index. */
export function newestYear(f: UsOutagesFile): { year: number; k: number } {
  const k = f.years.length - 1;
  return { year: f.years[k], k };
}
