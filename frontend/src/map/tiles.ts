// MapLibre's tiles for what is switched on: the world and US grid lines, the predicted grid,
// Global Renewables Watch, protected areas, flood depth, roads and rail, the resource atlases;
// each kept to the dashboard's area. One per map (the main map and each of the Maps view's maps).

import type maplibregl from "maplibre-gl";

import { shapeOf } from "../app/areaShape";
import { ensure, fileOf } from "../app/data";
import type { LayerId } from "../app/store";
import type { CountriesFile, WorldFile } from "../app/types";
import type { AreaSpec } from "../lib/area";
import { ATLAS_LAYERS, type AtlasFile, type AtlasId } from "../lib/atlas";
import type { ConstraintsFile, ProtectedFile } from "../lib/constraints";
import {
  FLOOD_LAYERS,
  GRID_LAYERS,
  GRW_LAYERS,
  PREDICTED_LAYERS,
  PROTECTED_LAYERS,
  ROADS_LAYERS,
  US_GRID_LAYERS,
  addAtlasLayer,
  addFloodLayers,
  addGridLayers,
  addGrwLayers,
  addProtectedLayers,
  addRoadsLayers,
  setAreaWithin,
  setWorldGridOutside,
} from "./style";

/** A map's tile sync: call it each frame; it changes the map only when something it uses changed. */
export function tileSync(map: maplibregl.Map) {
  let gridKey = "";
  let atlasKey = "";
  let consKey = "";
  let areaFilterKey = "";
  return (L: Record<LayerId, boolean>, area: string[] | null, drawn: AreaSpec | null) => {
    if (!map.getLayer("world-land")) return;
    const countriesFile = fileOf<CountriesFile>("countries");
    const worldFile = fileOf<WorldFile>("world");
    const gk = `${L.gridWorld}|${L.predicted}|${L.gridUS}|${L.gridEU}|${!!countriesFile}|${!!worldFile}`;
    if (gk !== gridKey) {
      gridKey = gk;
      if (L.gridWorld) addGridLayers(map, "hv");
      if (L.gridWorld) {
        // one line per place: Europe's grid and the US lines where they are on
        const inside: number[][][][] = [];
        if (L.gridEU && countriesFile)
          for (const c of countriesFile.countries) for (const rings of c.polygons) inside.push(rings.map((r) => Array.from({ length: r.length / 2 }, (_, i) => [r[2 * i], r[2 * i + 1]])));
        if (L.gridUS) {
          if (!worldFile) ensure("world");
          const us = worldFile?.features.find((f) => f.properties.iso3 === "USA");
          if (us) inside.push(...(us.geometry.coordinates as number[][][][]));
        }
        setWorldGridOutside(map, inside);
      }
      if (L.predicted) addGridLayers(map, "predicted");
      if (L.gridUS) addGridLayers(map, "us");
      for (const id of US_GRID_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", L.gridUS ? "visible" : "none");
      for (const id of GRID_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", L.gridWorld ? "visible" : "none");
      for (const id of PREDICTED_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", L.predicted ? "visible" : "none");
    }
    // a dashboard's area: the map's own line layers keep to it (map/style.ts)
    const areaShape = shapeOf(area, drawn, worldFile, countriesFile);
    const afk = `${areaShape && areaShape.km2 <= 3_000_000 ? areaShape.key : ""}|${gk}|${!!map.getLayer("roads-major")}|${!!map.getLayer("protected-line")}|${!!map.getLayer("grw-wind")}`;
    if (afk !== areaFilterKey) {
      areaFilterKey = afk;
      const polys = areaShape && areaShape.km2 <= 3_000_000 ? areaShape.polygons.map((p) => p.map((r) => Array.from({ length: r.length / 2 }, (_, i) => [r[2 * i], r[2 * i + 1]]))) : null;
      setAreaWithin(map, polys);
    }
    // Global Renewables Watch (vector tiles)
    if (L.grw) addGrwLayers(map);
    for (const id of GRW_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", L.grw ? "visible" : "none");
    // what stops a build: protected areas, flood depth, roads and rail (scripts/build_constraints.py)
    const cons = fileOf<ConstraintsFile>("constraints");
    const prot = fileOf<ProtectedFile>("protected");
    const ck = `${L.protectedAreas}|${L.flood}|${L.roadsRail}|${!!cons}|${!!prot}`;
    if (ck !== consKey) {
      consKey = ck;
      if (L.protectedAreas && prot) addProtectedLayers(map, prot.tiles);
      if (L.flood && cons) addFloodLayers(map, cons.flood.maps, cons.flood.source);
      if (L.roadsRail && cons) addRoadsLayers(map, cons.roads.tiles);
      for (const [ids, on] of [
        [PROTECTED_LAYERS, L.protectedAreas],
        [FLOOD_LAYERS, L.flood],
        [ROADS_LAYERS, L.roadsRail],
      ] as const)
        for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    }
    // the resource atlases (raster tiles), once their description has loaded
    const atlas = fileOf<AtlasFile>("atlas");
    const ak = `${L.solarResource}|${L.windResource}|${!!atlas}`;
    if (ak !== atlasKey && atlas) {
      atlasKey = ak;
      for (const [k, on] of [
        ["pvout", L.solarResource],
        ["wind", L.windResource],
      ] as [AtlasId, boolean][]) {
        const id = ATLAS_LAYERS[k];
        if (on) addAtlasLayer(map, id, atlas[k].tiles, atlas[k].max_zoom, atlas[k].source);
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      }
    }
  };
}
