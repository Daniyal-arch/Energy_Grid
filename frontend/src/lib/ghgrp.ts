// US industrial emitters (scripts/build_us_perf.py ghgrp): EPA GHGRP direct emitters, t CO2e as
// reported, positions from Envirofacts.

import { CT_COLOR } from "./ctrace";
import type { RGB } from "./theme";

export interface GhgrpFile {
  fetched: string;
  year: number;
  source: string;
  sectors: string[];
  /** [lon, lat, t CO2e, sector index, name, state], largest first */
  points: [number, number, number, number, string, string][];
}

/** GHGRP's sectors on Climate TRACE's colours (`CT_COLOR`): the same kind of emitter, the same colour. */
const CT_OF: Record<string, number> = {
  "Power Plants": 0,
  Metals: 1,
  Minerals: 2,
  Chemicals: 3,
  Refineries: 3,
  "Petroleum and Natural Gas Systems": 4,
};
export const ghgrpColor = (sector: string): RGB => CT_COLOR[CT_OF[sector] ?? 6];
/** dot radius in pixels: area follows t CO2e (1 Mt about 6 px) */
export const ghgrpRadius = (t: number) => Math.max(1.2, Math.sqrt(t / 1e6) * 6);
