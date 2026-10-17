// Every large solar array in the US (scripts/fetch_uspvdb.py): the USPVDB facilities and,
// zoomed in, their outlines. Values are USGS/LBNL's own.

/** [lon, lat, MW AC, MW DC, year, name, state, county, axis, system type, site type,
 *  agrivoltaic, technology, battery, EIA plant id, image date] (categories as indices) */
export type SolarSite = [
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  string | null,
  string | null,
  string | null,
  number | null,
  number | null,
  number | null,
  number | null,
  number | null,
  string | null,
  number | null,
  number | null,
];

export interface UsSolarFile {
  source: string;
  release: string;
  fetched: string;
  fields: string[];
  /** p_axis, p_sys_type, p_type, p_agrivolt, p_tech_pri: the published values */
  categories: Record<string, string[]>;
  sites: SolarSite[];
}

export interface UsSolarOutlinesFile {
  release: string;
  /** per site, same order: [polygon][ring] of flat lon/lat pairs */
  polygons: number[][][][];
}

/** From this zoom the outlines load and draw instead of the dots. */
export const SOLAR_OUTLINE_ZOOM = 7.5;

export const solarCat = (f: UsSolarFile, field: string, k: number | null) => (k == null ? null : (f.categories[field]?.[k] ?? null));
