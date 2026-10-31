// The generic layers of data wave 9 (docs/tasks/28): one point layer per source that is small
// enough for the app (frontend/public/data/eu/w9/<id>.json, written by scripts/wave9.py). The
// layers, their groups and colours come from app/wave9.json; the hover card lists the fields as
// published with the source. Larger sources stay in the lake for the agent.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

import WAVE9 from "../app/wave9.json";
import type { Frame } from "./build";

/** A wave-9 point file. */
export interface W9File {
  source: string;
  fetched?: string;
  fields: string[];
  points: (string | number | null)[][];
}

const LAYERS = WAVE9.layers as { id: string; color: string }[];
const rgb = (c: string): [number, number, number] => {
  const m = c.match(/\d+/g) ?? ["200", "200", "200"];
  return [Number(m[0]), Number(m[1]), Number(m[2])];
};

/** The files a frame needs for the wave-9 layers switched on ("w9:<source id>"). */
export function wave9Keys(L: Record<string, boolean>): string[] {
  return LAYERS.filter((d) => L[d.id]).map((d) => `w9:${d.id.slice(3)}`);
}

export function wave9Layers(fr: Frame): Layer[] {
  const r = fr.zoom < 4 ? 1.6 : fr.zoom < 7 ? 2.6 : 3.6;
  const out: Layer[] = [];
  for (const d of LAYERS) {
    const f = fr.files[`w9:${d.id.slice(3)}`] as W9File | undefined;
    if (!(fr.layers as Record<string, boolean>)[d.id] || !f) continue;
    out.push(
      new ScatterplotLayer<W9File["points"][number]>({
        id: `w9-${d.id.slice(3)}`,
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
  return out;
}

/** The hover card of a wave-9 record: its fields as published, the source. */
export function wave9Html(id: string, object: unknown, file: unknown): string | null {
  const f = file as W9File | undefined;
  if (!f) return null;
  const p = object as W9File["points"][number];
  const label = (LAYERS.find((d) => d.id === `w9_${id.slice(3)}`) as { label?: string } | undefined)?.label ?? "Record";
  const rows = f.fields
    .map((k, i) => [k, p[i]] as const)
    .filter(([k, v]) => v != null && v !== "" && k !== "lon" && k !== "lat" && k !== "name")
    .map(([k, v]) => `<div>${k.replace(/_/g, " ")}: <b>${typeof v === "number" ? v.toLocaleString("en-US") : v}</b></div>`)
    .join("");
  return `<b>${p[2] ?? label}</b><div style="color:#8d94a1">${label}</div>${rows}<div style="color:#8d94a1">${f.source}</div>`;
}
