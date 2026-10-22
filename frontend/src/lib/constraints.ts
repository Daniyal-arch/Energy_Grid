// What stops a build (scripts/build_constraints.py): protected areas (Natura 2000, PAD-US),
// river flood depth for a 100-year flood (JRC), major roads and railways (Overture). The map
// draws their tiles; "Check a site" reads the same tiles and the flood lookup grid. Shares and
// distances are computed here and say so.

import { VectorTile } from "@mapbox/vector-tile";
import Protobuf from "pbf";
import { PMTiles } from "pmtiles";

import { inGeoJsonPolygons, km, nearestOnFlat, type LonLat } from "./site";

export interface FloodLookup {
  url: string;
  cell_deg: number;
  origin: [number, number];
  width: number;
  height: number;
  computed: string;
}
export interface ConstraintsFile {
  fetched: string;
  flood: {
    title: string;
    source: string;
    /** [from m, to m | null, rgb] per class 1..5 */
    classes: [number | null, number | null, [number, number, number]][];
    maps: Record<"eu" | "world", { title: string; tiles: string; max_zoom: number; lookup: FloodLookup }>;
  };
  roads: { tiles: string; source: string; classes: string[]; rail: string; coverage: string };
}
export interface ProtectedFile {
  fetched: string;
  tiles: string;
  natura2000: { source: string; by_country: Record<string, [number, number]>; unit: string };
  padus: { source: string; by_state: Record<string, [number, number]>; unit: string };
  gap: Record<string, string>;
  /** sources that could not be read in the newest build (e.g. PAD-US timing out) */
  failed?: Record<string, string>;
}

/** Areas, roads and rail are read within this distance of a site. */
export const CONSTRAINT_RADIUS_KM = 10;
/** The share of the circle covered is counted on a grid of points this far apart. */
export const SHARE_STEP_KM = 0.5;
const ZOOM = 9;
const RAD = Math.PI / 180;

export const PROTECTED_COLOR: [number, number, number] = [96, 186, 120];
export const ROAD_COLOR: [number, number, number] = [200, 196, 186];
export const RAIL_COLOR: [number, number, number] = [176, 160, 220];

export const floodLabel = (f: ConstraintsFile, cls: number): string => {
  const c = f.flood.classes[cls - 1];
  if (!c) return "no flooding mapped";
  return c[0] == null ? `under ${c[1]} m` : c[1] == null ? `${c[0]} m or more` : `${c[0]}–${c[1]} m`;
};

const cache = new Map<string, Promise<number>>();
/** The flood class (1..5, 0 = none mapped) of the lookup cell holding a place; -1 outside the grid. */
export function floodClassAt(l: FloodLookup, lon: number, lat: number): Promise<number> {
  const col = Math.floor((lon - l.origin[0]) / l.cell_deg);
  const row = Math.floor((l.origin[1] - lat) / l.cell_deg);
  if (col < 0 || row < 0 || col >= l.width || row >= l.height) return Promise.resolve(-1);
  const at = row * l.width + col;
  const key = `${l.url}#${at}`;
  if (!cache.has(key))
    cache.set(
      key,
      fetch(l.url, { headers: { Range: `bytes=${at}-${at}` }, cache: "no-store" })
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((b) => new Uint8Array(b)[0]),
    );
  return cache.get(key) as Promise<number>;
}

