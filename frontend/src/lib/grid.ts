// Transmission-grid layer data. Loads the OSM 380/220 kV backbone GeoJSON and
// prepares it for an animated TripsLayer (flowing light along the lines): each
// line gets cumulative-distance "timestamps" + a random offset so energy flows
// along the network desynchronised, like a living grid.

import type { GridExchangeRow } from "./api";
import { flowDistances } from "./flowLayers";

const M_LAT = 111320;
const mLon = (lat: number) => M_LAT * Math.cos((lat * Math.PI) / 180);
const OFFSET_SPREAD = 240_000; // metres — stagger flow start per line

export interface GridSub {
  position: [number, number];
  voltage: number;
  name: string | null;
}
export interface GridData {
  subs: GridSub[];
}

export interface GridFlowPath {
  id: string;
  voltage: number;
  cables: number;
  seed: number;
  length_m: number;
  path: [number, number][];
  /** signed Mercator distance per vertex (FlowPathLayer); the sign sets dot direction */
  flow: number[];
  /** 0..1: how well the corridor lines up with the bulk-transfer direction */
  alignment: number;
}

// Per-line MW is not published for the German grid, so the dot direction shows
// the typical bulk transfer instead: out of the wind-heavy north and east toward
// the load centres in the south and west. Higher potential = further upstream.
const transferPotential = ([lon, lat]: [number, number]) => lat + 0.35 * (lon - 10.5);

// |cos| between a corridor's chord and the potential gradient (in km-like
// coordinates). Corridors running across the gradient get calmer dots, so
// near-arbitrary directions there don't read as head-on collisions.
function transferAlignment(path: [number, number][]): number {
  const a = path[0];
  const b = path[path.length - 1];
  const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180);
  const cx = (b[0] - a[0]) * k;
  const cy = b[1] - a[1];
  const gx = 0.35 / k;
  const gy = 1;
  const len = Math.hypot(cx, cy) * Math.hypot(gx, gy);
  return len > 0 ? Math.abs(cx * gx + cy * gy) / len : 0;
}

// backbone lines render via MVT tiles (frontend/scripts/tile-grid.mjs +
// MVTLayer in MapView.tsx) — substations are loaded from their own small
// GeoJSON (grid_substations.geojson, split out of grid_transmission.geojson
// so the client never has to fetch the full line network just for points).
export async function loadGrid(url: string): Promise<GridData> {
  const fc = await fetch(url).then((r) => r.json());
  const subs: GridSub[] = [];
  for (const f of fc.features as Array<{
    geometry: { coordinates: unknown };
    properties: { kind: string; voltage?: number; name?: string | null };
  }>) {
    const p = f.properties;
    if (p.kind === "substation") {
      subs.push({
        position: f.geometry.coordinates as [number, number],
        voltage: p.voltage || 0,
        name: p.name ?? null,
      });
    }
  }
  return { subs };
}

// merged 220/380 kV substation-to-substation corridors (scripts/build-power-flow-paths.mjs)
export async function loadGridFlowPaths(url = "/data/power_flow_paths.json"): Promise<GridFlowPath[]> {
  const data = await fetch(url).then((r) => r.json() as Promise<{ lines: Omit<GridFlowPath, "flow">[] }>);
  return data.lines
    .filter((line) => line.path.length >= 2)
    .map((line) => {
      const start = transferPotential(line.path[0]);
      const end = transferPotential(line.path[line.path.length - 1]);
      return {
        ...line,
        flow: flowDistances(line.path, end > start, line.seed % 1_000_000),
        alignment: transferAlignment(line.path),
      };
    });
}

// Same blue family across all three tiers (not a separate gray), descending in
// saturation as voltage steps down: 380 kV = brightest electric cyan, 220 kV = a
// more saturated mid blue, 110 kV = a paler, lighter blue — still clearly part of
// the backbone palette, not a dim slate that reads as "off"/washed out.
export const voltColor = (v: number): [number, number, number] =>
  v >= 380000 ? [130, 226, 255] : v >= 220000 ? [86, 150, 216] : [150, 188, 222];

