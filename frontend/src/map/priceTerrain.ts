// The Prices layer: each European country rises as a low slab, its height its day-ahead price
// and its colour the price along the day's range (cheapest to dearest of the replayed day). In 24 h the generation towers stand on top of the blocks and the flows
// arc from block to block (map/build.ts), so price and generation read together.
// Prices: ENTSO-E day-ahead auction per bidding zone; a country with several zones stands
// at their median (computed). Between two 15-min values the height glides (drawing only, as
// the towers do); labels and cards show the slot's own value.

import type { Layer } from "@deck.gl/core";
import { PathLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { dim } from "../app/colors";
import type { DayFile, Shape, StatsFile } from "../app/types";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";

/** 100 €/MWh stands 50 km tall: low slabs, so the generation towers on them stay the tallest thing. */
export const TERRAIN_M_PER_EUR = 500;
/** Every priced country stands at least this high (metres), so a cheap one still reads as a slab. */
const FLOOR_M = 3000;
const NONE: RGB = [96, 118, 150];
/** Cheapest to dearest of the day (or of the snapshot); below zero is ice-cyan. */
export const PRICE_RAMP: RGB[] = [
  [36, 150, 170],
  [120, 200, 120],
  [240, 214, 92],
  [244, 140, 62],
  [214, 56, 98],
];
export const BELOW_ZERO: RGB = [90, 235, 255];
export const rampCss = `linear-gradient(90deg, ${PRICE_RAMP.map((c) => `rgb(${c.join(",")})`).join(", ")})`;

/** The lowest (from 0) and highest zone price of the replayed day, or of the snapshot. */
export function priceRange(day: DayFile | null | undefined, stats: StatsFile | undefined): [number, number] | null {
  let lo = Infinity;
  let hi = -Infinity;
  if (day)
    for (const z of Object.values(day.prices))
      for (const v of z.values)
        if (v != null) {
          lo = Math.min(lo, v);
          hi = Math.max(hi, v);
        }
  if (!day) for (const z of Object.values(stats?.day_ahead_prices ?? {})) [lo, hi] = [Math.min(lo, z.eur_mwh), Math.max(hi, z.eur_mwh)];
  if (!Number.isFinite(lo)) return null;
  lo = Math.max(0, lo);
  return [lo, Math.max(hi, lo + 1)];
}

/** A price's colour along the ramp between the range's ends. */
export function rampColour(range: [number, number] | null, p: number | null): RGB {
  if (p == null || !range) return NONE;
  if (p < 0) return BELOW_ZERO;
  const t = Math.max(0, Math.min(1, (p - range[0]) / (range[1] - range[0]))) * (PRICE_RAMP.length - 1);
  const i = Math.min(PRICE_RAMP.length - 2, Math.floor(t));
  const f = t - i;
  return PRICE_RAMP[i].map((v, n) => Math.round(v + (PRICE_RAMP[i + 1][n] - v) * f)) as RGB;
}
const ADD = {
  depthCompare: "always",
  depthWriteEnabled: false,
  blend: true,
  blendColorSrcFactor: "src-alpha",
  blendColorDstFactor: "one",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;

interface Zones {
  /** zones of each country (Luxembourg trades in DE-LU) */
  of: Record<string, string[]>;
}

function zonesOf(fr: Frame): Zones {
  const src: Record<string, { country: string }> = fr.day?.prices ?? (fr.files.stats as StatsFile | undefined)?.day_ahead_prices ?? {};
  return memo("pt-zones", [src], () => {
    const of: Record<string, string[]> = {};
    for (const [z, v] of Object.entries(src)) (of[v.country] ??= []).push(z);
    if (src["DE-LU"]) of.LU = ["DE-LU"];
    return { of };
  });
}

/** Each zone's price in the slot (24 h) or the newest snapshot (live). */
function pricesAt(fr: Frame, k: number): Record<string, number> {
  return memo("pt-prices", [fr.day, k, fr.files.stats], () => {
    const out: Record<string, number> = {};
    if (fr.day) {
      for (const [z, v] of Object.entries(fr.day.prices)) if (v.values[k] != null) out[z] = v.values[k] as number;
    } else for (const [z, v] of Object.entries((fr.files.stats as StatsFile | undefined)?.day_ahead_prices ?? {})) out[z] = v.eur_mwh;
    return out;
  });
}

const median = (v: number[]) => {
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

function countryValue(z: Zones, iso: string, at: (zone: string) => number | null): number | null {
  const v = (z.of[iso] ?? []).flatMap((zone) => {
    const p = at(zone);
    return p == null ? [] : [p];
  });
  return v.length ? median(v) : null;
}

/** The last drawn prices, for the hover cards (map/tooltip.ts). */
export const priceState = { prices: {} as Record<string, number>, zones: { of: {} } as Zones };

export interface Terrain {
  layers: Layer[];
  /** a country's block height now (metres; 0 without a price) */
  height: (iso: string) => number;
  /** a country's price in the slot (€/MWh), for labels */
  price: (iso: string) => number | null;
  /** countries with a price */
  priced: Shape[];
}

export function priceTerrain(fr: Frame, k: number, shapes: Shape[]): Terrain {
  const z = zonesOf(fr);
  const P = pricesAt(fr, k);
  const stats = fr.files.stats as StatsFile | undefined;
  const range = memo("pt-range", [fr.day, stats], () => priceRange(fr.day, stats));
  const colour = (p: number | null) => rampColour(range, p);
  Object.assign(priceState, { prices: P, zones: z });
  // heights glide towards the next slot (drawing only)
  const frac = fr.day ? Math.max(0, Math.min(1, fr.daySlot - k)) : 0;
  const glide = (zone: string): number | null => {
    const v = fr.day?.prices[zone]?.values;
    if (!v) return P[zone] ?? null;
    const a = v[k];
    if (a == null) return null;
    const b = v[Math.min(v.length - 1, k + 1)] ?? a;
    return a + (b - a) * frac;
  };
  const drawn = new Map<string, number | null>();
  const value = (iso: string) => {
    if (!drawn.has(iso)) drawn.set(iso, countryValue(z, iso, glide));
    return drawn.get(iso) ?? null;
  };
  const height = (iso: string) => {
    const p = value(iso);
    return p == null ? 0 : p < 0 ? FLOOR_M / 2 : FLOOR_M + p * TERRAIN_M_PER_EUR;
  };
  const price = (iso: string) => countryValue(z, iso, (zone) => P[zone] ?? null);
  const priced = memo("pt-shapes", [shapes, z], () => shapes.filter((s) => z.of[s.iso]?.length));
  const rings = memo("pt-rings", [priced], () => priced.flatMap((s) => s.polygon.slice(0, 1).map((ring) => ({ iso: s.iso, ring }))));
  const below = memo("pt-below", [rings, P], () => rings.filter((r) => (price(r.iso) ?? 0) < 0));
  const key = [fr.day ? fr.daySlot : 0, P];
  type Ring = (typeof rings)[number];
  return {
    height,
    price,
    priced,
    layers: [
      new SolidPolygonLayer<Shape>({
        id: "price-terrain",
        data: priced,
        getPolygon: (d) => d.polygon,
        extruded: true,
        getElevation: (d) => height(d.iso),
        getFillColor: (d) => [...colour(value(d.iso)), 255],
        updateTriggers: { getElevation: key, getFillColor: key },
        material: { ambient: 0.7, diffuse: 0.45, shininess: 12, specularColor: [30, 30, 30] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
      }),
      // a thin darker edge on each slab's top, so neighbours of one colour stay apart
      new PathLayer<Ring>({
        id: "price-terrain-tops",
        data: rings,
        getPath: (r) => {
          const h = height(r.iso) + 200;
          return r.ring.map((p) => [p[0], p[1], h]) as unknown as [number, number][];
        },
        getColor: (r) => [...dim(colour(value(r.iso)), 0.55), 200],
        getWidth: 0.8,
        widthUnits: "pixels",
        updateTriggers: { getPath: key, getColor: key },
      }),
      // below zero: the country lies flat and glows ice-cyan
      new PathLayer<Ring>({
        id: "price-terrain-below",
        data: below,
        getPath: (r) => r.ring,
        getColor: [...BELOW_ZERO, 120],
        getWidth: 9,
        widthUnits: "pixels",
        jointRounded: true,
        parameters: ADD,
      }),
    ],
  };
}
