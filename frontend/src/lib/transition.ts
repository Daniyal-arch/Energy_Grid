// Transition tab: 25 years of Ember's yearly electricity data per country (transition.json,
// built by scripts/fetch_transition.py). Every value is Ember's own; this file only picks
// colours and joins codes.

import type { RGB } from "./theme";

type Series = (number | null)[];

export interface TransitionEntity {
  name: string;
  aggregate: boolean;
  /** generation by source, TWh */
  series: Record<string, Series>;
  renewables: Series;
  wind_solar: Series;
  coal: Series;
  intensity: Series;
  total_twh: Series;
}
export interface TransitionFile {
  fetched: string;
  years: string[];
  /** ISO 3166-1 alpha-3 for countries, Ember's name for aggregates (World, EU, ...) */
  entities: Record<string, TransitionEntity>;
}

export type MetricId = "renewables" | "wind_solar" | "coal" | "intensity";
export interface Metric {
  id: MetricId;
  label: string;
  short: string;
  unit: string;
  /** what the colour means, for the legend */
  note: string;
  stops: Array<[number, RGB]>;
  ticks: string[];
}

// share of generation: ember brown (none) -> sage -> bright teal (all)
const SHARE: Array<[number, RGB]> = [
  [0, [96, 44, 40]],
  [20, [128, 82, 56]],
  [40, [112, 116, 86]],
  [60, [62, 142, 124]],
  [80, [56, 186, 166]],
  [100, [104, 232, 204]],
];

export const METRICS: Metric[] = [
  {
    id: "renewables",
    label: "Renewable share",
    short: "Renewables",
    unit: "%",
    note: "renewables in % of generation",
    stops: SHARE,
    ticks: ["0 %", "50 %", "100 %"],
  },
  {
    id: "wind_solar",
    label: "Wind + solar share",
    short: "Wind + solar",
    unit: "%",
    note: "wind and solar in % of generation",
    stops: SHARE,
    ticks: ["0 %", "50 %", "100 %"],
  },
  {
    id: "coal",
    label: "Coal share",
    short: "Coal",
    unit: "%",
    note: "coal in % of generation",
    // none: cool slate -> much: hot brown
    stops: [
      [0, [38, 64, 78]],
      [20, [92, 86, 84]],
      [45, [150, 104, 74]],
      [70, [196, 112, 64]],
      [100, [226, 120, 60]],
    ],
    ticks: ["0 %", "50 %", "100 %"],
  },
  {
    id: "intensity",
    label: "Carbon intensity",
    short: "CO₂ intensity",
    unit: "g/kWh",
    note: "g CO₂ per kWh generated",
    stops: [
      [0, [104, 232, 204]],
      [100, [62, 160, 140]],
      [250, [118, 124, 90]],
      [450, [160, 104, 70]],
      [700, [184, 76, 58]],
      [1000, [132, 40, 48]],
    ],
    ticks: ["0", "500", "≥ 1000 g/kWh"],
  },
];

export const metricById = (id: MetricId) => METRICS.find((m) => m.id === id) ?? METRICS[0];

export function metricColor(m: Metric, v: number | null | undefined): RGB | null {
  if (v == null) return null;
  const s = m.stops;
  if (v <= s[0][0]) return s[0][1];
  for (let i = 1; i < s.length; i++) {
    const [v1, c1] = s[i];
    const [v0, c0] = s[i - 1];
    if (v <= v1) {
      const t = (v - v0) / (v1 - v0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * t)) as RGB;
    }
  }
  return s[s.length - 1][1];
}

export const metricGradient = (m: Metric) => {
  const top = m.stops[m.stops.length - 1][0];
  return `linear-gradient(90deg, ${m.stops.map(([v, c]) => `rgb(${c.join(",")}) ${(v / top) * 100}%`).join(", ")})`;
};

export const formatMetric = (m: Metric, v: number | null | undefined) =>
  v == null ? "–" : m.unit === "%" ? `${v.toFixed(0)} %` : `${Math.round(v)} g`;

/** The mapped European countries (ISO alpha-2, as countries.json) and Ember's alpha-3 code. */
export const ISO3: Record<string, string> = {
  AL: "ALB", AT: "AUT", BA: "BIH", BE: "BEL", BG: "BGR", CH: "CHE", CZ: "CZE", DE: "DEU",
  DK: "DNK", EE: "EST", ES: "ESP", FI: "FIN", FR: "FRA", GB: "GBR", GR: "GRC", HR: "HRV",
  HU: "HUN", IE: "IRL", IT: "ITA", LT: "LTU", LU: "LUX", LV: "LVA", ME: "MNE", MD: "MDA",
  MK: "MKD", NL: "NLD", NO: "NOR", PL: "POL", PT: "PRT", RO: "ROU", RS: "SRB", SE: "SWE",
  SI: "SVN", SK: "SVK", UA: "UKR", XK: "XKX",
}; // prettier-ignore
export const EUROPE_ISO3 = new Set(Object.values(ISO3));
