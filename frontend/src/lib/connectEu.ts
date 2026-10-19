// Room to connect in ten more countries (scripts/build_connect_eu.py): one file format for all,
// the operators' own figures as published. Each row carries a class for the map colour, from the
// operator's own category or from the feed-in MW in the four classes of the Grid capacity layer.

import { NL_COLOR } from "./connect";
import type { RGB } from "./theme";

/** A country, or a country and its distribution grid (ES-DSO, GB-DSO): connect/<id>.json */
export const CONNECT_EU = ["AT", "BG", "CZ", "DE", "DK", "EE", "LT", "LU", "MT", "SE", "ES-DSO", "GB-DSO"] as const;
export const connectEuKey = (id: string) => `connect7${id.replace("-", "")}`;
export const connectEuCountry = (id: string) => id.slice(0, 2);

type Values = (number | string | boolean | null)[];
/** [name, lon, lat, kV, values per column, class] */
export type EuPoint = [string, number, number, number | string | null, Values, number];
/** [name, [polygon][ring] flat lon/lat, values, class] */
export type EuArea = [string, number[][][], Values, number];
/** [name, region, values, class]: operators that publish no positions */
export type EuRow = [string, string | null, Values, number];

export interface ConnectEuFile {
  fetched: string;
  cc: string;
  source: string;
  url: string;
  licence: string;
  updated: string | null;
  note: string;
  /** [key, label, unit] */
  columns: [string, string, string][];
  classes: string[];
  class_of: string;
  points: EuPoint[];
  areas: EuArea[];
  table: EuRow[];
}

/** The class colours: the Grid capacity layer's four (most room first); two or three operator
 *  categories take the ends and the middle of the same scale. */
export function classColor(f: ConnectEuFile, k: number): RGB {
  if (k < 0) return [120, 120, 120];
  const n = f.classes.length;
  const idx = n === 4 ? k : n === 2 ? (k === 0 ? 0 : 3) : n === 3 ? [0, 1, 3][k] : Math.min(3, k);
  return NL_COLOR[idx];
}

export function valueText(v: number | string | boolean | null, unit: string): string {
  if (v == null || v === "") return "–";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return `${v.toLocaleString("en-US", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
  return v;
}
