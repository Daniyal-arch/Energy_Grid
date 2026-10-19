// What the user has chosen: time mode, layers, colour, selection and story. One store, synced
// with the URL so every view can be shared as a link. The map reads it without re-rendering
// React (getState in the render loop); panels subscribe to the parts they show.

import { create } from "zustand";

import type { WaterIndicator } from "../lib/risk";
import type { MastrTech } from "../lib/mastr";

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
  | "gridUS"
  | "predicted"
  | "cables"
  | "plantsEU"
  | "plantsWorld"
  | "plantsUS"
  | "turbinesUS"
  | "solarUS"
  | "grw"
  | "tyndp"
  | "ghgrpUS"
  | "solarResource"
  | "windResource"
  | "evChargersUS"
  | "usQueue"
  | "gasPipes"
  | "oilPipes"
  | "lngTerminals"
  | "coalTerminals"
  | "oilGasFields"
  | "coalMines"
  | "methane"
  | "gas"
  | "gasFlows"
  | "lngSendOut"
  | "ets"
  | "ctrace"
  | "connect"
  | "usNodePrices"
  | "plantOutput"
  | "financeCoal"
  | "financeGas"
  | "steel"
  | "cement"
  | "chemicals"
  | "ironOre"
  | "dataCentres"
  | "usOutages"
  | "water"
  | "protectedAreas"
  | "hydrogen"
  | "gasProjects"
  | "flood"
  | "roadsRail"
  | "mastrDE"
  | "offshoreWind"
  | "wind"
  | "sun"
  | "night";

