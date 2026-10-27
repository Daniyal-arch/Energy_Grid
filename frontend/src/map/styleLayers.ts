// A dataset drawn in a style of its own, the same menu on the main map and in the Maps view
// (docs/VISUALIZATION.md #5): records as bubbles sized by their value, summed into hexagons, as 3D
// bars or 3D beams; continuous data (rasters) averaged into hexagons (choropleth) or raised by
// value (3D terrain). Sizes and colours follow what is in view, so a continent spreads its own
// range and a city its own. Nothing switches by itself: the style holds at every zoom. Every
// figure is the file's own value (lib/measures.ts), a sum or a mean as the key says.

import type { Layer } from "@deck.gl/core";
import { ColumnLayer, LineLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { create } from "zustand";

import { shapeOf } from "../app/areaShape";
import { DATASET_BY_ID } from "../app/datasets";
import type { Style } from "../app/maps";
import { DEFAULT_STYLE, styleOf } from "../app/styleDefaults";
import type { LayerId } from "../app/store";
import type { CountriesFile, WorldFile } from "../app/types";
import { inside, type AreaShape } from "../lib/area";
import { RASTER_BY_DATASET, measureOfDataset, typeColour, type Measure, type Pt, type RasterMeasure } from "../lib/measures";
import { rasterCells } from "../lib/rasterCache";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { binPoints, hexKm, type Hex } from "./hexLayers";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
/** Areas larger than this (a continent) are not clipped: the veil around them says enough. */
const CLIP_MAX_KM2 = 3_000_000;
const OWN: ReadonlySet<Style> = new Set(["points", "lines", "raster"]);
export const is3D = (st: Style | undefined) => st === "bars" || st === "beams" || st === "terrain";

/** The styles a dataset can take: records, continuous data or lines (one menu everywhere). */
export function stylesOf(dataset: string): Style[] {
  if (RASTER_BY_DATASET.has(dataset)) return ["raster", "choropleth", "terrain"];
  if (measureOfDataset(dataset)) return ["points", "bubbles", "hex", "bars", "beams"];
  return [];
}
export const STYLE_LABEL: Record<Style, string> = {
  points: "Points",
  bubbles: "Bubbles",
  hex: "Hexagons",
  bars: "3D bars",
  beams: "3D beams",
  lines: "Lines",
  raster: "Raster",
  choropleth: "Choropleth",
  terrain: "3D terrain",
};

export { styleOf };

type Applied = { layers: Record<LayerId, boolean>; styled: [string, Style][] };
// the same inputs give the same objects, so what depends on the layers is not rebuilt every frame
const applied = new WeakMap<object, WeakMap<object, Applied>>();
/** The datasets drawn in a style of their own, and the layers the frame draws itself (their own
 *  layers step aside). */
export function applyStyles(layers: Record<LayerId, boolean>, styles: Record<string, Style>): Applied {
  let byStyles = applied.get(layers);
  if (!byStyles) applied.set(layers, (byStyles = new WeakMap()));
  const hit = byStyles.get(styles);
  if (hit) return hit;
  const out = applyStylesNow(layers, styles);
  byStyles.set(styles, out);
  return out;
}
function applyStylesNow(layers: Record<LayerId, boolean>, styles: Record<string, Style>): Applied {
  const all = [...Object.entries(DEFAULT_STYLE).filter(([d]) => !(d in styles)), ...Object.entries(styles)];
  const styled = all.filter(
    ([d, st]) => !OWN.has(st) && stylesOf(d).includes(st) && (DATASET_BY_ID.get(d)?.parts ?? []).some((p) => p.layer && layers[p.layer]),
  );
  if (!styled.length) return { layers, styled };
  const off = styled.flatMap(([d]) => DATASET_BY_ID.get(d)!.parts.flatMap((p) => (p.layer ? [[p.layer, false] as const] : [])));
  return { layers: { ...layers, ...Object.fromEntries(off) }, styled };
}

// ------------------------------------------------------------------ the key's figures

export interface StyleInfo {
  style: Style;
  /** the largest (and smallest, continuous data) value in view */
  max: number;
  min: number;
  /** the hexagon's circumradius (hexagons, choropleth, terrain), km */
  rKm: number;
  /** records or hexagons in view */
  count: number;
  /** the largest types in view and their colours (records) */
  types: [string, RGB][];
}
/** Per map (`scope`) and dataset: what its key says. Published when it changes. */
export const useStyleInfo = create<Record<string, StyleInfo>>(() => ({}));
const publish = (key: string, info: StyleInfo) => {
  const was = useStyleInfo.getState()[key];
  if (was && was.style === info.style && was.max === info.max && was.min === info.min && was.rKm === info.rKm && was.count === info.count && was.types.join() === info.types.join()) return;
  useStyleInfo.setState({ [key]: info });
};
/** The largest value of many records (no spread: a long array would overflow the call stack). */
const maxOf = (pts: Pt[]) => {
  let m = 1e-9;
  for (const p of pts) if (p[2] > m) m = p[2];
  return m;
};
/** Two significant digits: the key and the sizes change only when the view's range does. */
const round2 = (v: number) => {
  if (!(v > 0)) return v;
  const p = 10 ** (Math.floor(Math.log10(v)) - 1);
  return Math.round(v / p) * p;
};

function areaShape(fr: Frame): AreaShape | null {
  const shape = shapeOf(fr.area, fr.drawn, fr.files.world as WorldFile | undefined, fr.files.countries as CountriesFile | undefined);
  return shape && shape.km2 <= CLIP_MAX_KM2 ? shape : null;
}

/** A dataset's records inside the area. */
export function recordsOf(m: Measure, fr: Frame, shape: AreaShape | null): Pt[] | null {
  const pts = memo(`stPts:${m.id}`, m.files.map((k) => fr.files[k]), () => m.points(fr.files));
  if (!pts) return null;
  if (!shape) return pts;
  return memo(`stPtsIn:${m.id}`, [pts, shape.key], () => pts.filter((p) => inside(shape, p[0], p[1])));
}

/** The records in view (a quarter-degree box, so a small pan reuses it). */
function inView(key: string, pts: Pt[], bounds: Frame["bounds"]): Pt[] {
  const q = (v: number) => Math.round(v * 4) / 4;
  const [w, s, e, n] = bounds.map(q);
  return memo(`stView:${key}`, [pts, w, s, e, n], () => pts.filter((p) => p[0] >= w && p[0] <= e && p[1] >= s && p[1] <= n));
}

// ------------------------------------------------------------------ records

function recordLayers(fr: Frame, dataset: string, st: Style, shape: AreaShape | null): Layer[] {
  const m = measureOfDataset(dataset);
  if (!m) return [];
  const pts = recordsOf(m, fr, shape);
  if (!pts) return [];
  const seen = inView(`${fr.scope}:${m.id}`, pts, fr.bounds);
  const max = memo(`stMax:${fr.scope}:${m.id}`, [seen, pts], () => round2(maxOf(seen.length ? seen : pts)));
  const rKm = hexKm(fr.zoom);
  const types = memo(`stTypes:${fr.scope}:${m.id}`, [seen], () => {
    const by = new Map<string, number>();
    for (const p of seen) if (p[3]) by.set(p[3], (by.get(p[3]) ?? 0) + p[2]);
    return [...by.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([t]) => [t, typeColour(m, t)] as [string, RGB]);
  });
  publish(`${fr.scope}:${dataset}`, { style: st, max, min: 0, rKm, count: seen.length, types });
  const share = (p: Pt) => Math.sqrt(Math.min(1, Math.max(0, p[2]) / max));
  const colour = (p: Pt): RGB => typeColour(m, p[3]);
  const id = `st-${dataset}`;
  const sorted = memo(`stSorted:${m.id}`, [pts], () => [...pts].sort((a, b) => b[2] - a[2]));
  if (st === "bubbles")
    return [
      new ScatterplotLayer<Pt>({
        id: `${id}-bubbles`,
        data: sorted,
        getPosition: (p) => [p[0], p[1]],
        radiusUnits: "pixels",
        // area by value: the largest in view about 20 px across, the smallest a dot
        getRadius: (p) => 1.5 + 18 * share(p),
        getFillColor: (p) => [...colour(p), 175],
        stroked: true,
        getLineColor: [8, 10, 14, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        updateTriggers: { getRadius: [max] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 70],
        parameters: ON_TOP,
      }),
    ];
  // 3D: height by value (square root of the share of the largest in view), a few hexagons tall
  const tall = rKm * 1000 * 8;
  if (st === "bars")
    return [
      new ColumnLayer<Pt>({
        id: `${id}-bars`,
        data: sorted,
        getPosition: (p) => [p[0], p[1]],
        diskResolution: 10,
        radius: rKm * 1000 * 0.22,
        extruded: true,
        getElevation: (p) => Math.max(rKm * 40, share(p) * tall),
        getFillColor: (p) => [...colour(p), 235],
        updateTriggers: { getElevation: [max, rKm] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 70],
        material: { ambient: 0.6, diffuse: 0.55, shininess: 20, specularColor: [50, 50, 50] },
      }),
    ];
  if (st === "beams") {
    // a beam of light per record, brightest at the ground, fading upwards
    const bands = [
      [0, 0.4, 255],
      [0.4, 0.72, 170],
      [0.72, 1, 75],
    ] as const;
    return [
      new ScatterplotLayer<Pt>({
        id: `${id}-beam-glow`,
        data: sorted,
        getPosition: (p) => [p[0], p[1]],
        radiusUnits: "pixels",
        getRadius: (p) => 2 + 6 * share(p),
        getFillColor: (p) => [...colour(p), 70],
        updateTriggers: { getRadius: [max] },
        pickable: true,
        parameters: ON_TOP,
      }),
      ...bands.map(
        ([a, b, alpha], i) =>
          new LineLayer<Pt>({
            id: `${id}-beam-${i}`,
            data: sorted,
            getSourcePosition: (p) => [p[0], p[1], share(p) * tall * 1.15 * a],
            getTargetPosition: (p) => [p[0], p[1], share(p) * tall * 1.15 * b],
            getColor: (p) => [...colour(p), alpha],
            getWidth: (p) => 1.5 + 3.5 * share(p),
            widthUnits: "pixels",
            updateTriggers: { getSourcePosition: [max, rKm], getTargetPosition: [max, rKm], getWidth: [max] },
            pickable: i === 0,
            parameters: ON_TOP,
          }),
      ),
    ];
  }
  return [];
}

// ------------------------------------------------------------------ continuous data

/** Raster cells averaged into hexagons: [hexagons, the mean's range in view]. */
function rasterHexes(fr: Frame, r: RasterMeasure, shape: AreaShape | null): { hexes: Hex[]; rKm: number; min: number; max: number; step: number } | null {
  const [bw, bs, be, bn] = fr.bounds;
  const box: [number, number, number, number] = shape
    ? [Math.max(bw, shape.bbox[0]), Math.max(bs, shape.bbox[1]), Math.min(be, shape.bbox[2]), Math.min(bn, shape.bbox[3])]
    : [bw, bs, be, bn];
  if (box[2] <= box[0] || box[3] <= box[1]) return null;
  const cells = rasterCells(r, fr.files, box);
  if (!cells) return null;
  // a hexagon holds a few of the cells read
  const rKm = Math.max(hexKm(fr.zoom), cells.cell * 111 * 0.9);
  const lat0 = Math.round(fr.centre[1] / 5) * 5;
  return memo(`stRaster:${fr.scope}:${r.id}`, [cells, rKm, lat0, shape?.key ?? ""], () => {
    const keep = shape ? (lon: number, lat: number) => inside(shape, lon, lat) : null;
    const sum = binPoints(cells.pts, rKm, lat0, keep);
    const ones = binPoints(
      cells.pts.map((p) => [p[0], p[1], 1, ""] as Pt),
      rKm,
      lat0,
      keep,
    );
    const hexes: Hex[] = [];
    for (const [k, h] of ones) hexes.push({ ...h, v: (sum.get(k)?.v ?? 0) / h.v, types: [] });
    let min = Infinity;
    let max = -Infinity;
    for (const h of hexes) {
      if (h.v < min) min = h.v;
      if (h.v > max) max = h.v;
    }
    return { hexes, rKm, min, max, step: cells.step };
  });
}

const ramp = (r: RasterMeasure, t: number): RGB => {
  const x = Math.max(0, Math.min(1, t)) * (r.ramp.length - 1);
  const i = Math.min(r.ramp.length - 2, Math.floor(x));
  const f = x - i;
  return r.ramp[i].map((c, k) => Math.round(c + (r.ramp[i + 1][k] - c) * f)) as RGB;
};

function rasterLayers(fr: Frame, dataset: string, st: Style, shape: AreaShape | null): Layer[] {
  const r = RASTER_BY_DATASET.get(dataset);
  if (!r) return [];
  const got = rasterHexes(fr, r, shape);
  if (!got) return [];
  const { hexes, rKm, min, max } = got;
  publish(`${fr.scope}:${dataset}`, { style: st, max, min, rKm, count: hexes.length, types: [] });
  const t = (h: Hex) => (max > min ? (h.v - min) / (max - min) : 0.5);
  if (st === "terrain")
    return [
      new ColumnLayer<Hex>({
        id: `st-${dataset}-terrain`,
        data: hexes,
        getPosition: (h) => h.centre,
        diskResolution: 6,
        radius: rKm * 1000 * 0.95,
        extruded: true,
        getElevation: (h) => (0.04 + t(h)) * rKm * 1000 * 5,
        getFillColor: (h) => [...ramp(r, t(h)), 245],
        updateTriggers: { getElevation: [min, max], getFillColor: [min, max] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 60],
        material: { ambient: 0.7, diffuse: 0.5, shininess: 6, specularColor: [30, 30, 30] },
      }),
    ];
  return [
    new SolidPolygonLayer<Hex>({
      id: `st-${dataset}-choropleth`,
      data: hexes,
      getPolygon: (h) => h.polygon,
      getFillColor: (h) => [...ramp(r, t(h)), 225],
      updateTriggers: { getFillColor: [min, max] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 50],
      parameters: ON_TOP,
    }),
  ];
}

/** Every styled dataset's layers but the hexagons (map/hexLayers.ts draws those, two make a bivariate map). */
export function styleLayers(fr: Frame): Layer[] {
  if (!fr.styled.length) return [];
  const shape = areaShape(fr);
  const out: Layer[] = [];
  for (const [d, st] of fr.styled) {
    if (st === "choropleth" || st === "terrain") out.push(...rasterLayers(fr, d, st, shape));
    else if (st !== "hex") out.push(...recordLayers(fr, d, st, shape));
  }
  return out;
}

/** The value under the cursor, for the hover card. */
export function styleTip(layerId: string, object: unknown): string | null {
  const m = layerId.match(/^st-([A-Za-z0-9]+)-(bubbles|bars|beam-glow|beam-0|choropleth|terrain)/);
  if (!m || !object) return null;
  const d = m[1];
  const r = RASTER_BY_DATASET.get(d);
  if (r) {
    const h = object as Hex;
    return `<b>${r.label}: ${r.fmt(h.v)} ${r.unit}</b><div style="color:#8d94a1;font-size:10px;margin-top:3px">mean of the grid cells in a hexagon (computed) · ${r.sums}</div>`;
  }
  const ms = measureOfDataset(d);
  if (!ms) return null;
  const p = object as Pt;
  return `<b>${ms.label}: ${ms.fmt(p[2])}${ms.unit && !ms.fmt(p[2]).includes(ms.unit) ? ` ${ms.unit}` : ""}</b>${p[3] ? `<div>${p[3]}</div>` : ""}<div style="color:#8d94a1;font-size:10px;margin-top:3px">${ms.sums}</div>`;
}
