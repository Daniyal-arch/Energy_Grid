// Power scene styling: palette, a decluttered basemap, the Germany outline,
// orientation labels and the cross-border link geometry. Display-only; every
// number shown comes from the backend or the bundled source files.

import maplibregl from "maplibre-gl";

import type { GridExchangeRow, GridSnapshotLatest, Site } from "./api";
import { curvedPath, flowDistances } from "./flowLayers";
import type { RGB, Technology } from "./theme";

// Voltage is ordinal, so one hue stepped by lightness: brighter = higher voltage.
// Validated as an ordinal ramp against POWER_SURFACE (dataviz validate_palette).
export const POWER_LINE_COLOR: { v380: RGB; v220: RGB; v110: RGB } = {
  v380: [143, 216, 255],
  v220: [75, 147, 224],
  v110: [47, 95, 158],
};

export const powerLineColor = (voltage: number): RGB =>
  voltage >= 380_000 ? POWER_LINE_COLOR.v380 : voltage >= 220_000 ? POWER_LINE_COLOR.v220 : POWER_LINE_COLOR.v110;

// the basemap underneath the scene (outside Germany) and Germany's own land tone
export const POWER_SURFACE = "#07090e";
export const POWER_LAND: RGB = [17, 23, 33];

// Everything except the land/water fills and national borders is hidden, so the
// grid is the only line work on the map.
const HIDE_ID = /^(tunnel_|road_|bridge_|rail|aeroway|building|waterway|boundary_county|boundary_state|boundary_country_outline|landuse_residential|park_)/;

const POWER_PAINT: Array<[string, string, unknown]> = [
  ["background", "background-color", POWER_SURFACE],
  ["landcover", "fill-color", POWER_SURFACE],
  ["landuse", "fill-color", POWER_SURFACE],
  ["water", "fill-color", "#04060a"],
  ["boundary_country_inner", "line-color", "rgba(120,138,162,0.38)"],
];

interface SavedBasemap {
  visibility: Map<string, unknown>;
  paint: Map<string, [string, string, unknown]>;
}
const savedBasemaps = new WeakMap<maplibregl.Map, SavedBasemap>();

/**
 * Idempotent: call it whenever the style changes. It only needs the style JSON
 * (not tiles), and re-scans each time, so layers the app adds later (hillshade
 * in the load handler) are caught too. Everything it changes is restored on
 * `on = false`.
 */
export function setPowerBasemap(map: maplibregl.Map, on: boolean): void {
  let saved = savedBasemaps.get(map);
  if (on) {
    if (!saved) {
      saved = { visibility: new Map(), paint: new Map() };
      savedBasemaps.set(map, saved);
    }
    for (const id of map.getLayersOrder()) {
      if (saved.visibility.has(id)) continue;
      const type = map.getLayer(id)?.type;
      if (type !== "symbol" && type !== "hillshade" && !HIDE_ID.test(id)) continue;
      saved.visibility.set(id, map.getLayoutProperty(id, "visibility"));
      map.setLayoutProperty(id, "visibility", "none");
    }
    for (const [id, prop, value] of POWER_PAINT) {
      const key = `${id}|${prop}`;
      if (saved.paint.has(key) || !map.getLayer(id)) continue;
      saved.paint.set(key, [id, prop, map.getPaintProperty(id, prop)]);
      map.setPaintProperty(id, prop, value);
    }
  } else if (saved) {
    savedBasemaps.delete(map);
    for (const [id, visibility] of saved.visibility) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", (visibility as string | undefined) ?? "visible");
    }
    for (const [id, prop, value] of saved.paint.values()) {
      if (map.getLayer(id)) map.setPaintProperty(id, prop, value);
    }
  }
}

type Ring = [number, number][];

/**
 * Germany's outline from the federal-state polygons: GISCO states share exact
 * vertices, so an edge used by only one state is on the national border or coast.
 */
