// The US grid pack (scripts/fetch_us_grid.py, scripts/fetch_us_lines.py): EIA-860M plants,
// LBNL's interconnection queue, USWTDB turbines, Census state outlines, OSM lines on R2.
// Values come from the build scripts; this file only types them and picks colours.

import { FUEL_COLOR, FUEL_LABEL } from "./energy";
import type { RGB } from "./theme";
import { VOLTAGE_BANDS } from "../app/colors";

export interface UsPlantsFile {
  source: string;
  release: string;
  fetched: string;
  measure: string;
  types: string[];
  statuses: string[];
  /** [lon, lat, type, status, MW (net summer), year, plant index, units] */
  points: [number, number, number, number, number, number | null, number, number][];
  /** [name, state, EIA plant id] */
  plants: [string, string, number][];
  units: Record<string, number>;
  /** status -> type -> MW, 50 states + DC */
  totals: Record<string, Record<string, number>>;
  /** status -> EIA status code -> type -> MW */
  status_detail: Record<string, Record<string, Record<string, number>>>;
  /** state -> status -> type -> MW */
  states: Record<string, Record<string, Record<string, number>>>;
  /** year -> construction|planned -> type -> MW */
  additions: Record<string, Record<string, Record<string, number>>>;
  /** year -> type -> MW (operating units with a planned retirement year) */
  retirements_planned: Record<string, Record<string, number>>;
  /** year -> type -> MW (Retired sheet, from 2010) */
  retired: Record<string, Record<string, number>>;
  left_out: Record<string, number>;
}

export interface UsQueueFile {
  source: string;
  release: string;
  edition: string;
  through: string;
  fetched: string;
  types: string[];
  storage_types: string[];
  phases: string[];
  total: {
    active_n: number;
    suspended_n: number;
    active: number[];
    suspended: number[];
    generation_mw: number;
    storage_mw: number;
    phase: number[];
  };
  states: Record<string, { active_n: number; suspended_n: number; active: number[]; suspended: number[]; phase: number[] }>;
  no_state: { active_n: number; active: number[] };
  /** proposed online year -> MW per type (active requests) */
  by_year: Record<string, number[]>;
}

export interface UsTurbinesFile {
  source: string;
  release: string;
  fetched: string;
  count: number;
  with_capacity: number;
  mw: number;
  offshore_n: number;
  lon: number[];
  lat: number[];
  kw: (number | null)[];
  hh: (number | null)[];
  rd: (number | null)[];
  project: number[];
  model: number[];
  offshore: number[];
  /** [name, state, year online, turbines in the project, project MW] */
  projects: [string, string, number | null, number | null, number | null][];
  models: string[];
  /** state -> [turbines, MW] */
  states: Record<string, [number, number]>;
}

export interface UsState {
  code: string;
  name: string;
  label: [number, number];
  bbox: [number, number, number, number];
  /** [outer ring, holes...], each ring flat [lon, lat, lon, lat, ...] */
  polygons: number[][][];
}
export interface UsStatesFile {
  source: string;
  states: UsState[];
}

/** The lower 48 faces the camera from here (the US panel follows it). */
export const US_CENTRE: [number, number] = [-98, 39];

// EIA-860M fuel groups: the app's fuel colours, geothermal as on GEM's layer
export const US_TYPE_COLOR: Record<string, RGB> = { ...FUEL_COLOR, geothermal: [255, 140, 110] };
export const US_TYPE_LABEL: Record<string, string> = { ...FUEL_LABEL, coal: "Coal", bio: "Bioenergy", geothermal: "Geothermal" };
/** The order of the panel's bars and keys: largest operating first. */
export const US_TYPE_ORDER = ["gas", "solar", "coal", "wind", "nuclear", "hydro", "storage", "oil", "bio", "geothermal", "other"];

// LBNL's resource types (passthrough) -> colour
export const QUEUE_COLOR: Record<string, RGB> = {
  Solar: FUEL_COLOR.solar,
  // batteries lead in several states: a clear violet, not the pale storage grey of the plant layers
  Battery: [164, 128, 255],
  "Other Storage": [124, 104, 196],
  Gas: FUEL_COLOR.gas,
  Wind: FUEL_COLOR.wind,
  "Offshore Wind": [64, 178, 214],
  Nuclear: FUEL_COLOR.nuclear,
  Coal: FUEL_COLOR.coal,
  Hydro: FUEL_COLOR.hydro,
  Geothermal: [255, 140, 110],
  Oil: FUEL_COLOR.oil,
  Diesel: FUEL_COLOR.oil,
  Hydrogen: [140, 210, 255],
  Other: FUEL_COLOR.other,
};
export const queueColor = (t: string): RGB => QUEUE_COLOR[t] ?? FUEL_COLOR.other;

/** Operating capacity of a state, all fuels (EIA-860M net summer MW). */
export const operatingMw = (p: UsPlantsFile | undefined, code: string) =>
  Object.values(p?.states[code]?.operating ?? {}).reduce((sum, v) => sum + v, 0);

/** The queue against what a state runs today: GW waiting ÷ GW operating (computed). */
export const QUEUE_RATIO_STOPS: Array<[number, RGB]> = [
  [0, [30, 36, 48]],
  [0.5, [44, 74, 96]],
  [1, [58, 118, 132]],
  [2, [196, 160, 86]],
  [4, [232, 104, 76]],
  [8, [214, 64, 150]],
];
export const QUEUE_RATIO_TICKS = ["0", "1×", "2×", "4×", "≥ 8×"];
export const queueRatioCss = `linear-gradient(90deg, ${QUEUE_RATIO_STOPS.map(([, c]) => `rgb(${c.join(",")})`).join(", ")})`;
export const ratioText = (r: number) => (r >= 10 ? `${Math.round(r)}×` : `${r.toFixed(1)}×`);

