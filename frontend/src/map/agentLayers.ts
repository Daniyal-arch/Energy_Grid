// The agent's maps (app/agent.ts): every MapSpec style drawn from the rows of a saved map, with
// the app's palettes, calm by construction (bounded sizes, two overlays at most per map). Twelve
// flat styles (dots, bubbles, choropleth, hexbin, grid, heatmap, contour, lines, flows, labels,
// bivariate, pies) and ten in 3D (columns, beams, spikes, lollipops, hex_columns, grid_columns,
// prisms, arcs_3d, terrain, point_cloud). Colours and sizes run from the smallest to the largest
// value in the data; bins sum (or, for terrain, average) the rows' values: the key says which.
// Each overlay's key figures are published in useAgentKeys for the Ask tab and the Maps view.

import type { Layer } from "@deck.gl/core";
import { ContourLayer, HeatmapLayer } from "@deck.gl/aggregation-layers";
import { ArcLayer, ColumnLayer, LineLayer, PathLayer, PointCloudLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";
import { create } from "zustand";

import { ensure } from "../app/data";
import type { CountriesFile, WorldFile } from "../app/types";
import { FUEL_COLOR } from "../lib/energy";
import type { Overlay, ValueEncoding } from "../lib/mapspec";
import type { Pt } from "../lib/measures";
import type { RGB } from "../lib/theme";
import { ISO3 } from "../lib/transition";
import type { UsStatesFile } from "../lib/us";
import { PLANT_TYPE_COLOR } from "../lib/worldPlants";
import type { Frame } from "./build";
import { BIVARIATE, binPoints, hexKm, type Hex } from "./hexLayers";
import { memo } from "./memo";

export type Row = Record<string, unknown>;
/** One overlay of an agent map with its rows (app/agent.ts prepares them). */
export interface AgentDraw {
  mapId: string;
  overlay: Overlay;
  rows: Row[];
}

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

// ---------------------------------------------------------------- palettes (the app's own)

const RAMPS: Record<string, RGB[]> = {
  neutral: [[60, 72, 90], [96, 128, 160], [150, 186, 214], [214, 230, 244]],
  share: [[40, 56, 48], [52, 120, 96], [96, 186, 132], [196, 238, 170]],
  price: [[48, 94, 170], [120, 130, 150], [222, 132, 72], [250, 214, 120]],
  price_glow: [[40, 70, 160], [150, 120, 200], [255, 120, 90], [255, 230, 150]],
  offline: [[74, 52, 56], [146, 64, 54], [214, 92, 60], [246, 150, 80]],
  solar: [[90, 64, 30], [190, 130, 50], [246, 196, 90], [255, 240, 170]],
  wind: [[30, 60, 70], [44, 120, 130], [96, 190, 190], [190, 240, 230]],
  heat: [[70, 30, 40], [170, 60, 50], [240, 130, 60], [255, 220, 130]],
  cool: [[30, 40, 90], [50, 90, 170], [90, 160, 230], [190, 230, 255]],
  green: [[30, 60, 40], [50, 120, 70], [110, 190, 110], [210, 245, 180]],
  purple: [[50, 36, 80], [100, 70, 160], [160, 120, 220], [230, 200, 255]],
  emissions: [[60, 50, 50], [150, 90, 70], [230, 140, 90], [255, 210, 160]],
  room: [[150, 70, 60], [214, 150, 80], [200, 190, 110], [96, 190, 150]],
  voltage: [[160, 100, 70], [206, 132, 84], [236, 178, 120], [255, 220, 170]],
};
const CATEGORICAL: RGB[] = [
  [96, 170, 255],
  [255, 150, 92],
  [120, 210, 150],
  [230, 120, 180],
  [250, 210, 110],
  [170, 140, 255],
  [110, 210, 220],
  [210, 170, 130],
];

const lerp = (a: RGB, b: RGB, t: number): RGB => [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * t)) as RGB;
export function rampAt(name: string | undefined, t: number): RGB {
  const r = RAMPS[name ?? "neutral"] ?? RAMPS.neutral;
  const x = Math.max(0, Math.min(1, t)) * (r.length - 1);
  const i = Math.min(r.length - 2, Math.floor(x));
  return lerp(r[i], r[i + 1], x - i);
}
export const rampCss = (name: string | undefined) => `linear-gradient(90deg, ${(RAMPS[name ?? "neutral"] ?? RAMPS.neutral).map((c) => `rgb(${c.join(",")})`).join(", ")})`;

