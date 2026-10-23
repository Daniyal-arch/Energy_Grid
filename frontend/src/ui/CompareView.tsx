// Side by side: the same place in small maps, one variable each (small multiples), one camera for
// all. Each map: the countries, the high-voltage grid as thin context, the area's outline and the
// variable summed into hexagons (map/hexLayers.ts), with its title, key and source. Calm: no tiles,
// no motion.

import { Deck, MapView, WebMercatorViewport, type Layer, type MapViewState } from "@deck.gl/core";
import { ColumnLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { useEffect, useMemo, useRef, useState } from "react";

import { shapeOf } from "../app/areaShape";
import { useDataStore } from "../app/data";
import { actions, currentCamera, useApp } from "../app/store";
import type { CountriesFile, GridFile, WorldFile } from "../app/types";
import { inside, km2Text } from "../lib/area";
import type { Measure } from "../lib/measures";
import { rgbCss, type RGB } from "../lib/theme";
import { binPoints, hexKm, pickable, type Hex } from "../map/hexLayers";

const muted = "text-[#8d94a1]";
type Ring = [number, number][];
const pairs = (flat: number[]): Ring => Array.from({ length: flat.length / 2 }, (_, i) => [flat[2 * i], flat[2 * i + 1]]);

export function CompareView() {
  const compare = useApp((s) => s.compare);
  if (!compare) return null;
  return <Compare />;
}

function Compare() {
  const layers = useApp((s) => s.layers);
  const area = useApp((s) => s.area);
  const drawn = useApp((s) => s.drawn);
  const files = useDataStore((s) => s.files);
  const panels = useApp((s) => s.panels);
  const styles = useApp((s) => s.mapStyles);
  const avail = pickable(layers);
  const chosen = panels.map((id) => avail.find((m) => m.id === id)).filter((m): m is Measure => !!m);
  const vars = (chosen.length ? chosen : avail).slice(0, 6);
  const box = useRef<HTMLDivElement>(null);
  const deck = useRef<Deck | null>(null);
  const [size, setSize] = useState<[number, number]>([0, 0]);
  const [vs, setVs] = useState<MapViewState | null>(null);
  const world = files.world as WorldFile | undefined;
  const countries = files.countries as CountriesFile | undefined;
  const shape = shapeOf(area, drawn, world, countries);

  const n = Math.max(1, vars.length);
  const cols = n <= 2 ? n : n <= 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  const w = size[0] / cols;
  const h = size[1] / rows;

  // the container's size
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize([el.clientWidth, el.clientHeight]));
    ro.observe(el);
    setSize([el.clientWidth, el.clientHeight]);
    return () => ro.disconnect();
  }, []);

  // the first camera: the area in one panel, else the main map's
  useEffect(() => {
    if (vs || !w || !h) return;
    if (shape) {
      const [x0, y0, x1, y1] = shape.bbox[2] - shape.bbox[0] > 180 ? [-125, 24, -66, 50] : shape.bbox;
      const fit = new WebMercatorViewport({ width: w, height: h }).fitBounds(
        [
          [x0, y0],
          [x1, y1],
        ],
        { padding: 24 },
      );
      setVs({ longitude: fit.longitude, latitude: fit.latitude, zoom: fit.zoom, pitch: 0, bearing: 0 });
    } else {
      const c = currentCamera();
      setVs({ longitude: c?.center[0] ?? 10, latitude: c?.center[1] ?? 50, zoom: Math.max(3, (c?.zoom ?? 4) - 0.6), pitch: 0, bearing: 0 });
    }
  }, [vs, w, h, shape]);

  const rKm = hexKm(vs?.zoom ?? 5);
  const lat0 = Math.round((vs?.latitude ?? 50) / 5) * 5;
  const keep = useMemo(() => (shape && shape.km2 <= 3_000_000 ? (lon: number, lat: number) => inside(shape, lon, lat) : null), [shape]);
  // each variable's hexagons (rebuilt when the hexagon size or the grid's latitude changes)
  const hexes = useMemo(
    () =>
      vars.map((m) => {
        const pts = m.points(files);
        const all = pts ? [...binPoints(pts, rKm, lat0, keep).values()] : [];
        return { m, all, max: Math.max(1e-9, ...all.map((x) => x.v)) };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [vars.map((m) => m.id).join(), rKm, lat0, keep, ...vars.flatMap((m) => m.files.map((k) => files[k]))],
  );

  const base = useMemo(() => {
    const out: Layer[] = [];
    if (world)
      out.push(
        new SolidPolygonLayer<{ polygon: Ring[] }>({
          id: "base:land",
          data: world.features.flatMap((f) => f.geometry.coordinates.map((p) => ({ polygon: p as Ring[] }))),
          getPolygon: (d) => d.polygon,
          getFillColor: [24, 28, 36, 255],
        }),
      );
    if (countries)
      out.push(
        new PathLayer<Ring>({
          id: "base:borders",
          data: countries.countries.flatMap((c) => c.polygons.map((p) => pairs(p[0]))),
          getPath: (d) => d,
          getColor: [120, 128, 142, 110],
          getWidth: 0.6,
          widthUnits: "pixels",
        }),
      );
    const grid = files.grid as GridFile | undefined;
    if (grid)
      out.push(
        new PathLayer<[number, number[]]>({
          id: "base:grid",
          data: grid.lines,
          getPath: (l) => pairs(l[1]),
          getColor: [150, 158, 172, 70],
          getWidth: 0.6,
          widthUnits: "pixels",
        }),
      );
    if (shape)
      out.push(
        new PathLayer<Ring>({
          id: "base:area",
          data: shape.polygons.filter((_, k) => shape.boxes[k][2] - shape.boxes[k][0] < 180).map((p) => pairs(p[0])),
          getPath: (d) => d,
          getColor: [255, 246, 230, 200],
          getWidth: 1.2,
          widthUnits: "pixels",
        }),
      );
    return out;
  }, [world, countries, files.grid, shape]);

  const variable = useMemo(
    () =>
      hexes.map(({ m, all, max }, i) => {
        const colour = (x: Hex) => ((m.types && m.types[x.top]) ?? m.color) as RGB;
        const share = (x: Hex) => Math.sqrt(Math.min(1, x.v / max));
        const style = styles[m.id] ?? "hex";
        if (style === "bubbles")
          return new ScatterplotLayer<Hex>({
            id: `v${i}:hex`,
            data: [...all].sort((p, q) => q.v - p.v),
            getPosition: (x) => x.centre,
            radiusUnits: "pixels",
            getRadius: (x) => 2 + 16 * share(x),
            getFillColor: (x) => [...colour(x), 190],
            stroked: true,
            getLineColor: [8, 10, 14, 220],
            lineWidthUnits: "pixels",
            getLineWidth: 0.8,
            pickable: true,
          });
        if (style === "columns")
          return new ColumnLayer<Hex>({
            id: `v${i}:hex`,
            data: all,
            getPosition: (x) => x.centre,
            diskResolution: 6,
            radius: rKm * 1000 * 0.86,
            extruded: true,
            getElevation: (x) => share(x) * rKm * 1000 * 9,
            getFillColor: (x) => [...colour(x), 230],
            pickable: true,
          });
        return new SolidPolygonLayer<Hex>({
          id: `v${i}:hex`,
          data: all,
          getPolygon: (x) => x.polygon,
          getFillColor: (x) => [...colour(x), Math.round(45 + 190 * share(x))],
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 50],
        });
      }),
    [hexes, styles, rKm],
  );

  // one deck.gl canvas, one view per variable
  useEffect(() => {
    if (!box.current || !vs || !w) return;
    const views = vars.map((_, i) => new MapView({ id: `v${i}`, x: (i % cols) * w, y: Math.floor(i / cols) * h, width: w, height: h, controller: true }));
    const viewState = Object.fromEntries(views.map((v) => [v.id, vs]));
    const props = {
      views,
      viewState,
      layers: [...base, ...variable],
      layerFilter: ({ layer, viewport }: { layer: Layer; viewport: { id: string } }) => layer.id.startsWith("base:") || layer.id.startsWith(`${viewport.id}:`),
      onViewStateChange: ({ viewState: v }: { viewState: MapViewState }) => setVs({ ...v, pitch: 0, bearing: 0 }),
      getTooltip: ({ object, layer }: { object?: Hex; layer?: Layer | null }) => {
        if (!object || !layer) return null;
        const k = Number(layer.id.slice(1, layer.id.indexOf(":")));
        const m = vars[k];
        if (!m) return null;
        const types = object.types.slice(0, 3).map(([t, v]) => `<div>${t}: <b>${m.fmt(v)}</b></div>`).join("");
        return {
          html: `<b>${m.label}: ${m.fmt(object.v)}</b>${types}<div style="color:#8d94a1;font-size:10px;margin-top:3px">sum over a hexagon of about ${rKm * 2} km (computed)</div>`,
          style: { background: "rgba(11,15,22,0.95)", color: "#e2e8f0", fontSize: "11px", borderRadius: "8px", padding: "6px 8px", border: "1px solid rgba(255,255,255,0.1)" },
        };
      },
    };
    if (!deck.current) deck.current = new Deck({ parent: box.current, width: "100%", height: "100%", ...props } as never);
    else deck.current.setProps(props as never);
  }, [vs, w, h, cols, base, variable, vars.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(
    () => () => {
      deck.current?.finalize();
      deck.current = null;
    },
    [],
  );

  return (
    <div className="absolute bottom-14 left-[290px] right-[396px] top-16 z-[15] overflow-hidden rounded-xl border border-white/10 bg-[#05070b]">
      <div ref={box} className="absolute inset-0" />
      {/* titles, keys and sources over each map */}
      {hexes.map(({ m, max }, i) => (
        <div
          key={m.id}
          className="pointer-events-none absolute p-2"
          style={{ left: (i % cols) * w, top: Math.floor(i / cols) * h, width: w, height: h, boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.06)" }}
        >
          <PanelKey m={m} max={max} rKm={rKm} />
          {vars.length > 1 && (
            <button
              onClick={() => actions.setPanels(vars.filter((x) => x.id !== m.id).map((x) => x.id))}
              className="pointer-events-auto absolute right-2 top-2 rounded-md border border-white/10 bg-[#0b0f16]/90 px-1.5 text-[11px] text-slate-400 hover:text-slate-100"
              title="Remove this map"
            >
              ✕
            </button>
          )}
        </div>
      ))}
      <div className="absolute right-2 top-2 flex items-center gap-2">
        <span className={`rounded-md bg-[#0b0f16]/90 px-2 py-1 text-[10.5px] ${muted}`}>
          {shape ? `${shape.label} · ${km2Text(shape.km2)} · ` : ""}one camera for all · hexagons of about {rKm * 2} km
        </span>
        <button onClick={() => actions.setCompare(false)} className="rounded-md border border-white/10 bg-[#0b0f16]/95 px-2 py-1 text-[11px] text-slate-200 hover:bg-white/[0.08]">
          Back to one map
        </button>
      </div>
      {vars.length < 2 && (
        <div className="absolute inset-x-0 bottom-3 mx-auto w-fit rounded-md bg-[#0b0f16]/95 px-3 py-1.5 text-[11px] text-slate-300">
          Switch on more datasets with figures (plants, registers, emitters, EV charging, data centres) to compare them here.
        </div>
      )}
    </div>
  );
}

function PanelKey({ m, max, rKm }: { m: Measure; max: number; rKm: number }) {
  const c = rgbCss(m.color);
  return (
    <div className="w-fit max-w-[90%] rounded-md bg-[#0b0f16]/85 px-2 py-1.5">
      <div className="flex items-center gap-1.5 text-[12px] text-slate-100">
        <span className="h-2 w-2 rounded-full" style={{ background: c }} />
        {m.label}
      </div>
      <div className="mt-1 h-1.5 w-28 rounded-sm" style={{ background: `linear-gradient(90deg, ${c.replace("rgb(", "rgba(").replace(")", ",0.18)")}, ${c})` }} />
      <div className={`mt-0.5 flex w-28 justify-between text-[9px] ${muted}`}>
        <span>0</span>
        <span>{m.fmt(max)}</span>
      </div>
      <div className={`mt-0.5 max-w-[260px] text-[9px] leading-snug ${muted}`}>Per hexagon of about {rKm * 2} km: {m.sums}.</div>
    </div>
  );
}
