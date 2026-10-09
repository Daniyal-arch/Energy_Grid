// Geometry helpers and map placements shared by the map and the panels.

import type { Country, Hex, Unit } from "./types";

export const pairs = (flat: number[]): [number, number][] => {
  const p: [number, number][] = [];
  for (let k = 0; k < flat.length; k += 2) p.push([flat[k], flat[k + 1]]);
  return p;
};

export function bbox(c: Country): [[number, number], [number, number]] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  for (const rings of c.polygons)
    for (let k = 0; k < rings[0].length; k += 2) {
      x0 = Math.min(x0, rings[0][k]);
      x1 = Math.max(x1, rings[0][k]);
      y0 = Math.min(y0, rings[0][k + 1]);
      y1 = Math.max(y1, rings[0][k + 1]);
    }
  return [
    [x0, y0],
    [x1, y1],
  ];
}

export const angularDistance = (a: [number, number], b: [number, number]) => {
  const r = Math.PI / 180;
  const c = Math.sin(a[1] * r) * Math.sin(b[1] * r) + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.cos((a[0] - b[0]) * r);
  return Math.acos(Math.max(-1, Math.min(1, c))) / r;
};

/** Unit vector of a lon/lat point: a dot product with the camera's says which side faces it. */
export function unitVector(lon: number, lat: number): [number, number, number] {
  const r = Math.PI / 180;
  const c = Math.cos(lat * r);
  return [c * Math.cos(lon * r), c * Math.sin(lon * r), Math.sin(lat * r)];
}

// Europe faces the camera from here; beyond this angle its layers are on the far side
export const EUROPE_CENTRE: [number, number] = [12, 50];
export const FAR_SIDE_DEG = 78;

// where each country's flow arcs start and end (inland points, not capitals)
export const ANCHOR: Record<string, [number, number]> = {
  AL: [20.0, 41.1], AT: [14.3, 47.6], BA: [17.8, 44.2], BE: [4.6, 50.6], BG: [25.2, 42.7],
  CH: [8.2, 46.8], CZ: [15.3, 49.8], DE: [10.4, 51.1], DK: [9.3, 56.0], EE: [25.5, 58.7],
  ES: [-3.7, 40.3], FI: [26.0, 62.5], FR: [2.4, 46.6], GB: [-1.8, 52.8], GR: [22.0, 39.5],
  HR: [15.9, 45.6], HU: [19.4, 47.2], IE: [-8.0, 53.2], IT: [12.3, 43.0], LT: [23.9, 55.3],
  LU: [6.1, 49.7], LV: [24.9, 56.9], ME: [19.3, 42.8], MD: [28.5, 47.2], MK: [21.7, 41.6],
  NL: [5.6, 52.2], NO: [9.5, 61.0], PL: [19.2, 52.0], PT: [-8.1, 39.6], RO: [24.9, 45.9],
  RS: [20.8, 44.1], SE: [15.8, 61.0], SI: [14.8, 46.1], SK: [19.5, 48.7], UA: [31.0, 49.0],
  XK: [20.9, 42.6],
}; // prettier-ignore

// too small for a name at continent zoom
export const SMALL = new Set(["LU", "ME", "MK", "XK", "AL", "BA", "SI", "MD", "BE", "NL", "DK", "EE", "LV", "LT", "CH"]);

export const MOBILE_QUERY = "(max-width: 767px)";
export const isNarrow = () => window.matchMedia(MOBILE_QUERY).matches;

// "beams & fields" style: big plants as light beams, the rest summed into hexagons
export const BEAM_MIN_MW = 200;
export const HEX_KM = 12; // hexagon circumradius

/** Sum units into flat-top hexagons (circumradius HEX_KM) in a local km grid. */
export function hexBins(units: Unit[]): Hex[] {
  if (!units.length) return [];
  const lat0 = units.reduce((a, u) => a + u[3], 0) / units.length;
  const kx = 111.32 * Math.cos((lat0 * Math.PI) / 180);
  const ky = 110.57;
  const bins = new Map<string, Hex & { q: number; r: number }>();
  for (const u of units) {
    const x = u[2] * kx;
    const y = u[3] * ky;
    // axial coordinates of a flat-top hex grid, then cube rounding
    const qf = ((2 / 3) * x) / HEX_KM;
    const rf = ((-1 / 3) * x + (Math.sqrt(3) / 3) * y) / HEX_KM;
    const sf = -qf - rf;
    let q = Math.round(qf);
    let rr = Math.round(rf);
    const sr = Math.round(sf);
    const dq = Math.abs(q - qf);
    const dr = Math.abs(rr - rf);
    const ds = Math.abs(sr - sf);
    if (dq > dr && dq > ds) q = -rr - sr;
    else if (dr > ds) rr = -q - sr;
    const key = `${q},${rr}`;
    let bin = bins.get(key);
    if (!bin) {
      const cx = HEX_KM * 1.5 * q;
      const cy = HEX_KM * Math.sqrt(3) * (rr + q / 2);
      bin = { q, r: rr, position: [cx / kx, cy / ky], mw: 0, units: 0, mix: new Map(), dominant: 0 };
      bins.set(key, bin);
    }
    bin.mw += u[1];
    bin.units += 1;
    bin.mix.set(u[0], (bin.mix.get(u[0]) ?? 0) + u[1]);
  }
  const out = [...bins.values()];
  for (const b of out) b.dominant = [...b.mix.entries()].sort((a, c) => c[1] - a[1])[0][0];
  return out;
}
