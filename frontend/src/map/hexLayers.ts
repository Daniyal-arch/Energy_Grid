// Hexagons: a dataset's records summed into hexagons, at every scale (one dataset: coloured by the
// largest type, strength by the square root of the share of the largest hexagon in view; two
// datasets: a 3×3 bivariate colour from each one's terciles). The hexagons keep about the same size
// on screen. Every figure is a sum of the file's own values (lib/measures.ts), said in the key.

import type { Layer } from "@deck.gl/core";
import { SolidPolygonLayer } from "@deck.gl/layers";
import { create } from "zustand";

import { shapeOf } from "../app/areaShape";
import type { CountriesFile, WorldFile } from "../app/types";
import { measureOfDataset, typeColour, type Measure, type Pt } from "../lib/measures";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";
import { recordsOf } from "./styleLayers";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** Hexagon size by zoom (circumradius, km): about the same size on screen at every scale. */
export const hexKm = (zoom: number) => {
  const z = Math.floor(zoom * 2) / 2;
  return Math.round(Math.max(1, Math.min(45, 80 / 2 ** (z - 4))));
};

export interface Hex {
  key: string;
  centre: [number, number];
  polygon: [number, number][];
  v: number;
  v2: number;
  /** the largest type and the types' sums (single variable) */
  top: string;
  types: [string, number][];
  cls?: [number, number];
}

export interface HexInfo {
  rKm: number;
  vars: string[];
  max: number;
  breaks: [number[], number[]] | null;
  count: number;
}
/** What each map's key needs (published when it changes), by hexInfoKey. */
export const useHexInfo = create<Record<string, HexInfo>>(() => ({}));

export function binPoints(points: Pt[], rKm: number, lat0: number, keep: ((lon: number, lat: number) => boolean) | null) {
  const kx = 111.32 * Math.cos((lat0 * Math.PI) / 180);
  const ky = 110.57;
  const bins = new Map<string, { q: number; r: number; v: number; types: Map<string, number> }>();
  for (const [lon, lat, v, type] of points) {
    if (!(v > 0) || (keep && !keep(lon, lat))) continue;
    const x = lon * kx;
    const y = lat * ky;
    const qf = ((2 / 3) * x) / rKm;
    const rf = ((-1 / 3) * x + (Math.sqrt(3) / 3) * y) / rKm;
    const sf = -qf - rf;
    let q = Math.round(qf);
    let r = Math.round(rf);
    const s = Math.round(sf);
    const dq = Math.abs(q - qf);
    const dr = Math.abs(r - rf);
    const ds = Math.abs(s - sf);
    if (dq > dr && dq > ds) q = -r - s;
    else if (dr > ds) r = -q - s;
    const key = `${q},${r}`;
    let b = bins.get(key);
    if (!b) bins.set(key, (b = { q, r, v: 0, types: new Map() }));
    b.v += v;
    if (type) b.types.set(type, (b.types.get(type) ?? 0) + v);
  }
  // flat-top hexagons, 92 % of the cell: a thin gap of the map between them
  const corner = (cx: number, cy: number, k: number): [number, number] => {
    const a = (Math.PI / 3) * k;
    return [(cx + 0.92 * rKm * Math.cos(a)) / kx, (cy + 0.92 * rKm * Math.sin(a)) / ky];
  };
  const out = new Map<string, Hex>();
  for (const [key, b] of bins) {
    const cx = rKm * 1.5 * b.q;
    const cy = rKm * Math.sqrt(3) * (b.r + b.q / 2);
    const polygon = [0, 1, 2, 3, 4, 5, 0].map((k) => corner(cx, cy, k));
    const types = [...b.types.entries()].sort((a, c) => c[1] - a[1]);
    out.set(key, { key, centre: [cx / kx, cy / ky], polygon, v: b.v, v2: 0, top: types[0]?.[0] ?? "", types });
  }
  return out;
}

/** Terciles of the non-zero values: the two breaks. */
function terciles(v: number[]): number[] {
  const s = v.filter((x) => x > 0).sort((a, b) => a - b);
  if (!s.length) return [Infinity, Infinity];
  return [s[Math.floor(s.length / 3)], s[Math.floor((2 * s.length) / 3)]];
}
const cls = (v: number, br: number[]) => (v <= 0 ? 0 : v < br[0] ? 0 : v < br[1] ? 1 : 2);

