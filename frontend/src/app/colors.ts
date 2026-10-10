// Colour scales and fixed colours of the map.

import type { RGB } from "../lib/theme";
import type { ColorStops } from "./types";

export const NO_DATA: RGB = [30, 31, 36];
export const PLAIN_LAND: RGB = [34, 37, 46];
export const BORDER: [number, number, number, number] = [214, 206, 196, 70];
export const COAST: [number, number, number, number] = [150, 160, 176, 90];
export const HVDC: RGB = [178, 146, 255];
export const FLOW: RGB = [120, 222, 255];
export const GAS: RGB = [255, 150, 92]; // LNG terminals and storages (gas = orange, as gas plants)
export const GAS_PIPE: RGB = [226, 206, 160]; // pale sand, dashed, so pipelines never read as power lines
export const SUBSTATION: RGB = [226, 232, 240];
export const MULTI_ZONE: RGB = [44, 47, 58]; // countries with several price zones
export const TR_NO_DATA: RGB = [40, 43, 52]; // no value for that country and year

export const dim = (c: RGB, k: number): RGB => [c[0] * k, c[1] * k, c[2] * k].map(Math.round) as RGB;
export const lift = (c: RGB, k: number): RGB => c.map((v) => Math.round(v + (255 - v) * k)) as RGB;

/** Linear interpolation along colour stops; below the first or above the last stop clamps. */
export function stopColor(stops: ColorStops, v: number | null | undefined): RGB | null {
  if (v == null || Number.isNaN(v)) return null;
  if (v <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    const [v1, c1] = stops[i];
    const [v0, c0] = stops[i - 1];
    if (v <= v1) {
      const t = (v - v0) / (v1 - v0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * t)) as RGB;
    }
  }
  return stops[stops.length - 1][1];
}

export const gradientCss = (stops: ColorStops) => {
  const a = stops[0][0];
  const b = stops[stops.length - 1][0];
  return `linear-gradient(90deg, ${stops.map(([v, c]) => `rgb(${c.join(",")}) ${((v - a) / (b - a || 1)) * 100}%`).join(", ")})`;
};

// renewable share of generation, 0 -> 100 %: ember -> slate -> deep teal
export const SHARE_STOPS: ColorStops = [
  [0, [70, 38, 40]],
  [35, [58, 48, 58]],
  [65, [36, 58, 70]],
  [100, [22, 84, 86]],
];
// day-ahead price, EUR/MWh: cheap teal -> slate -> expensive ember
export const PRICE_STOPS: ColorStops = [
  [0, [22, 84, 86]],
  [80, [40, 62, 76]],
  [150, [86, 50, 58]],
  [250, [140, 54, 40]],
];
// the Prices layer: below zero ice cyan, cheap green, dear red, extreme magenta
export const PRICE_GLOW_STOPS: ColorStops = [
  [-50, [90, 235, 255]],
  [0, [70, 225, 170]],
  [60, [225, 225, 95]],
  [120, [255, 160, 60]],
  [200, [255, 75, 85]],
  [350, [235, 70, 220]],
];
export const PRICE_GLOW_TICKS = ["−50", "0", "60", "120", "200", "350 €/MWh"];

// generating capacity offline (GW): none stays calm, a lot glows hot
export const OFFLINE_STOPS: ColorStops = [
  [0, [34, 38, 48]],
  [1, [74, 52, 56]],
  [5, [146, 64, 54]],
  [15, [214, 92, 60]],
  [30, [246, 150, 80]],
];

// Europe's transmission lines (PyPSA): copper by voltage, dim so countries, plants and flows read first
export const VOLTAGE_BANDS: Array<{ min: number; label: string; color: RGB; width: number; alpha: number }> = [
  { min: 380, label: "380–750 kV", color: [236, 178, 120], width: 0.8, alpha: 125 },
  { min: 275, label: "275–330 kV", color: [206, 132, 84], width: 0.7, alpha: 95 },
  { min: 0, label: "220–254 kV", color: [160, 100, 70], width: 0.6, alpha: 75 },
];
export const band = (kv: number) => VOLTAGE_BANDS.find((b) => kv >= b.min)!;

export const CABLE_STYLE: Record<string, { color: [number, number, number, number]; width: number; label: string }> = {
  hvdc: { color: [178, 146, 255, 230], width: 1.8, label: "HVDC" },
  hv: { color: [110, 190, 255, 210], width: 1.5, label: "AC, 110 kV and more" },
  field: { color: [72, 222, 184, 150], width: 0.9, label: "below 110 kV (mostly offshore wind)" },
  other: { color: [150, 160, 176, 130], width: 0.8, label: "voltage not mapped" },
};
