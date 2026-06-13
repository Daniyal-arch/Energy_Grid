// Typed client for the gridwatch backend. The frontend never talks to Supabase
// directly — the API holds the service-role key and will host the agent.

import type { ConstructionState, Technology } from "./theme";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Site {
  id: string;
  name: string;
  technology: Technology | null;
  status: ConstructionState;
  mastr_status: string | null;
  capacity_mw: number;
  unit_count: number;
  state: string;
  district: string | null;
  municipality: string | null;
  owner: string | null;
  commissioning_date: string | null;
  planned_commissioning_date: string | null;
  lat: number;
  lon: number;
}

export interface Evidence {
  id: string;
  scene_id: string;
  sensor: string;
  acquired_at: string;
  chip_url: string | null;
  metrics: Record<string, number>;
}

export interface Detection {
  id: string;
  detected_at: string;
  from_state: ConstructionState;
  to_state: ConstructionState;
  confidence: "low" | "medium" | "high";
  evidence_ids: string[];
  evidence: Evidence[];
}

export interface SiteDetail {
  site: Site & Record<string, unknown>;
  detections: Detection[];
}

export type Point = { date: string; value: number };
export type Series = { ndvi: Point[]; bsi: Point[]; vh_db: Point[] };

export interface RecentDetection extends Detection {
  site_id: string;
  site: Pick<Site, "id" | "name" | "technology" | "capacity_mw" | "lat" | "lon" | "state">;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export const api = {
  sites: () => get<Site[]>("/sites"),
  site: (id: string) => get<SiteDetail>(`/sites/${id}`),
  timeseries: (id: string) => get<Series>(`/sites/${id}/timeseries`),
  recent: (limit = 50) => get<RecentDetection[]>(`/detections/recent?limit=${limit}`),
};
