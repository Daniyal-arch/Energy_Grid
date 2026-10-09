// MapLibre's part of the map: the globe, the world's land and the world grid tiles, plus the
// camera presets. deck.gl draws everything else on top (map/build.ts).

import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

import { HV_STEPS, HV_TILES, PREDICTED_TILES } from "../lib/worldPlants";
import { isNarrow } from "../app/geo";

export const OCEAN = "#0a111c";
export const LAND = "#161a22";

// the world grid: vector tiles in one PMTiles file on R2 (.github/workflows/world-hv.yml and
// world-grid.yml), read with HTTP range requests; only the tiles in view travel
maplibregl.addProtocol("pmtiles", new Protocol().tile);

const kv = ["coalesce", ["get", "kv"], 0];
const hvColor = ["step", kv, HV_STEPS[0][1], ...HV_STEPS.slice(1).flat()];

export const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  projection: { type: "globe" },
  sky: {
    "sky-color": "#08101d",
    "horizon-color": "#163052",
    "fog-color": "#05070b",
    "sky-horizon-blend": 0.6,
    "horizon-fog-blend": 0.6,
    "fog-ground-blend": 0.5,
    "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 0.7, 4, 0.45, 7, 0],
  },
  // label glyphs bundled with the site (public/fonts/README.md)
  glyphs: `${window.location.origin}/fonts/{fontstack}/{range}.pbf`,
  sources: {
    world: { type: "geojson", data: "/data/eu/world.json" },
    labels: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": OCEAN } },
    { id: "world-land", type: "fill", source: "world", paint: { "fill-color": LAND } },
    { id: "world-coast", type: "line", source: "world", paint: { "line-color": "rgba(150,162,182,0.22)", "line-width": 0.6 } },
    // Europe's countries (deck.gl) are drawn just below this point, the world grid above it
    { id: "deck-anchor", type: "background", layout: { visibility: "none" }, paint: { "background-color": OCEAN } },
    // the selected country's outline (outside Europe; Europe draws its own)
    {
      id: "world-pick",
      type: "line",
      source: "world",
      filter: ["==", ["get", "iso3"], ""],
      paint: { "line-color": "rgba(255,246,230,0.95)", "line-width": 1.8 },
    },
    // labels over everything (deck.gl's layers go just below "label-names"); MapLibre
    // places them on the globe and drops the ones that would collide
    {
      id: "label-names",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "country"],
      layout: {
        "text-field": [
          "case",
          ["!=", ["get", "sub"], ""],
          ["format", ["get", "text"], { "font-scale": 0.85 }, "\n", {}, ["get", "sub"], { "font-scale": 1.1, "text-color": "#ffffff" }],
          ["get", "text"],
        ] as unknown as string,
        "text-font": ["noto-medium"],
        "text-size": 11.5,
        "text-letter-spacing": 0.06,
        "text-line-height": 1.3,
        "text-padding": 1,
      },
      paint: { "text-color": "rgba(236,232,224,0.72)", "text-halo-color": "rgba(6,8,12,0.85)", "text-halo-width": 1.2 },
    },
    {
      id: "label-zones",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "zone"],
      layout: { "text-field": ["get", "text"], "text-font": ["noto-medium"], "text-size": 11, "text-offset": [0, 1.2] },
      paint: { "text-color": "#ffffff", "text-halo-color": "rgba(6,8,12,0.9)", "text-halo-width": 1.6 },
    },
    {
      id: "label-regions",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "region"],
      layout: { "text-field": ["get", "text"], "text-font": ["noto-medium"], "text-size": 11, "text-offset": [0, -1.4], "symbol-sort-key": ["get", "rank"] },
      paint: { "text-color": "rgb(255,236,210)", "text-halo-color": "rgba(6,9,14,0.95)", "text-halo-width": 2.4 },
    },
    {
      id: "label-dc",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "dc"],
      layout: { "text-field": ["get", "text"], "text-font": ["noto-medium"], "text-size": 10, "text-offset": [0, -1.3], "symbol-sort-key": ["get", "rank"] },
      paint: { "text-color": "rgb(236,220,255)", "text-halo-color": "rgba(6,8,12,0.9)", "text-halo-width": 1.6 },
    },
    {
      id: "label-money",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "money"],
      layout: { "text-field": ["get", "text"], "text-font": ["noto-medium"], "text-size": 11.5, "text-offset": [0, -1.6], "symbol-sort-key": ["get", "rank"] },
      paint: { "text-color": "rgb(255,222,150)", "text-halo-color": "rgba(6,8,12,0.95)", "text-halo-width": 2.4 },
    },
    {
      id: "label-flows",
      type: "symbol",
      source: "labels",
      filter: ["==", ["get", "kind"], "flow"],
      layout: { "text-field": ["get", "text"], "text-font": ["noto-medium"], "text-size": 11, "text-offset": [0, -1], "symbol-sort-key": ["get", "rank"] },
      paint: { "text-color": "rgb(214,244,255)", "text-halo-color": "rgba(6,9,14,0.95)", "text-halo-width": 2.6 },
    },
  ],
};

