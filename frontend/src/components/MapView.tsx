import type { Layer, PickingInfo } from "@deck.gl/core";
import { HexagonLayer } from "@deck.gl/aggregation-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { SimpleMeshLayer } from "@deck.gl/mesh-layers";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Footprint, RecentDetection, Site, Turbine } from "../lib/api";
import { OBJECT_MESH, objectSize } from "../lib/energyObjects";
import { mw } from "../lib/format";
import { ROTOR_MESH, TOWER_MESH } from "../lib/turbineMesh";
import {
  BASEMAP_STYLE,
  GERMANY_VIEW,
  HEX_RANGE,
  SITE_ZOOM,
  STATE_COLOR,
  STATE_LABEL,
  TECH_COLOR,
  TERRAIN_TILES,
  type RGB,
  type Technology,
} from "../lib/theme";

const CLOSE_ZOOM = 11; // above this, animate (spin rotors) — bounded instance count

export type ColorMode = "state" | "technology";

interface Props {
  sites: Site[];
  colorMode: ColorMode;
  recent: RecentDetection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  focusBounds: [[number, number], [number, number]] | null;
  flyTo: { lon: number; lat: number } | null;
  footprint: Footprint | null;
  turbines: Turbine[];
}

const TURBINE_COLOR: [number, number, number] = [226, 232, 240]; // light grey, like real towers

const DIM: RGB = [60, 70, 90];
const EMPTY_FC = { type: "FeatureCollection", features: [] };

function colorOf(s: Site, mode: ColorMode): [number, number, number, number] {
  const c =
    mode === "state"
      ? STATE_COLOR[s.status] ?? DIM
      : (s.technology && TECH_COLOR[s.technology]) || DIM;
  const alpha = mode === "state" && s.status === "unknown" ? 150 : 230;
  return [c[0], c[1], c[2], alpha];
}