/** A category's colour: the app's fuel or plant-type colours where the names match. */
function categoryColour(palette: string | undefined, name: string, order: string[]): RGB {
  const k = name.toLowerCase().replace(/[^a-z]/g, "");
  const keys: Record<string, string> = { hardcoal: "coal", lignite: "lignite", naturalgas: "gas", hydro: "hydro", solarpv: "solar", onshorewind: "wind", offshorewind: "wind" };
  const key = keys[k] ?? k;
  if (palette !== "plant_type" && FUEL_COLOR[key]) return FUEL_COLOR[key];
  if (PLANT_TYPE_COLOR[key]) return PLANT_TYPE_COLOR[key];
  if (FUEL_COLOR[key]) return FUEL_COLOR[key];
  return CATEGORICAL[Math.max(0, order.indexOf(name)) % CATEGORICAL.length];
}

// ---------------------------------------------------------------- the key's figures

export interface AgentKey {
  min: number;
  max: number;
  unit: string;
  palette?: string;
  scale?: string;
  categories: [string, RGB][];
  /** what a bin or a colour means for this style */
  note: string;
  missing: number;
}
export const useAgentKeys = create<Record<string, AgentKey>>(() => ({}));
const publish = (key: string, k: AgentKey) => {
  const was = useAgentKeys.getState()[key];
  if (was && was.min === k.min && was.max === k.max && was.note === k.note && was.missing === k.missing && was.categories.length === k.categories.length) return;
  useAgentKeys.setState({ [key]: k });
};

// ---------------------------------------------------------------- reading rows

const num = (v: unknown): number | null => {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
  return null;
};

interface Places {
  at: (r: Row) => [number, number] | null;
  shape: (r: Row) => [number, number][][][] | null;
}

const pairs = (flat: number[]): [number, number][] => {
  const out: [number, number][] = [];
  for (let i = 0; i + 1 < flat.length; i += 2) out.push([flat[i], flat[i + 1]]);
  return out;
};

/** Where a row goes: its lon/lat, else the label point and outline of its shape key. */
function placesOf(o: Overlay, files: Record<string, unknown>): Places {
  const d = o.data;
  const countries = files.countries as CountriesFile | undefined;
  const world = files.world as WorldFile | undefined;
  const states = files.usStates as UsStatesFile | undefined;
  if (d.key && d.shapes === "us_states") ensure("usStates");
  if (d.key && d.shapes && d.shapes !== "us_states") ensure("world");
  const shapes = memo(`agentShapes:${d.shapes}`, [countries, world, states, d.shapes], () => {
    const m = new Map<string, { at: [number, number]; polys: [number, number][][][] }>();
    if (d.shapes === "us_states") {
      for (const s of states?.states ?? []) m.set(s.code.toUpperCase(), { at: s.label, polys: (s.polygons as unknown as number[][][]).map((rings) => (Array.isArray(rings[0]) ? (rings as unknown as number[][]).map(pairs) : [pairs(rings as unknown as number[])])) });
      return m;
    }
    for (const f of world?.features ?? []) {
      const c = f.properties.iso3;
      const polys = (f.geometry.coordinates as number[][][][]).map((p) => p.map((ring) => ring.map((q) => [q[0], q[1]] as [number, number])));
      const xs = polys.flatMap((p) => p[0].map((q) => q[0]));
      const ys = polys.flatMap((p) => p[0].map((q) => q[1]));
      m.set(c, { at: [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2], polys });
    }
    for (const c of countries?.countries ?? []) {
      const entry = { at: c.label, polys: c.polygons.map((rings) => rings.map(pairs)) };
      m.set(c.iso, entry);
      if (ISO3[c.iso]) m.set(ISO3[c.iso], entry);
    }
    return m;
  });
  const lookup = (r: Row) => {
    const k = String(r[d.key ?? ""] ?? "").toUpperCase();
    return shapes.get(k) ?? (k.length === 2 && ISO3[k] ? shapes.get(ISO3[k]) : undefined) ?? null;
  };
  return {
    at: (r) => {
      if (d.lon && d.lat) {
        const x = num(r[d.lon]);
        const y = num(r[d.lat]);
        return x == null || y == null ? null : [x, y];
      }
      return d.key ? (lookup(r)?.at ?? null) : null;
    },
    shape: (r) => (d.key ? (lookup(r)?.polys ?? null) : null),
  };
}

