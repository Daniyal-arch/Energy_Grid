// Offshore wind farms (EMODnet): each farm's area filled by its status, faint while planned,
// and the point records without an area as small rings. Nothing moves.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { pairs } from "../app/geo";
import { OFFSHORE_STYLE, offshoreStatus, type OffshoreWindFile } from "../lib/offshoreWind";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
const GREY: [[number, number, number], number] = [[120, 128, 140], 40];

interface FarmShape {
  k: number;
  polygon: [number, number][][];
}

export function offshoreLayers(fr: Frame): Layer[] {
  const f = fr.layers.offshoreWind ? (fr.files.offshoreWind as OffshoreWindFile | undefined) : undefined;
  if (!f) return [];
  const style = (k: number) => OFFSHORE_STYLE[offshoreStatus(f, f.farms[k])] ?? GREY;
  const shapes = memo("offshoreShapes", [f], () =>
    f.farms.flatMap((farm, k) => (farm.polygons ?? []).map((rings) => ({ k, polygon: rings.map(pairs) }))),
  );
  const points = memo("offshorePoints", [f], () => f.farms.flatMap((farm, k) => (farm.polygons ? [] : [k])));
  return [
    new SolidPolygonLayer<FarmShape>({
      id: "eu-offshore-wind",
      data: shapes,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => {
        const [c, a] = style(d.k);
        return [...c, a];
      },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 50],
      parameters: ON_TOP,
    }),
    new PathLayer<FarmShape>({
      id: "eu-offshore-wind-lines",
      data: shapes,
      getPath: (d) => d.polygon[0],
      getColor: (d) => [...style(d.k)[0], 170],
      widthUnits: "pixels",
      getWidth: 0.8,
      parameters: ON_TOP,
    }),
    new ScatterplotLayer<number>({
      id: "eu-offshore-wind-points",
      data: points,
      getPosition: (k) => f.farms[k].at,
      radiusUnits: "pixels",
      getRadius: 3,
      filled: false,
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      getLineColor: (k) => [...style(k)[0], 200],
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
}