/** The world grid tiles, added the first time they are switched on (a source still loading
 *  would hold back the map's load event; a missing file only logs an error). */
export function addGridLayers(map: maplibregl.Map, which: "hv" | "predicted"): void {
  if (which === "predicted" && !map.getSource("world-predicted")) {
    map.addSource("world-predicted", { type: "vector", url: PREDICTED_TILES, attribution: "Gridfinder (Arderne et al. 2020)" });
    map.addLayer(
      {
        id: "grid-predicted",
        type: "line",
        source: "world-predicted",
        "source-layer": "grid",
        filter: ["==", ["get", "source"], "gridfinder"],
        paint: { "line-color": "rgba(255,190,110,0.35)", "line-width": 0.6 },
      },
      "world-pick",
    );
  }
  if (which === "hv" && !map.getSource("world-hv")) {
    map.addSource("world-hv", { type: "vector", url: HV_TILES, attribution: "© OpenStreetMap contributors" });
    // a soft glow under the backbone, then the lines; heavier for higher voltage
    map.addLayer(
      {
        id: "hv-glow",
        type: "line",
        source: "world-hv",
        "source-layer": "hv",
        filter: [">=", kv, 380] as unknown as maplibregl.FilterSpecification,
        paint: {
          "line-color": hvColor as unknown as string,
          "line-width": ["interpolate", ["linear"], ["zoom"], 1, 2, 5, 4, 9, 7],
          "line-blur": 3,
          "line-opacity": 0.28,
        },
      },
      "world-pick",
    );
    map.addLayer(
      {
        id: "hv-lines",
        type: "line",
        source: "world-hv",
        "source-layer": "hv",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": hvColor as unknown as string,
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            1,
            ["step", kv, 0.35, 380, 0.6, 500, 0.9],
            5,
            ["step", kv, 0.7, 380, 1.1, 500, 1.6],
            9,
            ["step", kv, 1.2, 380, 1.8, 500, 2.6],
          ] as unknown as number,
        },
      },
      "world-pick",
    );
  }
}
export const GRID_LAYERS = ["hv-glow", "hv-lines"];
export const PREDICTED_LAYERS = ["grid-predicted"];

/** Globe for the overview; flat (mercator) for tilted 3D views (towers, plant columns),
 *  which deck.gl's globe mode cannot draw. */
export function setProjection(map: maplibregl.Map, flat: boolean): boolean {
  try {
    if (map.getProjection()?.type !== (flat ? "mercator" : "globe")) map.setProjection({ type: flat ? "mercator" : "globe" });
  } catch {
    return false; // style not ready yet
  }
  // deck.gl's globe draws neither tilt nor rotation: lock both on the globe
  if (flat) {
    map.setMaxPitch(70);
    map.dragRotate.enable();
    map.touchZoomRotate.enableRotation();
    map.keyboard.enableRotation();
  } else {
    map.setMaxPitch(0);
    map.setBearing(0);
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
  }
  map.fire("deckviewsync");
  return true;
}

/** Room the panels take on each side, so the map frames what is left between them. */
export const panelPadding = () =>
  isNarrow() ? { left: 8, right: 8, top: 56, bottom: 150 } : { left: 300, right: 400, top: 64, bottom: 70 };
const EUROPE_BOUNDS: [[number, number], [number, number]] = [
  [-10, 35.5],
  [31, 70],
];
/** Europe framed between the panels (the globe's centre shifts to make room for them). */
export function europeView(map: maplibregl.Map): { center: [number, number]; zoom: number } {
  const cam = map.cameraForBounds(EUROPE_BOUNDS, { padding: panelPadding() });
  if (!cam?.center || cam.zoom == null) return europeCamera();
  const c = maplibregl.LngLat.convert(cam.center);
  return { center: [c.lng, c.lat], zoom: cam.zoom };
}
export const europeCamera = () => ({ center: (isNarrow() ? [12, 46] : [12, 49]) as [number, number], zoom: isNarrow() ? 1.7 : 2.55 });
export const worldCamera = () => ({ center: (isNarrow() ? [30, 8] : [34, 14]) as [number, number], zoom: isNarrow() ? 1.05 : 2.05 });

/** The 24 h view: continental Europe, tilted so the towers fill the screen. */
export const dayFrame = (map: maplibregl.Map, duration = 0) =>
  map.fitBounds(
    [
      isNarrow() ? [-10, 41] : [-9, 36],
      isNarrow() ? [27, 60] : [27, 63],
    ],
    {
      padding: isNarrow() ? { left: 4, right: 4, top: 90, bottom: 160 } : { left: 320, right: 380, top: 70, bottom: 110 },
      pitch: isNarrow() ? 52 : 55,
      duration,
    },
  );
