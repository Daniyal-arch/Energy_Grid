// An area to analyse: countries, a polygon drawn on the map, or a circle around a place (a city).
// Everything the dashboard counts in it is a point-in-polygon test, a sum or a length over the
// map's own files (computed here, said on each card). Nothing is estimated.

import { inFlatPolygons, km, type LonLat } from "./site";

export type { LonLat };

/** A drawn polygon or a circle around a place; countries are the store's `area` list. */
export type AreaSpec = { kind: "polygon"; ring: LonLat[]; name?: string } | { kind: "circle"; at: LonLat; r: number; name?: string };

export interface AreaShape {
  key: string;
  label: string;
  kind: "countries" | "polygon" | "circle";
  /** [polygon][ring] of flat lon/lat pairs, the first ring the outline */
  polygons: number[][][];
  bbox: [number, number, number, number];
  /** area on the sphere, km² (computed from the outline) */
  km2: number;
  /** the countries it is made of (country areas only) */
  countries?: string[];
  /** each polygon's box, tested before its rings */
  boxes: [number, number, number, number][];
}

const RAD = Math.PI / 180;
const EARTH_KM = 6371.0088;

/** Area of a ring of flat lon/lat pairs on the sphere, km² (the spherical excess formula). */
function ringKm2(r: number[]): number {
  let s = 0;
  for (let i = 0; i < r.length; i += 2) {
    const j = (i + 2) % r.length;
    s += (r[j] - r[i]) * RAD * (2 + Math.sin(r[i + 1] * RAD) + Math.sin(r[j + 1] * RAD));
  }
  return Math.abs((s * EARTH_KM * EARTH_KM) / 2);
}

function boxOf(ring: number[]): [number, number, number, number] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  for (let i = 0; i < ring.length; i += 2) {
    x0 = Math.min(x0, ring[i]);
    x1 = Math.max(x1, ring[i]);
    y0 = Math.min(y0, ring[i + 1]);
    y1 = Math.max(y1, ring[i + 1]);
  }
  return [x0, y0, x1, y1];
}

export function makeShape(kind: AreaShape["kind"], key: string, label: string, polygons: number[][][], countries?: string[]): AreaShape {
  const km2 = polygons.reduce((a, p) => a + ringKm2(p[0]) - p.slice(1).reduce((h, r) => h + ringKm2(r), 0), 0);
  const boxes = polygons.map((p) => boxOf(p[0]));
  const bbox: [number, number, number, number] = [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
  return { key, label, kind, polygons, bbox, km2, countries, boxes };
}

/** A circle as a 96-gon (local flat projection: fine at these sizes). */
export function circleRing(at: LonLat, rKm: number, n = 96): number[] {
  const dLat = rKm / 111.2;
  const dLon = dLat / Math.max(0.05, Math.cos(at[1] * RAD));
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n;
    out.push(at[0] + dLon * Math.sin(a), at[1] + dLat * Math.cos(a));
  }
  return out;
}

export function shapeOfSpec(spec: AreaSpec): AreaShape {
  if (spec.kind === "circle") {
    const label = `${spec.r} km around ${spec.name ?? `${spec.at[1].toFixed(2)}, ${spec.at[0].toFixed(2)}`}`;
    return makeShape("circle", `c:${spec.at.join(",")}:${spec.r}`, label, [[circleRing(spec.at, spec.r)]]);
  }
  const flat = spec.ring.flat();
  return makeShape("polygon", `p:${flat.map((v) => v.toFixed(3)).join(",")}`, spec.name ?? "Drawn area", [[flat]]);
}

/** Inside the area (its bounding box first, then the polygons). */
export function inside(s: AreaShape, lon: number, lat: number): boolean {
  const [x0, y0, x1, y1] = s.bbox;
  if (lon < x0 || lon > x1 || lat < y0 || lat > y1) return false;
  for (let k = 0; k < s.polygons.length; k++) {
    const b = s.boxes[k];
    if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) continue;
    if (inFlatPolygons([lon, lat], [s.polygons[k]])) return true;
  }
  return false;
}

/** The rows whose position lies in the area. */
export function pick<T>(rows: readonly T[] | undefined, at: (r: T) => [number, number], s: AreaShape): T[] {
  if (!rows) return [];
  const out: T[] = [];
  for (const r of rows) {
    const [lon, lat] = at(r);
    if (inside(s, lon, lat)) out.push(r);
  }
  return out;
}

/** Length of lines (flat lon/lat pairs) in the area: segments whose midpoint lies inside, km. */
export function kmInside(path: number[], s: AreaShape): number {
  let total = 0;
  for (let i = 0; i + 3 < path.length; i += 2) {
    const mx = (path[i] + path[i + 2]) / 2;
    const my = (path[i + 1] + path[i + 3]) / 2;
    if (inside(s, mx, my)) total += km([path[i], path[i + 1]], [path[i + 2], path[i + 3]]);
  }
  return total;
}

/** The area's size in words. */
export const km2Text = (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(2)} million km²` : `${Math.round(v).toLocaleString("en-US")} km²`);

// ------------------------------------------------------------------ grids read by HTTP range, row by row

export interface GridSpec {
  url: string;
  /** bytes per cell */
  bytes: 1 | 2 | 4;
  width: number;
  height: number;
  /** north-west corner [lon, lat] */
  origin: [number, number];
  cell: number;
}

/** Every cell of a row-major grid whose centre lies in the area: one range request per grid row
 *  the area spans, every `step`-th row and column when it spans more than `maxRows` rows (the
 *  result says which). Calls `each(view, offset, lon, lat)` per cell inside. */
export async function readGrid(g: GridSpec, s: AreaShape, each: (v: DataView, off: number, lon: number, lat: number) => void, maxRows = 240): Promise<{ cells: number; step: number }> {
  const [x0, y0, x1, y1] = s.bbox;
  const r0 = Math.max(0, Math.floor((g.origin[1] - y1) / g.cell));
  const r1 = Math.min(g.height - 1, Math.floor((g.origin[1] - y0) / g.cell));
  const c0 = Math.max(0, Math.floor((x0 - g.origin[0]) / g.cell));
  const c1 = Math.min(g.width - 1, Math.floor((x1 - g.origin[0]) / g.cell));
  if (r1 < r0 || c1 < c0) return { cells: 0, step: 1 };
  const step = Math.max(1, Math.ceil((r1 - r0 + 1) / maxRows));
  let cells = 0;
  const rows: number[] = [];
  for (let r = r0; r <= r1; r += step) rows.push(r);
  // a few rows at a time: the bucket answers many small requests well, but not hundreds at once
  for (let k = 0; k < rows.length; k += 24) {
    await Promise.all(
      rows.slice(k, k + 24).map(async (row) => {
        const a = (row * g.width + c0) * g.bytes;
        const r = await fetch(g.url, { headers: { Range: `bytes=${a}-${a + (c1 - c0 + 1) * g.bytes - 1}` } });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const v = new DataView(await r.arrayBuffer());
        const lat = g.origin[1] - (row + 0.5) * g.cell;
        for (let c = c0; c <= c1; c += step) {
          const lon = g.origin[0] + (c + 0.5) * g.cell;
          if (!inside(s, lon, lat)) continue;
          cells++;
          each(v, (c - c0) * g.bytes, lon, lat);
        }
      }),
    );
  }
  return { cells, step };
}
