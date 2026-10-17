// Offshore wind farms in European seas (scripts/fetch_emodnet_wind.py): EMODnet Human
// Activities' farm areas and the point records without an area. Values are EMODnet's own.

import type { RGB } from "./theme";

export interface OffshoreFarm {
  name: string | null;
  country: string | null;
  iso3: string | null;
  /** index into OffshoreWindFile.statuses */
  status: number | null;
  mw: number | null;
  turbines: number | null;
  year: number | null;
  coast_km: number | null;
  at: [number, number];
  /** [polygon][ring] of flat lon/lat pairs; null for a point record */
  polygons: number[][][] | null;
}

export interface OffshoreWindFile {
  fetched: string;
  source: string;
  licence: string;
  /** EMODnet's statuses: Production, Construction, Approved, Planned, Test site, Dismantled */
  statuses: string[];
  farms: OffshoreFarm[];
}

export const OFFSHORE_LABEL: Record<string, string> = {
  Production: "Operating",
  Construction: "Under construction",
  Approved: "Approved",
  Planned: "Planned",
  "Test site": "Test site",
  Dismantled: "Dismantled",
};

/** Calm: built farms solid, planned ones faint. [colour, fill alpha] */
export const OFFSHORE_STYLE: Record<string, [RGB, number]> = {
  Production: [[96, 190, 255], 130],
  Construction: [[72, 222, 184], 120],
  Approved: [[196, 214, 236], 70],
  Planned: [[140, 152, 176], 34],
  "Test site": [[178, 146, 255], 100],
  Dismantled: [[90, 96, 110], 40],
};

export const offshoreStatus = (f: OffshoreWindFile, farm: OffshoreFarm) => (farm.status != null ? f.statuses[farm.status] : "");
