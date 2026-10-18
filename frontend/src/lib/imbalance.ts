/** Imbalance prices per zone (scripts/build_imbalance.py, ENTSO-E A85; daily on eu-days). */

/** [average, lowest, highest, periods below zero, periods published] */
export type ImbalanceStats = [number | null, number | null, number | null, number, number];

export interface ImbalanceSeries {
  /** 0 in every period published: not a price (Italy's deficit series) */
  all_zero: boolean;
  /** over the complete days together */
  period: ImbalanceStats | null;
  /** per complete Brussels day of `days` */
  daily: ImbalanceStats[];
  /** the last 7 days at `step_s`, from `chart_start` */
  chart: (number | null)[];
}

export interface ImbalanceZone {
  currency: string | null;
  deficit: ImbalanceSeries | null;
  /** only where it differs from the deficit price */
  excess: ImbalanceSeries | null;
  /** single price: the excess series equals the deficit one */
  same: boolean;
}

export interface ImbalanceFile {
  fetched: string;
  source: string;
  days: string[];
  chart_start: string;
  step_s: number;
  zones: Record<string, ImbalanceZone>;
  /** zones ENTSO-E sent no imbalance price for */
  none: string[];
}
