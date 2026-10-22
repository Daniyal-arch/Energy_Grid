// The datasets as the user sees them (app/datasets.json): one entry per kind of data, made of the
// map layers that hold it for a region ("Transmission lines" = Europe's grid + the US lines + the
// world's lines from 220 kV). The Layers panel, the dashboards and the agent read the same file.

import { EUROPE_ISO3, ISO3 } from "../lib/transition";
import REGISTRY from "./datasets.json";
import { COLOURS, LAYERS, LAYER_GROUPS, actions, countryDashboards, useApp, type ColourId, type Dashboard, type LayerGroup, type LayerId, type TimeMode } from "./store";

export interface DatasetPart {
  /** the map layer (none for a dataset that colours the countries) */
  layer?: LayerId;
  /** ISO alpha-2 codes or the regions World, Europe, EU, US */
  where: string[];
  what: string;
  source: string;
  /** the docs/DATA_SOURCES.md section */
  doc: string;
}
export interface Dataset {
  id: string;
  name: string;
  category: LayerGroup;
  description: string;
  color: string;
  /** the coverage registry family (coverage.json), per-country status */
  family?: string;
  /** colours the countries (one such dataset at a time) instead of drawing layers */
  colour?: ColourId;
  updates?: string;
  parts: DatasetPart[];
}

export const DATASETS = REGISTRY.datasets as Dataset[];
export const DATASET_BY_ID = new Map(DATASETS.map((d) => [d.id, d]));
export const DATASET_OF_LAYER = new Map(DATASETS.flatMap((d) => d.parts.flatMap((p) => (p.layer ? [[p.layer, d] as const] : []))));
export const CATEGORIES: LayerGroup[] = LAYER_GROUPS.filter((g) => DATASETS.some((d) => d.category === g));

const MODES = new Map(LAYERS.map((l) => [l.id, l.modes]));
const COLOUR_MODES = new Map(COLOURS.map((c) => [c.id, c.modes]));
const layerIn = (layer: LayerId | undefined, mode: TimeMode) => !!layer && (!MODES.get(layer) || MODES.get(layer)!.includes(mode));
/** The parts shown in a time mode (a layer without modes is in all of them; a colouring in its own). */
export const partsIn = (d: Dataset, mode: TimeMode) => (d.colour ? (COLOUR_MODES.get(d.colour)?.includes(mode) ? d.parts : []) : d.parts.filter((p) => layerIn(p.layer, mode)));
/** On: a colouring when it colours the countries, else any of its layers on. */
export const datasetOn = (d: Dataset, layers: Record<LayerId, boolean>, colour?: ColourId) => (d.colour ? colour === d.colour : d.parts.some((p) => !!p.layer && layers[p.layer]));
/** The time modes a dataset has parts in. */
export const datasetModes = (d: Dataset): TimeMode[] => (["live", "day", "years"] as TimeMode[]).filter((m) => partsIn(d, m).length > 0);

export const EU27 = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"];
// codes the Europe table (lib/transition ISO3) does not hold
const MORE_ISO3: Record<string, string> = { CY: "CYP", MT: "MLT", IS: "ISL", LI: "LIE", US: "USA", BR: "BRA", AU: "AUS", TW: "TWN", CA: "CAN", NZ: "NZL", ZA: "ZAF" };
export const iso3Of = (iso2: string) => ISO3[iso2] ?? MORE_ISO3[iso2] ?? iso2;
export const iso2Of = (iso3: string) => Object.entries(ISO3).find(([, v]) => v === iso3)?.[0] ?? Object.entries(MORE_ISO3).find(([, v]) => v === iso3)?.[0];

/** A country's own files (capacity maps, registers) belong on the map: no dashboard area, or one
 *  holding the country (ISO alpha-2). */
export const inAreaCountry = (area: string[] | null, iso2: string) => !area || area.includes(iso3Of(iso2));

