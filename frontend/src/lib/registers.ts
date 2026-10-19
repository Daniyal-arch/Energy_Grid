// Every generating unit from the national registers (scripts/build_registers.py): GB (REPD and
// DUKES), Denmark and Sweden (every wind turbine), Ireland (wind farms), with positions; France,
// Belgium and Finland as tables (no positions published).

export const REGISTER_LAYERS = { regGB: "GB", regDK: "DK", regSE: "SE", regIE: "IE" } as const;
export type RegisterLayer = keyof typeof REGISTER_LAYERS;
/** every country with a register file, positions or not */
export const REGISTERS = ["GB", "FR", "DK", "SE", "IE", "BE", "FI"] as const;
export const registerKey = (cc: string) => `register${cc}`;

/** [name, lon, lat, group, MW, status, year, register] */
export type RegisterPoint = [string, number, number, string, number | null, string, number | null, string];
export interface RegisterFile {
  fetched: string;
  cc: string;
  source: string;
  url: string;
  licence: string;
  updated: string | null;
  note: string;
  sum_note: string;
  /** {status: {group: [units, MW]}} (computed) */
  totals: Record<string, Record<string, [number, number]>>;
  points: RegisterPoint[];
  table_columns: string[];
  table: (string | number | null)[][];
}

export const STATUS_LABEL: Record<string, string> = {
  operating: "Operating",
  construction: "Being built",
  permitted: "Permitted",
  planning: "In planning",
};
/** paler as a project is further from operation */
export const STATUS_ALPHA: Record<string, number> = { operating: 220, construction: 190, permitted: 140, planning: 100 };
