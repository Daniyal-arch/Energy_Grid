// What is coming and what it costs (scripts/build_coming.py): hydrogen projects (European
// Hydrogen Observatory), planned gas and hydrogen infrastructure (ENTSOG TYNDP 2026), renewable
// auctions (AURES II), technology costs (NREL ATB, IRENA). Values as published.

import type { RGB } from "./theme";

/** [name, city, ISO3, start year, MW, process, end use, t/year, lon, lat, stage] (indices into the lists) */
export type H2Project = [string, string | null, string | null, number | null, number | null, number | null, number | null, number | null, number, number, number | null];
export interface HydrogenFile {
  fetched: string;
  source: string;
  file: string;
  processes: string[];
  end_uses: string[];
  stages: string[];
  projects: H2Project[];
}
export const H2_STAGE_COLOR: Record<string, RGB> = { Operation: [96, 214, 255], Construction: [255, 196, 96] };
export const H2_OTHER: RGB = [190, 196, 210];
export const h2Color = (f: HydrogenFile, p: H2Project): RGB => (p[10] != null ? (H2_STAGE_COLOR[f.stages[p[10]]] ?? H2_OTHER) : H2_OTHER);
export const h2Radius = (mw: number | null) => (mw == null ? 2.5 : Math.min(14, 2.5 + Math.sqrt(mw) * 0.45));

/** [code, name, ISO3, promoter, maturity, category, first year, last year, CAPEX M EUR, pipeline km, PRJ group] */
export type GasProject = [string, string | null, string | null, string | null, string | null, string, number | null, number | null, number | null, number | null, string | null];
export interface GasProjectsFile {
  fetched: string;
  source: string;
  file: string;
  projects: GasProject[];
  categories: Record<string, string>;
}
/** Hydrogen categories cool, methane warm, the rest grey. */
export const GAS_CAT_COLOR: Record<string, RGB> = {
  TRA: [255, 196, 96],
  LNG: [255, 150, 92],
  UGS: [214, 150, 90],
  H2T: [96, 214, 255],
  H2S: [120, 170, 255],
  H2E: [150, 230, 220],
  H2L: [170, 150, 255],
};
export const GAS_OTHER: RGB = [160, 166, 180];
export const gasColor = (cat: string): RGB => GAS_CAT_COLOR[cat] ?? GAS_OTHER;

/** Projects per country (counted, computed) with the most common category. */
export function gasByCountry(f: GasProjectsFile): Record<string, { n: number; byCat: Record<string, number>; top: string }> {
  const out: Record<string, { n: number; byCat: Record<string, number>; top: string }> = {};
  for (const p of f.projects) {
    if (!p[2]) continue;
    const row = (out[p[2]] ??= { n: 0, byCat: {}, top: "" });
    row.n += 1;
    row.byCat[p[5]] = (row.byCat[p[5]] ?? 0) + 1;
  }
  for (const r of Object.values(out)) r.top = Object.entries(r.byCat).sort((a, b) => b[1] - a[1])[0][0];
  return out;
}

/** [date YYYY-MM, technologies, status, awarded MW, average, lowest, highest awarded price (ct/kWh), bids] */
export type AuctionRound = [string | null, string | null, string | null, number | null, number | null, number | null, number | null, number | null];
export interface AuctionsFile {
  fetched: string;
  source: string;
  file: string;
  doi: string;
  countries: Record<string, AuctionRound[]>;
}

export interface CostsFile {
  fetched: string;
  atb?: {
    source: string;
    edition: string;
    case: string;
    tax_credits: string | null;
    scenario: string;
    crp_years: number;
    years: number[];
    technologies: Record<string, { technology: string; units: Record<string, string>; values: Record<string, Record<string, number>> }>;
  };
  irena?: { source: string; file: string; tables: Record<string, { title: string; rows: Record<string, Record<string, number>> }> };
}
