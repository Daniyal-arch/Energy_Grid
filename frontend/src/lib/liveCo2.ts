// CO₂ per kWh as the operators publish it (scripts/fetch_live_co2.py): France (RTE éCO2mix, 15 min),
// Spain (REE, daily factor), Ireland (EirGrid, 15 min) and the US regions (EIA-930, hourly).

export interface LiveCo2File {
  fetched: string;
  /** [time, g/kWh, {fuel: MW}] */
  fr?: { source: string; licence: string; step_min: number; unit: string; fetched: string; series: [string, number, Record<string, number>][] };
  /** factor: [day, t CO₂-eq/MWh]; by_technology_t: {tech: [[day, t]]} */
  es?: { source: string; licence: string; step_min: number; unit: string; fetched: string; factor: [string, number][]; by_technology_t: Record<string, [string, number][]> };
  /** series per region (ROI, ALL): [time, g/kWh] */
  ie?: { source: string; licence: string; step_min: number; unit: string; fetched: string; regions: Record<string, string>; series: Record<string, [string, number][]> };
}

export interface UsCo2File {
  fetched: string;
  source: string;
  licence: string;
  unit: string;
  lb_to_g_kwh: number;
  /** region -> [UTC hour, lb/kWh generated, lb/kWh consumed] */
  regions: Record<string, [string, number | null, number | null][]>;
}

export const US_CO2_REGION: Record<string, string> = {
  US48: "Lower 48", CAL: "California", CAR: "Carolinas", CENT: "Central", FLA: "Florida", MIDA: "Mid-Atlantic", MIDW: "Midwest",
  NE: "New England", NW: "Northwest", NY: "New York", SE: "Southeast", SW: "Southwest", TEN: "Tennessee", TEX: "Texas",
};
