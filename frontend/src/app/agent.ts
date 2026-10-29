// Ask: the agent in the app. A question goes to the backend (POST /api/ask, Server-Sent Events:
// text, tool, map, chart, sources, done, error; backend/app/sse.py); its maps arrive as MapSpecs
// with an id, their data is read from the saved map (GET /api/maps/{id}) and drawn by
// map/agentLayers.ts: one map on the main map, or several maps side by side in the Maps view.
// The maps on screen go back with each question, so the agent can change them ("make it 3D").

import { create } from "zustand";

import type { ChartSpec, MapSpec, Overlay } from "../lib/mapspec";
import { polysOfGeometry, type AreaSpec } from "../lib/area";
import type { AgentDraw, ShapeFeature } from "../map/agentLayers";
import { DATASET_OF_LAYER } from "./datasets";
import type { MapPanel } from "./maps";
import { actions, currentCamera, useApp, type CameraPreset, type LayerId } from "./store";

/** The backend's origin: the dev server proxies /api to it (vite.config.ts). */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export interface Source {
  dataset?: string;
  table?: string;
  licence?: string;
  retrieved?: string;
}
export interface MapData {
  columns: string[];
  rows: unknown[][];
}
/** An area resolved by the agent (resolve_area), as the map record carries it. */
export interface AreaRec {
  area_id: string;
  name: string;
  level: string;
  bbox: [number, number, number, number];
  area_km2: number;
  geometry: { type: string; coordinates: unknown };
}
export interface AgentMap {
  id: string;
  spec: MapSpec;
  data: Record<string, MapData>;
  sources: Source[];
  /** the areas the map shows (spec.area, panels' area), outlines simplified for display */
  areas?: Record<string, AreaRec>;
  /** outlines of the backend's shape sets by key (choropleths below the country level) */
  shapes?: Record<string, { features: Record<string, ShapeFeature>; source?: string }>;
}
export interface ToolStep {
  name: string;
  args?: unknown;
  status: "running" | "done";
  ms?: number;
  rows?: number | null;
  error?: string | null;
}
export interface ChartMsg {
  spec: ChartSpec;
  rows: Record<string, unknown>[];
}
export interface Done {
  trace_id?: string;
  grounding?: { numbers?: number; grounded?: number; ungrounded?: string[]; score?: number };
  cost_usd?: number | null;
  latency_ms?: number;
  model?: string;
  stop?: string | null;
}
/** The router's plan: what kind of answer, a map, a chart, an edit, the skills it loads. */
export interface Plan {
  kind?: string;
  map?: boolean;
  chart?: boolean;
  edit?: boolean;
  skills?: string[];
}
/** The cartographer's design: the styles it chose, how many maps, and why. */
export interface Design {
  styles: string[];
  maps: number;
  edit: boolean;
  note: string;
  tries: number;
}
export interface Msg {
  id: string;
  role: "user" | "assistant";
  text: string;
  plan?: Plan;
  design?: Design;
  tools: ToolStep[];
  maps: string[];
  charts: ChartMsg[];
  sources: Source[];
  done?: Done;
  error?: string;
  pending: boolean;
}

interface AgentState {
  messages: Msg[];
  maps: Record<string, AgentMap>;
  /** the agent map drawn on the main map (one map); panels go to the Maps view */
  onMap: string | null;
  busy: boolean;
  /** the Ask chat is open at the side (ui/AskTab.tsx) */
  open: boolean;
  conversationId: string;
}

export const useAgent = create<AgentState>(() => ({
  messages: [],
  maps: {},
  onMap: null,
  busy: false,
  open: false,
  conversationId: `c_${Math.random().toString(36).slice(2, 10)}`,
}));

const STYLES_3D = new Set(["columns", "beams", "spikes", "lollipops", "hex_columns", "grid_columns", "prisms", "arcs_3d", "terrain", "point_cloud", "arcs"]);
export const is3DOverlay = (o: Overlay) => STYLES_3D.has(o.kind);
export const overlaysOf = (spec: MapSpec): Overlay[] => [...(spec.overlays ?? []), ...(spec.panels ?? []).flatMap((p) => p.overlays ?? [])];

