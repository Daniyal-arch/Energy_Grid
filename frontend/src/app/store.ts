// What the user has chosen: time mode, layers, colour, selection, dashboard and area. One store, synced
// with the URL so every view can be shared as a link. The map reads it without re-rendering
// React (getState in the render loop); panels subscribe to the parts they show.

import { create } from "zustand";

import type { WaterIndicator } from "../lib/risk";
import type { MastrTech } from "../lib/mastr";
import type { AreaSpec, LonLat } from "../lib/area";
import { EUROPE_ISO3 } from "../lib/transition";

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
  | "evChargersEU"
  | "usQueue"
  | "gasPipes"
  | "gasPipesUS"
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
  | "regGB"
  | "regDK"
  | "regSE"
  | "regIE"
  | "regPT"
  | "offshoreWind"
  | "wind"
  | "sun"
  | "night";

export type LayerGroup =
  | "Electricity"
  | "Prices"
  | "Power grid"
  | "Connections & queues"
  | "Power plants"
  | "Gas, oil & coal"
  | "Emissions"
  | "Industry & demand"
  | "Risk"
  | "Resources"
  | "Weather"
  | "Money";
export const LAYER_GROUPS: LayerGroup[] = [
  "Electricity",
  "Prices",
  "Power grid",
  "Connections & queues",
  "Power plants",
  "Gas, oil & coal",
  "Emissions",
  "Industry & demand",
  "Risk",
  "Resources",
  "Weather",
  "Money",
];

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
  { id: "flows", label: "Cross-border flows", desc: "Power moving between countries now", group: "Electricity", coverage: "Europe", color: "rgb(120,222,255)", modes: ["live", "day"] },
  { id: "prices", label: "Prices", desc: "Each country rises by its day-ahead price; generation towers stand on top", group: "Electricity", coverage: "Europe", color: "rgb(255,196,90)", modes: ["live", "day"] },
  { id: "liveGrids", label: "Live grids", desc: "US, Brazil, Australia, Taiwan, Ontario, New Zealand, South Africa now", group: "Electricity", coverage: "World", color: "rgb(255,196,120)", modes: ["live"] },
  { id: "usNodePrices", label: "Node prices", desc: "Day-ahead price at each placed node, hour by hour", group: "Electricity", coverage: "US West", color: "rgb(255,196,90)", modes: ["day"] },
  { id: "towers", label: "Generation towers", desc: "Each country's (or US region's) output by source", group: "Electricity", coverage: "Europe, US", color: "rgb(255,214,72)", modes: ["day"] },
  { id: "gridEU", label: "Transmission lines", desc: "220–750 kV, by voltage", group: "Power grid", coverage: "Europe", color: "rgb(236,178,120)" },
  { id: "hvdc", label: "HVDC links", desc: "Direct-current links between grids", group: "Power grid", coverage: "Europe", color: "rgb(178,146,255)" },
  { id: "substations", label: "Substations", desc: "220 kV and more, shown zoomed in", group: "Power grid", coverage: "Europe", color: "rgb(226,232,240)" },
  { id: "gridWorld", label: "High-voltage lines", desc: "220 kV and more, mapped in OpenStreetMap", group: "Power grid", coverage: "World", color: "rgb(160,210,255)" },
  { id: "gridUS", label: "US transmission lines", desc: "100–765 kV by voltage, mapped in OpenStreetMap", group: "Power grid", coverage: "US", color: "rgb(236,178,120)" },
  { id: "connect", label: "Grid capacity", desc: "Where new demand or generation can still connect", group: "Connections & queues", coverage: "GB, NL, ES, FR, IT, IE, PT, PL, AT, BG, CZ, DE, DK, EE, LT, LU, MT, SE", color: "rgb(206,138,72)" },
  { id: "cables", label: "Undersea power cables", desc: "HVDC and AC cables at sea", group: "Power grid", coverage: "World", color: "rgb(110,190,255)" },
  { id: "predicted", label: "Predicted local grid", desc: "Estimated from night lights (Gridfinder)", group: "Power grid", coverage: "World", color: "rgb(255,190,110)" },
  { id: "plantsEU", label: "Power plants", desc: "20 MW and more, by fuel", group: "Power plants", coverage: "Europe", color: "rgb(255,128,72)" },
  { id: "plantsWorld", label: "Power plants worldwide", desc: "Operating, building, planned or retired", group: "Power plants", coverage: "World", color: "rgb(255,214,72)" },
  { id: "plantsUS", label: "US power plants", desc: "Every generator of 1 MW and more (EIA)", group: "Power plants", coverage: "US", color: "rgb(255,128,72)" },
  { id: "mastrDE", label: "Germany: every unit", desc: "MW per municipality of solar, wind or storage; units of 1 MW and more (Marktstammdatenregister)", group: "Power plants", coverage: "DE", color: "rgb(255,214,72)" },
  { id: "tyndp", label: "Planned grid projects", desc: "ENTSO-E TYNDP 2024: lines and storage by status", group: "Power grid", coverage: "Europe", color: "rgb(255,196,96)" },
  { id: "grw", label: "Wind and solar seen from space", desc: "Every turbine and solar array found in satellite images, 2024 Q2 (Global Renewables Watch)", group: "Power plants", coverage: "World", color: "rgb(255,214,72)" },
  { id: "regGB", label: "UK: every project", desc: "Renewables and storage from 150 kW in planning or operating (REPD), gas, coal and nuclear stations (DUKES)", group: "Power plants", coverage: "GB", color: "rgb(255,214,72)" },
  { id: "regDK", label: "Denmark: every wind turbine", desc: "On land and at sea, with capacity and model (Energistyrelsen)", group: "Power plants", coverage: "DK", color: "rgb(72,222,184)" },
  { id: "regSE", label: "Sweden: every wind turbine", desc: "Built, permitted or in planning (Vindbrukskollen)", group: "Power plants", coverage: "SE", color: "rgb(72,222,184)" },
  { id: "regIE", label: "Ireland: wind farms", desc: "Connected by June 2022, at their grid node (SEAI)", group: "Power plants", coverage: "IE", color: "rgb(72,222,184)" },
  { id: "regPT", label: "Portugal: licensed plants", desc: "Wind, solar, thermal and small hydro in DGEG's licensing", group: "Power plants", coverage: "PT", color: "rgb(255,214,72)" },
  { id: "offshoreWind", label: "Offshore wind farms", desc: "Areas at sea: operating, building, approved, planned (EMODnet)", group: "Power plants", coverage: "Europe", color: "rgb(96,190,255)" },
  { id: "turbinesUS", label: "US wind turbines", desc: "Every turbine, shown from zoom 5", group: "Power plants", coverage: "US", color: "rgb(72,222,184)" },
  { id: "solarUS", label: "US solar farms", desc: "Every array of 1 MW and more; outlines zoomed in (USPVDB)", group: "Power plants", coverage: "US", color: "rgb(255,214,72)" },
  { id: "usQueue", label: "US interconnection queue", desc: "Each state raised by the GW waiting to connect", group: "Connections & queues", coverage: "US", color: "rgb(196,196,214)" },
  { id: "gasPipesUS", label: "US gas pipelines", desc: "Interstate and intrastate natural gas pipelines (EIA)", group: "Gas, oil & coal", coverage: "US", color: "rgb(255,196,96)" },
  { id: "gasPipes", label: "Gas pipelines", desc: "Operating, under construction, proposed", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,196,96)" },
  { id: "oilPipes", label: "Oil pipelines", desc: "Crude oil and NGL", group: "Gas, oil & coal", coverage: "World", color: "rgb(222,110,82)" },
  { id: "lngTerminals", label: "LNG terminals", desc: "Import and export, sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(255,150,92)" },
  { id: "coalTerminals", label: "Coal ports", desc: "Coal export and import terminals", group: "Gas, oil & coal", coverage: "World", color: "rgb(196,182,166)" },
  { id: "oilGasFields", label: "Oil and gas fields", desc: "Where oil and gas are produced", group: "Gas, oil & coal", coverage: "World", color: "rgb(214,96,64)" },
  { id: "coalMines", label: "Coal mines", desc: "Sized by capacity", group: "Gas, oil & coal", coverage: "World", color: "rgb(160,146,132)" },
  { id: "methane", label: "Methane plumes", desc: "Leaks seen by satellites", group: "Emissions", coverage: "World", color: "rgb(255,90,200)" },
  { id: "plantOutput", label: "Plant output", desc: "What each large plant produces at the clock", group: "Power plants", coverage: "Europe, US", color: "rgb(255,214,140)", modes: ["day"] },
  { id: "gasFlows", label: "Gas flows", desc: "Gas crossing borders and entering Europe, per gas day", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(255,178,62)", modes: ["live"] },
  { id: "lngSendOut", label: "LNG send-out", desc: "Gas each EU terminal sends into the grid, per day", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(120,180,255)" },
  { id: "gasProjects", label: "Planned gas projects", desc: "ENTSOG TYNDP 2026: gas and hydrogen projects per country", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(96,214,255)" },
  { id: "gas", label: "Gas storage", desc: "Underground storage sites", group: "Gas, oil & coal", coverage: "Europe", color: "rgb(255,150,92)" },
  { id: "financeCoal", label: "Who finances coal power", desc: "Money from lenders' countries to coal plants", group: "Money", coverage: "World", color: "rgb(232,204,128)" },
  { id: "financeGas", label: "Who finances gas", desc: "Money to gas plants and LNG terminals", group: "Money", coverage: "World", color: "rgb(255,170,60)" },
  { id: "ets", label: "CO₂ per installation", desc: "Verified emissions under the EU ETS, per year", group: "Emissions", coverage: "Europe", color: "rgb(236,128,92)" },
  { id: "ctrace", label: "Emissions per facility", desc: "Modelled CO₂e of plants, mills and fields (Climate TRACE)", group: "Emissions", coverage: "World", color: "rgb(255,196,96)" },
  { id: "ghgrpUS", label: "US industrial emitters", desc: "Reported CO₂e of large facilities (EPA GHGRP)", group: "Emissions", coverage: "US", color: "rgb(236,128,92)" },
  { id: "steel", label: "Steel plants", desc: "Electric furnaces stand out", group: "Industry & demand", coverage: "World", color: "rgb(120,200,255)" },
  { id: "cement", label: "Cement plants", desc: "Sized by capacity", group: "Industry & demand", coverage: "World", color: "rgb(206,192,166)" },
  { id: "chemicals", label: "Chemical plants", desc: "Large chemical sites", group: "Industry & demand", coverage: "World", color: "rgb(230,160,255)" },
  { id: "ironOre", label: "Iron ore mines", desc: "Sized by production", group: "Industry & demand", coverage: "World", color: "rgb(206,112,88)" },
  { id: "evChargersEU", label: "EV charging", desc: "Public charging points from the national registers, OpenStreetMap stations elsewhere (EAFO counts)", group: "Industry & demand", coverage: "Europe", color: "rgb(96,214,255)" },
  { id: "evChargersUS", label: "EV fast chargers", desc: "Public DC fast charging stations, sized by ports (NREL AFDC)", group: "Industry & demand", coverage: "US", color: "rgb(96,214,255)" },
  { id: "hydrogen", label: "Hydrogen projects", desc: "Electrolysers and other clean-hydrogen plants, operating or being built (European Hydrogen Observatory)", group: "Industry & demand", coverage: "Europe", color: "rgb(96,214,255)" },
  { id: "dataCentres", label: "Data centres", desc: "Mapped in OpenStreetMap", group: "Industry & demand", coverage: "World", color: "rgb(196,150,255)" },
  { id: "water", label: "Water stress", desc: "Water stress, flood and drought risk per river basin (WRI Aqueduct)", group: "Risk", coverage: "World", color: "rgb(255,153,0)" },
  { id: "usOutages", label: "US power outages", desc: "Customer-hours without power per county, newest year (EAGLE-I)", group: "Risk", coverage: "US", color: "rgb(230,120,80)" },
  { id: "protectedAreas", label: "Protected areas", desc: "Natura 2000 sites (EEA), PAD-US (USGS)", group: "Risk", coverage: "Europe, US", color: "rgb(96,186,120)" },
  { id: "flood", label: "River flood hazard", desc: "Water depth in a 100-year flood (JRC)", group: "Risk", coverage: "World", color: "rgb(60,130,210)" },
  { id: "roadsRail", label: "Major roads and railways", desc: "Motorways, trunk and primary roads; standard-gauge rail (OpenStreetMap)", group: "Risk", coverage: "Europe, US", color: "rgb(200,196,186)" },
  { id: "wind", label: "Wind", desc: "Moving wind at turbine height", group: "Weather", coverage: "World", color: "rgb(220,240,255)", modes: ["live", "day"] },
  { id: "sun", label: "Sunshine", desc: "Solar radiation reaching the ground", group: "Weather", coverage: "World", color: "rgb(255,214,72)", modes: ["live", "day"] },
  { id: "solarResource", label: "Solar resource", desc: "PV output per kWp installed, long-term average (Global Solar Atlas)", group: "Resources", coverage: "World", color: "rgb(240,196,112)" },
  { id: "windResource", label: "Wind resource", desc: "Mean wind speed at 100 m (Global Wind Atlas)", group: "Resources", coverage: "World", color: "rgb(128,206,206)" },
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
  "evChargersEU",
  "gasPipesUS",
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
  "regGB",
  "regDK",
  "regSE",
  "regIE",
  "regPT",
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
  | { kind: "site"; lon: number; lat: number; r?: number };

export type PlantStatus = "operating" | "construction" | "planned" | "retired";
export type Region = "europe" | "world" | "us";

/** A fixed camera, a frame the map computes for the screen (map/style.ts), or countries to frame. */
/** Which day files the 24 h replay reads: Europe (15 min, CET) or the US (hourly, ET). */
export type DayRegion = "eu" | "us";
export type CameraPreset = Camera | "europe" | "world" | "day" | "us" | "usQueue" | "usDay" | { area: string[] } | { bounds: [number, number, number, number] };
export interface Camera {
  center: [number, number];
  zoom: number;
  pitch?: number;
  bearing?: number;
}
/** The Dashboards menu's sections ("Mine": saved in this browser). */
export const DASHBOARD_GROUPS = ["Europe", "United States", "Countries", "World", "Mine"] as const;
export type DashboardGroup = (typeof DASHBOARD_GROUPS)[number];
/** A saved view: datasets (as their map layers), an area, the time mode and the countries' colour. */
export interface Dashboard {
  id: string;
  /** the Dashboards menu's section */
  group: DashboardGroup;
  label: string;
  blurb: string;
  mode: TimeMode;
  colour: ColourId;
  layers: LayerId[];
  /** the countries it is about (ISO alpha-3); none = wherever the camera looks */
  area?: string[];
  /** or a polygon drawn on the map, or a circle around a place */
  drawn?: AreaSpec;
  plantStatus?: PlantStatus;
  camera: CameraPreset;
  /** the overview panel it opens on (else from its camera) */
  region?: Region;
  /** the 24 h replay's day files (else Europe's) */
  dayRegion?: DayRegion;
}
const EUROPE = [...EUROPE_ISO3];
export const DASHBOARDS: Dashboard[] = [
  { id: "europe-live", group: "Europe", label: "Europe now", blurb: "Power flows, renewable share and the grid, every 30 minutes", mode: "live", colour: "renewable", layers: ["flows", "gridEU", "hvdc", "substations", "plantsEU"], area: EUROPE, camera: "europe" },
  { id: "europe-day", group: "Europe", label: "Europe's last 24 hours", blurb: "Generation, prices and flows every 15 minutes", mode: "day", colour: "none", layers: ["flows", "towers", "prices", "night", "wind", "gridEU"], camera: "day" },
  { id: "plants-day", group: "Europe", label: "Power plants hour by hour", blurb: "What each large plant produced through a day", mode: "day", colour: "none", layers: ["plantOutput", "gridEU", "night"], camera: "day" },
  { id: "price-year", group: "Europe", label: "Europe's price year", blurb: "Hours below zero and capture prices, 12 months", mode: "live", colour: "pr_negative", layers: [], area: EUROPE, camera: "europe" },
  { id: "europe-connect", group: "Europe", label: "Free grid capacity (Europe)", blurb: "Where new demand or generation can still connect, as each grid operator publishes it, on the high-voltage grid", mode: "live", colour: "none", layers: ["connect", "gridEU", "substations"], area: EUROPE, camera: "europe" },
  { id: "europe-emitters", group: "Europe", label: "Europe's biggest emitters", blurb: "Verified CO₂ per installation, steel and cement plants", mode: "live", colour: "none", layers: ["ets", "steel", "cement"], area: EUROPE, camera: "europe" },
  { id: "us-live", group: "United States", label: "US grid now", blurb: "Demand, generation and flows between the 13 grid regions", mode: "live", colour: "none", layers: ["liveGrids", "gridUS"], area: ["USA"], camera: "us", region: "us" },
  { id: "us-day", group: "United States", label: "US last 24 hours", blurb: "Demand, generation and flows hour by hour", mode: "day", colour: "none", layers: ["towers", "flows", "usNodePrices"], camera: "usDay", region: "us", dayRegion: "us" },
  { id: "us-plants-day", group: "United States", label: "US fossil plants hour by hour", blurb: "Every coal, gas and oil unit with its CO₂ (EPA)", mode: "day", colour: "none", layers: ["plantOutput", "gridUS"], camera: "usDay", region: "us", dayRegion: "us" },
  { id: "us-grid", group: "United States", label: "US power infrastructure", blurb: "Every plant, the lines, wind turbines and solar farms", mode: "live", colour: "none", layers: ["gridUS", "plantsUS", "turbinesUS", "solarUS"], plantStatus: "operating", area: ["USA"], camera: "us", region: "us" },
  { id: "us-queue", group: "United States", label: "US interconnection queue", blurb: "What waits to connect to the grid, state by state", mode: "live", colour: "none", layers: ["usQueue"], area: ["USA"], camera: "usQueue", region: "us" },
  { id: "us-outages", group: "United States", label: "US power outages", blurb: "Customer-hours without power per county", mode: "live", colour: "none", layers: ["usOutages", "gridUS"], area: ["USA"], camera: "us", region: "us" },
  { id: "site-screening", group: "World", label: "Site screening", blurb: "Lines, substations, free capacity, protected areas and flood hazard: draw an area or search a city", mode: "live", colour: "none", layers: ["gridEU", "gridUS", "substations", "connect", "protectedAreas", "flood"], camera: "europe" },
  { id: "germany", group: "Countries", label: "Germany in detail", blurb: "Every unit by municipality (MaStR) and the high-voltage grid", mode: "live", colour: "none", layers: ["mastrDE", "gridEU", "substations"], area: ["DEU"], camera: { area: ["DEU"] } },
  { id: "great-britain", group: "Countries", label: "Great Britain in detail", blurb: "Every project (REPD) and the high-voltage grid", mode: "live", colour: "none", layers: ["regGB", "gridEU", "substations"], area: ["GBR"], camera: { area: ["GBR"] } },
  { id: "nordic-wind", group: "Countries", label: "Nordic wind", blurb: "Every turbine in Denmark and Sweden, offshore farms, the grid", mode: "live", colour: "none", layers: ["regDK", "regSE", "offshoreWind", "gridEU"], area: ["DNK", "SWE"], camera: { area: ["DNK", "SWE"] } },
  { id: "transition", group: "World", label: "25 years of energy transition", blurb: "Every country's mix, 2000–2025", mode: "years", colour: "tr_renewables", layers: [], camera: "europe" },
  { id: "world-building", group: "World", label: "What the world is building", blurb: "Plants under construction", mode: "live", colour: "none", layers: ["plantsWorld", "gridWorld"], plantStatus: "construction", camera: "world" },
  { id: "world-live", group: "World", label: "Grids beyond Europe", blurb: "US, Brazil, Australia, Taiwan, Ontario live", mode: "live", colour: "access", layers: ["liveGrids", "gridWorld", "cables", "dataCentres"], camera: "world" },
  { id: "fuel-routes", group: "World", label: "Fuel routes", blurb: "Gas and oil pipelines, LNG and coal ports", mode: "live", colour: "none", layers: ["gasPipes", "oilPipes", "lngTerminals", "coalTerminals"], camera: "world" },
  { id: "methane", group: "World", label: "Methane from space", blurb: "Plumes seen by satellites, fields and mines", mode: "live", colour: "none", layers: ["methane", "oilGasFields", "coalMines"], camera: "world" },
  { id: "money", group: "World", label: "Who finances fossil power", blurb: "Banks' money flowing to coal and gas", mode: "live", colour: "none", layers: ["financeCoal", "financeGas"], camera: { center: [100, 22], zoom: 2.1 } },
  { id: "heavy-industry", group: "World", label: "Heavy industry", blurb: "Steel, cement and chemical plants", mode: "live", colour: "none", layers: ["steel", "cement", "chemicals", "ironOre"], camera: "world" },
];
export const DEFAULT_DASHBOARD = "europe-live";

/** Dashboards the user saved, kept in this browser only (localStorage; private windows may refuse). */
const MINE_KEY = "infraatlas.dashboards";
function loadMine(): Dashboard[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(MINE_KEY) ?? "[]");
    return Array.isArray(v) ? (v as Dashboard[]).filter((d) => d && typeof d.id === "string" && Array.isArray(d.layers)) : [];
  } catch {
    return [];
  }
}
function storeMine(list: Dashboard[]): void {
  try {
    window.localStorage.setItem(MINE_KEY, JSON.stringify(list));
  } catch {
    // storage refused: the dashboard lives until the page closes
  }
}
/** The box around a drawn polygon or circle [west, south, east, north]. */
export function specBounds(d: AreaSpec): [number, number, number, number] {
  if (d.kind === "circle") {
    const dLat = d.r / 111.2;
    const dLon = dLat / Math.max(0.05, Math.cos((d.at[1] * Math.PI) / 180));
    return [d.at[0] - dLon, d.at[1] - dLat, d.at[0] + dLon, d.at[1] + dLat];
  }
  const xs = d.ring.map((q) => q[0]);
  const ys = d.ring.map((q) => q[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
/** A country's dashboard (`country:DEU`), made from the datasets that cover it (app/datasets.ts). */
export const countryDashboards: { make: ((iso3: string) => Dashboard | undefined) | null } = { make: null };
export const findDashboard = (id: string | null) =>
  id ? (DASHBOARDS.find((d) => d.id === id) ?? useApp.getState().mine.find((d) => d.id === id) ?? (id.startsWith("country:") ? countryDashboards.make?.(id.slice(8)) : undefined)) : undefined;

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
  /** the dashboard shown (a preset or one of "mine") and whether layers changed since */
  dashboard: string | null;
  edited: boolean;
  /** the dashboard's countries (ISO alpha-3): its figures are for them; null = no area */
  area: string[] | null;
  /** the dashboard's area as a drawn polygon or a circle around a place (then `area` is null) */
  drawn: AreaSpec | null;
  /** corners clicked so far while drawing an area on the map */
  drawing: LonLat[] | null;
  /** a name for a view opened from a link (a dashboard saved elsewhere) */
  title: string | null;
  /** dashboards saved in this browser */
  mine: Dashboard[];
  /** the dataset whose coverage the map tints (Layers panel details) */
  coverageOf: string | null;
  /** the dashboard builder: a new one, or this view (to save or edit one of mine) */
  builder: { kind: "new" | "save"; id?: string } | null;
  /** the data catalogue is open over the map */
  catalogue: boolean;
  /** where the camera looks: decides the default panel */
  region: Region;
  /** a camera move requested by the UI (dashboard, search); the map consumes it */
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
export const layersOf = (ids: LayerId[]) => ({ ...allOff, ...Object.fromEntries(ids.map((id) => [id, true])) });

export const useApp = create<AppState>(() => ({
  mode: "live",
  day: null,
  slot: 0,
  yearK: 0,
  playing: false,
  layers: layersOf(DASHBOARDS[0].layers),
  colour: "renewable",
  plantStatus: "operating",
  plantStyle: "bars",
  connectSide: "offtake",
  waterIndicator: "bws",
  mastrTech: "solar",
  selection: null,
  tab: "dashboard",
  dashboard: DEFAULT_DASHBOARD,
  edited: false,
  area: null,
  drawn: null,
  drawing: null,
  title: null,
  mine: loadMine(),
  coverageOf: null,
  builder: null,
  catalogue: false,
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
      // the dashboard's figures follow the layers
      return { layers: { ...s.layers, [id]: on }, edited: true, tab: on && !s.selection ? "dashboard" : s.tab };
    });
  },
  setColour(colour: ColourId) {
    const s = useApp.getState();
    useApp.setState({ colour, edited: true, tab: colour.startsWith("pr_") && !s.selection ? "prices" : s.tab });
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
      edited: true,
      layers: mode === "day" ? { ...s.layers, towers: true, night: true } : s.layers,
      tab: mode === "years" ? "years" : s.tab === "years" ? "now" : s.tab,
      flyTo: mode === "day" ? "day" : s.mode === "day" ? "europe" : null,
    });
  },
  setPlantStatus(plantStatus: PlantStatus) {
    // the status shows on whichever plants layer is on (GEM's worldwide one by default)
    useApp.setState((s) => ({ plantStatus, layers: s.layers.plantsUS || s.layers.plantsWorld ? s.layers : { ...s.layers, plantsWorld: true }, edited: true }));
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
  /** Check a place as a site; the area keeps the radius chosen last. */
  checkSite(lon: number, lat: number) {
    const s = useApp.getState().selection;
    const r = s?.kind === "site" ? s.r : undefined;
    actions.select({ kind: "site", lon: Number(lon.toFixed(4)), lat: Number(lat.toFixed(4)), ...(r ? { r } : {}) }, "site");
  },
  setSiteRadius(r: number) {
    const s = useApp.getState().selection;
    if (s?.kind === "site") useApp.setState({ selection: { ...s, r } });
  },
  applyDashboard(id: string) {
    const st = findDashboard(id);
    if (!st) return;
    motion.daySlot = 0;
    motion.yearPos = 0;
    const area = st.area?.length ? st.area : null;
    useApp.setState({
      dashboard: st.id,
      edited: false,
      title: null,
      area,
      drawn: st.drawn ?? null,
      drawing: null,
      mode: st.mode,
      colour: st.colour,
      layers: layersOf(st.layers),
      plantStatus: st.plantStatus ?? useApp.getState().plantStatus,
      selection: null,
      tab: st.mode === "years" ? "years" : st.colour.startsWith("pr_") ? "prices" : "dashboard",
      region: st.region ?? (st.camera === "world" ? "world" : st.camera === "europe" || st.camera === "day" ? "europe" : area?.includes("USA") ? "us" : useApp.getState().region),
      playing: st.mode !== "live",
      slot: 0,
      yearK: 0,
      flyTo: st.camera,
      sheet: "none",
      dayRegion: st.dayRegion ?? "eu",
      day: null,
      coverageOf: null,
    });
  },
  /** Keep the view as a dashboard of mine: a new one, or replacing one of mine (same id). */
  saveDashboard(label: string, blurb: string, id?: string): string {
    const s = useApp.getState();
    const d: Dashboard = {
      id: id && id.startsWith("my-") ? id : `my-${Date.now().toString(36)}`,
      group: "Mine",
      label: label.trim() || "My dashboard",
      blurb,
      mode: s.mode,
      colour: s.colour,
      layers: (Object.keys(s.layers) as LayerId[]).filter((k) => s.layers[k]),
      ...(s.area ? { area: s.area } : {}),
      ...(s.drawn ? { drawn: s.drawn } : {}),
      plantStatus: s.plantStatus,
      camera: s.area ? { area: s.area } : s.drawn ? { bounds: specBounds(s.drawn) } : s.region === "us" ? "us" : s.region === "world" ? "world" : "europe",
      region: s.region,
      dayRegion: s.dayRegion,
    };
    const mine = [...s.mine.filter((x) => x.id !== d.id), d];
    storeMine(mine);
    useApp.setState({ mine, dashboard: d.id, edited: false, title: null });
    return d.id;
  },
  deleteDashboard(id: string) {
    const s = useApp.getState();
    const mine = s.mine.filter((x) => x.id !== id);
    storeMine(mine);
    useApp.setState({ mine, ...(s.dashboard === id ? { dashboard: null, edited: true } : {}) });
  },
  /** The dashboard's countries (null: none); the map frames them. */
  setArea(area: string[] | null) {
    const a = area?.length ? [...new Set(area)] : null;
    useApp.setState({ area: a, drawn: null, edited: true, selection: null, tab: "dashboard", ...(a ? { flyTo: { area: a } } : {}) });
  },
  /** A polygon or a circle as the area (null: none); the map frames it. */
  setDrawn(drawn: AreaSpec | null) {
    useApp.setState({ drawn, area: null, drawing: null, picking: false, edited: true, selection: null, tab: "dashboard", sheet: "panel", ...(drawn ? { flyTo: { bounds: specBounds(drawn) } } : {}) });
  },
  /** Drawing an area: each click adds a corner; three or more make the polygon. */
  startDrawing() {
    useApp.setState({ drawing: [], picking: false });
  },
  addCorner(p: LonLat) {
    const d = useApp.getState().drawing;
    if (!d) return;
    const last = d[d.length - 1];
    // the two clicks of a double click land on the same spot: one corner
    if (last && Math.abs(last[0] - p[0]) < 1e-6 && Math.abs(last[1] - p[1]) < 1e-6) return;
    useApp.setState({ drawing: [...d, [Number(p[0].toFixed(4)), Number(p[1].toFixed(4))]] });
  },
  undoCorner() {
    const d = useApp.getState().drawing;
    if (d?.length) useApp.setState({ drawing: d.slice(0, -1) });
  },
  finishDrawing() {
    const d = useApp.getState().drawing;
    if (!d) return;
    if (d.length < 3) return useApp.setState({ drawing: null });
    actions.setDrawn({ kind: "polygon", ring: d });
  },
  cancelDrawing() {
    useApp.setState({ drawing: null });
  },
  openBuilder(builder: AppState["builder"]) {
    useApp.setState({ builder });
  },
  /** Tint where a dataset has data (null: stop). */
  showCoverage(id: string | null) {
    useApp.setState({ coverageOf: id });
  },
};

/** ?year=2015: resolved once the transition file (and its list of years) has arrived. */
export let yearFromUrl: string | null = null;
export const clearYearFromUrl = () => (yearFromUrl = null);

/** Old links (?day=, ?view=prices, ?story=, ?country=FR, ...) and new ones (?dash=, ?layers=, ?area=, ...). */
export function readUrl(): void {
  const p = new URLSearchParams(window.location.search);
  const view = p.get("view");
  const dash =
    p.get("dash") ?? p.get("story") ?? (p.get("day") ? "europe-day" : view === "prices" ? "price-year" : view === "transition" ? "transition" : view === "world" ? "world-live" : null);
  if (dash) actions.applyDashboard(dash);
  const patch: Partial<AppState> = {};
  const mode = p.get("mode");
  if (!dash && (mode === "day" || mode === "years")) actions.setMode(mode);
  if (!dash && p.get("layers") !== null) {
    // a view built by hand (or a dashboard saved in another browser)
    patch.dashboard = null;
    patch.edited = true;
    patch.title = p.get("dname");
  }
  // ?poly=lon,lat;lon,lat;... (a drawn area), ?circle=lon,lat,km[,name]
  const poly = p.get("poly");
  const circle = p.get("circle");
  if (poly) {
    const ring = poly.split(";").map((xy) => xy.split(",").map(Number) as LonLat).filter((q) => q.length === 2 && q.every(Number.isFinite));
    if (ring.length >= 3) patch.drawn = { kind: "polygon", ring, ...(p.get("aname") ? { name: p.get("aname")! } : {}) };
  } else if (circle) {
    const [lon, lat, r, ...name] = circle.split(",");
    if ([lon, lat, r].map(Number).every(Number.isFinite) && Number(r) > 0 && Number(r) <= 500)
      patch.drawn = { kind: "circle", at: [Number(lon), Number(lat)], r: Number(r), ...(name.length ? { name: name.join(",") } : {}) };
  }
  if (patch.drawn && !p.get("cam")) patch.flyTo = { bounds: specBounds(patch.drawn) };
  const area = p.get("area");
  if (area !== null) {
    const codes = area.split(",").filter((c) => /^[A-Z]{3}$/.test(c));
    patch.area = codes.length ? codes : null;
    if (codes.length && !p.get("cam")) patch.flyTo = { area: codes };
  }
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
      const [lon, lat, r] = (a ?? "").split(",").map(Number);
      if (Number.isFinite(lon) && Number.isFinite(lat) && Math.abs(lat) <= 85 && Math.abs(lon) <= 180)
        patch.selection = { kind, lon, lat, ...(Number.isFinite(r) && r > 0 && r <= 200 ? { r } : {}) };
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
  // a preset as itself; anything else (edited, or one of mine) with its layers, so the link opens anywhere
  const preset = s.dashboard && !s.edited && DASHBOARDS.some((d) => d.id === s.dashboard);
  if (preset) p.set("dash", s.dashboard!);
  else {
    if (s.mode !== "live") p.set("mode", s.mode);
    p.set("colour", s.colour);
    p.set("layers", (Object.keys(s.layers) as LayerId[]).filter((k) => s.layers[k]).join(","));
    if (s.area) p.set("area", s.area.join(","));
    if (s.drawn?.kind === "polygon") {
      p.set("poly", s.drawn.ring.map((q) => `${q[0]},${q[1]}`).join(";"));
      if (s.drawn.name) p.set("aname", s.drawn.name);
    }
    if (s.drawn?.kind === "circle") p.set("circle", [s.drawn.at[0], s.drawn.at[1], s.drawn.r, ...(s.drawn.name ? [s.drawn.name] : [])].join(","));
    const name = s.title ?? findDashboard(s.dashboard)?.label;
    if (name) p.set("dname", name);
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
  if (sel?.kind === "site") p.set("sel", `site:${sel.lon},${sel.lat}${sel.r ? `,${sel.r}` : ""}`);
  if (sel && s.tab !== "now" && s.tab !== "dashboard" && sel.kind !== "site") p.set("tab", s.tab);
  if (camera) {
    const tilt = camera.pitch || camera.bearing ? `,${(camera.pitch ?? 0).toFixed(0)},${(camera.bearing ?? 0).toFixed(0)}` : "";
    p.set("cam", `${camera.center[0].toFixed(2)},${camera.center[1].toFixed(2)},${camera.zoom.toFixed(2)}${tilt}`);
  }
  window.history.replaceState(null, "", `?${p.toString()}`);
}

// development only: lets headless checks read and set the state
if (import.meta.env.DEV) (window as unknown as { __app: typeof useApp }).__app = useApp;
