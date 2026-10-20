// More regional and live grids (scripts/build_regional_live.py): France's regions (RTE éCO2mix
// régional), Spain's autonomous communities (REE REData), New Zealand (Transpower, em6) and
// South Africa (Eskom). Values as published.

export interface FrRegionsFile {
  fetched: string;
  source: string;
  regions: Record<string, { name: string; nuts1: string | null; ts: string; mw: Record<string, number | null>; consumption_24h: [string, number | null][] }>;
}
export interface EsRegionsFile {
  fetched: string;
  source: string;
  unit: string;
  regions: Record<string, { name: string; nuts2: string; mwh: Record<string, Record<string, number>> }>;
}
export interface NzFile {
  fetched: string;
  source: string;
  at: string;
  total_mw: number;
  fuels: Record<string, { mw: number | null; capacity_mw: number | null }>;
  load: Record<string, [string, number][]>;
}
export interface ZaFile {
  fetched: string;
  source: string;
  loadshedding_stage: number | null;
  demand?: { url: string; columns: string[]; rows: string[][] };
  supply?: { url: string; columns: string[]; rows: string[][] };
}
export const NZ_POINT: [number, number] = [174.5, -40.8];
export const NZ_COLOR: [number, number, number] = [120, 222, 200];
export const ZA_POINT: [number, number] = [25.5, -29.0];
export const ZA_COLOR: [number, number, number] = [255, 180, 110];
export const FR_LABEL: Record<string, string> = {
  nucleaire: "Nuclear",
  eolien: "Wind",
  solaire: "Solar",
  hydraulique: "Hydro",
  thermique: "Fossil thermal",
  bioenergies: "Bioenergy",
  pompage: "Pumping",
  destockage_batterie: "Battery discharge",
  stockage_batterie: "Battery charge",
};
