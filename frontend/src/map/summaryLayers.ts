// The continent picture of a dataset: at country scale, while the countries are not coloured by
// something else, each country carries the dataset's own per-country figure (shaded in the
// dataset's colour by its rank, the value under the country's name). Zoomed in, the points take
// over. Every figure is the file's per-country total or a sum of its records by country, said in
// the Datasets panel's key (SUMMARY_TEXT).

import type { Layer } from "@deck.gl/core";
import { SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { DATASETS, datasetOn, type Dataset } from "../app/datasets";
import type { CountriesFile, ReferenceFile, WorldFile } from "../app/types";
import type { CtraceFile } from "../lib/ctrace";
import type { EtsFile } from "../lib/ets";
import type { EvEuFile } from "../lib/evEu";
import type { OffshoreWindFile } from "../lib/offshoreWind";
import { ISO3 } from "../lib/transition";
import type { DataCentresFile } from "../lib/world";
import type { WorldPlantsFile } from "../lib/worldPlants";
import type { Frame } from "./build";
import { memo } from "./memo";

type Ring = [number, number][];
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
/** Country scale: below this zoom the countries carry the figure. */
export const SUMMARY_MAX_ZOOM = 5.4;
const iso3 = (iso2: string) => ISO3[iso2] ?? ({ CY: "CYP", MT: "MLT" } as Record<string, string>)[iso2];

interface Summary {
  /** what the figure is, for the key */
  text: (f: Record<string, unknown>) => string;
  values: (f: Record<string, unknown>) => Map<string, number> | null;
  label: (v: number) => string;
}

const intText = (v: number) => Math.round(v).toLocaleString("en-US");

/** The datasets with a per-country figure. */
export const SUMMARIES: Record<string, Summary> = {
  emitters: {
    text: (f) => `verified CO₂ ${(f.ets as EtsFile | undefined)?.newest ?? ""} per country, every installation (EU ETS registry totals)`,
    values: (f) => {
      const ets = f.ets as EtsFile | undefined;
      if (!ets) return null;
      const k = ets.years.indexOf(ets.newest);
      return new Map(Object.entries(ets.countries).flatMap(([c, v]) => (iso3(c) && v.t[k] ? [[iso3(c), v.t[k]] as [string, number]] : [])));
    },
    label: (t) => `${(t / 1e6).toFixed(t >= 1e7 ? 0 : 1)} Mt`,
  },
  plants: {
    text: () => "installed capacity per country: ENTSO-E (A68) in Europe, Global Energy Monitor's operating plants elsewhere",
    values: (f) => {
      const ref = f.reference as ReferenceFile | undefined;
      const gem = f.worldPlants as WorldPlantsFile | undefined;
      if (!ref && !gem) return null;
      const m = new Map<string, number>();
      for (const [c, types] of Object.entries(gem?.countries ?? {})) {
        const op = Object.values(types.operating ?? {}).reduce((a, b) => a + b, 0);
        if (op > 0) m.set(c, op / 1000);
      }
      for (const [c, v] of Object.entries(ref?.capacity ?? {})) if (iso3(c)) m.set(iso3(c), Object.values(v.gw).reduce((a, b) => a + b, 0));
      return m;
    },
    label: (gw) => `${gw >= 10 ? Math.round(gw) : gw.toFixed(1)} GW`,
  },
  ev: {
    text: () => "public charging points per country, newest year (EAFO)",
    values: (f) => {
      const ev = f.evEu as EvEuFile | undefined;
      if (!ev) return null;
      const m = new Map<string, number>();
      for (const [c, v] of Object.entries(ev.eafo.countries)) {
        const k = v.years.length - 1;
        const n = (v.ac[k] ?? 0) + (v.dc[k] ?? 0);
        if (iso3(c) && n > 0) m.set(iso3(c), n);
      }
      return m;
    },
    label: intText,
  },
  dataCentres: {
    text: () => "data centres per country, mapped in OpenStreetMap",
    values: (f) => {
      const dc = f.datacentres as DataCentresFile | undefined;
      return dc ? new Map(Object.entries(dc.by_country).filter(([, n]) => n > 0)) : null;
    },
    label: intText,
  },
  ctrace: {
    text: () => "modelled CO₂e of the facilities per country (Climate TRACE, summed)",
    values: (f) => {
      const ct = f.ctrace as CtraceFile | undefined;
      if (!ct) return null;
      const m = new Map<string, number>();
      for (const r of ct.rows) m.set(r[2], (m.get(r[2]) ?? 0) + r[5]);
      return m;
    },
    label: (t) => `${(t / 1e6).toFixed(t >= 1e7 ? 0 : 1)} Mt`,
  },
  offshoreWind: {
    text: () => "offshore wind farm areas per country, every status (EMODnet)",
    values: (f) => {
      const o = f.offshoreWind as OffshoreWindFile | undefined;
      if (!o) return null;
      const m = new Map<string, number>();
      for (const x of o.farms) if (x.iso3) m.set(x.iso3, (m.get(x.iso3) ?? 0) + 1);
      return m;
    },
    label: intText,
  },
};

/** The files each figure reads (loaded while its dataset is on at country scale). */
export const SUMMARY_FILES: Record<string, string[]> = {
  emitters: ["ets"],
  plants: ["reference", "worldPlants"],
  ev: ["evEu"],
  dataCentres: ["datacentres"],
  ctrace: ["ctrace"],
  offshoreWind: ["offshoreWind"],
};

/** The dataset whose figure the countries carry: the first one on that has one, on a plain map. */
export function summaryOf(fr: { colour: string; layers: Frame["layers"]; selection: Frame["selection"] }): Dataset | null {
  if (fr.colour !== "none" || fr.selection) return null;
  return DATASETS.find((d) => SUMMARIES[d.id] && datasetOn(d, fr.layers)) ?? null;
}

interface Place {
  code: string;
  polygon: Ring[];
}
const pairs = (flat: number[]): Ring => Array.from({ length: flat.length / 2 }, (_, i) => [flat[2 * i], flat[2 * i + 1]]);

function places(w: WorldFile, c: CountriesFile | undefined): { shapes: Place[]; at: Map<string, [number, number]> } {
  const shapes: Place[] = [];
  const at = new Map<string, [number, number]>();
  const eu = new Map((c?.countries ?? []).map((x) => [iso3(x.iso), x]));
  for (const f of w.features) {
    const code = f.properties.iso3;
    const e = eu.get(code);
    if (e) {
      for (const p of e.polygons) shapes.push({ code, polygon: p.map(pairs) });
      at.set(code, e.label);
      continue;
    }
    for (const p of f.geometry.coordinates) shapes.push({ code, polygon: p as Ring[] });
    // the label at the middle of the largest polygon's box
    const big = [...f.geometry.coordinates].sort((a, b) => b[0].length - a[0].length)[0][0];
    const xs = big.map((q) => q[0]);
    const ys = big.map((q) => q[1]);
    at.set(code, [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]);
  }
  return { shapes, at };
}

function current(fr: Frame) {
  const d = summaryOf(fr);
  const w = fr.files.world as WorldFile | undefined;
  if (!d || !w || fr.zoom >= SUMMARY_MAX_ZOOM) return null;
  const values = memo(`summary:${d.id}`, (SUMMARY_FILES[d.id] ?? []).map((k) => fr.files[k]), () => SUMMARIES[d.id].values(fr.files));
  if (!values?.size) return null;
  const geo = memo("summaryPlaces", [w, fr.files.countries], () => places(w, fr.files.countries as CountriesFile | undefined));
  return { d, values, geo };
}

const rgbOf = (css: string): [number, number, number] => {
  const m = css.match(/\d+/g)?.map(Number) ?? [150, 160, 180];
  return [m[0], m[1], m[2]];
};

/** The shading, under the points. */
export function summaryFill(fr: Frame): Layer[] {
  const c = current(fr);
  if (!c) return [];
  const { d, values, geo } = c;
  const ranked = memo(`summaryRank:${d.id}`, [values], () => {
    const sorted = [...values.values()].sort((a, b) => a - b);
    return (v: number) => (sorted.length > 1 ? sorted.findIndex((x) => x >= v) / (sorted.length - 1) : 1);
  });
  const col = rgbOf(d.color);
  const data = memo(`summaryShapes:${d.id}`, [geo, values], () => geo.shapes.filter((s) => values.has(s.code)));
  return [
    new SolidPolygonLayer<Place>({
      id: "summary-fill",
      data,
      getPolygon: (s) => s.polygon,
      getFillColor: (s) => [...col, Math.round(25 + 115 * ranked(values.get(s.code)!))],
      updateTriggers: { getFillColor: [d.id, values] },
      parameters: ON_TOP,
    }),
  ];
}

/** The values, over everything. */
export function summaryLabels(fr: Frame): Layer[] {
  const c = current(fr);
  if (!c) return [];
  const { d, values, geo } = c;
  const s = SUMMARIES[d.id];
  const data = memo(`summaryLabels:${d.id}`, [geo, values], () =>
    [...values.entries()].flatMap(([code, v]) => (geo.at.has(code) ? [{ at: geo.at.get(code)!, text: s.label(v), v }] : [])).sort((a, b) => b.v - a.v),
  );
  return [
    new TextLayer<{ at: [number, number]; text: string; v: number }>({
      id: "summary-labels",
      data,
      getPosition: (x) => x.at,
      getText: (x) => x.text,
      getSize: 11.5,
      getColor: [236, 240, 246, 235],
      getPixelOffset: [0, 13],
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      fontWeight: 600,
      outlineWidth: 3,
      outlineColor: [8, 10, 14, 230],
      fontSettings: { sdf: true },
      parameters: ON_TOP,
    }),
  ];
}