/** Metres per screen pixel at the centre of the view. */
const metresPerPixel = (fr: Frame) => (40_075_016.686 * Math.cos((fr.centre[1] * Math.PI) / 180)) / (512 * 2 ** fr.zoom);

function domain(vs: number[], scale?: string): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of vs) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!Number.isFinite(lo)) return [0, 1];
  if (scale === "diverging") {
    const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
    return [-m, m];
  }
  return lo === hi ? [Math.min(0, lo), hi || 1] : [lo, hi];
}

// ---------------------------------------------------------------- bins

function squareBins(pts: Pt[], km: number, lat0: number): { centre: [number, number]; polygon: [number, number][]; v: number; n: number; cell: number }[] {
  const dLat = km / 110.57;
  const dLon = km / (111.32 * Math.max(0.2, Math.cos((lat0 * Math.PI) / 180)));
  const bins = new Map<string, { i: number; j: number; v: number; n: number }>();
  for (const [lon, lat, v] of pts) {
    const i = Math.floor(lon / dLon);
    const j = Math.floor(lat / dLat);
    const k = `${i},${j}`;
    const b = bins.get(k) ?? { i, j, v: 0, n: 0 };
    b.v += v;
    b.n += 1;
    bins.set(k, b);
  }
  return [...bins.values()].map((b) => {
    const x0 = b.i * dLon;
    const y0 = b.j * dLat;
    const g = 0.06;
    return {
      centre: [x0 + dLon / 2, y0 + dLat / 2] as [number, number],
      polygon: [
        [x0 + dLon * g, y0 + dLat * g],
        [x0 + dLon * (1 - g), y0 + dLat * g],
        [x0 + dLon * (1 - g), y0 + dLat * (1 - g)],
        [x0 + dLon * g, y0 + dLat * (1 - g)],
      ] as [number, number][],
      v: b.v,
      n: b.n,
      cell: km,
    };
  });
}

const terciles = (v: number[]): [number, number] => {
  const s = v.filter((x) => x > 0).sort((a, b) => a - b);
  return s.length ? [s[Math.floor(s.length / 3)], s[Math.floor((2 * s.length) / 3)]] : [Infinity, Infinity];
};
const cls = (v: number, b: [number, number]) => (v <= 0 || v < b[0] ? 0 : v < b[1] ? 1 : 2);

// ---------------------------------------------------------------- one overlay

/** The registry the hover card reads: layer id -> overlay. */
const TIPS = new Map<string, Overlay>();

