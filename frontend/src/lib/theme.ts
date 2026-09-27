// Germany InfraAtlas map palette. Lifecycle is sequential; asset type is categorical.
// RGB tuples feed deck.gl directly.

export type RGB = [number, number, number];

export const STATE_ORDER = [
  "unknown",
  "no_activity",
  "clearing",
  "earthworks",
  "construction",
  "complete",
] as const;
export type ConstructionState = (typeof STATE_ORDER)[number]; // lifecycle signal (DB enum)

// Derived display states from the registry, for sites without a satellite signal:
//   operational = registry says in service · planned = registry says in development.
// Remote-sensing stages apply to solar only; compact assets use registry/permit/grid
// milestones, so they read as planned -> operational.
export type DisplayState = ConstructionState | "operational" | "planned";

// legend order: active build states first, terminal states last
export const DISPLAY_ORDER: DisplayState[] = [
  "construction",
  "earthworks",
  "clearing",
  "no_activity",
  "complete",
  "planned",
  "operational",
  "unknown",
];

export const STATE_COLOR: Record<DisplayState, RGB> = {
  unknown: [78, 86, 100], // cool grey — pending
  no_activity: [120, 130, 148], // grey
  clearing: [216, 170, 86], // muted amber
  earthworks: [212, 120, 72], // muted orange
  construction: [86, 158, 210], // steel blue
  complete: [88, 182, 140], // muted green
  planned: [110, 118, 142], // muted slate-indigo — in development (registry)
  operational: [92, 138, 150], // muted teal — in service (registry/grid)
};

export const STATE_LABEL: Record<DisplayState, string> = {
  unknown: "Pending",
  no_activity: "No activity",
  clearing: "Clearing",
  earthworks: "Earthworks",
  construction: "Construction",
  complete: "Complete",
  planned: "Planned",
  operational: "Operational",
};

// no satellite state → derive from the registry (operating vs in development)
export function displayState(status: ConstructionState, mastrStatus: string | null): DisplayState {
  if (status === "unknown") {
    if (mastrStatus === "In Betrieb") return "operational";
    if (mastrStatus === "In Planung") return "planned";
  }
  return status;
}

export const TECH_ORDER = [
  "solar",
  "wind",
  "biomass",
  "hydro",
  "geothermal",
  "combustion",
  "storage",
] as const;
export type Technology = (typeof TECH_ORDER)[number];

export const TECH_COLOR: Record<Technology, RGB> = {
  solar: [224, 176, 72], // gold
  wind: [108, 158, 216], // steel
  biomass: [142, 186, 86], // olive
  hydro: [78, 182, 196], // teal
  geothermal: [206, 124, 168], // mauve
  combustion: [214, 116, 104], // terracotta
  storage: [156, 138, 208], // muted violet
};

export const TECH_LABEL: Record<Technology, string> = {
  solar: "Solar",
  wind: "Wind",
  biomass: "Biomass",
  hydro: "Hydro",
  geothermal: "Geothermal",
  combustion: "Combustion",
  storage: "Storage",
};

export const rgbCss = (c: RGB, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

// dark CARTO basemap — premium, no API key required
export const BASEMAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// free global terrain (Terrarium-encoded DEM, AWS open data) — gives real relief
export const TERRAIN_TILES =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export const GERMANY_VIEW = {
  longitude: 10.2,
  latitude: 51.1,
  zoom: 5.1,
  pitch: 48,
  bearing: -12,
};

// below this zoom the map shows the extruded density field; above it, the
// per-technology 3D objects (which are only legible once you're this close in)
export const SITE_ZOOM = 9.4;

// sequential ramp for the national capacity-density hexbins (dim blue → hot cyan)
export const HEX_RANGE: RGB[] = [
  [22, 42, 71],
  [29, 78, 137],
  [37, 122, 196],
  [56, 170, 233],
  [120, 214, 245],
  [196, 240, 252],
];