export function outlineFromStates(fc: GeoJSON.FeatureCollection): Ring[] {
  const rings: Ring[] = [];
  for (const f of fc.features) {
    const g = f.geometry;
    if (g?.type === "Polygon") rings.push(...(g.coordinates as Ring[]));
    else if (g?.type === "MultiPolygon") for (const poly of g.coordinates as Ring[][]) rings.push(...poly);
  }
  const key = (p: [number, number]) => `${p[0].toFixed(6)},${p[1].toFixed(6)}`;
  const edgeKey = (a: [number, number], b: [number, number]) => {
    const ka = key(a);
    const kb = key(b);
    return ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
  };
  const uses = new Map<string, number>();
  for (const ring of rings)
    for (let i = 1; i < ring.length; i++) {
      const k = edgeKey(ring[i - 1], ring[i]);
      uses.set(k, (uses.get(k) ?? 0) + 1);
    }
  const paths: Ring[] = [];
  for (const ring of rings) {
    let run: Ring = [];
    for (let i = 1; i < ring.length; i++) {
      if (uses.get(edgeKey(ring[i - 1], ring[i])) === 1) {
        if (!run.length) run.push(ring[i - 1]);
        run.push(ring[i]);
      } else if (run.length) {
        paths.push(run);
        run = [];
      }
    }
    if (run.length) paths.push(run);
  }
  return paths;
}

// orientation only — a handful of load centres, like the reference maps' city callouts
export const POWER_CITIES: Array<{ name: string; position: [number, number] }> = [
  { name: "Hamburg", position: [9.99, 53.55] },
  { name: "Berlin", position: [13.4, 52.52] },
  { name: "Hannover", position: [9.73, 52.37] },
  { name: "Leipzig", position: [12.37, 51.34] },
  { name: "Köln", position: [6.96, 50.94] },
  { name: "Frankfurt", position: [8.68, 50.11] },
  { name: "Stuttgart", position: [9.18, 48.78] },
  { name: "München", position: [11.58, 48.14] },
];

// Cross-border links drawn as short curves from a German-side interconnector
// area to a label point in the neighbour zone (energy-charts reports one flow
// per neighbour, not per line). NO/SE are subsea DC links (NordLink, Baltic Cable).
const EXCHANGE_LINKS: Record<string, { de: [number, number]; ext: [number, number] }> = {
  Netherlands: { de: [7.2, 52.15], ext: [5.75, 52.35] },
  Belgium: { de: [6.45, 50.87], ext: [5.2, 50.55] },
  Luxembourg: { de: [6.8, 49.85], ext: [6.05, 49.55] },
  France: { de: [7.05, 49.3], ext: [5.95, 48.75] },
  Switzerland: { de: [8.2, 47.72], ext: [8.3, 47.08] },
  Austria: { de: [12.6, 48.25], ext: [13.95, 47.85] },
  "Czech Republic": { de: [12.35, 50.1], ext: [13.65, 49.85] },
  Poland: { de: [14.1, 52.55], ext: [15.65, 52.4] },
  Denmark: { de: [9.45, 54.55], ext: [9.3, 55.45] },
  Sweden: { de: [10.85, 53.97], ext: [13.2, 55.42] },
  Norway: { de: [9.25, 54.0], ext: [7.25, 55.25] },
};

export interface ExchangeFlowLine {
  row: GridExchangeRow;
  code: string;
  valueMw: number; // energy-charts cbpf sign: positive = import into DE
  path: [number, number][];
  flow: number[];
  label: [number, number];
  // label placement: on the far side of the curve's end, away from Germany
  anchor: maplibregl.PositionAnchor;
  offset: [number, number];
}

/** Flows below this are shown as idle (no dots, neutral colour, "0 MW"). */
export const IDLE_FLOW_MW = 20;

export function exchangeFlowLines(rows: GridExchangeRow[], codes: Record<string, string>): ExchangeFlowLine[] {
  const out: ExchangeFlowLine[] = [];
  for (const row of rows) {
    const link = EXCHANGE_LINKS[row.neighbor_zone];
    if (!link) continue;
    const valueMw = Number(row.value_mw) || 0;
    // path always runs neighbour -> DE; exports reverse the dot direction
    const path = curvedPath(link.ext, link.de, 0.16, 28);
    const k = Math.cos((link.ext[1] * Math.PI) / 180);
    let ox = (path[0][0] - path[1][0]) * k;
    let oy = path[0][1] - path[1][1];
    const len = Math.hypot(ox, oy) || 1;
    ox /= len;
    oy /= len;
    const vertical = oy > 0.4 ? "bottom" : oy < -0.4 ? "top" : "";
    const horizontal = ox > 0.4 ? "left" : ox < -0.4 ? "right" : "";
    out.push({
      row,
      code: codes[row.neighbor_zone] ?? row.neighbor_zone.slice(0, 2).toUpperCase(),
      valueMw,
      path,
      flow: flowDistances(path, valueMw < 0),
      label: link.ext,
      anchor: ((vertical && horizontal ? `${vertical}-${horizontal}` : vertical || horizontal) ||
        "center") as maplibregl.PositionAnchor,
      offset: [ox * 8, -oy * 8], // screen y grows downward
    });
  }
  return out;
}