export default function MapView({
  sites,
  colorMode,
  recent,
  selectedId,
  onSelect,
  focusBounds,
  flyTo,
  footprint,
  turbines,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const groundZ = useRef<Map<string, number>>(new Map());
  const [phase, setPhase] = useState(0);
  const [groundTick, setGroundTick] = useState(0);
  const [closeUp, setCloseUp] = useState(GERMANY_VIEW.zoom >= CLOSE_ZOOM);
  // only the regime (density field vs. individual sites) is React state, flipped
  // once when zoom crosses SITE_ZOOM — not on every zoom tick, so panning/zooming
  // never triggers a React re-render or layer rebuild.
  const [aggregated, setAggregated] = useState(GERMANY_VIEW.zoom < SITE_ZOOM);

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
          "fill-extrusion-opacity": 0.5,
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
    });
    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
      getTooltip: (info: PickingInfo) => {
        const o = info.object as Site | undefined;
        if (!o?.name) return null;
        return {
          html: `<b>${o.name}</b><br/>${mw(o.capacity_mw)} · ${o.technology ?? "—"}<br/>${
            STATE_LABEL[o.status]
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

  // national zoom: extruded capacity-density field (reads as a heat terrain)
  const hexes = useMemo(
    () =>
      new HexagonLayer<Site>({
        id: "hex",
        data: sites,
        visible: aggregated,
        radius: 9000,
        coverage: 0.86,
        extruded: true,
        pickable: false,
        elevationScale: 26,
        elevationRange: [0, 1600],
        getPosition: (s) => [s.lon, s.lat],
        getElevationWeight: (s) => s.capacity_mw,
        elevationAggregation: "SUM",
        getColorWeight: (s) => s.capacity_mw,
        colorAggregation: "SUM",
        colorRange: HEX_RANGE as unknown as [number, number, number][],
        material: { ambient: 0.64, diffuse: 0.6, shininess: 28, specularColor: [40, 60, 80] },
      }),
    [sites, aggregated],
  );

  // site zoom: every site is its own 3D object by technology. group by tech and
  // drop the open site (it gets detailed geometry — footprint + real turbines).
  const byTech = useMemo(() => {
    const m = new Map<Technology, Site[]>();
    for (const s of sites) {
      if (!s.technology || s.id === selectedId) continue;
      const arr = m.get(s.technology);
      if (arr) arr.push(s);
      else m.set(s.technology, [s]);
    }
    return m;
  }, [sites, selectedId]);

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
      // wind: the turbines are the model, so the footprint is just a thin ground
      // pad marking the farm extent. everything else: the footprint IS the volume.
      const height = footprint.technology === "wind" ? 4 : 32;
      src.setData({
        type: "Feature",
        geometry: { type: "MultiPolygon", coordinates: footprint.geom.coordinates },
        properties: { color: `rgb(${c[0]},${c[1]},${c[2]})`, height },
      } as never);
    };
    if (map.getSource("footprint")) apply();
    else map.once("load", apply);
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

  // one instanced 3D-object layer per technology, over every visible site
  const objectLayers = useMemo<Layer[]>(() => {
    if (aggregated) return [];
    const click = (info: PickingInfo) => {
      const o = info.object as Site | undefined;
      if (o) onSelect(o.id);
    };
    const gz = (s: Site) => groundZ.current.get(s.id) ?? 0;
    const layers: Layer[] = [];
    for (const [tech, rows] of byTech) {
      if (tech === "wind") {
        // tower height = 0.55·size; rotor sits at the top
        layers.push(
          new SimpleMeshLayer<Site>({
            id: "obj-wind-tower",
            data: rows,
            mesh: TOWER_MESH as never,
            getPosition: (s) => [s.lon, s.lat, gz(s)],
            getScale: (s) => {
              const B = objectSize(s.capacity_mw);
              const r = Math.max(20, B * 0.04);
              return [r, r, B * 0.55];
            },
            getColor: (s) => colorOf(s, colorMode),
            pickable: true,
            onClick: click,
            updateTriggers: { getColor: colorMode },
            material: { ambient: 0.55, diffuse: 0.6, shininess: 36 },
          }),
        );
        layers.push(
          new SimpleMeshLayer<Site>({
            id: "obj-wind-rotor",
            data: rows,
            mesh: ROTOR_MESH as never,
            getPosition: (s) => [s.lon, s.lat, gz(s) + objectSize(s.capacity_mw) * 0.55],
            getScale: (s) => {
              const r = objectSize(s.capacity_mw) * 0.3;
              return [r, r, r];
            },
            getColor: (s) => colorOf(s, colorMode),
            getOrientation: closeUp
              ? (s: Site) => [phase * 720 + ((s.lat * 9973) % 360), 0, 0]
              : [0, 0, 0],
            pickable: true,
            onClick: click,
            updateTriggers: { getColor: colorMode, getOrientation: closeUp ? phase : 0 },
            material: { ambient: 0.55, diffuse: 0.6, shininess: 36 },
          }),
        );
      } else {
        // proportions are baked into the mesh; scale uniformly by size
        layers.push(
          new SimpleMeshLayer<Site>({
            id: `obj-${tech}`,
            data: rows,
            mesh: OBJECT_MESH[tech] as never,
            getPosition: (s) => [s.lon, s.lat, gz(s)],
            getScale: (s) => {
              const B = objectSize(s.capacity_mw);
              return [B, B, B];
            },
            getColor: (s) => colorOf(s, colorMode),
            pickable: true,
            onClick: click,
            updateTriggers: { getColor: colorMode },
            material: { ambient: 0.55, diffuse: 0.55, shininess: 28 },
          }),
        );
      }
    }
    return layers;
  }, [byTech, aggregated, colorMode, closeUp, phase, onSelect, groundTick]);

  useEffect(() => {
    if (!overlayRef.current) return;
    const pulseR = 1500 + phase * 9000;
    const pulse = new ScatterplotLayer<RecentDetection>({
      id: "pulse",
      data: recent,
      getPosition: (d) => [d.site.lon, d.site.lat],
      getRadius: pulseR,
      radiusUnits: "meters",
      stroked: true,
      filled: false,
      getLineColor: [56, 189, 248, Math.round(180 * (1 - phase))],
      lineWidthMinPixels: 1.5,
    });
    const selected = sites.find((s) => s.id === selectedId);
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

    overlayRef.current.setProps({
      layers: [
        hexes,
        ...objectLayers,
        ...(towers ? [towers, rotors!] : []),
        pulse,
        ...(ring ? [ring] : []),
      ],
    });
  }, [hexes, objectLayers, aggregated, recent, phase, selectedId, sites, footprint, turbines, groundTick]);

  // fly to a query/agent result (fit the set)
  useEffect(() => {
    if (!mapRef.current || !focusBounds) return;
    mapRef.current.fitBounds(focusBounds, { padding: 120, pitch: GERMANY_VIEW.pitch, duration: 1400 });
  }, [focusBounds]);

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
