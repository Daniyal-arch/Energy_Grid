// Shapes of the static files in public/data/eu/ (built by scripts/; see docs/DATA_SOURCES.md).

import type { OutageTotals, OutageUnit } from "../components/CountryCards";
import type { RGB } from "../lib/theme";

export type Series = (number | null)[];

export interface GridFile {
  lines: [number, number[]][];
  links: [number, number[]][];
  /** [kV, lon, lat, ISO] */
  substations: Substation[];
}
export type Substation = [number, number, number, string];
/** [name, ISO, lon, lat, start year, capacity or null when the dataset only estimates it] */
export type GasSite = [string, string, number, number, number | null, number | null];
/** focused-country unit: [group index, MW, lon, lat, name, year in operation] */
export type Unit = [number, number, number, number, string, number | null];
export interface GasFile {
  pipes: [number, number[]][];
  lng: GasSite[];
  storages: GasSite[];
}
export interface ReferenceFile {
  fetched: string;
  capacity: Record<string, { year: string; gw: Record<string, number> }>;
  reservoirs: Record<string, { week: string; twh: number; year_ago_week: string | null; year_ago_twh: number | null }>;
}
export interface PriceRow {
  country: string;
  ts: string;
  eur_mwh: number;
}
/** [group index, MW, lon, lat, ISO, name, year in operation] */
export type Plant = [number, number, number, number, string, string, number | null];
export interface PlantsFile {
  groups: string[];
  plants: Plant[];
  /** per country and group: [units, MW] of the plants drawn (>= 20 MW, operating) */
  by_country: Record<string, Record<string, [number, number]>>;
}
export interface Country {
  iso: string;
  name: string;
  label: [number, number];
  polygons: number[][][];
}
export interface CountriesFile {
  countries: Country[];
  borders: number[][];
  coast: number[][];
}
export interface FlowRow {
  a: string;
  b: string;
  mw: number;
  ts: string;
  series?: Series;
}
export interface FlowsFile {
  fetched: string;
  series_start?: string;
  series_step_s?: number;
  borders: FlowRow[];
}
export interface Power {
  ts: string;
  load_mw: number;
  renewable_share_of_generation: number | null;
  generation_mw: Record<string, number>;
  /** EU totals: the member states summed */
  sum_of?: string[];
}
export interface StatsFile {
  fetched: string;
  eu: Power | null;
  countries: Record<string, Power>;
  day_ahead_prices?: Record<string, PriceRow>;
}
export interface Arc {
  from: string;
  to: string;
  mw: number;
  ts: string;
  path: [number, number][];
  timestamps: number[];
}
export interface Shape {
  iso: string;
  name: string;
  polygon: [number, number][][];
}
export interface WorldFile {
  features: { properties: { name: string; iso3: string }; geometry: { coordinates: number[][][][] } }[];
}
export interface DaySeries {
  load: Series;
  renewable_share: Series;
  generation: Record<string, Series>;
  /** EU only: resolution (archives before October 2026 are hourly) and members summed */
  step_s?: number;
  sum_of?: string[];
}
export interface Highlight {
  slot: number;
  kind: string;
  gw?: number;
  pct?: number;
  eur?: number;
  zone?: string;
  country?: string;
  from?: string;
  to?: string;
}
export interface DayFile {
  date: string;
  start: string;
  step_s: number;
  slots: number;
  prices: Record<string, { country: string; values: Series }>;
  countries: Record<string, DaySeries>;
  eu: DaySeries | null;
  borders: { a: string; b: string; values: Series }[];
  highlights?: Highlight[];
}
/** undersea power cable: [class, kV | null, name | null, flat lon/lat] */
export type Cable = [string, number | null, string | null, number[]];
export interface TowerPiece {
  iso: string;
  name: string;
  group: string;
  /** stacked height of the pieces below, MW as drawn */
  base: number;
  /** real value of this source in the slot on the clock */
  mw: number;
  /** value as drawn this frame (glides to the next slot) */
  drawn: number;
  /** real total of the country in the slot on the clock */
  total: number;
}
export interface Hex {
  position: [number, number];
  mw: number;
  units: number;
  /** MW per fuel group index */
  mix: Map<number, number>;
  dominant: number;
}
export type ColorStops = Array<[number, RGB]>;
export interface OutagesFile {
  fetched: string;
  at: string;
  total: OutageTotals;
  countries: Record<string, OutageTotals>;
  units: OutageUnit[];
}
