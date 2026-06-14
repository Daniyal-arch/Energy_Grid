// gridwatch visual identity. Construction state is our signature dimension — a
// sequential ramp from dormant (dim) to complete (bright green). Technology is a
// categorical palette for the density overview. RGB tuples feed deck.gl directly.

export type RGB = [number, number, number];

export const STATE_ORDER = [
  "unknown",
  "no_activity",
  "clearing",
  "earthworks",
  "construction",
  "complete",
] as const;
export type ConstructionState = (typeof STATE_ORDER)[number];

export const STATE_COLOR: Record<ConstructionState, RGB> = {
  unknown: [74, 85, 104], // dim slate — not yet analysed
  no_activity: [113, 128, 150], // grey
  clearing: [244, 183, 64], // amber
  earthworks: [239, 125, 58], // orange
  construction: [56, 189, 248], // cyan
  complete: [52, 211, 153], // green
};

export const STATE_LABEL: Record<ConstructionState, string> = {
  unknown: "Not yet analysed",
  no_activity: "No activity",
  clearing: "Clearing",
  earthworks: "Earthworks",
  construction: "Construction",
  complete: "Complete",
};

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
  solar: [251, 191, 36],
  wind: [96, 165, 250],
  biomass: [132, 204, 22],
  hydro: [34, 211, 238],
  geothermal: [244, 114, 182],
  combustion: [248, 113, 113],
  storage: [167, 139, 250],
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

// below this zoom the map shows an extruded density field; above it, individual sites
export const SITE_ZOOM = 7.6;

// sequential ramp for the national capacity-density hexbins (dim blue → hot cyan)
export const HEX_RANGE: RGB[] = [
  [22, 42, 71],
  [29, 78, 137],
  [37, 122, 196],
  [56, 170, 233],
  [120, 214, 245],
  [196, 240, 252],
];
