import type { FeatureCollection, Geometry } from "geojson";

import type { GridPick } from "./grid";

export type InfraSourceKey = "rail" | "gas" | "ports" | "airports" | "industry" | "boundaries" | "energy";
export type InfraPathKind = "rail" | "gas_pipeline" | "rail_bridge" | "rail_tunnel";
export type InfraNodeKind =
  | "rail_station"
  | "rail_crossing"
  | "port"
  | "airport"
  | "gas_storage"
  | "lng_terminal"
  | "gas_border"
  | "gas_compressor"
  | "gas_consumer"
  | "gas_production"
  | "gas_powerplant"
  | "industry";
export type InfraValue = string | number | boolean | null;

export interface InfraSource {
  name: string;
  url: string;
  published: string;
  coverage: string;
  caveat: string;
}

export interface InfrastructureManifest {
  generated_at: string;
  counts: Record<string, number>;
  sources: Record<InfraSourceKey, InfraSource>;
  hydrogen_context: {
    name: string;
    url: string;
    approved_length_km: number;
    conversion_share_percent: number;
    target_year: number;
    investment_eur_billion: number;
    map_note: string;
  };
}

export interface InfraPath {
  featureType: "path";
  kind: InfraPathKind;
  name: string;
  path: [number, number][];
  timestamps: number[];
  sourceKey: InfraSourceKey;
  properties: Record<string, InfraValue>;
}

export interface InfraNode {
  featureType: "node";
  kind: InfraNodeKind;
  name: string;
  position: [number, number];
  sourceKey: InfraSourceKey;
  properties: Record<string, InfraValue>;
}

export type InfraItem = InfraPath | InfraNode;
export type InfraPick = { kind: "infrastructure"; item: InfraItem; manifest: InfrastructureManifest };
export type MapFeaturePick = GridPick | InfraPick;

export interface InfrastructureData {
  rail: InfraPath[];
  railStructures: InfraPath[];
  gas: InfraPath[];
  nodes: InfraNode[];
  states: FeatureCollection<Geometry, Record<string, InfraValue>>;
  manifest: InfrastructureManifest;
  maxTime: number;
}

interface RawFeatureCollection {
  features: Array<{
    geometry: { type: string; coordinates: unknown } | null;
    properties: Record<string, InfraValue>;
  }>;
}

const M_LAT = 111_320;
const mLon = (lat: number) => M_LAT * Math.cos((lat * Math.PI) / 180);

function hashOffset(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  return hash % 180_000;
}

function timedPath(path: [number, number][], name: string): { timestamps: number[]; end: number } {
  let distance = hashOffset(name);
  const timestamps = [distance];
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    const lat = (a[1] + b[1]) / 2;
    distance += Math.hypot((b[0] - a[0]) * mLon(lat), (b[1] - a[1]) * M_LAT);
    timestamps.push(distance);
  }
  return { timestamps, end: distance };
}

function pathKind(value: InfraValue): InfraPathKind {
  if (value === "gas_pipeline") return "gas_pipeline";
  if (value === "rail_bridge") return "rail_bridge";
  if (value === "rail_tunnel") return "rail_tunnel";
  return "rail";
}

function sourceFor(kind: InfraPathKind | InfraNodeKind | "state_boundary"): InfraSourceKey {
  if (kind === "gas_pipeline" || kind.startsWith("gas_") || kind === "lng_terminal") return "gas";
  if (kind === "port") return "ports";
  if (kind === "airport") return "airports";
  if (kind === "industry") return "industry";
  if (kind === "state_boundary") return "boundaries";
  return "rail";
}

function linesFromGeometry(geometry: { type: string; coordinates: unknown }): [number, number][][] {
  if (geometry.type === "LineString") return [geometry.coordinates as [number, number][]];
  if (geometry.type === "MultiLineString") return geometry.coordinates as [number, number][][];
  return [];
}

