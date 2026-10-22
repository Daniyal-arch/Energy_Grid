// Country scale: a dataset's records summed into hexagons (one variable: coloured by the largest
// type, strength by the square root of the share of the largest hexagon; two variables: a 3×3
// bivariate colour from each variable's terciles). Zoomed in past POINTS_ZOOM the records are drawn
// one by one again. Every figure is a sum of the file's own values (lib/measures.ts), said in the key.

import type { Layer } from "@deck.gl/core";
import { SolidPolygonLayer } from "@deck.gl/layers";
import { create } from "zustand";

import { shapeOf } from "../app/areaShape";
import { DATASETS, DATASET_BY_ID, datasetOn } from "../app/datasets";
import type { CountriesFile, WorldFile } from "../app/types";
import { inside } from "../lib/area";
import { MEASURES, MEASURE_BY_ID, type Measure, type Pt } from "../lib/measures";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";

/** From this zoom every record is drawn (sites, cities); below it, hexagons. */
export const POINTS_ZOOM = 7.2;
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** Hexagon size by zoom (circumradius, km): about the same size on screen at every scale. */
export const hexKm = (zoom: number) => {
  const z = Math.floor(zoom * 2) / 2;
  return Math.round(Math.max(4, Math.min(45, 80 / 2 ** (z - 4))));
};

/** The variables drawn: the user's pick (up to two) among the datasets on, else the first on. */
export function mapVariables(st: { layers: Frame["layers"]; colour?: string; mapVars?: string[] }): Measure[] {
  const on = new Set(DATASETS.filter((d) => datasetOn(d, st.layers)).map((d) => d.id));
  const picked = (st.mapVars ?? []).map((id) => MEASURE_BY_ID.get(id)).filter((m): m is Measure => !!m && on.has(m.dataset)).slice(0, 2);
  if (picked.length) return picked;
  const auto = MEASURES.find((m) => on.has(m.dataset) && m.id !== "gb-waiting");
  return auto ? [auto] : [];
}

/** The datasets drawn as hexagons in this frame (their points are not drawn). */
export function hexDatasets(fr: { zoom: number; layers: Frame["layers"]; colour?: string; mapVars?: string[] }): Set<string> {
  if (fr.zoom >= POINTS_ZOOM) return new Set();
  return new Set(mapVariables(fr).map((m) => m.dataset));
}

export interface Hex {
  key: string;
  polygon: [number, number][];
  v: number;
  v2: number;
  /** the largest type and the types' sums (single variable) */
  top: string;
  types: [string, number][];
  cls?: [number, number];
}

/** What the key needs (published when it changes). */
export const useHexInfo = create<{ rKm: number; vars: string[]; max: number; breaks: [number[], number[]] | null; count: number }>(() => ({ rKm: 0, vars: [], max: 0, breaks: null, count: 0 }));

function bin(points: Pt[], rKm: number, lat0: number, keep: ((lon: number, lat: number) => boolean) | null) {
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
    out.set(key, { key, polygon, v: b.v, v2: 0, top: types[0]?.[0] ?? "", types });
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
  if (fr.zoom >= POINTS_ZOOM || !fr.mapVars.length) return [];
  const vars = fr.mapVars.map((id) => MEASURE_BY_ID.get(id)!).filter(Boolean);
  if (!vars.length) return [];
  const rKm = hexKm(fr.zoom);
  // the hexagon grid is laid out for the latitude in view (5° steps)
  const lat0 = Math.round(fr.centre[1] / 5) * 5;
  const w = fr.files.world as WorldFile | undefined;
  const shape = shapeOf(fr.area, fr.drawn, w, fr.files.countries as CountriesFile | undefined);
  const keep = shape && shape.km2 <= 3_000_000 ? (lon: number, lat: number) => inside(shape, lon, lat) : null;
  const pts = vars.map((m) => memo(`hexPts:${m.id}`, m.files.map((k) => fr.files[k]), () => m.points(fr.files)));
  if (pts.some((p) => !p)) return [];
  const hexes = memo(`hexes:${vars.map((m) => m.id).join("+")}`, [...pts, rKm, lat0, shape?.key ?? ""], () => {
    const a = bin(pts[0]!, rKm, lat0, keep);
    if (vars.length === 1) return [...a.values()];
    const b = bin(pts[1]!, rKm, lat0, keep);
    for (const [key, h] of b) {
      const x = a.get(key);
      if (x) x.v2 = h.v;
      else a.set(key, { ...h, v: 0, v2: h.v, top: "", types: [] });
    }
    const all = [...a.values()];
    const bx = terciles(all.map((h) => h.v));
    const by = terciles(all.map((h) => h.v2));
    for (const h of all) h.cls = [cls(h.v, bx), cls(h.v2, by)];
    return Object.assign(all, { breaks: [bx, by] as [number[], number[]] });
  });
  const max = Math.max(1e-9, ...hexes.map((h) => h.v));
  const breaks = (hexes as Hex[] & { breaks?: [number[], number[]] }).breaks ?? null;
  const info = useHexInfo.getState();
  const ids = vars.map((m) => m.id);
  if (info.rKm !== rKm || info.max !== max || info.count !== hexes.length || info.vars.join() !== ids.join()) useHexInfo.setState({ rKm, vars: ids, max, breaks, count: hexes.length });
  const m = vars[0];
  const fill = (h: Hex): [number, number, number, number] => {
    if (vars.length === 2 && h.cls) return [...BIVARIATE[h.cls[1]][h.cls[0]], 225];
    const c = (m.types && m.types[h.top]) ?? m.color;
    return [...c, Math.round(45 + 190 * Math.sqrt(h.v / max))];
  };
  return [
    new SolidPolygonLayer<Hex>({
      id: vars.length === 2 ? "hex-bivariate" : "hex-map",
      data: hexes,
      getPolygon: (h) => h.polygon,
      getFillColor: fill,
      updateTriggers: { getFillColor: [ids.join(), max] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 50],
      parameters: ON_TOP,
    }),
  ];
}

/** The measures of a dataset that is on (for the variable picker). */
export const pickable = (layers: Frame["layers"]) => MEASURES.filter((m) => datasetOn(DATASET_BY_ID.get(m.dataset)!, layers));
