// EMODnet Human Activities in European seas (scripts/build_grid_more.py emodnet): the national
// power-cable layers and the pipelines at sea, as published (CC BY 4.0).

import type { RGB } from "./theme";

/** [EMODnet layer, name, status, flat lon/lat] */
export type SeaCable = [string, string | null, string | null, number[]];
/** [name, medium, status, operator, country, size (inches), flat lon/lat] */
export type SeaPipe = [string | null, string | null, string | null, string | null, string | null, number | string | null, number[]];

export interface SeaCablesFile {
  fetched: string;
  source: string;
  layers: string[];
  cables: SeaCable[];
  pipelines: SeaPipe[];
}

export const SEA_CABLE_COLOR: RGB = [150, 210, 255];

/** Which pipelines layer shows a medium: gas, oil and condensate; mixed hydrocarbons in both;
 *  water, chemicals, sewage and the rest stay off the map. */
export function seaPipeLayer(medium: string | null): ("gasPipes" | "oilPipes")[] {
  if (medium === "Gas") return ["gasPipes"];
  if (medium === "Oil" || medium === "Condensate") return ["oilPipes"];
  if (medium === "Mixed Hydrocarbons") return ["gasPipes", "oilPipes"];
  return [];
}

/** The EMODnet layer's publisher, for the hover. */
export const SEA_CABLE_SOURCE: Record<string, string> = {
  pcablesbshcontis: "BSH (Germany)",
  pcablesnve: "NVE (Norway)",
  pcablesrijks: "Rijkswaterstaat (Netherlands)",
  pcablesshom: "SHOM (France)",
};
