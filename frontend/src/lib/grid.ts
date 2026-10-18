// German redispatch 2013-2020 (scripts/build_germany.py) and lines out of service (ENTSO-E A78,
// scripts/build_transmission_outages.py).

export interface RedispatchFile {
  fetched: string;
  source: string;
  measures: number;
  months: string[];
  /** MWh per month (by the measure's start), as summed from the published measures */
  by_direction: Record<string, number[]>;
  by_requesting_tso: Record<string, number[]>;
}

export interface LinesOutFile {
  fetched: string;
  source: string;
  window: [string, string];
  /** [area, element, psr type, voltage, start, end, planned/forced, reason code, reason, lowest available MW] */
  items: [string, string | null, string | null, string | null, string | null, string | null, string, string | null, string | null, number | null][];
  failed: string[];
}
