// The US grid pack on the map: EIA-860M plants in the style of GEM's world plants, USWTDB
// turbines as fine dots from zoom 5, and the interconnection queue: on each state a tower of
// what is waiting to connect, stacked by type, the state shaded by how that compares with
// the plants it runs today. Calm: nothing moves. The lines are vector tiles drawn by
// MapLibre (map/style.ts).

import type { Layer } from "@deck.gl/core";
import { ColumnLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { stopColor } from "../app/colors";
import { pairs, unitVector } from "../app/geo";
import {
  QUEUE_RATIO_STOPS,
  US_TYPE_COLOR,
  gwText,
  operatingMw,
  queueColor,
  ratioText,
  type UsPlantsFile,
  type UsQueueFile,
  type UsStatesFile,
  type UsTurbinesFile,
} from "../lib/us";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";

/** Turbines appear from this zoom; zoomed out they would only be a smear. */
export const TURBINE_ZOOM = 5;
/** Below this zoom only plants from PLANT_MIN_MW show, as on Europe's plant layer, so the lines stay readable. */
export const PLANT_DETAIL_ZOOM = 5;
export const PLANT_MIN_MW = 50;
/** 1 GW waiting stands 1.4 km tall; Texas's ~440 GW about 600 km. */
export const QUEUE_M_PER_GW = 1400;
const TOWER_RADIUS_M = 36_000;
const LABELLED = 10;
const LABELLED_PHONE = 6;
/** A label is left out within this many degrees of a larger queue's label. */
const LABEL_GAP_DEG = 4;
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
/** Text the labels use (deck.gl draws its own glyph atlas). */
const LABEL_CHARS = `${Array.from({ length: 95 }, (_, i) => String.fromCharCode(32 + i)).join("")}×·`;

export interface QueueShape {
  code: string;
  name: string;
  polygon: [number, number][][];
}

export function usLayers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  const f = fr.files;
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = (lon: number, lat: number) => {
    const v = unitVector(lon, lat);
    return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.17;
  };

  // ------------------------------------------------------------ plants (EIA-860M)
  const up = f.usPlants as UsPlantsFile | undefined;
  if (fr.layers.plantsUS && up) {
    const st = up.statuses.indexOf(fr.plantStatus);
    const coarse = fr.zoom < PLANT_DETAIL_ZOOM;
    const idx = memo("usPlantIdx", [up, st, fr.camKey, coarse], () => {
      const keep: number[] = [];
      up.points.forEach((p, k) => {
        if (p[3] === st && (!coarse || p[4] >= PLANT_MIN_MW) && facing(p[0], p[1])) keep.push(k);
      });
      return keep;
    });
    const status = fr.plantStatus;
    const colorOf = (k: number): RGB => US_TYPE_COLOR[up.types[up.points[k][2]]] ?? [150, 150, 150];
    out.push(
      new ScatterplotLayer<number>({
        id: "us-plants",
        data: idx,
        getPosition: (k) => [up.points[k][0], up.points[k][1]],
        // the same sizes and status styles as GEM's world plants (map/build.ts)
        getRadius: (k) => Math.min(9, 0.6 + Math.sqrt(Math.max(0, up.points[k][4])) * (fr.zoom < 3 ? 0.07 : 0.11)),
        radiusUnits: "pixels",
        getFillColor: (k) => (status === "retired" ? [110, 110, 120, 170] : status === "planned" ? [...colorOf(k), 60] : [...colorOf(k), 210]),
        stroked: status !== "operating",
        getLineColor: (k) => [...colorOf(k), 230],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        updateTriggers: { getRadius: [fr.zoom < 3], getFillColor: [status], getLineColor: [status] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ------------------------------------------------------------ wind turbines (USWTDB)
  const tb = f.usTurbines as UsTurbinesFile | undefined;
  if (fr.layers.turbinesUS && tb && fr.zoom >= TURBINE_ZOOM) {
    const idx = memo("usTurbineIdx", [tb, fr.camKey], () => {
      const keep: number[] = [];
      for (let k = 0; k < tb.count; k++) if (facing(tb.lon[k], tb.lat[k])) keep.push(k);
      return keep;
    });
    // fine wind-coloured dots; from zoom 8 each turbine a small ring
    const near = fr.zoom >= 8;
    const step = near ? 2 : fr.zoom >= 7 ? 1 : 0;
    out.push(
      new ScatterplotLayer<number>({
        id: "us-turbines",
        data: idx,
        getPosition: (k) => [tb.lon[k], tb.lat[k]],
        getRadius: [0.8, 1.1, 2][step],
        radiusUnits: "pixels",
        getFillColor: [72, 222, 184, [150, 180, 70][step]],
        stroked: near,
        getLineColor: [72, 222, 184, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 0.8,
        updateTriggers: { getFillColor: [step] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ------------------------------------------------------------ the queue: towers on shaded states
  const q = f.usQueue as UsQueueFile | undefined;
  const states = f.usStates as UsStatesFile | undefined;
  if (fr.layers.usQueue && q && states) out.unshift(...queueView(q, states, up, fr.isMobile ? LABELLED_PHONE : LABELLED));
  // faint state lines under the plants, turbines and lines, for orientation
  else if (states && (fr.layers.plantsUS || fr.layers.turbinesUS || fr.layers.gridUS)) out.unshift(stateLines(states, [150, 162, 184, 55]));
  return out;
}

function stateLines(states: UsStatesFile, color: [number, number, number, number]): Layer {
  const rings = memo("usStateRings", [states], () => states.states.flatMap((s) => s.polygons.map((r) => pairs(r[0]))));
  return new PathLayer<[number, number][]>({
    id: "us-state-lines",
    data: rings,
    getPath: (d) => d,
    getColor: color,
    getWidth: 0.7,
    widthUnits: "pixels",
    parameters: ON_TOP,
  });
}

/** GW of active requests in a state (all types; LBNL's reported capacity). */
export const queueMw = (q: UsQueueFile, code: string) => (q.states[code]?.active ?? []).reduce((a, v) => a + v, 0);
/** The type with the most active MW in a state. */
export function largestType(q: UsQueueFile, code: string): string | null {
  const v = q.states[code]?.active;
  if (!v?.some((x) => x > 0)) return null;
  return q.types[v.indexOf(Math.max(...v))];
}

/** GW waiting ÷ GW operating in a state (computed), or null without plants data. */
export function queueRatio(q: UsQueueFile, p: UsPlantsFile | undefined, code: string): number | null {
  const op = operatingMw(p, code);
  return p && op > 0 ? queueMw(q, code) / op : null;
}

interface TowerPiece {
  code: string;
  type: string;
  base: number;
  mw: number;
}

function queueView(q: UsQueueFile, states: UsStatesFile, plants: UsPlantsFile | undefined, labelled: number): Layer[] {
  const shapes = memo("queueShapes", [states], () =>
    states.states.flatMap((s) => s.polygons.map((rings) => ({ code: s.code, name: s.name, polygon: rings.map(pairs) }))),
  );
  const shade = (code: string): RGB => {
    const r = queueRatio(q, plants, code);
    return r == null ? [30, 36, 48] : (stopColor(QUEUE_RATIO_STOPS, Math.min(8, r)) ?? [30, 36, 48]);
  };
  // one tower per state at its label point, stacked by type in the national order
  const pieces = memo("queueTowers", [states, q], () =>
    states.states.flatMap((s) => {
      const active = q.states[s.code]?.active;
      if (!active) return [];
      let base = 0;
      return q.types.flatMap((type, i) => {
        const mw = active[i] ?? 0;
        if (mw <= 0) return [];
        const piece = { code: s.code, type, base, mw };
        base += mw;
        return [piece];
      });
    }),
  );
  const at = memo("queueAt", [states], () => new Map(states.states.map((s) => [s.code, s.label] as const)));
  const labels = memo("queueLabels", [states, q, plants, labelled], () =>
    states.states
      .map((s) => ({ code: s.code, at: s.label, mw: queueMw(q, s.code), ratio: queueRatio(q, plants, s.code) }))
      .filter((s) => s.mw > 0)
      .sort((a, b) => b.mw - a.mw)
      .reduce<{ code: string; at: [number, number]; mw: number; ratio: number | null }[]>(
        (kept, s) => (kept.length < labelled && !kept.some((k) => Math.hypot(k.at[0] - s.at[0], k.at[1] - s.at[1]) < LABEL_GAP_DEG) ? [...kept, s] : kept),
        [],
      ),
  );
  const m = (mw: number) => (mw / 1000) * QUEUE_M_PER_GW;
  return [
    // the states, shaded by queue ÷ operating plants
    new SolidPolygonLayer<QueueShape>({
      id: "us-queue",
      data: shapes,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => [...shade(d.code), 235],
      updateTriggers: { getFillColor: [plants] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 30],
      parameters: ON_TOP,
    }),
    stateLines(states, [8, 10, 14, 200]),
    new ColumnLayer<TowerPiece>({
      id: "us-queue-towers",
      data: pieces,
      getPosition: (d) => [...(at.get(d.code) ?? [0, 0]), m(d.base)] as unknown as [number, number],
      getElevation: (d) => m(d.mw),
      getFillColor: (d) => [...queueColor(d.type), 240],
      radius: TOWER_RADIUS_M,
      diskResolution: 20,
      extruded: true,
      pickable: true,
      material: { ambient: 0.6, diffuse: 0.55, shininess: 16, specularColor: [40, 40, 40] },
    }),
    new TextLayer<{ code: string; at: [number, number]; mw: number; ratio: number | null }>({
      id: "us-queue-labels",
      data: labels,
      getPosition: (d) => [d.at[0], d.at[1], m(d.mw) + 30_000] as unknown as [number, number],
      getText: (d) => `${d.code} ${gwText(d.mw)}${d.ratio != null ? ` · ${ratioText(d.ratio)} its plants` : ""}`,
      getSize: 12,
      getColor: [236, 240, 246, 255],
      fontFamily: "Inter, system-ui, sans-serif",
      fontWeight: 700,
      characterSet: LABEL_CHARS,
      background: true,
      getBackgroundColor: [6, 9, 14, 210],
      backgroundPadding: [4, 2],
      updateTriggers: { getText: [plants] },
      parameters: ON_TOP,
    }),
  ];
}
