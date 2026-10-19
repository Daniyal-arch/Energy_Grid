// ENTSO-E TYNDP 2024 projects (scripts/build_tyndp.py): one feature per investment of a
// transmission project, and per storage project, as the project map publishes them.

import type { RGB } from "./theme";

export interface TyndpFeature {
  project: string | null;
  investment?: string | null;
  type: string | null;
  id: number | null;
  /** index into TyndpFile.statuses */
  status: number | null;
  /** as published: "MM-YYYY" or "YYYY" */
  year: string | null;
  promoter?: string | null;
  country?: string | null;
  offshore?: string | null;
  kind: "line" | "area" | "point";
  /** line: [part][flat lon/lat]; area: [polygon][ring][flat]; point: [lon, lat] */
  geometry: number[][] | number[][][] | number[];
  capacity_mw?: number;
  voltage_kv?: number;
  element?: string;
  technology?: string;
  length_km?: number;
  generating_mw?: number;
  storage_mw?: number;
}

export interface TyndpFile {
  fetched: string;
  source: string;
  statuses: string[];
  features: TyndpFeature[];
}

/** Calm: building solid, permitting clear, earlier stages faint. */
export const TYNDP_STYLE: Record<string, [RGB, number]> = {
  "Under Construction": [[72, 222, 184], 230],
  "In Permitting": [[255, 196, 96], 210],
  "Planned But Not Yet Permitting": [[196, 170, 255], 170],
  "Under Consideration": [[150, 160, 180], 120],
  Commissioned: [[235, 240, 248], 220],
  Completed: [[235, 240, 248], 220],
};
export const TYNDP_GREY: [RGB, number] = [[120, 128, 140], 100];
export const tyndpStyle = (f: TyndpFile, x: TyndpFeature) => (x.status != null ? TYNDP_STYLE[f.statuses[x.status]] : undefined) ?? TYNDP_GREY;
