// Check a site: what the map's own files say about one place. Every figure is a value from a
// file (named with its source in the cards) or computed here: straight-line distances on the
// sphere, point-in-polygon tests and sums over a fixed radius. Nothing is estimated.

import { VectorTile } from "@mapbox/vector-tile";
import Protobuf from "pbf";
import { PMTiles } from "pmtiles";
import { create } from "zustand";

import { HV_TILES } from "./worldPlants";
import { US_LINES_TILES } from "./us";

/** Plants, data centres and capacity sites are summed within this distance of the site. */
export const SITE_RADIUS_KM = 50;
/** The line tiles are read at this zoom (all features: the tiles drop none). */
const LINE_ZOOM = 9;
const EARTH_KM = 6371.0088;
const RAD = Math.PI / 180;

export type LonLat = [number, number];

/** Great-circle distance in km (haversine). */
export function km(a: LonLat, b: LonLat): number {
  const dLat = (b[1] - a[1]) * RAD;
  const dLon = (b[0] - a[0]) * RAD;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Is the point inside a ring of flat lon/lat pairs [x0, y0, x1, y1, ...] (ray casting)? */
function inFlatRing(x: number, y: number, ring: number[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
    const xi = ring[i];
    const yi = ring[i + 1];
    const xj = ring[j];
    const yj = ring[j + 1];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Polygons as the build scripts write them: [polygon][ring] of flat lon/lat pairs, the first
 *  ring the outline, the others holes. */
export function inFlatPolygons(p: LonLat, polygons: number[][][]): boolean {
  return polygons.some((poly) => poly.length > 0 && inFlatRing(p[0], p[1], poly[0]) && !poly.slice(1).some((hole) => inFlatRing(p[0], p[1], hole)));
}

/** The same for rings of [lon, lat] pairs (the Dutch capacity map's areas). */
export function inPairPolygons(p: LonLat, polygons: [number, number][][][]): boolean {
  return inFlatPolygons(
    p,
    polygons.map((poly) => poly.map((ring) => ring.flat())),
  );
}

/** World outlines (GeoJSON MultiPolygon coordinates). */
export function inGeoJsonPolygons(p: LonLat, coordinates: number[][][][]): boolean {
  return inFlatPolygons(
    p,
    coordinates.map((poly) => poly.map((ring) => ring.flat())),
  );
}

/** Distance from the site to a segment, on a local flat projection around the site (km; the
 *  error stays well under 1 % within a few hundred km), and the nearest point. */
function toSegment(site: LonLat, a: LonLat, b: LonLat): { d: number; at: LonLat } {
  const kx = Math.cos(site[1] * RAD) * EARTH_KM * RAD;
  const ky = EARTH_KM * RAD;
  const ax = (a[0] - site[0]) * kx;
  const ay = (a[1] - site[1]) * ky;
  const bx = (b[0] - site[0]) * kx;
  const by = (b[1] - site[1]) * ky;
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
  const px = ax + t * dx;
  const py = ay + t * dy;
  return { d: Math.hypot(px, py), at: [site[0] + px / kx, site[1] + py / ky] };
}

/** Nearest point of a line of flat lon/lat pairs. */
export function nearestOnFlat(site: LonLat, flat: number[]): { d: number; at: LonLat } {
  let best = { d: Infinity, at: site };
  for (let i = 0; i + 3 < flat.length; i += 2) {
    const r = toSegment(site, [flat[i], flat[i + 1]], [flat[i + 2], flat[i + 3]]);
    if (r.d < best.d) best = r;
  }
  return best;
}

// ------------------------------------------------------------------ lines from the map's tiles

export interface NearLine {
  kv: number | null;
  name: string | null;
  km: number;
  at: LonLat;
  dc: boolean;
}
export interface LineSearch {
  /** the nearest line of any voltage in the tiles, and the nearest of 345 kV or more */
  nearest: NearLine | null;
  ehv: NearLine | null;
  /** lines farther than this may sit outside the tiles read: they are not reported */
  radiusKm: number;
}

const archives = new Map<string, PMTiles>();
const archiveOf = (url: string) => {
  const u = url.replace(/^pmtiles:\/\//, "");
  let a = archives.get(u);
  if (!a) archives.set(u, (a = new PMTiles(u)));
  return a;
};

const tileX = (lon: number, n: number) => Math.floor(((lon + 180) / 360) * n);
const tileY = (lat: number, n: number) => {
  const r = lat * RAD;
  return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
};
const lonOf = (x: number, n: number) => (x / n) * 360 - 180;
const latOf = (y: number, n: number) => Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) / RAD;

/** The nearest lines around a site in a PMTiles archive of lines (properties kv, name, dc):
 *  the tile holding the site and its eight neighbours at zoom 9, so every line within one
 *  tile's width (about 78 km at the equator, 50 km at 50° N) is found. */
export async function nearestTileLines(url: string, layer: string, site: LonLat): Promise<LineSearch> {
  const z = LINE_ZOOM;
  const n = 2 ** z;
  const tx = tileX(site[0], n);
  const ty = tileY(site[1], n);
  const a = archiveOf(url);
  const jobs: Promise<NearLine[]>[] = [];
  for (let dx = -1; dx <= 1; dx++)
    for (let dy = -1; dy <= 1; dy++) {
      const x = (tx + dx + n) % n;
      const y = ty + dy;
      if (y < 0 || y >= n) continue;
      jobs.push(
        a.getZxy(z, x, y).then((res) => {
          if (!res) return [];
          const vt = new VectorTile(new Protobuf(new Uint8Array(res.data)));
          const lyr = vt.layers[layer];
          if (!lyr) return [];
          const out: NearLine[] = [];
          for (let i = 0; i < lyr.length; i++) {
            const f = lyr.feature(i);
            const props = f.properties as { kv?: number; name?: string; dc?: number };
            let best: { d: number; at: LonLat } = { d: Infinity, at: site };
            for (const part of f.loadGeometry()) {
              const flat: number[] = [];
              for (const p of part) flat.push(lonOf(x + p.x / lyr.extent, n), latOf(y + p.y / lyr.extent, n));
              const r = nearestOnFlat(site, flat);
              if (r.d < best.d) best = r;
            }
            if (Number.isFinite(best.d)) out.push({ kv: typeof props.kv === "number" ? props.kv : null, name: props.name ?? null, km: best.d, at: best.at, dc: props.dc === 1 });
          }
          return out;
        }),
      );
    }
  const all = (await Promise.all(jobs)).flat();
  // the shortest distance from the site to the edge of the nine tiles read
  const x0 = lonOf(tx - 1, n);
  const x1 = lonOf(tx + 2, n);
  const y0 = latOf(ty + 2, n);
  const y1 = latOf(ty - 1, n);
  const radiusKm = Math.min(km(site, [x0, site[1]]), km(site, [x1, site[1]]), km(site, [site[0], y0]), km(site, [site[0], y1]));
  const inside = all.filter((l) => l.km <= radiusKm).sort((p, q) => p.km - q.km);
  return { nearest: inside[0] ?? null, ehv: inside.find((l) => (l.kv ?? 0) >= 345) ?? null, radiusKm };
}

// ------------------------------------------------------------------ the site's line searches, shared with the map

type Search = { key: string; result: LineSearch | null; failed: boolean };
interface SiteLines {
  /** OpenStreetMap lines of 220 kV and more (worldwide tiles) */
  world: Search;
  /** OpenStreetMap lines of 100 kV and more (the US tiles) */
  us: Search;
}
const idle: Search = { key: "", result: null, failed: false };
/** The line searches for the selected site (the panel shows them, the map draws the link). */
export const useSiteLines = create<SiteLines>(() => ({ world: idle, us: idle }));

export const siteKey = (site: LonLat) => `${site[0].toFixed(4)},${site[1].toFixed(4)}`;

/** Start a line search for a site (once per site and tile set). */
export function searchSiteLines(which: keyof SiteLines, site: LonLat): void {
  const key = siteKey(site);
  if (useSiteLines.getState()[which].key === key) return;
  useSiteLines.setState({ [which]: { key, result: null, failed: false } });
  const done = (v: Search) => {
    if (useSiteLines.getState()[which].key === key) useSiteLines.setState({ [which]: v });
  };
  const [url, layer] = which === "world" ? [HV_TILES, "hv"] : [US_LINES_TILES, "lines"];
  nearestTileLines(url, layer, site)
    .then((result) => done({ key, result, failed: false }))
    .catch(() => done({ key, result: null, failed: true }));
}

/** "4.2 km" (one decimal under 10 km). */
export const kmText = (v: number) => (v < 10 ? `${v.toFixed(1)} km` : `${Math.round(v)} km`);
