import type { PickingInfo } from "@deck.gl/core";
import { ColumnLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { RecentDetection, Site } from "../lib/api";
import { mw } from "../lib/format";
import {
  BASEMAP_STYLE,
  GERMANY_VIEW,
  STATE_COLOR,
  STATE_LABEL,
  TECH_COLOR,
  type RGB,
} from "../lib/theme";

export type ColorMode = "state" | "technology";

interface Props {
  sites: Site[];
  colorMode: ColorMode;
  recent: RecentDetection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  focusBounds: [[number, number], [number, number]] | null;
  flyTo: { lon: number; lat: number } | null;
}

const DIM: RGB = [60, 70, 90];

function colorOf(s: Site, mode: ColorMode): [number, number, number, number] {
  const c =
    mode === "state"
      ? STATE_COLOR[s.status] ?? DIM
      : (s.technology && TECH_COLOR[s.technology]) || DIM;
  const alpha = mode === "state" && s.status === "unknown" ? 150 : 230;
  return [c[0], c[1], c[2], alpha];
}

// height compresses a 5–1060 MW range so large plants read big but don't dwarf the rest
const elevation = (s: Site) => Math.sqrt(s.capacity_mw) * 1100;

export default function MapView({
  sites,
  colorMode,
  recent,
  selectedId,
  onSelect,
  focusBounds,
  flyTo,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [phase, setPhase] = useState(0);

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
      attributionControl: false,
    });
    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
      getTooltip: (info: PickingInfo) => {
        const o = info.object as Site | undefined;
        if (!o) return null;
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
    let t0 = performance.now();
    const loop = (t: number) => {
      setPhase(((t - t0) % 2200) / 2200);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const columns = useMemo(
    () =>
      new ColumnLayer<Site>({
        id: "sites",
        data: sites,
        diskResolution: 6,
        radius: 1300,
        extruded: true,
        pickable: true,
        elevationScale: 1,
        radiusUnits: "meters",
        getPosition: (s) => [s.lon, s.lat],
        getElevation: elevation,
        getFillColor: (s) => colorOf(s, colorMode),
        onClick: (info: PickingInfo) => {
          const o = info.object as Site | undefined;
          if (o) onSelect(o.id);
        },
        updateTriggers: { getFillColor: colorMode },
        material: { ambient: 0.6, diffuse: 0.5, shininess: 32 },
      }),
    [sites, colorMode, onSelect],
  );

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
    const ring = selected
      ? new ScatterplotLayer<Site>({
          id: "selected",
          data: [selected],
          getPosition: (s) => [s.lon, s.lat],
          getRadius: 2600,
          radiusUnits: "meters",
          stroked: true,
          filled: false,
          getLineColor: [255, 255, 255, 230],
          lineWidthMinPixels: 2,
        })
      : null;
    overlayRef.current.setProps({ layers: [columns, pulse, ...(ring ? [ring] : [])] });
  }, [columns, recent, phase, selectedId, sites]);

  // fly to a query/agent result (fit the set)
  useEffect(() => {
    if (!mapRef.current || !focusBounds) return;
    mapRef.current.fitBounds(focusBounds, { padding: 120, pitch: GERMANY_VIEW.pitch, duration: 1400 });
  }, [focusBounds]);

  // 3D fly-to a single selected site — camera drops in close
  useEffect(() => {
    if (!mapRef.current || !flyTo) return;
    mapRef.current.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: 14.5,
      pitch: 62,
      bearing: -18,
      duration: 2200,
      essential: true,
    });
  }, [flyTo]);

  return <div ref={container} className="absolute inset-0" />;
}