let n = 0;
const nextId = () => `msg_${Date.now().toString(36)}_${n++}`;

function patchLast(fn: (m: Msg) => Msg): void {
  useAgent.setState((s) => {
    const msgs = s.messages.slice();
    const i = msgs.length - 1;
    if (i >= 0 && msgs[i].role === "assistant") msgs[i] = fn(msgs[i]);
    return { messages: msgs };
  });
}

/** What the agent should know about the screen: its maps on screen, the layers on, the area. */
/** The drawn area as the agent reads it ("what I drew"); an agent area goes back by its id. */
function drawnOf(d: AreaSpec | null): Record<string, unknown> | null {
  if (!d) return null;
  if (d.kind !== "shape") return d;
  const points = d.polygons.reduce((n, p) => n + p.reduce((k, r) => k + r.length / 2, 0), 0);
  return { kind: "shape", area_id: d.areaId, name: d.name, ...(points <= 5000 ? { polygons: d.polygons } : {}) };
}

function viewOf(): Record<string, unknown> {
  const s = useApp.getState();
  const a = useAgent.getState();
  const shown = new Set<string>([...(a.onMap ? [a.onMap] : []), ...(s.compare ? s.maps.flatMap((m) => (m.agent ? [m.agent.mapId] : [])) : [])]);
  const cam = currentCamera();
  return {
    maps: [...shown].filter((id) => a.maps[id]).map((id) => ({ id, spec: a.maps[id].spec })),
    layers: Object.entries(s.layers)
      .filter(([, on]) => on)
      .map(([k]) => k),
    area: s.area,
    drawn: drawnOf(s.drawn),
    camera: cam ? { center: cam.center, zoom: Math.round(cam.zoom * 10) / 10, ...(cam.box ? { bounds: cam.box.map((v) => Math.round(v * 1e4) / 1e4) } : {}) } : null,
  };
}

function cameraOf(spec: MapSpec): CameraPreset | null {
  const c = spec.camera;
  const tilt = overlaysOf(spec).some(is3DOverlay);
  if (c?.bbox) return { bounds: c.bbox };
  if (c?.center) return { center: c.center, zoom: c.zoom ?? 5, pitch: tilt ? 50 : 0 };
  if (c?.preset) return c.preset;
  if (tilt) {
    const cur = currentCamera();
    if (cur && !cur.pitch) return { ...cur, pitch: 50 };
  }
  return null;
}

/** Draw an agent map: one map on the main map, or its panels in the Maps view. */
export function showAgentMap(id: string): void {
  const m = useAgent.getState().maps[id];
  if (!m) return;
  const spec = m.spec;
  const s = useApp.getState();
  const layers = [...(spec.app?.layers ?? []), ...(spec.panels ?? []).flatMap((p) => p.app?.layers ?? [])].filter((l) => l in s.layers) as LayerId[];
  if (layers.length) useApp.setState({ layers: { ...s.layers, ...Object.fromEntries(layers.map((l) => [l, true])) } });
  const areaOf = (ref?: { area_id: string } | null) => {
    const a = ref ? m.areas?.[ref.area_id] : undefined;
    return a && a.level !== "world" ? specOfArea(a) : undefined;
  };
  // the map's area becomes the app's area: outline, veil, base layers clipped, camera framed
  const main = areaOf(spec.area);
  if (main) actions.setDrawn(main);
  if (spec.panels?.length) {
    const panels: MapPanel[] = spec.panels.map((p, i) => ({
      title: p.title,
      ...(areaOf(p.area) ? { drawn: areaOf(p.area) } : {}),
      items: (p.app?.layers ?? []).flatMap((l) => {
        const d = DATASET_OF_LAYER.get(l as LayerId);
        return d ? [{ dataset: d.id, style: "points" as const }] : [];
      }),
      agent: { mapId: id, panel: i },
    }));
    actions.setMaps(panels);
    actions.setCompare(true);
    useAgent.setState({ onMap: null });
  } else {
    useAgent.setState({ onMap: id });
    if (s.compare) actions.setCompare(false);
  }
  const cam = cameraOf(spec);
  if (cam) useApp.setState({ flyTo: cam });
}

