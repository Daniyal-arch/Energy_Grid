// The dashboard's area: outside it the map is dimmed, its outline drawn over everything; while an
// area is being drawn, its corners and edges. Also a dataset's coverage (the countries it holds data
// for, tinted in its colour while the Datasets panel shows its details). Calm: no motion.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { shapeOf } from "../app/areaShape";
import { DATASET_BY_ID, coverageIso3 } from "../app/datasets";
import type { CountriesFile, WorldFile } from "../app/types";
import { inside, type AreaShape } from "../lib/area";
import { ISO3 } from "../lib/transition";
import type { Frame } from "./build";
import { memo } from "./memo";

type Ring = [number, number][];
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
const EDGE: [number, number, number] = [255, 246, 230];

const rgbOf = (css: string): [number, number, number] => {
  const m = css.match(/\d+/g)?.map(Number) ?? [150, 160, 180];
  return [m[0], m[1], m[2]];
};
const pairs = (flat: number[]): Ring => Array.from({ length: flat.length / 2 }, (_, i) => [flat[2 * i], flat[2 * i + 1]]);

function shapesOf(w: WorldFile, codes: Set<string> | null): { polygon: Ring[] }[] {
  return w.features.filter((f) => !codes || codes.has(f.properties.iso3)).flatMap((f) => f.geometry.coordinates.map((poly) => ({ polygon: poly as Ring[] })));
}

/** Polygons drawable as holes: those crossing the date line (Alaska's Aleutians) are left out. */
const holesOf = (s: AreaShape) => s.polygons.filter((_, k) => s.boxes[k][2] - s.boxes[k][0] < 180);

/** A frame around the area with the area cut out: everything around it is dimmed. */
function maskOf(s: AreaShape): Ring[] {
  const holes = holesOf(s);
  const boxes = s.polygons.map((_, k) => s.boxes[k]).filter((b) => b[2] - b[0] < 180);
  const x0 = Math.min(...boxes.map((b) => b[0]));
  const y0 = Math.min(...boxes.map((b) => b[1]));
  const x1 = Math.max(...boxes.map((b) => b[2]));
  const y1 = Math.max(...boxes.map((b) => b[3]));
  const pad = Math.max(8, (x1 - x0) * 1.5, (y1 - y0) * 1.5);
  const X0 = Math.max(-180, x0 - pad);
  const X1 = Math.min(180, x1 + pad);
  const Y0 = Math.max(-85, y0 - pad);
  const Y1 = Math.min(85, y1 + pad);
  return [
    [
      [X0, Y0],
      [X1, Y0],
      [X1, Y1],
      [X0, Y1],
      [X0, Y0],
    ],
    ...holes.map((p) => pairs(p[0])),
  ];
}

/** Every other country, dimmed (a country area): no frame around the area, nothing across the date line. */
function veilOf(s: AreaShape, w: WorldFile, c: CountriesFile | undefined): { polygon: Ring[] }[] {
  const keep = new Set(s.countries ?? []);
  const eu = new Map((c?.countries ?? []).map((x) => [ISO3[x.iso] ?? x.iso, x]));
  const out: { polygon: Ring[] }[] = [];
  for (const f of w.features) {
    const code = f.properties.iso3;
    if (keep.has(code)) continue;
    const e = eu.get(code);
    if (e) for (const p of e.polygons) out.push({ polygon: p.map(pairs) });
    else
      for (const p of f.geometry.coordinates) {
        const xs = p[0].map((q) => q[0]);
        if (Math.max(...xs) - Math.min(...xs) < 180) out.push({ polygon: p as Ring[] });
      }
  }
  return out;
}