/** The countries (ISO alpha-3) a list of places names; null = the whole world. */
export function placesIso3(where: string[]): Set<string> | null {
  if (where.includes("World")) return null;
  const out = new Set<string>();
  for (const w of where) {
    if (w === "Europe") EUROPE_ISO3.forEach((c) => out.add(c));
    else if (w === "EU") EU27.forEach((c) => out.add(iso3Of(c)));
    else out.add(iso3Of(w));
  }
  return out;
}
/** Where a dataset has data (ISO alpha-3), null = everywhere. */
export function coverageIso3(d: Dataset): Set<string> | null {
  const out = new Set<string>();
  for (const p of d.parts) {
    const s = placesIso3(p.where);
    if (!s) return null;
    s.forEach((c) => out.add(c));
  }
  return out;
}
/** Does the dataset hold anything for this area (ISO alpha-3 list; null = world)? */
export function covers(d: Dataset, area: string[] | null): boolean {
  if (!area) return true;
  const c = coverageIso3(d);
  return !c || area.some((a) => c.has(a));
}
/** The parts that hold data for an area. */
export function partsFor(d: Dataset, area: string[] | null): DatasetPart[] {
  if (!area) return d.parts;
  return d.parts.filter((p) => {
    const s = placesIso3(p.where);
    return !s || area.some((a) => s.has(a));
  });
}

const PLACE_LABEL: Record<string, string> = { World: "World", Europe: "Europe", EU: "EU", US: "US" };
/** "Europe · US", "DE · GB · DK +5": short, for a row. */
export function coverageLabel(d: Dataset): string {
  const all = [...new Set(d.parts.flatMap((p) => p.where))];
  if (all.includes("World") && d.parts.length === 1) return "";
  const regions = all.filter((w) => PLACE_LABEL[w] && w !== "World");
  const codes = all.filter((w) => !PLACE_LABEL[w]);
  const head = [...regions, ...codes.slice(0, Math.max(0, 3 - regions.length))];
  const more = regions.length + codes.length - head.length;
  return [...head, ...(all.includes("World") ? ["world"] : [])].join(" · ") + (more > 0 ? ` +${more}` : "");
}
/** Every place, in words, for the details. */
export const placesText = (where: string[]) => where.map((w) => (w === "World" ? "the world" : w === "EU" ? "the EU" : w)).join(", ");

/** Layers of a set of datasets. */
export const layersOfDatasets = (ids: string[]): LayerId[] => ids.flatMap((id) => DATASET_BY_ID.get(id)?.parts.flatMap((p) => (p.layer ? [p.layer] : [])) ?? []);
/** Datasets with a layer on. */
export const datasetsOn = (layers: Record<LayerId, boolean>, colour?: ColourId) => DATASETS.filter((d) => datasetOn(d, layers, colour));
/** The colouring among chosen datasets (the first), else none. */
export const colourOfDatasets = (ids: string[]): ColourId => ids.map((id) => DATASET_BY_ID.get(id)?.colour).find(Boolean) ?? "none";

// ------------------------------------------------------------------ a dashboard for any country

/** What a country's dashboard shows: these datasets, the parts that cover the country. */
const COUNTRY_SET = ["plants", "registers", "transmission", "substations", "capacity", "offshoreWind", "emitters", "ev", "dataCentres"];
const NAMES: Record<string, string> = {};
/** Country names for the generated dashboards (set once the world outlines have loaded). */
export const setCountryNames = (pairs: [string, string][]) => pairs.forEach(([c, n]) => (NAMES[c] = n));
countryDashboards.make = (code: string): Dashboard | undefined => {
  if (!/^[A-Z]{3}$/.test(code)) return undefined;
  const area = [code];
  const ds = COUNTRY_SET.map((id) => DATASET_BY_ID.get(id)!).filter((d) => d && covers(d, area));
  const layers = ds.flatMap((d) => partsFor(d, area).flatMap((p) => (p.layer && layerIn(p.layer, "live") ? [p.layer] : [])));
  const name = NAMES[code] ?? code;
  return {
    id: `country:${code}`,
    group: "Countries",
    label: `${name} in detail`,
    blurb: ds.map((d) => d.name.toLowerCase()).join(", "),
    mode: "live",
    colour: "none",
    layers,
    area,
    camera: { area },
    region: code === "USA" ? "us" : EUROPE_ISO3.has(code) ? "europe" : "world",
  };
};

/** Switch a dataset: off if any of its layers is on, else its layers for the current time mode on. */
export function toggleDataset(d: Dataset): void {
  if (d.colour) {
    const s = useApp.getState();
    return actions.setColour(s.colour === d.colour ? "none" : d.colour);
  }
  useApp.setState((s) => {
    const on = !partsIn(d, s.mode).some((p) => !!p.layer && s.layers[p.layer]);
    const set = (on ? partsIn(d, s.mode) : d.parts).flatMap((p) => (p.layer ? [p.layer] : []));
    return {
      layers: { ...s.layers, ...Object.fromEntries(set.map((l) => [l, on])) },
      edited: true,
      tab: on && !s.selection ? "dashboard" : s.tab,
    };
  });
}
