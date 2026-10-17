// US day-ahead prices at every node, hour by hour (scripts/fetch_us_nodes.py): CAISO's nodes
// placed by its price map, every market's spread over its priced locations.

/** [min, 10th percentile, median, 90th percentile, max] over a market's locations (computed) */
export type Spread = [number, number, number, number, number];

export interface UsNodesFile {
  fetched: string;
  source: string;
  date: string;
  timezone: string;
  /** UTC start of the Eastern-Time day */
  start: string;
  slots: number;
  step_s: number;
  markets: Record<string, { nodes: number; placed: number; hours: (Spread | null)[] }>;
  /** colour range of the placed nodes: 2nd to 98th percentile of the day (computed) */
  range: [number, number] | null;
  /** [lon, lat, node, balancing area] */
  nodes: [number, number, string, string][];
  /** USD/MWh per node and hour, as the market publishes it */
  prices: (number | null)[][];
}

export const usdMwh = (v: number | null | undefined) => (v == null ? "–" : `$${v.toFixed(2)}`);
