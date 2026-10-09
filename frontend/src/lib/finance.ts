// Who finances coal and gas power (GEM finance trackers, gem/finance.json built by
// scripts/build_gem_finance.py): money flows from the financiers' countries to the projects.
// Amounts are GEM's (US$ million); sums are the build script's.

import type { RGB } from "./theme";

/** [from ISO3, to ISO3, fuel, US$ million, deals, first year, last year, end [lon, lat]] */
export type FinanceFlow = [string, string, number, number, number, number | null, number | null, [number, number]];
/** [lon, lat, fuel, US$ million, deals, name, ISO3, status, top financiers [name, US$ million][]] */
export type FinanceProject = [number, number, number, number, number, string, string, string, [string, number][]];
/** [financier, ISO3 or "", fuel, US$ million, deals, public/private] */
export type FinanceLender = [string, string, number, number, number, string];
export interface FinanceFile {
  source: string;
  fetched: string;
  fuels: string[];
  unit: string;
  countries: Record<string, { name: string; at: [number, number] }>;
  flows: FinanceFlow[];
  projects: FinanceProject[];
  lenders: FinanceLender[];
  totals: Record<string, { out: [number, number]; in: [number, number]; domestic: [number, number] }>;
  deals: number;
}

/** coal money pale gold, gas money amber */
export const MONEY: RGB[] = [
  [232, 204, 128],
  [255, 170, 60],
];
export const FINANCE_LAYER = ["financeCoal", "financeGas"] as const;

/** "$1.2 bn", "$340 m" */
export const usd = (m: number) => (m >= 1000 ? `$${(m / 1000).toFixed(m >= 10_000 ? 0 : 1)} bn` : `$${Math.round(m)} m`);
export const years = (y0: number | null, y1: number | null) => (y0 && y1 ? (y0 === y1 ? `${y0}` : `${y0}–${y1}`) : "");
