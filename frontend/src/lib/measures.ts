// Variables the map can draw as hexagons at country scale (and two of them as a bivariate map):
// one value per record of a dataset's own files, summed per hexagon by map/hexLayers.ts. Each says
// what it sums; nothing is estimated.

import { gbSiteTotals, type ConnectFile } from "./connect";
import type { CtraceFile } from "./ctrace";
import { FUEL_COLOR, FUEL_LABEL } from "./energy";
import type { EtsFile } from "./ets";
import type { EvChargersFile } from "./evChargers";
import type { EvEuFile } from "./evEu";
import type { GhgrpFile } from "./ghgrp";
import type { MastrMuniFile } from "./mastr";
import { REGISTER_LAYERS, registerKey, type RegisterFile } from "./registers";
import type { RGB } from "./theme";
import { US_TYPE_COLOR, US_TYPE_LABEL, type UsPlantsFile, type UsTurbinesFile } from "./us";
import type { UsSolarFile } from "./usSolar";
import type { DataCentresFile } from "./world";
import { PLANT_TYPE_COLOR, PLANT_TYPE_LABEL, type WorldPlantsFile } from "./worldPlants";
import type { GridFile, PlantsFile } from "../app/types";
import type { AtlasFile } from "./atlas";
import type { HydrogenFile } from "./coming";
import { NL_COLOR } from "./connect";
import { CONNECT_EU, connectEuKey, type ConnectEuFile } from "./connectEu";
import type { ConstraintsFile } from "./constraints";
import { GEM_POINTS, type GemPointsFile } from "./gem";
import type { OffshoreWindFile } from "./offshoreWind";
import type { GridSpec } from "./area";

/** [lon, lat, value, type label] */
export type Pt = [number, number, number, string];
type Files = Record<string, unknown>;

export interface Measure {
  id: string;
  /** the dataset it belongs to (app/datasets.json) */
  dataset: string;
  label: string;
  unit: string;
  /** what a hexagon's figure is, for the key */
  sums: string;
  /** files it reads */
  files: string[];
  color: RGB;
  /** type colours, when the hexagons are coloured by their largest type */
  types?: Record<string, RGB>;
  typeColor?: (type: string) => RGB;
  /** the unit from the file, when it varies by file */
  unitOf?: (f: Files) => string;
  points: (f: Files) => Pt[] | null;
  fmt: (v: number) => string;
}

const mw = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v)} MW`);
const t = (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(2)} Mt` : `${Math.round(v / 1000).toLocaleString("en-US")} kt`);
const n = (v: number) => Math.round(v).toLocaleString("en-US");
const fuelTypes: Record<string, RGB> = {
  ...Object.fromEntries(Object.entries(FUEL_LABEL).map(([k, l]) => [l, FUEL_COLOR[k]])),
  ...Object.fromEntries(Object.entries(US_TYPE_LABEL).map(([k, l]) => [l, US_TYPE_COLOR[k] ?? FUEL_COLOR.other])),
  ...Object.fromEntries(Object.entries(PLANT_TYPE_LABEL).map(([k, l]) => [l, PLANT_TYPE_COLOR[k] ?? FUEL_COLOR.other])),
};