// Whole-country view for the power scene, including the neighbour labels.
export const POWER_VIEW_BOUNDS: [[number, number], [number, number]] = [
  [5.0, 46.95],
  [15.9, 55.95],
];

export function formatFlowMw(valueMw: number): string {
  const v = Math.abs(valueMw);
  return v >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v)} MW`;
}

function labelElement(className: string, lines: Array<[string, string]>): HTMLElement {
  const el = document.createElement("div");
  el.className = `power-label ${className}`;
  for (const [cls, text] of lines) {
    const line = document.createElement("div");
    line.className = cls;
    line.textContent = text;
    el.appendChild(line);
  }
  return el;
}

/** DOM labels (crisp text, always above the WebGL glow); caller removes them. */
export function powerLabelMarkers(
  map: maplibregl.Map,
  cities: boolean,
  exchange: ExchangeFlowLine[],
  /** video framing: idle links keep their line but lose the label */
  compact = false,
): maplibregl.Marker[] {
  const markers: maplibregl.Marker[] = [];
  if (cities) {
    for (const city of POWER_CITIES) {
      const el = document.createElement("div");
      el.className = "power-label power-label-city";
      el.textContent = city.name;
      markers.push(
        new maplibregl.Marker({ element: el, anchor: "left", offset: [-3, 0] }).setLngLat(city.position).addTo(map),
      );
    }
  }
  for (const line of exchange) {
    const idle = Math.abs(line.valueMw) < IDLE_FLOW_MW;
    if (compact && idle) continue;
    const value = idle ? "0 MW" : `${line.valueMw >= 0 ? "import" : "export"} ${formatFlowMw(line.valueMw)}`;
    const el = labelElement("text-center", [
      ["power-label-code", line.code],
      ["power-label-value", value],
    ]);
    markers.push(
      new maplibregl.Marker({ element: el, anchor: line.anchor, offset: line.offset }).setLngLat(line.label).addTo(map),
    );
  }
  return markers;
}

// ── Power plants ────────────────────────────────────────────────────────────
// Four colour groups (validated all-pairs, CVD-safe, against the land tone and
// the 380 kV line colour). Storage shares "other" but is drawn as a ring.
export type PlantGroup = "fossil" | "wind" | "solar" | "other";

export const PLANT_GROUP: Record<Technology, PlantGroup> = {
  combustion: "fossil",
  wind: "wind",
  solar: "solar",
  biomass: "other",
  hydro: "other",
  geothermal: "other",
  storage: "other",
};

export const PLANT_COLOR: Record<PlantGroup, RGB> = {
  fossil: [255, 111, 89],
  wind: [63, 220, 160],
  solar: [255, 210, 63],
  other: [177, 140, 255],
};

export const PLANT_LABEL: Record<PlantGroup, string> = {
  fossil: "Fossil & thermal",
  wind: "Wind",
  solar: "Solar parks",
  other: "Bio, hydro, storage",
};

// cross-border links: one neutral colour; the labels say import/export and the
// dots show direction, which keeps hue free for the plant groups
export const EXCHANGE_COLOR: RGB = [233, 226, 208];

export interface PlantCluster {
  id: string;
  name: string;
  technology: Technology;
  group: PlantGroup;
  position: [number, number];
  capacity_mw: number;
  units: number;
  /** the site id when the cluster is a single unit (click opens its drawer) */
  siteId: string | null;
  // Site-shaped fields so the map's existing tooltip can describe a cluster
  status: "unknown";
  mastr_status: string;
}

/**
 * Operating units grouped per technology into cells of `cellDeg` (lon) — a
 * display aggregation so 43k small units read as regional glows instead of
 * confetti. cellDeg = 0 keeps every unit. Position is capacity-weighted.
 */
export function plantClusters(sites: Site[], cellDeg: number): PlantCluster[] {
  const cells = new Map<string, { sx: number; sy: number; mw: number; units: number; top: Site }>();
  for (const s of sites) {
    if (!s.technology || s.mastr_status !== "In Betrieb" || !(s.capacity_mw > 0)) continue;
    const key =
      cellDeg > 0
        ? `${s.technology}|${Math.floor(s.lon / cellDeg)}|${Math.floor(s.lat / (cellDeg * 0.65))}`
        : s.id;
    const c = cells.get(key);
    if (c) {
      c.sx += s.lon * s.capacity_mw;
      c.sy += s.lat * s.capacity_mw;
      c.mw += s.capacity_mw;
      c.units += 1;
      if (s.capacity_mw > c.top.capacity_mw) c.top = s;
    } else {
      cells.set(key, { sx: s.lon * s.capacity_mw, sy: s.lat * s.capacity_mw, mw: s.capacity_mw, units: 1, top: s });
    }
  }
  const out: PlantCluster[] = [];
  for (const [key, c] of cells) {
    const tech = c.top.technology as Technology;
    const group = PLANT_GROUP[tech];
    out.push({
      id: key,
      name: c.units === 1 ? c.top.name : `${PLANT_LABEL[group]} · ${c.units.toLocaleString("en-US")} units`,
      technology: tech,
      group,
      position: [c.sx / c.mw, c.sy / c.mw],
      capacity_mw: c.mw,
      units: c.units,
      siteId: c.units === 1 ? c.top.id : null,
      status: "unknown",
      mastr_status: "In Betrieb",
    });
  }
  // biggest first, so small glows draw on top and stay visible
  return out.sort((a, b) => b.capacity_mw - a.capacity_mw);
}

/** Disc radius in px: area ∝ capacity, capped so large clusters never bury the grid. */
export const plantRadius = (mw: number): number => Math.min(4.5, 1.0 + Math.sqrt(mw) * 0.14);

/**
 * Per zoom band: cell size (degrees of longitude, 0 = every unit) and the
 * smallest cluster shown per group. Zoomed out only regional-scale generation
 * shows (~300 symbols), so the grid stays the main read; detail appears as you
 * zoom in.
 */
export const PLANT_LOD: Array<{ cell: number; min: Record<PlantGroup, number> }> = [
  { cell: 0.4, min: { wind: 150, fossil: 150, solar: 20, other: 50 } },
  { cell: 0.1, min: { wind: 25, fossil: 20, solar: 5, other: 10 } },
  { cell: 0, min: { wind: 0, fossil: 1, solar: 1, other: 1 } },
];

export interface PlantFeeder {
  id: string;
  group: PlantGroup;
  capacity_mw: number;
  path: [number, number][];
  flow: number[];
}

/**
 * Short curves from large clusters to the nearest 220/380 kV substation, with
 * dots flowing plant -> grid. Connection points aren't in the data, so these are
 * explicitly approximate. Storage is left out (its direction flips with
 * charging, which isn't observed).
 */
export function plantFeeders(
  clusters: PlantCluster[],
  subs: Array<{ position: [number, number] }>,
  minMw = 150,
  maxKm = 60,
): PlantFeeder[] {
  const out: PlantFeeder[] = [];
  for (const c of clusters) {
    if (c.capacity_mw < minMw || c.technology === "storage") continue;
    const k = Math.cos((c.position[1] * Math.PI) / 180);
    let best: [number, number] | null = null;
    let bestD = Infinity;
    for (const s of subs) {
      const dx = (s.position[0] - c.position[0]) * k;
      const dy = s.position[1] - c.position[1];
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = s.position;
      }
    }
    const km = Math.sqrt(bestD) * 111.32;
    if (!best || km > maxKm || km < 1.5) continue;
    const path = curvedPath(c.position, best, 0.22, 16);
    out.push({ id: c.id, group: c.group, capacity_mw: c.capacity_mw, path, flow: flowDistances(path) });
  }
  return out;
}

/**
 * Share of current national generation per plant group (from /grid/latest
 * observations), used only to drive animation intensity — never displayed.
 * Null when there is no live data yet.
 */
export function plantActivity(latest: GridSnapshotLatest): Record<PlantGroup, number> | null {
  const v = (metric: string) => Math.max(0, Number(latest[metric]?.value) || 0);
  const fossil = v("gen_lignite") + v("gen_hard_coal") + v("gen_gas") + v("gen_oil");
  const other = v("gen_biomass") + v("gen_hydro") + v("gen_geothermal");
  const wind = v("gen_wind");
  const solar = v("gen_solar");
  const total = fossil + other + wind + solar + v("gen_waste") + v("gen_other");
  if (total <= 0) return null;
  return { fossil: fossil / total, wind: wind / total, solar: solar / total, other: other / total };
}
