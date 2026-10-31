// Wave 9 colourings (scripts/wave9.py, w9c/<id>.json): one published series per country or US
// county, coloured along quantile stops of its own values (so each series spreads over the
// ramp); the key shows the values at the stops and the source, period and series named.

import type { ColorStops } from "../app/types";
import type { RGB } from "./theme";

export interface W9cFile {
  source: string;
  fetched?: string;
  label: string;
  unit: string;
  period: string | null;
  scope: "country" | "us_county";
  filter: Record<string, string>;
  values: Record<string, number>;
}

const RAMP: RGB[] = [
  [36, 52, 78],
  [44, 104, 120],
  [78, 160, 132],
  [190, 196, 104],
  [250, 214, 120],
];

/** Stops at the 0, 25, 50, 75 and 100 % quantiles of the file's values (computed for the key). */
export function w9cStops(f: W9cFile): ColorStops {
  const v = Object.values(f.values).filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return [[0, RAMP[0]], [1, RAMP[4]]];
  const q = (p: number) => v[Math.min(v.length - 1, Math.round(p * (v.length - 1)))];
  const stops: ColorStops = [];
  [0, 0.25, 0.5, 0.75, 1].forEach((p, i) => {
    const x = q(p);
    if (!stops.length || x > stops[stops.length - 1][0]) stops.push([x, RAMP[i]]);
  });
  return stops.length > 1 ? stops : [[stops[0][0], RAMP[0]], [stops[0][0] + 1, RAMP[4]]];
}

export const w9cNumber = (x: number) =>
  Math.abs(x) >= 1000 ? Math.round(x).toLocaleString("en-US") : Math.abs(x) >= 10 ? x.toFixed(1) : x.toPrecision(3);
