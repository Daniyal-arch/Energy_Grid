import { PathStyleExtension, type PathStyleExtensionProps } from "@deck.gl/extensions";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { CometPathLayer } from "../lib/cometLayer";
import { FlowClock, curvedPath, flowDistances } from "../lib/flowLayers";
import { rgbCss, type RGB } from "../lib/theme";

// Europe's transmission grid, power plants and measured cross-border flows (?europe).
// Static layers: frontend/public/data/eu/{grid,plants,countries}.json from
// scripts/build_eu_grid.py; flows.json from scripts/fetch_eu_flows.py (a snapshot).
// Only cross-border arcs move: they carry measured physical flows. Lines inside a
// country stay still because no public per-line flow data exists.

interface GridFile {
  lines: [number, number[]][];
  links: [number, number[]][];
}
interface PlantsFile {
  groups: string[];
  plants: [number, number, number, number][];
}
interface CountriesFile {
  land: number[][][];
  borders: number[][];
  coast: number[][];
}
interface FlowRow {
  a: string;
  b: string;
  mw: number;
  ts: string;
}
interface FlowsFile {
  source: string;
  fetched: string;
  borders: FlowRow[];
}
interface Arc {
  from: string;
  to: string;
  mw: number;
  path: [number, number][];
  timestamps: number[];
}

const SEA = "#06070a";
const LAND: RGB = [19, 18, 18];
const COAST: [number, number, number, number] = [84, 76, 68, 150];
const BORDER: [number, number, number, number] = [120, 106, 92, 85];
const HVDC: RGB = [178, 146, 255];
const FLOW: RGB = [120, 214, 255];

// copper by voltage: the highest level is brightest
const VOLTAGE_BANDS: Array<{ min: number; label: string; color: RGB; width: number; alpha: number }> = [
  { min: 380, label: "380–750 kV", color: [236, 178, 120], width: 0.9, alpha: 170 },
  { min: 275, label: "275–330 kV", color: [196, 122, 76], width: 0.75, alpha: 130 },
  { min: 0, label: "220–254 kV", color: [140, 84, 58], width: 0.6, alpha: 110 },
];
const band = (kv: number) => VOLTAGE_BANDS.find((b) => kv >= b.min)!;

const PLANT_COLOR: Record<string, RGB> = {
  nuclear: [255, 96, 150],
  coal: [150, 138, 126],
  gas: [255, 128, 72],
  hydro: [84, 156, 255],
  wind: [72, 222, 184],
  solar: [255, 214, 72],
  bio: [150, 196, 92],
  storage: [190, 190, 210],
  other: [168, 146, 210],
};
const PLANT_LABEL: Record<string, string> = {
  nuclear: "Nuclear",
  coal: "Coal & lignite",
  gas: "Gas & oil",
  hydro: "Hydro",
  wind: "Wind",
  solar: "Solar",
  bio: "Bioenergy & waste",
  storage: "Storage",
  other: "Other",
};

// where each country's flow arcs start and end (inland points, not capitals)
const ANCHOR: Record<string, [number, number]> = {
  AL: [20.0, 41.1],
  AT: [14.3, 47.6],
  BA: [17.8, 44.2],
  BE: [4.6, 50.6],
  BG: [25.2, 42.7],
  CH: [8.2, 46.8],
  CZ: [15.3, 49.8],
  DE: [10.4, 51.1],
  DK: [9.3, 56.0],
  EE: [25.5, 58.7],
  ES: [-3.7, 40.3],
  FI: [26.0, 62.5],
  FR: [2.4, 46.6],
  GB: [-1.8, 52.8],
  GR: [22.0, 39.5],
  HR: [15.9, 45.6],
  HU: [19.4, 47.2],
  IE: [-8.0, 53.2],
  IT: [12.3, 43.0],
  LT: [23.9, 55.3],
  LU: [6.1, 49.7],
  LV: [24.9, 56.9],
  ME: [19.3, 42.8],
  MD: [28.5, 47.2],
  MK: [21.7, 41.6],
  NL: [5.6, 52.2],
  NO: [9.5, 61.0],
  PL: [19.2, 52.0],
  PT: [-8.1, 39.6],
  RO: [24.9, 45.9],
  RS: [20.8, 44.1],
  SE: [15.8, 61.0],
  SI: [14.8, 46.1],
  SK: [19.5, 48.7],
  UA: [31.0, 49.0],
  XK: [20.9, 42.6],
};

const EUROPE: [[number, number], [number, number]] = [
  [-11, 35.5],
  [32, 70],
];
const BLANK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": SEA } }],
};
const IDLE_MW = 20;

