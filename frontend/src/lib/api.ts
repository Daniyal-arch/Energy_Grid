// Typed client for the Germany InfraAtlas backend. The frontend never talks to Supabase
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
  type:
    | "site"
    | "detection"
    | "evidence"
    | "deadline"
    | "grid_snapshot"
    | "grid_exchange"
    | "context_source";
  id: string;
  label: string;
  url?: string;
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

export interface StrategicAspect {
  id: string;
  label: string;
  questions: string[];
  dataset_ids: string[];
}

export interface StrategicDataset {
  id: string;
  name: string;
  source: string;
  url: string;
  access: string;
  cadence: string;
  status: "implemented" | "partial" | "planned" | "candidate";
  why: string;
  adapter: string | null;
}

export interface StrategicContext {
  aspects: StrategicAspect[];
  datasets: StrategicDataset[];
  note: string;
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

// metric -> { value, ts, source }. metric is "gen_<fuel>" | "carbon_intensity" | "price_eur_mwh"
export type GridSnapshotLatest = Record<string, { value: number; ts: string; source: string }>;
export type GridHistoryPoint = { ts: string; value: number };
export interface GridExchangeRow {
  neighbor_zone: string;
  ts: string;
  value_mw: number; // signed: + = import to DE, - = export
}

export interface RailTimetableEvent {
  id: string;
  station_eva: string | null;
  kind: "arrival" | "departure";
  category: string | null;
  line: string | null;
  operator: string | null;
  planned_time: string | null;
  changed_time: string | null;
  planned_platform: string | null;
  changed_platform: string | null;
  planned_path: string[];
  changed_path: string[];
  status: string | null;
  wings: string | null;
  source: "planned" | "full_changes" | "recent_changes";
}

export interface RailTimetableBoard {
  eva: string;
  station: string | null;
  date: string;
  hour: string;
  generated_at: string;
  planned: RailTimetableEvent[];
  full_changes: RailTimetableEvent[];
  recent_changes: RailTimetableEvent[];
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
  recent: (limit = 50) => get<RecentDetection[]>(`/signals/recent?limit=${limit}`),
  meta: () => get<Meta>("/meta"),
  legalDeadlines: () => get<Record<string, string>>("/deadlines/legal"),
  strategyContext: (aspect?: string) =>
    get<StrategicContext>(`/strategy/context${aspect ? `?aspect=${encodeURIComponent(aspect)}` : ""}`),
  ask: (question: string, history: ChatTurn[]) =>
    post<AgentResult>("/agent/query", { question, history }),
  gridLatest: (zone = "DE") => get<GridSnapshotLatest>(`/grid/latest?zone=${zone}`),
  gridHistory: (metric: string, zone = "DE", hours = 48) =>
    get<GridHistoryPoint[]>(`/grid/history?metric=${metric}&zone=${zone}&hours=${hours}`),
  gridExchange: (zone = "DE") => get<GridExchangeRow[]>(`/grid/exchange?zone=${zone}`),
  railTimetable: (eva = "8000105") => get<RailTimetableBoard>(`/rail/timetables/${eva}`),
};
