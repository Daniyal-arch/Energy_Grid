/** EV charging in Europe (scripts/build_ev_eu.py): EAFO counts per country, and where the chargers
 * are from the national registers (DE, FR) or OpenStreetMap, summed in 0.1° cells. */

export interface EvEuMap {
  source: string;
  url: string;
  licence: string;
  /** what a cell counts: "charging points" (registers) or "stations" (OpenStreetMap) */
  unit: string;
  note: string;
  n: number;
  n_rows: number;
  fetched: string;
}

export interface EvEuFile {
  fetched: string;
  cell_deg: number;
  eafo: {
    source: string;
    url: string;
    licence: string;
    classes: string[];
    countries: Record<string, { years: number[]; ac: (number | null)[]; dc: (number | null)[]; classes: (number | null)[] | null }>;
  };
  maps: Record<string, EvEuMap>;
  /** per country: [lon, lat, count] per cell centre, largest first */
  cells: Record<string, [number, number, number][]>;
}

export const EV_EU_COLOR: [number, number, number] = [96, 214, 255];
// OpenStreetMap stations: the same hue, paler, so a register and a mapped count are told apart
export const EV_OSM_COLOR: [number, number, number] = [150, 196, 214];

export const isRegister = (m: EvEuMap | undefined) => m?.unit === "charging points";
