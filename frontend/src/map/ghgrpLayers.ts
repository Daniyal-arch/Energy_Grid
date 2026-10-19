// US industrial emitters (EPA GHGRP): a dot per facility, area by reported t CO2e, colour by
// sector (Climate TRACE's colours). Nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

import { unitVector } from "../app/geo";
import { ghgrpColor, ghgrpRadius, type GhgrpFile } from "../lib/ghgrp";
import type { Frame } from "./build";
import { memo } from "./memo";

export function ghgrpLayers(fr: Frame): Layer[] {
  const f = fr.layers.ghgrpUS ? (fr.files.ghgrp as GhgrpFile | undefined) : undefined;
  if (!f) return [];
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = memo("ghgrpFacing", [f, fr.camKey], () =>
    f.points.flatMap((p, k) => {
      const v = unitVector(p[0], p[1]);
      return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.1 ? [k] : [];
    }),
  );
  return [
    new ScatterplotLayer<number>({
      id: "us-ghgrp",
      data: facing,
      getPosition: (k) => [f.points[k][0], f.points[k][1]],
      radiusUnits: "pixels",
      getRadius: (k) => ghgrpRadius(f.points[k][2]),
      getFillColor: (k) => [...ghgrpColor(f.sectors[f.points[k][3]]), 170],
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 0.5,
      getLineColor: [8, 10, 14, 160],
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 110],
    }),
  ];
}
