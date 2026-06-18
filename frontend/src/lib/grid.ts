// Transmission-grid layer data. Loads the OSM 380/220 kV backbone GeoJSON and
// prepares it for an animated TripsLayer (flowing light along the lines): each
// line gets cumulative-distance "timestamps" + a random offset so energy flows
// along the network desynchronised, like a living grid.

const M_LAT = 111320;
const mLon = (lat: number) => M_LAT * Math.cos((lat * Math.PI) / 180);
const OFFSET_SPREAD = 240_000; // metres — stagger flow start per line

export interface GridLine {
  path: [number, number][];
  timestamps: number[];
  voltage: number;
}
export interface GridSub {
  position: [number, number];
  voltage: number;
}
export interface GridData {
  lines: GridLine[];
  subs: GridSub[];
  maxTime: number;
}

export async function loadGrid(url: string): Promise<GridData> {
  const fc = await fetch(url).then((r) => r.json());
  const lines: GridLine[] = [];
  const subs: GridSub[] = [];
  let maxTime = 0;
  for (const f of fc.features as Array<{
    geometry: { coordinates: unknown };
    properties: { kind: string; voltage?: number };
  }>) {
    const p = f.properties;
    if (p.kind === "line") {
      const path = f.geometry.coordinates as [number, number][];
      if (path.length < 2) continue;
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
      lines.push({ path, timestamps: ts, voltage: p.voltage || 0 });
    } else if (p.kind === "substation") {
      subs.push({ position: f.geometry.coordinates as [number, number], voltage: p.voltage || 0 });
    }
  }
  return { lines, subs, maxTime };
}

// 380 kV = bright electric cyan; 220 kV = cooler blue
export const voltColor = (v: number): [number, number, number] =>
  v >= 380000 ? [130, 226, 255] : [86, 150, 216];

// ── Planned transmission corridors (netzausbau BBPlG) with construction phase ──
export type Phase = "construction" | "operational" | "approval" | "planned";

export interface PlannedSeg {
  path: [number, number][];
  phase: Phase;
  status: string;
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
  for (const f of fc.features as Array<{ geometry: { type: string; coordinates: unknown }; properties: { Vorhabenst?: string } }>) {
    if (!f.geometry) continue;
    const status = f.properties.Vorhabenst || "";
    const phase = phaseOf(status);
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
      segs.push({ path, phase, status, timestamps: ts });
    }
  }
  return { segs, maxTime };
}
