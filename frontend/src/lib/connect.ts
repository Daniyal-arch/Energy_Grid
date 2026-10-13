// Where new demand or generation can still connect (scripts/fetch_connect_here.py): the grid
// operators' own figures for Great Britain (NESO TEC register), the Netherlands (Netbeheer
// Nederland's capacity map) and Spain (Red Eléctrica's node capacities).

import type { RGB } from "./theme";

/** [project, site index, MW total, MW connected, type, status, effective from | null, agreement | null] */
export type GbProject = [string, number, number, number, number, number, string | null, string | null];
/** [site, lon | null, lat | null, transmission owner] */
export type GbSite = [string, number | null, number | null, string];

export interface NlArea {
  id: string;
  name: string;
  operator: string | null;
  /** 0 available, 1 limited, 2 under study with a queue, 3 shortage with a queue */
  offtake: number;
  feedin: number;
  queue_offtake_mw: number | null;
  queue_feedin_mw: number | null;
  requests_offtake: number | null;
  requests_feedin: number | null;
  polygons: [number, number][][][];
}

/** [node, substation code, region, demand CEP CH, demand CEP SH, demand not CEP, storage MPE, storage MGES, tender node] */
export type EsNode = [string, string, string, number | null, number | null, number | null, number | null, number | null, boolean];

export interface ConnectFile {
  fetched: string;
  gb: { source: string; date: string; types: string[]; statuses: string[]; sites: GbSite[]; projects: GbProject[] };
  nl: { source: string; status: string[]; areas: NlArea[] };
  es: { source: string; date: string; url: string; columns: string[]; nodes: EsNode[] };
}

export type ConnectSide = "offtake" | "feedin";

/** The capacity map's four states, calm: room, limited, under study, shortage. */
export const NL_COLOR: RGB[] = [
  [52, 120, 108],
  [168, 160, 92],
  [206, 138, 72],
  [196, 72, 60],
];

export const GB_TYPE_COLOR: Record<string, RGB> = {
  Storage: [150, 120, 230],
  Solar: [255, 214, 72],
  "Wind onshore": [72, 222, 184],
  "Wind offshore": [96, 190, 255],
  Gas: [255, 150, 92],
  Demand: [226, 232, 240],
  Nuclear: [196, 120, 255],
  Interconnector: [178, 146, 255],
  Other: [150, 154, 166],
};

export const gwText = (mw: number) => (mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw).toLocaleString("en-US")} MW`);

/** Sites with a position and the MW waiting there (not yet connected), largest first. */
export function gbSiteTotals(f: ConnectFile["gb"]): { k: number; site: GbSite; mw: number; byType: number[] }[] {
  const out = new Map<number, { k: number; site: GbSite; mw: number; byType: number[] }>();
  for (const p of f.projects) {
    const site = f.sites[p[1]];
    if (site[1] == null) continue;
    const waiting = Math.max(0, p[2] - p[3]);
    if (waiting <= 0) continue;
    const row = out.get(p[1]) ?? { k: p[1], site, mw: 0, byType: f.types.map(() => 0) };
    row.mw += waiting;
    row.byType[p[4]] += waiting;
    out.set(p[1], row);
  }
  return [...out.values()].sort((a, b) => b.mw - a.mw);
}