export const MEASURES: Measure[] = [
  {
    id: "plants-mw",
    dataset: "plants",
    label: "Operating capacity",
    unit: "MW",
    sums: "MW of operating plants (Europe: powerplantmatching, units of 20 MW and more; US: EIA-860M; elsewhere: Global Energy Monitor)",
    files: ["plants", "usPlants", "worldPlants"],
    color: [255, 128, 72],
    types: fuelTypes,
    points: (f) => {
      const eu = f.plants as PlantsFile | undefined;
      const us = f.usPlants as UsPlantsFile | undefined;
      const gem = f.worldPlants as WorldPlantsFile | undefined;
      if (!eu && !us && !gem) return null;
      const out: Pt[] = [];
      if (eu) for (const p of eu.plants) out.push([p[2], p[3], p[1], FUEL_LABEL[eu.groups[p[0]]] ?? eu.groups[p[0]]]);
      if (us) {
        const op = us.statuses.indexOf("operating");
        for (const p of us.points) if (p[3] === op) out.push([p[0], p[1], p[4], US_TYPE_LABEL[us.types[p[2]]] ?? us.types[p[2]]]);
      }
      if (gem) {
        const op = gem.statuses.indexOf("operating");
        // Europe's and the US files hold those regions (their boxes; the GEM points inside are left out)
        for (const p of gem.points) {
          if (p[3] !== op) continue;
          if (eu && p[0] > -25 && p[0] < 45 && p[1] > 34 && p[1] < 72) continue;
          if (us && p[0] < -64 && p[0] > -170 && p[1] > 17) continue;
          out.push([p[0], p[1], p[4], PLANT_TYPE_LABEL[gem.types[p[2]]] ?? gem.types[p[2]]]);
        }
      }
      return out;
    },
    fmt: mw,
  },
  {
    id: "registers-mw",
    dataset: "registers",
    label: "Units in national registers",
    unit: "MW",
    sums: "MW of operating units in the national registers (MaStR per municipality, REPD, Energistyrelsen, Vindbrukskollen, SEAI, DGEG; US: USWTDB, USPVDB)",
    files: ["mastrMuni", ...Object.values(REGISTER_LAYERS).map(registerKey), "usTurbines", "usSolar"],
    color: [255, 214, 72],
    types: fuelTypes,
    points: (f) => {
      const out: Pt[] = [];
      const muni = f.mastrMuni as MastrMuniFile | undefined;
      if (muni)
        for (const g of muni.gemeinden)
          if (g.label) muni.techs.forEach((tech, i) => g.mw[i] > 0 && out.push([g.label![0], g.label![1], g.mw[i], FUEL_LABEL[tech] ?? tech]));
      for (const cc of Object.values(REGISTER_LAYERS)) {
        const r = f[registerKey(cc)] as RegisterFile | undefined;
        if (r) for (const p of r.points) if (p[5] === "operating" && p[4]) out.push([p[1], p[2], p[4], FUEL_LABEL[p[3] === "wind_offshore" ? "wind" : p[3]] ?? p[3]]);
      }
      const tu = f.usTurbines as UsTurbinesFile | undefined;
      if (tu) for (let i = 0; i < tu.lon.length; i++) if (tu.kw[i]) out.push([tu.lon[i], tu.lat[i], (tu.kw[i] ?? 0) / 1000, FUEL_LABEL.wind]);
      const so = f.usSolar as UsSolarFile | undefined;
      if (so) for (const x of so.sites) if (x[0] != null && x[1] != null && x[2]) out.push([x[0], x[1], x[2], FUEL_LABEL.solar]);
      return out.length ? out : null;
    },
    fmt: mw,
  },
  {
    id: "emitters-t",
    dataset: "emitters",
    label: "Verified CO₂",
    unit: "t",
    sums: "t CO₂ verified (EU ETS installations with a position, newest year; US: EPA GHGRP CO₂e)",
    files: ["ets", "ghgrp"],
    color: [236, 128, 92],
    points: (f) => {
      const e = f.ets as EtsFile | undefined;
      const g = f.ghgrp as GhgrpFile | undefined;
      if (!e && !g) return null;
      const out: Pt[] = [];
      if (e) {
        const k = e.years.indexOf(e.newest);
        for (const r of e.rows) if (r[5] != null && r[6] != null && r[4][k]) out.push([r[5], r[6], r[4][k]!, e.groups[r[3]] ?? ""]);
      }
      if (g) for (const p of g.points) out.push([p[0], p[1], p[2], g.sectors[p[3]] ?? ""]);
      return out;
    },
    fmt: t,
  },
  {
    id: "ctrace-t",
    dataset: "ctrace",
    label: "Modelled CO₂e",
    unit: "t",
    sums: "t CO₂e modelled by Climate TRACE per facility",
    files: ["ctrace"],
    color: [255, 196, 96],
    points: (f) => {
      const c = f.ctrace as CtraceFile | undefined;
      return c ? c.rows.map((r) => [r[0], r[1], r[5], ""] as Pt) : null;
    },
    fmt: t,
  },
  {
    id: "ev-n",
    dataset: "ev",
    label: "Charging points",
    unit: "points",
    sums: "public charging points (Europe: per 0.1° cell, registers and OpenStreetMap; US: DC fast ports, NREL AFDC)",
    files: ["evEu", "evChargers"],
    color: [96, 214, 255],
    points: (f) => {
      const eu = f.evEu as EvEuFile | undefined;
      const us = f.evChargers as EvChargersFile | undefined;
      if (!eu && !us) return null;
      const out: Pt[] = [];
      if (eu) for (const cells of Object.values(eu.cells)) for (const c of cells) out.push([c[0], c[1], c[2], ""]);
      if (us) for (const p of us.points) out.push([p[0], p[1], p[2], ""]);
      return out;
    },
    fmt: n,
  },
  {
    id: "dc-n",
    dataset: "dataCentres",
    label: "Data centres",
    unit: "sites",
    sums: "data centres mapped in OpenStreetMap",
    files: ["datacentres"],
    color: [196, 150, 255],
    points: (f) => {
      const d = f.datacentres as DataCentresFile | undefined;
      return d ? d.points.map((p) => [p[0], p[1], 1, ""] as Pt) : null;
    },
    fmt: n,
  },
  {
    id: "gb-waiting",
    dataset: "capacity",
    label: "Waiting to connect (GB)",
    unit: "MW",
    sums: "MW of projects not yet connected per transmission site (NESO TEC register)",
    files: ["connect"],
    color: [206, 138, 72],
    points: (f) => {
      const c = f.connect as ConnectFile | undefined;
      return c ? gbSiteTotals(c.gb).map((x) => [x.site[1] as number, x.site[2] as number, x.mw, ""] as Pt) : null;
    },
    fmt: mw,
  },
];