const pairs = (flat: number[]): [number, number][] => {
  const p: [number, number][] = [];
  for (let k = 0; k < flat.length; k += 2) p.push([flat[k], flat[k + 1]]);
  return p;
};
const gw = (mw: number) => `${(Math.abs(mw) / 1000).toFixed(1)} GW`;

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

export default function EuropeView() {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [grid, setGrid] = useState<GridFile | null>(null);
  const [plants, setPlants] = useState<PlantsFile | null>(null);
  const [countries, setCountries] = useState<CountriesFile | null>(null);
  const [flows, setFlows] = useState<FlowsFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState(0);
  const clock = useRef(new FlowClock());

  useEffect(() => {
    Promise.all([
      getJson<GridFile>("/data/eu/grid.json").then(setGrid),
      getJson<PlantsFile>("/data/eu/plants.json").then(setPlants),
      getJson<CountriesFile>("/data/eu/countries.json").then(setCountries),
    ]).catch((e) => setError(String(e)));
    // flows are optional: without a snapshot the grid still renders, just still
    getJson<FlowsFile>("/data/eu/flows.json").then(setFlows).catch(() => {});
  }, []);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BLANK_STYLE,
      bounds: EUROPE,
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      renderWorldCopies: false,
    });
    const o = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(o);
    overlay.current = o;
    mapRef.current = map;
    return () => map.remove();
  }, []);

  const lineBands = useMemo(() => {
    if (!grid) return [];
    return VOLTAGE_BANDS.map((b) => ({
      ...b,
      paths: grid.lines.filter(([kv]) => band(kv) === b).map(([, flat]) => pairs(flat)),
    })).reverse(); // low voltage first, 380+ on top
  }, [grid]);
  const links = useMemo(() => (grid ? grid.links.map(([mw, flat]) => ({ mw, path: pairs(flat) })) : []), [grid]);
  const land = useMemo(() => (countries ? countries.land.map((rings) => rings.map(pairs)) : []), [countries]);

  const arcs = useMemo<Arc[]>(() => {
    if (!flows) return [];
    const out: Arc[] = [];
    for (const f of flows.borders) {
      if (Math.abs(f.mw) < IDLE_MW) continue;
      const [from, to] = f.mw > 0 ? [f.a, f.b] : [f.b, f.a];
      if (!ANCHOR[from] || !ANCHOR[to]) continue;
      const path = curvedPath(ANCHOR[from], ANCHOR[to], 0.16, 40);
      out.push({ from, to, mw: Math.abs(f.mw), path, timestamps: flowDistances(path, false, out.length * 91_000) });
    }
    return out.sort((x, y) => x.mw - y.mw);
  }, [flows]);
  const topFlows = useMemo(() => [...arcs].sort((x, y) => y.mw - x.mw).slice(0, 6), [arcs]);

  // one clock for the comets; only the uniforms change per frame
  useEffect(() => {
    let raf = 0;
    const loop = (now: number) => {
      clock.current.tick(now, mapRef.current?.getZoom() ?? 4, 34);
      setFrame((n) => n + 1);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    const zoom = mapRef.current?.getZoom() ?? 4;
    const flow = clock.current.uniforms(zoom, 110);
    const noDepth = { depthCompare: "always", depthWriteEnabled: false } as const;
    overlay.current?.setProps({
      layers: [
        new SolidPolygonLayer<[number, number][][]>({
          id: "eu-land",
          data: land,
          getPolygon: (d) => d,
          getFillColor: [...LAND, 255],
          parameters: noDepth,
        }),
        new PathLayer<number[]>({
          id: "eu-coast",
          data: countries?.coast ?? [],
          getPath: (d) => pairs(d),
          getColor: COAST,
          getWidth: 0.6,
          widthUnits: "pixels",
          parameters: noDepth,
        }),
        new PathLayer<number[], PathStyleExtensionProps<number[]>>({
          id: "eu-borders",
          data: countries?.borders ?? [],
          getPath: (d) => pairs(d),
          getColor: BORDER,
          getWidth: 0.6,
          widthUnits: "pixels",
          getDashArray: [3, 3],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          parameters: noDepth,
        }),
        new ScatterplotLayer<[number, number, number, number]>({
          id: "eu-plants",
          data: plants?.plants ?? [],
          getPosition: (p) => [p[2], p[3]],
          getRadius: (p) => Math.min(4, 0.7 + Math.sqrt(p[1]) * 0.065),
          radiusUnits: "pixels",
          getFillColor: (p) => [...PLANT_COLOR[plants!.groups[p[0]]], 115],
          stroked: false,
          parameters: noDepth,
        }),
        ...lineBands.flatMap((b) => [
          new PathLayer<[number, number][]>({
            id: `eu-grid-glow-${b.min}`,
            data: b.paths,
            getPath: (d) => d,
            getColor: [...b.color, 14],
            getWidth: b.width * 4,
            widthUnits: "pixels",
            parameters: noDepth,
          }),
          new PathLayer<[number, number][]>({
            id: `eu-grid-${b.min}`,
            data: b.paths,
            getPath: (d) => d,
            getColor: [...b.color, b.alpha],
            getWidth: b.width,
            widthUnits: "pixels",
            parameters: noDepth,
          }),
        ]),
        new PathLayer<{ mw: number; path: [number, number][] }, PathStyleExtensionProps>({
          id: "eu-hvdc",
          data: links,
          getPath: (d) => d.path,
          getColor: [...HVDC, 210],
          getWidth: 1,
          widthUnits: "pixels",
          getDashArray: [4, 3],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          parameters: noDepth,
        }),
        new CometPathLayer<Arc>({
          id: "eu-flows",
          data: arcs,
          getPath: (d) => d.path,
          getTimestamps: (d) => d.timestamps,
          getColor: [...FLOW, 255],
          getWidth: (d) => 14 + Math.min(10, d.mw / 300),
          getCometStyle: (d) => [1.1, 2.2 + Math.min(2.6, d.mw / 1000), Math.min(1, 0.55 + d.mw / 2500)],
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          phase: flow.phase,
          spacing: flow.spacing,
          tailPx: 110,
          lineAlpha: 0.3,
          parameters: {
            depthCompare: "always",
            depthWriteEnabled: false,
            blend: true,
            // additive: comets glow over the grid instead of covering it
            blendColorSrcFactor: "one",
            blendColorDstFactor: "one",
            blendAlphaSrcFactor: "one",
            blendAlphaDstFactor: "one-minus-src-alpha",
          },
        }),
      ],
    });
  }, [frame, land, countries, plants, lineBands, links, arcs]);

  const plantGroups = plants ? plants.groups.filter((g) => g !== "other") : [];

  return (
    <div className="relative h-screen w-screen overflow-hidden text-slate-100" style={{ background: SEA }}>
      <div ref={container} className="absolute inset-0" />

      <div className="pointer-events-none absolute left-6 top-5 z-10">
        <div className="font-serif text-[34px] uppercase leading-none tracking-[0.2em]">Europe</div>
        <div className="mt-2 text-[10px] uppercase tracking-[0.32em] text-[#b9ab9b]">Grid, plants & cross-border flows</div>
        {topFlows.length > 0 && (
          <div className="mt-5 w-[210px]">
            <div className="text-[9px] uppercase tracking-[0.24em] text-[#8f877e]">Largest cross-border flows</div>
            <div className="mt-2 space-y-1">
              {topFlows.map((f) => (
                <div key={`${f.from}${f.to}`} className="flex items-center justify-between text-[12px] tabular-nums">
                  <span className="tracking-[0.08em] text-slate-200">
                    {f.from} <span className="text-[#8f877e]">→</span> {f.to}
                  </span>
                  <span style={{ color: rgbCss(FLOW) }}>{gw(f.mw)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute bottom-6 left-6 z-10 space-y-3 text-[11px] text-slate-300">
        <div className="space-y-1">
          {VOLTAGE_BANDS.map((b) => (
            <div key={b.label} className="flex items-center gap-2">
              <span className="h-[2px] w-5 rounded" style={{ background: rgbCss(b.color) }} />
              {b.label}
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="w-5 border-t border-dashed" style={{ borderColor: rgbCss(HVDC) }} />
            HVDC link
          </div>
          <div className="flex items-center gap-2">
            <span className="h-[3px] w-5 rounded" style={{ background: `linear-gradient(90deg, transparent, ${rgbCss(FLOW)})` }} />
            Cross-border flow
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {plantGroups.map((g) => (
            <div key={g} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(PLANT_COLOR[g]) }} />
              {PLANT_LABEL[g]}
            </div>
          ))}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 right-5 z-10 text-right text-[9px] leading-relaxed text-[#77706a]">
        <div>Grid: PyPSA-Eur network from © OpenStreetMap contributors (ODbL) · Plants ≥ 20 MW: powerplantmatching</div>
        <div>Flows: Energy-Charts (Fraunhofer ISE), ENTSO-E physical flows, latest complete 15-min value per border · Borders: © EuroGeographics</div>
      </div>
      <a
        href="/"
        className="absolute right-5 top-4 z-10 rounded border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10"
      >
        ← Atlas
      </a>
      {(error || !grid) && (
        <div className="absolute inset-0 z-20 flex items-center justify-center text-sm text-slate-400">
          {error ?? "loading European grid…"}
        </div>
      )}
    </div>
  );
}
