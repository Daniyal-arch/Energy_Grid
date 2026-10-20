// Room to connect in six more countries (scripts/build_connect_more.py): the operators' own
// figures for France (Capareseau), Italy (Terna Econnextion), Belgium (Elia), Portugal
// (E-REDES), Ireland (ESB Networks) and Poland (PSE). Values as published.

import { NL_COLOR } from "./connect";
import type { RGB } from "./theme";

/** [code, name, region, lon, lat, u max kV, updated, values per code] */
export type FrSite = [string, string, string, number, number, number | null, string | null, (number | string | null)[]];
export interface FrFile {
  fetched: string;
  source: string;
  url: string;
  codes: string[];
  labels: Record<string, string>;
  sites: FrSite[];
}

/** {region: {source: [MW, requests]}} */
export type ItRegions = Record<string, Record<string, [number, number | null]>>;
export interface ItFile {
  fetched: string;
  source: string;
  renewables: { regions: ItRegions; provinces: Record<string, string | number>[] };
  storage: { regions: ItRegions; provinces: Record<string, string | number>[] };
  nuts2: Record<string, string[]>;
  /** NUTS-2 id -> [polygon][ring] of flat lon/lat pairs */
  shapes: Record<string, number[][][]>;
}

/** [code, name, type, district, municipality, NUTS-3 name, RNT bus, values of columns] */
export type PtRow = [string, string, string, string, string, string, string | null, (number | null)[]];
export interface PtFile {
  fetched: string;
  source: string;
  date: string;
  columns: string[];
  substations: PtRow[];
}

/** [name, primary kV, voltage class, lon, lat, values of columns, comment] */
export type IeStation = [string, string | null, string | null, number, number, (number | null)[], string | null];
export interface IeFile {
  fetched: string;
  source: string;
  file: string;
  transformers_total: number;
  columns: string[];
  stations: IeStation[];
}

/** [name, type, status, voltage, MW injected, MW withdrawn, location] */
export type PlRequest = [string, string | null, string | null, number | string | null, number | null, number | null, string | null];
export interface PlFile {
  fetched: string;
  source: string;
  date: string | null;
  requests: PlRequest[];
  /** [station, symbol, switchgear, PSE area]: no free connection bays */
  full: [string, string, string, string][];
}

export interface BeFile {
  fetched: string;
  source: string;
  file: string;
  sheets: Record<string, { columns: string[]; rows: (number | string | null)[][] }>;
}

/** MW (or MVA) left at a substation, in four classes for the map (the panel shows the value). */
export const ROOM_CLASSES = ["50 or more", "10 to 50", "under 10", "none"];
export function roomClass(v: number | null | undefined): number {
  if (v == null) return -1;
  return v >= 50 ? 0 : v >= 10 ? 1 : v > 0 ? 2 : 3;
}
export const roomColor = (v: number | null | undefined): RGB => NL_COLOR[Math.max(0, roomClass(v))];

export const frValue = (f: FrFile, s: FrSite, code: string): number | string | null => {
  const k = f.codes.indexOf(code);
  return k >= 0 ? s[7][k] : null;
};
export const frNumber = (f: FrFile, s: FrSite, code: string): number | null => {
  const v = frValue(f, s, code);
  return typeof v === "number" ? v : null;
};

/** Ireland: demand (MVA) or generation, firm (MW), available at a station. */
export const ieRoom = (f: IeFile, s: IeStation, side: "offtake" | "feedin"): number | null =>
  s[5][f.columns.indexOf(side === "offtake" ? "demand_available_mva" : "gen_available_firm_mw")] ?? null;

/** Italy: MW requested per region (renewables and storage), summed over sources (computed). */
export function itTotals(f: ItFile): Record<string, { fer: number; storage: number; n: number }> {
  const out: Record<string, { fer: number; storage: number; n: number }> = {};
  for (const [key, part] of [["fer", f.renewables], ["storage", f.storage]] as const)
    for (const [reg, by] of Object.entries(part.regions)) {
      const row = (out[reg] ??= { fer: 0, storage: 0, n: 0 });
      for (const [mw, n] of Object.values(by)) {
        row[key] += mw;
        row.n += n ?? 0;
      }
    }
  return out;
}
/** GW requested, four classes for the shading. */
export const IT_CLASSES = ["under 10 GW", "10 to 30 GW", "30 to 60 GW", "60 GW or more"];
export const IT_COLOR: RGB[] = [
  [96, 84, 70],
  [150, 112, 70],
  [206, 138, 72],
  [240, 170, 90],
];
export const itClass = (mw: number) => (mw >= 60_000 ? 3 : mw >= 30_000 ? 2 : mw >= 10_000 ? 1 : 0);

export const PT_LABEL: Record<string, string> = {
  potencia_de_ligacao_ligado_mva_ultimo_trimestre: "Connected (MVA)",
  potencia_de_ligacao_comprometido_mva_ultimo_trimestre: "Committed (MVA)",
  potencia_de_ligacao_em_confirmacao_mva_ultimo_trimestre: "Being confirmed (MVA)",
  capacidade_de_recepcao_at_mva_ultimo_trimestre: "Reception capacity, HV (MVA)",
  capacidade_de_recepcao_mt_at_mva_ultimo_trimestre: "Reception capacity, MV+HV (MVA)",
  capacidade_de_recepcao_mt_30kv_mva_ultimo_trimestre: "Reception capacity, MV 30 kV (MVA)",
  capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre: "Reception capacity, MV 15 kV (MVA)",
  capacidade_de_recepcao_mt_10kv_mva_ultimo_trimestre: "Reception capacity, MV 10 kV (MVA)",
};