/** 3×3 bivariate colours for a dark map: [y class][x class]; low-low recedes, high-high is lightest. */
export const BIVARIATE: RGB[][] = [
  [
    [58, 64, 78],
    [40, 122, 132],
    [52, 196, 196],
  ],
  [
    [128, 86, 48],
    [118, 128, 112],
    [104, 202, 176],
  ],
  [
    [214, 132, 52],
    [222, 172, 96],
    [236, 226, 170],
  ],
];

export function hexLayers(fr: Frame): Layer[] {
  // the datasets drawn as hexagons on this map: one, or two for a bivariate map
  const vars = fr.styled
    .filter(([, st]) => st === "hex")
    .map(([d]) => measureOfDataset(d))
    .filter((m): m is Measure => !!m)
    .slice(0, 2);
  if (!vars.length) return [];
  const rKm = hexKm(fr.zoom);
  // the hexagon grid is laid out for the latitude in view (5° steps)
  const lat0 = Math.round(fr.centre[1] / 5) * 5;
  const w = fr.files.world as WorldFile | undefined;
  const shape = shapeOf(fr.area, fr.drawn, w, fr.files.countries as CountriesFile | undefined);
  const clip = shape && shape.km2 <= 3_000_000 ? shape : null;
  const pts = vars.map((m) => recordsOf(m, fr, clip));
  if (pts.some((p) => !p)) return [];
  const hexes = memo(`hexes:${fr.scope}:${vars.map((m) => m.id).join("+")}`, [...pts, rKm, lat0], () => {
    const a = binPoints(pts[0]!, rKm, lat0, null);
    if (vars.length === 1) return [...a.values()];
    const b = binPoints(pts[1]!, rKm, lat0, null);
    for (const [key, h] of b) {
      const x = a.get(key);
      if (x) x.v2 = h.v;
      else a.set(key, { ...h, v: 0, v2: h.v, top: "", types: [] });
    }
    return [...a.values()];
  });
  // the scale follows what is in view (a quarter-degree box, so a small pan keeps it): a city
  // spreads its own range, a continent its own; two datasets: the thirds of the hexagons in view
  const q = (v: number) => Math.round(v * 4) / 4;
  const [bw, bs, be, bn] = fr.bounds.map(q);
  const view = memo(`hexView:${fr.scope}`, [hexes, bw, bs, be, bn], () => {
    const seen = hexes.filter((h) => h.centre[0] >= bw && h.centre[0] <= be && h.centre[1] >= bs && h.centre[1] <= bn);
    const pool = seen.length ? seen : hexes;
    let max = 1e-9;
    for (const h of pool) if (h.v > max) max = h.v;
    const breaks: [number[], number[]] | null = vars.length === 2 ? [terciles(pool.map((h) => h.v)), terciles(pool.map((h) => h.v2))] : null;
    if (breaks) for (const h of hexes) h.cls = [cls(h.v, breaks[0]), cls(h.v2, breaks[1])];
    return { max, breaks, count: seen.length };
  });
  const { max, breaks } = view;
  const ids = vars.map((m) => m.id);
  const key = `${fr.scope}:${vars.map((m) => m.dataset).join("+")}`;
  const info = useHexInfo.getState()[key];
  if (!info || info.rKm !== rKm || info.max !== max || info.count !== view.count || info.breaks !== breaks)
    useHexInfo.setState({ [key]: { rKm, vars: ids, max, breaks, count: view.count } });
  const m = vars[0];
  const colourOf = (h: Hex): RGB => typeColour(m, h.top);
  const fill = (h: Hex): [number, number, number, number] => {
    if (vars.length === 2 && h.cls) return [...BIVARIATE[h.cls[1]][h.cls[0]], 225];
    return [...colourOf(h), Math.round(45 + 190 * Math.sqrt(Math.min(1, h.v / max)))];
  };
  return [
    new SolidPolygonLayer<Hex>({
      // the datasets and the hexagon size travel in the id, for the hover card (map/tooltip.ts)
      id: `${vars.length === 2 ? "hex-bivariate" : "hex-map"}|${ids.join("+")}|${rKm}`,
      data: hexes,
      getPolygon: (h) => h.polygon,
      getFillColor: fill,
      updateTriggers: { getFillColor: [ids.join(), max, breaks] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 50],
      parameters: ON_TOP,
    }),
  ];
}

/** The hexagon map of a map (`scope`) and its datasets (`a` or `a+b`): what the key says. */
export const hexInfoKey = (scope: string, datasets: string[]) => `${scope}:${datasets.join("+")}`;
