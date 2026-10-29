// The Maps view: the place in up to six maps, one theme each (docs/VISUALIZATION.md #2), one camera
// for all. Each map is a full map of its own (MapLibre's land, labels and grid tiles; deck.gl's
// layers from map/build.ts, so a dataset looks the same here as on the main map), with its
// datasets, each in its style (the same menu as the main map), its key and its sources. A country's
// dashboard opens here. Calm: no motion; the maps redraw when the camera or the data change.

import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { shapeOf } from "../app/areaShape";
import { ensure, useDataStore } from "../app/data";
import { CATEGORIES, DATASETS, DATASET_BY_ID, covers, datasetsOn, layersOfDatasets, partsIn } from "../app/datasets";
import { defaultMaps, panelOf, type MapPanel, type Style } from "../app/maps";
import { actions, currentCamera, layersOf, useApp } from "../app/store";
import type { CountriesFile, WorldFile } from "../app/types";
import { km2Text } from "../lib/area";
import { useRasterCache } from "../lib/rasterCache";
import { buildLayers, labelsOf, type Frame } from "../map/build";
import { wantedKeys } from "../map/MapCanvas";
import { STYLE } from "../map/style";
import { hexInfoKey, useHexInfo } from "../map/hexLayers";
import { applyStyles, is3D, styleOf, stylesOf, useStyleInfo } from "../map/styleLayers";
import { tileSync } from "../map/tiles";
import { tooltip } from "../map/tooltip";
import { LayerLegend } from "./LayersPanel";
import { BivariateKey, StyleKey, StyleSelect, StyleText } from "./StyleControls";
import { AgentPanelKey } from "./AskTab";
import { is3DOverlay, panelAgentDraws, useAgent } from "../app/agent";

const muted = "text-[#8d94a1]";
/** The main map's style, flat, with the country names only. */
const PANEL_STYLE: maplibregl.StyleSpecification = {
  ...STYLE,
  projection: { type: "mercator" },
  sky: undefined,
  layers: STYLE.layers.filter((l) => !l.id.startsWith("label-") || l.id === "label-names"),
};

type Camera = { center: [number, number]; zoom: number; pitch: number; bearing: number };

/** Open the Maps view: its maps, else one map per dataset on, else the area's themes. */
export function openMaps() {
  const s = useApp.getState();
  if (s.maps.length) return actions.setCompare(true);
  const on = datasetsOn(s.layers, s.colour).filter((d) => !d.colour);
  const maps: MapPanel[] = on.length ? on.slice(0, 6).map((d) => panelOf(d.id, styleOf(s.mapStyles, d.id) ?? stylesOf(d.id)[0] ?? "lines")) : defaultMaps(s.area);
  actions.setMaps(maps);
  actions.setCompare(true);
}

/** The top bar's switch between one map and the Maps view. */
export function MapsButton() {
  const compare = useApp((s) => s.compare);
  const n = useApp((s) => s.maps.length);
  return (
    <button
      onClick={() => (compare ? actions.setCompare(false) : openMaps())}
      className={`shrink-0 rounded-lg border px-2.5 py-1.5 text-[12px] ${compare ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 bg-[#0b0f16]/90 text-slate-200 hover:bg-white/[0.08]"}`}
      title="The place in several maps, one theme each, one camera (six at most)"
    >
      {compare ? "One map" : n ? `Maps (${n})` : "Maps"}
    </button>
  );
}

export function MapsView() {
  const compare = useApp((s) => s.compare);
  if (!compare) return null;
  return <Maps />;
}

function Maps() {
  const maps = useApp((s) => s.maps);
  const area = useApp((s) => s.area);
  const drawn = useApp((s) => s.drawn);
  const files = useDataStore((s) => s.files);
  const shape = shapeOf(area, drawn, files.world as WorldFile | undefined, files.countries as CountriesFile | undefined);
  // one camera: the map being moved leads, the others follow
  const peers = useRef(new Set<maplibregl.Map>());
  const leader = useRef<maplibregl.Map | null>(null);
  const camera = useRef<Camera | null>(null);
  useEffect(() => {
    ensure("world");
    ensure("countries");
    // a country's dashboard opened by a link: its themes (app/maps.ts)
    const s = useApp.getState();
    if (!s.maps.length) useApp.setState({ maps: defaultMaps(s.area) });
  }, []);
  const n = Math.max(1, maps.length);
  const cols = n <= 1 ? 1 : n <= 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  return (
    <div className="absolute bottom-14 left-[290px] right-[396px] top-16 z-[15] flex flex-col overflow-hidden rounded-xl border border-white/10 bg-[#05070b]">
      <div className="flex shrink-0 items-center gap-2 border-b border-white/[0.07] px-2.5 py-1.5">
        <span className="text-[11.5px] font-medium text-slate-100">{maps.length} {maps.length === 1 ? "map" : "maps"}</span>
        <span className={`truncate text-[10.5px] ${muted}`}>{shape ? `${shape.label} · ${km2Text(shape.km2)} · ` : ""}one camera for all; each map keeps to the area</span>
        <span className="flex-1" />
        <AddMap area={area} count={maps.length} />
        <button onClick={() => actions.setCompare(false)} className="rounded-md border border-white/10 bg-[#0b0f16]/95 px-2 py-0.5 text-[11px] text-slate-200 hover:bg-white/[0.08]">
          Back to one map
        </button>
      </div>
      {maps.length === 0 ? (
        <div className={`m-auto max-w-sm text-center text-[11.5px] ${muted}`}>No maps yet. Add one above, or switch on a dataset in the Layers panel and choose “As a new map”.</div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-px bg-white/[0.06]" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))` }}>
          {maps.map((m, i) => (
            <PanelMap key={i} index={i} panel={m} peers={peers.current} leader={leader} camera={camera} count={maps.length} />
          ))}
        </div>
      )}
    </div>
  );
}