function overlayLayers(fr: Frame, draw: AgentDraw): Layer[] {
  const o = draw.overlay;
  const id = `agent:${draw.mapId}:${o.id}`;
  TIPS.set(id, o);
  const P = placesOf(o, fr.files);
  const enc: ValueEncoding | undefined = o.value ?? undefined;
  const valueCol = enc?.column ?? o.size?.column;
  const unit = enc?.unit ?? o.size?.unit ?? "";
  const valOf = (r: Row) => (valueCol ? num(r[valueCol]) : 1) ?? 0;
  const rows = draw.rows;
  const placed = memo(`agentPlaced:${id}`, [rows, fr.files.countries, fr.files.world, fr.files.usStates], () => rows.filter((r) => P.at(r) != null || P.shape(r) != null));
  const vals = memo(`agentVals:${id}`, [placed], () => placed.map(valOf));
  const [lo, hi] = domain(vals, enc?.scale);
  const t = (v: number) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
  const share = (v: number) => Math.sqrt(Math.max(0, v) / Math.max(1e-12, hi > 0 ? hi : 1));
  const cats = memo(`agentCats:${id}`, [placed], () => (o.category ? [...new Set(placed.map((r) => String(r[o.category!] ?? "")))].filter(Boolean).slice(0, 12) : []));
  const colour = (r: Row): RGB => (o.category ? categoryColour(enc?.palette, String(r[o.category] ?? ""), cats) : rampAt(enc?.palette, t(valOf(r))));
  const mpp = metresPerPixel(fr);
  const tall = 110 * mpp;
  const rKm = o.radius_km ?? hexKm(fr.zoom);
  const lat0 = Math.round(fr.centre[1] / 5) * 5;
  const key = (note: string, k?: Partial<AgentKey>) =>
    publish(`${draw.mapId}:${o.id}`, {
      min: lo,
      max: hi,
      unit,
      palette: enc?.palette,
      scale: enc?.scale,
      categories: cats.map((c) => [c, categoryColour(enc?.palette, c, cats)] as [string, RGB]),
      note,
      missing: rows.length - placed.length,
      ...k,
    });
  const pts = (): Pt[] => placed.flatMap((r) => {
    const a = P.at(r);
    return a ? [[a[0], a[1], valOf(r), o.category ? String(r[o.category] ?? "") : ""] as Pt] : [];
  });
  const common = { pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 70] as [number, number, number, number] };
  const pos = (r: Row) => P.at(r) ?? [0, 0];

  switch (o.kind) {
    case "dots":
    case "points": {
      key(o.category ? "one dot per record, coloured by its type" : "one dot per record, colour by value");
      return [new ScatterplotLayer<Row>({ id, data: placed, getPosition: pos, getRadius: 3, radiusUnits: "pixels", getFillColor: (r) => [...colour(r), 220], stroked: true, getLineColor: [8, 10, 14, 200], lineWidthUnits: "pixels", getLineWidth: 0.5, ...common, parameters: ON_TOP })];
    }
    case "bubbles": {
      const maxPx = o.size?.max_px ?? 18;
      const sizeOf = (r: Row) => (o.size ? (num(r[o.size.column]) ?? 0) : valOf(r));
      const smax = Math.max(1e-12, ...placed.map(sizeOf).slice(0, 50_000));
      key("circle area by value (square root of its share of the largest)");
      const sorted = memo(`agentSorted:${id}`, [placed], () => [...placed].sort((a, b) => sizeOf(b) - sizeOf(a)));
      return [new ScatterplotLayer<Row>({ id, data: sorted, getPosition: pos, getRadius: (r) => 2 + maxPx * Math.sqrt(Math.max(0, sizeOf(r)) / smax), radiusUnits: "pixels", getFillColor: (r) => [...colour(r), 175], stroked: true, getLineColor: [8, 10, 14, 220], lineWidthUnits: "pixels", getLineWidth: 0.7, updateTriggers: { getRadius: [smax] }, ...common, parameters: ON_TOP })];
    }
    case "labels": {
      key("the value written at each place");
      const fmt = (r: Row) => (o.label ? String(r[o.label] ?? "") : `${valOf(r).toLocaleString("en-US", { maximumFractionDigits: 1 })}${unit ? ` ${unit}` : ""}`);
      return [new TextLayer<Row>({ id, data: placed, getPosition: pos, getText: fmt, getSize: 11, getColor: [240, 243, 248, 240], fontFamily: "ui-sans-serif, system-ui, sans-serif", background: true, getBackgroundColor: [8, 10, 14, 200], backgroundPadding: [3, 1], ...common, parameters: ON_TOP })];
    }
    case "choropleth":
    case "prisms": {
      const polys = memo(`agentPolys:${id}`, [placed], () => placed.flatMap((r) => (P.shape(r) ?? []).map((polygon) => ({ r, polygon }))));
      const extruded = o.kind === "prisms";
      key(extruded ? "height and colour by value" : "colour by value");
      return [
        new SolidPolygonLayer<{ r: Row; polygon: [number, number][][] }>({
          id,
          data: polys,
          getPolygon: (d) => d.polygon,
          getFillColor: (d) => [...colour(d.r), extruded ? 235 : 200],
          extruded,
          getElevation: (d) => (0.03 + t(valOf(d.r))) * tall * 2.2,
          updateTriggers: { getElevation: [lo, hi, tall] },
          material: { ambient: 0.65, diffuse: 0.5, shininess: 12, specularColor: [40, 40, 40] },
          ...common,
          ...(extruded ? {} : { parameters: ON_TOP }),
        }),
      ];
    }
    case "hexbin":
    case "hex_columns":
    case "terrain":
    case "bivariate": {
      if (o.kind === "bivariate" && o.value2) {
        const v2 = (r: Row) => num(r[o.value2!.column]) ?? 0;
        if (o.data.key && o.data.shapes) {
          const bx = terciles(placed.map(valOf));
          const by = terciles(placed.map(v2));
          const polys = memo(`agentBiv:${id}`, [placed], () => placed.flatMap((r) => (P.shape(r) ?? []).map((polygon) => ({ r, polygon }))));
          key("thirds of each variable (computed): light = high on both", { categories: [] });
          return [new SolidPolygonLayer<{ r: Row; polygon: [number, number][][] }>({ id, data: polys, getPolygon: (d) => d.polygon, getFillColor: (d) => [...BIVARIATE[cls(v2(d.r), by)][cls(valOf(d.r), bx)], 220], ...common, parameters: ON_TOP })];
        }
        const a = binPoints(pts(), rKm, lat0, null);
        const b = binPoints(placed.flatMap((r) => { const p = P.at(r); return p ? [[p[0], p[1], v2(r), ""] as Pt] : []; }), rKm, lat0, null);
        for (const [k, h] of b) {
          const x = a.get(k);
          if (x) x.v2 = h.v;
          else a.set(k, { ...h, v: 0, v2: h.v, top: "", types: [] });
        }
        const all = [...a.values()];
        const bx = terciles(all.map((h) => h.v));
        const by = terciles(all.map((h) => h.v2));
        key(`hexagons of about ${Math.round(rKm * 2)} km; thirds of each variable (computed)`);
        return [new SolidPolygonLayer<Hex>({ id, data: all, getPolygon: (h) => h.polygon, getFillColor: (h) => [...BIVARIATE[cls(h.v2, by)][cls(h.v, bx)], 225], ...common, parameters: ON_TOP })];
      }
      const mean = o.kind === "terrain";
      const hexes = memo(`agentHex:${id}`, [placed, rKm, lat0, mean], () => {
        const sum = binPoints(pts(), rKm, lat0, null);
        if (!mean) return [...sum.values()];
        const ones = binPoints(pts().map((p) => [p[0], p[1], 1, ""] as Pt), rKm, lat0, null);
        return [...ones].map(([k, h]) => ({ ...h, v: (sum.get(k)?.v ?? 0) / h.v }));
      });
      const [hlo, hhi] = domain(hexes.map((h) => h.v));
      const ht = (v: number) => (hhi > hlo ? (v - (mean ? hlo : 0)) / (hhi - (mean ? hlo : 0)) : 0.5);
      key(mean ? `mean per hexagon of about ${Math.round(rKm * 2)} km (computed)` : `sum per hexagon of about ${Math.round(rKm * 2)} km (computed)`, { min: mean ? hlo : 0, max: hhi });
      if (o.kind === "hexbin")
        return [new SolidPolygonLayer<Hex>({ id, data: hexes, getPolygon: (h) => h.polygon, getFillColor: (h) => [...rampAt(enc?.palette, ht(h.v)), 225], updateTriggers: { getFillColor: [hlo, hhi] }, ...common, parameters: ON_TOP })];
      return [
        new ColumnLayer<Hex>({
          id,
          data: hexes,
          getPosition: (h) => h.centre,
          diskResolution: 6,
          radius: rKm * 1000 * (mean ? 0.98 : 0.86),
          extruded: true,
          getElevation: (h) => (mean ? 0.04 + ht(h.v) : Math.sqrt(Math.max(0, ht(h.v)))) * tall * (mean ? 0.8 : 1.4),
          getFillColor: (h) => [...rampAt(enc?.palette, ht(h.v)), 240],
          updateTriggers: { getElevation: [hlo, hhi, tall], getFillColor: [hlo, hhi] },
          material: { ambient: 0.7, diffuse: 0.45, shininess: 8, specularColor: [30, 30, 30] },
          ...common,
        }),
      ];
    }
    case "grid":
    case "grid_columns": {
      const km = o.radius_km ?? hexKm(fr.zoom) * 1.6;
      const cells = memo(`agentGrid:${id}`, [placed, km, lat0], () => squareBins(pts(), km, lat0));
      const [glo, ghi] = domain(cells.map((c) => c.v));
      const gt = (v: number) => (ghi > 0 ? v / ghi : 0);
      key(`sum per square of ${Math.round(km)} km (computed)`, { min: 0, max: ghi });
      void glo;
      if (o.kind === "grid")
        return [new SolidPolygonLayer<(typeof cells)[number]>({ id, data: cells, getPolygon: (c) => c.polygon, getFillColor: (c) => [...rampAt(enc?.palette, Math.sqrt(gt(c.v))), 220], ...common, parameters: ON_TOP })];
      return [
        new ColumnLayer<(typeof cells)[number]>({
          id,
          data: cells,
          getPosition: (c) => c.centre,
          diskResolution: 4,
          angle: 45,
          radius: (km * 1000 * 0.62),
          extruded: true,
          getElevation: (c) => Math.sqrt(gt(c.v)) * tall * 1.4,
          getFillColor: (c) => [...rampAt(enc?.palette, Math.sqrt(gt(c.v))), 240],
          updateTriggers: { getElevation: [ghi, tall] },
          material: { ambient: 0.7, diffuse: 0.45, shininess: 8, specularColor: [30, 30, 30] },
          ...common,
        }),
      ];
    }
    case "heatmap": {
      key("density weighted by value (relative, no unit per pixel)");
      const range = (RAMPS[enc?.palette ?? "heat"] ?? RAMPS.heat).map((c) => [...c, 255] as [number, number, number, number]);
      return [new HeatmapLayer<Row>({ id, data: placed, getPosition: pos, getWeight: (r) => Math.max(0, valOf(r)), radiusPixels: 36, intensity: 1, threshold: 0.04, colorRange: range, parameters: ON_TOP })];
    }
    case "contour": {
      const km = o.radius_km ?? hexKm(fr.zoom) * 1.6;
      const cells = memo(`agentContourCells:${id}`, [placed, km, lat0], () => squareBins(pts(), km, lat0).map((c) => c.v).sort((a, b) => a - b));
      const q = (p: number) => cells[Math.min(cells.length - 1, Math.floor(p * cells.length))] ?? 0;
      const levels = [0.3, 0.55, 0.75, 0.9].map(q).filter((v, i, a) => v > 0 && a.indexOf(v) === i);
      key(`isolines of the sum per ${Math.round(km)} km cell at its 30, 55, 75 and 90 % quantiles (computed)`, { min: levels[0] ?? 0, max: levels[levels.length - 1] ?? 0 });
      return [
        new ContourLayer<Row>({
          id,
          data: placed,
          getPosition: pos,
          getWeight: (r) => Math.max(0, valOf(r)),
          cellSize: km * 1000,
          contours: levels.map((threshold, i) => ({ threshold, color: [...rampAt(enc?.palette, (i + 1) / levels.length), 230] as [number, number, number, number], strokeWidth: 1.6 })),
          pickable: false,
          parameters: ON_TOP,
        }),
      ];
    }
    case "lines":
    case "flows":
    case "arcs_3d":
    case "arcs": {
      const d = o.data;
      const from = (r: Row): [number, number] => [num(r[d.from_lon!]) ?? 0, num(r[d.from_lat!]) ?? 0];
      const to = (r: Row): [number, number] => [num(r[d.to_lon!]) ?? 0, num(r[d.to_lat!]) ?? 0];
      const fv = rows.map(valOf);
      const fmax = Math.max(1e-12, ...fv.slice(0, 50_000));
      const width = (r: Row) => 1 + 6 * Math.sqrt(Math.max(0, valOf(r)) / fmax);
      key("width by value");
      if (o.kind === "lines")
        return [new LineLayer<Row>({ id, data: rows, getSourcePosition: from, getTargetPosition: to, getColor: (r) => [...colour(r), 210], getWidth: width, widthUnits: "pixels", ...common, parameters: ON_TOP })];
      if (o.kind === "flows") {
        // a flat curve bending to the right of the direction of flow
        const curve = (r: Row): [number, number][] => {
          const a = from(r);
          const b = to(r);
          const mx = (a[0] + b[0]) / 2 + (b[1] - a[1]) * 0.18;
          const my = (a[1] + b[1]) / 2 - (b[0] - a[0]) * 0.18;
          return Array.from({ length: 17 }, (_, k) => {
            const s = k / 16;
            return [(1 - s) ** 2 * a[0] + 2 * (1 - s) * s * mx + s * s * b[0], (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * my + s * s * b[1]] as [number, number];
          });
        };
        return [new PathLayer<Row>({ id, data: rows, getPath: curve, getColor: (r) => [...colour(r), 220], getWidth: width, widthUnits: "pixels", capRounded: true, jointRounded: true, ...common, parameters: ON_TOP })];
      }
      return [new ArcLayer<Row>({ id, data: rows, getSourcePosition: from, getTargetPosition: to, getSourceColor: (r) => [...colour(r), 220], getTargetColor: (r) => [...colour(r), 120], getWidth: width, widthUnits: "pixels", getHeight: 0.6, ...common })];
    }
    case "pies": {
      // one donut per place: its ring split by category in proportion to the values
      const groups = memo(`agentPies:${id}`, [placed], () => {
        const g = new Map<string, { at: [number, number]; parts: Map<string, number>; total: number }>();
        for (const r of placed) {
          const a = P.at(r);
          if (!a) continue;
          const k = o.data.key ? String(r[o.data.key]) : `${a[0].toFixed(3)},${a[1].toFixed(3)}`;
          const e = g.get(k) ?? { at: a, parts: new Map(), total: 0 };
          const v = Math.max(0, valOf(r));
          e.parts.set(String(r[o.category!] ?? ""), (e.parts.get(String(r[o.category!] ?? "")) ?? 0) + v);
          e.total += v;
          g.set(k, e);
        }
        return [...g.values()];
      });
      const gmax = Math.max(1e-12, ...groups.map((g) => g.total));
      const zk = Math.round(fr.zoom * 4) / 4;
      const arcs = memo(`agentPieArcs:${id}`, [groups, zk], () =>
        groups.flatMap((g) => {
          const rPx = 7 + 16 * Math.sqrt(g.total / gmax);
          const rLat = (rPx * mpp) / 111_320;
          const rLon = rLat / Math.max(0.2, Math.cos((g.at[1] * Math.PI) / 180));
          let a0 = 0;
          return [...g.parts.entries()]
            .sort((a, b) => b[1] - a[1])
            .map(([cat, v]) => {
              const a1 = a0 + (2 * Math.PI * v) / Math.max(1e-12, g.total);
              const steps = Math.max(2, Math.ceil(((a1 - a0) / (2 * Math.PI)) * 48));
              const path = Array.from({ length: steps + 1 }, (_, k) => {
                const a = a0 + 0.04 + ((a1 - a0 - 0.08) * k) / steps;
                return [g.at[0] + rLon * Math.sin(a), g.at[1] + rLat * Math.cos(a)] as [number, number];
              });
              a0 = a1;
              return { cat, v, total: g.total, path };
            });
        }),
      );
      key("each ring is one place: its size by the total, its parts by category");
      return [new PathLayer<(typeof arcs)[number]>({ id, data: arcs, getPath: (x) => x.path, getColor: (x) => [...categoryColour(enc?.palette, x.cat, cats), 235], getWidth: 5, widthUnits: "pixels", ...common, parameters: ON_TOP })];
    }
    case "columns":
    case "spikes": {
      const spike = o.kind === "spikes";
      key("height by value (square root of its share of the largest)");
      return [
        new ColumnLayer<Row>({
          id,
          data: placed,
          getPosition: pos,
          diskResolution: spike ? 3 : 10,
          radius: (spike ? 1.4 : 2.8) * mpp,
          extruded: true,
          getElevation: (r) => Math.max(2 * mpp, share(valOf(r)) * tall * (spike ? 1.5 : 1)),
          getFillColor: (r) => [...colour(r), 235],
          updateTriggers: { getElevation: [hi, tall] },
          material: { ambient: 0.6, diffuse: 0.55, shininess: 20, specularColor: [50, 50, 50] },
          ...common,
        }),
      ];
    }
    case "beams": {
      key("a beam per record, height by value");
      const bands = [
        [0, 0.4, 255],
        [0.4, 0.72, 170],
        [0.72, 1, 75],
      ] as const;
      return [
        new ScatterplotLayer<Row>({ id: `${id}:glow`, data: placed, getPosition: pos, radiusUnits: "pixels", getRadius: (r) => 2 + 6 * share(valOf(r)), getFillColor: (r) => [...colour(r), 70], pickable: true, parameters: ON_TOP }),
        ...bands.map(
          ([a, b, alpha], i) =>
            new LineLayer<Row>({
              id: `${id}:beam${i}`,
              data: placed,
              getSourcePosition: (r) => [...pos(r), share(valOf(r)) * tall * 1.2 * a] as [number, number, number],
              getTargetPosition: (r) => [...pos(r), share(valOf(r)) * tall * 1.2 * b] as [number, number, number],
              getColor: (r) => [...colour(r), alpha],
              getWidth: (r) => 1.5 + 3.5 * share(valOf(r)),
              widthUnits: "pixels",
              updateTriggers: { getSourcePosition: [hi, tall], getTargetPosition: [hi, tall] },
              pickable: i === 0,
              parameters: ON_TOP,
            }),
        ),
      ];
    }
    case "lollipops": {
      key("a stem per record, its head at height by value");
      const h = (r: Row) => share(valOf(r)) * tall;
      return [
        new LineLayer<Row>({ id: `${id}:stem`, data: placed, getSourcePosition: (r) => [...pos(r), 0] as [number, number, number], getTargetPosition: (r) => [...pos(r), h(r)] as [number, number, number], getColor: (r) => [...colour(r), 160], getWidth: 1.4, widthUnits: "pixels", updateTriggers: { getTargetPosition: [hi, tall] } }),
        new ScatterplotLayer<Row>({ id, data: placed, getPosition: (r) => [...pos(r), h(r)] as [number, number, number], billboard: true, radiusUnits: "pixels", getRadius: 4.5, getFillColor: (r) => [...colour(r), 240], stroked: true, getLineColor: [8, 10, 14, 220], lineWidthUnits: "pixels", getLineWidth: 0.8, updateTriggers: { getPosition: [hi, tall] }, ...common }),
      ];
    }
    case "point_cloud": {
      key("each record a point at height by value");
      return [new PointCloudLayer<Row>({ id, data: placed, getPosition: (r) => [...pos(r), t(valOf(r)) * tall * 1.2] as [number, number, number], getColor: (r) => [...colour(r), 230], pointSize: 3.5, sizeUnits: "pixels", updateTriggers: { getPosition: [lo, hi, tall] }, ...common })];
    }
    default:
      return [];
  }
}

