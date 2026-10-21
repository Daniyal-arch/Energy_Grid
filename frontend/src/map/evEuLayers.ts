// EV charging in Europe (scripts/build_ev_eu.py): one calm dot per 0.1° cell, area by the points
// (registers) or stations (OpenStreetMap) in it; the two shades say which.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

import { EV_EU_COLOR, EV_OSM_COLOR, isRegister, type EvEuFile } from "../lib/evEu";
import type { Frame } from "./build";
import { memo } from "./memo";

/** [lon, lat, count, country] */
export type EvEuCell = [number, number, number, string];

export function evEuLayers(fr: Frame): Layer[] {
  const f = fr.layers.evChargersEU ? (fr.files.evEu as EvEuFile | undefined) : undefined;
  if (!f) return [];
  const data = memo("evEuCells", [f], () => Object.entries(f.cells).flatMap(([cc, cs]) => cs.map((c): EvEuCell => [c[0], c[1], c[2], cc])));
  return [
    new ScatterplotLayer<EvEuCell>({
      id: "eu-ev",
      data,
      getPosition: (c) => [c[0], c[1]],
      radiusUnits: "pixels",
      // area follows the count: 1 -> 1 px, 100 -> 4 px, 1,000 -> 9.5 px
      getRadius: (c) => Math.min(14, Math.max(1, Math.sqrt(c[2]) * 0.3)),
      radiusMinPixels: 1,
      getFillColor: (c) => [...(isRegister(f.maps[c[3]]) ? EV_EU_COLOR : EV_OSM_COLOR), 150],
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
    }),
  ];
}
