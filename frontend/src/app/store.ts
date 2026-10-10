// What the user has chosen: time mode, layers, colour, selection and story. One store, synced
// with the URL so every view can be shared as a link. The map reads it without re-rendering
// React (getState in the render loop); panels subscribe to the parts they show.

import { create } from "zustand";

export type TimeMode = "live" | "day" | "years";

export type LayerId =
  | "flows"
  | "prices"
  | "liveGrids"
  | "towers"
  | "gridEU"
  | "hvdc"
  | "substations"
  | "gridWorld"
  | "predicted"
  | "cables"
  | "plantsEU"
  | "plantsWorld"
  | "gasPipes"
  | "oilPipes"
  | "lngTerminals"
  | "coalTerminals"
  | "oilGasFields"
  | "coalMines"
  | "methane"
  | "gas"
  | "financeCoal"
  | "financeGas"
  | "steel"
  | "cement"
  | "chemicals"
  | "ironOre"
  | "dataCentres"
  | "wind"
  | "sun"
  | "night";

export type LayerGroup = "Electricity now" | "Power grid" | "Power plants" | "Gas, oil & coal" | "Money" | "Industry & data" | "Weather";
export const LAYER_GROUPS: LayerGroup[] = ["Electricity now", "Power grid", "Power plants", "Gas, oil & coal", "Money", "Industry & data", "Weather"];

