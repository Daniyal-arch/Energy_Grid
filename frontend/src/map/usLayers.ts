// The US grid pack on the map: EIA-860M plants in the style of GEM's world plants, USWTDB
// turbines as fine dots from zoom 5, and the interconnection queue raised on the states like
// the price terrain (height = GW waiting, colour = the largest type). Calm: nothing moves.
// The lines are vector tiles drawn by MapLibre (map/style.ts).

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { dim } from "../app/colors";
import { pairs, unitVector } from "../app/geo";
import { US_TYPE_COLOR, gwText, queueColor, type UsPlantsFile, type UsQueueFile, type UsStatesFile, type UsTurbinesFile } from "../lib/us";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";

/** Turbines appear from this zoom; zoomed out they would only be a smear. */
export const TURBINE_ZOOM = 5;
/** Below this zoom only plants from PLANT_MIN_MW show, as on Europe's plant layer, so the lines stay readable. */
export const PLANT_DETAIL_ZOOM = 5;
export const PLANT_MIN_MW = 50;
/** 1 GW waiting stands 700 m tall; Texas's ~440 GW about 300 km. */
export const QUEUE_M_PER_GW = 700;
/** Every state with requests stands at least this high (metres), so a small queue still reads as a slab. */
const FLOOR_M = 3000;
const LABELLED = 10;
const LABELLED_PHONE = 6;
/** A label is left out within this many degrees of a larger queue's label. */
const LABEL_GAP_DEG = 5;
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

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

  // ------------------------------------------------------------ the queue, raised
  const q = f.usQueue as UsQueueFile | undefined;
  const states = f.usStates as UsStatesFile | undefined;
  if (fr.layers.usQueue && q && states) out.push(...queueTerrain(q, states, fr.isMobile ? LABELLED_PHONE : LABELLED));
  return out;
}

/** GW of active requests in a state (all types; LBNL's reported capacity). */
export const queueMw = (q: UsQueueFile, code: string) => (q.states[code]?.active ?? []).reduce((a, v) => a + v, 0);
/** The type with the most active MW in a state. */
export function largestType(q: UsQueueFile, code: string): string | null {
  const v = q.states[code]?.active;
  if (!v?.some((x) => x > 0)) return null;
  return q.types[v.indexOf(Math.max(...v))];
}

function queueTerrain(q: UsQueueFile, states: UsStatesFile, labelled: number): Layer[] {
  const shapes = memo("queueShapes", [states, q], () =>
    states.states
      .filter((s) => queueMw(q, s.code) > 0)
      .flatMap((s) => s.polygons.map((rings) => ({ code: s.code, name: s.name, polygon: rings.map(pairs) }))),
  );
  const height = (code: string) => FLOOR_M + (queueMw(q, code) / 1000) * QUEUE_M_PER_GW;
  const colour = (code: string): RGB => queueColor(largestType(q, code) ?? "Other");
  const tops = memo("queueTops", [shapes], () => shapes.map((s) => ({ code: s.code, path: s.polygon[0].map((p) => [p[0], p[1], height(s.code) + 200]) as unknown as [number, number][] })));
  const labels = memo("queueLabels", [states, q, labelled], () =>
    states.states
      .map((s) => ({ code: s.code, at: s.label, mw: queueMw(q, s.code) }))
      .filter((s) => s.mw > 0)
      .sort((a, b) => b.mw - a.mw)
      .reduce<{ code: string; at: [number, number]; mw: number }[]>(
        (kept, s) => (kept.length < labelled && !kept.some((k) => Math.hypot(k.at[0] - s.at[0], k.at[1] - s.at[1]) < LABEL_GAP_DEG) ? [...kept, s] : kept),
        [],
      ),
  );
  return [
    new SolidPolygonLayer<QueueShape>({
      id: "us-queue",
      data: shapes,
      getPolygon: (d) => d.polygon,
      extruded: true,
      getElevation: (d) => height(d.code),
      getFillColor: (d) => [...colour(d.code), 255],
      material: { ambient: 0.7, diffuse: 0.45, shininess: 12, specularColor: [30, 30, 30] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 40],
    }),
    // a darker edge on each slab's top, so neighbours of one colour stay apart
    new PathLayer<{ code: string; path: [number, number][] }>({
      id: "us-queue-tops",
      data: tops,
      getPath: (d) => d.path,
      getColor: (d) => [...dim(colour(d.code), 0.55), 200],
      getWidth: 0.8,
      widthUnits: "pixels",
    }),
    new TextLayer<{ code: string; at: [number, number]; mw: number }>({
      id: "us-queue-labels",
      data: labels,
      getPosition: (d) => [d.at[0], d.at[1], height(d.code) + 30_000] as unknown as [number, number],
      getText: (d) => `${d.code} ${gwText(d.mw)}`,
      getSize: 12,
      getColor: [236, 240, 246, 255],
      fontFamily: "Inter, system-ui, sans-serif",
      fontWeight: 700,
      background: true,
      getBackgroundColor: [6, 9, 14, 200],
      backgroundPadding: [4, 2],
      parameters: ON_TOP,
    }),
  ];
}
