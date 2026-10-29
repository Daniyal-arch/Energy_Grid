// The Maps view's themes: several maps of one place, one theme each (docs/VISUALIZATION.md #2).
// A country dashboard opens with the themes that have data there, six at most.

import { DATASET_BY_ID, covers } from "./datasets";
import { mapsFor, useApp } from "./store";

/** How a dataset is drawn, the same menu on the map and in the Maps view. */
export type Style = "points" | "bubbles" | "hex" | "bars" | "beams" | "lines" | "raster" | "choropleth" | "terrain";
export const POINT_STYLES: [Style, string][] = [
  ["bubbles", "Bubbles"],
  ["hex", "Hexagons"],
  ["bars", "3D bars"],
  ["beams", "3D beams"],
];
export const RASTER_STYLES: [Style, string][] = [
  ["raster", "Raster"],
  ["choropleth", "Choropleth"],
  ["terrain", "3D terrain"],
];

export interface MapItem {
  dataset: string;
  style: Style;
}
export interface MapPanel {
  title: string;
  items: MapItem[];
  /** one panel of an agent map (app/agent.ts) */
  agent?: { mapId: string; panel: number };
}

export const THEMES: MapPanel[] = [
  { title: "Power plants", items: [{ dataset: "plants", style: "bubbles" }] },
  {
    title: "High-voltage grid",
    items: [
      { dataset: "transmission", style: "lines" },
      { dataset: "substations", style: "points" },
    ],
  },
  { title: "Every unit (national register)", items: [{ dataset: "registers", style: "hex" }] },
  { title: "Room to connect", items: [{ dataset: "capacity", style: "points" }] },
  { title: "Emissions", items: [{ dataset: "emitters", style: "hex" }] },
  { title: "Solar resource", items: [{ dataset: "solarResource", style: "raster" }] },
  { title: "Wind resource", items: [{ dataset: "windResource", style: "raster" }] },
  { title: "EV charging", items: [{ dataset: "ev", style: "hex" }] },
  { title: "Data centres", items: [{ dataset: "dataCentres", style: "bubbles" }] },
  {
    title: "Heavy industry",
    items: [
      { dataset: "steel", style: "bubbles" },
      { dataset: "cement", style: "bubbles" },
    ],
  },
];

/** The themes with data in an area (countries, ISO alpha-3; null: anywhere), six at most. */
export function defaultMaps(area: string[] | null): MapPanel[] {
  return THEMES.map((t) => ({ ...t, items: t.items.filter((i) => DATASET_BY_ID.has(i.dataset) && covers(DATASET_BY_ID.get(i.dataset)!, area)) }))
    .filter((t) => t.items.length > 0)
    .slice(0, 6);
}

/** A map of one dataset, in its first style. */
export function panelOf(dataset: string, style: Style): MapPanel {
  return { title: DATASET_BY_ID.get(dataset)?.name ?? dataset, items: [{ dataset, style }] };
}

mapsFor.make = defaultMaps;
mapsFor.title = (d) => THEMES.find((t) => t.items[0]?.dataset === d)?.title ?? DATASET_BY_ID.get(d)?.name ?? d;
// a link read before this module: its maps take their titles now
useApp.setState((st) => ({ maps: st.maps.map((m) => (m.title === m.items[0]?.dataset ? { ...m, title: mapsFor.title!(m.title) } : m)) }));
