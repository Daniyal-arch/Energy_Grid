// The 24-hour replay: market clock, the sun and night shadow, key moments, one slot as Power.

import type { RGB } from "../lib/theme";
import type { DaySeries, Highlight, Power } from "./types";

const MARKET_CLOCK = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Berlin",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});
export const marketTime = (iso: string) => MARKET_CLOCK.format(new Date(iso));
export const utc = (iso: string) => `${iso.slice(11, 16)} UTC`;
export const dayLabel = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

export const DAY_SECONDS = 36; // the whole day plays in this many seconds
export const TOWER_M_PER_MW = 14; // 1 GW of generation stands 14 km tall
export const TOWER_RADIUS_M = 58_000;
export const TOWER_LABEL_MW = 8000; // towers from this total carry a "DE 61 GW" label
export const CAPTION_SLOTS = 10; // a caption stays for 2.5 h of the day
export const NIGHT_BOUNDS: [number, number, number, number] = [-180, -85, 180, 85];

/** Title and sentence for a key moment; every number is the build script's. */
export function captionText(h: Highlight, name: (iso?: string) => string): { title: string; text: string; color: RGB } {
  switch (h.kind) {
    case "load_min":
      return { title: "Night low", text: `Europe uses the least power of the day: ${h.gw} GW.`, color: [154, 167, 189] };
    case "wind_peak":
      return { title: "Wind peak", text: `EU wind turbines deliver ${h.gw} GW.`, color: [72, 222, 184] };
    case "flow_max":
      return { title: "Biggest flow", text: `${name(h.from)} sends ${h.gw} GW to ${name(h.to)}.`, color: [120, 222, 255] };
    case "price_low":
      return {
        title: (h.eur ?? 0) < 0 ? "Negative price" : "Cheapest power",
        text: `${h.zone === h.country ? name(h.country) : h.zone} pays ${h.eur} €/MWh.`,
        color: [22, 170, 160],
      };
    case "solar_peak":
      return { title: "Solar peak", text: `EU solar reaches ${h.gw} GW, ${h.pct} % of all generation.`, color: [255, 214, 72] };
    case "greenest":
      return { title: "Greenest grid", text: `${name(h.country)}: ${h.pct} % of its power is renewable.`, color: [72, 222, 184] };
    case "price_high":
      return {
        title: "Most expensive",
        text: `${h.zone === h.country ? name(h.country) : h.zone} pays ${h.eur} €/MWh.`,
        color: [240, 110, 80],
      };
    case "load_max":
      return { title: "Demand peak", text: `Europe needs ${h.gw} GW.`, color: [236, 240, 246] };
    case "gas_peak":
      return { title: "Gas peak", text: `EU gas plants deliver ${h.gw} GW.`, color: [255, 128, 72] };
    default:
      return { title: h.kind, text: "", color: [200, 200, 200] };
  }
}

/** Sun altitude (degrees) at a place and moment: NOAA's solar position approximation. */
export function sunAltitude(lon: number, lat: number, when: Date, decl: number, eqMin: number): number {
  const minutes = when.getUTCHours() * 60 + when.getUTCMinutes() + when.getUTCSeconds() / 60;
  const hourAngle = ((minutes + eqMin + 4 * lon) / 4 - 180) * (Math.PI / 180);
  const phi = (lat * Math.PI) / 180;
  const sinAlt = Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(hourAngle);
  return (Math.asin(Math.max(-1, Math.min(1, sinAlt))) * 180) / Math.PI;
}

/** Solar declination (rad) and equation of time (min) for a moment (NOAA). */
export function sunState(when: Date): { decl: number; eqMin: number } {
  const start = Date.UTC(when.getUTCFullYear(), 0, 1);
  const doy = Math.floor((when.getTime() - start) / 86_400_000);
  const g = ((2 * Math.PI) / 365) * (doy + (when.getUTCHours() - 12) / 24);
  const decl =
    0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) +
    0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const eqMin =
    229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  return { decl, eqMin };
}

/** Sun altitude over Central Europe (10 E, 50 N), the reference for lighting and the sun arc. */
export const centralSun = (when: Date) => {
  const { decl, eqMin } = sunState(when);
  return sunAltitude(10, 50, when, decl, eqMin);
};

/** Night shadow over the world at a moment, one pixel per lng/lat cell (equirectangular). */
export function nightImage(when: Date): HTMLCanvasElement {
  const { decl, eqMin } = sunState(when);
  const W = 240;
  const H = 114;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(W, H);
  const [west, south, east, north] = NIGHT_BOUNDS;
  for (let row = 0; row < H; row++) {
    const lat = north + ((south - north) * (row + 0.5)) / H;
    for (let col = 0; col < W; col++) {
      const lon = west + ((east - west) * (col + 0.5)) / W;
      const alt = sunAltitude(lon, lat, when, decl, eqMin);
      // full night below -12 deg (nautical dusk), soft edge through twilight
      const k = Math.max(0, Math.min(1, (2 - alt) / 14));
      const i = (row * W + col) * 4;
      img.data[i] = 2;
      img.data[i + 1] = 5;
      img.data[i + 2] = 18;
      img.data[i + 3] = Math.round(175 * k * k * (3 - 2 * k));
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

/** One slot of a day series in the shape of the snapshot's Power. */
export function dayPower(series: DaySeries | null | undefined, k: number, ts: string): Power | undefined {
  const load = series?.load[k];
  if (!series || load == null) return undefined;
  const generation_mw: Record<string, number> = {};
  for (const [g, col] of Object.entries(series.generation)) if (col[k] != null) generation_mw[g] = col[k] as number;
  return { ts, load_mw: load, renewable_share_of_generation: series.renewable_share[k] ?? null, generation_mw, sum_of: series.sum_of };
}