/** "+ Add a map": the datasets with data in the area. */
function AddMap({ area, count }: { area: string[] | null; count: number }) {
  const mode = useApp((s) => s.mode);
  const options = useMemo(() => DATASETS.filter((d) => !d.colour && partsIn(d, mode).some((p) => p.layer) && covers(d, area)), [mode, area]);
  return (
    <select
      value=""
      onChange={(e) => {
        const id = e.target.value;
        if (id) actions.addMap(panelOf(id, styleOf({}, id) ?? stylesOf(id)[0] ?? "lines"));
      }}
      className="max-w-[180px] rounded-md border border-white/10 bg-[#0b0f16] px-1.5 py-0.5 text-[11px] text-slate-200"
      title={count >= 6 ? "Six maps at most: the oldest goes" : "A map of its own for a dataset"}
    >
      <option value="">+ Add a map{count >= 6 ? " (replaces the oldest)" : ""}</option>
      {CATEGORIES.map((c) => {
        const ds = options.filter((d) => d.category === c);
        return ds.length ? (
          <optgroup key={c} label={c}>
            {ds.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </optgroup>
        ) : null;
      })}
    </select>
  );
}

function PanelMap({
  index,
  panel,
  peers,
  leader,
  camera,
  count,
}: {
  index: number;
  panel: MapPanel;
  peers: Set<maplibregl.Map>;
  leader: React.MutableRefObject<maplibregl.Map | null>;
  camera: React.MutableRefObject<Camera | null>;
  count: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const draw = useRef<() => void>(() => {});
  const panelRef = useRef(panel);
  panelRef.current = panel;
  const scope = `map${index}`;

  useEffect(() => {
    if (!box.current) return;
    const map = new maplibregl.Map({
      container: box.current,
      style: PANEL_STYLE,
      center: [10, 50],
      zoom: 4,
      attributionControl: false,
      renderWorldCopies: false,
      fadeDuration: 0,
      maxPitch: 70,
      pixelRatio: Math.min(window.devicePixelRatio, 2),
    });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    mapRef.current = map;
    peers.add(map);
    const overlay = new MapboxOverlay({ interleaved: true, layers: [], getTooltip: tooltip as never });
    map.addControl(overlay as unknown as maplibregl.IControl);
    const syncTiles = tileSync(map);
    let lastLabels: unknown = null;
    let queued = false;

    // the first camera: the one in use, else the area, else the main map's
    const start = () => {
      if (camera.current) return map.jumpTo(camera.current);
      const s = useApp.getState();
      const shape = shapeOf(s.area, s.drawn, useDataStore.getState().files.world as WorldFile | undefined, useDataStore.getState().files.countries as CountriesFile | undefined);
      if (shape && shape.bbox[2] - shape.bbox[0] < 180) {
        map.fitBounds(
          [
            [shape.bbox[0], shape.bbox[1]],
            [shape.bbox[2], shape.bbox[3]],
          ],
          { padding: 18, duration: 0 },
        );
      } else {
        const c = currentCamera();
        map.jumpTo({ center: c?.center ?? [10, 50], zoom: Math.max(2.5, (c?.zoom ?? 4) - 0.8) });
      }
    };

    draw.current = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        if (!map.getLayer("world-land")) return;
        const s = useApp.getState();
        const files = useDataStore.getState().files;
        const p = panelRef.current;
        const ids = p.items.map((x) => x.dataset);
        const own = layersOf(layersOfDatasets(ids));
        const styles = Object.fromEntries(p.items.map((x) => [x.dataset, x.style])) as Record<string, Style>;
        const { layers, styled } = applyStyles(own, styles);
        const zoom = map.getZoom();
        for (const k of wantedKeys(zoom, own)) ensure(k);
        if (s.area || s.drawn) ensure("world");
        syncTiles(layers, s.area, s.drawn);
        const b = map.getBounds();
        const c = map.getCenter();
        const frame: Frame = {
          mode: s.mode === "day" ? "live" : s.mode,
          layers,
          styled,
          scope,
          agent: p.agent ? panelAgentDraws(p.agent.mapId, p.agent.panel) : undefined,
          bounds: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
          colour: "none",
          plantStatus: s.plantStatus,
          plantStyle: s.plantStyle,
          connectSide: s.connectSide,
          waterIndicator: s.waterIndicator,
          mastrTech: s.mastrTech,
          selection: s.selection,
          area: s.area,
          coverageOf: null,
          drawn: s.drawn,
          drawing: null,
          files,
          zoom,
          centre: [c.lng, c.lat],
          camKey: `${Math.round(c.lng / 3)},${Math.round(c.lat / 3)}`,
          clock: { phase: 0, spacing: 72 },
          day: null,
          daySlot: 0,
          yearK: s.yearK,
          isMobile: false,
          wind: null,
          sunAlt: 0,
          now: performance.now(),
          dayRegion: s.dayRegion,
          sun: null,
          night: null,
        };
        overlay.setProps({ layers: buildLayers(frame) });
        const labels = labelsOf();
        if (labels !== lastLabels) {
          const src = map.getSource("labels") as maplibregl.GeoJSONSource | undefined;
          if (src) {
            src.setData(labels as unknown as GeoJSON.FeatureCollection);
            lastLabels = labels;
          }
        }
      });
    };

    map.once("style.load", () => {
      start();
      draw.current();
    });
    // one camera: the map a gesture starts on leads; the others jump with it
    map.on("movestart", (e) => {
      if ((e as { originalEvent?: unknown }).originalEvent) leader.current = map;
    });
    map.on("move", () => {
      draw.current();
      if (leader.current !== map) return;
      const c = map.getCenter();
      const cam: Camera = { center: [c.lng, c.lat], zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() };
      camera.current = cam;
      for (const other of peers) if (other !== map) other.jumpTo(cam);
    });
    map.on("moveend", () => {
      if (leader.current === map) leader.current = null;
      const c = map.getCenter();
      camera.current = { center: [c.lng, c.lat], zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() };
    });
    const unsubData = useDataStore.subscribe(() => draw.current());
    const unsubApp = useApp.subscribe((s, prev) => {
      if (s.maps !== prev.maps || s.area !== prev.area || s.drawn !== prev.drawn || s.selection !== prev.selection) draw.current();
    });
    const unsubRaster = useRasterCache.subscribe(() => draw.current());
    const unsubAgent = useAgent.subscribe(() => draw.current());
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      unsubData();
      unsubApp();
      unsubRaster();
      unsubAgent();
      peers.delete(map);
      if (leader.current === map) leader.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // a style or a dataset changed: draw again; a 3D style leans every map
  useEffect(() => {
    draw.current();
    const map = mapRef.current;
    const agent3D = panel.agent ? panelAgentDraws(panel.agent.mapId, panel.agent.panel).some((d) => is3DOverlay(d.overlay)) : false;
    if (map && (panel.items.some((x) => is3D(x.style)) || agent3D) && map.getPitch() < 5) {
      const c = map.getCenter();
      const cam: Camera = { center: [c.lng, c.lat], zoom: map.getZoom(), pitch: 50, bearing: map.getBearing() };
      camera.current = cam;
      for (const m of peers) m.jumpTo(cam);
    }
  }, [panel, peers, camera]);

  const setItems = (items: MapPanel["items"]) => {
    const maps = useApp.getState().maps;
    actions.setMaps(maps.map((m, i) => (i === index ? { ...m, items } : m)));
  };
  const hexes = panel.items.filter((x) => x.style === "hex").map((x) => x.dataset);
  return (
    <div className="relative min-h-0 min-w-0 overflow-hidden">
      <div ref={box} className="absolute inset-0" />
      <PanelKey
        index={index}
        panel={panel}
        scope={scope}
        hexes={hexes}
        onStyle={(d, st) => setItems(panel.items.map((x) => (x.dataset === d ? { ...x, style: st } : x)))}
        onRemoveItem={(d) => setItems(panel.items.filter((x) => x.dataset !== d))}
        onReplace={(from, to) => setItems(panel.items.map((x) => (x.dataset === from ? { dataset: to, style: x.style } : x)))}
      />
      {count > 1 && (
        <button
          onClick={() => actions.setMaps(useApp.getState().maps.filter((_, i) => i !== index))}
          className="absolute right-1.5 top-1.5 rounded-md border border-white/10 bg-[#0b0f16]/90 px-1.5 text-[11px] text-slate-400 hover:text-slate-100"
          title="Remove this map"
        >
          ✕
        </button>
      )}
    </div>
  );
}

/** Where a dataset has no placed record in the area, a dataset that may: suggested on its map. */
const INSTEAD: Record<string, { dataset: string; text: string }> = {
  emitters: { dataset: "ctrace", text: "Show modelled emissions (Climate TRACE) here" },
};

/** A map's key: small, at its top left. Its title; each dataset with its style and a one-line key;
 *  the explanation, the layers' own keys and the sources on request. */
function PanelKey({
  index,
  panel,
  scope,
  hexes,
  onStyle,
  onRemoveItem,
  onReplace,
}: {
  index: number;
  panel: MapPanel;
  scope: string;
  hexes: string[];
  onStyle: (dataset: string, st: Style) => void;
  onRemoveItem: (dataset: string) => void;
  onReplace: (from: string, to: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const sources = [...new Set(panel.items.flatMap((x) => DATASET_BY_ID.get(x.dataset)?.parts.map((p) => p.source) ?? []))];
  const mode = useApp((s) => s.mode);
  return (
    <div className="absolute left-1.5 top-1.5 max-h-[calc(100%-40px)] w-[min(240px,calc(100%-44px))] overflow-y-auto rounded-md border border-white/[0.08] bg-[#0b0f16]/85 px-2 py-1">
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] tabular-nums text-slate-500">{index + 1}</span>
        <span className="flex-1 truncate text-[11px] font-medium text-slate-100">{panel.title}</span>
        <button onClick={() => setOpen(!open)} className={`text-[10px] ${open ? "text-sky-200" : "text-slate-500 hover:text-slate-200"}`} aria-expanded={open} title="What the map shows and its sources">
          {open ? "less" : "about"}
        </button>
      </div>
      <div className="mt-0.5 space-y-1">
        {panel.agent && <AgentPanelKey mapId={panel.agent.mapId} panel={panel.agent.panel} compact />}
        {panel.items.map((x) => {
          const d = DATASET_BY_ID.get(x.dataset);
          const own = !stylesOf(x.dataset).length || x.style === "points" || x.style === "raster" || x.style === "lines";
          return (
            <div key={x.dataset}>
              <div className="flex items-center gap-1 text-[10px] text-slate-300">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: d?.color ?? "#999" }} />
                <span className="min-w-0 flex-1 truncate">{d?.name ?? x.dataset}</span>
                <StyleSelect dataset={x.dataset} value={x.style} onChange={(st) => onStyle(x.dataset, st)} />
                {panel.items.length > 1 && (
                  <button onClick={() => onRemoveItem(x.dataset)} className="text-[10px] text-slate-500 hover:text-slate-200" title="Take off this map">
                    ✕
                  </button>
                )}
              </div>
              {!(hexes.length === 2 && hexes.includes(x.dataset)) && <StyleKey scope={scope} dataset={x.dataset} style={x.style} compact />}
              <Instead scope={scope} dataset={x.dataset} style={x.style} onReplace={onReplace} />
              {open && (
                <div className={`mt-0.5 text-[9.5px] leading-snug ${muted}`}>
                  <StyleText dataset={x.dataset} style={x.style} />
                  {own && d && (
                    <div className="mt-0.5 space-y-1">
                      {partsIn(d, mode)
                        .filter((p) => p.layer)
                        .map((p) => (
                          <LayerLegend key={p.layer} id={p.layer!} />
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {hexes.length === 2 && <BivariateKey scope={scope} a={hexes[0]} b={hexes[1]} compact />}
      </div>
      <div className={`mt-0.5 border-t border-white/[0.06] pt-0.5 text-[9px] leading-snug ${muted} ${open ? "" : "truncate"}`} title={sources.join("; ")}>
        Source: {sources.join("; ")}
      </div>
    </div>
  );
}

/** A dataset with no placed record here: a dataset that has some, one click away. */
function Instead({ scope, dataset, style, onReplace }: { scope: string; dataset: string; style: Style; onReplace: (from: string, to: string) => void }) {
  const info = useStyleInfo((s) => s[`${scope}:${dataset}`]);
  const hex = useHexInfo((s) => s[hexInfoKey(scope, [dataset])]);
  const alt = INSTEAD[dataset];
  const empty = style === "hex" ? hex && !hex.total : info && !info.total && style !== "points";
  if (!alt || !empty) return null;
  return (
    <button onClick={() => onReplace(dataset, alt.dataset)} className="mt-0.5 rounded border border-white/10 px-1.5 text-[9.5px] text-sky-200 hover:bg-white/[0.07]">
      {alt.text}
    </button>
  );
}
