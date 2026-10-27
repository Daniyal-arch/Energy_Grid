// Room to connect in one schema (scripts/build_connect_harmonised.py, brief 23): every operator's
// published record as one row, the operator's own classes mapped one to one to four classes, MW as
// published. The Grid capacity layer, the two country colourings, the card and the key read it.

import type { ColorStops } from "../app/types";
import type { RGB } from "./theme";
import { NL_COLOR } from "./connect";

export type HClass = "available" | "limited" | "queue" | "none";

export interface HOperator {
  cc: string;
  operator: string;
  level: "transmission" | "distribution";
  source: string;
  url: string;
  licence: string;
  as_of: string | null;
  /** the operator's classes -> ours, as documented */
  mapping: string;
  note: string;
  /** false where the operator says its nodes share capacity (not summed) */
  summable?: boolean;
  rows: number;
  placed: number;
  matched: number;
}

/** [operator index, id, name, kind, lon, lat, kv, mw_gen, mw_load, mva_gen, mva_load, mw_queue, class, class_load, polygon] */
export type HRow = [
  number,
  string | null,
  string,
  "node" | "area",
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  HClass | null,
  HClass | null,
  number[][][] | null,
];

export interface HFile {
  fetched: string;
  fields: string[];
  classes: HClass[];
  note: string;
  operators: HOperator[];
  rows: HRow[];
}

export const H = { op: 0, id: 1, name: 2, kind: 3, lon: 4, lat: 5, kv: 6, mwGen: 7, mwLoad: 8, mvaGen: 9, mvaLoad: 10, mwQueue: 11, cls: 12, clsLoad: 13, polygon: 14 } as const;

export const H_CLASSES: HClass[] = ["available", "limited", "queue", "none"];
export const H_LABEL: Record<HClass, string> = {
  available: "capacity available",
  limited: "limited",
  queue: "under study or waiting list",
  none: "no capacity",
};
/** The same four colours everywhere (the Dutch capacity map's calm ramp). */
export const H_COLOR: Record<HClass, RGB> = { available: NL_COLOR[0], limited: NL_COLOR[1], queue: NL_COLOR[2], none: NL_COLOR[3] };
/** a record the operator publishes without a class (a value only) */
export const H_NO_CLASS: RGB = [128, 132, 144];

export type Side = "offtake" | "feedin";

/** The class and the published figure of a row for new generation (feed-in) or new demand (offtake). */
export function sideOf(r: HRow, side: Side): { cls: HClass | null; mw: number | null; mva: number | null } {
  return side === "feedin" ? { cls: r[H.cls], mw: r[H.mwGen], mva: r[H.mvaGen] } : { cls: r[H.clsLoad], mw: r[H.mwLoad], mva: r[H.mvaLoad] };
}

/** Dot radius in pixels: area follows the MW published (1 MW 2.5 px, 100 MW 7 px, 400 MW 12 px); a fixed small dot where no MW is published. */
export function hRadius(mw: number | null): number {
  if (mw == null) return 2;
  return Math.min(12, 2 + Math.sqrt(Math.max(0, mw)) * 0.5);
}

export interface CountryRoom {
  /** free MW for new generation / new demand: sums over the summable operators' rows (computed) */
  gen: number;
  load: number;
  genRows: number;
  loadRows: number;
  /** rows by class, generation side and demand side */
  byClass: Record<HClass, number>;
  byClassLoad: Record<HClass, number>;
  operators: HOperator[];
}

const emptyCount = (): Record<HClass, number> => ({ available: 0, limited: 0, queue: 0, none: 0 });

const ROOM_CACHE = new WeakMap<HFile, Record<string, CountryRoom>>();

/** Per country (ISO alpha-2; the US utilities under "US"): sums and counts, computed from the rows (once per file). */
export function countryRoom(f: HFile): Record<string, CountryRoom> {
  const hit = ROOM_CACHE.get(f);
  if (hit) return hit;
  const out: Record<string, CountryRoom> = {};
  ROOM_CACHE.set(f, out);
  const cc = (o: HOperator) => (o.cc.startsWith("US-") ? "US" : o.cc);
  for (const o of f.operators) {
    const c = (out[cc(o)] ??= { gen: 0, load: 0, genRows: 0, loadRows: 0, byClass: emptyCount(), byClassLoad: emptyCount(), operators: [] });
    c.operators.push(o);
  }
  for (const r of f.rows) {
    const o = f.operators[r[H.op]];
    const c = out[cc(o)];
    if (o.summable !== false) {
      if (r[H.mwGen] != null) {
        c.gen += r[H.mwGen]!;
        c.genRows++;
      }
      if (r[H.mwLoad] != null) {
        c.load += r[H.mwLoad]!;
        c.loadRows++;
      }
    }
    if (r[H.cls]) c.byClass[r[H.cls]!]++;
    if (r[H.clsLoad]) c.byClassLoad[r[H.clsLoad]!]++;
  }
  return out;
}

/** Country colouring: free MW published, summed per country, in GW. */
export const ROOM_STOPS: ColorStops = [
  [0, [44, 52, 62]],
  [2, [52, 96, 92]],
  [10, [52, 120, 108]],
  [40, [120, 178, 150]],
];
export const ROOM_TICKS = ["0", "2", "10", "≥ 40 GW free"];

/** Flat [x, y, x, y, ...] rings as [[x, y], ...] for deck.gl. */
export const pairsOf = (ring: number[]): [number, number][] => {
  const out: [number, number][] = [];
  for (let i = 0; i + 1 < ring.length; i += 2) out.push([ring[i], ring[i + 1]]);
  return out;
};

export const mwText = (mw: number | null | undefined) =>
  mw == null ? "–" : mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${mw.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW`;
