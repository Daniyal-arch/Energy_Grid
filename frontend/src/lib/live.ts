/** Great Britain's carbon intensity (scripts/fetch_gb_carbon.py, NESO) and Denmark every 5
 *  minutes (scripts/fetch_dk_live.py, Energinet): live files on the eu-data branch. */

export interface GbCarbonFile {
  source: string;
  licence: string;
  fetched: string;
  now: { from: string; to: string; gco2_kwh: number; kind: "actual" | "forecast"; index: string | null };
  /** the last 24 h: [from, forecast, actual] */
  past: [string, number | null, number | null][];
  /** the next 48 h: [from, forecast, index] */
  ahead: [string, number | null, string | null][];
  mix: { from: string; to: string; pct: Record<string, number> };
  /** forecast only: [id, name, DNO, forecast gCO2/kWh, index] */
  regions: { from: string; to: string; rows: [number, string, string | null, number | null, string | null][] };
}

export interface DkLiveFile {
  source: string;
  licence: string;
  fetched: string;
  co2: { start: string; step_s: number; DK1: (number | null)[]; DK2: (number | null)[] };
  production: Record<string, { at: string; mw: Record<string, number | null> }>;
}
