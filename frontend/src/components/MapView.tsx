import type { Layer, PickingInfo } from "@deck.gl/core";
import { TripsLayer } from "@deck.gl/geo-layers";
import { ColumnLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { SimpleMeshLayer } from "@deck.gl/mesh-layers";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Footprint, RecentDetection, Site, Turbine } from "../lib/api";
import { OBJECT_MESH, REAL_COLOR, REAL_HZ, STACK_H } from "../lib/energyObjects";
import { glint, plume, pulse as pulseFx, type Particle } from "../lib/effects";
import { loadGrid, voltColor, type GridData } from "../lib/grid";
import { mw } from "../lib/format";
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
  recent: RecentDetection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  focusBounds: [[number, number], [number, number]] | null;
  flyTo: { lon: number; lat: number } | null;
  footprint: Footprint | null;
  turbines: Turbine[];
  basemap: "dark" | "satellite";
  showGrid: boolean;
}

const TURBINE_COLOR: [number, number, number] = [226, 232, 240]; // light grey, like real towers

const DIM: RGB = [60, 70, 90];
const EMPTY_FC = { type: "FeatureCollection", features: [] };

function colorOf(s: Site, mode: ColorMode): [number, number, number, number] {
  const ds = displayState(s.status, s.mastr_status);
  const c =
    mode === "state" ? STATE_COLOR[ds] ?? DIM : (s.technology && TECH_COLOR[s.technology]) || DIM;
  const alpha = mode === "state" && ds === "unknown" ? 150 : 230;
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
  basemap,
  showGrid,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [grid, setGrid] = useState<GridData | null>(null);
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

  // lazy-load the transmission grid GeoJSON once it's first switched on
  useEffect(() => {
    if (showGrid && !grid) loadGrid("/grid_transmission.geojson").then(setGrid).catch(() => {});
  }, [showGrid, grid]);

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
  // far ⇆ near crossfade: spikes fade out and 3D objects fade in across this band
  const objOpacity = Math.max(0, Math.min(1, (viewZoom - 8.6) / 0.8));
  const objectLayers = useMemo<Layer[]>(() => {
    if (objOpacity <= 0) return [];
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
  }, [byTech, colorMode, closeUp, spinPhase, onSelect, groundTick, viewZoom, objOpacity]);

  // far/overview tier: every plant as a thin, tech-coloured capacity spike (height
  // scaled to the screen so the field reads cleanly at any altitude, rebase-style)
  const spikeOpacity = Math.max(0, Math.min(1, (9.4 - viewZoom) / 0.8));
  const spikes = useMemo<Layer | null>(() => {
    if (spikeOpacity <= 0) return null;
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
    const mpp = (156543.03 * Math.cos((GERMANY_VIEW.latitude * Math.PI) / 180)) / 2 ** viewZoom;
    return new ColumnLayer<Site>({
      id: "spikes",
      data: inView,
      diskResolution: 6,
      radius: mpp * 0.5, // ~1px needle — thin so thousands stay clean
      radiusUnits: "meters",
      extruded: true,
      pickable: true,
      opacity: spikeOpacity,
      getPosition: (s) => [s.lon, s.lat],
      getElevation: (s) => mpp * (8 + Math.min(46, Math.sqrt(Math.max(s.capacity_mw, 1)) * 6.5)),
      getFillColor: (s) => colorOf(s, colorMode),
      onClick: (info: PickingInfo) => {
        const o = info.object as Site | undefined;
        if (o) onSelect(o.id);
      },
      updateTriggers: { getFillColor: colorMode, getElevation: viewZoom, getRadius: viewZoom },
      material: false, // unlit → pure, bright tech colour like the reference
    });
  }, [sites, bounds, selectedId, viewZoom, colorMode, spikeOpacity, onSelect]);

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

    // transmission grid: dim backbone + flowing energy trails + glowing substations
    const gridLayers: Layer[] = [];
    if (showGrid && grid) {
      const t = (performance.now() * 0.16) % (grid.maxTime + 40000);
      gridLayers.push(
        new PathLayer<(typeof grid.lines)[number]>({
          id: "grid-base",
          data: grid.lines,
          getPath: (d) => d.path,
          getColor: (d) => {
            const c = voltColor(d.voltage);
            return [c[0], c[1], c[2], 60];
          },
          getWidth: (d) => (d.voltage >= 380000 ? 2.4 : 1.4),
          widthUnits: "pixels",
          widthMinPixels: 1,
          capRounded: true,
          jointRounded: true,
        }),
        new TripsLayer<(typeof grid.lines)[number]>({
          id: "grid-flow",
          data: grid.lines,
          getPath: (d) => d.path,
          getTimestamps: (d) => d.timestamps,
          getColor: (d) => voltColor(d.voltage),
          currentTime: t,
          trailLength: 16000,
          fadeTrail: true,
          widthUnits: "pixels",
          getWidth: (d) => (d.voltage >= 380000 ? 3 : 2),
          widthMinPixels: 1.5,
          capRounded: true,
          jointRounded: true,
          updateTriggers: { currentTime: t },
        }),
        new ScatterplotLayer<(typeof grid.subs)[number]>({
          id: "grid-subs",
          data: grid.subs,
          getPosition: (d) => d.position,
          getRadius: (d) => (d.voltage >= 380000 ? 3.2 : 2.2),
          radiusUnits: "pixels",
          radiusMinPixels: 1.5,
          radiusMaxPixels: 6,
          getFillColor: (d) => {
            const c = voltColor(d.voltage);
            return [c[0], c[1], c[2], Math.round(120 + 90 * (0.5 + 0.5 * Math.sin(phase * 6.28)))];
          },
          stroked: false,
          updateTriggers: { getFillColor: phase },
        }),
      );
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
      const sel = sites.find((s) => s.id === selectedId);
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
        ...gridLayers,
        ...(spikes ? [spikes] : []),
        ...objectLayers,
        ...(selObject ? [selObject] : []),
        ...(towers ? [towers, rotors!] : []),
        ...selFx,
        ...fx,
        pulse,
        ...(ring ? [ring] : []),
      ],
    });
  }, [spikes, objectLayers, aggregated, recent, phase, selectedId, sites, footprint, footMeta, turbines, groundTick, closeUp, byTech, viewZoom, showGrid, grid]);

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