/** OpenStreetMap lines from 100 kV (scripts/fetch_us_lines.py), vector tiles on R2. */
export const US_LINES_TILES = "pmtiles://https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid/us-lines.pmtiles";
/** Europe's colour bands, by the same voltage steps, plus the 100–199 kV lines the US grid
 *  leans on (darker, from zoom 5). */
export const US_BANDS: Array<{ min: number; label: string; color: RGB; alpha: number }> = [
  ...VOLTAGE_BANDS.slice(0, 2).map((b) => ({ min: b.min, label: b.min === 380 ? "380–765 kV" : "275–379 kV", color: b.color, alpha: b.alpha })),
  { min: 200, label: "200–274 kV", color: VOLTAGE_BANDS[2].color, alpha: VOLTAGE_BANDS[2].alpha },
  { min: 100, label: "100–199 kV, from zoom 5", color: [118, 84, 66], alpha: 70 },
];

/** Inside a US state (Census outlines)? Point in polygon after a bounding-box test. */
export function usTester(file: UsStatesFile): (lon: number, lat: number) => boolean {
  const polys = file.states.flatMap((s) =>
    s.polygons.map((rings) => {
      const outer = rings[0];
      let [x0, y0, x1, y1] = [180, 90, -180, -90];
      for (let k = 0; k < outer.length; k += 2) {
        x0 = Math.min(x0, outer[k]);
        x1 = Math.max(x1, outer[k]);
        y0 = Math.min(y0, outer[k + 1]);
        y1 = Math.max(y1, outer[k + 1]);
      }
      return { rings, box: [x0, y0, x1, y1] };
    }),
  );
  const inRing = (r: number[], x: number, y: number) => {
    let inside = false;
    for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) {
      const [xi, yi, xj, yj] = [r[i], r[i + 1], r[j], r[j + 1]];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  };
  return (lon, lat) =>
    polys.some((p) => lon >= p.box[0] && lon <= p.box[2] && lat >= p.box[1] && lat <= p.box[3] && inRing(p.rings[0], lon, lat) && !p.rings.slice(1).some((h) => inRing(h, lon, lat)));
}

export const gwText = (mw: number) => (mw >= 10_000 ? `${Math.round(mw / 1000).toLocaleString("en-US")} GW` : mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`);

/** Day-ahead price at one trading hub per market (scripts/fetch_us_prices.py), $/MWh. */
export interface UsPricesFile {
  source: string;
  unit: string;
  fetched: string;
  step_s: number;
  hubs: Record<string, { market: string; name: string; region: string; clock: string }>;
  /** today and tomorrow in Eastern Time, once published */
  days: { date: string; start: string; slots: number; prices: Record<string, { country: string; market: string; name: string; values: (number | null)[] }> }[];
}

export interface HubPrice {
  hub: string;
  market: string;
  name: string;
  region: string;
  usd: number;
}

/** Each hub's price in one hour of a day's prices (hubs without a value left out). */
export function hubPrices(prices: Record<string, { country: string; market?: string; name?: string; values: (number | null)[] }>, k: number): HubPrice[] {
  return Object.entries(prices).flatMap(([hub, p]) => {
    const usd = p.values[k];
    return usd == null ? [] : [{ hub, market: p.market ?? hub, name: p.name ?? hub, region: p.country, usd }];
  });
}

/** The hour of now in us_prices.json: the day and the slot holding it. */
export function hubPricesNow(f: UsPricesFile, now: number = Date.now()): { rows: HubPrice[]; hour: string } | null {
  for (const d of f.days) {
    const k = Math.floor((now - Date.parse(d.start)) / (f.step_s * 1000));
    if (k >= 0 && k < d.slots) {
      const rows = hubPrices(d.prices, k);
      return rows.length ? { rows, hour: new Date(Date.parse(d.start) + k * f.step_s * 1000).toISOString() } : null;
    }
  }
  return null;
}

/** "$45.20" with the source's two decimals; a minus before the sign. */
export const usd = (v: number) => `${v < 0 ? "−" : ""}$${Math.abs(v).toFixed(2)}`;

/** The markets' own queues (scripts/fetch_us_queues.py): active requests per state and type, MW. */
export interface UsQueuesLiveFile {
  fetched: string;
  source: string;
  markets: Record<
    string,
    {
      requests?: number;
      active?: number;
      active_mw?: number;
      by_type?: Record<string, number>;
      by_state?: Record<string, Record<string, number>>;
      statuses?: Record<string, number>;
      error?: string;
      missing?: string;
    }
  >;
}

/** Real-time prices at the same hubs (scripts/fetch_us_rt.py): [UTC interval start, USD/MWh]. */
export interface UsRtFile {
  source: string;
  unit: string;
  fetched: string;
  markets: Record<string, { hub: string; step?: string; points?: [string, number][]; error?: string; missing?: string }>;
}

/** The day-ahead price of the hour holding `t` at `hub`, or null. */
export function dayAheadAt(f: UsPricesFile | undefined, hub: string, t: number): number | null {
  for (const d of f?.days ?? []) {
    const k = Math.floor((t - Date.parse(d.start)) / (f!.step_s * 1000));
    if (k >= 0 && k < d.slots) return d.prices[hub]?.values[k] ?? null;
  }
  return null;
}