// ------------------------------------------------------------------ every point dataset has a figure

const SUM_SIZES: Record<string, string> = { gemChemicals: "", gemFields: "" };
function gemMeasure(dataset: string, label: string, plural: string): Measure {
  const style = GEM_POINTS[dataset];
  const sized = !(style.file in SUM_SIZES);
  return {
    id: `${dataset}-gem`,
    dataset,
    label,
    unit: sized ? "" : plural,
    sums: sized ? `${label.toLowerCase()} of the operating ${plural} (Global Energy Monitor)` : `operating ${plural} (Global Energy Monitor, a count)`,
    files: [style.file],
    color: style.color(""),
    typeColor: (t) => style.color(t),
    points: (f) => {
      const g = f[style.file] as GemPointsFile | undefined;
      if (!g) return null;
      const op = g.classes.indexOf("operating");
      return g.points.filter((p) => p[3] === op).map((p) => [p[0], p[1], sized ? (p[4] ?? 0) : 1, g.kinds[p[2]] ?? ""] as Pt);
    },
    fmt: (v) => (sized ? `${v >= 100 ? Math.round(v).toLocaleString("en-US") : v.toFixed(1)}` : n(v)),
    unitOf: (f) => ((f[style.file] as GemPointsFile | undefined)?.unit ?? ""),
  };
}

MEASURES.push(
  gemMeasure("steel", "Crude steel capacity", "steel plants"),
  gemMeasure("cement", "Cement capacity", "cement plants"),
  gemMeasure("chemicals", "Chemical plants", "chemical plants"),
  gemMeasure("ironOre", "Iron ore production", "iron ore mines"),
  gemMeasure("lngTerminals", "LNG capacity", "LNG terminals"),
  gemMeasure("coalTerminals", "Coal port capacity", "coal ports"),
  gemMeasure("oilGasFields", "Oil and gas fields", "fields"),
  gemMeasure("coalMines", "Coal mine capacity", "coal mines"),
  gemMeasure("methane", "Methane emission rate", "plumes"),
  {
    id: "h2-mw",
    dataset: "hydrogen",
    label: "Electrolysis",
    unit: "MW",
    sums: "MW of the hydrogen projects where given (European Hydrogen Observatory)",
    files: ["hydrogen"],
    color: [96, 214, 255],
    points: (f) => {
      const h = f.hydrogen as HydrogenFile | undefined;
      return h ? h.projects.map((p) => [p[8], p[9], p[4] ?? 0, p[10] != null ? (h.stages[p[10]] ?? "") : ""] as Pt) : null;
    },
    fmt: mw,
  },
  {
    id: "offshore-mw",
    dataset: "offshoreWind",
    label: "Offshore wind",
    unit: "MW",
    sums: "MW of the offshore wind farm areas where given, every status (EMODnet)",
    files: ["offshoreWind"],
    color: [96, 190, 255],
    points: (f) => {
      const o = f.offshoreWind as OffshoreWindFile | undefined;
      return o ? o.farms.map((x) => [x.at[0], x.at[1], x.mw ?? 0, x.status != null ? (o.statuses[x.status] ?? "") : ""] as Pt) : null;
    },
    fmt: mw,
  },
  {
    id: "subs-n",
    dataset: "substations",
    label: "Substations",
    unit: "",
    sums: "substations of 220 kV and more (PyPSA-Eur from OpenStreetMap, a count)",
    files: ["grid"],
    color: [226, 232, 240],
    points: (f) => {
      const g = f.grid as GridFile | undefined;
      return g ? g.substations.map((x) => [x[1], x[2], 1, x[0] >= 380 ? "380 kV and more" : "220–379 kV"] as Pt) : null;
    },
    typeColor: (t) => (t.startsWith("380") ? [236, 178, 120] : [176, 120, 82]),
    fmt: n,
  },
  {
    id: "connect-points",
    dataset: "capacity",
    label: "Grid capacity points",
    unit: "",
    sums: "points each grid operator publishes, in its class (the operators' capacity maps, a count)",
    files: CONNECT_EU.map(connectEuKey),
    color: [206, 138, 72],
    typeColor: (t) => NL_COLOR[CAPACITY_CLASSES.indexOf(t)] ?? [150, 154, 166],
    points: (f) => {
      const out: Pt[] = [];
      for (const id of CONNECT_EU) {
        const c = f[connectEuKey(id)] as ConnectEuFile | undefined;
        if (!c) continue;
        for (const p of c.points) {
          const k = p[5];
          const n4 = c.classes.length;
          const idx = k < 0 ? -1 : n4 === 4 ? k : n4 === 2 ? (k === 0 ? 0 : 3) : n4 === 3 ? [0, 1, 3][k] : Math.min(3, k);
          out.push([p[1], p[2], 1, CAPACITY_CLASSES[idx] ?? "no class"]);
        }
      }
      return out.length ? out : null;
    },
    fmt: n,
  },
);

