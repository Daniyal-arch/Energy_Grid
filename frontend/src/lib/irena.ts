// Installed capacity per country and technology, 2000 to the newest year (IRENA statistics,
// irena.json built by scripts/fetch_irena.py). Values are IRENA's; the two map colours are
// solar PV as published and wind = onshore + offshore (summed here, said in the legend).

import type { RGB } from "./theme";

export interface IrenaFile {
  fetched: string;
  table: string;
  years: string[];
  /** IRENA technology code -> label */
  techs: Record<string, string>;
  /** ISO alpha-3 -> technology code -> MW per year (null where missing) */
  capacity_mw: Record<string, Record<string, (number | null)[]>>;
}

export type IrenaMetricId = "solar" | "wind";
export interface IrenaMetric {
  id: IrenaMetricId;
  label: string;
  note: string;
  /** IRENA labels summed for this metric */
  techs: string[];
}
export const IRENA_METRICS: IrenaMetric[] = [
  { id: "solar", label: "Solar PV installed", note: "solar photovoltaic capacity, IRENA", techs: ["Solar photovoltaic"] },
  { id: "wind", label: "Wind installed", note: "onshore + offshore wind capacity, IRENA (summed)", techs: ["Onshore wind energy", "Offshore wind energy"] },
];
export const irenaMetricById = (id: IrenaMetricId) => IRENA_METRICS.find((m) => m.id === id) ?? IRENA_METRICS[0];

/** MW of a metric for one country and year index; null when IRENA has none of its techs. */
export function irenaValue(f: IrenaFile, iso3: string | undefined, m: IrenaMetric, k: number): number | null {
  const c = iso3 ? f.capacity_mw[iso3] : undefined;
  if (!c) return null;
  const codes = Object.entries(f.techs).filter(([, label]) => m.techs.includes(label)).map(([code]) => code);
  let sum: number | null = null;
  for (const code of codes) {
    const v = c[code]?.[k];
    if (v != null) sum = (sum ?? 0) + v;
  }
  return sum;
}

/** The year index of a year label, or the newest year. */
export const irenaYearIndex = (f: IrenaFile, year?: string) => {
  const k = year ? f.years.indexOf(year) : -1;
  return k >= 0 ? k : f.years.length - 1;
};

// installed GW on a log scale: a few MW stay dark, hundreds of GW glow
export const IRENA_STOPS: Array<[number, RGB]> = [
  [-2, [34, 38, 48]],
  [-1, [52, 60, 70]],
  [0, [64, 96, 104]],
  [1, [86, 150, 140]],
  [2, [170, 210, 150]],
  [3, [255, 236, 160]],
];
export const IRENA_TICKS = ["10 MW", "100 MW", "1 GW", "10 GW", "100 GW", "1 TW"];
/** The colour scale's input: log10 of GW. */
export const irenaScale = (mw: number | null) => (mw == null || mw <= 0 ? null : Math.log10(mw / 1000));
export const formatGw = (mw: number | null) =>
  mw == null ? "–" : mw >= 10_000 ? `${Math.round(mw / 1000).toLocaleString("en-US")} GW` : mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`;

/** The IRENA year index to show: the years mode's year (from Ember's list), else the newest. */
export function irenaK(f: IrenaFile, mode: string, yearLabels: string[] | undefined, yearK: number): number {
  return irenaYearIndex(f, mode === "years" ? yearLabels?.[yearK] : undefined);
}