/** Where a dataset has data: its countries tinted and outlined, under the data itself. */
export function coverageLayers(fr: Frame): Layer[] {
  const w = fr.files.world as WorldFile | undefined;
  const out: Layer[] = [];
  const ds = fr.coverageOf ? DATASET_BY_ID.get(fr.coverageOf) : undefined;
  if (ds && w) {
    const codes = coverageIso3(ds);
    const shapes = memo("coverageShapes", [w, ds], () => shapesOf(w, codes));
    const c = rgbOf(ds.color);
    out.push(
      new SolidPolygonLayer<{ polygon: Ring[] }>({ id: "coverage-fill", data: shapes, getPolygon: (d) => d.polygon, getFillColor: [...c, 30], parameters: ON_TOP }),
      new PathLayer<Ring>({
        id: "coverage-outline",
        data: memo("coverageRings", [shapes], () => shapes.map((s) => s.polygon[0])),
        getPath: (d) => d,
        getColor: [...c, 150],
        getWidth: 1,
        widthUnits: "pixels",
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}

export function areaLayers(fr: Frame): Layer[] {
  const w = fr.files.world as WorldFile | undefined;
  const out: Layer[] = [];
  // the area (not while a country is selected: the country panel outlines its own)
  const shape = fr.selection ? null : shapeOf(fr.area, fr.drawn, w, fr.files.countries as CountriesFile | undefined);
  if (shape) {
    const countries = fr.files.countries as CountriesFile | undefined;
    const mask = memo("areaMask", [shape.key, w, countries], () => (shape.kind === "countries" && w ? veilOf(shape, w, countries) : [{ polygon: maskOf(shape) }]));
    const rings = memo("areaRings", [shape.key], () => holesOf(shape).map((p) => pairs(p[0])));
    out.push(
      new SolidPolygonLayer<{ polygon: Ring[] }>({ id: "area-mask", data: mask, getPolygon: (d) => d.polygon, getFillColor: [5, 7, 11, 150], parameters: ON_TOP }),
      new PathLayer<Ring>({ id: "area-glow", data: rings, getPath: (d) => d, getColor: [...EDGE, 40], getWidth: 6, widthUnits: "pixels", jointRounded: true, parameters: ON_TOP }),
      new PathLayer<Ring>({ id: "area-outline", data: rings, getPath: (d) => d, getColor: [...EDGE, 210], getWidth: 1.4, widthUnits: "pixels", jointRounded: true, parameters: ON_TOP }),
    );
  }
  // an area being drawn: its edges, closed with a faint one back to the first corner
  const d = fr.drawing;
  if (d && d.length) {
    const open: Ring = d.map((p) => [p[0], p[1]]);
    // from three corners the area fills in as it grows
    if (d.length >= 3)
      out.push(
        new SolidPolygonLayer<{ polygon: Ring }>({
          id: "draw-fill",
          data: [{ polygon: [...open, open[0]] }],
          getPolygon: (x) => x.polygon,
          getFillColor: [120, 190, 255, 55],
          parameters: ON_TOP,
          updateTriggers: { getPolygon: [d.length] },
        }),
      );
    out.push(
      new PathLayer<Ring>({ id: "draw-edges", data: [open], getPath: (x) => x, getColor: [...EDGE, 230], getWidth: 1.6, widthUnits: "pixels", parameters: ON_TOP }),
      ...(d.length >= 3
        ? [new PathLayer<Ring>({ id: "draw-close", data: [[open[open.length - 1], open[0]]], getPath: (x) => x, getColor: [...EDGE, 90], getWidth: 1, widthUnits: "pixels", parameters: ON_TOP })]
        : []),
      new ScatterplotLayer<[number, number]>({
        id: "draw-corners",
        data: open,
        getPosition: (p) => p,
        radiusUnits: "pixels",
        getRadius: (_p, { index }) => (index === 0 ? 5 : 3.5),
        getFillColor: [12, 15, 21, 255],
        getLineColor: [...EDGE, 255],
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}

// ------------------------------------------------------------------ the data inside the area only

/** Data layers drawn only inside a dashboard's area (a country, a drawn polygon, a circle): plants,
 *  grid, emitters, charging, capacity maps, registers, industry... Flows, prices, towers, the
 *  countries and the area's own layers are left whole. */
const CLIPPED = /^(eu-grid-|eu-hvdc|eu-substations|eu-plants|eu-plant-glow|eu-ets|eu-ev|eu-gas-storage|eu-gas-projects|eu-hydrogen|eu-lng-|eu-offshore-wind|eu-tyndp|eu-connect|reg:|de-mastr-|w-plants|w-datacentres|w-dc-|label-dc|w-ctrace|gem-|us-plants|us-turbines|us-solar|us-ev|us-ghgrp|us-gas-pipes|fin-projects|w-cables|w-sea-cables|w-sea-pipes)/;
/** Continents are not clipped: the dimmed world around them says enough. */
const CLIP_MAX_KM2 = 3_000_000;

type Pos = number[];
type Fn = (d: unknown, info: { index: number; data: unknown; target: unknown[] }) => unknown;

function anyInside(s: AreaShape, path: unknown): boolean {
  if (!Array.isArray(path) || !path.length) return false;
  if (typeof path[0] === "number") {
    for (let i = 0; i + 1 < path.length; i += 2) if (inside(s, path[i] as number, path[i + 1] as number)) return true;
    return false;
  }
  if (Array.isArray(path[0]) && typeof path[0][0] === "number") return (path as Pos[]).some((p) => inside(s, p[0], p[1]));
  // rings of a polygon: its outline decides
  return anyInside(s, path[0]);
}

/** Country-level layers keep the area's countries (records with a country code; flows touching them). */
const BY_COUNTRY = /^(price-terrain|eu-tower)/;
type Coded = { iso?: string; country?: string };
const codeOf = (d: unknown) => (d && typeof d === "object" ? ((d as Coded).iso ?? (d as Coded).country) : undefined);

/** The layers with only the records inside the area (each layer's own position accessor). */
export function clipToArea(fr: Frame, layers: Layer[]): Layer[] {
  const w = fr.files.world as WorldFile | undefined;
  const shape = shapeOf(fr.area, fr.drawn, w, fr.files.countries as CountriesFile | undefined);
  if (!shape || shape.km2 > CLIP_MAX_KM2) return layers;
  const mine = new Set(shape.countries ?? []);
  return layers.map((l) => {
    if (shape.countries && BY_COUNTRY.test(l.id) && Array.isArray((l.props as { data?: unknown }).data)) {
      const data = (l.props as { data: unknown[] }).data;
      const kept = memo(`clipc:${l.id}`, [data, shape.key], () => data.filter((d) => {
        const c = codeOf(d);
        return !c || mine.has(ISO3[c] ?? c);
      }));
      return l.clone({ data: kept } as never);
    }
    if (!CLIPPED.test(l.id)) return l;
    const p = l.props as unknown as { data: unknown; getPosition?: unknown; getPath?: unknown; getPolygon?: unknown; getSourcePosition?: unknown; getTargetPosition?: unknown };
    if (!Array.isArray(p.data)) return l;
    const data = p.data as unknown[];
    const test =
      typeof p.getPosition === "function"
        ? (d: unknown, i: number) => {
            const q = (p.getPosition as Fn)(d, { index: i, data, target: [] }) as Pos;
            return !!q && inside(shape, q[0], q[1]);
          }
        : typeof p.getPath === "function"
          ? (d: unknown, i: number) => anyInside(shape, (p.getPath as Fn)(d, { index: i, data, target: [] }))
          : typeof p.getPolygon === "function"
            ? (d: unknown, i: number) => anyInside(shape, (p.getPolygon as Fn)(d, { index: i, data, target: [] }))
            : typeof p.getSourcePosition === "function"
              ? (d: unknown, i: number) => {
                  const a = (p.getSourcePosition as Fn)(d, { index: i, data, target: [] }) as Pos;
                  const b = (p.getTargetPosition as Fn)(d, { index: i, data, target: [] }) as Pos;
                  return inside(shape, a[0], a[1]) || inside(shape, b[0], b[1]);
                }
              : null;
    if (!test) return l;
    const kept = memo(`clip:${l.id}`, [data, shape.key], () => data.filter((d, i) => test(d, i)));
    return l.clone({ data: kept } as never);
  });
}