/** The four classes every capacity map is drawn in (most room first). */
export const CAPACITY_CLASSES = ["room", "some room", "little room", "no room"];

// ------------------------------------------------------------------ continuous data (rasters)

/** A lookup grid read by range request for an area (lib/rasterCache.ts). */
export interface RasterDef {
  spec: GridSpec;
  /** a cell's value in the source unit; null where the grid has none */
  value: (v: DataView, off: number) => number | null;
}
export interface RasterMeasure {
  id: string;
  dataset: string;
  label: string;
  unit: string;
  sums: string;
  files: string[];
  color: RGB;
  /** low to high */
  ramp: RGB[];
  grid: (f: Files) => RasterDef | null;
  fmt: (v: number) => string;
}
const atlasGrid =
  (k: "pvout" | "wind") =>
  (f: Files): RasterDef | null => {
    const a = (f.atlas as AtlasFile | undefined)?.[k];
    if (!a) return null;
    const l = a.lookup;
    return {
      spec: { url: l.url, bytes: 2, width: l.width, height: l.height, origin: l.origin, cell: l.cell_deg },
      value: (v, off) => {
        const x = v.getInt16(off, true);
        return x === l.nodata ? null : x / a.scale;
      },
    };
  };
export const RASTERS: RasterMeasure[] = [
  {
    id: "pvout",
    dataset: "solarResource",
    label: "Solar resource",
    unit: "kWh/kWp per day",
    sums: "PV output per kWp installed, long-term average (Global Solar Atlas, 0.1° cells)",
    files: ["atlas"],
    color: [240, 196, 112],
    ramp: [
      [70, 52, 40],
      [150, 96, 52],
      [214, 150, 70],
      [246, 206, 112],
      [255, 240, 180],
    ],
    grid: atlasGrid("pvout"),
    fmt: (v) => v.toFixed(2),
  },
  {
    id: "wind100",
    dataset: "windResource",
    label: "Wind speed at 100 m",
    unit: "m/s",
    sums: "mean wind speed at 100 m (Global Wind Atlas, 0.1° cells)",
    files: ["atlas"],
    color: [128, 206, 206],
    ramp: [
      [36, 52, 64],
      [44, 98, 116],
      [64, 150, 160],
      [118, 200, 196],
      [200, 240, 230],
    ],
    grid: atlasGrid("wind"),
    fmt: (v) => v.toFixed(1),
  },
  {
    id: "flood",
    dataset: "flood",
    label: "River flood hazard",
    unit: "% of cells",
    sums: "share of the hazard map's cells with any water depth in a 100-year flood (JRC)",
    files: ["constraints"],
    color: [60, 130, 210],
    ramp: [
      [30, 40, 60],
      [40, 70, 120],
      [56, 104, 176],
      [90, 150, 220],
      [170, 210, 250],
    ],
    grid: (f) => {
      const c = f.constraints as ConstraintsFile | undefined;
      if (!c) return null;
      const l = c.flood.maps.world.lookup;
      return {
        spec: { url: l.url, bytes: 1, width: l.width, height: l.height, origin: l.origin, cell: l.cell_deg },
        value: (v, off) => {
          const x = v.getUint8(off);
          return x === 255 ? null : x > 0 ? 100 : 0;
        },
      };
    },
    fmt: (v) => `${v.toFixed(0)} %`,
  },
];
export const RASTER_BY_DATASET = new Map(RASTERS.map((r) => [r.dataset, r]));
/** A dataset's figure for the styles (capacity: the operators' points, not the GB queue). */
export const measureOfDataset = (d: string) => MEASURES.find((m) => m.dataset === d && m.id !== "gb-waiting") ?? MEASURES.find((m) => m.dataset === d);

export const MEASURE_BY_ID = new Map(MEASURES.map((m) => [m.id, m]));
export const measuresOf = (dataset: string) => MEASURES.filter((m) => m.dataset === dataset);
/** The colour of a record's type for a measure. */
export const typeColour = (m: Measure, t: string): RGB => m.typeColor?.(t) ?? m.types?.[t] ?? m.color;
