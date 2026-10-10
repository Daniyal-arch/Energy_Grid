// Gas flows per gas day (ENTSOG, scripts/fetch_entsog.py → gas_flows.json): types, where the
// sources outside Europe sit on the map, and the sums the panels show.

import type { RGB } from "./theme";

export interface GasPair {
  /** a country (ISO), a source outside Europe (a key of `nodes`) or "LNG" */
  a: string;
  b: string;
  kind: "border" | "entry" | "lng";
  /** the country whose operators' reports are summed */
  read_from: string;
  /** GWh/d a→b and b→a as reported, and a→b minus b→a; one value per gas day */
  ab: (number | null)[];
  ba: (number | null)[];
  net: (number | null)[];
  /** the other side's net a→b by its own reports (borders where both report) */
  other_side_net: (number | null)[] | null;
  /** [point, operator, "a>b" | "b>a", GWh/d on the newest gas day] */
  points: [string, string, string, number | null][];
}
export interface GasFlowsFile {
  source: string;
  fetched: string;
  unit: string;
  gas_day: string;
  gas_day_note: string;
  days: string[];
  nodes: Record<string, string>;
  pairs: GasPair[];
}

export const GAS_FLOW: RGB = [255, 178, 62];
/** below this net flow (GWh/d) no arc is drawn; labels from GAS_LABEL_GWH */
export const GAS_IDLE_GWH = 5;
export const GAS_LABEL_GWH = 250;

// Sources outside Europe and each country's LNG terminals: placed for reading (near the
// landfall or the main terminals), not at a measured point.
export const GAS_NODE_AT: Record<string, [number, number]> = {
  NO: [3.0, 58.6],
  DZ: [3.0, 36.1],
  "DZ-MA": [-5.6, 34.6],
  LY: [12.6, 33.4],
  "AZ-TR": [32.5, 40.2],
  "RU-TR": [29.6, 42.6],
  TR: [27.4, 41.4],
  RU: [21.4, 54.7], // the only flow left is to Kaliningrad
  "RU-BY": [27.6, 53.8],
  BY: [27.6, 53.8],
  SM: [12.45, 43.94],
}; // prettier-ignore
/** Map labels where the placement narrows the source down. */
export const GAS_NODE_LABEL: Record<string, string> = { RU: "Kaliningrad (Russia)" };
export const LNG_AT: Record<string, [number, number]> = {
  BE: [2.9, 51.6], DE: [7.4, 54.1], ES: [-0.2, 38.6], FI: [23.9, 59.7], FR: [-3.7, 47.0],
  GB: [-5.6, 51.4], GR: [23.6, 37.5], HR: [14.4, 44.8], IT: [13.0, 44.5], LT: [20.4, 55.8],
  NL: [3.6, 52.4], PL: [14.4, 54.4], PT: [-9.5, 37.8],
}; // prettier-ignore

export const latestOf = (v: (number | null)[]) => v[v.length - 1] ?? null;

/** Map position of one end of a pair (b is always a country, or a country for LNG). */
export function endAt(key: string, country: string, anchor: Record<string, [number, number]>): [number, number] | undefined {
  if (key === "LNG") return LNG_AT[country];
  // "NO" is the Norwegian shelf here, not Norway's inland anchor
  return GAS_NODE_AT[key] ?? anchor[key];
}

/** Name of one end: a country, a source, or the LNG terminals of a country. */
export function endName(key: string, f: GasFlowsFile, countryName: (iso: string) => string, lngOf?: string): string {
  if (key === "LNG") return lngOf ? `LNG terminals in ${countryName(lngOf)}` : "LNG terminals";
  return f.nodes[key] ?? countryName(key);
}

export const gwhd = (v: number | null | undefined, digits = 0) =>
  v == null ? "–" : `${v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })} GWh/d`;

/** One country's gas in and out: per pair, the flow into it (positive) on every gas day. */
export function countryFlows(f: GasFlowsFile, iso: string) {
  return f.pairs
    .filter((p) => p.a === iso || p.b === iso)
    .map((p) => {
      const into = p.b === iso;
      return {
        pair: p,
        other: into ? p.a : p.b,
        inflow: into ? p.ab : p.ba,
        outflow: into ? p.ba : p.ab,
        net: p.net.map((v) => (v == null ? null : into ? v : -v)),
      };
    });
}

/** Sum of the non-null values of several series, per day (null where none has a value). */
export function sumSeries(series: (number | null)[][], n: number): (number | null)[] {
  return Array.from({ length: n }, (_, i) => {
    const vals = series.map((s) => s[i]).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, v) => a + v, 0) : null;
  });
}
