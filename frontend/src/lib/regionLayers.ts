// Live grids outside Europe drawn the same way: a bubble per region, a label, and moving
// arrows for the flows between regions. Region positions are map placements for reading.

import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";

import { FlowArrowLayer } from "./flowArrowLayer";
import { curvedPath, flowDistances } from "./flowLayers";

export interface RegionArc {
  from: string;
  to: string;
  mw: number;
  ts: string;
  path: [number, number][];
  timestamps: number[];
}
export interface RegionFlow {
  id: string;
  from: string;
  to: string;
  /** positive = from -> to */
  mw: number | null;
}

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** Arcs for the flows above `idleMw`, pointing the way the power goes. */
export function regionArcs(flows: RegionFlow[], points: Record<string, [number, number]>, ts: string, idleMw = 20): RegionArc[] {
  return flows.flatMap((f, n) => {
    if (f.mw == null || Math.abs(f.mw) < idleMw || !points[f.from] || !points[f.to]) return [];
    const [a, b] = f.mw > 0 ? [f.from, f.to] : [f.to, f.from];
    const path = curvedPath(points[a], points[b], 0.16, 30);
    return [{ from: a, to: b, mw: Math.abs(f.mw), ts, path, timestamps: flowDistances(path, false, n * 91_000) }];
  });
}

/** Casing + chevron arrows; `mwScale` sets how fast widths grow with the flow. */
export function regionFlowLayers(
  id: string,
  arcs: RegionArc[],
  clock: { phase: number; spacing: number },
  color: [number, number, number],
  mwScale: number,
) {
  return [
    new PathLayer<RegionArc>({
      id: `${id}-casing`,
      data: arcs,
      getPath: (d) => d.path,
      getColor: [4, 6, 10, 190],
      getWidth: (d) => 5 + Math.min(4, d.mw / (mwScale * 3)),
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      parameters: ON_TOP,
    }),
    new FlowArrowLayer<RegionArc>({
      id: `${id}-flows`,
      data: arcs,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: [...color, 240],
      getWidth: (d) => 16 + Math.min(12, d.mw / mwScale),
      getArrowStyle: (d) => [1.4 + Math.min(1.8, d.mw / (mwScale * 5)), 4.5 + Math.min(5, d.mw / (mwScale * 2)), 1],
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      pickable: true,
      phase: clock.phase,
      spacing: clock.spacing,
      strokePx: 2.4,
      lineAlpha: 0.85,
      parameters: {
        ...ON_TOP,
        blend: true,
        blendColorSrcFactor: "one",
        blendColorDstFactor: "one-minus-src-alpha",
        blendAlphaSrcFactor: "one",
        blendAlphaDstFactor: "one-minus-src-alpha",
      },
    }),
  ];
}

export interface RegionDot {
  id: string;
  at: [number, number];
  /** MW: sets the bubble size */
  mw: number;
  label: string;
}

/** A bubble sized by MW (square root) and a label above it. */
export function regionDotLayers(id: string, dots: RegionDot[], color: [number, number, number], showLabels: boolean) {
  return [
    new ScatterplotLayer<RegionDot>({
      id: `${id}-regions`,
      data: dots,
      getPosition: (d) => d.at,
      getRadius: (d) => 4 + Math.sqrt(Math.max(0, d.mw) / 1000) * 1.6,
      radiusUnits: "pixels",
      getFillColor: [...color, 70],
      stroked: true,
      getLineColor: [...color, 230],
      lineWidthUnits: "pixels",
      getLineWidth: 1.2,
      pickable: true,
      parameters: ON_TOP,
    }),
    new TextLayer<RegionDot>({
      id: `${id}-labels`,
      data: showLabels ? dots : [],
      getPosition: (d) => d.at,
      getText: (d) => d.label,
      getSize: 10.5,
      getColor: [255, 236, 210, 255],
      fontFamily: "Inter, system-ui, sans-serif",
      fontWeight: 700,
      background: true,
      getBackgroundColor: [6, 9, 14, 200],
      backgroundPadding: [4, 2],
      getPixelOffset: [0, -14],
      parameters: ON_TOP,
    }),
  ];
}
