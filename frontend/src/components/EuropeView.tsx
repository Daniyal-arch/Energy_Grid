import { AmbientLight, LightingEffect, _SunLight as SunLight, type PickingInfo } from "@deck.gl/core";
import { PathStyleExtension, type PathStyleExtensionProps } from "@deck.gl/extensions";
import { BitmapLayer, ColumnLayer, LineLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { FlowArrowLayer } from "../lib/flowArrowLayer";
import { FlowClock, curvedPath, flowDistances } from "../lib/flowLayers";
import { rgbCss, type RGB } from "../lib/theme";

// Europe's transmission grid, power plants and measured cross-border flows (the app's only view).
// Static layers: frontend/public/data/eu/{grid,plants,countries}.json from
// scripts/build_eu_grid.py; flows.json + stats.json from scripts/fetch_eu_snapshot.py.
// Countries are shaded by the renewable share of generation that Energy-Charts
// publishes. Click a country to focus it: its stats, outline and own flows. Only
// cross-border arcs move: they carry measured physical flows. Lines inside a country
// stay still because no public per-line flow data exists.

interface GridFile {
  lines: [number, number[]][];
  links: [number, number[]][];
  /** [kV, lon, lat, ISO] */
  substations: Substation[];
}
type Substation = [number, number, number, string];
/** [name, ISO, lon, lat, start year, capacity or null when the dataset only estimates it] */
type GasSite = [string, string, number, number, number | null, number | null];
/** focused-country unit: [group index, MW, lon, lat, name, year in operation] */
type Unit = [number, number, number, number, string, number | null];
interface GasFile {
  pipes: [number, number[]][];
  lng: GasSite[];
  storages: GasSite[];
}
interface ReferenceFile {
  fetched: string;
  capacity: Record<string, { year: string; gw: Record<string, number> }>;
  reservoirs: Record<string, { week: string; twh: number; year_ago_week: string | null; year_ago_twh: number | null }>;
}
interface PriceRow {
  country: string;
  ts: string;
  eur_mwh: number;
}
interface PlantsFile {
  groups: string[];
  plants: Plant[];
  /** per country and group: [units, MW] of the plants drawn (>= 20 MW, operating) */
  by_country: Record<string, Record<string, [number, number]>>;
}
interface Country {
  iso: string;
  name: string;
  label: [number, number];
  polygons: number[][][];
}
interface CountriesFile {
  countries: Country[];
  borders: number[][];
  coast: number[][];
}
interface FlowRow {
  a: string;
  b: string;
  mw: number;
  ts: string;
  /** 24 h of 15-min values (a -> b positive), for the replay */
  series?: (number | null)[];
}
interface FlowsFile {
  fetched: string;
  series_start?: string;
  series_step_s?: number;
  borders: FlowRow[];
}
interface Power {
  ts: string;
  load_mw: number;
  renewable_share_of_generation: number | null;
  generation_mw: Record<string, number>;
}
interface StatsFile {
  fetched: string;
  eu: Power | null;
  countries: Record<string, Power>;
  day_ahead_prices?: Record<string, PriceRow>;
}
interface Arc {
  from: string;
  to: string;
  mw: number;
  ts: string;
  path: [number, number][];
  timestamps: number[];
}
interface Shape {
  iso: string;
  name: string;
  polygon: [number, number][][];
}
/** [group index, MW, lon, lat, ISO, name, year in operation] */
type Plant = [number, number, number, number, string, string, number | null];

const SEA = "#05070b";
const NO_DATA: RGB = [30, 31, 36];
const BORDER: [number, number, number, number] = [214, 206, 196, 70];
const COAST: [number, number, number, number] = [150, 160, 176, 90];
const HVDC: RGB = [178, 146, 255];
const FLOW: RGB = [120, 222, 255];

// renewable share of generation, 0 -> 100 %: ember -> slate -> deep teal
const SHARE_STOPS: Array<[number, RGB]> = [
  [0, [70, 38, 40]],
  [35, [58, 48, 58]],
  [65, [36, 58, 70]],
  [100, [22, 84, 86]],
];
const dim = (c: RGB, k: number): RGB => [c[0] * k, c[1] * k, c[2] * k].map(Math.round) as RGB;
const lift = (c: RGB, k: number): RGB => c.map((v) => Math.round(v + (255 - v) * k)) as RGB;

function bbox(c: Country): [[number, number], [number, number]] {
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

function shareColor(share: number | null | undefined): RGB {
  if (share == null) return NO_DATA;
  for (let i = 1; i < SHARE_STOPS.length; i++) {
    const [s1, c1] = SHARE_STOPS[i];
    const [s0, c0] = SHARE_STOPS[i - 1];
    if (share <= s1) {
      const t = (share - s0) / (s1 - s0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * t)) as RGB;
    }
  }
  return SHARE_STOPS[SHARE_STOPS.length - 1][1];
}

// day-ahead price, EUR/MWh: cheap teal -> slate -> expensive ember
const PRICE_STOPS: Array<[number, RGB]> = [
  [0, [22, 84, 86]],
  [80, [40, 62, 76]],
  [150, [86, 50, 58]],
  [250, [140, 54, 40]],
];
const PRICE_MAX = 250;
const MULTI_ZONE: RGB = [48, 46, 58];
function priceColor(eur: number | null | undefined): RGB {
  if (eur == null) return NO_DATA;
  const v = Math.max(0, Math.min(PRICE_MAX, eur));
  for (let i = 1; i < PRICE_STOPS.length; i++) {
    const [s1, c1] = PRICE_STOPS[i];
    const [s0, c0] = PRICE_STOPS[i - 1];
    if (v <= s1) {
      const t = (v - s0) / (s1 - s0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * t)) as RGB;
    }
  }
  return PRICE_STOPS[PRICE_STOPS.length - 1][1];
}
const GAS: RGB = [255, 150, 92]; // LNG terminals and storages (gas = orange, as gas plants)
const GAS_PIPE: RGB = [226, 206, 160]; // pale sand, dashed, so pipelines never read as power lines
const GAS_DETAIL_ZOOM = 5.5; // pipelines and storages from here, or for the focused country
const COLUMN_MIN_MW = 10; // focused units from here stand as columns, smaller ones lie flat
// "beams & fields" style: big plants as light beams, the rest summed into hexagons
const BEAM_MIN_MW = 200;
const HEX_KM = 12; // hexagon circumradius
const HEX_M_PER_SQRT_MW = 450; // fields stay low next to the beams
const BEAM_BANDS = [
  [0, 0.4, 255],
  [0.4, 0.72, 175],
  [0.72, 1, 80],
] as const; // [from, to, alpha] of the beam height: bright base, fading top

interface Hex {
  position: [number, number];
  mw: number;
  units: number;
  /** MW per fuel group index */
  mix: Map<number, number>;
  dominant: number;
}

/** Sum units into flat-top hexagons (circumradius HEX_KM) in a local km grid. */
function hexBins(units: Unit[]): Hex[] {
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
const SUBSTATION: RGB = [226, 232, 240];

// copper by voltage, kept dim so countries, plants and flows read first
const VOLTAGE_BANDS: Array<{ min: number; label: string; color: RGB; width: number; alpha: number }> = [
  { min: 380, label: "380–750 kV", color: [236, 178, 120], width: 0.8, alpha: 125 },
  { min: 275, label: "275–330 kV", color: [206, 132, 84], width: 0.7, alpha: 95 },
  { min: 0, label: "220–254 kV", color: [160, 100, 70], width: 0.6, alpha: 75 },
];
const band = (kv: number) => VOLTAGE_BANDS.find((b) => kv >= b.min)!;

const FUEL_ORDER = ["solar", "wind", "nuclear", "gas", "coal", "hydro", "bio", "oil", "other"];
const FUEL_COLOR: Record<string, RGB> = {
  nuclear: [255, 96, 150],
  coal: [160, 146, 132],
  gas: [255, 128, 72],
  oil: [214, 96, 64],
  hydro: [84, 156, 255],
  wind: [72, 222, 184],
  solar: [255, 214, 72],
  bio: [150, 196, 92],
  storage: [196, 196, 214],
  other: [168, 146, 210],
};
const FUEL_LABEL: Record<string, string> = {
  nuclear: "Nuclear",
  coal: "Coal & lignite",
  gas: "Gas",
  oil: "Oil",
  hydro: "Hydro",
  wind: "Wind",
  solar: "Solar",
  bio: "Bioenergy & waste",
  storage: "Storage",
  other: "Other",
};
const PLANT_LABEL: Record<string, string> = { ...FUEL_LABEL, gas: "Gas & oil" };

// where each country's flow arcs start and end (inland points, not capitals)
const ANCHOR: Record<string, [number, number]> = {
  AL: [20.0, 41.1],
  AT: [14.3, 47.6],
  BA: [17.8, 44.2],
  BE: [4.6, 50.6],
  BG: [25.2, 42.7],
  CH: [8.2, 46.8],
  CZ: [15.3, 49.8],
  DE: [10.4, 51.1],
  DK: [9.3, 56.0],
  EE: [25.5, 58.7],
  ES: [-3.7, 40.3],
  FI: [26.0, 62.5],
  FR: [2.4, 46.6],
  GB: [-1.8, 52.8],
  GR: [22.0, 39.5],
  HR: [15.9, 45.6],
  HU: [19.4, 47.2],
  IE: [-8.0, 53.2],
  IT: [12.3, 43.0],
  LT: [23.9, 55.3],
  LU: [6.1, 49.7],
  LV: [24.9, 56.9],
  ME: [19.3, 42.8],
  MD: [28.5, 47.2],
  MK: [21.7, 41.6],
  NL: [5.6, 52.2],
  NO: [9.5, 61.0],
  PL: [19.2, 52.0],
  PT: [-8.1, 39.6],
  RO: [24.9, 45.9],
  RS: [20.8, 44.1],
  SE: [15.8, 61.0],
  SI: [14.8, 46.1],
  SK: [19.5, 48.7],
  UA: [31.0, 49.0],
  XK: [20.9, 42.6],
};
// too small for a name at continent zoom
const SMALL = new Set(["LU", "ME", "MK", "XK", "AL", "BA", "SI", "MD", "BE", "NL", "DK", "EE", "LV", "LT", "CH"]);

const EUROPE: [[number, number], [number, number]] = [
  [-11, 35.5],
  [32, 70],
];
const BLANK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": SEA } }],
};
const IDLE_MW = 20;
const LABEL_MW = 1000; // arcs from this size carry a GW label
const DETAIL_ZOOM = 5; // below: plants >= 50 MW only
// focused-country columns: height grows with the square root of capacity, so a 20 MW
// wind farm still reads as a bar next to a 5 GW plant (100 MW: 31 km, 1 GW: 98 km)
const COLUMN_M_PER_SQRT_MW = 3100;

// ?capture=16x9: video stage for scripts/record-video.mjs (virtual clock). A drawn
// cursor tours Europe -> France -> Italy -> Poland -> Germany in the beams & fields style.
// The page is recorded exactly as it looks in the browser; only the cursor is added.
const CAPTURE = new URLSearchParams(window.location.search).get("capture") === "16x9";

// ?day=YYYY-MM-DD (or day=latest): 24 h time-lapse of one real day, every 15 min,
// from frontend/public/data/eu/day/<date>.json (scripts/build_eu_day.py). The clock shows
// the market's own time (Europe/Berlin, CET/CEST) of the slot whose values are on screen.
const DAY_PARAM = new URLSearchParams(window.location.search).get("day");
const DAY_SECONDS = Number(new URLSearchParams(window.location.search).get("daySeconds")) || 36;
// ?day=...&at=21:30 opens the day at that local time, paused
const DAY_AT = new URLSearchParams(window.location.search).get("at");
type Series = (number | null)[];
interface DaySeries {
  load: Series;
  renewable_share: Series;
  generation: Record<string, Series>;
}
interface DayFile {
  date: string;
  start: string;
  step_s: number;
  slots: number;
  prices: Record<string, { country: string; values: Series }>;
  countries: Record<string, DaySeries>;
  eu: DaySeries | null;
  borders: { a: string; b: string; values: Series }[];
  /** key moments, computed by scripts/day_highlights.py */
  highlights?: Highlight[];
}
const MARKET_CLOCK = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Berlin",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});
const marketTime = (iso: string) => MARKET_CLOCK.format(new Date(iso));

