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
