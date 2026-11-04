// The generic layers of the registry waves (9, 10, ...; scripts/wave9.py): one point layer per
// source small enough for the app (data/eu/w<N>/<id>.json) and the area colourings
// (data/eu/w<N>c/<id>.json) drawn on US counties or GB districts. The layers, groups and colours
// come from app/waves.ts; the hover card lists the fields as published with the source. Larger
// sources are vector tiles (map/wave9Tiles.ts) or stay in the lake for the agent.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { WAVES, deckId, fromDeckId, isWaveColour, waveKey } from "../app/waves";
import { stopColor } from "../app/colors";
import { pairs } from "../app/geo";
import type { UsCountiesFile } from "../lib/risk";
import { type W9cFile, w9cStops } from "../lib/wave9";
import type { Frame } from "./build";
import { memo } from "./memo";

/** A wave-9 point file. */
export interface W9File {
  source: string;
  fetched?: string;
  fields: string[];
  points: (string | number | null)[][];
}

/** The shapes of a GB local authority district colouring (scripts/wave9.py gb-lad, ONS). */
export interface GbLadFile {
  source: string;
  areas: { code: string; name: string; polygons: number[][][] }[];
}

/** The shapes file each area colouring needs (none for countries: the map's own outlines). */
const SCOPE_SHAPES: Record<string, string> = { us_county: "usCounties", gb_lad: "gbLad", gb_lad24: "gbLad24" };
export const W9C_SHAPES: Record<string, string> = Object.fromEntries(
  (WAVES.colours as { id: string; scope: string }[]).filter((c) => SCOPE_SHAPES[c.scope]).map((c) => [c.id, SCOPE_SHAPES[c.scope]]),
);

// point layers drawn here; layers with vector tiles are MapLibre's (map/tiles.ts)
const LAYERS = (WAVES.layers as { id: string; color: string; tiles?: string }[]).filter((d) => !d.tiles);
const rgb = (c: string): [number, number, number] => {
  const m = c.match(/\d+/g) ?? ["200", "200", "200"];
  return [Number(m[0]), Number(m[1]), Number(m[2])];
};

/** The files a frame needs for the wave layers switched on ("w<N>:<source id>"). */
export function wave9Keys(L: Record<string, boolean>): string[] {
  return LAYERS.filter((d) => L[d.id]).map((d) => waveKey(d.id));
}

export function wave9Layers(fr: Frame): Layer[] {
  const r = fr.zoom < 4 ? 1.6 : fr.zoom < 7 ? 2.6 : 3.6;
  const out: Layer[] = [];
  for (const d of LAYERS) {
    const f = fr.files[waveKey(d.id)] as W9File | undefined;
    if (!(fr.layers as Record<string, boolean>)[d.id] || !f) continue;
    out.push(
      new ScatterplotLayer<W9File["points"][number]>({
        id: deckId(d.id),
        data: f.points,
        getPosition: (p) => [Number(p[0]), Number(p[1])],
        getRadius: r,
        radiusUnits: "pixels",
        getFillColor: [...rgb(d.color), 200],
        stroked: true,
        getLineColor: [12, 16, 24, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        pickable: true,
        updateTriggers: { getRadius: [r] },
      }),
    );
  }
  // a wave colouring per US county or GB local authority district (the app's area shapes)
  if (isWaveColour(fr.colour)) {
    const w9 = fr.files[waveKey(fr.colour)] as W9cFile | undefined;
    const shapes0 = w9 ? fr.files[SCOPE_SHAPES[w9.scope] ?? ""] : undefined;
    const areas = w9?.scope === "us_county" ? (shapes0 as UsCountiesFile | undefined)?.counties : (shapes0 as GbLadFile | undefined)?.areas;
    if (w9 && areas) {
      const stops = memo(`w9cStops:${fr.colour}`, [w9], () => w9cStops(w9));
      const shapes = memo(`areaShapes:${w9.scope}`, [areas], () =>
        areas.flatMap((a) => a.polygons.map((rings) => ({ code: a.code, name: a.name, polygon: rings.map(pairs) }))),
      );
      out.push(
        new SolidPolygonLayer<(typeof shapes)[number]>({
          id: deckId(fr.colour),
          data: shapes,
          getPolygon: (d) => d.polygon,
          getFillColor: (d) => [...(stopColor(stops, w9.values[d.code]) ?? [24, 28, 36]), 225] as [number, number, number, number],
          updateTriggers: { getFillColor: [w9] },
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 40],
        }),
        new PathLayer<(typeof shapes)[number]>({
          id: `${deckId(fr.colour)}-lines`,
          data: shapes,
          getPath: (d) => d.polygon[0],
          getColor: [8, 10, 14, 120],
          widthUnits: "pixels",
          getWidth: 0.4,
        }),
      );
    }
  }
  return out;
}

/** The hover card of an area in a wave-9 colouring: its value as published, the source. */
export function wave9CountyHtml(object: unknown, file: unknown): string | null {
  const f = file as W9cFile | undefined;
  const d = object as { code?: string; name?: string } | undefined;
  if (!f || !d?.code) return null;
  const v = f.values[d.code];
  const title = f.scope.startsWith("gb_lad") ? `${d.name ?? ""} (${d.code})` : `County ${d.code}`;
  return `<b>${title}</b><div>${f.label}: <b>${v == null ? "not published" : `${v.toLocaleString("en-US")} ${f.unit}`}</b></div><div style="color:#8d94a1">${f.period ?? ""} · ${f.source}</div>`;
}

/** The hover card of a wave-9 record: its fields as published, the source. */
export function wave9Html(id: string, object: unknown, file: unknown): string | null {
  const f = file as W9File | undefined;
  if (!f) return null;
  const p = object as W9File["points"][number];
  const label = (LAYERS.find((d) => d.id === fromDeckId(id)) as { label?: string } | undefined)?.label ?? "Record";
  const rows = f.fields
    .map((k, i) => [k, p[i]] as const)
    .filter(([k, v]) => v != null && v !== "" && k !== "lon" && k !== "lat" && k !== "name")
    .map(([k, v]) => `<div>${k.replace(/_/g, " ")}: <b>${typeof v === "number" ? v.toLocaleString("en-US") : v}</b></div>`)
    .join("");
  return `<b>${p[2] ?? label}</b><div style="color:#8d94a1">${label}</div>${rows}<div style="color:#8d94a1">${f.source}</div>`;
}
