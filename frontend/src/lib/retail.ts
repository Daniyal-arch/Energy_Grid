// What consumers pay (scripts/fetch_retail_prices.py): Eurostat half-yearly prices per
// consumption band (EUR/kWh) and EIA's monthly average price per US state (US cents/kWh).

import type { ColorStops } from "../app/types";

export type Tax = "I_TAX" | "X_VAT" | "X_TAX";
export interface RetailRow {
  I_TAX: (number | null)[];
  X_VAT: (number | null)[];
  X_TAX: (number | null)[];
  flags: (string | null)[];
}
export type RetailSeries = "elec_household" | "elec_business" | "gas_household" | "gas_business";

export interface RetailFile {
  fetched: string;
  eu: { source: string; periods: string[]; updated: Record<string, string>; series: Record<RetailSeries, Record<string, RetailRow>> };
  us?: { source: string; months: string[]; names: Record<string, string>; price: Record<string, Record<"RES" | "COM" | "IND" | "ALL", (number | null)[]>> };
}

export const SERIES_LABEL: Record<RetailSeries, { title: string; band: string }> = {
  elec_household: { title: "Electricity, households", band: "band DC, 2,500–4,999 kWh a year" },
  elec_business: { title: "Electricity, businesses", band: "band IC, 500–1,999 MWh a year" },
  gas_household: { title: "Gas, households", band: "band D2, 20–199 GJ a year" },
  gas_business: { title: "Gas, businesses", band: "band I3, 10,000–99,999 GJ a year" },
};

export const FLAG_TEXT: Record<string, string> = { p: "provisional", e: "estimated", b: "break in series", d: "definition differs", c: "confidential", u: "low reliability" };

/** The newest half-year with a value (all taxes), with its flag. */
export function newestOf(f: RetailFile, row: RetailRow | undefined): { k: number; period: string; v: number; flag: string | null } | null {
  if (!row) return null;
  for (let k = row.I_TAX.length - 1; k >= 0; k--) {
    const v = row.I_TAX[k];
    if (v != null) return { k, period: f.eu.periods[k], v, flag: row.flags[k] };
  }
  return null;
}

/** The newest month with a value in a US series. */
export function newestMonth(months: string[], vs: (number | null)[] | undefined): { k: number; month: string; v: number } | null {
  if (!vs) return null;
  for (let k = vs.length - 1; k >= 0; k--) if (vs[k] != null) return { k, month: months[k], v: vs[k] as number };
  return null;
}

/** EUR/kWh as Eurostat gives it (4 decimals) shown in cents: exact, 2 decimals. */
export const euroCents = (v: number | null | undefined) => (v == null ? "–" : `${(v * 100).toFixed(2)} c€`);
export const usCents = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(2)} ¢`);

// household electricity, cents per kWh (euro cents in Europe, US cents in the US): calm sand -> deep rust
export const RETAIL_STOPS: ColorStops = [
  [8, [34, 62, 70]],
  [20, [58, 60, 74]],
  [32, [104, 62, 58]],
  [45, [150, 66, 44]],
];
export const RETAIL_TICKS = ["≤ 8", "20", "32", "≥ 45 cents/kWh"];