export type LayerGroup = "Electricity now" | "Power grid" | "Power plants" | "Gas, oil & coal" | "Money" | "Industry & data" | "Risk" | "Weather";
export const LAYER_GROUPS: LayerGroup[] = ["Electricity now", "Power grid", "Power plants", "Gas, oil & coal", "Money", "Industry & data", "Risk", "Weather"];

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
  /** listed in the Layers panel only while on: the layer belongs to this story */
  story?: string;
}
export const LAYERS: LayerInfo[] = [
  { id: "flows", label: "Cross-border flows", desc: "Power moving between countries now", group: "Electricity now", coverage: "Europe", color: "rgb(120,222,255)", modes: ["live", "day"] },
  { id: "prices", label: "Prices", desc: "Each country rises by its day-ahead price; generation towers stand on top", group: "Electricity now", coverage: "Europe", color: "rgb(255,196,90)", modes: ["live", "day"] },
  { id: "liveGrids", label: "Live grids", desc: "US, Brazil, Australia, Taiwan, Ontario, New Zealand, South Africa now", group: "Electricity now", coverage: "World", color: "rgb(255,196,120)", modes: ["live"] },
  { id: "usNodePrices", label: "Node prices", desc: "Day-ahead price at each placed node, hour by hour", group: "Electricity now", coverage: "US West", color: "rgb(255,196,90)", modes: ["day"] },
  { id: "towers", label: "Generation towers", desc: "Each country's (or US region's) output by source", group: "Electricity now", coverage: "Europe, US", color: "rgb(255,214,72)", modes: ["day"] },
  { id: "gridEU", label: "Transmission lines", desc: "220–750 kV, by voltage", group: "Power grid", coverage: "Europe", color: "rgb(236,178,120)" },
  { id: "hvdc", label: "HVDC links", desc: "Direct-current links between grids", group: "Power grid", coverage: "Europe", color: "rgb(178,146,255)" },
  { id: "substations", label: "Substations", desc: "220 kV and more, shown zoomed in", group: "Power grid", coverage: "Europe", color: "rgb(226,232,240)" },
  { id: "gridWorld", label: "High-voltage lines", desc: "220 kV and more, mapped in OpenStreetMap", group: "Power grid", coverage: "World", color: "rgb(160,210,255)" },
  { id: "gridUS", label: "US transmission lines", desc: "100–765 kV by voltage, mapped in OpenStreetMap", group: "Power grid", coverage: "US", color: "rgb(236,178,120)" },
  { id: "connect", label: "Grid capacity", desc: "Where new demand or generation can still connect", group: "Power grid", coverage: "GB, NL, ES, FR, IT, IE, PT, PL", color: "rgb(206,138,72)" },
  { id: "cables", label: "Undersea power cables", desc: "HVDC and AC cables at sea", group: "Power grid", coverage: "World", color: "rgb(110,190,255)" },
  { id: "predicted", label: "Predicted local grid", desc: "Estimated from night lights (Gridfinder)", group: "Power grid", coverage: "World", color: "rgb(255,190,110)" },
  { id: "plantsEU", label: "Power plants", desc: "20 MW and more, by fuel", group: "Power plants", coverage: "Europe", color: "rgb(255,128,72)" },
  { id: "plantsWorld", label: "Power plants worldwide", desc: "Operating, building, planned or retired", group: "Power plants", coverage: "World", color: "rgb(255,214,72)" },
  { id: "plantsUS", label: "US power plants", desc: "Every generator of 1 MW and more (EIA)", group: "Power plants", coverage: "US", color: "rgb(255,128,72)" },
  { id: "mastrDE", label: "Germany: every unit", desc: "MW per municipality of solar, wind or storage; units of 1 MW and more (Marktstammdatenregister)", group: "Power plants", coverage: "DE", color: "rgb(255,214,72)" },
  { id: "tyndp", label: "Planned grid projects", desc: "ENTSO-E TYNDP 2024: lines and storage by status", group: "Power grid", coverage: "Europe", color: "rgb(255,196,96)" },
  { id: "grw", label: "Wind and solar seen from space", desc: "Every turbine and solar array found in satellite images, 2024 Q2 (Global Renewables Watch)", group: "Power plants", coverage: "World", color: "rgb(255,214,72)" },
  { id: "offshoreWind", label: "Offshore wind farms", desc: "Areas at sea: operating, building, approved, planned (EMODnet)", group: "Power plants", coverage: "Europe", color: "rgb(96,190,255)" },
  { id: "turbinesUS", label: "US wind turbines", desc: "Every turbine, shown from zoom 5", group: "Power plants", coverage: "US", color: "rgb(72,222,184)" },
  { id: "solarUS", label: "US solar farms", desc: "Every array of 1 MW and more; outlines zoomed in (USPVDB)", group: "Power plants", coverage: "US", color: "rgb(255,214,72)" },
  { id: "usQueue", label: "US interconnection queue", desc: "Each state raised by the GW waiting to connect", group: "Power plants", coverage: "US", color: "rgb(196,196,214)", story: "us-queue" },
  { id: "gasPipes", label: "Gas pipelines", desc: "Operating, under construction, proposed", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,196,96)" },
  { id: "oilPipes", label: "Oil pipelines", desc: "Crude oil and NGL", group: "Gas, oil & coal", coverage: "World", color: "rgb(222,110,82)" },
  { id: "lngTerminals", label: "LNG terminals", desc: "Import and export, sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,150,92)" },
  { id: "coalTerminals", label: "Coal ports", desc: "Coal export and import terminals", group: "Gas, oil & coal", coverage: "World", color: "rgb(196,182,166)" },
  { id: "oilGasFields", label: "Oil and gas fields", desc: "Where oil and gas are produced", group: "Gas, oil & coal", coverage: "World", color: "rgb(214,96,64)" },
  { id: "coalMines", label: "Coal mines", desc: "Sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(160,146,132)" },
  { id: "methane", label: "Methane plumes", desc: "Leaks seen by satellites", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,90,200)" },
  { id: "plantOutput", label: "Plant output", desc: "What each large plant produces at the clock", group: "Power plants", coverage: "Europe, US", color: "rgb(255,214,140)", modes: ["day"] },
  { id: "gasFlows", label: "Gas flows", desc: "Gas crossing borders and entering Europe, per gas day", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(255,178,62)", modes: ["live"] },
  { id: "lngSendOut", label: "LNG send-out", desc: "Gas each EU terminal sends into the grid, per day", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(120,180,255)" },
  { id: "gasProjects", label: "Planned gas projects", desc: "ENTSOG TYNDP 2026: gas and hydrogen projects per country", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(96,214,255)" },
  { id: "gas", label: "Gas storage", desc: "Underground storage sites", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(255,150,92)" },
  { id: "financeCoal", label: "Who finances coal power", desc: "Money from lenders' countries to coal plants", group: "Money", coverage: "World", color: "rgb(232,204,128)" },
  { id: "financeGas", label: "Who finances gas", desc: "Money to gas plants and LNG terminals", group: "Money", coverage: "World", color: "rgb(255,170,60)" },
  { id: "ets", label: "CO₂ per installation", desc: "Verified emissions under the EU ETS, per year", group: "Industry & data", coverage: "Europe", color: "rgb(236,128,92)" },
  { id: "ctrace", label: "Emissions per facility", desc: "Modelled CO₂e of plants, mills and fields (Climate TRACE)", group: "Industry & data", coverage: "World", color: "rgb(255,196,96)" },
  { id: "steel", label: "Steel plants", desc: "Electric furnaces stand out", group: "Industry & data", coverage: "World", color: "rgb(120,200,255)" },
  { id: "cement", label: "Cement plants", desc: "Sized by capacity", group: "Industry & data", coverage: "World", color: "rgb(206,192,166)" },
  { id: "chemicals", label: "Chemical plants", desc: "Large chemical sites", group: "Industry & data", coverage: "World", color: "rgb(230,160,255)" },
  { id: "ironOre", label: "Iron ore mines", desc: "Sized by production", group: "Industry & data", coverage: "World", color: "rgb(206,112,88)" },
  // { id: "evChargersUS", label: "EV fast chargers", desc: "Public DC fast charging stations, sized by ports (NREL AFDC)", group: "Industry & data", coverage: "US", color: "rgb(96,214,255)" },
  // listed once frontend/public/data/us/ev_chargers.json exists (us-grid.yml needs NREL_API_KEY)
  { id: "ghgrpUS", label: "US industrial emitters", desc: "Reported CO₂e of large facilities (EPA GHGRP)", group: "Industry & data", coverage: "US", color: "rgb(236,128,92)" },
  { id: "hydrogen", label: "Hydrogen projects", desc: "Electrolysers and other clean-hydrogen plants, operating or being built (European Hydrogen Observatory)", group: "Industry & data", coverage: "Europe", color: "rgb(96,214,255)" },
  { id: "dataCentres", label: "Data centres", desc: "Mapped in OpenStreetMap", group: "Industry & data", coverage: "World", color: "rgb(196,150,255)" },
  { id: "water", label: "Water stress", desc: "Water stress, flood and drought risk per river basin (WRI Aqueduct)", group: "Industry & data", coverage: "World", color: "rgb(255,153,0)" },
  { id: "usOutages", label: "US power outages", desc: "Customer-hours without power per county, newest year (EAGLE-I)", group: "Power grid", coverage: "US", color: "rgb(230,120,80)" },
  { id: "protectedAreas", label: "Protected areas", desc: "Natura 2000 sites (EEA) and US protected lands (PAD-US)", group: "Risk", coverage: "Europe, US", color: "rgb(96,186,120)" },
  { id: "flood", label: "River flood hazard", desc: "Water depth in a 100-year flood (JRC)", group: "Risk", coverage: "World", color: "rgb(60,130,210)" },
  { id: "roadsRail", label: "Major roads and railways", desc: "Motorways, trunk and primary roads; standard-gauge rail (OpenStreetMap)", group: "Risk", coverage: "Europe, US", color: "rgb(200,196,186)" },
  { id: "wind", label: "Wind", desc: "Moving wind at turbine height", group: "Weather", coverage: "World", color: "rgb(220,240,255)", modes: ["live", "day"] },
  { id: "sun", label: "Sunshine", desc: "Solar radiation reaching the ground", group: "Weather", coverage: "World", color: "rgb(255,214,72)", modes: ["live", "day"] },
  { id: "solarResource", label: "Solar resource", desc: "PV output per kWp installed, long-term average (Global Solar Atlas)", group: "Weather", coverage: "World", color: "rgb(240,196,112)" },
  { id: "windResource", label: "Wind resource", desc: "Mean wind speed at 100 m (Global Wind Atlas)", group: "Weather", coverage: "World", color: "rgb(128,206,206)" },
  { id: "night", label: "Night", desc: "Where it is dark at that moment", group: "Weather", coverage: "World", color: "rgb(90,110,160)", modes: ["day"] },
];

/** Layers with their own figures in the panel's "On the map" tab (ui/LayerStats.tsx). */
export const STATS_LAYERS = new Set<LayerId>([
  "liveGrids",
  "plantOutput",
  "plantsWorld",
  "plantsUS",
  "turbinesUS",
  "solarUS",
  "grw",
  "tyndp",
  "ghgrpUS",
  "evChargersUS",
  "usQueue",
  "cables",
  "gasPipes",
  "oilPipes",
  "lngTerminals",
  "lngSendOut",
  "coalTerminals",
  "oilGasFields",
  "coalMines",
  "methane",
  "financeCoal",
  "financeGas",
  "ets",
  "ctrace",
  "connect",
  "usNodePrices",
  "steel",
  "cement",
  "chemicals",
  "ironOre",
  "dataCentres",
  "usOutages",
  "water",
  "protectedAreas",
  "hydrogen",
  "gasProjects",
  "mastrDE",
  "offshoreWind",
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
  | "ir_wind"
  | "rt_household";
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
  { id: "rt_household", label: "Household electricity price", group: "What consumers pay", modes: ["live", "years"] },
];
export const isPriceColour = (c: ColourId) => c.startsWith("pr_");
export const isYearColour = (c: ColourId) => c.startsWith("tr_");

export type Selection =
  | { kind: "country"; iso2?: string; iso3?: string }
  | { kind: "zone"; id: string }
  | { kind: "region"; grid: "us" | "br" | "au" | "tw" | "on" | "nz" | "za"; id: string }
  /** "Check a site": one place, what the map's files say about it (ui/SitePanel.tsx) */
  | { kind: "site"; lon: number; lat: number };

export type PlantStatus = "operating" | "construction" | "planned" | "retired";
export type Region = "europe" | "world" | "us";

/** A fixed camera, or a frame the map computes for the screen (map/style.ts). */
/** Which day files the 24 h replay reads: Europe (15 min, CET) or the US (hourly, ET). */
export type DayRegion = "eu" | "us";
export type CameraPreset = Camera | "europe" | "world" | "day" | "us" | "usQueue" | "usDay";
export interface Camera {
  center: [number, number];
  zoom: number;
  pitch?: number;
  bearing?: number;
}
/** The Stories menu's sections. */
export const STORY_GROUPS = ["Europe", "United States", "World"] as const;
export type StoryGroup = (typeof STORY_GROUPS)[number];
export interface Story {
  id: string;
  /** the Stories menu's section */
  group: StoryGroup;
  label: string;
  blurb: string;
  mode: TimeMode;
  colour: ColourId;
  layers: LayerId[];
  plantStatus?: PlantStatus;
  camera: CameraPreset;
  /** the overview panel the story opens on (else from its camera) */
  region?: Region;
  /** the 24 h replay's day files (else Europe's) */
  dayRegion?: DayRegion;
}
export const STORIES: Story[] = [
  {
    id: "europe-live",
    group: "Europe",
    label: "Europe live",
    blurb: "Grid, plants and power flows now",
    mode: "live",
    colour: "renewable",
    layers: ["flows", "gridEU", "hvdc", "substations", "plantsEU"],
    camera: "europe",
  },
  {
    id: "europe-day",
    group: "Europe",
    label: "A day in Europe",
    blurb: "24 hours, every 15 minutes",
    mode: "day",
    colour: "none",
    layers: ["flows", "towers", "prices", "night", "wind", "gridEU"],
    camera: "day",
  },
  {
    id: "plants-day",
    group: "Europe",
    label: "Plants through a day",
    blurb: "What each large plant produced, every 15 minutes",
    mode: "day",
    colour: "none",
    layers: ["plantOutput", "gridEU", "night"],
    camera: "day",
  },
  {
    id: "price-year",
    group: "Europe",
    label: "The price year",
    blurb: "Hours below zero, capture prices",
    mode: "live",
    colour: "pr_negative",
    layers: [],
    camera: "europe",
  },
  {
    id: "transition",
    group: "World",
    label: "25 years of transition",
    blurb: "Every country, 2000–2025",
    mode: "years",
    colour: "tr_renewables",
    layers: [],
    camera: "europe",
  },
  {
    id: "world-building",
    group: "World",
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
    group: "World",
    label: "Grids beyond Europe",
    blurb: "US, Brazil, Australia, Taiwan, Ontario live",
    mode: "live",
    colour: "access",
    layers: ["liveGrids", "gridWorld", "cables", "dataCentres"],
    camera: "world",
  },
  {
    id: "fuel-routes",
    group: "World",
    label: "Fuel routes",
    blurb: "Gas and oil pipelines, LNG and coal ports",
    mode: "live",
    colour: "none",
    layers: ["gasPipes", "oilPipes", "lngTerminals", "coalTerminals"],
    camera: "world",
  },
  {
    id: "methane",
    group: "World",
    label: "Methane from space",
    blurb: "Plumes seen by satellites, fields and mines",
    mode: "live",
    colour: "none",
    layers: ["methane", "oilGasFields", "coalMines"],
    camera: "world",
  },
  {
    id: "money",
    group: "World",
    label: "Who pays for fossil power",
    blurb: "Banks' money flowing to coal and gas",
    mode: "live",
    colour: "none",
    layers: ["financeCoal", "financeGas"],
    camera: { center: [100, 22], zoom: 2.1 },
  },
  {
    id: "us-live",
    group: "United States",
    label: "US live",
    blurb: "Demand, generation and flows between the 13 grid regions now",
    mode: "live",
    colour: "none",
    layers: ["liveGrids", "gridUS"],
    camera: "us",
    region: "us",
  },
  {
    id: "us-day",
    group: "United States",
    label: "A day in the US",
    blurb: "24 hours of demand, generation and flows between the 13 regions",
    mode: "day",
    colour: "none",
    layers: ["towers", "flows", "usNodePrices"],
    camera: "usDay",
    region: "us",
    dayRegion: "us",
  },
  {
    id: "us-plants-day",
    group: "United States",
    label: "US fossil plants through a day",
    blurb: "Every coal, gas and oil unit hour by hour, with its CO₂ (EPA)",
    mode: "day",
    colour: "none",
    layers: ["plantOutput", "gridUS"],
    camera: "usDay",
    region: "us",
    dayRegion: "us",
  },
  {
    id: "us-grid",
    group: "United States",
    label: "US grid",
    blurb: "Every plant, the lines, every wind turbine",
    mode: "live",
    colour: "none",
    layers: ["gridUS", "plantsUS", "turbinesUS"],
    plantStatus: "operating",
    camera: "us",
    region: "us",
  },
  {
    id: "us-queue",
    group: "United States",
    label: "US interconnection queue",
    blurb: "What is waiting to connect, state by state",
    mode: "live",
    colour: "none",
    layers: ["usQueue"],
    camera: "usQueue",
    region: "us",
  },
  {
    id: "us-outages",
    group: "United States",
    label: "US outages",
    blurb: "Customer-hours without power per county; the biggest storms",
    mode: "live",
    colour: "none",
    layers: ["usOutages", "gridUS"],
    camera: "us",
    region: "us",
  },
  {
    id: "heavy-industry",
    group: "World",
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
  /** the Grid capacity layer's Dutch areas: room for new demand or for new generation */
  connectSide: "offtake" | "feedin";
  /** the Water stress layer's indicator (WRI Aqueduct) */
  waterIndicator: WaterIndicator;
  /** the Germany layer's technology (Marktstammdatenregister) */
  mastrTech: MastrTech;
  selection: Selection | null;
  tab: string;
  story: string | null;
  /** where the camera looks: decides the default panel */
  region: Region;
  /** a camera move requested by the UI (story, search); the map consumes it */
  flyTo: CameraPreset | null;
  sheet: "none" | "panel" | "layers" | "search";
  /** the Layers panel is open (desktop) */
  layersPanel: boolean;
  /** the 24 h replay's region */
  dayRegion: DayRegion;
  /** "Check a site" is armed: the next click on the map picks the place */
  picking: boolean;
  /** the country report open over the map (ISO alpha-2 in Europe, else alpha-3) */
  report: string | null;
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
  connectSide: "offtake",
  waterIndicator: "bws",
  mastrTech: "solar",
  selection: null,
  tab: "now",
  story: "europe-live",
  region: "europe",
  flyTo: null,
  sheet: "none",
  layersPanel: true,
  dayRegion: "eu",
  picking: false,
  report: null,
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
    // the status shows on whichever plants layer is on (GEM's worldwide one by default)
    useApp.setState((s) => ({ plantStatus, layers: s.layers.plantsUS || s.layers.plantsWorld ? s.layers : { ...s.layers, plantsWorld: true }, story: null }));
  },
  setPlantStyle(plantStyle: "bars" | "beams") {
    useApp.setState({ plantStyle });
  },
  setConnectSide(connectSide: "offtake" | "feedin") {
    useApp.setState({ connectSide });
  },
  setWaterIndicator(waterIndicator: WaterIndicator) {
    useApp.setState({ waterIndicator });
  },
  setMastrTech(mastrTech: MastrTech) {
    useApp.setState({ mastrTech });
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
    useApp.setState({ selection, tab, sheet: selection ? "panel" : "none", picking: false });
  },
  /** Arm (or disarm) "Check a site": the next click on the map picks the place. */
  setPicking(picking: boolean) {
    useApp.setState({ picking });
  },
  openReport(report: string | null) {
    useApp.setState({ report });
  },
  checkSite(lon: number, lat: number) {
    actions.select({ kind: "site", lon: Number(lon.toFixed(4)), lat: Number(lat.toFixed(4)) }, "site");
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
      region: st.region ?? (st.camera === "world" ? "world" : st.camera === "europe" || st.camera === "day" ? "europe" : useApp.getState().region),
      playing: st.mode !== "live",
      slot: 0,
      yearK: 0,
      flyTo: st.camera,
      sheet: "none",
      dayRegion: st.dayRegion ?? "eu",
      day: null,
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
    if (kind === "region") patch.selection = { kind, grid: a as "us" | "br" | "au" | "tw" | "on" | "nz" | "za", id: b };
    if (kind === "site") {
      const [lon, lat] = (a ?? "").split(",").map(Number);
      if (Number.isFinite(lon) && Number.isFinite(lat) && Math.abs(lat) <= 85 && Math.abs(lon) <= 180) patch.selection = { kind, lon, lat };
    }
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
  const report = p.get("report");
  if (report && /^[A-Za-z]{2,3}$/.test(report)) patch.report = report.toUpperCase();
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
  if ((s.layers.plantsWorld || s.layers.plantsUS) && s.plantStatus !== "operating") p.set("status", s.plantStatus);
  if (s.plantStyle === "beams") p.set("style", "beams");
  if (!s.layersPanel) p.set("panel", "closed");
  if (s.report) p.set("report", s.report);
  const sel = s.selection;
  if (sel?.kind === "country") p.set("sel", `country:${sel.iso2 ?? sel.iso3}`);
  if (sel?.kind === "zone") p.set("sel", `zone:${sel.id}`);
  if (sel?.kind === "region") p.set("sel", `region:${sel.grid}:${sel.id}`);
  if (sel?.kind === "site") p.set("sel", `site:${sel.lon},${sel.lat}`);
  if (sel && s.tab !== "now" && sel.kind !== "site") p.set("tab", s.tab);
  if (camera) {
    const tilt = camera.pitch || camera.bearing ? `,${(camera.pitch ?? 0).toFixed(0)},${(camera.bearing ?? 0).toFixed(0)}` : "";
    p.set("cam", `${camera.center[0].toFixed(2)},${camera.center[1].toFixed(2)},${camera.zoom.toFixed(2)}${tilt}`);
  }
  window.history.replaceState(null, "", `?${p.toString()}`);
}

// development only: lets headless checks read and set the state
if (import.meta.env.DEV) (window as unknown as { __app: typeof useApp }).__app = useApp;