const archives = new Map<string, PMTiles>();
const archiveOf = (url: string) => {
  const u = url.replace(/^pmtiles:\/\//, "");
  let a = archives.get(u);
  if (!a) archives.set(u, (a = new PMTiles(u)));
  return a;
};

interface TileFeature {
  layer: string;
  props: Record<string, unknown>;
  geometry: GeoJSON.Geometry;
}

/** Every feature of the given layers in the zoom-9 tile holding the site and its neighbours,
 *  with lon/lat geometry (a feature cut by tile edges comes in pieces). */
async function aroundSite(url: string, layers: string[], site: LonLat): Promise<{ feats: TileFeature[]; radiusKm: number }> {
  const n = 2 ** ZOOM;
  const tx = Math.floor(((site[0] + 180) / 360) * n);
  const r = site[1] * RAD;
  const ty = Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
  const a = archiveOf(url);
  const jobs: Promise<TileFeature[]>[] = [];
  for (let dx = -1; dx <= 1; dx++)
    for (let dy = -1; dy <= 1; dy++) {
      const x = (tx + dx + n) % n;
      const y = ty + dy;
      if (y < 0 || y >= n) continue;
      jobs.push(
        a.getZxy(ZOOM, x, y).then((res) => {
          if (!res) return [];
          const vt = new VectorTile(new Protobuf(new Uint8Array(res.data)));
          const out: TileFeature[] = [];
          for (const name of layers) {
            const lyr = vt.layers[name];
            if (!lyr) continue;
            for (let i = 0; i < lyr.length; i++) {
              const f = lyr.feature(i);
              out.push({ layer: name, props: f.properties as Record<string, unknown>, geometry: f.toGeoJSON(x, y, ZOOM).geometry });
            }
          }
          return out;
        }),
      );
    }
  // the shortest distance from the site to the edge of the nine tiles read
  const lonOf = (v: number) => (v / n) * 360 - 180;
  const latOf = (v: number) => Math.atan(Math.sinh(Math.PI * (1 - (2 * v) / n))) / RAD;
  const radiusKm = Math.min(km(site, [lonOf(tx - 1), site[1]]), km(site, [lonOf(tx + 2), site[1]]), km(site, [site[0], latOf(ty + 2)]), km(site, [site[0], latOf(ty - 1)]));
  return { feats: (await Promise.all(jobs)).flat(), radiusKm };
}

const polysOf = (g: GeoJSON.Geometry): number[][][][] => (g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : []);
const linesOf = (g: GeoJSON.Geometry): number[][][] => (g.type === "LineString" ? [g.coordinates] : g.type === "MultiLineString" ? g.coordinates : []);

export interface NearArea {
  src: "n2k" | "padus";
  name: string;
  kind: string | null;
  id: string | null;
  gap: string | null;
  /** 0 when the site is inside */
  km: number;
}
export interface ProtectedSearch {
  areas: NearArea[];
  /** share of the circle's sample points inside any area, 0..1 */
  share: number;
  points: number;
}

/** Protected areas within CONSTRAINT_RADIUS_KM (inside first, then by distance to the outline)
 *  and the share of that circle they cover (points on a SHARE_STEP_KM grid, computed). */
export async function protectedAround(url: string, site: LonLat): Promise<ProtectedSearch> {
  const { feats } = await aroundSite(url, ["protected"], site);
  const byKey = new Map<string, NearArea>();
  const polys: number[][][][] = [];
  for (const f of feats) {
    const p = polysOf(f.geometry);
    if (!p.length) continue;
    polys.push(...p);
    const inside = inGeoJsonPolygons(site, p);
    let d = inside ? 0 : Infinity;
    if (!inside) for (const poly of p) for (const ring of poly) d = Math.min(d, nearestOnFlat(site, ring.flat()).d);
    if (d > CONSTRAINT_RADIUS_KM) continue;
    const pr = f.props;
    const key = `${pr.src}|${pr.id ?? pr.name}`;
    const prev = byKey.get(key);
    if (!prev || d < prev.km)
      byKey.set(key, { src: pr.src === "padus" ? "padus" : "n2k", name: String(pr.name ?? "unnamed"), kind: (pr.kind as string) ?? null, id: (pr.id as string) ?? null, gap: (pr.gap as string) ?? null, km: d });
  }
  // the share: sample points on a grid inside the circle
  const kx = Math.cos(site[1] * RAD) * 111.32;
  const steps = Math.floor(CONSTRAINT_RADIUS_KM / SHARE_STEP_KM);
  let points = 0;
  let hits = 0;
  for (let i = -steps; i <= steps; i++)
    for (let j = -steps; j <= steps; j++) {
      const p: LonLat = [site[0] + (i * SHARE_STEP_KM) / kx, site[1] + (j * SHARE_STEP_KM) / 110.57];
      if (km(site, p) > CONSTRAINT_RADIUS_KM) continue;
      points++;
      if (polys.length && inGeoJsonPolygons(p, polys)) hits++;
    }
  return { areas: [...byKey.values()].sort((a, b) => a.km - b.km), share: points ? hits / points : 0, points };
}

export interface NearWay {
  km: number;
  cls: string;
  name: string | null;
}
/** The nearest major road and standard-gauge railway within the tiles read (null when none
 *  lies within radiusKm, the distance to the edge of the tiles). */
export async function roadsAround(url: string, site: LonLat): Promise<{ road: NearWay | null; rail: NearWay | null; radiusKm: number }> {
  const { feats, radiusKm } = await aroundSite(url, ["roads", "rail"], site);
  let road: NearWay | null = null;
  let rail: NearWay | null = null;
  for (const f of feats)
    for (const line of linesOf(f.geometry)) {
      const d = nearestOnFlat(site, line.flat()).d;
      if (d > radiusKm) continue;
      const way = { km: d, cls: String(f.props.class ?? ""), name: (f.props.name as string) ?? null };
      if (f.layer === "rail") {
        if (!rail || d < rail.km) rail = way;
      } else if (!road || d < road.km) road = way;
    }
  return { road, rail, radiusKm };
}
