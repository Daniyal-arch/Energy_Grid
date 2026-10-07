// Prices tab: twelve months of day-ahead prices per bidding zone (prices.json and
// prices/<zone>.json, built by scripts/build_prices.py from ENTSO-E). Values are the
// build script's; this file picks colours and places zone labels.

import type { RGB } from "./theme";

export interface ZoneStats {
  country: string;
  mean: number;
  negative_hours: number;
  negative_by_month: number[];
  /** [EUR/MWh, interval start] */
  min: [number, string];
  max: [number, string];
  coverage: number;
  solar_capture: number | null;
  solar_capture_rate: number | null;
  solar_twh: number | null;
  wind_capture: number | null;
  wind_capture_rate: number | null;
  wind_twh: number | null;
  /** average price per local hour of the day, per month (rows follow PricesFile.months) */
  by_month_hour: (number | null)[][];
  /** the same per season */
  by_season_hour: Record<string, (number | null)[]>;
}
export interface PricesFile {
  fetched: string;
  /** the twelve full months the statistics cover */
  period: [string, string];
  months: string[];
  /** season -> the months it covers in the period */
  seasons: Record<string, string[]>;
  zones: Record<string, ZoneStats>;
}

export type PriceMetricId = "negative" | "mean" | "solar" | "wind";
export interface PriceMetric {
  id: PriceMetricId;
  label: string;
  note: string;
  value: (z: ZoneStats) => number | null;
  format: (v: number | null) => string;
  stops: Array<[number, RGB]>;
  ticks: string[];
}

const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v)} %`);
const CAPTURE_STOPS: Array<[number, RGB]> = [
  [40, [196, 70, 56]],
  [60, [206, 140, 76]],
  [80, [120, 132, 118]],
  [95, [56, 168, 158]],
  [110, [110, 228, 206]],
];

export const PRICE_METRICS: PriceMetric[] = [
  {
    id: "negative",
    label: "Negative-price hours",
    note: "hours with a day-ahead price below zero",
    value: (z) => z.negative_hours,
    format: (v) => (v == null ? "–" : `${Math.round(v)} h`),
    stops: [
      [0, [36, 42, 54]],
      [50, [34, 66, 92]],
      [200, [36, 120, 170]],
      [400, [70, 186, 232]],
      [700, [170, 238, 255]],
    ],
    ticks: ["0 h", "350 h", "≥ 700 h"],
  },
  {
    id: "mean",
    label: "Average price",
    note: "average day-ahead price, €/MWh",
    value: (z) => z.mean,
    format: (v) => (v == null ? "–" : `${Math.round(v)} €`),
    stops: [
      [30, [40, 132, 128]],
      [70, [56, 86, 96]],
      [100, [120, 96, 84]],
      [125, [184, 96, 62]],
      [150, [214, 64, 56]],
    ],
    ticks: ["≤ 30 €", "90 €", "≥ 150 €/MWh"],
  },
  {
    id: "solar",
    label: "Solar capture rate",
    note: "what solar earned per MWh, in % of the average price",
    value: (z) => z.solar_capture_rate,
    format: pct,
    stops: CAPTURE_STOPS,
    ticks: ["≤ 40 %", "75 %", "≥ 110 %"],
  },
  {
    id: "wind",
    label: "Wind capture rate",
    note: "what wind earned per MWh, in % of the average price",
    value: (z) => z.wind_capture_rate,
    format: pct,
    stops: CAPTURE_STOPS,
    ticks: ["≤ 40 %", "75 %", "≥ 110 %"],
  },
];
export const priceMetricById = (id: PriceMetricId) => PRICE_METRICS.find((m) => m.id === id) ?? PRICE_METRICS[0];

export function stopColor(stops: Array<[number, RGB]>, v: number | null | undefined): RGB | null {
  if (v == null) return null;
  if (v <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    const [v1, c1] = stops[i];
    const [v0, c0] = stops[i - 1];
    if (v <= v1) {
      const t = (v - v0) / (v1 - v0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * t)) as RGB;
    }
  }
  return stops[stops.length - 1][1];
}
export const stopGradient = (stops: Array<[number, RGB]>) => {
  const a = stops[0][0];
  const b = stops[stops.length - 1][0];
  return `linear-gradient(90deg, ${stops.map(([v, c]) => `rgb(${c.join(",")}) ${((v - a) / (b - a)) * 100}%`).join(", ")})`;
};

// hour-of-day grid: below zero in ice blue, cheap in deep teal, expensive in ember and red
const CARPET: Array<[number, RGB]> = [
  [0, [20, 48, 60]],
  [50, [30, 96, 100]],
  [100, [96, 104, 100]],
  [160, [204, 132, 64]],
  [260, [222, 60, 56]],
  [500, [255, 120, 210]],
];
export function hourColor(eur: number): RGB {
  if (eur < 0) {
    const t = Math.min(1, -eur / 100);
    return [Math.round(70 + 140 * t), Math.round(196 + 52 * t), 255];
  }
  return stopColor(CARPET, eur) as RGB;
}
export const HOUR_KEY: Array<[string, RGB]> = [
  ["< 0", [110, 210, 255]],
  ["0", CARPET[0][1]],
  ["50", CARPET[1][1]],
  ["100", CARPET[2][1]],
  ["160", CARPET[3][1]],
  ["260", CARPET[4][1]],
  ["≥ 500 €", CARPET[5][1]],
];

/** Where a bidding zone's marker sits in countries with several zones (map placement). */
export const ZONE_POINT: Record<string, { at: [number, number]; short: string }> = {
  DK1: { at: [9.0, 56.2], short: "DK1" },
  DK2: { at: [11.9, 55.45], short: "DK2" },
  NO1: { at: [10.8, 60.6], short: "NO1" },
  NO2: { at: [7.6, 58.9], short: "NO2" },
  NO3: { at: [10.4, 63.2], short: "NO3" },
  NO4: { at: [18.0, 68.2], short: "NO4" },
  NO5: { at: [6.4, 60.8], short: "NO5" },
  SE1: { at: [20.4, 66.8], short: "SE1" },
  SE2: { at: [16.2, 63.3], short: "SE2" },
  SE3: { at: [15.4, 59.4], short: "SE3" },
  SE4: { at: [14.0, 56.3], short: "SE4" },
  "IT-North": { at: [9.8, 45.4], short: "IT-N" },
  "IT-Centre-North": { at: [11.3, 43.5], short: "IT-CN" },
  "IT-Centre-South": { at: [13.1, 41.9], short: "IT-CS" },
  "IT-South": { at: [15.9, 41.0], short: "IT-S" },
  "IT-Calabria": { at: [16.35, 38.95], short: "IT-Cal" },
  "IT-Sicily": { at: [14.1, 37.5], short: "IT-Sic" },
  "IT-Sardinia": { at: [9.0, 40.1], short: "IT-Sar" },
};

export const SEASON_COLOR: Record<string, RGB> = {
  winter: [120, 170, 255],
  spring: [124, 222, 150],
  summer: [255, 206, 84],
  autumn: [236, 128, 84],
};

export const monthLabel = (ym: string) =>
  new Date(`${ym}-15T12:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