export function removeAgentMap(id: string): void {
  const a = useAgent.getState();
  if (a.onMap === id) useAgent.setState({ onMap: null });
  const s = useApp.getState();
  if (s.maps.some((m) => m.agent?.mapId === id)) {
    actions.setMaps(s.maps.filter((m) => m.agent?.mapId !== id));
    if (!s.maps.some((m) => m.agent?.mapId !== id)) actions.setCompare(false);
  }
}

async function loadMap(id: string, spec: MapSpec): Promise<void> {
  let rec: Omit<AgentMap, "id"> | null = null;
  try {
    const r = await fetch(`${API_BASE}/api/maps/${id}`);
    if (r.ok) rec = await r.json();
  } catch {
    rec = null;
  }
  const map: AgentMap = { id, spec: rec?.spec ?? spec, data: rec?.data ?? {}, sources: rec?.sources ?? [], areas: rec?.areas, shapes: rec?.shapes };
  useAgent.setState((s) => ({ maps: { ...s.maps, [id]: map } }));
  if (map.spec.replaces) removeAgentMap(map.spec.replaces);
  patchLast((m) => ({ ...m, maps: [...m.maps, id] }));
  showAgentMap(id);
}

function onEvent(name: string, data: Record<string, unknown>): void {
  if (name === "text") {
    if (data.reset) patchLast((m) => ({ ...m, text: "" }));
    else if (typeof data.delta === "string") patchLast((m) => ({ ...m, text: m.text + (data.delta as string) }));
  } else if (name === "tool") {
    const t = data as unknown as ToolStep & { status: string };
    patchLast((m) => {
      if (t.status === "running") return { ...m, tools: [...m.tools, { name: t.name, args: t.args, status: "running" }] };
      const tools = m.tools.slice();
      const i = tools.map((x) => x.name).lastIndexOf(t.name);
      if (i >= 0) tools[i] = { ...tools[i], status: "done", ms: t.ms, rows: t.rows, error: t.error };
      return { ...m, tools };
    });
  } else if (name === "plan") {
    patchLast((m) => ({ ...m, plan: data as Plan }));
  } else if (name === "design") {
    patchLast((m) => ({ ...m, design: data as unknown as Design }));
  } else if (name === "map") {
    void loadMap(String(data.id), data.spec as MapSpec);
  } else if (name === "chart") {
    patchLast((m) => ({ ...m, charts: [...m.charts, { spec: data.spec as ChartSpec, rows: (data.rows as Record<string, unknown>[]) ?? [] }] }));
  } else if (name === "sources") {
    patchLast((m) => ({ ...m, sources: (data.sources as Source[]) ?? [] }));
  } else if (name === "done") {
    const answer = typeof data.answer === "string" ? data.answer : "";
    patchLast((m) => ({ ...m, done: data as Done, text: m.text || answer, pending: false }));
  } else if (name === "error") {
    patchLast((m) => ({ ...m, error: String(data.message ?? "error"), pending: false }));
  }
}

/** Ask a question; the answer streams into the last message. */
export async function ask(question: string): Promise<void> {
  const q = question.trim();
  const st = useAgent.getState();
  if (!q || st.busy) return;
  const history = st.messages
    .filter((m) => m.text)
    .slice(-8)
    .map((m) => ({ role: m.role, content: m.text.slice(0, 4000) }));
  const view = viewOf();
  useAgent.setState((s) => ({
    busy: true,
    messages: [
      ...s.messages,
      { id: nextId(), role: "user", text: q, tools: [], maps: [], charts: [], sources: [], pending: false },
      { id: nextId(), role: "assistant", text: "", tools: [], maps: [], charts: [], sources: [], pending: true },
    ],
  }));
  try {
    const r = await fetch(`${API_BASE}/api/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: q, history, view, conversation_id: st.conversationId }),
    });
    if (!r.ok || !r.body) {
      const detail = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}${detail ? `: ${detail.slice(0, 200)}` : ""}`);
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut: number;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        let ev = "";
        let payload = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) ev = line.slice(6).trim();
          else if (line.startsWith("data:")) payload += line.slice(5).trim();
        }
        if (ev && payload) {
          try {
            onEvent(ev, JSON.parse(payload));
          } catch {
            /* a malformed event is skipped */
          }
        }
      }
    }
  } catch (e) {
    patchLast((m) => ({ ...m, error: e instanceof Error ? e.message : String(e) }));
  } finally {
    patchLast((m) => ({ ...m, pending: false }));
    useAgent.setState({ busy: false });
  }
}

