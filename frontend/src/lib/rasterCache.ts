// Continuous data (solar and wind resource, flood hazard) read for a box by HTTP range: the lookup
// grid's cells (every n-th row and column for large boxes, said with the result), cached per box
// so the maps can draw them as cells, hexagon means or 3D terrain. A change wakes the map.

import { create } from "zustand";

import { makeShape, readGrid } from "./area";
import type { Pt, RasterMeasure } from "./measures";

type Files = Record<string, unknown>;
export interface RasterCells {
  pts: Pt[];
  /** the side of a drawn cell, degrees (the grid's cell times the sampling step) */
  cell: number;
  step: number;
}

/** Bumped when a box has been read: subscribers redraw. */
export const useRasterCache = create<{ v: number }>(() => ({ v: 0 }));
const cache = new Map<string, RasterCells | "loading" | "failed">();

/** The cells of a raster in a box [west, south, east, north]; null while reading. */
export function rasterCells(r: RasterMeasure, files: Files, box: [number, number, number, number], maxRows = 140): RasterCells | null {
  const def = r.grid(files);
  if (!def) return null;
  // a box rounded out to whole degrees, so small pans read nothing new
  const q = (v: number, up: boolean) => (up ? Math.ceil(v) : Math.floor(v));
  const b: [number, number, number, number] = [Math.max(-180, q(box[0], false)), Math.max(-85, q(box[1], false)), Math.min(180, q(box[2], true)), Math.min(85, q(box[3], true))];
  const key = `${r.id}|${b.join(",")}|${maxRows}`;
  const hit = cache.get(key);
  if (hit && hit !== "loading" && hit !== "failed") return hit;
  if (hit) return null;
  cache.set(key, "loading");
  const shape = makeShape("polygon", key, "", [[[b[0], b[1], b[2], b[1], b[2], b[3], b[0], b[3]]]]);
  const pts: Pt[] = [];
  readGrid(
    def.spec,
    shape,
    (v, off, lon, lat) => {
      const x = def.value(v, off);
      if (x != null) pts.push([lon, lat, x, ""]);
    },
    maxRows,
  )
    .then((res) => {
      if (cache.size > 60) cache.clear();
      cache.set(key, { pts, cell: def.spec.cell * res.step, step: res.step });
      useRasterCache.setState((s) => ({ v: s.v + 1 }));
    })
    .catch(() => {
      cache.set(key, "failed");
      useRasterCache.setState((s) => ({ v: s.v + 1 }));
    });
  return null;
}