// day view: one tower of generation per country, stacked steady sources first and the
// weather-driven ones on top, so solar visibly swells at noon and vanishes at night
const TOWER_ORDER = ["nuclear", "coal", "gas", "oil", "hydro", "bio", "other", "wind", "solar"];
const TOWER_M_PER_MW = 14; // 1 GW of generation stands 14 km tall
const TOWER_RADIUS_M = 58_000;
const TOWER_LABEL_MW = 8000; // towers from this total carry a "DE 61 GW" label
const PLAIN_LAND: RGB = [34, 37, 46];
const CAPTION_SLOTS = 10; // a caption stays for 2.5 h of the day (~4 s at 36 s per day)

interface Highlight {
  slot: number;
  kind: string;
  gw?: number;
  pct?: number;
  eur?: number;
  zone?: string;
  country?: string;
  from?: string;
  to?: string;
}

/** Title and sentence for a key moment; every number is the script's. */
function captionText(h: Highlight, name: (iso?: string) => string): { title: string; text: string; color: RGB } {
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
const NIGHT_BOUNDS: [number, number, number, number] = [-35, 27, 65, 75];

/**
 * Sun altitude (degrees) at a place and moment: NOAA's solar position approximation
 * (declination and equation of time from the fractional year).
 */
function sunAltitude(lon: number, lat: number, when: Date, decl: number, eqMin: number): number {
  const minutes = when.getUTCHours() * 60 + when.getUTCMinutes() + when.getUTCSeconds() / 60;
  const hourAngle = ((minutes + eqMin + 4 * lon) / 4 - 180) * (Math.PI / 180);
  const phi = (lat * Math.PI) / 180;
  const sinAlt = Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(hourAngle);
  return (Math.asin(Math.max(-1, Math.min(1, sinAlt))) * 180) / Math.PI;
}

/** Solar declination (rad) and equation of time (min) for a moment (NOAA). */
function sunState(when: Date): { decl: number; eqMin: number } {
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
const centralSun = (when: Date) => {
  const { decl, eqMin } = sunState(when);
  return sunAltitude(10, 50, when, decl, eqMin);
};

/** Night shadow over Europe at a moment, drawn per pixel in Web Mercator rows. */
function nightImage(when: Date): HTMLCanvasElement {
  const { decl, eqMin } = sunState(when);
  const W = 128;
  const H = 96;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(W, H);
  const [west, south, east, north] = NIGHT_BOUNDS;
  const merc = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  const y0 = merc(north);
  const y1 = merc(south);
  for (let row = 0; row < H; row++) {
    const yy = y0 + ((y1 - y0) * (row + 0.5)) / H;
    const lat = ((2 * Math.atan(Math.exp(yy)) - Math.PI / 2) * 180) / Math.PI;
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

interface TowerPiece {
  iso: string;
  name: string;
  group: string;
  /** stacked height of the pieces below, MW as drawn */
  base: number;
  /** real value of this source in the slot on the clock */
  mw: number;
  /** value as drawn this frame (glides to the next slot) */
  drawn: number;
  /** real total of the country in the slot on the clock */
  total: number;
}

/** One slot of a day series in the shape of the snapshot's Power. */
function dayPower(series: DaySeries | null | undefined, k: number, ts: string): Power | undefined {
  const load = series?.load[k];
  if (!series || load == null) return undefined;
  const generation_mw: Record<string, number> = {};
  for (const [g, col] of Object.entries(series.generation)) if (col[k] != null) generation_mw[g] = col[k] as number;
  return { ts, load_mw: load, renewable_share_of_generation: series.renewable_share[k] ?? null, generation_mw };
}

/** Small area chart of a day with a cursor at slot k; `band` draws [low, high] per slot. */
function DayChart({
  title,
  layers,
  band,
  k,
  slots,
  unit,
}: {
  title: string;
  layers?: { values: Series; color: RGB }[];
  band?: { low: Series; high: Series; color: RGB };
  k: number;
  slots: number;
  unit: string;
}) {
  const W = 220;
  const H = 40;
  const x = (i: number) => (i / Math.max(1, slots - 1)) * W;
  let max = 1;
  let min = 0;
  if (layers) {
    for (let i = 0; i < slots; i++) max = Math.max(max, layers.reduce((a, l) => a + (l.values[i] ?? 0), 0));
  }
  if (band) {
    max = Math.max(...band.high.map((v) => v ?? -Infinity));
    min = Math.min(0, ...band.low.map((v) => v ?? Infinity));
  }
  const y = (v: number) => H - ((v - min) / (max - min || 1)) * H;
  const paths: { d: string; color: RGB }[] = [];
  if (layers) {
    const base = new Array<number>(slots).fill(0);
    for (const l of layers) {
      const top = base.map((b, i) => b + (l.values[i] ?? 0));
      let d = `M${x(0)},${y(top[0])}`;
      for (let i = 1; i < slots; i++) d += `L${x(i).toFixed(1)},${y(top[i]).toFixed(1)}`;
      for (let i = slots - 1; i >= 0; i--) d += `L${x(i).toFixed(1)},${y(base[i]).toFixed(1)}`;
      paths.push({ d: `${d}Z`, color: l.color });
      for (let i = 0; i < slots; i++) base[i] = top[i];
    }
  }
  if (band) {
    let d = "";
    for (let i = 0; i < slots; i++) if (band.high[i] != null) d += `${d ? "L" : "M"}${x(i).toFixed(1)},${y(band.high[i] as number).toFixed(1)}`;
    for (let i = slots - 1; i >= 0; i--) if (band.low[i] != null) d += `L${x(i).toFixed(1)},${y(band.low[i] as number).toFixed(1)}`;
    paths.push({ d: `${d}Z`, color: band.color });
  }
  return (
    <div className="mt-3">
      <div className="flex justify-between text-[9px] uppercase tracking-[0.2em] text-[#8f877e]">
        <span>{title}</span>
        <span>{unit}</span>
      </div>
      <svg width={W} height={H + 2} className="mt-1 block">
        {min < 0 && <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="rgba(255,255,255,0.25)" strokeDasharray="2 2" />}
        {paths.map((pt, i) => (
          <path key={i} d={pt.d} fill={rgbCss(pt.color, 0.55)} />
        ))}
        <line x1={x(k)} x2={x(k)} y1={0} y2={H} stroke="#f1f5f9" strokeWidth={1.2} />
      </svg>
    </div>
  );
}
const TOUR_COUNTRIES = ["FR", "IT", "PL", "DE"];
type TourTarget = string; // ISO code, or "close" for the panel's close button
type TourStep = { kind: "wait"; ms: number } | { kind: "move"; to: TourTarget; ms: number } | { kind: "click"; on: TourTarget };
const TOUR: TourStep[] = [
  { kind: "wait", ms: 2200 },
  { kind: "move", to: "FR", ms: 1500 },
  { kind: "click", on: "FR" },
  { kind: "wait", ms: 6000 },
  { kind: "move", to: "IT", ms: 1400 },
  { kind: "click", on: "IT" },
  { kind: "wait", ms: 6000 },
  { kind: "move", to: "PL", ms: 1500 },
  { kind: "click", on: "PL" },
  { kind: "wait", ms: 6000 },
  { kind: "move", to: "DE", ms: 1400 },
  { kind: "click", on: "DE" },
  { kind: "wait", ms: 60000 },
];
const RIPPLE_MS = 550;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

declare global {
  interface Window {
    __captureReady?: boolean;
    /** called by the recorder on its first frame: starts the tour */
    __captureGo?: () => void;
  }
}

const pairs = (flat: number[]): [number, number][] => {
  const p: [number, number][] = [];
  for (let k = 0; k < flat.length; k += 2) p.push([flat[k], flat[k + 1]]);
  return p;
};
const gw = (mw: number) => `${(Math.abs(mw) / 1000).toFixed(1)} GW`;
const utc = (iso: string) => `${iso.slice(11, 16)} UTC`;

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

// refreshed every 30 min by .github/workflows/eu-snapshot.yml
const SNAPSHOT_REMOTE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-data/eu";
// rolling archive of complete days, kept by .github/workflows/eu-days.yml
const DAYS_REMOTE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu/day";
const MOBILE_QUERY = "(max-width: 767px)";
const isNarrow = () => window.matchMedia(MOBILE_QUERY).matches;
const dayLabel = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

/** Views of the app, shown as tabs (more join as they are built). */
const TABS: { id: "live" | "day"; label: string; href: string }[] = [
  { id: "live", label: "Live map", href: "/" },
  { id: "day", label: "24 hours", href: "/?day=latest" },
];

/**
 * Hands over the copy bundled with the app at once, then the cloud snapshot if it
 * is newer (the remote fetch can be slow or missing, so it never blocks the map).
 */
function loadSnapshot<T extends { fetched: string }>(name: string, use: (v: T) => void): void {
  let bundled: T | null = null;
  getJson<T>(`/data/eu/${name}`)
    .then((v) => {
      bundled = v;
      use(v);
    })
    .catch(() => {});
  fetch(`${SNAPSHOT_REMOTE}/${name}?t=${Date.now()}`, { signal: AbortSignal.timeout(8000) })
    .then((r) => (r.ok ? (r.json() as Promise<T>) : Promise.reject()))
    .then((v) => {
      if (!bundled || v.fetched > bundled.fetched) use(v);
    })
    .catch(() => {});
}

function powerHtml(title: string, p: Power | undefined): string {
  if (!p) return `<b>${title}</b><br/><span style="color:#8d94a1">no Energy-Charts data</span>`;
  const rows = Object.entries(p.generation_mw)
    .filter(([, mw]) => mw > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([f, mw]) => `<div style="display:flex;justify-content:space-between;gap:16px"><span>${FUEL_LABEL[f] ?? f}</span><span>${gw(mw)}</span></div>`)
    .join("");
  const share = p.renewable_share_of_generation;
  return `<b style="letter-spacing:.08em">${title}</b>
    <div style="color:#8d94a1;margin:2px 0 6px">interval ${utc(p.ts)}</div>
    ${share != null ? `<div>Renewable share of generation <b>${share.toFixed(1)} %</b></div>` : ""}
    <div>Load <b>${gw(p.load_mw)}</b></div>
    <div style="margin-top:6px">${rows}</div>`;
}

const power = (mw: number) => (Math.abs(mw) >= 1000 ? gw(mw) : `${Math.round(Math.abs(mw))} MW`);

/** Load, published renewable share and generation mix of one interval. */
function PowerBlock({ power: p, time = utc }: { power: Power; time?: (iso: string) => string }) {
  const sources = FUEL_ORDER.filter((f) => (p.generation_mw[f] ?? 0) > 0).sort((a, b) => p.generation_mw[b] - p.generation_mw[a]);
  const max = Math.max(1, ...Object.values(p.generation_mw));
  return (
    <>
      <div className="mt-0.5 text-[9px] uppercase tracking-[0.2em] text-[#8f877e]">interval {time(p.ts)}</div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <div className="text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Load</div>
          <div className="text-[20px] font-light tabular-nums">{power(p.load_mw)}</div>
        </div>
        {p.renewable_share_of_generation != null && (
          <div>
            <div className="text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Renewable gen.</div>
            <div className="text-[20px] font-light tabular-nums">{p.renewable_share_of_generation.toFixed(1)} %</div>
          </div>
        )}
      </div>
      <div className="mt-3 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Generation by source</div>
      <div className="mt-1.5 space-y-1">
        {sources.map((f) => (
          <div key={f}>
            <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
              <span>{FUEL_LABEL[f]}</span>
              <span>{power(p.generation_mw[f])}</span>
            </div>
            <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full" style={{ width: `${(p.generation_mw[f] / max) * 100}%`, background: rgbCss(FUEL_COLOR[f]) }} />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/** Drawn mouse pointer with a click ripple; headless capture has no OS cursor. */
function TourCursor({ tour }: { tour: { cursor: [number, number]; ripple: { at: number; x: number; y: number } | null } }) {
  const [x, y] = tour.cursor;
  const k = tour.ripple ? (performance.now() - tour.ripple.at) / RIPPLE_MS : 1;
  return (
    <>
      {tour.ripple && k < 1 && (
        <div
          className="pointer-events-none absolute z-30 rounded-full border-2 border-white"
          style={{
            left: tour.ripple.x - (8 + 30 * k),
            top: tour.ripple.y - (8 + 30 * k),
            width: 2 * (8 + 30 * k),
            height: 2 * (8 + 30 * k),
            opacity: 1 - k,
          }}
        />
      )}
      <svg
        className="pointer-events-none absolute z-30"
        style={{ left: x - 2, top: y - 1, filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.6))" }}
        width="24"
        height="30"
        viewBox="0 0 24 30"
      >
        <path d="M2 1 L2 23 L8 17.5 L12 27 L15.5 25.5 L11.5 16.5 L19.5 16.5 Z" fill="#ffffff" stroke="#111" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </>
  );
}

export default function EuropeView() {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [grid, setGrid] = useState<GridFile | null>(null);
  const [plants, setPlants] = useState<PlantsFile | null>(null);
  const [countries, setCountries] = useState<CountriesFile | null>(null);
  const [flows, setFlows] = useState<FlowsFile | null>(null);
  const [stats, setStats] = useState<StatsFile | null>(null);
  const [gas, setGas] = useState<GasFile | null>(null);
  const [reference, setReference] = useState<ReferenceFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState(0);
  // the day view is its own picture: price on the ground, generation towers, night shadow
  const [shade, setShade] = useState<"none" | "renewable" | "price">(DAY_PARAM ? "none" : "renewable");
  const [show, setShow] = useState(
    DAY_PARAM
      ? { plants: false, flows: true, substations: false, gas: false }
      : { plants: true, flows: true, substations: true, gas: true },
  );
  // 24 h replay: index into the flow series, null = latest complete interval
  const [replay, setReplay] = useState<number | null>(null);
  // day time-lapse: slot position (fractional) and play state live in refs; frame re-renders
  const [day, setDay] = useState<DayFile | null>(null);
  const daySlot = useRef(0);
  const [, setNightVersion] = useState(0); // bumps when a night frame is ready
  const [dayList, setDayList] = useState<string[]>([]);
  // phones: panels live in a bottom sheet, one at a time
  const [isMobile, setIsMobile] = useState(isNarrow);
  const [sheet, setSheet] = useState<"none" | "info" | "legend" | "sources">("none");
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const onChange = () => setIsMobile(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const dayPlaying = useRef(!CAPTURE);
  const lastFrame = useRef<number | null>(null);
  const [units, setUnits] = useState<{ iso: string; rows: Unit[] } | null>(null);
  // ?country=PL&style=beams opens the focused country in the beams & fields style
  const [plantStyle, setPlantStyle] = useState<"bars" | "beams">(() =>
    CAPTURE || new URLSearchParams(window.location.search).get("style") === "beams" ? "beams" : "bars",
  );
  const [playing, setPlaying] = useState(false);
  const [zoom, setZoom] = useState(4);
  // ?country=FR opens with a country focused
  const [selected, setSelected] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("country")?.toUpperCase() ?? null,
  );
  const clock = useRef(new FlowClock());

  useEffect(() => {
    Promise.all([
      getJson<GridFile>("/data/eu/grid.json").then(setGrid),
      getJson<PlantsFile>("/data/eu/plants.json").then(setPlants),
      getJson<CountriesFile>("/data/eu/countries.json").then(setCountries),
    ]).catch((e) => setError(String(e)));
    getJson<GasFile>("/data/eu/gas.json").then(setGas).catch(() => {});
  }, []);

  useEffect(() => {
    if (!DAY_PARAM) return;
    // days from the cloud archive (eu-days branch) plus any bundled with the site
    Promise.allSettled([
      fetch(`${DAYS_REMOTE}/index.json?t=${Date.now()}`, { signal: AbortSignal.timeout(6000) }).then((r) =>
        r.ok ? (r.json() as Promise<{ days: string[] }>) : Promise.reject(new Error(String(r.status))),
      ),
      getJson<{ days: string[] }>("/data/eu/day/index.json"),
    ])
      .then(([remote, local]) => {
        const remoteDays = remote.status === "fulfilled" ? remote.value.days : [];
        const localDays = local.status === "fulfilled" ? local.value.days : [];
        const all = [...new Set([...remoteDays, ...localDays])].sort();
        if (!all.length) throw new Error("no days built yet");
        setDayList(all);
        const d = DAY_PARAM !== "latest" && all.includes(DAY_PARAM) ? DAY_PARAM : all[all.length - 1];
        return getJson<DayFile>(remoteDays.includes(d) ? `${DAYS_REMOTE}/${d}.json` : `/data/eu/day/${d}.json`);
      })
      .then((d) => {
        if (DAY_AT) {
          const [h, m] = DAY_AT.split(":").map(Number);
          daySlot.current = Math.max(0, Math.min(d.slots - 1, Math.floor(((h || 0) * 60 + (m || 0)) / 15)));
          dayPlaying.current = false;
        }
        setDay(d);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // day view: frame continental Europe tighter so the towers fill the screen
  useEffect(() => {
    const map = mapRef.current;
    if (!day || !map) return;
    const frame = () =>
      map.fitBounds(
        [
          isNarrow() ? [-10, 41] : [-9, 36],
          isNarrow() ? [27, 60] : [27, 63],
        ],
        {
          padding: isNarrow()
            ? { left: 4, right: 4, top: 120, bottom: 60 }
            : { left: 300, right: 300, top: 40, bottom: 110 },
          pitch: isNarrow() ? 52 : 55,
          duration: 0,
        },
      );
    if (map.loaded()) frame();
    else map.once("load", frame);
  }, [day]);

  // night shadow for the slot on screen (and the next one), cached as it is computed
  const nightCache = useRef(new Map<number, ImageBitmap>());
  const nightSlot = day ? Math.min(day.slots - 1, Math.floor(daySlot.current)) : -1;
  useEffect(() => {
    if (!day || nightSlot < 0) return;
    let live = true;
    for (const k of [nightSlot, Math.min(day.slots - 1, nightSlot + 1)]) {
      if (nightCache.current.has(k)) continue;
      createImageBitmap(nightImage(new Date(Date.parse(day.start) + k * day.step_s * 1000))).then((b) => {
        nightCache.current.set(k, b);
        if (live) setNightVersion((v) => v + 1);
      });
    }
    return () => {
      live = false;
    };
  }, [day, nightSlot]);

  // the snapshot is optional: without it the map still renders, unshaded and still
  useEffect(() => {
    const load = () => {
      loadSnapshot<FlowsFile>("flows.json", setFlows);
      loadSnapshot<StatsFile>("stats.json", setStats);
      loadSnapshot<ReferenceFile>("reference.json", setReference);
    };
    load();
    const t = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BLANK_STYLE,
      bounds: EUROPE,
      fitBoundsOptions: { padding: isNarrow() ? { top: 150, bottom: 110, left: 6, right: 6 } : 24 },
      attributionControl: false,
      renderWorldCopies: false,
      pixelRatio: Math.min(window.devicePixelRatio, isNarrow() ? 1.5 : 2),
    });
    map.on("zoomend", () => setZoom(map.getZoom()));
    const o = new MapboxOverlay({
      interleaved: false,
      useDevicePixels: isNarrow() ? 1.5 : true,
      layers: [],
      // click a country to focus it; click it again or the sea to go back to Europe
      onClick: ({ object, layer }: PickingInfo) => {
        if (layer?.id === "eu-countries" && object) {
          const iso = (object as Shape).iso;
          setSelected((cur) => (cur === iso ? null : iso));
        } else if (!object) {
          setSelected(null);
        }
      },
      getTooltip: ({ object, layer }: PickingInfo) => {
        if (!object || !layer) return null;
        const style = {
          background: "rgba(8,10,14,0.92)",
          color: "#e2e8f0",
          fontSize: "11px",
          lineHeight: "1.5",
          padding: "8px 10px",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "6px",
        };
        if (layer.id === "eu-countries") {
          const s = object as Shape;
          return { html: powerHtml(s.name, statsRef.current?.countries[s.iso]), style };
        }
        if (layer.id === "eu-flows") {
          const a = object as Arc;
          return { html: `<b>${a.from} → ${a.to}</b> ${gw(a.mw)}<div style="color:#8d94a1">physical flow, interval ${utc(a.ts)}</div>`, style };
        }
        if (layer.id === "eu-lng" || layer.id === "eu-gas-storage") {
          const g = object as GasSite;
          const lng = layer.id === "eu-lng";
          const cap =
            g[5] != null ? (lng ? ` · send-out ${g[5]} M m³/day` : ` · working gas ${g[5].toLocaleString("en-US")} M m³`) : "";
          const since = g[4] ? ` · since ${g[4]}` : "";
          return {
            html: `<b>${g[0]}</b><div>${lng ? "LNG terminal" : "Gas storage"}${cap}${since}</div><div style="color:#8d94a1">SciGRID_gas 2021</div>`,
            style,
          };
        }
        if (layer.id === "eu-towers") {
          const t = object as TowerPiece;
          return {
            html: `<b>${t.name}</b><div>${FUEL_LABEL[t.group] ?? t.group} ${power(t.mw)} of ${power(t.total)} generated</div>`,
            style,
          };
        }
        if (layer.id === "eu-substations") {
          const b = object as Substation;
          return { html: `Substation · ${b[0]} kV`, style };
        }
        if (layer.id.startsWith("eu-hex")) {
          const h = object as Hex;
          const groups = plantsRef.current?.groups ?? [];
          const mix = [...h.mix.entries()]
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([g, mw]) => `${PLANT_LABEL[groups[g] ?? "other"]} ${power(mw)}`)
            .join(" · ");
          return {
            html: `<b>${power(h.mw)}</b> in ${h.units.toLocaleString("en-US")} units under ${BEAM_MIN_MW} MW<div>${mix}</div><div style="color:#8d94a1">sum over a ${HEX_KM * 2} km hexagon</div>`,
            style,
          };
        }
        if (layer.id === "eu-plant-columns" || layer.id === "eu-focus-small" || layer.id.startsWith("eu-beam")) {
          // beam segments wrap their unit; the glow, bars and dots are units themselves
          const u = (Array.isArray(object) ? object : (object as { unit: Unit }).unit) as Unit;
          const fuel = PLANT_LABEL[plantsRef.current?.groups[u[0]] ?? "other"];
          const year = u[5] ? ` · since ${u[5]}` : "";
          return { html: `<b>${u[4]}</b><div>${fuel} · ${u[1].toLocaleString("en-US")} MW installed${year}</div>`, style };
        }
        if (layer.id === "eu-plants") {
          const p = object as Plant;
          const fuel = PLANT_LABEL[plantsRef.current?.groups[p[0]] ?? "other"];
          const year = p[6] ? ` · since ${p[6]}` : "";
          return {
            html: `<b>${p[5]}</b><div>${fuel} · ${p[1].toLocaleString("en-US")} MW installed${year}</div>`,
            style,
          };
        }
        return null;
      },
    });
    map.addControl(o);
    overlay.current = o;
    mapRef.current = map;
    return () => map.remove();
  }, []);

  // the tooltip callback is created once; it reads the latest data through refs
  const statsRef = useRef<StatsFile | null>(null);
  const plantsRef = useRef<PlantsFile | null>(null);
  statsRef.current = stats;
  plantsRef.current = plants;

  const lineBands = useMemo(() => {
    if (!grid) return [];
    return VOLTAGE_BANDS.map((b) => ({
      ...b,
      paths: grid.lines.filter(([kv]) => band(kv) === b).map(([, flat]) => pairs(flat)),
    })).reverse(); // low voltage first, 380+ on top
  }, [grid]);
  const links = useMemo(() => (grid ? grid.links.map(([mw, flat]) => ({ mw, path: pairs(flat) })) : []), [grid]);
  const shapes = useMemo<Shape[]>(
    () =>
      countries
        ? countries.countries.flatMap((c) => c.polygons.map((rings) => ({ iso: c.iso, name: c.name, polygon: rings.map(pairs) })))
        : [],
    [countries],
  );
  // flat dots everywhere except the focused country, which gets 3D columns (all >= 20 MW)
  const visiblePlants = useMemo(
    () =>
      plants
        ? plants.plants.filter((p) => p[4] !== selected && (zoom >= DETAIL_ZOOM || p[1] >= 50))
        : [],
    [plants, zoom, selected],
  );
  // focused country: every unit >= 1 MW from plants/<ISO>.json (loaded on click);
  // until it arrives, the >= 20 MW plants of the main file stand in
  const unitCache = useRef(new Map<string, Unit[]>());
  const [tourUnitsReady, setTourUnitsReady] = useState(!CAPTURE);
  useEffect(() => {
    if (!selected) return;
    const cached = unitCache.current.get(selected);
    if (cached) {
      setUnits({ iso: selected, rows: cached });
      return;
    }
    let live = true;
    getJson<{ plants: Unit[] }>(`/data/eu/plants/${selected}.json`)
      .then((d) => {
        unitCache.current.set(selected, d.plants);
        if (live) setUnits({ iso: selected, rows: d.plants });
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [selected]);
  // the video tour must not wait for a plant file mid-recording: load them up front
  useEffect(() => {
    if (!CAPTURE) return;
    Promise.all(
      TOUR_COUNTRIES.map((iso) =>
        getJson<{ plants: Unit[] }>(`/data/eu/plants/${iso}.json`).then((d) => unitCache.current.set(iso, d.plants)),
      ),
    )
      .then(() => setTourUnitsReady(true))
      .catch((e) => setError(String(e)));
  }, []);
  const focusUnits = useMemo<Unit[]>(() => {
    if (!selected) return [];
    if (units?.iso === selected) return units.rows;
    return plants ? plants.plants.filter((p) => p[4] === selected).map((p) => [p[0], p[1], p[2], p[3], p[5], p[6]]) : [];
  }, [selected, units, plants]);
  const focusColumns = useMemo(() => focusUnits.filter((u) => u[1] >= COLUMN_MIN_MW), [focusUnits]);
  const focusSmall = useMemo(() => focusUnits.filter((u) => u[1] < COLUMN_MIN_MW), [focusUnits]);
  const focusBeams = useMemo(() => focusUnits.filter((u) => u[1] >= BEAM_MIN_MW), [focusUnits]);
  const focusHexes = useMemo(() => hexBins(focusUnits.filter((u) => u[1] < BEAM_MIN_MW)), [focusUnits]);
  const hexPeak = useMemo(() => Math.max(1, ...focusHexes.map((h) => h.mw)), [focusHexes]);
  const beamSegments = useMemo(
    () =>
      BEAM_BANDS.map(([a, b, alpha]) => ({
        alpha,
        rows: focusBeams.map((u) => {
          const h = Math.sqrt(u[1]) * COLUMN_M_PER_SQRT_MW * 1.15;
          return { unit: u, from: [u[2], u[3], h * a] as [number, number, number], to: [u[2], u[3], h * b] as [number, number, number] };
        }),
      })),
    [focusBeams],
  );

  const seriesLength = flows?.borders.reduce((n, f) => Math.max(n, f.series?.length ?? 0), 0) ?? 0;
  const replayTs = (k: number) =>
    flows?.series_start ? new Date(Date.parse(flows.series_start) + k * (flows.series_step_s ?? 900) * 1000).toISOString() : "";
  const dayK = day ? Math.min(day.slots - 1, Math.floor(daySlot.current)) : 0;
  const slotTs = (k: number) => (day ? new Date(Date.parse(day.start) + k * day.step_s * 1000).toISOString() : "");
  const arcs = useMemo<Arc[]>(() => {
    if (day) {
      const out: Arc[] = [];
      day.borders.forEach((f, n) => {
        const mw = f.values[dayK];
        if (mw == null || Math.abs(mw) < IDLE_MW) return;
        const [from, to] = mw > 0 ? [f.a, f.b] : [f.b, f.a];
        if (!ANCHOR[from] || !ANCHOR[to]) return;
        const path = curvedPath(ANCHOR[from], ANCHOR[to], 0.16, 40);
        out.push({ from, to, mw: Math.abs(mw), ts: slotTs(dayK), path, timestamps: flowDistances(path, false, n * 91_000) });
      });
      return out.sort((x, y) => x.mw - y.mw);
    }
    if (!flows) return [];
    const out: Arc[] = [];
    flows.borders.forEach((f, n) => {
      const mw = replay == null ? f.mw : f.series?.[replay];
      const ts = replay == null ? f.ts : replayTs(replay);
      if (mw == null || Math.abs(mw) < IDLE_MW) return;
      const [from, to] = mw > 0 ? [f.a, f.b] : [f.b, f.a];
      if (!ANCHOR[from] || !ANCHOR[to]) return;
      const path = curvedPath(ANCHOR[from], ANCHOR[to], 0.16, 40);
      out.push({ from, to, mw: Math.abs(mw), ts, path, timestamps: flowDistances(path, false, n * 91_000) });
    });
    return out.sort((x, y) => x.mw - y.mw);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flows, replay, day, dayK]);

  // replay: one 15-min step every 350 ms, back to the latest interval at the end
  useEffect(() => {
    if (!playing || !seriesLength) return;
    const t = setInterval(() => {
      setReplay((k) => {
        const next = (k ?? -1) + 1;
        if (next >= seriesLength) {
          setPlaying(false);
          return null;
        }
        return next;
      });
    }, 350);
    return () => clearInterval(t);
  }, [playing, seriesLength]);

  // tower heights glide between the 15-min values (drawing only); tooltips and labels
  // show the real value of the slot on the clock
  const dayFrac = day ? Math.max(0, Math.min(1, daySlot.current - dayK)) : 0;
  const towerNames = useMemo(() => new Map(countries?.countries.map((c) => [c.iso, c.name]) ?? []), [countries]);
  const towers: TowerPiece[] = [];
  if (day && countries) {
    const next = Math.min(day.slots - 1, dayK + 1);
    for (const [iso, series] of Object.entries(day.countries)) {
      if (!ANCHOR[iso] || (selected && selected !== iso)) continue;
      let base = 0;
      let slotTotal = 0;
      const pieces: TowerPiece[] = [];
      for (const g of TOWER_ORDER) {
        const now = series.generation[g]?.[dayK];
        const then = series.generation[g]?.[next] ?? now;
        if (now != null && now > 0) slotTotal += now;
        if (now == null || then == null) continue;
        const drawn = now + (then - now) * dayFrac;
        if (drawn <= 0) continue;
        pieces.push({ iso, name: towerNames.get(iso) ?? iso, group: g, base, mw: now, drawn, total: 0 });
        base += drawn;
      }
      for (const piece of pieces) piece.total = slotTotal;
      towers.push(...pieces);
    }
  }
  // a soft light under each tower in the colour of its largest source right now
  const towerPools = useMemo(() => {
    const best = new Map<string, TowerPiece>();
    for (const t of towers) if (!best.has(t.iso) || t.mw > best.get(t.iso)!.mw) best.set(t.iso, t);
    return [...best.values()].map((t) => ({ iso: t.iso, total: t.total, group: t.group }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day, dayK, selected, countries]);
  // the top piece of each tower, where its label sits
  const ranking = useMemo(() => {
    if (!day) return [];
    return Object.entries(day.countries)
      .map(([iso, c]) => {
        const parts = TOWER_ORDER.map((g) => [g, c.generation[g]?.[dayK] ?? 0] as [string, number]).filter(([, v]) => v > 0);
        return { iso, total: parts.reduce((a, [, v]) => a + v, 0), parts };
      })
      .filter((x) => x.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
  }, [day, dayK]);
  const captions = day?.highlights?.filter((h) => daySlot.current >= h.slot && daySlot.current < h.slot + CAPTION_SLOTS) ?? [];
  const countryName = (iso?: string) => countries?.countries.find((c) => c.iso === iso)?.name ?? iso ?? "";
  const towerTop = useMemo(() => new Map(towers.map((t) => [t.iso, t.group])), [towers]);
  const night = nightCache.current.get(dayK) ?? null;
  // real sunlight on the towers: direction from the clock's moment, strength from the sun's
  // height over Central Europe, so they brighten through the morning and dim after sunset
  const sunAlt = day ? centralSun(new Date(slotTs(dayK))) : 0;
  const lighting = useMemo(() => {
    if (!day) return null;
    const dayness = Math.max(0, Math.min(1, (sunAlt + 2) / 20));
    return new LightingEffect({
      ambient: new AmbientLight({ color: [255, 255, 255], intensity: 0.45 + 0.4 * dayness }),
      sun: new SunLight({ timestamp: Date.parse(slotTs(dayK)), color: [255, 236, 206], intensity: 2.2 * dayness }),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day, dayK]);
  const sunArc = useMemo(
    () => (day ? Array.from({ length: day.slots }, (_, k) => centralSun(new Date(Date.parse(day.start) + k * day.step_s * 1000))) : []),
    [day],
  );

  const prices: Record<string, PriceRow> = day
    ? Object.fromEntries(
        Object.entries(day.prices)
          .filter(([, z]) => z.values[dayK] != null)
          .map(([zone, z]) => [zone, { country: z.country, ts: slotTs(dayK), eur_mwh: z.values[dayK] as number }]),
      )
    : (stats?.day_ahead_prices ?? {});
  const shareOf = (iso: string) =>
    day ? day.countries[iso]?.renewable_share[dayK] : stats?.countries[iso]?.renewable_share_of_generation;
  const timeOf = day ? marketTime : utc;
  const zonesOf = (iso: string) => Object.entries(prices).filter(([, p]) => p.country === iso);
  const countryFill = (iso: string): RGB => {
    if (shade === "none") {
      const light = day ? Math.max(0, Math.min(1, (sunAlt + 4) / 24)) : 0;
      return [PLAIN_LAND[0] - 8 + 14 * light, PLAIN_LAND[1] - 8 + 16 * light, PLAIN_LAND[2] - 8 + 20 * light].map(Math.round) as RGB;
    }
    if (shade === "renewable") return shareColor(shareOf(iso));
    const zones = zonesOf(iso);
    return zones.length === 1 ? priceColor(zones[0][1].eur_mwh) : zones.length > 1 ? MULTI_ZONE : NO_DATA;
  };
  const substations = useMemo(() => (grid && (zoom >= 4.8 || selected) ? grid.substations : []), [grid, zoom, selected]);
  const topFlows = useMemo(() => [...arcs].sort((x, y) => y.mw - x.mw).slice(0, day ? 3 : 6), [arcs, day]);
  const countryLabels = useMemo(
    () => (countries ? countries.countries.filter((c) => zoom >= DETAIL_ZOOM || !SMALL.has(c.iso)) : []),
    [countries, zoom],
  );

  const focus = useMemo(() => countries?.countries.find((c) => c.iso === selected) ?? null, [countries, selected]);
  // shareable country links: ?country=FR stays in the address bar
  useEffect(() => {
    if (CAPTURE) return;
    const params = new URLSearchParams(window.location.search);
    if (selected) params.set("country", selected);
    else params.delete("country");
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
    document.title = focus ? `${focus.name} · Europe InfraAtlas` : "Europe InfraAtlas";
    if (focus) setSheet("info");
  }, [selected, focus]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (focus) {
      // tilt into the country so the plant columns stand up
      const pad = isNarrow()
        ? { left: 10, right: 10, top: 150, bottom: Math.round(window.innerHeight * 0.48) }
        : { left: 280, right: 320, top: 90, bottom: 60 };
      const cam = map.cameraForBounds(bbox(focus), { padding: pad });
      if (!cam?.center) return;
      map.flyTo({ center: cam.center, zoom: Math.min(6.2, (cam.zoom ?? 5) - 0.1), pitch: 52, bearing: -12, duration: 1400 });
    } else {
      const cam = map.cameraForBounds(EUROPE, { padding: 24 });
      map.flyTo({ center: cam?.center ?? [10, 52], zoom: cam?.zoom ?? 3.5, pitch: 0, bearing: 0, duration: 1200 });
    }
  }, [focus]);
  const gasDetail = !!selected || zoom >= GAS_DETAIL_ZOOM;
  const gasPipes = useMemo(() => {
    if (!show.gas || !gas || !gasDetail) return [];
    if (!focus || zoom >= GAS_DETAIL_ZOOM + 0.5) return gas.pipes;
    const [[x0, y0], [x1, y1]] = bbox(focus);
    return gas.pipes.filter(([, f]) => f.some((v, k) => (k % 2 ? v >= y0 && v <= y1 : v >= x0 && v <= x1 && f[k + 1] >= y0 && f[k + 1] <= y1)));
  }, [show.gas, gas, gasDetail, focus, zoom]);
  const focusRings = useMemo(() => (focus ? focus.polygons.map((rings) => pairs(rings[0])) : []), [focus]);
  const touches = (a: Arc) => a.from === selected || a.to === selected;

  // ---- video tour: a drawn cursor glides to each country and clicks it ----
  const countriesRef = useRef<CountriesFile | null>(null);
  countriesRef.current = countries;
  const tour = useRef({
    started: null as number | null,
    queue: [...TOUR],
    stepStart: 0,
    from: [1560, 860] as [number, number],
    to: [1560, 860] as [number, number],
    cursor: [1560, 860] as [number, number],
    ripple: null as { at: number; x: number; y: number } | null,
    /** the current move step has picked its target */
    aimed: false,
  });
  const [mapLoaded, setMapLoaded] = useState(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.loaded()) setMapLoaded(true);
    else map.once("load", () => setMapLoaded(true));
  }, []);
  useEffect(() => {
    if (!CAPTURE) return;
    window.__captureGo = () => {
      if (DAY_PARAM) {
        daySlot.current = 0;
        dayPlaying.current = true;
        return;
      }
      tour.current.started = performance.now();
      tour.current.stepStart = performance.now();
    };
    const data = DAY_PARAM ? day : stats && flows && tourUnitsReady;
    if (mapLoaded && grid && plants && countries && gas && reference && data) {
      window.__captureReady = true;
    }
  }, [mapLoaded, grid, plants, countries, stats, flows, gas, reference, tourUnitsReady, day]);

  /** Screen point to click for a target, or null when it is off-screen or under a panel. */
  const tourPoint = (target: TourTarget): [number, number] | null => {
    if (target === "close") {
      const b = document.querySelector('[title="Back to Europe"]')?.getBoundingClientRect();
      return b ? [b.left + b.width / 2, b.top + b.height / 2] : null;
    }
    const map = mapRef.current;
    const c = countriesRef.current?.countries.find((k) => k.iso === target);
    if (!map || !c) return null;
    const w = window.innerWidth;
    const h = window.innerHeight;
    const ok = ([x, y]: [number, number]) => x > 320 && x < w - 340 && y > 100 && y < h - 140;
    const label = map.project(c.label);
    if (ok([label.x, label.y])) return [label.x, label.y];
    // otherwise a point between the label and the outline that is in view
    const ring = c.polygons.reduce((a, b) => (b[0].length > a[0].length ? b : a))[0];
    for (let k = 0; k < ring.length; k += 2) {
      const lon = c.label[0] + (ring[k] - c.label[0]) * 0.55;
      const lat = c.label[1] + (ring[k + 1] - c.label[1]) * 0.55;
      const q = map.project([lon, lat]);
      if (ok([q.x, q.y])) return [q.x, q.y];
    }
    return null;
  };

  const tourTick = (now: number) => {
    const t = tour.current;
    if (t.started == null) return;
    const step = t.queue[0];
    if (!step) return;
    const elapsed = now - t.stepStart;
    if (step.kind === "move") {
      if (!t.aimed) {
        const target = tourPoint(step.to);
        if (!target) {
          // not reachable from this camera: close the panel first (back to Europe)
          t.queue.unshift({ kind: "move", to: "close", ms: 1000 }, { kind: "click", on: "close" }, { kind: "wait", ms: 1700 });
          t.stepStart = now;
          return;
        }
        t.from = [...t.cursor] as [number, number];
        t.to = target;
        t.aimed = true;
      }
      const k = Math.min(1, elapsed / step.ms);
      const e = ease(k);
      t.cursor = [t.from[0] + (t.to[0] - t.from[0]) * e, t.from[1] + (t.to[1] - t.from[1]) * e];
      if (k >= 1) {
        t.queue.shift();
        t.aimed = false;
        t.stepStart = now;
      }
    } else if (step.kind === "click") {
      t.ripple = { at: now, x: t.cursor[0], y: t.cursor[1] };
      setSelected(step.on === "close" ? null : step.on);
      t.queue.shift();
      t.stepStart = now;
    } else if (elapsed >= step.ms) {
      t.queue.shift();
      t.stepStart = now;
    }
  };

  // day time-lapse: the whole day in DAY_SECONDS, then it holds on the last slot
  const dayRef = useRef<DayFile | null>(null);
  dayRef.current = day;
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selected;
  const dayTick = (now: number) => {
    const d = dayRef.current;
    const dt = lastFrame.current == null ? 0 : Math.min(100, now - lastFrame.current);
    lastFrame.current = now;
    if (!d) return;
    if (dayPlaying.current) {
      daySlot.current = Math.min(d.slots - 0.001, daySlot.current + (dt / 1000) * (d.slots / DAY_SECONDS));
      if (daySlot.current >= d.slots - 0.001) dayPlaying.current = false;
    }
    // slow orbit over Europe while no country is focused
    const map = mapRef.current;
    if (map && map.loaded()) {
      // sky: near-black at night, deep blue by day (sun height over Central Europe)
      const when = new Date(Date.parse(d.start) + Math.floor(daySlot.current) * d.step_s * 1000);
      const light = Math.max(0, Math.min(1, (centralSun(when) + 4) / 24));
      const sky = [5 + 9 * light, 7 + 17 * light, 11 + 29 * light].map(Math.round);
      if (map.getLayer("background")) map.setPaintProperty("background", "background-color", `rgb(${sky.join(",")})`);
    }
    if (map && !selectedRef.current && map.loaded() && !isNarrow()) {
      const f = daySlot.current / d.slots;
      map.jumpTo({ bearing: -14 + 28 * f, pitch: 55 });
    }
  };

  // one clock for the arrows; only the uniforms change per frame
  useEffect(() => {
    let raf = 0;
    let tick = 0;
    const loop = (now: number) => {
      clock.current.tick(now, mapRef.current?.getZoom() ?? 4, 40);
      if (CAPTURE && !DAY_PARAM) tourTick(now);
      dayTick(now);
      // phones: re-render the page every other frame
      if (isNarrow() && (tick = (tick + 1) % 2) === 1) {
        raf = requestAnimationFrame(loop);
        return;
      }
      setFrame((n) => n + 1);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    const flow = clock.current.uniforms(mapRef.current?.getZoom() ?? 4, 72);
    const noDepth = { depthCompare: "always", depthWriteEnabled: false } as const;
    // day view: flat lines are hidden where a tower stands in front of them
    const flowDepth = { depthCompare: "less-equal", depthWriteEnabled: false } as const;
    const shares = stats?.countries;
    overlay.current?.setProps({
      effects: lighting ? [lighting] : [],
      layers: [
        new SolidPolygonLayer<Shape>({
          id: "eu-countries",
          data: shapes,
          getPolygon: (d) => d.polygon,
          getFillColor: (d) => {
            const c = countryFill(d.iso);
            return [...(!selected ? c : d.iso === selected ? lift(c, 0.05) : dim(c, 0.45)), 255];
          },
          updateTriggers: { getFillColor: [shares, selected, shade, day, dayK] },
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 22],
          parameters: noDepth,
        }),
        new BitmapLayer({
          id: "eu-night",
          visible: !!day && !!night,
          image: night ?? undefined,
          bounds: NIGHT_BOUNDS,
          parameters: noDepth,
        }),
        new PathLayer<number[]>({
          id: "eu-coast",
          data: countries?.coast ?? [],
          getPath: (d) => pairs(d),
          getColor: COAST,
          getWidth: 0.7,
          widthUnits: "pixels",
          parameters: noDepth,
        }),
        new PathLayer<number[]>({
          id: "eu-borders",
          data: countries?.borders ?? [],
          getPath: (d) => pairs(d),
          getColor: BORDER,
          getWidth: 0.9,
          widthUnits: "pixels",
          parameters: noDepth,
        }),
        new PathLayer<[number, number][]>({
          id: "eu-focus-glow",
          data: focusRings,
          getPath: (d) => d,
          getColor: [255, 246, 230, 45],
          getWidth: 7,
          widthUnits: "pixels",
          jointRounded: true,
          parameters: noDepth,
        }),
        new PathLayer<[number, number][]>({
          id: "eu-focus-outline",
          data: focusRings,
          getPath: (d) => d,
          getColor: [255, 246, 230, 235],
          getWidth: 1.8,
          widthUnits: "pixels",
          jointRounded: true,
          parameters: noDepth,
        }),
        ...lineBands.map(
          (b) =>
            new PathLayer<[number, number][]>({
              id: `eu-grid-${b.min}`,
              data: b.paths,
              getPath: (d) => d,
              getColor: [...b.color, day ? Math.round(b.alpha * 0.35) : b.alpha],
              updateTriggers: { getColor: [!!day] },
              getWidth: b.width,
              widthUnits: "pixels",
              parameters: noDepth,
            }),
        ),
        new PathLayer<[number, number[]], PathStyleExtensionProps<[number, number[]]>>({
          id: "eu-gas-pipes",
          data: gasPipes,
          getPath: (d) => pairs(d[1]),
          getColor: [...GAS_PIPE, 150],
          getWidth: (d) => 0.6 + Math.min(1, d[0] / 1200),
          widthUnits: "pixels",
          getDashArray: [3, 2],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          parameters: noDepth,
        }),
        new ScatterplotLayer<Substation>({
          id: "eu-substations",
          data: show.substations ? substations : [],
          getPosition: (b) => [b[1], b[2]],
          getRadius: (b) => (b[0] >= 380 ? 1.9 : 1.3),
          radiusUnits: "pixels",
          getFillColor: [...SUBSTATION, 150],
          pickable: true,
          parameters: noDepth,
        }),
        new PathLayer<{ mw: number; path: [number, number][] }, PathStyleExtensionProps>({
          id: "eu-hvdc",
          data: links,
          getPath: (d) => d.path,
          getColor: [...HVDC, 190],
          getWidth: 1,
          widthUnits: "pixels",
          getDashArray: [4, 3],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          parameters: noDepth,
        }),
        new ScatterplotLayer<Plant>({
          id: "eu-plants",
          data: show.plants ? visiblePlants : [],
          getPosition: (p) => [p[2], p[3]],
          getRadius: (p) => Math.min(zoom < DETAIL_ZOOM ? 4.2 : 6.5, 1 + Math.sqrt(p[1]) * (zoom < DETAIL_ZOOM ? 0.06 : 0.085)),
          radiusUnits: "pixels",
          getFillColor: (p) => [...FUEL_COLOR[plants!.groups[p[0]]], zoom < DETAIL_ZOOM ? 200 : 235],
          stroked: true,
          getLineColor: [6, 7, 10, 220],
          lineWidthUnits: "pixels",
          getLineWidth: 0.7,
          updateTriggers: { getRadius: [zoom < DETAIL_ZOOM], getFillColor: [zoom < DETAIL_ZOOM] },
          pickable: true,
          parameters: noDepth,
        }),
        // focused country: one column per plant, height = installed capacity
        new ScatterplotLayer<Unit>({
          id: "eu-focus-small",
          data: show.plants && plantStyle === "bars" ? focusSmall : [],
          getPosition: (u) => [u[2], u[3]],
          getRadius: 1.8,
          radiusUnits: "pixels",
          getFillColor: (u) => [...FUEL_COLOR[plants?.groups[u[0]] ?? "other"], 200],
          pickable: true,
          parameters: noDepth,
        }),
        new ColumnLayer<Unit>({
          id: "eu-plant-columns",
          data: show.plants && plantStyle === "bars" ? focusColumns : [],
          getPosition: (p) => [p[2], p[3]],
          getElevation: (p) => Math.sqrt(p[1]) * COLUMN_M_PER_SQRT_MW,
          getFillColor: (p) => [...FUEL_COLOR[plants!.groups[p[0]]], 235],
          radius: 3800,
          diskResolution: 12,
          extruded: true,
          pickable: true,
          material: { ambient: 0.55, diffuse: 0.6, shininess: 24, specularColor: [60, 60, 60] },
        }),
        // beams & fields: low glowing hexagons for units under BEAM_MIN_MW ...
        new ColumnLayer<Hex>({
          id: "eu-hex-fields",
          data: show.plants && plantStyle === "beams" ? focusHexes : [],
          getPosition: (h) => h.position,
          getElevation: (h) => Math.sqrt(h.mw) * HEX_M_PER_SQRT_MW,
          // brightness follows capacity, so sparse hexagons fade into the ground
          getFillColor: (h) => [
            ...FUEL_COLOR[plants?.groups[h.dominant] ?? "other"],
            Math.round(40 + 170 * Math.min(1, Math.sqrt(h.mw / hexPeak))),
          ],
          updateTriggers: { getFillColor: [hexPeak] },
          radius: HEX_KM * 1000,
          coverage: 0.84,
          diskResolution: 6,
          extruded: true,
          pickable: true,
          material: { ambient: 0.8, diffuse: 0.35, shininess: 8, specularColor: [30, 30, 30] },
        }),
        // ... a soft glow at each beam's foot ...
        new ScatterplotLayer<Unit>({
          id: "eu-beam-glow",
          data: show.plants && plantStyle === "beams" ? focusBeams : [],
          getPosition: (u) => [u[2], u[3]],
          getRadius: (u) => 5 + Math.sqrt(u[1]) * 0.18,
          radiusUnits: "pixels",
          getFillColor: (u) => [...FUEL_COLOR[plants?.groups[u[0]] ?? "other"], 70],
          pickable: true,
          parameters: noDepth,
        }),
        // ... and a vertical light beam per big plant, fading towards the top
        ...beamSegments.map(
          (band, i) =>
            new LineLayer<{ unit: Unit; from: [number, number, number]; to: [number, number, number] }>({
              id: `eu-beam-${i}`,
              data: show.plants && plantStyle === "beams" ? band.rows : [],
              getSourcePosition: (d) => d.from,
              getTargetPosition: (d) => d.to,
              getColor: (d) => [...FUEL_COLOR[plants?.groups[d.unit[0]] ?? "other"], band.alpha],
              getWidth: (d) => 3.5 + Math.min(4.5, d.unit[1] / 800),
              widthUnits: "pixels",
              pickable: true,
              // always on top of the fields
              parameters: noDepth,
            }),
        ),
        new ScatterplotLayer<GasSite>({
          id: "eu-gas-storage",
          data: show.gas && gas && gasDetail ? gas.storages.filter((g) => !selected || g[1] === selected || zoom >= GAS_DETAIL_ZOOM) : [],
          getPosition: (g) => [g[2], g[3]],
          getRadius: 3.2,
          radiusUnits: "pixels",
          filled: false,
          stroked: true,
          getLineColor: [...GAS, 210],
          lineWidthUnits: "pixels",
          getLineWidth: 1.2,
          pickable: true,
          parameters: noDepth,
        }),
        new ScatterplotLayer<GasSite>({
          id: "eu-lng",
          data: show.gas && gas ? gas.lng : [],
          getPosition: (g) => [g[2], g[3]],
          getRadius: gasDetail ? 5 : 2.6,
          radiusUnits: "pixels",
          getFillColor: [...GAS, 235],
          stroked: true,
          getLineColor: [255, 255, 255, 230],
          lineWidthUnits: "pixels",
          getLineWidth: gasDetail ? 1.5 : 0.8,
          updateTriggers: { getRadius: [gasDetail], getLineWidth: [gasDetail] },
          pickable: true,
          parameters: noDepth,
        }),
        new TextLayer<Country>({
          id: "eu-country-names",
          data: countryLabels,
          getPosition: (c) => c.label,
          getText: (c) => c.name.toUpperCase(),
          getSize: 10.5,
          getColor: [236, 232, 224, 170],
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 600,
          parameters: noDepth,
        }),
        new ScatterplotLayer<{ iso: string; total: number; group: string }>({
          id: "eu-tower-pools",
          data: towerPools,
          getPosition: (t) => ANCHOR[t.iso],
          getRadius: (t) => 30_000 + Math.sqrt(t.total) * 450,
          getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 70],
          stroked: false,
          parameters: {
            depthCompare: "always",
            depthWriteEnabled: false,
            blend: true,
            blendColorSrcFactor: "src-alpha",
            blendColorDstFactor: "one",
            blendAlphaSrcFactor: "one",
            blendAlphaDstFactor: "one-minus-src-alpha",
          },
        }),
        new ColumnLayer<TowerPiece>({
          id: "eu-towers",
          data: towers,
          getPosition: (t) => [...ANCHOR[t.iso], t.base * TOWER_M_PER_MW] as [number, number, number],
          getElevation: (t) => t.drawn * TOWER_M_PER_MW,
          getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 235],
          radius: TOWER_RADIUS_M,
          diskResolution: 24,
          extruded: true,
          pickable: true,
          material: { ambient: 0.55, diffuse: 0.6, shininess: 20, specularColor: [50, 50, 50] },
        }),
        // dark casing so the flow lines read over countries, plants and grid
        new PathLayer<Arc>({
          id: "eu-flow-casing",
          data: show.flows ? arcs : [],
          getPath: (d) => d.path,
          getColor: (d) => [4, 6, 10, !selected || touches(d) ? (day ? 120 : 190) : 60],
          getWidth: (d) => (day ? 3.5 : 5) + Math.min(4, d.mw / 700),
          updateTriggers: { getColor: [selected, !!day], getWidth: [!!day] },
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          parameters: day ? flowDepth : noDepth,
        }),
        new FlowArrowLayer<Arc>({
          id: "eu-flows",
          data: show.flows ? arcs : [],
          getPath: (d) => d.path,
          getTimestamps: (d) => d.timestamps,
          // with a country focused, its own flows stay bright and the rest fade
          getColor: (d) => [...FLOW, !selected || touches(d) ? (day ? 165 : 255) : 45],
          getWidth: (d) => (day ? 14 : 20) + Math.min(12, d.mw / 250),
          getArrowStyle: (d) => [1.4 + Math.min(1.8, d.mw / 1500), 4.5 + Math.min(5, d.mw / 500), 1],
          updateTriggers: { getColor: [selected, !!day], getWidth: [!!day] },
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          pickable: true,
          phase: flow.phase,
          spacing: flow.spacing,
          strokePx: 2.4,
          lineAlpha: 0.85,
          parameters: {
            depthCompare: day ? "less-equal" : "always",
            depthWriteEnabled: false,
            blend: true,
            blendColorSrcFactor: "one",
            blendColorDstFactor: "one-minus-src-alpha",
            blendAlphaSrcFactor: "one",
            blendAlphaDstFactor: "one-minus-src-alpha",
          },
        }),
        new TextLayer<Arc>({
          id: "eu-flow-labels",
          data:
            !show.flows || (day && !selected)
              ? []
              : selected
                ? arcs.filter(touches)
                : isMobile
                  ? [...arcs].sort((a, b) => b.mw - a.mw).slice(0, 4)
                  : arcs.filter((a) => a.mw >= LABEL_MW),
          getPosition: (a) => a.path[20],
          getText: (a) => power(a.mw),
          getSize: 11,
          getColor: [214, 244, 255, 255],
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700,
          background: true,
          getBackgroundColor: [6, 9, 14, 215],
          backgroundPadding: [5, 2],
          getBorderColor: [...FLOW, 110],
          getBorderWidth: 1,
          getPixelOffset: [0, -12],
          parameters: noDepth,
        }),
        new TextLayer<TowerPiece>({
          id: "eu-tower-labels",
          data: towers
            .filter((t) => t.group === towerTop.get(t.iso) && t.total >= TOWER_LABEL_MW)
            .sort((a, b) => b.total - a.total)
            .slice(0, isMobile ? 5 : 9),
          getPosition: (t) => [...ANCHOR[t.iso], (t.base + t.drawn) * TOWER_M_PER_MW + 25_000] as [number, number, number],
          getText: (t) => `${t.iso} ${Math.round(t.total / 1000)} GW`,
          getSize: 12,
          getColor: [236, 240, 246, 255],
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700,
          background: true,
          getBackgroundColor: [6, 9, 14, 200],
          backgroundPadding: [4, 2],
          // labels that would overlap hide; the bigger country wins
          parameters: noDepth,
        }),
      ],
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frame, night, lighting, towerPools, shapes, countries, visiblePlants, focusColumns, focusSmall, focusHexes, hexPeak, beamSegments, plantStyle, plants, lineBands, links, arcs, countryLabels, stats, selected, focusRings, gas, gasPipes, gasDetail, substations, show, shade]);

  // the EU aggregate is hourly: label it with the start of its hour
  const euHour = day ? Math.floor((dayK * day.step_s) / 3600) * (3600 / day.step_s) : 0;
  const eu = day ? (dayPower(day.eu, dayK, slotTs(euHour)) ?? null) : (stats?.eu ?? null);
  const focusPower = selected
    ? day
      ? dayPower(day.countries[selected], dayK, slotTs(dayK))
      : stats?.countries[selected]
    : undefined;
  const dayCharts = useMemo(() => {
    if (!day) return null;
    const low: Series = [];
    const high: Series = [];
    for (let i = 0; i < day.slots; i++) {
      const v = Object.values(day.prices)
        .map((z) => z.values[i])
        .filter((x): x is number => x != null);
      low.push(v.length ? Math.min(...v) : null);
      high.push(v.length ? Math.max(...v) : null);
    }
    const gen = day.eu?.generation ?? {};
    return { low, high, solar: gen.solar ?? [], wind: gen.wind ?? [] };
  }, [day]);
  const focusFlows = selected ? arcs.filter(touches).sort((x, y) => y.mw - x.mw) : [];
  const focusPlants = selected && plants ? Object.entries(plants.by_country[selected] ?? {}).sort((x, y) => y[1][1] - x[1][1]) : [];
  const plantGroups = plants ? plants.groups.filter((g) => g !== "other") : [];
  const stops = shade === "renewable" ? SHARE_STOPS : PRICE_STOPS;
  const top = shade === "renewable" ? 100 : PRICE_MAX;
  const gradient = `linear-gradient(90deg, ${stops.map(([s, c]) => `${rgbCss(c)} ${(s / top) * 100}%`).join(", ")})`;
  const focusZones = selected ? zonesOf(selected) : [];
  const focusCapacity = selected ? reference?.capacity[selected] : undefined;
  const focusReservoir = selected ? reference?.reservoirs[selected] : undefined;
  const focusLng = selected && gas ? gas.lng.filter((g) => g[1] === selected) : [];
  const focusStorages = selected && gas ? gas.storages.filter((g) => g[1] === selected) : [];
  // phones: one sheet above the bottom bar (and above the timeline when there is one)
  const sheetClass = "absolute inset-x-2 z-20 max-h-[46vh] overflow-y-auto rounded-md border border-white/[0.09] bg-[#05070b]/95 px-4 py-3 backdrop-blur";
  const sheetBottom = day || seriesLength > 1 ? 104 : 52;

  return (
    <div className="relative h-screen w-screen overflow-hidden text-slate-100" style={{ background: SEA }}>
      <div ref={container} className="absolute inset-0" />

      <div
        className={`absolute z-10 rounded-md bg-[#05070b]/75 px-3 py-2 backdrop-blur-sm ${
          isMobile ? "left-2 right-2 top-2 flex flex-wrap items-center gap-x-2 gap-y-1.5" : "left-4 top-4"
        }`}
      >
        <div className={`font-serif uppercase leading-none tracking-[0.2em] ${isMobile ? "mr-1 text-[20px]" : "text-[34px]"}`}>
          Europe
        </div>
        {!isMobile && (
          <div className="mt-2 text-[10px] uppercase tracking-[0.32em] text-[#b9ab9b]">
            {day ? "24 hours of electricity" : "Grid, plants & cross-border flows"}
          </div>
        )}
        {/* the two views: the live map, and one real day as a time-lapse */}
        <div className={isMobile ? "contents" : "mt-3 flex flex-wrap items-center gap-2"}>
          <nav className="inline-flex rounded border border-white/15 p-0.5 text-[11px]">
            {TABS.map((t) => {
              const active = t.id === (DAY_PARAM ? "day" : "live");
              return (
                <a
                  key={t.id}
                  href={t.href}
                  className={`rounded px-2.5 py-1 ${active ? "bg-white/15 text-slate-100" : "text-slate-400 hover:text-slate-100"}`}
                >
                  {t.label}
                </a>
              );
            })}
          </nav>
          {countries && (
            <select
              value={selected ?? ""}
              onChange={(e) => setSelected(e.target.value || null)}
              className="rounded border border-white/15 bg-[#0b0e15] px-1.5 py-1 text-[11px] text-slate-200"
              aria-label="Country"
            >
              <option value="">All of Europe</option>
              {[...countries.countries]
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((c) => (
                  <option key={c.iso} value={c.iso}>
                    {c.name}
                  </option>
                ))}
            </select>
          )}
        </div>
        {day && dayList.length > 0 && (
          <div className={`flex items-center gap-1 text-[11px] ${isMobile ? "" : "mt-2"}`}>
            {(() => {
              const i = dayList.indexOf(day.date);
              const go = (d?: string) => {
                if (!d) return;
                const params = new URLSearchParams(window.location.search);
                params.set("day", d);
                params.delete("at");
                window.location.search = params.toString();
              };
              return (
                <>
                  <button
                    onClick={() => go(dayList[i - 1])}
                    disabled={i <= 0}
                    className="rounded border border-white/15 px-1.5 py-0.5 text-slate-300 disabled:opacity-30"
                    aria-label="Previous day"
                  >
                    ‹
                  </button>
                  <select
                    value={day.date}
                    onChange={(e) => go(e.target.value)}
                    className="rounded border border-white/15 bg-[#0b0e15] px-1.5 py-0.5 text-slate-200"
                    aria-label="Day"
                  >
                    {[...dayList].reverse().map((d) => (
                      <option key={d} value={d}>
                        {dayLabel(d)}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => go(dayList[i + 1])}
                    disabled={i < 0 || i >= dayList.length - 1}
                    className="rounded border border-white/15 px-1.5 py-0.5 text-slate-300 disabled:opacity-30"
                    aria-label="Next day"
                  >
                    ›
                  </button>
                </>
              );
            })()}
          </div>
        )}
        {day && dayCharts && (
          <div className={isMobile ? "w-full" : "mt-3 w-[240px]"}>
            <div className="flex items-end justify-between">
              <div
                className={`whitespace-nowrap font-light leading-none tabular-nums tracking-wide ${isMobile ? "text-[24px]" : "text-[34px]"}`}
              >
                {marketTime(slotTs(dayK))}
              </div>
              <svg width={64} height={30} className="mb-1" aria-label="sun height over Central Europe">
                <line x1={0} x2={64} y1={20} y2={20} stroke="rgba(255,255,255,0.25)" />
                <path
                  d={sunArc.map((a, i) => `${i ? "L" : "M"}${((i / (sunArc.length - 1)) * 64).toFixed(1)},${(20 - Math.max(-10, a) * 0.42).toFixed(1)}`).join("")}
                  fill="none"
                  stroke="rgba(255,214,72,0.45)"
                />
                <circle
                  cx={(dayK / Math.max(1, sunArc.length - 1)) * 64}
                  cy={20 - Math.max(-10, sunAlt) * 0.42}
                  r={3.5}
                  fill={sunAlt > 0 ? "#ffd648" : "#9aa7bd"}
                />
              </svg>
            </div>
            {!isMobile && (
              <>
            <DayChart
              title="EU solar + wind"
              unit={eu ? `${gw((eu.generation_mw.solar ?? 0) + (eu.generation_mw.wind ?? 0))}` : "GW"}
              layers={[
                { values: dayCharts.wind, color: FUEL_COLOR.wind },
                { values: dayCharts.solar, color: FUEL_COLOR.solar },
              ]}
              k={dayK}
              slots={day.slots}
            />
            <DayChart
              title="Price range, all zones"
              unit={
                dayCharts.low[dayK] != null
                  ? `${Math.round(dayCharts.low[dayK] as number)}–${Math.round(dayCharts.high[dayK] as number)} €/MWh`
                  : "€/MWh"
              }
              band={{ low: dayCharts.low, high: dayCharts.high, color: [214, 140, 96] }}
              k={dayK}
              slots={day.slots}
            />
              </>
            )}
          </div>
        )}
        <div className={`mt-3 flex flex-wrap gap-1 ${isMobile ? "hidden" : ""}`}>
          {(Object.keys(show) as Array<keyof typeof show>).map((k) => (
            <button
              key={k}
              onClick={() => setShow({ ...show, [k]: !show[k] })}
              className={`rounded border px-2 py-0.5 text-[10px] capitalize ${
                show[k] ? "border-white/25 bg-white/10 text-slate-100" : "border-white/10 text-slate-500"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
        {topFlows.length > 0 && !isMobile && (
          <div className="mt-5 w-[210px]">
            <div className="text-[9px] uppercase tracking-[0.24em] text-[#8f877e]">Largest cross-border flows</div>
            <div className="mt-2 space-y-1">
              {topFlows.map((f) => (
                <div key={`${f.from}${f.to}`} className="flex items-center justify-between text-[12px] tabular-nums">
                  <span className="tracking-[0.08em] text-slate-200">
                    {f.from} <span className="text-[#8f877e]">→</span> {f.to}
                  </span>
                  <span style={{ color: rgbCss(FLOW) }}>{gw(f.mw)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {isMobile && sheet !== "info" ? null : focus ? (
        <div
          className={
            isMobile
              ? `${sheetClass}`
              : "absolute right-5 top-16 z-10 max-h-[calc(100vh-110px)] w-[250px] overflow-y-auto rounded-md border border-white/[0.09] bg-black/60 px-4 py-3 backdrop-blur"
          }
          style={isMobile ? { bottom: sheetBottom } : undefined}
        >
          <div className="flex items-start justify-between">
            <div className="font-serif text-[20px] uppercase leading-tight tracking-[0.12em]">{focus.name}</div>
            <button onClick={() => setSelected(null)} className="text-[11px] text-slate-400 hover:text-slate-100" title="Back to Europe">
              ✕
            </button>
          </div>
          {isMobile && show.plants && (
            <div className="mt-2 flex gap-1 text-[11px]">
              {(["bars", "beams"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setPlantStyle(m)}
                  className={`rounded border px-2 py-0.5 ${
                    plantStyle === m ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400"
                  }`}
                >
                  {m === "bars" ? "Bars" : "Beams & fields"}
                </button>
              ))}
            </div>
          )}
          {focusPower ? (
            <PowerBlock power={focusPower} time={timeOf} />
          ) : (
            <div className="mt-2 text-[11px] text-[#8d94a1]">No load or generation data from Energy-Charts for this country.</div>
          )}
          {focusZones.length > 0 && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">
                Day-ahead price · {timeOf(focusZones[0][1].ts)}
              </div>
              <div className="mt-1.5 space-y-0.5">
                {focusZones.map(([zone, pr]) => (
                  <div key={zone} className="flex justify-between text-[11px] tabular-nums text-slate-200">
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-sm" style={{ background: rgbCss(priceColor(pr.eur_mwh)) }} />
                      {zone}
                    </span>
                    <span>{pr.eur_mwh.toFixed(1)} €/MWh</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {focusFlows.length > 0 && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Cross-border physical flows</div>
              <div className="mt-1.5 space-y-0.5">
                {focusFlows.map((f) => {
                  const out = f.from === selected;
                  return (
                    <div key={`${f.from}${f.to}`} className="flex justify-between text-[11px] tabular-nums">
                      <span className="text-slate-200">
                        <span style={{ color: out ? rgbCss(FLOW) : "#f0b37e" }}>{out ? "export →" : "import ←"}</span>{" "}
                        {out ? f.to : f.from}
                      </span>
                      <span>{power(f.mw)}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
          {focusCapacity && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">
                Installed capacity · {focusCapacity.year}
              </div>
              <div className="mt-1.5 space-y-1">
                {Object.entries(focusCapacity.gw)
                  .filter(([, v]) => v > 0)
                  .sort((x, y) => y[1] - x[1])
                  .map(([g, v], _, all) => (
                    <div key={g}>
                      <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
                        <span>{FUEL_LABEL[g] ?? g}</span>
                        <span>{v.toFixed(1)} GW</span>
                      </div>
                      <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${(v / all[0][1]) * 100}%`, background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </>
          )}
          {focusReservoir && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Hydro reservoirs</div>
              <div className="mt-1 text-[11px] text-slate-200">
                <span className="text-[16px] font-light tabular-nums">{focusReservoir.twh.toFixed(1)} TWh</span> stored, week of{" "}
                {focusReservoir.week}
              </div>
              {focusReservoir.year_ago_twh != null && (
                <div className="text-[10px] text-[#8d94a1]">same week last year: {focusReservoir.year_ago_twh.toFixed(1)} TWh</div>
              )}
            </>
          )}
          {(focusLng.length > 0 || focusStorages.length > 0) && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Gas infrastructure (2021 dataset)</div>
              {focusLng.length > 0 && (
                <div className="mt-1 text-[11px] text-slate-200">
                  LNG terminals: <span className="text-[#8d94a1]">{focusLng.map((g) => g[0]).join(", ")}</span>
                </div>
              )}
              {focusStorages.length > 0 && (
                <div className="mt-0.5 text-[11px] text-slate-200">Gas storage sites: {focusStorages.length}</div>
              )}
            </>
          )}
          {focusPlants.length > 0 && (
            <>
              <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Plants on the map (units ≥ 1 MW)</div>
              <div className="mt-1 text-[10px] text-[#8d94a1]">
                {plantStyle === "bars"
                  ? "Columns: units ≥ 10 MW, height ∝ √ installed capacity (not current output)"
                  : `Beams: plants ≥ ${BEAM_MIN_MW} MW, height ∝ √ installed capacity. Fields: smaller units summed per ${HEX_KM * 2} km hexagon, coloured by the largest fuel.`}
              </div>
              <div className="mt-1.5 space-y-0.5">
                {focusPlants.map(([g, [n, mw]]) => (
                  <div key={g} className="flex justify-between text-[11px] tabular-nums text-slate-200">
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(FUEL_COLOR[g]) }} />
                      {PLANT_LABEL[g]}
                    </span>
                    <span>
                      {power(mw)} <span className="text-[#8d94a1]">· {n}</span>
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ) : (
        eu && (
          <div
            className={
              isMobile
                ? sheetClass
                : "pointer-events-none absolute right-5 top-16 z-10 w-[230px] rounded-md border border-white/[0.07] bg-black/45 px-4 py-3 backdrop-blur"
            }
            style={isMobile ? { bottom: sheetBottom } : undefined}
          >
            <div className="text-[9px] uppercase tracking-[0.24em] text-[#8f877e]">European Union</div>
            <PowerBlock power={eu} time={timeOf} />
            {day && ranking.length > 0 && (
              <>
                <div className="mt-4 text-[9px] uppercase tracking-[0.16em] text-[#8d94a1]">Largest producers now</div>
                <div className="mt-1.5 space-y-1">
                  {ranking.map((c) => (
                    <div key={c.iso} className="flex items-center gap-2 text-[11px] tabular-nums">
                      <span className="w-6 text-slate-300">{c.iso}</span>
                      <div className="flex h-[7px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
                        {c.parts.map(([g, v]) => (
                          <div
                            key={g}
                            style={{ width: `${(v / ranking[0].total) * 100}%`, background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }}
                          />
                        ))}
                      </div>
                      <span className="w-12 text-right text-slate-200">{gw(c.total)}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
            <div className="mt-3 text-[10px] text-[#8d94a1]">Click a country for its figures and flows.</div>
          </div>
        )
      )}

      <div
        className={
          isMobile
            ? `${sheetClass} space-y-3 text-[11px] text-slate-300 ${sheet === "legend" ? "" : "hidden"}`
            : "pointer-events-none absolute bottom-4 left-4 z-10 w-[270px] space-y-3 rounded-md bg-[#05070b]/70 px-3 py-3 text-[11px] text-slate-300 backdrop-blur-sm"
        }
        style={isMobile ? { bottom: sheetBottom } : undefined}
      >
        {isMobile && (
          <div>
            <div className="text-[9px] uppercase tracking-[0.18em] text-[#8d94a1]">Layers</div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {(Object.keys(show) as Array<keyof typeof show>).map((k) => (
                <button
                  key={k}
                  onClick={() => setShow({ ...show, [k]: !show[k] })}
                  className={`rounded border px-2.5 py-1 text-[11px] capitalize ${
                    show[k] ? "border-white/25 bg-white/10 text-slate-100" : "border-white/10 text-slate-500"
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
          </div>
        )}
        {(stats || day) && (
          <div>
            <div className="pointer-events-auto flex gap-1">
              {(["none", "renewable", "price"] as const).filter((m) => m !== "none" || day).map((m) => (
                <button
                  key={m}
                  onClick={() => setShade(m)}
                  className={`rounded border px-2 py-0.5 text-[10px] ${
                    shade === m ? "border-white/25 bg-white/10 text-slate-100" : "border-white/10 text-slate-500"
                  }`}
                >
                  {m === "none" ? "None" : m === "renewable" ? "Renewable share" : "Price"}
                </button>
              ))}
            </div>
            {shade !== "none" && <div className="mt-1.5 h-2 rounded-sm" style={{ background: gradient }} />}
            <div className={`mt-0.5 flex justify-between text-[9px] text-[#8d94a1] ${shade === "none" ? "hidden" : ""}`}>
              {shade === "renewable" ? (
                <>
                  <span>0 %</span>
                  <span>50 %</span>
                  <span>100 % of generation</span>
                </>
              ) : (
                <>
                  <span>0</span>
                  <span>125</span>
                  <span>≥ 250 €/MWh</span>
                </>
              )}
            </div>
            {shade === "price" && (
              <div className="mt-1 flex items-center gap-2 text-[9px] text-[#8d94a1]">
                <span className="h-2 w-3 rounded-sm" style={{ background: rgbCss(MULTI_ZONE) }} />
                several price zones (DK, IT, NO, SE): click for each zone
              </div>
            )}
          </div>
        )}
        {day && (
          <div>
            <div className="mb-1.5 text-[11px] leading-snug text-slate-300">
              Each tower is one country's power generation at the time on the clock, stacked by source.
            </div>
            <div className="text-[9px] uppercase tracking-[0.18em] text-[#8d94a1]">Sources (1 GW = 14 km of height)</div>
            <div className="mt-1.5 grid grid-cols-3 gap-x-3 gap-y-1">
              {[...TOWER_ORDER].reverse().map((g) => (
                <div key={g} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm" style={{ background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }} />
                  {FUEL_LABEL[g] === "Bioenergy & waste" ? "Bio & waste" : FUEL_LABEL[g] === "Coal & lignite" ? "Coal" : FUEL_LABEL[g]}
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="h-2 w-5 rounded-sm" style={{ background: "linear-gradient(90deg, rgba(2,5,18,0.75), transparent)" }} />
              Night (sun below the horizon)
            </div>
          </div>
        )}
        <div className={`grid grid-cols-2 gap-x-4 gap-y-1 ${day && !show.plants ? "hidden" : ""}`}>
          {plantGroups.map((g) => (
            <div key={g} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(FUEL_COLOR[g]) }} />
              {PLANT_LABEL[g]}
            </div>
          ))}
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="h-[3px] w-5 rounded" style={{ background: `linear-gradient(90deg, transparent, ${rgbCss(FLOW)})` }} />
            Cross-border flow
          </div>
          <div className="flex items-center gap-2">
            <span className="h-[2px] w-5 rounded" style={{ background: rgbCss(VOLTAGE_BANDS[0].color) }} />
            Transmission line ≥ 220 kV
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 border-t border-dashed" style={{ borderColor: rgbCss(HVDC) }} />
            HVDC link
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 border-t border-dashed" style={{ borderColor: rgbCss(GAS_PIPE) }} />
            Gas pipeline (zoomed in)
          </div>
          <div className="flex items-center gap-2">
            <span className="flex w-5 justify-center">
              <span className="h-2 w-2 rounded-full border border-white" style={{ background: rgbCss(GAS) }} />
            </span>
            LNG terminal
            <span className="ml-2 h-2 w-2 rounded-full border" style={{ borderColor: rgbCss(GAS) }} />
            gas storage
          </div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: rgbCss(SUBSTATION) }} />
            Substation ≥ 220 kV (zoomed in)
          </div>
        </div>
      </div>

      {focus && show.plants && !isMobile && (
        <div className="absolute left-1/2 top-4 z-10 flex -translate-x-1/2 items-center gap-2 rounded-md border border-white/[0.1] bg-[#05070b]/80 px-3 py-1.5 text-[11px] text-slate-300 backdrop-blur">
          <span className="text-[9px] uppercase tracking-[0.2em] text-[#8d94a1]">3D style</span>
          {(["bars", "beams"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setPlantStyle(m)}
              className={`rounded border px-2.5 py-0.5 text-[11px] ${
                plantStyle === m ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400 hover:text-slate-200"
              }`}
            >
              {m === "bars" ? "Bars" : "Beams & fields"}
            </button>
          ))}
        </div>
      )}

      {day && captions.length > 0 && !selected && (
        <div
          className={`pointer-events-none absolute z-10 flex flex-col items-center gap-2 ${
            isMobile ? "inset-x-2 bottom-[104px]" : "left-1/2 top-6 -translate-x-1/2"
          }`}
        >
          {captions.map((h) => {
            const c = captionText(h, countryName);
            const age = daySlot.current - h.slot;
            const alpha = Math.min(1, age / 0.6, (CAPTION_SLOTS - age) / 2);
            return (
              <div
                key={h.kind}
                className={`rounded-lg border border-white/[0.1] bg-[#05070b]/80 text-center backdrop-blur ${
                  isMobile ? "w-full px-3 py-2" : "min-w-[340px] px-5 py-3"
                }`}
                style={{ opacity: alpha, transform: `translateY(${(1 - Math.min(1, age / 0.6)) * -8}px)` }}
              >
                <div className="text-[10px] uppercase tracking-[0.28em]" style={{ color: rgbCss(c.color) }}>
                  {marketTime(slotTs(h.slot))} · {c.title}
                </div>
                <div className={`mt-1 font-light text-slate-100 ${isMobile ? "text-[14px]" : "text-[17px]"}`}>{c.text}</div>
              </div>
            );
          })}
        </div>
      )}

      {day && (
        <div
          className={`absolute z-10 flex items-center gap-3 rounded-md border border-white/[0.08] bg-[#05070b]/80 px-3 py-2 text-[11px] text-slate-200 backdrop-blur ${
            isMobile ? "inset-x-2 bottom-12" : "bottom-12 left-1/2 w-[560px] -translate-x-1/2"
          }`}
        >
          <button
            onClick={() => {
              if (!dayPlaying.current && daySlot.current >= day.slots - 1) daySlot.current = 0;
              dayPlaying.current = !dayPlaying.current;
            }}
            className="w-14 rounded border border-white/20 px-2 py-0.5 text-[10px] hover:bg-white/10"
          >
            {dayPlaying.current ? "Pause" : "▶ Play"}
          </button>
          <div className="relative flex-1">
            {(day.highlights ?? []).map((h) => (
              <span
                key={h.kind}
                title={captionText(h, countryName).title}
                className="pointer-events-none absolute -top-2 h-1.5 w-1.5 -translate-x-1/2 rounded-full"
                style={{ left: `${(h.slot / (day.slots - 1)) * 100}%`, background: rgbCss(captionText(h, countryName).color) }}
              />
            ))}
          <input
            type="range"
            min={0}
            max={day.slots - 1}
            value={dayK}
            onChange={(e) => {
              dayPlaying.current = false;
              daySlot.current = Number(e.target.value);
            }}
            className="w-full accent-sky-300"
          />
          </div>
          <span className={`text-right tabular-nums text-[#aab3c0] ${isMobile ? "w-[72px]" : "w-[112px]"}`}>
            {marketTime(slotTs(dayK))}
          </span>
        </div>
      )}

      {seriesLength > 1 && !day && (
        <div
          className={`absolute z-10 flex items-center gap-3 rounded-md border border-white/[0.08] bg-[#05070b]/80 px-3 py-2 text-[11px] text-slate-200 backdrop-blur ${
            isMobile ? "inset-x-2 bottom-12" : "bottom-12 left-1/2 w-[440px] -translate-x-1/2"
          }`}
        >
          <button
            onClick={() => {
              if (!playing && replay == null) setReplay(0);
              setPlaying(!playing);
            }}
            className="w-14 rounded border border-white/20 px-2 py-0.5 text-[10px] hover:bg-white/10"
          >
            {playing ? "Pause" : "▶ 24 h"}
          </button>
          <input
            type="range"
            min={0}
            max={seriesLength - 1}
            value={replay ?? seriesLength - 1}
            onChange={(e) => {
              setPlaying(false);
              const k = Number(e.target.value);
              setReplay(k >= seriesLength - 1 ? null : k);
            }}
            className="flex-1 accent-sky-300"
          />
          <span className="w-[112px] text-right tabular-nums text-[#aab3c0]">
            {replay == null ? "latest interval" : `flows ${utc(replayTs(replay))}`}
          </span>
        </div>
      )}

      <div
        className={
          isMobile
            ? `${sheetClass} text-[10px] leading-relaxed text-[#9a938c] ${sheet === "sources" ? "" : "hidden"}`
            : "pointer-events-none absolute bottom-4 right-5 z-10 text-right text-[9px] leading-relaxed text-[#77706a]"
        }
        style={isMobile ? { bottom: sheetBottom } : undefined}
      >
        <div>Grid: PyPSA-Eur network from © OpenStreetMap contributors (ODbL) · Plants ≥ 20 MW: powerplantmatching</div>
        <div>
          Flows, load, generation, renewable share, prices, installed capacity: Energy-Charts (Fraunhofer ISE) from ENTSO-E data ·
          Reservoirs: ENTSO-E · Gas: SciGRID_gas (2021) · Borders: © EuroGeographics
        </div>
      </div>
      {isMobile && (
        <div className="absolute inset-x-2 bottom-2 z-20 flex gap-1 text-[11px]">
          {(
            [
              ["info", focus ? focus.name : "Europe now"],
              ["legend", "Legend"],
              ["sources", "Sources"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setSheet(sheet === id ? "none" : id)}
              className={`flex-1 truncate rounded-md border px-2 py-2 backdrop-blur ${
                sheet === id ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 bg-[#05070b]/80 text-slate-300"
              }`}
            >
              {label} {sheet === id ? "▾" : "▴"}
            </button>
          ))}
        </div>
      )}
      {CAPTURE && tour.current.started != null && <TourCursor tour={tour.current} />}
      {(error || !grid) && (
        <div className="absolute inset-0 z-20 flex items-center justify-center text-sm text-slate-400">
          {error ?? "loading European grid…"}
        </div>
      )}
    </div>
  );
}
