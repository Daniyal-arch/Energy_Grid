// Every generating unit in Germany: the Marktstammdatenregister (scripts/build_mastr.py).

import type { ColorStops } from "../app/types";
import type { RGB } from "./theme";

export interface MastrUnitsFile {
  fetched: string;
  snapshot: string;
  source: string;
  techs: string[];
  /** [lon, lat, tech index, MW (gross), "YYYY-MM" commissioned] */
  units: [number, number, number, number, string | null][];
}

export interface Gemeinde {
  ags: string;
  name: string | null;
  label: [number, number] | null;
  polygons: number[][][];
  /** operating MW per technology (index of `techs`) */
  mw: number[];
  n: number[];
}

export interface MastrMuniFile {
  fetched: string;
  snapshot: string;
  source: string;
  techs: string[];
  /** [units, MW] operating */
  national: Record<string, [number, number]>;
  no_ags: Record<string, [number, number]>;
  offshore: Record<string, [number, number]>;
  months: string[];
  /** [units, MW] commissioned per month */
  additions: Record<string, [number, number][]>;
  gemeinden: Gemeinde[];
}

export type MastrTech = "solar" | "wind" | "storage";
export const MASTR_TECHS: MastrTech[] = ["solar", "wind", "storage"];

export const MASTR_COLOR: Record<string, RGB> = {
  solar: [255, 214, 72],
  wind: [72, 222, 184],
  storage: [178, 146, 255],
  biomass: [140, 200, 90],
  hydro: [84, 156, 255],
  combustion: [230, 120, 80],
  nuclear: [255, 120, 200],
  other: [160, 160, 170],
};
export const MASTR_LABEL: Record<string, string> = {
  solar: "Solar",
  wind: "Wind",
  storage: "Storage",
  biomass: "Biomass",
  hydro: "Hydro",
  combustion: "Combustion",
  nuclear: "Nuclear",
  other: "Geothermal, mine gas, other",
};

/** MW per municipality, log10 scale. */
export const MASTR_STOPS: ColorStops = [
  [-1, [30, 34, 44]],
  [0, [52, 58, 80]],
  [1, [96, 92, 120]],
  [2, [170, 120, 110]],
  [2.7, [255, 200, 120]],
];
export const MASTR_TICKS = ["≤ 0.1", "10", "≥ 500 MW"];

/** Large units appear from this zoom. */
export const MASTR_UNIT_ZOOM = 6;

export const mwText = (mw: number) => (mw >= 1000 ? `${(mw / 1000).toFixed(2)} GW` : mw >= 10 ? `${Math.round(mw).toLocaleString("en-US")} MW` : `${mw.toFixed(1)} MW`);
