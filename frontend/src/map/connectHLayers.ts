// The Grid capacity layer in one symbology (brief 23): every operator's records from
// connect/harmonised.json, nodes as dots and areas as outlines with a light fill, the same four
// class colours everywhere; dot area by the free MW published for the chosen side (new generation
// or new demand), a fixed small dot where none is published.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { H, H_COLOR, H_NO_CLASS, hRadius, pairsOf, sideOf, type HFile, type HRow } from "../lib/connectH";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** one outline part: the row and its first ring as [x, y] pairs */
type Part = { r: HRow; ring: [number, number][] };

export function connectHLayers(fr: Frame): Layer[] {
  const f = fr.layers.connect ? (fr.files.connectH as HFile | undefined) : undefined;
  if (!f) return [];
  const side = fr.connectSide;
  const nodes = memo("connectHNodes", [f], () => f.rows.filter((r) => r[H.kind] === "node" && r[H.lon] != null && r[H.lat] != null));
  const parts = memo("connectHParts", [f], () =>
    f.rows.flatMap((r) => (r[H.kind] === "area" && r[H.polygon] ? r[H.polygon]!.map((poly) => ({ r, ring: pairsOf(poly[0]) })) : [])),
  );
  const colour = (r: HRow) => {
    const c = sideOf(r, side).cls;
    return c ? H_COLOR[c] : H_NO_CLASS;
  };
  // nothing published for this side (neither class nor value): a faint dot, so the operator's
  // nodes stay visible without suggesting a value
  const silent = (r: HRow) => {
    const v = sideOf(r, side);
    return v.cls == null && v.mw == null && v.mva == null;
  };
  return [
    new SolidPolygonLayer<Part>({
      id: "eu-connect-h-areas",
      data: parts,
      getPolygon: (d) => d.ring,
      getFillColor: (d) => [...colour(d.r), 60],
      updateTriggers: { getFillColor: [side] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 40],
      parameters: ON_TOP,
    }),
    new PathLayer<Part>({
      id: "eu-connect-h-outlines",
      data: parts,
      getPath: (d) => [...d.ring, d.ring[0]],
      getColor: (d) => [...colour(d.r), 190],
      updateTriggers: { getColor: [side] },
      getWidth: 1,
      widthUnits: "pixels",
      parameters: ON_TOP,
    }),
    new ScatterplotLayer<HRow>({
      id: "eu-connect-h",
      data: nodes,
      getPosition: (r) => [r[H.lon]!, r[H.lat]!],
      getRadius: (r) => (silent(r) ? 1.5 : hRadius(sideOf(r, side).mw)),
      radiusUnits: "pixels",
      getFillColor: (r) => [...colour(r), silent(r) ? 60 : 200],
      stroked: true,
      getLineColor: (r) => [6, 7, 10, silent(r) ? 0 : 200],
      lineWidthUnits: "pixels",
      getLineWidth: 0.5,
      updateTriggers: { getRadius: [side], getFillColor: [side], getLineColor: [side] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
      parameters: ON_TOP,
    }),
  ];
}
