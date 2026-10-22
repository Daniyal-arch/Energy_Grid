// Room to connect in ten more countries (the "Grid capacity" layer): the operators' substations as
// dots, Sweden's counties as areas, coloured by each file's class. Nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { pairs } from "../app/geo";
import { CONNECT_EU, classColor, connectEuKey, type ConnectEuFile, type EuArea, type EuPoint } from "../lib/connectEu";
import { inAreaCountry } from "../app/datasets";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

export function connectEuLayers(fr: Frame): Layer[] {
  if (!fr.layers.connect) return [];
  const out: Layer[] = [];
  for (const cc of CONNECT_EU) {
    const f = fr.files[connectEuKey(cc)] as ConnectEuFile | undefined;
    if (!f || !inAreaCountry(fr.area, cc.slice(0, 2))) continue;
    if (f.areas.length) {
      const areas = memo(`connectEuAreas${cc}`, [f], () => f.areas.flatMap((a) => a[1].map((rings) => ({ a, polygon: rings.map(pairs) }))));
      out.push(
        new SolidPolygonLayer<(typeof areas)[number]>({
          id: `eu-connect7-areas:${cc}`,
          data: areas,
          getPolygon: (d) => d.polygon,
          getFillColor: (d) => [...classColor(f, (d.a as EuArea)[3]), 110],
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 40],
          parameters: ON_TOP,
        }),
      );
    }
    if (f.points.length)
      out.push(
        new ScatterplotLayer<EuPoint>({
          id: `eu-connect7:${cc}`,
          data: f.points,
          getPosition: (p) => [p[1], p[2]],
          getRadius: (p) => (typeof p[3] === "number" && p[3] >= 220 ? 5 : 3.5),
          radiusUnits: "pixels",
          radiusMinPixels: 2,
          getFillColor: (p) => [...classColor(f, p[5]), 215],
          stroked: true,
          getLineColor: [6, 7, 10, 200],
          lineWidthUnits: "pixels",
          getLineWidth: 0.5,
          pickable: true,
          parameters: ON_TOP,
        }),
      );
  }
  return out;
}