// per-tier visibility toggle (Grid dropdown) — independent of the backbone/planned
// on-off switch, so you can e.g. show only 380 kV without the 110 kV clutter.
export interface VoltageTiers {
  v380: boolean;
  v220: boolean;
  v110: boolean;
}
export const ALL_VOLTAGES: VoltageTiers = { v380: true, v220: true, v110: true };
// startup default — 110 kV is ~5,400 substations nationwide (vs. ~580 for 380/220 kV
// combined); shown blanket-on at country zoom it floods the screen as a solid gray
// mass and visually buries the actual backbone underneath it. Off by default; the
// user can switch it on (and it self-thins once zoomed into a region — see
// MapView's pulseSubs/grid-subs zoom gating).
export const DEFAULT_VOLTAGES: VoltageTiers = { v380: true, v220: true, v110: false };
export const voltageAllowed = (v: number, t: VoltageTiers): boolean =>
  v >= 380000 ? t.v380 : v >= 220000 ? t.v220 : t.v110;

// a clicked grid element (for the info panel)
export type GridPick =
  | { kind: "corridor"; seg: PlannedSeg }
  | { kind: "substation"; sub: GridSub }
  | { kind: "exchange"; flow: GridExchangeRow };

// ── Planned transmission corridors (netzausbau BBPlG + EnLAG) with construction phase ──
export type Phase = "construction" | "operational" | "approval" | "planned";

export interface PlannedSeg {
  path: [number, number][];
  phase: Phase;
  status: string;
  name: string;
  number: string;
  technik: string;
  spannung: string;
  timestamps: number[];
}

const phaseOf = (status: string): Phase => {
  if (status.includes("genehmigt oder im Bau")) return "construction";
  if (status.includes("in Betrieb") || status.includes("fertiggestellt")) return "operational";
  if (status.includes("Planfeststellung") || status.includes("Raumvertr") || status.includes("Bundesfach"))
    return "approval";
  return "planned";
};

// amber = actively building, green = done, blue = in approval, slate = early
export const PHASE_COLOR: Record<Phase, [number, number, number]> = {
  construction: [233, 150, 58],
  operational: [88, 182, 140],
  approval: [86, 158, 210],
  planned: [120, 128, 150],
};

export async function loadPlanned(url: string): Promise<{ segs: PlannedSeg[]; maxTime: number }> {
  const fc = await fetch(url).then((r) => r.json());
  const segs: PlannedSeg[] = [];
  let maxTime = 0;
  for (const f of fc.features as Array<{
    geometry: { type: string; coordinates: unknown };
    properties: { Vorhabenst?: string; Vorhaben?: string; Vorhabennu?: string; Technik?: string; Spannung?: string };
  }>) {
    if (!f.geometry) continue;
    const pr = f.properties;
    const status = pr.Vorhabenst || "";
    const phase = phaseOf(status);
    const meta = {
      status,
      phase,
      name: pr.Vorhaben || "",
      number: pr.Vorhabennu || "",
      technik: pr.Technik || "",
      spannung: pr.Spannung || "",
    };
    const g = f.geometry;
    const lines = (g.type === "MultiLineString" ? g.coordinates : [g.coordinates]) as [number, number][][];
    for (const path of lines) {
      if (!path || path.length < 2) continue;
      const ts: number[] = [];
      let d = Math.random() * OFFSET_SPREAD;
      ts.push(d);
      for (let i = 1; i < path.length; i++) {
        const a = path[i - 1];
        const b = path[i];
        const lat = (a[1] + b[1]) / 2;
        d += Math.hypot((b[0] - a[0]) * mLon(lat), (b[1] - a[1]) * M_LAT);
        ts.push(d);
      }
      if (d > maxTime) maxTime = d;
      segs.push({ path, timestamps: ts, ...meta });
    }
  }
  return { segs, maxTime };
}
