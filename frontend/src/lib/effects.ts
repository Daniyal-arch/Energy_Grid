// Per-frame particle generators for the "living power system" animations. All are
// pure math: given the in-view sites, the animation phase (0..1), and helpers for
// object size + ground elevation, they return billboard particles for a
// ScatterplotLayer. Driven only at close zoom for a bounded particle count.

import type { Site } from "./api";

export interface Particle {
  position: [number, number, number];
  radius: number;
  color: [number, number, number, number];
}

const M_PER_DEG_LAT = 111320;
const degLon = (lat: number) => M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);

type SizeFn = (capacityMw: number) => number;
type GroundFn = (s: Site) => number;

export interface PlumeOpts {
  baseFactor: number; // height of the stack/tower top, in object-size units
  height: number; // how far the plume rises, in object-size units
  spread: number; // lateral drift as it rises
  color: [number, number, number];
  count: number;
}

/** Rising puffs from a stack or cooling tower (smoke / steam). */
export function plume(sites: Site[], phase: number, size: SizeFn, gz: GroundFn, o: PlumeOpts): Particle[] {
  const out: Particle[] = [];
  for (const s of sites) {
    const B = size(s.capacity_mw);
    const baseZ = gz(s) + B * o.baseFactor;
    const dLon = degLon(s.lat);
    for (let i = 0; i < o.count; i++) {
      const t = (phase + i / o.count) % 1;
      const ang = i * 2.39996; // golden angle → even scatter
      const drift = t * B * o.spread;
      out.push({
        position: [
          s.lon + (Math.cos(ang) * drift) / dLon,
          s.lat + (Math.sin(ang) * drift) / M_PER_DEG_LAT,
          baseZ + t * B * o.height,
        ],
        radius: B * (0.05 + t * 0.17),
        color: [o.color[0], o.color[1], o.color[2], Math.round((1 - t) * 130)],
      });
    }
  }
  return out;
}

/** A bright reflection sweeping across a (solar) array. */
export function glint(sites: Site[], phase: number, size: SizeFn, gz: GroundFn): Particle[] {
  const out: Particle[] = [];
  const u = (phase * 1.7) % 1; // sweep position
  const fade = Math.sin(u * Math.PI); // brightest mid-sweep
  for (const s of sites) {
    const B = size(s.capacity_mw);
    const off = (u - 0.5) * B * 0.85;
    const dLon = degLon(s.lat);
    out.push({
      position: [s.lon + off / dLon, s.lat + (off * 0.4) / M_PER_DEG_LAT, gz(s) + B * 0.13],
      radius: B * 0.14,
      color: [255, 248, 214, Math.round(205 * fade)],
    });
  }
  return out;
}

/** A glow pad breathing under a (battery) site. */
export function pulse(sites: Site[], phase: number, size: SizeFn, gz: GroundFn, color: [number, number, number]): Particle[] {
  const k = 0.5 + 0.5 * Math.sin(phase * 2 * Math.PI);
  return sites.map((s) => {
    const B = size(s.capacity_mw);
    return {
      position: [s.lon, s.lat, gz(s) + B * 0.04] as [number, number, number],
      radius: B * (0.45 + 0.3 * k),
      color: [color[0], color[1], color[2], Math.round(35 + 75 * k)] as [number, number, number, number],
    };
  });
}
