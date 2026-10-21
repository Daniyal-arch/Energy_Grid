// The datasets as the user sees them (app/datasets.json): one entry per kind of data, made of the
// map layers that hold it for a region ("Transmission lines" = Europe's grid + the US lines + the
// world's lines from 220 kV). The Layers panel, the dashboards and the agent read the same file.

import { EUROPE_ISO3, ISO3 } from "../lib/transition";
import REGISTRY from "./datasets.json";
import { LAYERS, LAYER_GROUPS, useApp, type LayerGroup, type LayerId, type TimeMode } from "./store";

export interface DatasetPart {
  layer: LayerId;
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
  updates?: string;
  parts: DatasetPart[];
}

export const DATASETS = REGISTRY.datasets as Dataset[];
export const DATASET_BY_ID = new Map(DATASETS.map((d) => [d.id, d]));
export const DATASET_OF_LAYER = new Map(DATASETS.flatMap((d) => d.parts.map((p) => [p.layer, d] as const)));
export const CATEGORIES: LayerGroup[] = LAYER_GROUPS.filter((g) => DATASETS.some((d) => d.category === g));

const MODES = new Map(LAYERS.map((l) => [l.id, l.modes]));
/** The parts drawn in a time mode (a layer without modes is in all of them). */
export const partsIn = (d: Dataset, mode: TimeMode) => d.parts.filter((p) => !MODES.get(p.layer) || MODES.get(p.layer)!.includes(mode));
export const datasetOn = (d: Dataset, layers: Record<LayerId, boolean>) => d.parts.some((p) => layers[p.layer]);
/** The time modes a dataset has parts in. */
export const datasetModes = (d: Dataset): TimeMode[] => (["live", "day", "years"] as TimeMode[]).filter((m) => partsIn(d, m).length > 0);

export const EU27 = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"];
// codes the Europe table (lib/transition ISO3) does not hold
const MORE_ISO3: Record<string, string> = { CY: "CYP", MT: "MLT", IS: "ISL", LI: "LIE", US: "USA", BR: "BRA", AU: "AUS", TW: "TWN", CA: "CAN", NZ: "NZL", ZA: "ZAF" };
export const iso3Of = (iso2: string) => ISO3[iso2] ?? MORE_ISO3[iso2] ?? iso2;
export const iso2Of = (iso3: string) => Object.entries(ISO3).find(([, v]) => v === iso3)?.[0] ?? Object.entries(MORE_ISO3).find(([, v]) => v === iso3)?.[0];

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
export const layersOfDatasets = (ids: string[]): LayerId[] => ids.flatMap((id) => DATASET_BY_ID.get(id)?.parts.map((p) => p.layer) ?? []);
/** Datasets with a layer on. */
export const datasetsOn = (layers: Record<LayerId, boolean>) => DATASETS.filter((d) => datasetOn(d, layers));

/** Switch a dataset: off if any of its layers is on, else its layers for the current time mode on. */
export function toggleDataset(d: Dataset): void {
  useApp.setState((s) => {
    const on = !partsIn(d, s.mode).some((p) => s.layers[p.layer]);
    const set = on ? partsIn(d, s.mode) : d.parts;
    return {
      layers: { ...s.layers, ...Object.fromEntries(set.map((p) => [p.layer, on])) },
      edited: true,
      tab: on && !s.selection ? "dashboard" : s.tab,
    };
  });
}
