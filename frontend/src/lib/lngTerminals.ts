// LNG send-out per terminal (scripts/fetch_alsi.py, GIE ALSI), the last 30 gas days.

import type { RGB } from "./theme";

/** [gas day, send-out GWh/d, in tanks GWh, declared send-out GWh/d, GIE status C|E|N] */
export type LngDay = [string, number | null, number | null, number | null, string | null];

export interface LngTerminal {
  eic: string;
  name: string;
  type: string | null;
  country: string;
  operator: string;
  lon: number;
  lat: number;
  series: LngDay[];
}

export interface LngTerminalsFile {
  fetched: string;
  source: string;
  /** newest gas day with data */
  date: string;
  terminals: LngTerminal[];
}

export const LNG_SEND: RGB = [120, 180, 255];

/** A terminal's row for a gas day (the file's newest when absent). */
export const lngDay = (t: LngTerminal, date: string): LngDay | undefined => t.series.find((s) => s[0] === date);

export const STATUS_TEXT: Record<string, string> = { C: "confirmed", E: "estimated", N: "no data" };

/** Pixel radius for GWh/d (area follows the flow). */
export const lngRadius = (gwhd: number) => 2 + Math.sqrt(Math.max(0, gwhd)) * 0.75;

export const gwhdText = (v: number | null | undefined) => (v == null ? "–" : `${v.toLocaleString("en-US", { maximumFractionDigits: 1 })} GWh/d`);
