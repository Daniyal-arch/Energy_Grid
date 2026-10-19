// ENTSO-E TYNDP 2024 projects: lines and areas by status, storage and point projects as rings.
// Nothing moves.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { pairs } from "../app/geo";
import { tyndpStyle, type TyndpFile } from "../lib/tyndp";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

interface Part {
  k: number;
  path: [number, number][];
}
interface Area {
  k: number;
  polygon: [number, number][][];
}

export function tyndpLayers(fr: Frame): Layer[] {
  const f = fr.layers.tyndp ? (fr.files.tyndp as TyndpFile | undefined) : undefined;
  if (!f) return [];
  const style = (k: number) => tyndpStyle(f, f.features[k]);
  const lines = memo("tyndpLines", [f], () =>
    f.features.flatMap((x, k) => (x.kind === "line" ? (x.geometry as number[][]).map((flat) => ({ k, path: pairs(flat) })) : [])),
  );
  const areas = memo("tyndpAreas", [f], () =>
    f.features.flatMap((x, k) => (x.kind === "area" ? (x.geometry as number[][][]).map((rings) => ({ k, polygon: rings.map(pairs) })) : [])),
  );
  const points = memo("tyndpPoints", [f], () => f.features.flatMap((x, k) => (x.kind === "point" ? [k] : [])));
  return [
    new SolidPolygonLayer<Area>({
      id: "eu-tyndp-areas",
      data: areas,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => [...style(d.k)[0], 50],
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 40],
      parameters: ON_TOP,
    }),
    new PathLayer<Part>({
      id: "eu-tyndp",
      data: lines,
      getPath: (d) => d.path,
      getColor: (d) => [...style(d.k)[0], style(d.k)[1]],
      widthUnits: "pixels",
      getWidth: 2,
      capRounded: true,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 140],
      parameters: ON_TOP,
    }),
    new ScatterplotLayer<number>({
      id: "eu-tyndp-points",
      data: points,
      getPosition: (k) => f.features[k].geometry as [number, number],
      radiusUnits: "pixels",
      getRadius: 4,
      filled: false,
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      getLineColor: (k) => [...style(k)[0], 230],
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
}