// ---------------------------------------------------------------- what the maps draw

const ROWS = new WeakMap<MapData, Record<string, unknown>[]>();
function rowsOf(m: AgentMap, o: Overlay): Record<string, unknown>[] {
  if (o.data.inline) return o.data.inline as Record<string, unknown>[];
  const d = o.data.result_id ? m.data[o.data.result_id] : undefined;
  if (!d) return [];
  let rows = ROWS.get(d);
  if (!rows) {
    rows = d.rows.map((r) => Object.fromEntries(d.columns.map((c, i) => [c, r[i]])));
    ROWS.set(d, rows);
  }
  return rows;
}
const DRAWS = new Map<string, AgentDraw[]>();
/** The outlines an overlay's keys refer to when the backend served them (or the area itself). */
function servedShapes(m: AgentMap, o: Overlay): Record<string, ShapeFeature> | undefined {
  const set = o.data.shapes;
  if (!set) return undefined;
  if (set === "area") {
    const out: Record<string, ShapeFeature> = {};
    for (const a of Object.values(m.areas ?? {})) out[a.area_id] = { name: a.name, at: [(a.bbox[0] + a.bbox[2]) / 2, (a.bbox[1] + a.bbox[3]) / 2], geometry: a.geometry };
    return out;
  }
  return m.shapes?.[set]?.features;
}

/** An agent area as the app's area (several polygons of flat lon/lat pairs). */
export function specOfArea(a: AreaRec): AreaSpec {
  return { kind: "shape", polygons: polysOfGeometry(a.geometry).map((p) => p.map((ring) => ring.flat())), name: a.name, areaId: a.area_id };
}

function drawsOf(m: AgentMap, overlays: Overlay[], key: string): AgentDraw[] {
  const k = `${m.id}:${key}:${Object.keys(m.data).length}`;
  let d = DRAWS.get(k);
  if (!d) {
    d = overlays.map((overlay) => ({ mapId: m.id, overlay, rows: rowsOf(m, overlay), shapes: servedShapes(m, overlay) }));
    DRAWS.set(k, d);
  }
  return d;
}

/** The overlays the main map draws: the agent's one-map answer shown now. */
export function mainAgentDraws(): AgentDraw[] {
  const a = useAgent.getState();
  const m = a.onMap ? a.maps[a.onMap] : undefined;
  return m ? drawsOf(m, m.spec.overlays ?? [], "main") : [];
}

/** The overlays of one panel of an agent map (the Maps view). */
export function panelAgentDraws(mapId: string, panel: number): AgentDraw[] {
  const m = useAgent.getState().maps[mapId];
  const p = m?.spec.panels?.[panel];
  return m && p ? drawsOf(m, p.overlays ?? [], `p${panel}`) : [];
}

/** The main map tilts while it shows a 3D agent style. */
export function agentIs3D(): boolean {
  return mainAgentDraws().some((d) => is3DOverlay(d.overlay));
}

export function clearConversation(): void {
  const a = useAgent.getState();
  for (const id of Object.keys(a.maps)) removeAgentMap(id);
  useAgent.setState({ messages: [], maps: {}, onMap: null, conversationId: `c_${Math.random().toString(36).slice(2, 10)}` });
}

// ?aid=a_... (a link to an agent area): its outline from the backend becomes the app's area
const linkedArea = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("aid") : null;
if (linkedArea && /^a_[0-9a-f]{12}$/.test(linkedArea)) {
  void fetch(`${API_BASE}/api/areas/${linkedArea}`)
    .then((r) => (r.ok ? (r.json() as Promise<AreaRec>) : null))
    .then((a) => {
      if (a) actions.setDrawn(specOfArea(a));
    })
    .catch(() => undefined);
}
