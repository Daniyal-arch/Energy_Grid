// The asset layers of data wave 8 (docs/tasks/27, B4): industrial facilities (EEA Industrial
// Reporting), dams (Global Dam Watch), CO2 storage units (CO2StoP), excess heat sites (Hotmaps)
// and fires (NIFC perimeters, FIRMS detections). Each file lists its fields; the hover card shows
// them as published with the file's source.

import type { Layer } from "@deck.gl/core";
import { PolygonLayer, ScatterplotLayer } from "@deck.gl/layers";

import type { LayerId } from "../app/store";
import type { Frame } from "./build";
import { memo } from "./memo";

/** A wave-8 point file (scripts/build_assets_w8.py). */
export interface W8File {
  source: string;
  fetched?: string;
  how?: string;
  fields: string[];
  points: (string | number | null)[][];
}
export interface W8FiresFile {
  source: string;
  fetched?: string;
  perimeters: { name: string | null; acres: number | null; discovered: number | null; rings: number[][][] }[];
  detections: (string | number | null)[][];
  skipped: string[];
}

export const W8_LAYERS: { layer: LayerId; file: string; color: [number, number, number]; noun: string }[] = [
  { layer: "w8Industrial", file: "w8Industrial", color: [214, 160, 255], noun: "Reporting facility" },
  { layer: "w8Dams", file: "w8Dams", color: [96, 170, 255], noun: "Dam" },
  { layer: "w8Co2Storage", file: "w8Co2Storage", color: [140, 220, 180], noun: "CO₂ storage unit" },
  { layer: "w8ExcessHeat", file: "w8ExcessHeat", color: [255, 150, 90], noun: "Industrial site with excess heat" },
];

/** The files a frame needs for the wave-8 layers switched on. */
export function wave8Keys(L: Record<string, boolean>): string[] {
  return [...W8_LAYERS.filter((d) => L[d.layer]).map((d) => d.file), ...(L.w8Fires ? ["w8Fires"] : [])];
}

export function wave8Layers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  const r = fr.zoom < 4 ? 1.6 : fr.zoom < 7 ? 2.6 : 3.6;
  for (const d of W8_LAYERS) {
    const f = fr.files[d.file] as W8File | undefined;
    if (!fr.layers[d.layer] || !f) continue;
    out.push(
      new ScatterplotLayer<W8File["points"][number]>({
        id: `w8-${d.file}`,
        data: f.points,
        getPosition: (p) => [Number(p[0]), Number(p[1])],
        getRadius: r,
        radiusUnits: "pixels",
        getFillColor: [...d.color, 200],
        stroked: true,
        getLineColor: [12, 16, 24, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        pickable: true,
        updateTriggers: { getRadius: [r] },
      }),
    );
  }
  const fires = fr.files.w8Fires as W8FiresFile | undefined;
  if (fr.layers.w8Fires && fires) {
    const polys = memo("w8FirePolys", [fires], () => fires.perimeters.flatMap((p, i) => p.rings.map((rings) => ({ i, rings }))));
    out.push(
      new PolygonLayer<{ i: number; rings: number[][] }>({
        id: "w8-fire-perimeters",
        data: polys,
        getPolygon: (p) => p.rings.map((ring) => ring.reduce<number[][]>((a, v, k) => (k % 2 ? a : [...a, [v, ring[k + 1]]]), [])),
        getFillColor: [255, 96, 48, 70],
        getLineColor: [255, 120, 60, 230],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        pickable: true,
      }),
      new ScatterplotLayer<W8FiresFile["detections"][number]>({
        id: "w8-fire-detections",
        data: fires.detections,
        getPosition: (p) => [Number(p[0]), Number(p[1])],
        getRadius: 2.2,
        radiusUnits: "pixels",
        getFillColor: [255, 70, 30, 230],
        pickable: true,
      }),
    );
  }
  return out;
}

/** The hover card of a wave-8 record: its fields as published, the source. */
export function wave8Html(id: string, object: unknown, files: Record<string, unknown>): string | null {
  const src = (s: string) => `<div style="color:#8d94a1">${s}</div>`;
  if (id === "w8-fire-perimeters" || id === "w8-fire-detections") {
    const f = files.w8Fires as W8FiresFile | undefined;
    if (!f) return null;
    if (id === "w8-fire-perimeters") {
      const p = f.perimeters[(object as { i: number }).i];
      return `<b>${p?.name ?? "Fire perimeter"}</b>${p?.acres != null ? `<div>${Math.round(p.acres).toLocaleString("en-US")} acres (as published)</div>` : ""}${src(`${f.source} · ${f.fetched?.slice(0, 10) ?? ""}`)}`;
    }
    const d = object as W8FiresFile["detections"][number];
    return `<b>Fire detection</b><div>${d[2]} ${d[3]} UTC · FRP ${d[4]} MW · confidence ${d[5]}</div>${src(f.source)}`;
  }
  const def = W8_LAYERS.find((d) => id === `w8-${d.file}`);
  const f = def ? (files[def.file] as W8File | undefined) : undefined;
  if (!def || !f) return null;
  const p = object as W8File["points"][number];
  const rows = f.fields
    .map((k, i) => [k, p[i]] as const)
    .filter(([k, v]) => v != null && v !== "" && k !== "lon" && k !== "lat" && k !== "name")
    .map(([k, v]) => `<div>${k.replace(/_/g, " ")}: <b>${typeof v === "number" ? v.toLocaleString("en-US") : v}</b></div>`)
    .join("");
  const name = f.fields.indexOf("name");
  return `<b>${(name >= 0 && p[name]) || def.noun}</b>${rows}${src(f.source)}`;
}
