/** US public EV fast chargers (scripts/fetch_ev_chargers.py, NREL AFDC; monthly in us-grid). */

/** [stations, DC fast stations, level 2 ports, DC fast ports] (sums, computed) */
export type EvCounts = [number, number, number, number];

export interface EvChargersFile {
  source: string;
  licence: string;
  fetched: string;
  networks: string[];
  /** station names, same order as `points` */
  names: string[];
  /** DC fast stations: [lon, lat, DC fast ports, network index, open year] */
  points: [number, number, number, number, number | null][];
  states: Record<string, EvCounts>;
  total: EvCounts;
  /** [network, DC fast stations, DC fast ports], most ports first */
  by_network: [string, number, number][];
}

export const EV_COLOR: [number, number, number] = [96, 214, 255];
