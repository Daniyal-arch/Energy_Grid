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

export interface SiteDetail {
  site: Site & Record<string, unknown>;
  detections: Detection[];
  deadlines: Deadline[];
}

export type Point = { date: string; value: number };
export type Series = { ndvi: Point[]; bsi: Point[]; vh_db: Point[] };

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
  timeseries: (id: string) => get<Series>(`/sites/${id}/timeseries`),
  recent: (limit = 50) => get<RecentDetection[]>(`/detections/recent?limit=${limit}`),
  ask: (question: string) => post<AgentResult>("/agent/query", { question }),
};