function readPaths(fc: RawFeatureCollection): { rows: InfraPath[]; maxTime: number } {
  const rows: InfraPath[] = [];
  let maxTime = 0;
  for (const feature of fc.features) {
    if (!feature.geometry) continue;
    const kind = pathKind(feature.properties.kind);
    for (const path of linesFromGeometry(feature.geometry)) {
      if (!path || path.length < 2) continue;
      const name = String(feature.properties.name || (kind === "gas_pipeline" ? "Gas pipeline" : "Rail route"));
      const timed = timedPath(path, `${kind}-${name}-${rows.length}`);
      maxTime = Math.max(maxTime, timed.end);
      rows.push({
        featureType: "path",
        kind,
        name,
        path,
        timestamps: timed.timestamps,
        sourceKey: sourceFor(kind),
        properties: feature.properties,
      });
    }
  }
  return { rows, maxTime };
}

function readNodes(fc: RawFeatureCollection): InfraNode[] {
  const valid = new Set<InfraNodeKind>([
    "rail_station",
    "rail_crossing",
    "port",
    "airport",
    "gas_storage",
    "lng_terminal",
    "gas_border",
    "gas_compressor",
    "gas_consumer",
    "gas_production",
    "gas_powerplant",
    "industry",
  ]);
  const rows: InfraNode[] = [];
  for (const feature of fc.features) {
    if (!feature.geometry || feature.geometry.type !== "Point") continue;
    const kind = String(feature.properties.kind) as InfraNodeKind;
    if (!valid.has(kind)) continue;
    rows.push({
      featureType: "node",
      kind,
      name: String(feature.properties.name || kind.replaceAll("_", " ")),
      position: feature.geometry.coordinates as [number, number],
      sourceKey: sourceFor(kind),
      properties: feature.properties,
    });
  }
  return rows;
}

let cache: Promise<InfrastructureData> | null = null;

export function loadInfrastructure(): Promise<InfrastructureData> {
  if (cache) return cache;
  cache = Promise.all([
    fetch("/data/rail_network.geojson").then((r) => r.json() as Promise<RawFeatureCollection>),
    fetch("/data/rail_structures.geojson").then((r) => r.json() as Promise<RawFeatureCollection>),
    fetch("/data/gas_network.geojson").then((r) => r.json() as Promise<RawFeatureCollection>),
    fetch("/data/infrastructure_nodes.geojson").then((r) => r.json() as Promise<RawFeatureCollection>),
    fetch("/data/state_boundaries.geojson").then(
      (r) => r.json() as Promise<FeatureCollection<Geometry, Record<string, InfraValue>>>,
    ),
    fetch("/data/infrastructure_manifest.json").then((r) => r.json() as Promise<InfrastructureManifest>),
  ]).then(([railFc, railStructureFc, gasFc, nodeFc, states, manifest]) => {
    const rail = readPaths(railFc);
    const railStructures = readPaths(railStructureFc);
    const gas = readPaths(gasFc);
    return {
      rail: rail.rows,
      railStructures: railStructures.rows,
      gas: gas.rows,
      nodes: readNodes(nodeFc),
      states,
      manifest,
      maxTime: Math.max(rail.maxTime, railStructures.maxTime, gas.maxTime),
    };
  });
  return cache;
}

export const INFRA_COLOR: Record<InfraNodeKind | InfraPathKind | "state_boundary", [number, number, number]> = {
  state_boundary: [92, 112, 138],
  rail: [126, 220, 238],
  rail_station: [226, 242, 255],
  rail_crossing: [170, 185, 202],
  rail_bridge: [255, 226, 130],
  rail_tunnel: [218, 126, 244],
  gas_pipeline: [244, 176, 70],
  gas_storage: [173, 139, 246],
  lng_terminal: [45, 212, 191],
  gas_border: [244, 145, 74],
  gas_compressor: [255, 208, 120],
  gas_consumer: [246, 167, 94],
  gas_production: [255, 224, 146],
  gas_powerplant: [238, 118, 104],
  port: [60, 190, 232],
  airport: [158, 201, 255],
  industry: [240, 105, 92],
};

export const INDUSTRY_COLOR: Record<string, [number, number, number]> = {
  ENERGY: [240, 105, 92],
  METALS: [163, 177, 198],
  MINERALS: [226, 201, 105],
  CHEMICALS: [70, 210, 191],
  "PAPER AND WOOD": [112, 208, 139],
};
