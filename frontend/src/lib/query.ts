// Deterministic asset/lifecycle filters shared by map and table views.

import type { Site } from "./api";
import { STATE_LABEL, TECH_LABEL, displayState, type DisplayState, type Technology } from "./theme";

export interface Filter {
  technologies: Set<Technology>;
  states: Set<DisplayState>; // observed or registry-derived lifecycle state
  minCapacityMw: number | null;
  region: string | null; // German federal state
  planningOnly: boolean;
}

export const emptyFilter = (): Filter => ({
  technologies: new Set(),
  states: new Set(),
  minCapacityMw: null,
  region: null,
  planningOnly: false,
});

const REGION_ALIASES: Record<string, string> = {
  bavaria: "Bayern",
  bayern: "Bayern",
  "baden-wurttemberg": "Baden-Württemberg",
  "baden-württemberg": "Baden-Württemberg",
  "baden-wuerttemberg": "Baden-Württemberg",
  nrw: "Nordrhein-Westfalen",
  brandenburg: "Brandenburg",
  saxony: "Sachsen",
  sachsen: "Sachsen",
  niedersachsen: "Niedersachsen",
  "lower saxony": "Niedersachsen",
};

export interface Parsed {
  filter: Filter;
  understood: string[];
}

export function parseQuery(q: string): Parsed {
  const text = q.toLowerCase();
  const filter = emptyFilter();
  const understood: string[] = [];

  for (const tech of Object.keys(TECH_LABEL) as Technology[]) {
    if (text.includes(tech)) {
      filter.technologies.add(tech);
      understood.push(TECH_LABEL[tech]);
    }
  }
  for (const st of Object.keys(STATE_LABEL) as DisplayState[]) {
    if (st !== "unknown" && text.includes(st.replace("_", " "))) {
      filter.states.add(st);
      understood.push(STATE_LABEL[st]);
    }
  }
  for (const [alias, region] of Object.entries(REGION_ALIASES)) {
    if (text.includes(alias)) {
      filter.region = region;
      understood.push(region);
    }
  }
  if (/(in planning|planned|under construction|behind|pipeline)/.test(text)) {
    filter.planningOnly = true;
    understood.push("in planning");
  }
  const cap = text.match(/(?:over|above|>|>=|at least)\s*(\d+(?:\.\d+)?)\s*mw/);
  if (cap) {
    filter.minCapacityMw = parseFloat(cap[1]);
    understood.push(`≥ ${cap[1]} MW`);
  }
  return { filter, understood };
}

export function applyFilter(sites: Site[], f: Filter): Site[] {
  return sites.filter((s) => {
    if (f.technologies.size && (!s.technology || !f.technologies.has(s.technology))) return false;
    if (f.states.size && !f.states.has(displayState(s.status, s.mastr_status))) return false;
    if (f.region && s.state !== f.region) return false;
    if (f.minCapacityMw != null && s.capacity_mw < f.minCapacityMw) return false;
    if (f.planningOnly && s.mastr_status !== "In Planung") return false;
    return true;
  });
}

export const filterActive = (f: Filter): boolean =>
  f.technologies.size > 0 ||
  f.states.size > 0 ||
  f.minCapacityMw != null ||
  f.region != null ||
  f.planningOnly;
