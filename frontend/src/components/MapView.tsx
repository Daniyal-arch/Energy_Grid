import type { Layer, PickingInfo } from "@deck.gl/core";
import { MVTLayer, TripsLayer } from "@deck.gl/geo-layers";
import { ArcLayer, ColumnLayer, GeoJsonLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { SimpleMeshLayer } from "@deck.gl/mesh-layers";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Footprint, GridExchangeRow, GridSnapshotLatest, Site, Turbine } from "../lib/api";
import { OBJECT_MESH, REAL_COLOR, REAL_HZ, STACK_H } from "../lib/energyObjects";
import { glint, plume, pulse as pulseFx, type Particle } from "../lib/effects";
import { capturePadding, type CaptureConfig } from "../lib/capture";
import {
  FLOW_BLEND,
  FlowClock,
  FlowPathLayer,
  PREMULTIPLIED_BLEND,
  PlantGlowLayer,
  SCREEN_BLEND,
  StationDotLayer,
} from "../lib/flowLayers";
import {
  PHASE_COLOR,
  loadGrid,
  loadGridFlowPaths,
  loadPlanned,
  voltColor,
  voltageAllowed,
  type GridFlowPath,
  type GridData,
  type PlannedSeg,
  type VoltageTiers,
} from "../lib/grid";
import { EXCHANGE_COUNTRY_CODE } from "../lib/gridLive";
import { mw } from "../lib/format";
import {
  EXCHANGE_COLOR,
  IDLE_FLOW_MW,
  PLANT_COLOR,
  POWER_LAND,
  POWER_VIEW_BOUNDS,
  exchangeFlowLines,
  outlineFromStates,
  PLANT_LOD,
  plantActivity,
  plantClusters,
  plantFeeders,
  plantRadius,
  powerLabelMarkers,
  powerLineColor,
  setPowerBasemap,
  type ExchangeFlowLine,
  type PlantCluster,
  type PlantFeeder,
  type PlantGroup,
} from "../lib/powerScene";
import {
  INDUSTRY_COLOR,
  INFRA_COLOR,
  loadInfrastructure,
  type InfraItem,
  type InfraNode,
  type InfraPath,
  type InfrastructureData,
  type MapFeaturePick,
} from "../lib/infrastructure";
import { BRIDGE_PIER_MESH, STATION_MESH, TRAIN_MESH, TRAIN_WINDOW_MESH, TUNNEL_PORTAL_MESH } from "../lib/railMeshes";
import { ROTOR_MESH, TOWER_MESH } from "../lib/turbineMesh";
import {
  BASEMAP_STYLE,
  GERMANY_VIEW,
  SITE_ZOOM,
  STATE_COLOR,
  STATE_LABEL,
  TECH_COLOR,
  TERRAIN_TILES,
  displayState,
  type RGB,
  type Technology,
} from "../lib/theme";

const CLOSE_ZOOM = 11; // above this, animate (spin rotors) — bounded instance count

export type ColorMode = "state" | "technology";

interface Props {
  sites: Site[];
  colorMode: ColorMode;
  selectedId: string | null;
  onSelect: (id: string) => void;
  flyTo: { lon: number; lat: number } | null;
  footprint: Footprint | null;
  turbines: Turbine[];
  basemap: "dark" | "satellite";
  gridBackbone: boolean;
  gridPlanned: boolean;
  gridExchangeFlows: boolean;
  gridConstructionOnly: boolean;
  gridVoltages: VoltageTiers;
  infraStateBoundaries: boolean;
  infraRail: boolean;
  infraRailStations: boolean;
  infraRailStructures: boolean;
  infraGas: boolean;
  infraPorts: boolean;
  infraAirports: boolean;
  infraGasNodes: boolean;
  infraGasFacilities: boolean;
  infraIndustry: boolean;
  railSceneRequest: number;
  powerSceneRequest: number;
  sceneMode: "atlas" | "rail" | "power";
  gridLatest?: GridSnapshotLatest;
  exchange?: GridExchangeRow[];
  onGridSelect: (p: MapFeaturePick) => void;
  /** video capture stage (?capture=): fixed framing, no interaction */
  capture?: CaptureConfig | null;
}

const TURBINE_COLOR: [number, number, number] = [226, 232, 240]; // light grey, like real towers

const DIM: RGB = [60, 70, 90];
const EMPTY_FC = { type: "FeatureCollection", features: [] };

type Position3D = [number, number, number];

interface RailVehicle {
  id: string;
  position: Position3D;
  headPosition: [number, number, number];
  tailPosition: [number, number, number];
  bearing: number;
  color: [number, number, number, number];
  scale: [number, number, number];
}

interface RailStructurePoint {
  id: string;
  position: [number, number];
  height: number;
  item: InfraPath;
}

function colorOf(s: Site, mode: ColorMode): [number, number, number, number] {
  const ds = displayState(s.status, s.mastr_status);
  const c =
    mode === "state" ? STATE_COLOR[ds] ?? DIM : (s.technology && TECH_COLOR[s.technology]) || DIM;
  const alpha = mode === "state" && ds === "unknown" ? 150 : 230;
  return [c[0], c[1], c[2], alpha];
}

function pathAtHeight(path: [number, number][], height: number): Position3D[] {
  return path.map(([lon, lat]) => [lon, lat, height]);
}

function railStructureHeight(d: InfraPath): number {
  const length = Number(d.properties.length_m || 0);
  const scale = Math.sqrt(Math.max(length, 80));
  return d.kind === "rail_bridge" ? Math.min(7_200, 1_100 + scale * 105) : 120;
}

function railNodeScore(node: InfraNode): number {
  const type = String(node.properties.type || "").toLowerCase();
  const name = node.name.toLowerCase();
  if (name.includes("hbf") || type.includes("hauptbahnhof")) return 1;
  if (type.includes("bahnhof")) return 0.78;
  if (type.includes("abzweig") || type.includes("überleit") || type.includes("Ã¼berleit")) return 0.66;
  if (type.includes("ausweich") || type.includes("anschluss")) return 0.56;
  if (type.includes("haltepunkt")) return 0.38;
  return 0.48;
}

function pathDistanceMeters(path: InfraPath): number {
  if (path.timestamps.length < 2) return 0;
  return Math.max(0, path.timestamps[path.timestamps.length - 1] - path.timestamps[0]);
}

function hashString(value: string): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function majorRailNameBoost(name: string): number {
  const text = name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const hubs = ["berlin", "hamburg", "hannover", "frankfurt", "koln", "koeln", "munchen", "muenchen", "munich", "stuttgart", "nurnberg", "nuernberg"];
  return hubs.some((hub) => text.includes(hub)) ? 95_000 : 0;
}

function railRouteScore(path: InfraPath): number {
  const tracks = String(path.properties.tracks || "").toLowerCase();
  const electrification = String(path.properties.electrification || "").toLowerCase();
  const route = String(path.properties.route || path.name);
  const score =
    pathDistanceMeters(path) +
    (tracks.includes("zweigleisig") ? 135_000 : 0) +
    (electrification.includes("oberleitung") ? 85_000 : 0) +
    majorRailNameBoost(path.name);
  return score + (hashString(`${route}-${path.name}`) % 10_000) / 10_000;
}