export interface LayerInfo {
  id: LayerId;
  label: string;
  /** one short line under the name: what the layer shows */
  desc: string;
  group: LayerGroup;
  /** where it has data; "World" is not shown */
  coverage: string;
  /** the layer's colour in the panel */
  color: string;
  /** only in these time modes (all when absent) */
  modes?: TimeMode[];
}
export const LAYERS: LayerInfo[] = [
  { id: "flows", label: "Cross-border flows", desc: "Power moving between countries now", group: "Electricity now", coverage: "Europe", color: "rgb(120,222,255)", modes: ["live", "day"] },
  { id: "prices", label: "Prices", desc: "Each country rises by its day-ahead price; generation towers stand on top", group: "Electricity now", coverage: "Europe", color: "rgb(255,196,90)", modes: ["live", "day"] },
  { id: "liveGrids", label: "Live grids", desc: "US, Brazil, Australia, Taiwan, Ontario now", group: "Electricity now", coverage: "World", color: "rgb(255,196,120)", modes: ["live"] },
  { id: "towers", label: "Generation towers", desc: "Each country's output by source", group: "Electricity now", coverage: "Europe", color: "rgb(255,214,72)", modes: ["day"] },
  { id: "gridEU", label: "Transmission lines", desc: "220–750 kV, by voltage", group: "Power grid", coverage: "Europe", color: "rgb(236,178,120)" },
  { id: "hvdc", label: "HVDC links", desc: "Direct-current links between grids", group: "Power grid", coverage: "Europe", color: "rgb(178,146,255)" },
  { id: "substations", label: "Substations", desc: "220 kV and more, shown zoomed in", group: "Power grid", coverage: "Europe", color: "rgb(226,232,240)" },
  { id: "gridWorld", label: "High-voltage lines", desc: "220 kV and more, mapped in OpenStreetMap", group: "Power grid", coverage: "World", color: "rgb(160,210,255)" },
  { id: "cables", label: "Undersea power cables", desc: "HVDC and AC cables at sea", group: "Power grid", coverage: "World", color: "rgb(110,190,255)" },
  { id: "predicted", label: "Predicted local grid", desc: "Estimated from night lights (Gridfinder)", group: "Power grid", coverage: "World", color: "rgb(255,190,110)" },
  { id: "plantsEU", label: "Power plants", desc: "20 MW and more, by fuel", group: "Power plants", coverage: "Europe", color: "rgb(255,128,72)" },
  { id: "plantsWorld", label: "Power plants worldwide", desc: "Operating, building, planned or retired", group: "Power plants", coverage: "World", color: "rgb(255,214,72)" },
  { id: "gasPipes", label: "Gas pipelines", desc: "Operating, under construction, proposed", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,196,96)" },
  { id: "oilPipes", label: "Oil pipelines", desc: "Crude oil and NGL", group: "Gas, oil & coal", coverage: "World", color: "rgb(222,110,82)" },
  { id: "lngTerminals", label: "LNG terminals", desc: "Import and export, sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,150,92)" },
  { id: "coalTerminals", label: "Coal ports", desc: "Coal export and import terminals", group: "Gas, oil & coal", coverage: "World", color: "rgb(196,182,166)" },
  { id: "oilGasFields", label: "Oil and gas fields", desc: "Where oil and gas are produced", group: "Gas, oil & coal", coverage: "World", color: "rgb(214,96,64)" },
  { id: "coalMines", label: "Coal mines", desc: "Sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(160,146,132)" },
  { id: "methane", label: "Methane plumes", desc: "Leaks seen by satellites", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,90,200)" },
  { id: "gas", label: "Gas storage", desc: "Underground storage sites", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(255,150,92)" },
  { id: "financeCoal", label: "Who finances coal power", desc: "Money from lenders' countries to coal plants", group: "Money", coverage: "World", color: "rgb(232,204,128)" },
  { id: "financeGas", label: "Who finances gas", desc: "Money to gas plants and LNG terminals", group: "Money", coverage: "World", color: "rgb(255,170,60)" },
  { id: "steel", label: "Steel plants", desc: "Electric furnaces stand out", group: "Industry & data", coverage: "World", color: "rgb(120,200,255)" },
  { id: "cement", label: "Cement plants", desc: "Sized by capacity", group: "Industry & data", coverage: "World", color: "rgb(206,192,166)" },
  { id: "chemicals", label: "Chemical plants", desc: "Large chemical sites", group: "Industry & data", coverage: "World", color: "rgb(230,160,255)" },
  { id: "ironOre", label: "Iron ore mines", desc: "Sized by production", group: "Industry & data", coverage: "World", color: "rgb(206,112,88)" },
  { id: "dataCentres", label: "Data centres", desc: "Mapped in OpenStreetMap", group: "Industry & data", coverage: "World", color: "rgb(196,150,255)" },
  { id: "wind", label: "Wind", desc: "Moving wind at turbine height", group: "Weather", coverage: "World", color: "rgb(220,240,255)", modes: ["live", "day"] },
  { id: "sun", label: "Sunshine", desc: "Solar radiation reaching the ground", group: "Weather", coverage: "World", color: "rgb(255,214,72)", modes: ["live", "day"] },
  { id: "night", label: "Night", desc: "Where it is dark at that moment", group: "Weather", coverage: "World", color: "rgb(90,110,160)", modes: ["day"] },
];

/** Layers with their own figures in the panel's "On the map" tab (ui/LayerStats.tsx). */
export const STATS_LAYERS = new Set<LayerId>([
  "liveGrids",
  "plantsWorld",
  "cables",
  "gasPipes",
  "oilPipes",
  "lngTerminals",
  "coalTerminals",
  "oilGasFields",
  "coalMines",
  "methane",
  "financeCoal",
  "financeGas",
  "steel",
  "cement",
  "chemicals",
  "ironOre",
  "dataCentres",
]);

export type ColourId =
  | "none"
  | "renewable"
  | "price"
  | "offline"
  | "pr_negative"
  | "pr_mean"
  | "pr_solar"
  | "pr_wind"
  | "tr_renewables"
  | "tr_wind_solar"
  | "tr_coal"
  | "tr_intensity"
  | "access"
  | "ir_solar"
  | "ir_wind";
export interface ColourInfo {
  id: ColourId;
  label: string;
  group: string;
  modes: TimeMode[];
}
export const COLOURS: ColourInfo[] = [
  { id: "none", label: "Plain", group: "", modes: ["live", "day", "years"] },
  { id: "renewable", label: "Renewable share now", group: "Live", modes: ["live", "day"] },
  { id: "price", label: "Day-ahead price now", group: "Live", modes: ["live", "day"] },
  { id: "offline", label: "Plants offline now", group: "Live", modes: ["live"] },
  { id: "pr_negative", label: "Hours below zero", group: "Prices, 12 months", modes: ["live"] },
  { id: "pr_mean", label: "Average price", group: "Prices, 12 months", modes: ["live"] },
  { id: "pr_solar", label: "Solar capture rate", group: "Prices, 12 months", modes: ["live"] },
  { id: "pr_wind", label: "Wind capture rate", group: "Prices, 12 months", modes: ["live"] },
  { id: "tr_renewables", label: "Renewable share", group: "Yearly (Ember)", modes: ["years"] },
  { id: "tr_wind_solar", label: "Wind + solar share", group: "Yearly (Ember)", modes: ["years"] },
  { id: "tr_coal", label: "Coal share", group: "Yearly (Ember)", modes: ["years"] },
  { id: "tr_intensity", label: "Carbon intensity", group: "Yearly (Ember)", modes: ["years"] },
  { id: "access", label: "Access to electricity", group: "World", modes: ["live", "years"] },
  { id: "ir_solar", label: "Solar PV installed", group: "Capacity (IRENA)", modes: ["live", "years"] },
  { id: "ir_wind", label: "Wind installed", group: "Capacity (IRENA)", modes: ["live", "years"] },
];
export const isPriceColour = (c: ColourId) => c.startsWith("pr_");
export const isYearColour = (c: ColourId) => c.startsWith("tr_");

export type Selection =
  | { kind: "country"; iso2?: string; iso3?: string }
  | { kind: "zone"; id: string }
  | { kind: "region"; grid: "us" | "br" | "au" | "tw" | "on"; id: string };

export type PlantStatus = "operating" | "construction" | "planned" | "retired";

export interface Camera {
  center: [number, number];
  zoom: number;
  pitch?: number;
  bearing?: number;
}
export interface Story {
  id: string;
  label: string;
  blurb: string;
  mode: TimeMode;
  colour: ColourId;
  layers: LayerId[];
  plantStatus?: PlantStatus;
  camera: Camera | "europe" | "world" | "day";
}
export const STORIES: Story[] = [
  {
    id: "europe-live",
    label: "Europe live",
    blurb: "Grid, plants and power flows now",
    mode: "live",
    colour: "renewable",
    layers: ["flows", "gridEU", "hvdc", "substations", "plantsEU"],
    camera: "europe",
  },
  {
    id: "europe-day",
    label: "A day in Europe",
    blurb: "24 hours, every 15 minutes",
    mode: "day",
    colour: "none",
    layers: ["flows", "towers", "prices", "night", "wind", "gridEU"],
    camera: "day",
  },
  {
    id: "price-year",
    label: "The price year",
    blurb: "Hours below zero, capture prices",
    mode: "live",
    colour: "pr_negative",
    layers: [],
    camera: "europe",
  },
  {
    id: "transition",
    label: "25 years of transition",
    blurb: "Every country, 2000–2025",
    mode: "years",
    colour: "tr_renewables",
    layers: [],
    camera: "europe",
  },
  {
    id: "world-building",
    label: "What the world is building",
    blurb: "Plants under construction",
    mode: "live",
    colour: "none",
    layers: ["plantsWorld", "gridWorld"],
    plantStatus: "construction",
    camera: "world",
  },
  {
    id: "world-live",
    label: "Grids beyond Europe",
    blurb: "US, Brazil, Australia, Taiwan, Ontario live",
    mode: "live",
    colour: "access",
    layers: ["liveGrids", "gridWorld", "cables", "dataCentres"],
    camera: "world",
  },
  {
    id: "fuel-routes",
    label: "Fuel routes",
    blurb: "Gas and oil pipelines, LNG and coal ports",
    mode: "live",
    colour: "none",
    layers: ["gasPipes", "oilPipes", "lngTerminals", "coalTerminals"],
    camera: "world",
  },
  {
    id: "methane",
    label: "Methane from space",
    blurb: "Plumes seen by satellites, fields and mines",
    mode: "live",
    colour: "none",
    layers: ["methane", "oilGasFields", "coalMines"],
    camera: "world",
  },
  {
    id: "money",
    label: "Who pays for fossil power",
    blurb: "Banks' money flowing to coal and gas",
    mode: "live",
    colour: "none",
    layers: ["financeCoal", "financeGas"],
    camera: { center: [100, 22], zoom: 2.1 },
  },
  {
    id: "heavy-industry",
    label: "Heavy industry",
    blurb: "Steel, cement and chemical plants",
    mode: "live",
    colour: "none",
    layers: ["steel", "cement", "chemicals", "ironOre"],
    camera: "world",
  },
];

interface AppState {
  mode: TimeMode;
  /** the replayed day (24 h mode); null = newest */
  day: string | null;
  /** integer slot on the 24 h clock, and the year index (both advanced by the map's loop) */
  slot: number;
  yearK: number;
  playing: boolean;
  layers: Record<LayerId, boolean>;
  colour: ColourId;
  plantStatus: PlantStatus;
  plantStyle: "bars" | "beams";
  selection: Selection | null;
  tab: string;
  story: string | null;
  /** where the camera looks: decides the default panel */
  region: "europe" | "world";
  /** a camera move requested by the UI (story, search); the map consumes it */
  flyTo: Camera | "europe" | "world" | "day" | null;
  sheet: "none" | "panel" | "layers" | "search";
  /** the Layers panel is open (desktop) */
  layersPanel: boolean;
}

/** Positions between the integer steps (24 h slot, year), advanced by the map's render loop
 *  every frame without touching React; the store's `slot` and `yearK` follow their floor. */
export const motion = { daySlot: 0, yearPos: 0 };

const allOff = Object.fromEntries(LAYERS.map((l) => [l.id, false])) as Record<LayerId, boolean>;
const layersOf = (ids: LayerId[]) => ({ ...allOff, ...Object.fromEntries(ids.map((id) => [id, true])) });

export const useApp = create<AppState>(() => ({
  mode: "live",
  day: null,
  slot: 0,
  yearK: 0,
  playing: false,
  layers: layersOf(STORIES[0].layers),
  colour: "renewable",
  plantStatus: "operating",
  plantStyle: "bars",
  selection: null,
  tab: "now",
  story: "europe-live",
  region: "europe",
  flyTo: null,
  sheet: "none",
  layersPanel: true,
}));

export const actions = {
  toggleLayer(id: LayerId) {
    useApp.setState((s) => {
      const on = !s.layers[id];
      // a layer with figures opens them in the panel
      return { layers: { ...s.layers, [id]: on }, story: null, tab: on && STATS_LAYERS.has(id) ? "layers" : s.tab };
    });
  },
  setColour(colour: ColourId) {
    const s = useApp.getState();
    useApp.setState({ colour, story: null, tab: colour.startsWith("pr_") && !s.selection ? "prices" : s.tab });
  },
  setMode(mode: TimeMode) {
    const s = useApp.getState();
    if (mode === s.mode) return;
    motion.daySlot = 0;
    motion.yearPos = 0;
    const ok = COLOURS.find((c) => c.id === s.colour)?.modes.includes(mode);
    useApp.setState({
      mode,
      colour: ok ? s.colour : mode === "years" ? "tr_renewables" : "renewable",
      playing: mode !== "live",
      slot: 0,
      yearK: 0,
      story: null,
      layers: mode === "day" ? { ...s.layers, towers: true, night: true } : s.layers,
      tab: mode === "years" ? "years" : s.tab === "years" ? "now" : s.tab,
      flyTo: mode === "day" ? "day" : s.mode === "day" ? "europe" : null,
    });
  },
  setPlantStatus(plantStatus: PlantStatus) {
    useApp.setState((s) => ({ plantStatus, layers: { ...s.layers, plantsWorld: true }, story: null }));
  },
  setPlantStyle(plantStyle: "bars" | "beams") {
    useApp.setState({ plantStyle });
  },
  /** Jump the 24 h clock to a slot (pauses at the end of the day). */
  seekDay(slot: number) {
    motion.daySlot = slot;
    useApp.setState({ slot: Math.floor(slot) });
  },
  seekYear(k: number) {
    motion.yearPos = k;
    useApp.setState({ yearK: Math.floor(k) });
  },
  setDay(day: string) {
    motion.daySlot = 0;
    useApp.setState({ day, slot: 0, playing: true });
  },
  togglePlay() {
    const s = useApp.getState();
    useApp.setState({ playing: !s.playing });
  },
  select(selection: Selection | null, tab = "now") {
    useApp.setState({ selection, tab, sheet: selection ? "panel" : "none" });
  },
  applyStory(id: string) {
    const st = STORIES.find((x) => x.id === id);
    if (!st) return;
    motion.daySlot = 0;
    motion.yearPos = 0;
    useApp.setState({
      story: st.id,
      mode: st.mode,
      colour: st.colour,
      layers: layersOf(st.layers),
      plantStatus: st.plantStatus ?? useApp.getState().plantStatus,
      selection: null,
      tab: st.mode === "years" ? "years" : st.colour.startsWith("pr_") ? "prices" : st.layers.some((l) => STATS_LAYERS.has(l)) ? "layers" : "now",
      region: st.camera === "world" ? "world" : st.camera === "europe" || st.camera === "day" ? "europe" : useApp.getState().region,
      playing: st.mode !== "live",
      slot: 0,
      yearK: 0,
      flyTo: st.camera,
      sheet: "none",
    });
  },
};

/** ?year=2015: resolved once the transition file (and its list of years) has arrived. */
export let yearFromUrl: string | null = null;
export const clearYearFromUrl = () => (yearFromUrl = null);

/** Old links (?day=, ?view=prices, ?country=FR, ...) and new ones (?story=, ?layers=, ...). */
export function readUrl(): void {
  const p = new URLSearchParams(window.location.search);
  const view = p.get("view");
  const story = p.get("story") ?? (p.get("day") ? "europe-day" : view === "prices" ? "price-year" : view === "transition" ? "transition" : view === "world" ? "world-live" : null);
  if (story) actions.applyStory(story);
  const patch: Partial<AppState> = {};
  const mode = p.get("mode");
  if (!story && (mode === "day" || mode === "years")) actions.setMode(mode);
  const day = p.get("day");
  if (day && day !== "latest") patch.day = day;
  const colour = p.get("colour");
  if (colour && COLOURS.some((c) => c.id === colour)) patch.colour = colour as ColourId;
  const metric = p.get("metric");
  if (metric && view === "prices") patch.colour = `pr_${metric}` as ColourId;
  if (metric && view === "transition") patch.colour = `tr_${metric}` as ColourId;
  const layers = p.get("layers");
  if (layers !== null) patch.layers = layersOf(layers.split(",").filter(Boolean) as LayerId[]);
  const status = p.get("status");
  if (status) patch.plantStatus = status as PlantStatus;
  const country = p.get("country");
  const zone = p.get("zone");
  const sel = p.get("sel");
  if (country) patch.selection = { kind: "country", iso2: country.toUpperCase() };
  else if (zone) patch.selection = { kind: "zone", id: zone };
  else if (sel) {
    const [kind, a, b] = sel.split(":");
    if (kind === "country") patch.selection = a.length === 2 ? { kind, iso2: a } : { kind, iso3: a };
    if (kind === "zone") patch.selection = { kind, id: a };
    if (kind === "region") patch.selection = { kind, grid: a as "us" | "br" | "au" | "tw" | "on", id: b };
  }
  const at = p.get("at");
  if (at) {
    // ?at=13:45 opens the day paused at that moment
    const [h, m] = at.split(":").map(Number);
    motion.daySlot = Math.max(0, Math.floor(((h || 0) * 60 + (m || 0)) / 15));
    patch.slot = motion.daySlot;
    patch.playing = false;
  }
  const year = p.get("year");
  if (year && Number.isFinite(Number(year))) yearFromUrl = year;
  const tab = p.get("tab");
  if (tab) patch.tab = tab;
  if (p.get("style") === "beams") patch.plantStyle = "beams";
  if (p.get("panel") === "closed") patch.layersPanel = false;
  const cam = p.get("cam");
  if (cam) {
    const [lon, lat, zoom, pitch, bearing] = cam.split(",").map(Number);
    if ([lon, lat, zoom].every(Number.isFinite)) patch.flyTo = { center: [lon, lat], zoom, pitch: Number.isFinite(pitch) ? pitch : undefined, bearing: bearing || 0 };
  }
  useApp.setState(patch);
}

/** Keep the address bar in step (replaceState: no history entries). */
let lastCamera: Camera | undefined;
export function writeUrl(camera?: Camera): void {
  if (camera) lastCamera = camera;
  camera = lastCamera;
  const s = useApp.getState();
  const p = new URLSearchParams();
  if (s.story) p.set("story", s.story);
  else {
    if (s.mode !== "live") p.set("mode", s.mode);
    p.set("colour", s.colour);
    p.set("layers", (Object.keys(s.layers) as LayerId[]).filter((k) => s.layers[k]).join(","));
  }
  if (s.day) p.set("day", s.day);
  if (s.layers.plantsWorld && s.plantStatus !== "operating") p.set("status", s.plantStatus);
  if (s.plantStyle === "beams") p.set("style", "beams");
  if (!s.layersPanel) p.set("panel", "closed");
  const sel = s.selection;
  if (sel?.kind === "country") p.set("sel", `country:${sel.iso2 ?? sel.iso3}`);
  if (sel?.kind === "zone") p.set("sel", `zone:${sel.id}`);
  if (sel?.kind === "region") p.set("sel", `region:${sel.grid}:${sel.id}`);
  if (sel && s.tab !== "now") p.set("tab", s.tab);
  if (camera) {
    const tilt = camera.pitch || camera.bearing ? `,${(camera.pitch ?? 0).toFixed(0)},${(camera.bearing ?? 0).toFixed(0)}` : "";
    p.set("cam", `${camera.center[0].toFixed(2)},${camera.center[1].toFixed(2)},${camera.zoom.toFixed(2)}${tilt}`);
  }
  window.history.replaceState(null, "", `?${p.toString()}`);
}

// development only: lets headless checks read and set the state
if (import.meta.env.DEV) (window as unknown as { __app: typeof useApp }).__app = useApp;