/** The agent's overlays of this frame (main map or one of the Maps view's maps). */
export function agentLayers(fr: Frame): Layer[] {
  if (!fr.agent?.length) return [];
  return fr.agent.flatMap((d) => overlayLayers(fr, d));
}

/** The hover card of an agent layer: the overlay's tooltip columns (rows), or the bin's figure. */
export function agentTip(layerId: string, object: unknown): string | null {
  const id = layerId.split(":").slice(0, 3).join(":");
  const o = TIPS.get(id);
  if (!o || !object || typeof object !== "object") return null;
  const obj = object as Record<string, unknown>;
  const SRC = `<div style="color:#8d94a1;font-size:10px;margin-top:3px">${o.source}</div>`;
  const unit = o.value?.unit ?? o.size?.unit ?? "";
  if ("polygon" in obj && "v" in obj && !("r" in obj)) {
    const h = obj as { v: number; v2?: number };
    return `<b>${o.legend.title}: ${Number(h.v).toLocaleString("en-US", { maximumFractionDigits: 2 })} ${unit}</b>${o.value2 && h.v2 != null ? `<div>${o.value2.column}: ${h.v2.toLocaleString("en-US", { maximumFractionDigits: 2 })} ${o.value2.unit}</div>` : ""}<div>${o.legend.how}</div>${SRC}`;
  }
  if ("centre" in obj && "v" in obj) {
    const c = obj as { v: number };
    return `<b>${o.legend.title}: ${c.v.toLocaleString("en-US", { maximumFractionDigits: 2 })} ${unit}</b><div>${o.legend.how}</div>${SRC}`;
  }
  if ("cat" in obj && "total" in obj) {
    const p = obj as { cat: string; v: number; total: number };
    return `<b>${p.cat}: ${p.v.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${unit}</b><div>of ${p.total.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${unit} here</div>${SRC}`;
  }
  const row = ("r" in obj ? obj.r : obj) as Row;
  const cols = o.tooltip?.length ? o.tooltip : [o.label, o.category, o.value?.column, o.value2?.column, o.size?.column].filter(Boolean) as string[];
  const lines = cols.map((c) => `<div>${c}: <b>${typeof row[c] === "number" ? (row[c] as number).toLocaleString("en-US", { maximumFractionDigits: 2 }) : String(row[c] ?? "–")}</b></div>`).join("");
  return `<b>${o.legend.title}</b>${lines}${SRC}`;
}