function pathIntersectsBounds(
  path: [number, number][],
  [w, s, e, n]: [number, number, number, number],
  margin = 0.08,
): boolean {
  const dx = (e - w) * margin;
  const dy = (n - s) * margin;
  for (const [lon, lat] of path) {
    if (lon >= w - dx && lon <= e + dx && lat >= s - dy && lat <= n + dy) return true;
  }
  return false;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function offsetLonLat([lon, lat]: [number, number], bearing: number, meters: number): [number, number] {
  const rad = (bearing * Math.PI) / 180;
  const north = Math.cos(rad) * meters;
  const east = Math.sin(rad) * meters;
  const nextLat = lat + north / 111_320;
  const nextLon = lon + east / (111_320 * Math.cos((lat * Math.PI) / 180));
  return [nextLon, nextLat];
}

function easeOutCubic(t: number): number {
  const x = Math.max(0, Math.min(1, t));
  return 1 - (1 - x) ** 3;
}

function metersPerPixel(viewZoom: number, latitude = GERMANY_VIEW.latitude): number {
  return (156543.03 * Math.cos((latitude * Math.PI) / 180)) / 2 ** viewZoom;
}

function bearingBetween(a: [number, number], b: [number, number]): number {
  const y = Math.sin((b[0] - a[0]) * (Math.PI / 180)) * Math.cos(b[1] * (Math.PI / 180));
  const x =
    Math.cos(a[1] * (Math.PI / 180)) * Math.sin(b[1] * (Math.PI / 180)) -
    Math.sin(a[1] * (Math.PI / 180)) *
      Math.cos(b[1] * (Math.PI / 180)) *
      Math.cos((b[0] - a[0]) * (Math.PI / 180));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function pointAtTimedPath(
  path: [number, number][],
  timestamps: number[],
  time: number,
  reverse = false,
): { position: [number, number]; bearing: number } | null {
  if (path.length < 2 || timestamps.length < 2) return null;
  const start = timestamps[0];
  const end = timestamps[timestamps.length - 1];
  const span = end - start;
  if (span <= 0) return { position: path[0], bearing: 0 };
  const progress = ((((time - start) % span) + span) % span);
  const target = reverse ? end - progress : start + progress;
  for (let i = 1; i < timestamps.length; i++) {
    if (timestamps[i] < target) continue;
    const t0 = timestamps[i - 1];
    const t1 = timestamps[i];
    const a = path[i - 1];
    const b = path[i];
    const r = t1 === t0 ? 0 : (target - t0) / (t1 - t0);
    const bearing = bearingBetween(a, b);
    return {
      position: [a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r],
      bearing: reverse ? (bearing + 180) % 360 : bearing,
    };
  }
  return { position: path[path.length - 1], bearing: reverse ? 180 : 0 };
}

function railPointAt(path: InfraPath, time: number): { position: [number, number]; bearing: number } | null {
  return pointAtTimedPath(path.path, path.timestamps, time);
}

function railVehicleColor(index: number): [number, number, number, number] {
  if (index % 11 === 0) return [255, 120, 105, 245];
  if (index % 5 === 0) return [255, 232, 150, 245];
  return [220, 248, 255, 245];
}

function structurePoints(items: InfraPath[], kind: "portal" | "pier"): RailStructurePoint[] {
  const rows: RailStructurePoint[] = [];
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const height = railStructureHeight(item);
    if (kind === "portal") {
      const first = item.path[0];
      const last = item.path[item.path.length - 1];
      if (first) rows.push({ id: `${i}-a`, position: first, height: 900, item });
      if (last) rows.push({ id: `${i}-b`, position: last, height: 900, item });
      continue;
    }
    const middle = item.path[Math.floor(item.path.length / 2)];
    if (middle) {
      rows.push({
        id: `${i}-m`,
        position: middle,
        height,
        item,
      });
    }
  }
  return rows;
}

function trainGlyphLengthMeters(viewZoom: number, index: number): number {
  const classBoost = index % 11 === 0 ? 1.28 : index % 5 === 0 ? 1.12 : 1;
  const px = viewZoom < 7 ? 7 : viewZoom < 8.6 ? 10 : 13;
  return metersPerPixel(viewZoom) * px * classBoost;
}

function trainMeshScale(index: number): [number, number, number] {
  const classBoost = index % 11 === 0 ? 1.25 : index % 5 === 0 ? 1.12 : 1;
  return [42 * classBoost, 72 * classBoost, 28 * classBoost];
}

function gridLiveSignal(latest: GridSnapshotLatest | undefined, exchange: GridExchangeRow[] | undefined) {
  const entries = Object.entries(latest ?? {});
  const totalGeneration = entries
    .filter(([metric]) => metric.startsWith("gen_"))
    .reduce((sum, [, row]) => sum + Math.max(0, Number(row.value) || 0), 0);
  const renewableGeneration = ["gen_solar", "gen_wind", "gen_wind_onshore", "gen_wind_offshore", "gen_hydro", "gen_biomass", "gen_geothermal"]
    .map((metric) => Number(latest?.[metric]?.value) || 0)
    .reduce((sum, value) => sum + Math.max(0, value), 0);
  const netImport = (exchange ?? []).reduce((sum, row) => sum + (Number(row.value_mw) || 0), 0);
  const renewableShare = totalGeneration > 0 ? renewableGeneration / totalGeneration : 0.45;
  const carbon = Number(latest?.carbon_intensity?.value) || 260;
  const price = Number(latest?.price_eur_mwh?.value) || 80;
  const generationScale = totalGeneration > 0 ? clamp(totalGeneration / 65_000, 0.6, 1.5) : 1;
  const exchangeScale = clamp(Math.abs(netImport) / 13_000, 0, 0.75);
  return {
    generationScale,
    exchangeScale,
    renewableShare,
    netImport,
    carbon,
    price,
    speed: 0.14 * (0.8 + exchangeScale + generationScale * 0.22),
    intensity: clamp(0.68 + generationScale * 0.34 + exchangeScale * 0.28, 0.7, 1.65),
  };
}

// [line core px, dot radius px, dot opacity] for FlowPathLayer. In the power
// scene the flow layer IS the line; in the atlas the MVT lines stay underneath
// and only the dots ride on them.
function gridFlowStyle(line: GridFlowPath, powerScene: boolean, zoom: number): [number, number, number] {
  const z = clamp(1 + (zoom - 6) * 0.14, 0.9, 1.6);
  const v380 = line.voltage >= 380_000;
  // corridors running across the bulk-transfer direction get calmer dots
  const t = clamp((line.alignment - 0.15) / 0.45, 0, 1);
  const calm = 0.35 + 0.65 * t * t * (3 - 2 * t);
  if (!powerScene) return [0, (v380 ? 1.6 : 1.3) * z, (v380 ? 0.95 : 0.75) * calm];
  return v380 ? [1.3 * z, 1.8 * z, calm] : [0.95 * z, 1.45 * z, 0.8 * calm];
}

type PlantActivity = Record<PlantGroup, number> | null;

// Live generation share of the plant's group -> 0..1 animation level (a share
// of ~45% already reads as "running flat out"). Without live data: mid level.
const plantLevel = (group: PlantGroup, activity: PlantActivity) =>
  activity ? clamp(activity[group] * 2.2, 0, 1) : 0.45;

// PlantGlowLayer glow: [brightness, twinkle rad/s, twinkle depth, ring]. Each
// group moves differently (secondary encoding next to colour): wind twinkles
// faster the windier it is, solar parks go dim at night, thermal plants breathe.
function plantGlowStyle(c: PlantCluster, activity: PlantActivity): [number, number, number, number] {
  const level = plantLevel(c.group, activity);
  const ring = c.technology === "storage" ? 1 : 0;
  if (c.group === "wind") return [0.6 + 0.4 * level, 1.2 + 4.5 * level, 0.3, ring];
  if (c.group === "solar") {
    const night = activity !== null && activity.solar < 0.005;
    return [night ? 0.3 : 0.55 + 0.45 * level, 0.9, night ? 0.05 : 0.2, ring];
  }
  if (c.group === "fossil") return [0.6 + 0.4 * level, 0.7, 0.14, ring];
  return [0.6 + 0.3 * level, 0.5, 0.12, ring];
}

// feeder dots only while the group is actually generating (no solar dots at night)
function feederDotOpacity(group: PlantGroup, activity: PlantActivity): number {
  if (!activity) return 0.6;
  return activity[group] < 0.005 ? 0 : clamp(0.35 + activity[group] * 1.8, 0.35, 1);
}

export default function MapView({
  sites,
  colorMode,
  selectedId,
  onSelect,
  flyTo,
  footprint,
  turbines,
  basemap,
  gridBackbone,
  gridPlanned,
  gridExchangeFlows,
  gridConstructionOnly,
  gridVoltages,
  infraStateBoundaries,
  infraRail,
  infraRailStations,
  infraRailStructures,
  infraGas,
  infraPorts,
  infraAirports,
  infraGasNodes,
  infraGasFacilities,
  infraIndustry,
  railSceneRequest,
  powerSceneRequest,
  sceneMode,
  gridLatest,
  exchange,
  onGridSelect,
  capture = null,
}: Props) {
  const showGrid = gridBackbone || gridPlanned;
  const showInfrastructure =
    infraStateBoundaries ||
    infraRail ||
    infraRailStations ||
    infraRailStructures ||
    infraGas ||
    infraPorts ||
    infraAirports ||
    infraGasNodes ||
    infraGasFacilities ||
    infraIndustry;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [grid, setGrid] = useState<GridData | null>(null);
  const [gridFlows, setGridFlows] = useState<GridFlowPath[] | null>(null);
  const flowClock = useRef(new FlowClock());
  const [planned, setPlanned] = useState<{ segs: PlannedSeg[]; maxTime: number } | null>(null);
  const [infrastructure, setInfrastructure] = useState<InfrastructureData | null>(null);
  const groundZ = useRef<Map<string, number>>(new Map());
  const [phase, setPhase] = useState(0);
  const [groundTick, setGroundTick] = useState(0);
  const [closeUp, setCloseUp] = useState(GERMANY_VIEW.zoom >= CLOSE_ZOOM);
  // objects are sized to the screen (like the old bars), so they stay visible at
  // every altitude. quantise zoom to 0.25 so they resize in steps, not per-tick.
  const [viewZoom, setViewZoom] = useState(Math.round(GERMANY_VIEW.zoom * 4) / 4);
  // current viewport [w, s, e, n] — objects are culled to it so we never draw all
  // 5,402 at once (that's the spike-forest at national zoom)
  const [bounds, setBounds] = useState<[number, number, number, number]>([-4, 44, 22, 58]);
  // only used to gate terrain-seating (expensive) to closer zooms
  const [aggregated, setAggregated] = useState(GERMANY_VIEW.zoom < SITE_ZOOM);
  const railSceneActive = sceneMode === "rail" && infraRail;
  const powerSceneActive = sceneMode === "power" && gridBackbone;
  const railSceneStartedAt = useRef(performance.now());

  // init once
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP_STYLE,
      center: [GERMANY_VIEW.longitude, GERMANY_VIEW.latitude],
      zoom: GERMANY_VIEW.zoom,
      pitch: GERMANY_VIEW.pitch,
      bearing: GERMANY_VIEW.bearing,
      maxPitch: 80,
      attributionControl: false,
      interactive: !capture,
      // MSAA for the deck.gl overlay (interleaved into this GL context) — without
      // it every line and dot edge is stair-stepped
      antialias: true,
    });
    map.on("load", () => {
      // real terrain relief — subtle nationally, dramatic when you drop into a site
      map.addSource("terrain", {
        type: "raster-dem",
        tiles: [TERRAIN_TILES],
        encoding: "terrarium",
        tileSize: 256,
        maxzoom: 13,
      });
      map.setTerrain({ source: "terrain", exaggeration: 1.25 });
      map.addLayer({
        id: "hillshade",
        type: "hillshade",
        source: "terrain",
        paint: {
          "hillshade-shadow-color": "#05070b",
          "hillshade-highlight-color": "#1b2433",
          "hillshade-exaggeration": 0.55,
        },
      });
      map.setSky({
        "sky-color": "#0a1018",
        "horizon-color": "#10161f",
        "fog-color": "#06080d",
        "sky-horizon-blend": 0.6,
        "horizon-fog-blend": 0.6,
        "fog-ground-blend": 0.4,
      });
      // satellite imagery basemap (Esri World Imagery, free) — drapes on the same
      // terrain. inserted under the first label layer so place names stay on top.
      const firstSymbol = map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
      map.addSource("satellite", {
        type: "raster",
        tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        maxzoom: 19,
        attribution: "Esri",
      });
      map.addLayer(
        {
          id: "satellite",
          type: "raster",
          source: "satellite",
          layout: { visibility: "none" },
          paint: { "raster-opacity": 1 },
        },
        firstSymbol,
      );
      // real site footprint — extruded and draped on terrain (fill-extrusion
      // follows the DEM, so a hillside array sits on the slope, not at sea level)
      map.addSource("footprint", { type: "geojson", data: EMPTY_FC as never });
      map.addLayer({
        id: "footprint-fill",
        type: "fill-extrusion",
        source: "footprint",
        paint: {
          "fill-extrusion-color": ["get", "color"],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.22,
        },
      });
      map.addLayer({
        id: "footprint-edge",
        type: "line",
        source: "footprint",
        paint: { "line-color": ["get", "color"], "line-width": 2.2, "line-opacity": 0.95, "line-blur": 0.4 },
      });
    });
    map.on("zoom", () => {
      const z = map.getZoom();
      const agg = z < SITE_ZOOM;
      setAggregated((prev) => (prev === agg ? prev : agg));
      const close = z >= CLOSE_ZOOM;
      setCloseUp((prev) => (prev === close ? prev : close));
      const vz = Math.round(z * 4) / 4;
      setViewZoom((prev) => (prev === vz ? prev : vz));
    });
    const onMove = () => {
      const b = map.getBounds();
      setBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    };
    map.on("moveend", onMove);
    map.once("load", onMove);
    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
      getTooltip: (info: PickingInfo) => {
        const infra = info.object as InfraItem | undefined;
        if (infra?.featureType) return `${infra.name}\n${infra.kind.replaceAll("_", " ")}`;
        const o = info.object as Site | undefined;
        if (!o?.name) return null;
        return {
          html: `<b>${o.name}</b><br/>${mw(o.capacity_mw)} · ${o.technology ?? "—"}<br/>${
            STATE_LABEL[displayState(o.status, o.mastr_status)]
          }`,
          style: {
            background: "rgba(12,16,24,0.95)",
            color: "#e8edf4",
            fontSize: "12px",
            padding: "8px 10px",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.1)",
          },
        };
      },
    });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;
    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  // gentle pulse animation for recently-changed sites
  useEffect(() => {
    let raf: number;
    const t0 = performance.now();
    const loop = (t: number) => {
      setPhase(((t - t0) % 2200) / 2200);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  // every site is its own 3D object by technology. group by tech and drop the
  // open site (it gets detailed geometry). LOD: cull to the viewport and, when
  // zoomed far out, show only the largest plants so the wide view stays clean.
  const byTech = useMemo(() => {
    const [w, s0, e, n] = bounds;
    const mLon = (e - w) * 0.06;
    const mLat = (n - s0) * 0.06;
    const minCap =
      viewZoom >= 10.5 ? 0 : viewZoom >= 9 ? 7 : viewZoom >= 7.75 ? 14 : viewZoom >= 6.5 ? 30 : 65;
    const m = new Map<Technology, Site[]>();
    for (const s of sites) {
      if (!s.technology) continue;
      // the open site is drawn separately as a real-scale object fitted to its
      // footprint (or real turbines for wind), so drop it from the field here
      if (s.id === selectedId) continue;
      if (s.capacity_mw < minCap) continue;
      if (s.lon < w - mLon || s.lon > e + mLon || s.lat < s0 - mLat || s.lat > n + mLat) continue;
      const arr = m.get(s.technology);
      if (arr) arr.push(s);
      else m.set(s.technology, [s]);
    }
    return m;
  }, [sites, selectedId, bounds, viewZoom]);

  // lazy-load the transmission grid GeoJSON once it's first switched on. Lines
  // render via MVT tiles; this fetch is substations-only (848 KB, not the 16 MB
  // combined file — that would re-download the whole line network just for points).
  useEffect(() => {
    if (showGrid && !grid) loadGrid("/grid_substations.geojson").then(setGrid).catch(() => {});
    if (gridBackbone && !gridFlows) loadGridFlowPaths().then(setGridFlows).catch(() => {});
    if (showGrid && !planned) loadPlanned("/grid_planned.geojson").then(setPlanned).catch(() => {});
  }, [showGrid, gridBackbone, grid, gridFlows, planned]);

  useEffect(() => {
    if (showInfrastructure && !infrastructure) loadInfrastructure().then(setInfrastructure).catch(() => {});
  }, [showInfrastructure, infrastructure]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || railSceneRequest <= 0) return;
    railSceneStartedAt.current = performance.now();
    map.flyTo({
      center: [8.68, 50.11],
      zoom: 8.9,
      pitch: 67,
      bearing: -32,
      duration: 1600,
      essential: true,
    });
  }, [railSceneRequest]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || powerSceneRequest <= 0) return;
    // whole country + neighbour labels, flat, clear of the HUD (left) and legend (right)
    const wide = map.getContainer().clientWidth > 1100;
    const cam = map.cameraForBounds(POWER_VIEW_BOUNDS, {
      padding: capture
        ? capturePadding(capture)
        : { top: 24, bottom: 40, left: wide ? 350 : 24, right: wide ? 300 : 24 },
    });
    if (capture) {
      // the video frames the country instantly; no fly-in to wait for
      map.jumpTo({ center: cam?.center ?? [10.35, 51.05], zoom: cam?.zoom ?? 5, pitch: 0, bearing: 0 });
      return;
    }
    map.flyTo({
      center: cam?.center ?? [10.35, 51.05],
      zoom: cam?.zoom ?? 5.6,
      pitch: 0,
      bearing: 0,
      duration: 1450,
      essential: true,
    });
  }, [powerSceneRequest]);

  // nearest substation to the open site → a 3D arc connecting plant to the grid
  const plantArc = useMemo(() => {
    if (!grid || !selectedId) return null;
    const s = sites.find((x) => x.id === selectedId);
    if (!s) return null;
    let best: GridData["subs"][number] | null = null;
    let bestD = Infinity;
    for (const sub of grid.subs) {
      const d = (sub.position[0] - s.lon) ** 2 + (sub.position[1] - s.lat) ** 2;
      if (d < bestD) {
        bestD = d;
        best = sub;
      }
    }
    return best ? { from: [s.lon, s.lat] as [number, number], to: best.position } : null;
  }, [grid, selectedId, sites]);

  // substations for the power view: only where drawn corridors end (the others
  // sit on dropped stubs and read as stray specks), with how many corridor ends
  // meet there so the national view can show just the junction hubs
  const flowNodeSubs = useMemo(() => {
    if (!grid || !gridFlows) return [];
    const ends = new Map<string, number>();
    for (const line of gridFlows) {
      for (const [lon, lat] of [line.path[0], line.path[line.path.length - 1]]) {
        const key = `${Math.round(lon * 50)},${Math.round(lat * 50)}`;
        ends.set(key, (ends.get(key) ?? 0) + 1);
      }
    }
    const out: Array<GridData["subs"][number] & { degree: number }> = [];
    for (const sub of grid.subs) {
      if (sub.voltage < 220000) continue;
      const cx = Math.round(sub.position[0] * 50);
      const cy = Math.round(sub.position[1] * 50);
      let degree = 0;
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) degree += ends.get(`${cx + dx},${cy + dy}`) ?? 0;
      if (degree > 0) out.push({ ...sub, degree });
    }
    return out;
  }, [grid, gridFlows]);

  // STATIC grid layers (built ONCE per data/toggle change, never on pan/zoom —
  // a per-moveend viewport filter over 10k paths was re-triangulating the whole
  // backbone on every interaction, which was the actual stutter. 10k thin lines
  // + 600 points is trivial for the GPU; let it clip naturally instead.)
  const gridStatic = useMemo<Layer[]>(() => {
    const layers: Layer[] = [];
    if (gridBackbone) {
      // backbone lines are MVT-tiled (frontend/scripts/tile-grid.mjs) — deck.gl
      // fetches+rasterizes only the tiles in view, instead of the old PathLayer
      // shading all ~10k segments every frame forever (depthCompare:"always"
      // disables early-Z rejection, so that was a steady, escalating GPU cost).
      layers.push(
        new MVTLayer({
          id: "grid-base",
          data: "/tiles/grid-backbone/{z}/{x}/{y}.pbf",
          minZoom: 0,
          maxZoom: 9,
          // NOT pickable: same readPixels-stall reasoning as before — substations
          // + corridors carry the click targets instead.
          pickable: false,
          // MVTLayer decodes tiles to a binary typed-array format by default, not a
          // plain Feature[] — renderSubLayers below filters props.data with a normal
          // array .filter(), which needs the non-binary (GeoJSON) tile shape.
          binary: false,
          parameters: { depthCompare: "always", depthWriteEnabled: false },
          renderSubLayers: (props) => {
            // empty tiles (no features at that z/x/y) are omitted from the pyramid
            // entirely (see tile-grid.mjs), so the fetch 404s and props.data is null —
            // not an error, just an empty tile.
            const raw = (props.data ?? []) as unknown as Array<{
              properties: { voltage: number };
            }>;
            // power scene: 220/380 kV are drawn by the flow layer (merged, clean
            // corridors), so the raw OSM ways only contribute the 110 kV mesh
            const data = raw.filter(
              (f) =>
                voltageAllowed(f.properties.voltage, gridVoltages) &&
                (!powerSceneActive || f.properties.voltage < 220000),
            );
            if (powerSceneActive) {
              const c = powerLineColor(110000);
              return new GeoJsonLayer({
                ...props,
                data: data as unknown as GeoJSON.Feature[],
                stroked: true,
                filled: false,
                getLineColor: [c[0], c[1], c[2], 150],
                getLineWidth: 0.8,
                lineWidthUnits: "pixels",
                lineWidthMinPixels: 0.6,
                lineCapRounded: true,
                lineJointRounded: true,
                parameters: { depthCompare: "always", depthWriteEnabled: false },
              });
            }
            return new GeoJsonLayer({
              ...props,
              data: data as unknown as GeoJSON.Feature[],
              stroked: true,
              filled: false,
              getLineColor: (f: { properties: { voltage: number } }) => {
                const c = voltColor(f.properties.voltage);
                return [c[0], c[1], c[2], 150];
              },
              getLineWidth: (f: { properties: { voltage: number } }) =>
                f.properties.voltage >= 380000 ? 2.6 : 1.6,
              lineWidthUnits: "pixels",
              lineWidthMinPixels: 1.6,
              lineCapRounded: true,
              lineJointRounded: true,
              parameters: { depthCompare: "always", depthWriteEnabled: false },
            });
          },
        }),
      );
    }
    if (gridBackbone && grid && powerSceneActive) {
      // substations as transit-map station rings where corridors meet: opaque,
      // so they read as nodes, not as more flow dots. Zoomed out, only junction
      // hubs (380 kV first), so the national view doesn't turn into confetti.
      const subs = flowNodeSubs.filter(
        (d) =>
          voltageAllowed(d.voltage, gridVoltages) &&
          (viewZoom >= 7.5 || (d.degree >= (viewZoom < 5.5 ? 4 : 3) && (viewZoom >= 6.5 || d.voltage >= 380000))),
      );
      const size = viewZoom >= 8 ? 1.25 : viewZoom < 5.5 ? 0.8 : 1;
      layers.push(
        new StationDotLayer<(typeof subs)[number]>({
          id: "grid-subs-power",
          data: subs,
          getPosition: (d) => d.position,
          getRadius: (d) => (d.voltage >= 380000 ? 3.3 : 2.7) * size,
          radiusUnits: "pixels",
          getFillColor: (d) => {
            const c = powerLineColor(d.voltage);
            return [c[0], c[1], c[2], 255];
          },
          holeColor: POWER_LAND,
          stroked: false,
          pickable: true,
          onClick: (info) => info.object && onGridSelect({ kind: "substation", sub: info.object }),
          parameters: PREMULTIPLIED_BLEND,
          updateTriggers: { getRadius: size },
        }),
      );
    }
    if (gridBackbone && grid && !powerSceneActive) {
      // 110 kV alone is ~5,400 substations nationwide (vs. ~580 for 380/220 kV) — shown
      // at country zoom they overlap into a solid mass that buries the lines underneath
      // them. Only render that tier once zoomed into a region where they have room to
      // read as individual points (matches the SITE_ZOOM-style zoom gating used elsewhere).
      const subs = grid.subs.filter(
        (d) => voltageAllowed(d.voltage, gridVoltages) && (d.voltage >= 220000 || viewZoom >= 7),
      );
      layers.push(
        new ScatterplotLayer<GridData["subs"][number]>({
          id: "grid-subs",
          data: subs,
          getPosition: (d) => d.position,
          getRadius: (d) => (d.voltage >= 380000 ? 3.0 : 2.1),
          radiusUnits: "pixels",
          radiusMinPixels: 1.4,
          radiusMaxPixels: 6,
          getFillColor: (d) => {
            const c = voltColor(d.voltage);
            return [c[0], c[1], c[2], powerSceneActive ? 128 : 215];
          },
          stroked: false,
          pickable: true,
          radiusScale: 2.2,
          onClick: (info) => info.object && onGridSelect({ kind: "substation", sub: info.object }),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (gridPlanned && planned) {
      const segs = gridConstructionOnly
        ? planned.segs.filter((s) => s.phase === "construction")
        : planned.segs;
      layers.push(
        new PathLayer<PlannedSeg>({
          id: "planned-base",
          data: segs,
          getPath: (d) => d.path,
          getColor: (d) => {
            const c = PHASE_COLOR[d.phase];
            return [c[0], c[1], c[2], d.phase === "planned" ? 130 : 215];
          },
          getWidth: (d) => (d.phase === "construction" || d.phase === "operational" ? 4 : 3),
          widthUnits: "pixels",
          widthMinPixels: 3,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && onGridSelect({ kind: "corridor", seg: info.object }),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    return layers;
  }, [grid, flowNodeSubs, planned, gridBackbone, gridPlanned, gridConstructionOnly, gridVoltages, viewZoom, powerSceneActive, onGridSelect]);

  const germanyOutline = useMemo(
    () => (infrastructure ? outlineFromStates(infrastructure.states as GeoJSON.FeatureCollection) : []),
    [infrastructure],
  );

  const infraStatic = useMemo<Layer[]>(() => {
    if (!infrastructure) return [];
    const layers: Layer[] = [];
    const pathVisible = (item: InfraPath) => pathIntersectsBounds(item.path, bounds, 0.08);
    const select = (item: InfraItem) =>
      onGridSelect({ kind: "infrastructure", item, manifest: infrastructure.manifest });

    if (infraStateBoundaries && powerSceneActive) {
      // power scene: Germany as one solid land mass, faint state lines, crisp national outline
      layers.push(
        new GeoJsonLayer({
          id: "infra-state-boundaries-power",
          data: infrastructure.states,
          stroked: true,
          filled: true,
          getFillColor: [...POWER_LAND, 255],
          getLineColor: [58, 72, 94, 150],
          getLineWidth: 0.7,
          lineWidthUnits: "pixels",
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new PathLayer<[number, number][]>({
          id: "infra-germany-outline",
          data: germanyOutline,
          getPath: (d) => d,
          getColor: [112, 132, 158, 210],
          getWidth: 1.1,
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    } else if (infraStateBoundaries) {
      layers.push(
        new GeoJsonLayer({
          id: "infra-state-boundaries",
          data: infrastructure.states,
          stroked: true,
          filled: true,
          getFillColor: [28, 40, 56, 34],
          getLineColor: [118, 151, 181, 92],
          getLineWidth: 1.1,
          lineWidthUnits: "pixels",
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }

    if (infraRail) {
      const railRows = railSceneActive ? infrastructure.rail.filter(pathVisible) : infrastructure.rail;
      layers.push(
        new PathLayer<InfraPath>({
          id: "infra-rail",
          data: railRows,
          getPath: (d) => d.path,
          getColor: railSceneActive ? [104, 145, 166, 68] : [126, 220, 238, 118],
          getWidth: (d) =>
            railSceneActive
              ? String(d.properties.tracks || "").toLowerCase().includes("zweigleisig")
                ? 1.15
                : 0.9
              : 1.35,
          widthUnits: "pixels",
          widthMinPixels: 1,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraRailStructures) {
      const minLength = viewZoom < 7.2 ? 2_200 : viewZoom < 8.5 ? 900 : 90;
      const visibleStructures = infrastructure.railStructures.filter(
        (d) => pathVisible(d) && Number(d.properties.length_m || 0) >= minLength,
      );
      const bridges = visibleStructures.filter((d) => d.kind === "rail_bridge");
      const tunnels = visibleStructures.filter((d) => d.kind === "rail_tunnel");
      const bridgePiers = structurePoints(bridges, "pier");
      const tunnelPortals = structurePoints(tunnels, "portal");

      layers.push(
        new PathLayer<InfraPath>({
          id: "infra-rail-tunnel-tubes",
          data: tunnels,
          getPath: (d) => pathAtHeight(d.path, 90),
          getColor: [42, 28, 62, 230],
          getWidth: (d) => Math.max(5.2, Math.min(11, Math.sqrt(Number(d.properties.length_m || 120)) / 6)),
          widthUnits: "pixels",
          widthMinPixels: 4,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new PathLayer<InfraPath>({
          id: "infra-rail-tunnel-glow",
          data: tunnels,
          getPath: (d) => pathAtHeight(d.path, 130),
          getColor: [222, 135, 255, 215],
          getWidth: 1.8,
          widthUnits: "pixels",
          widthMinPixels: 1.6,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new PathLayer<InfraPath>({
          id: "infra-rail-bridge-decks",
          data: bridges,
          getPath: (d) => pathAtHeight(d.path, railStructureHeight(d)),
          getColor: [255, 226, 130, 225],
          getWidth: (d) => Math.max(2.8, Math.min(6, Math.sqrt(Number(d.properties.length_m || 90)) / 6)),
          widthUnits: "pixels",
          widthMinPixels: 2.4,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new SimpleMeshLayer<RailStructurePoint>({
          id: "infra-rail-bridge-piers",
          data: bridgePiers,
          mesh: BRIDGE_PIER_MESH as never,
          getPosition: (d) => [d.position[0], d.position[1], 0],
          getScale: (d) => [520, 520, d.height],
          getColor: [230, 212, 164, 205],
          pickable: true,
          onClick: (info) => info.object && select(info.object.item),
          material: { ambient: 0.55, diffuse: 0.6, shininess: 18 },
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new SimpleMeshLayer<RailStructurePoint>({
          id: "infra-rail-tunnel-portals",
          data: tunnelPortals,
          mesh: TUNNEL_PORTAL_MESH as never,
          getPosition: (d) => [d.position[0], d.position[1], 0],
          getScale: [760, 760, 760],
          getColor: [168, 110, 245, 215],
          pickable: true,
          onClick: (info) => info.object && select(info.object.item),
          material: { ambient: 0.48, diffuse: 0.55, shininess: 22 },
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraGas) {
      layers.push(
        new PathLayer<InfraPath>({
          id: "infra-gas",
          data: infrastructure.gas,
          getPath: (d) => d.path,
          getColor: [236, 180, 72, 190],
          getWidth: (d) => Math.max(1.7, Math.min(4.5, Number(d.properties.diameter_mm || 0) / 320)),
          widthUnits: "pixels",
          widthMinPixels: 1.5,
          capRounded: true,
          jointRounded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    return layers;
  }, [infrastructure, germanyOutline, bounds, viewZoom, railSceneActive, powerSceneActive, infraStateBoundaries, infraRail, infraRailStructures, infraGas, onGridSelect]);

  const infraNodeLayers = useMemo<Layer[]>(() => {
    if (!infrastructure) return [];
    const [w, s0, e, n] = bounds;
    const marginX = (e - w) * 0.05;
    const marginY = (n - s0) * 0.05;
    const inView = (node: InfraNode) =>
      node.position[0] >= w - marginX &&
      node.position[0] <= e + marginX &&
      node.position[1] >= s0 - marginY &&
      node.position[1] <= n + marginY;
    const select = (item: InfraItem) =>
      onGridSelect({ kind: "infrastructure", item, manifest: infrastructure.manifest });
    const layers: Layer[] = [];

    if (infraRailStations) {
      const stationThreshold = railSceneActive
        ? viewZoom < 8.5
          ? 0.78
          : viewZoom < 9.4
            ? 0.56
            : 0.36
        : viewZoom >= 7.2
          ? 0
          : 0.72;
      const railNodes = infrastructure.nodes
        .filter((d) => (d.kind === "rail_station" || d.kind === "rail_crossing") && inView(d))
        .filter((d) => d.kind === "rail_crossing" || railNodeScore(d) >= stationThreshold);
      const stations = railNodes.filter((d) => d.kind === "rail_station");
      const crossings = viewZoom >= (railSceneActive ? 10 : 8) ? railNodes.filter((d) => d.kind === "rail_crossing") : [];
      layers.push(
        new SimpleMeshLayer<InfraNode>({
          id: "infra-rail-station-objects",
          data: stations,
          mesh: STATION_MESH as never,
          getPosition: (d) => [d.position[0], d.position[1], 0],
          getScale: (d) => {
            const s = 520 + railNodeScore(d) * 820;
            return [s, s, s * 1.35];
          },
          getColor: (d) => {
            const s = railNodeScore(d);
            return s > 0.7 ? [226, 242, 255, 230] : [126, 220, 238, 205];
          },
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          material: { ambient: 0.55, diffuse: 0.58, shininess: 26 },
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
        new ScatterplotLayer<InfraNode>({
          id: "infra-rail-crossings",
          data: crossings,
          getPosition: (d) => d.position,
          getRadius: 1.7,
          radiusUnits: "pixels",
          radiusMinPixels: 1,
          radiusMaxPixels: 4.5,
          getFillColor: (d) => {
            const c = INFRA_COLOR[d.kind];
            return [c[0], c[1], c[2], 170];
          },
          stroked: true,
          getLineColor: [8, 14, 20, 180],
          lineWidthMinPixels: 0.5,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }

    if (infraPorts) {
      const ports = infrastructure.nodes.filter((d) => d.kind === "port" && inView(d));
      layers.push(
        new ColumnLayer<InfraNode>({
          id: "infra-ports",
          data: ports,
          getPosition: (d) => d.position,
          getElevation: 7_000,
          getFillColor: [...INFRA_COLOR.port, 215],
          getLineColor: [205, 246, 255, 230],
          radius: 850,
          radiusUnits: "meters",
          diskResolution: 8,
          extruded: true,
          stroked: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraAirports) {
      const airports = infrastructure.nodes.filter((d) => d.kind === "airport" && inView(d));
      layers.push(
        new ColumnLayer<InfraNode>({
          id: "infra-airports",
          data: airports,
          getPosition: (d) => d.position,
          getElevation: (d) => (d.properties.tentec ? 8_500 : 5_200),
          getFillColor: [...INFRA_COLOR.airport, 205],
          getLineColor: [218, 235, 255, 230],
          radius: 720,
          radiusUnits: "meters",
          diskResolution: 6,
          extruded: true,
          stroked: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraGasNodes) {
      const gasNodes = infrastructure.nodes.filter(
        (d) => (d.kind === "gas_storage" || d.kind === "lng_terminal" || d.kind === "gas_border") && inView(d),
      );
      layers.push(
        new ColumnLayer<InfraNode>({
          id: "infra-gas-nodes",
          data: gasNodes,
          getPosition: (d) => d.position,
          getElevation: (d) => {
            if (d.kind === "gas_border") return 5_000;
            const workingGas = Number(d.properties.working_gas_mcm || 0);
            return 7_000 + Math.sqrt(workingGas) * 260;
          },
          getFillColor: (d) => [...INFRA_COLOR[d.kind], 220],
          getLineColor: [245, 243, 255, 220],
          radius: 950,
          radiusUnits: "meters",
          diskResolution: 8,
          extruded: true,
          stroked: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraGasFacilities) {
      const gasFacilities = infrastructure.nodes.filter(
        (d) =>
          (d.kind === "gas_compressor" ||
            d.kind === "gas_consumer" ||
            d.kind === "gas_production" ||
            d.kind === "gas_powerplant") &&
          inView(d),
      );
      layers.push(
        new ScatterplotLayer<InfraNode>({
          id: "infra-gas-facilities",
          data: gasFacilities,
          getPosition: (d) => d.position,
          getRadius: (d) => (d.kind === "gas_compressor" ? 4.5 : 3),
          radiusUnits: "pixels",
          radiusMinPixels: 2,
          radiusMaxPixels: 7,
          getFillColor: (d) => {
            const c = INFRA_COLOR[d.kind];
            return [c[0], c[1], c[2], 220];
          },
          stroked: true,
          getLineColor: [28, 22, 12, 180],
          lineWidthMinPixels: 0.7,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    if (infraIndustry) {
      const industry = infrastructure.nodes.filter((d) => d.kind === "industry" && inView(d));
      layers.push(
        new ColumnLayer<InfraNode>({
          id: "infra-industry",
          data: industry,
          getPosition: (d) => d.position,
          getElevation: (d) => 2_800 + Math.log1p(Number(d.properties.facilities || 1)) * 2_400,
          getFillColor: (d) => [...(INDUSTRY_COLOR[String(d.properties.sector)] || INFRA_COLOR.industry), 190],
          radius: 480,
          radiusUnits: "meters",
          diskResolution: 6,
          extruded: true,
          pickable: true,
          onClick: (info) => info.object && select(info.object),
          parameters: { depthCompare: "always", depthWriteEnabled: false },
        }),
      );
    }
    return layers;
  }, [
    infrastructure,
    bounds,
    infraRailStations,
    viewZoom,
    infraPorts,
    infraAirports,
    infraGasNodes,
    infraGasFacilities,
    infraIndustry,
    railSceneActive,
    onGridSelect,
  ]);

  const infraFlowData = useMemo(
    () => {
      const [w, s0, e, n] = bounds;
      const marginX = (e - w) * 0.08;
      const marginY = (n - s0) * 0.08;
      const inView = (node: InfraNode) =>
        node.position[0] >= w - marginX &&
        node.position[0] <= e + marginX &&
        node.position[1] >= s0 - marginY &&
        node.position[1] <= n + marginY;
      const railStride = railSceneActive ? (viewZoom < 7 ? 4 : viewZoom < 8.3 ? 2 : 1) : 8;
      const railLimit = railSceneActive ? (viewZoom < 7 ? 520 : 320) : 420;
      return {
        gas: infrastructure?.gas.filter((d, i) => i % 3 === 0 && pathIntersectsBounds(d.path, bounds, 0.08)) ?? [],
        rail:
          infrastructure?.rail
            .filter((d, i) => i % railStride === 0 && pathIntersectsBounds(d.path, bounds, 0.1))
            .sort((a, b) => railRouteScore(b) - railRouteScore(a))
            .slice(0, railLimit) ?? [],
        railNodes:
          infrastructure?.nodes
            .filter((d, i) => infraRailStations && d.kind === "rail_station" && i % 13 === 0 && inView(d))
            .slice(0, 900) ?? [],
        nodes:
          infrastructure?.nodes.filter(
            (d) =>
              ((infraPorts && d.kind === "port") ||
                (infraAirports && d.kind === "airport") ||
                (infraGasNodes && (d.kind === "gas_storage" || d.kind === "lng_terminal" || d.kind === "gas_border")) ||
                (infraGasFacilities &&
                  (d.kind === "gas_compressor" ||
                    d.kind === "gas_consumer" ||
                    d.kind === "gas_production" ||
                    d.kind === "gas_powerplant"))) &&
              inView(d),
          ) ?? [],
      };
    },
    [
      infrastructure,
      bounds,
      viewZoom,
      railSceneActive,
      infraRailStations,
      infraPorts,
      infraAirports,
      infraGasNodes,
      infraGasFacilities,
    ],
  );

  // all ~325 corridors, never viewport-culled: the flow layer animates on the GPU,
  // so a stable array (no re-upload on pan) is cheaper than culling
  const gridFlowData = useMemo(
    () => (gridFlows && gridBackbone ? gridFlows.filter((line) => voltageAllowed(line.voltage, gridVoltages)) : []),
    [gridFlows, gridBackbone, gridVoltages],
  );

  // power-view plants. LOD by zoom band (PLANT_LOD): ~28 km cells and only
  // regional-scale clusters nationally, ~7 km cells regionally, every unit up
  // close. Rebuilt only when the band changes.
  const plantLod = !powerSceneActive || !sites.length ? -1 : viewZoom < 6.5 ? 0 : viewZoom < 8.5 ? 1 : 2;
  const plantsNational = useMemo(
    () => (powerSceneActive && sites.length ? plantClusters(sites, PLANT_LOD[0].cell) : []),
    [powerSceneActive, sites],
  );
  const plantData = useMemo(() => {
    if (plantLod < 0) return [];
    const { cell, min } = PLANT_LOD[plantLod];
    const clusters = plantLod === 0 ? plantsNational : plantClusters(sites, cell);
    return clusters.filter((d) => d.capacity_mw >= min[d.group]);
  }, [plantLod, plantsNational, sites]);
  // only the largest thermal plants and pumped storage emit slow pulse rings
  const plantPings = useMemo(
    () =>
      plantData.filter(
        (d) => (d.group === "fossil" && d.capacity_mw >= 600) || (d.technology === "storage" && d.capacity_mw >= 200),
      ),
    [plantData],
  );
  // feeders use the national clusters at every zoom so the links stay stable
  const plantFeederData = useMemo<PlantFeeder[]>(
    () =>
      grid && plantsNational.length
        ? plantFeeders(
            plantsNational,
            grid.subs.filter((d) => d.voltage >= 220000),
            400,
          )
        : [],
    [grid, plantsNational],
  );
  const activity = useMemo(() => plantActivity(gridLatest ?? {}), [gridLatest]);

  // cross-border links: curved geometry once per data refresh (5 min); the shared
  // flow clock animates them with the grid, so only uniforms change per frame.
  const exchangeLines = useMemo<ExchangeFlowLine[]>(
    () => (gridExchangeFlows ? exchangeFlowLines(exchange ?? [], EXCHANGE_COUNTRY_CODE) : []),
    [exchange, gridExchangeFlows],
  );

  // text for the power view: city callouts + each neighbour's live flow, as
  // MapLibre markers (DOM text: crisp, and always above the WebGL glow). Rebuilt
  // only when the scene or the 5-minute exchange data changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || (!powerSceneActive && !exchangeLines.length)) return;
    const markers = powerLabelMarkers(map, powerSceneActive, exchangeLines, !!capture);
    return () => markers.forEach((m) => m.remove());
  }, [powerSceneActive, exchangeLines]);

  // construction-phase planned segments for the flow trail — memoized so its
  // array identity is stable across animation frames. Re-filtering this every
  // frame (60/sec) made the TripsLayer think `data` changed each frame and
  // rebuild its GPU buffers from scratch, which piled up GC pressure until the
  // tab stalled after a few seconds.
  const buildingSegs = useMemo(
    () => (gridPlanned && planned ? planned.segs.filter((s) => s.phase === "construction") : []),
    [gridPlanned, planned],
  );

  // toggle the satellite basemap
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (!map.getLayer("satellite")) return;
      map.setLayoutProperty("satellite", "visibility", basemap === "satellite" ? "visible" : "none");
    };
    if (map.getLayer("satellite")) apply();
    else map.once("load", apply);
  }, [basemap]);

  // power scene: strip the dark basemap to land, water and national borders so
  // the grid is the only line work on screen (restored when the scene ends)
  // The power view is flat, so terrain is switched off there: it adds nothing at
  // pitch 0 but costs a depth/coords pass every frame plus a GPU readback per
  // label marker (MapLibre marker occlusion), which dropped the view to ~15 fps.
  const powerBasemap = powerSceneActive && basemap === "dark";
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    // needs only the style JSON, not tiles ("load" waits for every initial tile,
    // terrain included, which can take many seconds); re-run on style changes so
    // layers added later (hillshade, in the load handler) are hidden too
    const apply = () => {
      if (!map.getLayer("background")) return;
      setPowerBasemap(map, powerBasemap);
      const wantTerrain = !powerSceneActive && !!map.getSource("terrain");
      if (wantTerrain !== !!map.getTerrain()) {
        map.setTerrain(wantTerrain ? { source: "terrain", exaggeration: 1.25 } : null);
      }
    };
    apply();
    map.on("styledata", apply);
    map.on("load", apply);
    return () => {
      map.off("styledata", apply);
      map.off("load", apply);
    };
  }, [powerBasemap, powerSceneActive]);

  // push the open site's footprint into the terrain-draped extrusion source
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const src = map.getSource("footprint") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      if (!footprint) {
        src.setData(EMPTY_FC as never);
        return;
      }
      // colour by construction state; fall back to technology for not-yet-analysed
      // sites so the footprint stays legible instead of dim grey
      const c =
        footprint.status !== "unknown"
          ? STATE_COLOR[footprint.status] ?? DIM
          : (footprint.technology && TECH_COLOR[footprint.technology]) || DIM;
      // the 3D object is the model now; the footprint is just a thin pad + bright
      // outline marking the real site extent (reads well over satellite too)
      src.setData({
        type: "Feature",
        geometry: { type: "MultiPolygon", coordinates: footprint.geom.coordinates },
        properties: { color: `rgb(${c[0]},${c[1]},${c[2]})`, height: 5 },
      } as never);
    };
    if (map.getSource("footprint")) apply();
    else map.once("load", apply);
  }, [footprint]);

  // centre + extent (metres) of the open site's footprint, to fit a real-scale
  // object onto the actual parcel
  const footMeta = useMemo(() => {
    if (!footprint?.technology || footprint.technology === "wind") return null;
    let minX = 180;
    let minY = 90;
    let maxX = -180;
    let maxY = -90;
    for (const poly of footprint.geom.coordinates)
      for (const ring of poly)
        for (const [x, y] of ring) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const wM = (maxX - minX) * 111320 * Math.cos((cy * Math.PI) / 180);
    const hM = (maxY - minY) * 111320;
    return {
      center: [cx, cy] as [number, number],
      span: Math.max(wM, hM, 60),
      tech: footprint.technology as Exclude<Technology, "wind">,
      status: footprint.status,
    };
  }, [footprint]);

  // deck.gl meshes don't drape on the DEM, so look up the ground elevation under
  // each turbine and lift it explicitly; recompute once the fly-in camera settles
  useEffect(() => {
    const map = mapRef.current;
    if (!map || turbines.length === 0) {
      groundZ.current = new Map();
      return;
    }
    const compute = () => {
      const next = new Map<string, number>();
      for (const t of turbines) next.set(t.id, map.queryTerrainElevation([t.lon, t.lat]) ?? 0);
      groundZ.current = next;
      setGroundTick((x) => x + 1);
    };
    compute();
    map.on("moveend", compute);
    map.on("idle", compute);
    return () => {
      map.off("moveend", compute);
      map.off("idle", compute);
    };
  }, [turbines]);

  // terrain-seat the per-site objects: look up ground elevation for the sites in
  // view (so they sit on slopes, not at sea level). only while objects are shown.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || aggregated) return;
    const compute = () => {
      const b = map.getBounds();
      const [w, e, s, n] = [b.getWest(), b.getEast(), b.getSouth(), b.getNorth()];
      for (const site of sites) {
        if (site.lon < w || site.lon > e || site.lat < s || site.lat > n) continue;
        groundZ.current.set(site.id, map.queryTerrainElevation([site.lon, site.lat]) ?? 0);
      }
      setGroundTick((x) => x + 1);
    };
    compute();
    map.on("moveend", compute);
    return () => {
      map.off("moveend", compute);
    };
  }, [sites, aggregated]);

  // every site is a capacity-scaled 3D object, sized to the *screen* (like the old
  // bars) so it stays clearly visible at any altitude — not in real metres, which
  // would vanish when zoomed out. spin rotors only when close (bounded instances).
  const spinPhase = closeUp ? phase : 0;
  // far ⇆ near crossfade: the density field fades out and 3D objects fade in across this band
  const objOpacity = Math.max(0, Math.min(1, (viewZoom - 8.6) / 0.8));
  const objectLayers = useMemo<Layer[]>(() => {
    if (objOpacity <= 0 || powerSceneActive) return [];
    const click = (info: PickingInfo) => {
      const o = info.object as Site | undefined;
      if (o) onSelect(o.id);
    };
    const gz = (s: Site) => groundZ.current.get(s.id) ?? 0;
    // metres-per-pixel at this zoom → size objects to a target on-screen pixel size
    const mpp = (156543.03 * Math.cos((GERMANY_VIEW.latitude * Math.PI) / 180)) / 2 ** viewZoom;
    const sizeFor = (cap: number) => (9 + Math.min(15, Math.sqrt(Math.max(cap, 1))) * 1.9) * mpp;
    const layers: Layer[] = [];
    for (const [tech, rows] of byTech) {
      if (tech === "wind") {
        // tall, thin tower → a clear vertical silhouette at any zoom (like a bar)
        layers.push(
          new SimpleMeshLayer<Site>({
            id: "obj-wind-tower",
            data: rows,
            mesh: TOWER_MESH as never,
            getPosition: (s) => [s.lon, s.lat, gz(s)],
            getScale: (s) => {
              const B = sizeFor(s.capacity_mw);
              const r = Math.max(B * 0.05, 8);
              return [r, r, B * 1.3];
            },
            getColor: (s) => colorOf(s, colorMode),
            opacity: objOpacity,
            pickable: true,
            onClick: click,
            updateTriggers: { getColor: colorMode, getScale: viewZoom },
            material: { ambient: 0.55, diffuse: 0.6, shininess: 36 },
          }),
        );
        layers.push(
          new SimpleMeshLayer<Site>({
            id: "obj-wind-rotor",
            data: rows,
            mesh: ROTOR_MESH as never,
            getPosition: (s) => [s.lon, s.lat, gz(s) + sizeFor(s.capacity_mw) * 1.3],
            getScale: (s) => {
              const r = sizeFor(s.capacity_mw) * 0.7;
              return [r, r, r];
            },
            getColor: (s) => colorOf(s, colorMode),
            opacity: objOpacity,
            getOrientation: closeUp
              ? (s: Site) => [spinPhase * 720 + ((s.lat * 9973) % 360), 0, 0]
              : [0, 0, 0],
            pickable: true,
            onClick: click,
            updateTriggers: {
              getColor: colorMode,
              getScale: viewZoom,
              getOrientation: closeUp ? spinPhase : 0,
            },
            material: { ambient: 0.55, diffuse: 0.6, shininess: 36 },
          }),
        );
      } else {
        // proportions are baked into the mesh; scale uniformly to the screen size
        layers.push(
          new SimpleMeshLayer<Site>({
            id: `obj-${tech}`,
            data: rows,
            mesh: OBJECT_MESH[tech] as never,
            getPosition: (s) => [s.lon, s.lat, gz(s)],
            getScale: (s) => {
              const B = sizeFor(s.capacity_mw);
              return [B, B, B];
            },
            getColor: (s) => colorOf(s, colorMode),
            opacity: objOpacity,
            pickable: true,
            onClick: click,
            updateTriggers: { getColor: colorMode, getScale: viewZoom },
            material: { ambient: 0.55, diffuse: 0.55, shininess: 28 },
          }),
        );
      }
    }
    return layers;
  }, [byTech, colorMode, closeUp, spinPhase, onSelect, groundTick, viewZoom, objOpacity, powerSceneActive]);

  // looked up once per selection, not inside the per-frame effect (a 51k-site
  // scan every animation frame)
  const selectedSite = useMemo(
    () => (selectedId ? sites.find((s) => s.id === selectedId) : undefined),
    [sites, selectedId],
  );

  // far/overview tier: every plant as a flat, capacity-proportional bubble
  // (area ∝ capacity, colour = the same state/technology palette the close-up
  // 3D objects use) — a classic proportional-symbol map, same idea as
  // OpenGridWorks' national plants view. Radius is in literal screen PIXELS
  // (not metres scaled by zoom) with a hard radiusMaxPixels ceiling, so a
  // bubble's on-screen size never grows as you zoom out further — zooming out
  // just shows more real, same-sized bubbles closer together, never bigger ones.
  const fieldOpacity = Math.max(0, Math.min(1, (9.4 - viewZoom) / 0.8));
  const plantBubbles = useMemo<Layer | null>(() => {
    if (fieldOpacity <= 0 || powerSceneActive) return null;
    const [w, s0, e, n] = bounds;
    const mLon = (e - w) * 0.06;
    const mLat = (n - s0) * 0.06;
    const inView = sites.filter(
      (s) =>
        s.id !== selectedId &&
        s.lon >= w - mLon &&
        s.lon <= e + mLon &&
        s.lat >= s0 - mLat &&
        s.lat <= n + mLat,
    );
    return new ScatterplotLayer<Site>({
      id: "plant-bubbles",
      data: inView,
      getPosition: (s) => [s.lon, s.lat],
      getRadius: (s) => 1 + Math.sqrt(Math.max(s.capacity_mw, 1)) * 0.45,
      radiusUnits: "pixels",
      radiusMinPixels: 1,
      radiusMaxPixels: 8,
      getFillColor: (s) => colorOf(s, colorMode),
      // a thin dark stroke is what keeps overlapping bubbles reading as many
      // circles instead of merging into one grey blob at Germany's site density
      stroked: true,
      getLineColor: [6, 8, 13, 140],
      lineWidthMinPixels: 0.6,
      lineWidthUnits: "pixels",
      pickable: true,
      opacity: fieldOpacity,
      onClick: (info: PickingInfo) => {
        const o = info.object as Site | undefined;
        if (o) onSelect(o.id);
      },
      updateTriggers: { getFillColor: colorMode },
    });
  }, [sites, bounds, selectedId, fieldOpacity, colorMode, onSelect, powerSceneActive]);

  useEffect(() => {
    if (!overlayRef.current) return;
    const selected = selectedSite;
    // the footprint extrusion is the marker once it loads; until then, a ring
    const ring =
      selected && !aggregated && !footprint
        ? new ScatterplotLayer<Site>({
            id: "selected",
            data: [selected],
            getPosition: (s) => [s.lon, s.lat],
            getRadius: 1200,
            radiusUnits: "meters",
            stroked: true,
            filled: false,
            getLineColor: [255, 255, 255, 230],
            lineWidthMinPixels: 2,
          })
        : null;
    // real per-turbine 3D models for the open wind farm (tower + rotor, scaled to
    // each turbine's hub height and rotor diameter, lifted onto the terrain)
    const showTurbines = !aggregated && turbines.length > 0;
    const towers = showTurbines
      ? new SimpleMeshLayer<Turbine>({
          id: "turbine-towers",
          data: turbines,
          mesh: TOWER_MESH as never,
          getPosition: (t) => [t.lon, t.lat, groundZ.current.get(t.id) ?? 0],
          getScale: (t) => {
            // tower height ~real hub height; radius exaggerated so it's visible
            // when the whole farm is in frame (a real 1.3m tower is sub-pixel)
            const h = t.hub_height_m ?? 100;
            return [Math.max(7, h * 0.07), Math.max(7, h * 0.07), h];
          },
          getColor: TURBINE_COLOR,
          material: { ambient: 0.55, diffuse: 0.6, shininess: 40 },
        })
      : null;
    const rotors = showTurbines
      ? new SimpleMeshLayer<Turbine>({
          id: "turbine-rotors",
          data: turbines,
          mesh: ROTOR_MESH as never,
          getPosition: (t) => [t.lon, t.lat, (groundZ.current.get(t.id) ?? 0) + (t.hub_height_m ?? 100)],
          getScale: (t) => {
            const r = (t.rotor_diameter_m ?? 90) / 2;
            return [r, r, r];
          },
          // spin the blades about the hub axis; per-turbine phase offset so a farm
          // doesn't rotate in lockstep. updateTriggers keeps the animation live.
          getOrientation: (t) => [phase * 720 + ((t.lat * 9973) % 360), 0, 0],
          getColor: TURBINE_COLOR,
          material: { ambient: 0.55, diffuse: 0.6, shininess: 40 },
          updateTriggers: { getOrientation: phase },
        })
      : null;

    const infraLayers: Layer[] = [];
    if (infrastructure) {
      const currentTime = (performance.now() * 0.16) % (infrastructure.maxTime + 60_000);
      if (infraGas && infraFlowData.gas.length) {
        infraLayers.push(
          new TripsLayer<InfraPath>({
            id: "infra-gas-flow",
            data: infraFlowData.gas,
            getPath: (d) => d.path,
            getTimestamps: (d) => d.timestamps,
            getColor: [255, 218, 137, 235],
            currentTime,
            trailLength: 34_000,
            fadeTrail: true,
            widthUnits: "pixels",
            getWidth: 3.4,
            widthMinPixels: 2,
            capRounded: true,
            jointRounded: true,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { currentTime },
          }),
        );
      }
      if (infraRail && infraFlowData.rail.length) {
        const sceneAge = railSceneActive ? performance.now() - railSceneStartedAt.current : 0;
        const railRamp = railSceneActive ? easeOutCubic(sceneAge / 42_000) : (performance.now() * 0.000018) % 1;
        const railTarget = Math.min(
          railSceneActive ? (viewZoom < 7 ? 220 : viewZoom < 8.6 ? 150 : 105) : 160,
          infraFlowData.rail.length,
        );
        const railCount = Math.min(
          infraFlowData.rail.length,
          Math.max(7, Math.floor(7 + railRamp * Math.max(0, railTarget - 7))),
        );
        const activeRailPaths = infraFlowData.rail.slice(0, railCount);
        const railClock = performance.now() * (railSceneActive ? 0.105 : 0.16);
        const railVehicles: RailVehicle[] = activeRailPaths
          .map((path, index) => {
            const point = railPointAt(path, railClock + (hashString(`${path.name}-${index}`) % 140_000));
            const glyphLength = trainGlyphLengthMeters(viewZoom, index);
            const head = point ? offsetLonLat(point.position, point.bearing, glyphLength / 2) : null;
            const tail = point ? offsetLonLat(point.position, point.bearing, -glyphLength / 2) : null;
            return point
              ? {
                  id: `${path.name}-${index}`,
                  position: [point.position[0], point.position[1], 28],
                  headPosition: [head![0], head![1], 30],
                  tailPosition: [tail![0], tail![1], 30],
                  bearing: point.bearing,
                  color: railVehicleColor(index),
                  scale: trainMeshScale(index),
                }
              : null;
          })
          .filter((row): row is RailVehicle => Boolean(row));
        const trackWidth = railSceneActive ? (viewZoom < 7 ? 2.6 : 4.8) : 2.8;
        const showDetailedTrains = railSceneActive && viewZoom >= 10.2 && railVehicles.length <= 90;
        infraLayers.push(
          new PathLayer<InfraPath>({
            id: "infra-rail-active-ribbons",
            data: activeRailPaths,
            getPath: (d) => d.path,
            getColor: railSceneActive ? [90, 210, 236, 72] : [126, 220, 238, 54],
            getWidth: trackWidth,
            widthUnits: "pixels",
            widthMinPixels: railSceneActive ? 2 : 1.5,
            capRounded: true,
            jointRounded: true,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
          }),
          new TripsLayer<InfraPath>({
            id: "infra-rail-flow",
            data: activeRailPaths,
            getPath: (d) => d.path,
            getTimestamps: (d) => d.timestamps,
            getColor: [220, 246, 255, 225],
            currentTime: railClock,
            trailLength: railSceneActive ? (viewZoom < 7 ? 18_000 : 8_800) : 15_000,
            fadeTrail: true,
            widthUnits: "pixels",
            getWidth: railSceneActive ? 2.2 : 2.8,
            widthMinPixels: railSceneActive ? 1.4 : 1.5,
            capRounded: true,
            jointRounded: true,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { currentTime: railClock },
          }),
          new PathLayer<RailVehicle>({
            id: "infra-rail-vehicle-capsules",
            data: railVehicles,
            getPath: (d) => [d.tailPosition, d.headPosition],
            getColor: (d) => d.color,
            getWidth: railSceneActive ? (viewZoom < 7 ? 2.2 : 3.4) : 2.2,
            widthUnits: "pixels",
            widthMinPixels: railSceneActive ? 2 : 1.4,
            capRounded: true,
            jointRounded: true,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getPath: railClock, getWidth: viewZoom },
          }),
          new ScatterplotLayer<RailVehicle>({
            id: "infra-rail-vehicle-glow",
            data: railVehicles,
            getPosition: (d) => d.position,
            getRadius: railSceneActive ? (viewZoom < 7 ? 1.9 : 2.8) : 2.2,
            radiusUnits: "pixels",
            getFillColor: (d) => [d.color[0], d.color[1], d.color[2], 78],
            stroked: false,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getPosition: railClock },
          }),
        );
        if (showDetailedTrains) {
          infraLayers.push(
          new SimpleMeshLayer<RailVehicle>({
            id: "infra-rail-vehicles",
            data: railVehicles,
            mesh: TRAIN_MESH as never,
            getPosition: (d) => d.position,
            getScale: (d) => d.scale,
            getColor: (d) => d.color,
            getOrientation: (d) => [0, 0, d.bearing],
            material: { ambient: 0.62, diffuse: 0.58, shininess: 38 },
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getPosition: railClock, getOrientation: railClock, getScale: viewZoom },
          }),
          new SimpleMeshLayer<RailVehicle>({
            id: "infra-rail-vehicle-windows",
            data: railVehicles,
            mesh: TRAIN_WINDOW_MESH as never,
            getPosition: (d) => d.position,
            getScale: (d) => d.scale,
            getColor: [242, 252, 255, 238],
            getOrientation: (d) => [0, 0, d.bearing],
            material: { ambient: 0.8, diffuse: 0.45, shininess: 64 },
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getPosition: railClock, getOrientation: railClock, getScale: viewZoom },
          }),
          );
        }
        infraLayers.push(
          new ScatterplotLayer<RailVehicle>({
            id: "infra-rail-headlights",
            data: railVehicles,
            getPosition: (d) => d.headPosition,
            getRadius: railSceneActive ? (viewZoom < 7 ? 1.2 : 1.8) : 1.4,
            radiusUnits: "pixels",
            getFillColor: [255, 246, 200, 230],
            stroked: false,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getPosition: railClock },
          }),
        );
      }
      if (infraRailStations && infraFlowData.railNodes.length) {
        const pulseT = (phase * 1.75) % 1;
        infraLayers.push(
          new ScatterplotLayer<InfraNode>({
            id: "infra-rail-node-dispatch-pulse",
            data: infraFlowData.railNodes,
            getPosition: (d) => d.position,
            getRadius: (d) => 900 + railNodeScore(d) * 2_400 + pulseT * 5_800,
            radiusUnits: "meters",
            stroked: true,
            filled: false,
            getLineColor: (d) => {
              const s = railNodeScore(d);
              return s > 0.7 ? [230, 248, 255, Math.round(170 * (1 - pulseT))] : [126, 220, 238, Math.round(115 * (1 - pulseT))];
            },
            lineWidthMinPixels: 1,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getRadius: pulseT, getLineColor: pulseT },
          }),
        );
      }
      if (infraFlowData.nodes.length) {
        const pulseT = (phase * 1.45) % 1;
        infraLayers.push(
          new ScatterplotLayer<InfraNode>({
            id: "infra-node-pulse",
            data: infraFlowData.nodes,
            getPosition: (d) => d.position,
            getRadius: 1_200 + pulseT * 7_500,
            radiusUnits: "meters",
            stroked: true,
            filled: false,
            getLineColor: (d) => {
              const c = INFRA_COLOR[d.kind];
              return [c[0], c[1], c[2], Math.round(165 * (1 - pulseT))];
            },
            lineWidthMinPixels: 1,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { getRadius: pulseT, getLineColor: pulseT },
          }),
        );
      }
    }

    // ANIMATED grid layers (flow dots, planned-corridor trails, plant arc). The
    // static base lines/substations/corridors live in the gridStatic memo.
    // Grid flow is GPU-animated: the FlowPathLayer instance is re-created each
    // frame but its data/attributes are stable, so a frame only updates the
    // clock uniforms — no per-frame particle arrays.
    const gridLayers: Layer[] = [];
    const signal = gridLiveSignal(gridLatest, exchange);
    const zoomNow = mapRef.current?.getZoom() ?? viewZoom;
    // one clock for every flow: constant on-screen speed (px/s), a little faster
    // when national generation is high
    flowClock.current.tick(performance.now(), zoomNow, 16 + 12 * clamp((signal.generationScale - 0.6) / 0.9, 0, 1));
    if (gridBackbone && gridFlowData.length) {
      gridLayers.push(
        new FlowPathLayer<GridFlowPath>({
          id: "grid-flow",
          data: gridFlowData,
          getPath: (d) => d.path,
          getTimestamps: (d) => d.flow,
          getColor: (d) => {
            const c = powerLineColor(d.voltage);
            return [c[0], c[1], c[2], d.voltage >= 380_000 ? 235 : 200];
          },
          // footprint only: it must hold the dot halo; the visible line is the core
          getWidth: (d) => Math.max(10, gridFlowStyle(d, powerSceneActive, viewZoom)[1] * 10),
          getFlowStyle: (d) => gridFlowStyle(d, powerSceneActive, viewZoom),
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          lineGlow: powerSceneActive ? 0.3 : 0,
          dotGlow: 0.55,
          dotWhite: 0.72,
          ...flowClock.current.uniforms(zoomNow, powerSceneActive ? 36 : 44),
          parameters: FLOW_BLEND,
          updateTriggers: {
            getWidth: [powerSceneActive, viewZoom],
            getFlowStyle: [powerSceneActive, viewZoom],
          },
        }),
      );
    }
    if (gridPlanned && planned) {
      const tp = (performance.now() * 0.14) % (planned.maxTime + 40000);
      if (buildingSegs.length)
        gridLayers.push(
          new TripsLayer<PlannedSeg>({
            id: "planned-flow",
            data: buildingSegs,
            getPath: (d) => d.path,
            getTimestamps: (d) => d.timestamps,
            getColor: [255, 200, 120],
            currentTime: tp,
            trailLength: 22000,
            fadeTrail: true,
            widthUnits: "pixels",
            getWidth: 5,
            widthMinPixels: 2.5,
            capRounded: true,
            jointRounded: true,
            parameters: { depthCompare: "always", depthWriteEnabled: false },
            updateTriggers: { currentTime: tp },
          }),
        );
    }

    // energised pulse rings at substations, coloured by voltage — gives the
    // backbone a "live" feel without animating the ~10k-segment MVT lines
    // themselves (that per-vertex/per-frame cost is exactly what the earlier
    // grid-freeze fixes this session removed). Capped to 220kV+ substations
    // (a few hundred) — the 110kV tier added ~4,800 more substations, and
    // animating a breathing ring on all of them every frame would reintroduce
    // the same per-frame cost problem, just from a different layer.
    const pulseSubs =
      grid?.subs.filter((d) => d.voltage >= 220000 && voltageAllowed(d.voltage, gridVoltages)) ?? [];
    if (gridBackbone && pulseSubs.length && !powerSceneActive) {
      const pulseT = (phase * 1.6) % 1; // restart slightly faster than the 2.2s site pulse
      gridLayers.push(
        new ScatterplotLayer<GridData["subs"][number]>({
          id: "grid-sub-pulse",
          data: pulseSubs,
          getPosition: (d) => d.position,
          getRadius: (d) => (800 + pulseT * 7000) * (d.voltage >= 380000 ? 1.15 : 0.8),
          radiusUnits: "meters",
          stroked: true,
          filled: false,
          getLineColor: (d) => {
            const c = voltColor(d.voltage);
            return [c[0], c[1], c[2], Math.round(190 * (1 - pulseT))];
          },
          lineWidthMinPixels: 1.5,
          parameters: { depthCompare: "always", depthWriteEnabled: false },
          updateTriggers: { getRadius: pulseT, getLineColor: pulseT },
        }),
      );
    }

    // cross-border flow (energy-charts cbpf): one curved link per neighbour, dots
    // travel exporter -> importer, line and dots grow with MW. Same flow clock and
    // shader as the grid, so both read as one system.
    if (gridExchangeFlows && exchangeLines.length) {
      const dotRadius = (d: ExchangeFlowLine) => clamp(1.9 + Math.abs(d.valueMw) / 1500, 1.9, 3.2);
      gridLayers.push(
        new FlowPathLayer<ExchangeFlowLine>({
          id: "exchange-flow",
          data: exchangeLines,
          getPath: (d) => d.path,
          getTimestamps: (d) => d.flow,
          getColor: (d) => {
            if (Math.abs(d.valueMw) < IDLE_FLOW_MW) return [120, 132, 150, 170];
            return [...EXCHANGE_COLOR, 235];
          },
          getWidth: (d) => dotRadius(d) * 10,
          getFlowStyle: (d) => [
            clamp(1.1 + Math.abs(d.valueMw) / 1400, 1.1, 3),
            dotRadius(d),
            Math.abs(d.valueMw) >= IDLE_FLOW_MW ? 1 : 0,
          ],
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          lineGlow: 0.35,
          dotGlow: 0.6,
          dotWhite: 0.6,
          ...flowClock.current.uniforms(zoomNow, 30),
          pickable: true,
          onClick: (info) => info.object && onGridSelect({ kind: "exchange", flow: info.object.row }),
          parameters: FLOW_BLEND,
        }),
      );
    }

    // 3D arc from the open plant to its nearest substation (its grid connection)
    if (showGrid && plantArc) {
      gridLayers.push(
        new ArcLayer<typeof plantArc>({
          id: "plant-grid-arc",
          data: [plantArc],
          getSourcePosition: (d) => d.from,
          getTargetPosition: (d) => d.to,
          getSourceColor: [150, 230, 255, 230],
          getTargetColor: [150, 230, 255, 40],
          getHeight: 0.5,
          getWidth: 3 + 1.5 * (0.5 + 0.5 * Math.sin(phase * 6.28)),
          widthUnits: "pixels",
          greatCircle: false,
          parameters: { depthCompare: "always", depthWriteEnabled: false },
          updateTriggers: { getWidth: phase },
        }),
      );
    }

    // power-view plants, drawn UNDER the grid (see the setProps order): feeder
    // curves into the nearest 220/380 kV substation, soft animated glows, and
    // slow pulse rings on the big thermal / pumped-storage plants. All motion is
    // shader-side from `time`; data and attributes only change with the LOD band
    // or the 5-minute live refresh.
    const plantLayers: Layer[] = [];
    if (powerSceneActive && plantData.length) {
      const time = performance.now() / 1000;
      const scale = clamp(1 + (zoomNow - 8) * 0.15, 1, 1.6);
      const feederFade = clamp((9.2 - zoomNow) / 0.7, 0, 1);
      // no plant->substation links in the video: they are approximate (nearest
      // substation), and every mark in a published frame has to be real
      if (plantFeederData.length && feederFade > 0 && !capture) {
        plantLayers.push(
          new FlowPathLayer<PlantFeeder>({
            id: "power-plant-feeders",
            data: plantFeederData,
            getPath: (d) => d.path,
            getTimestamps: (d) => d.flow,
            getColor: (d) => [...PLANT_COLOR[d.group], 150],
            getWidth: 12,
            getFlowStyle: (d) => [0.75, 1.35, feederDotOpacity(d.group, activity)],
            widthUnits: "pixels",
            capRounded: true,
            jointRounded: true,
            lineGlow: 0.06,
            dotGlow: 0.4,
            dotWhite: 0.45,
            opacity: feederFade,
            ...flowClock.current.uniforms(zoomNow, 22),
            parameters: FLOW_BLEND,
            updateTriggers: { getFlowStyle: activity },
          }),
        );
      }
      plantLayers.push(
        new PlantGlowLayer<PlantCluster>({
          id: "power-plants",
          data: plantData,
          getPosition: (d) => d.position,
          // quad radius; the shader puts the disc edge at 55% of it, faint halo beyond
          getRadius: (d) => (plantRadius(d.capacity_mw) * scale) / 0.55,
          radiusUnits: "pixels",
          getFillColor: (d) => [...PLANT_COLOR[d.group], 255],
          getGlow: (d) => plantGlowStyle(d, activity),
          time,
          pickable: true,
          onClick: (info) => {
            const d = info.object;
            if (!d) return;
            if (d.siteId) onSelect(d.siteId);
            else mapRef.current?.flyTo({ center: d.position, zoom: Math.min(zoomNow + 2, 11), duration: 900 });
          },
          parameters: SCREEN_BLEND,
          updateTriggers: { getGlow: activity, getRadius: scale },
        }),
      );
      if (plantPings.length) {
        const pingLevel = plantLevel("fossil", activity);
        plantLayers.push(
          new PlantGlowLayer<PlantCluster>({
            id: "power-plant-pings",
            mode: "ping",
            data: plantPings,
            getPosition: (d) => d.position,
            getRadius: (d) => plantRadius(d.capacity_mw) * scale * 3.4,
            radiusUnits: "pixels",
            getFillColor: (d) => [...PLANT_COLOR[d.group], 255],
            // thermal pulses quicken with the fossil share; storage keeps a slow beat
            getGlow: (d) => [d.group === "fossil" ? 0.12 + 0.3 * pingLevel : 0.1, 0.4, 0, 0],
            time,
            parameters: SCREEN_BLEND,
            updateTriggers: { getGlow: pingLevel, getRadius: scale },
          }),
        );
      }
    }

    const billboard = (id: string, data: Particle[], flat = false) =>
      new ScatterplotLayer<Particle>({
        id,
        data,
        billboard: !flat,
        stroked: false,
        radiusUnits: "meters",
        getPosition: (p) => p.position,
        getRadius: (p) => p.radius,
        getFillColor: (p) => p.color,
        updateTriggers: { getPosition: phase, getRadius: phase, getFillColor: phase },
      });

    // open site → a real-scale object fitted to its footprint, realistic material.
    // being in real metres, it grows as you zoom in (no vanishing) and sits on the
    // actual parcel. its animation is generated at real scale too.
    let selObject: Layer | null = null;
    const selFx: Layer[] = [];
    if (footMeta) {
      const gzc = groundZ.current.get(selectedId ?? "") ?? 0;
      const S = footMeta.span * 0.7;
      selObject = new SimpleMeshLayer<number>({
        id: "sel-object",
        data: [0],
        mesh: OBJECT_MESH[footMeta.tech] as never,
        getPosition: () => [footMeta.center[0], footMeta.center[1], gzc],
        getScale: () => [S, S, REAL_HZ[footMeta.tech]],
        getColor: REAL_COLOR[footMeta.tech],
        material: { ambient: 0.5, diffuse: 0.65, shininess: 26 },
        updateTriggers: { getPosition: [footMeta.center[0], footMeta.center[1], gzc], getScale: S },
      });
      const sel = selectedSite;
      if (closeUp && sel) {
        const c = { ...sel, lon: footMeta.center[0], lat: footMeta.center[1] };
        const gzf = () => gzc;
        const t = footMeta.tech;
        if (t === "solar") selFx.push(billboard("sel-glint", glint([c], phase, () => footMeta.span, gzf)));
        else if (t === "storage")
          selFx.push(billboard("sel-pulse", pulseFx([c], phase, () => footMeta.span, gzf, [167, 139, 250]), true));
        else if (STACK_H[t]) {
          const P = {
            combustion: { baseFactor: 1, height: 1.2, spread: 0.28, color: [120, 120, 128] as [number, number, number], count: 16 },
            biomass: { baseFactor: 1, height: 1.1, spread: 0.25, color: [160, 162, 168] as [number, number, number], count: 12 },
            geothermal: { baseFactor: 1, height: 1.2, spread: 0.3, color: [226, 233, 240] as [number, number, number], count: 14 },
            hydro: { baseFactor: 0.3, height: 0.9, spread: 0.7, color: [228, 238, 245] as [number, number, number], count: 18 },
          }[t]!;
          selFx.push(billboard("sel-plume", plume([c], phase, () => STACK_H[t]!, gzf, P)));
        }
      }
    }

    // field animations for the other near sites (screen-sized objects)
    const fx: Layer[] = [];
    if (closeUp) {
      const mpp = (156543.03 * Math.cos((GERMANY_VIEW.latitude * Math.PI) / 180)) / 2 ** viewZoom;
      const size = (cap: number) => (9 + Math.min(15, Math.sqrt(Math.max(cap, 1))) * 1.9) * mpp;
      const gz = (s: Site) => groundZ.current.get(s.id) ?? 0;
      const at = (t: Technology) => byTech.get(t) ?? [];
      const puffs: Particle[] = [
        ...plume(at("combustion"), phase, size, gz, { baseFactor: 0.62, height: 1.4, spread: 0.18, color: [120, 120, 128], count: 11 }),
        ...plume(at("biomass"), phase, size, gz, { baseFactor: 0.46, height: 1.0, spread: 0.15, color: [160, 162, 168], count: 8 }),
        ...plume(at("geothermal"), phase, size, gz, { baseFactor: 0.42, height: 1.1, spread: 0.22, color: [226, 233, 240], count: 10 }),
        ...plume(at("hydro"), phase, size, gz, { baseFactor: 0.1, height: 0.7, spread: 0.5, color: [228, 238, 245], count: 16 }),
      ];
      const glints = glint(at("solar"), phase, size, gz);
      const pulses = pulseFx(at("storage"), phase, size, gz, [167, 139, 250]);
      if (pulses.length) fx.push(billboard("fx-pulse", pulses, true));
      if (puffs.length) fx.push(billboard("fx-plumes", puffs));
      if (glints.length) fx.push(billboard("fx-glint", glints));
    }

    overlayRef.current.setProps({
      layers: [
        ...infraStatic,
        ...plantLayers,
        ...gridStatic,
        ...gridLayers,
        ...infraLayers,
        ...(plantBubbles ? [plantBubbles] : []),
        ...infraNodeLayers,
        ...objectLayers,
        ...(selObject ? [selObject] : []),
        ...(towers ? [towers, rotors!] : []),
        ...selFx,
        ...fx,
        ...(ring ? [ring] : []),
      ],
    });
  }, [infraStatic, infraNodeLayers, infraFlowData, infrastructure, infraGas, infraRail, railSceneActive, gridStatic, gridFlowData, gridLatest, exchange, plantBubbles, objectLayers, aggregated, phase, selectedId, sites, footprint, footMeta, turbines, groundTick, closeUp, byTech, viewZoom, gridBackbone, gridPlanned, gridExchangeFlows, gridVoltages, grid, planned, plantArc, exchangeLines, powerSceneActive, plantData, plantPings, plantFeederData, activity, selectedSite, onSelect, onGridSelect]);

  // 3D fly-to a selected site — a gentle approach; the footprint effect below
  // then frames the site's true extent (so a big wind farm isn't flown into the
  // base of one turbine)
  useEffect(() => {
    if (!mapRef.current || !flyTo) return;
    mapRef.current.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: 12.5,
      pitch: 58,
      bearing: -18,
      duration: 1600,
      essential: true,
    });
  }, [flyTo]);

  // frame the open site to its footprint extent — adaptive, so small solar sites
  // fill the view and large wind farms show every turbine
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !footprint) return;
    let minX = 180;
    let minY = 90;
    let maxX = -180;
    let maxY = -90;
    for (const poly of footprint.geom.coordinates)
      for (const ring of poly)
        for (const [x, y] of ring) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
    const cam = map.cameraForBounds(
      [
        [minX, minY],
        [maxX, maxY],
      ],
      { padding: 90, maxZoom: 16 },
    );
    if (!cam?.center) return;
    map.flyTo({
      center: cam.center,
      zoom: Math.min((cam.zoom ?? 14) - 0.3, 15.5),
      pitch: 62,
      bearing: -17,
      duration: 1500,
      essential: true,
    });
  }, [footprint]);

  return <div ref={container} className="absolute inset-0" />;
}
