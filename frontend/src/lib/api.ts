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

export interface Deadline {
  id: string;
  source: string;
  deadline_date: string;
  type: "legal_completion" | "planned_commissioning" | string;
}

export interface GridUnit {
  eic: string;
  name: string;
  capacity_mw: number | null;
  psr_type: string | null;
}

export interface SiteDetail {
  site: Site & Record<string, unknown>;
  detections: Detection[];
  deadlines: Deadline[];
  grid_unit: GridUnit | null;
}

export type Point = { date: string; value: number };
export type Series = { ndvi: Point[]; bsi: Point[]; vh_db: Point[] };
export type GenPoint = { date: string; mwh: number };

export interface RecentDetection extends Detection {
  site_id: string;
  site: Pick<Site, "id" | "name" | "technology" | "capacity_mw" | "lat" | "lon" | "state">;
}

export interface Citation {
  type: "site" | "detection" | "evidence";
  id: string;
  label: string;
}
export interface AgentResult {
  answer: string;
  sources: Citation[];
  site_ids: string[];
  provider: string;
  follow_ups: string[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface Meta {
  latest_observation: string | null;
  sites: number;
  analysed: number;
}

// GeoJSON MultiPolygon as PostgREST serializes PostGIS geometry
export interface GeoMultiPolygon {
  type: "MultiPolygon";
  coordinates: number[][][][];
}
export interface Footprint {
  id: string;
  geom: GeoMultiPolygon;
  status: ConstructionState;
  technology: Technology | null;
  unit_count: number;
  capacity_mw: number;
  aoi_method: string | null;
  lat: number;
  lon: number;
}

export interface Turbine {
  id: string;
  lat: number;
  lon: number;
  hub_height_m: number | null;
  rotor_diameter_m: number | null;
  capacity_kw: number | null;
  status: string | null;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${path} → ${res.status}`);
  }
  return res.json();
}

export const api = {
  sites: () => get<Site[]>("/sites"),
  site: (id: string) => get<SiteDetail>(`/sites/${id}`),
  footprint: (id: string) => get<Footprint>(`/sites/${id}/footprint`),
  turbines: (id: string) => get<Turbine[]>(`/sites/${id}/turbines`),
  timeseries: (id: string) => get<Series>(`/sites/${id}/timeseries`),
  powerOutput: (technology: string) => get<GenPoint[]>(`/power-output/${technology}`),
  recent: (limit = 50) => get<RecentDetection[]>(`/detections/recent?limit=${limit}`),
  meta: () => get<Meta>("/meta"),
  legalDeadlines: () => get<Record<string, string>>("/deadlines/legal"),
  ask: (question: string, history: ChatTurn[]) =>
    post<AgentResult>("/agent/query", { question, history }),
};
