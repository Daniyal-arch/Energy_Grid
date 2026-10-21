/** Gas on the US side (scripts/fetch_us_gas.py): EIA weekly storage, Henry Hub, citygate prices,
 * and EIA's pipeline map. Values as EIA publishes them. */

export interface UsGasSeries {
  name: string;
  unit: string;
  /** [period, value], oldest first */
  points: [string, number][];
  /** storage only: per week of the newest year, [min, max] of the same week in the five years before */
  range_5y?: Record<string, [number, number]>;
}

export interface UsGasFile {
  source: string;
  fetched: string;
  storage: Record<string, UsGasSeries>;
  henry_hub: UsGasSeries | null;
  citygate: Record<string, UsGasSeries>;
  range_note: string;
}

export interface UsGasPipesFile {
  source: string;
  note: string;
  /** [paths, type, operator, status] */
  lines: [[number, number][][], string | null, string | null, string | null][];
}

export const US_PIPE_COLOR: [number, number, number] = [255, 196, 96];
