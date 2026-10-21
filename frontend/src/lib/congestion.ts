// Redispatch, countertrading and congestion costs (ENTSO-E A63/A91/A92), GB's constraint costs
// (NESO) and California's curtailment (CAISO), monthly sums (scripts/build_congestion.py).

type Months = Record<string, number>;
export interface CongestionCountry {
  redispatch_internal?: { unit: string; n: number; by_direction: Record<string, Months> };
  redispatch_cross_border?: { unit: string; n: number; by_direction: Record<string, Months> };
  countertrading?: { unit: string; n: number; by_direction: Record<string, Months> };
  costs?: { unit: string; field: string | null; n: number; months: Months };
}
export interface CongestionFile {
  fetched: string;
  entsoe?: { source: string; window: [string, string]; countries: Record<string, CongestionCountry> };
  gb?: { source: string; licence: string; url: string; unit: string; months: Record<string, Record<string, number>> };
  caiso?: { source: string; licence: string; url: string; unit: string; months: Record<string, Record<string, number>> };
}

/** ENTSO-E's flowDirection codes */
export const DIRECTION: Record<string, string> = { A01: "up", A02: "down", all: "" };

/** The newest `n` months of a series, summed over directions (computed). */
export function lastMonths(series: Record<string, Months> | undefined, n = 12): [string, number][] {
  const sum: Months = {};
  for (const m of Object.values(series ?? {})) for (const [k, v] of Object.entries(m)) sum[k] = (sum[k] ?? 0) + v;
  return Object.entries(sum).sort((a, b) => a[0].localeCompare(b[0])).slice(-n);
}
