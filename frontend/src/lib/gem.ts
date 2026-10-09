// Global Energy Monitor layers beyond power plants (files built by scripts/build_gem_layers.py):
// pipelines as routes, everything else as points. Values are GEM's; the drawing style says
// the status: solid = operating, dashed or ring = under construction, faint = planned, grey = idle.

import type { RGB } from "./theme";

/** [lon, lat, kind index, class index, size, year, name, status index, country] */
export type GemPoint = [number, number, number, number, number | null, number | null, string, number, string];
export interface GemPointsFile {
  source: string;
  fetched: string;
  classes: string[];
  kinds: string[];
  statuses: string[];
  unit: string;
  size_label: string;
  left_out: number;
  points: GemPoint[];
}
/** [class, status index, capacity, length km, start year, name, countries] */
export type GemPipeRow = [number, number, number | null, number | null, number | null, string, string];
export interface GemPipesFile {
  source: string;
  fetched: string;
  classes: string[];
  statuses: string[];
  capacity_unit: string;
  left_out: number;
  rows: GemPipeRow[];
  /** [row index, lon, lat, lon, lat, ...] */
  paths: number[][];
}

export const IDLE: RGB = [130, 134, 146];

export interface GemPointStyle {
  file: string;
  /** what one point is, for the hover card */
  noun: string;
  color: (kind: string) => RGB;
  /** pixels from the point's size (null when the tracker gives none) */
  radius: (size: number | null) => number;
  /** drawn with an additive glow */
  glow?: boolean;
}
const sqrt = (v: number | null) => Math.sqrt(Math.max(0, v ?? 0));
export const GEM_POINTS: Record<string, GemPointStyle> = {
  lngTerminals: {
    file: "gemLng",
    noun: "LNG terminal",
    color: (k) => (k === "export" ? [255, 150, 92] : [255, 215, 150]),
    radius: (s) => Math.min(14, 3 + sqrt(s) * 1.6),
  },
  coalTerminals: {
    file: "gemCoalTerminals",
    noun: "Coal terminal",
    color: () => [196, 182, 166],
    radius: (s) => Math.min(12, 2.5 + sqrt(s) * 0.9),
  },
  oilGasFields: {
    file: "gemFields",
    noun: "Oil and gas field",
    color: (k) => (/^oil$/i.test(k) ? [214, 96, 64] : /^gas$/i.test(k) ? [255, 150, 92] : [235, 120, 80]),
    radius: () => 2.2,
  },
  coalMines: {
    file: "gemCoalMines",
    noun: "Coal mine",
    color: () => [160, 146, 132],
    radius: (s) => Math.min(12, 2 + sqrt(s) * 1.1),
  },
  methane: {
    file: "gemMethane",
    noun: "Methane plume",
    color: () => [255, 90, 200],
    radius: (s) => Math.min(16, 2.5 + sqrt(s) / 12),
    glow: true,
  },
  steel: {
    file: "gemSteel",
    noun: "Steel plant",
    color: (k) => (/EAF|electric/i.test(k) ? [120, 200, 255] : [200, 205, 215]),
    radius: (s) => Math.min(12, 2.5 + sqrt(s) / 12),
  },
  cement: {
    file: "gemCement",
    noun: "Cement plant",
    color: () => [206, 192, 166],
    radius: (s) => Math.min(10, 2 + sqrt(s) * 1.5),
  },
  chemicals: {
    file: "gemChemicals",
    noun: "Chemical plant",
    color: () => [230, 160, 255],
    radius: () => 2.6,
  },
  ironOre: {
    file: "gemIronOre",
    noun: "Iron ore mine",
    color: () => [206, 112, 88],
    radius: (s) => Math.min(10, 2 + sqrt(s) / 20),
  },
};

export interface GemPipeStyle {
  file: string;
  noun: string;
  color: RGB;
  width: (capacity: number | null) => number;
}
export const GEM_PIPES: Record<string, GemPipeStyle> = {
  gasPipes: { file: "gemGas", noun: "Gas pipeline", color: [255, 196, 96], width: (c) => 0.7 + Math.min(2.3, sqrt(c) / 3) },
  oilPipes: { file: "gemOil", noun: "Oil pipeline", color: [222, 110, 82], width: (c) => 0.7 + Math.min(2.3, sqrt(c) / 600) },
};

export const CLASS_LABEL = ["operating", "under construction", "planned", "idle"];

const fmt = (v: number) => (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 10 ? v.toFixed(1) : v.toFixed(2));

/** "12.5 Mtpa capacity" etc., or "" when GEM gives no size. */
export function sizeText(f: GemPointsFile, size: number | null): string {
  return size == null || !f.unit ? "" : `${fmt(size)} ${f.unit} ${f.size_label}`;
}
export function capacityText(f: GemPipesFile, cap: number | null): string {
  if (cap == null) return "";
  return f.capacity_unit === "boe/d" ? `${Math.round(cap).toLocaleString("en-US")} barrels of oil equivalent a day` : `${fmt(cap)} ${f.capacity_unit}`;
}
