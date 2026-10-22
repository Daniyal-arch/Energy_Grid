// The dashboard's area: outside it the map is dimmed, its outline drawn over everything; while an
// area is being drawn, its corners and edges. Also a dataset's coverage (the countries it holds data
// for, tinted in its colour while the Datasets panel shows its details). Calm: no motion.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { shapeOf } from "../app/areaShape";
import { DATASET_BY_ID, coverageIso3 } from "../app/datasets";
import type { CountriesFile, WorldFile } from "../app/types";
import type { AreaShape } from "../lib/area";
import type { Frame } from "./build";
import { memo } from "./memo";

type Ring = [number, number][];
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
const EDGE: [number, number, number] = [255, 246, 230];

const rgbOf = (css: string): [number, number, number] => {
  const m = css.match(/\d+/g)?.map(Number) ?? [150, 160, 180];
  return [m[0], m[1], m[2]];
};
const pairs = (flat: number[]): Ring => Array.from({ length: flat.length / 2 }, (_, i) => [flat[2 * i], flat[2 * i + 1]]);

function shapesOf(w: WorldFile, codes: Set<string> | null): { polygon: Ring[] }[] {
  return w.features.filter((f) => !codes || codes.has(f.properties.iso3)).flatMap((f) => f.geometry.coordinates.map((poly) => ({ polygon: poly as Ring[] })));
}

/** Polygons drawable as holes: those crossing the date line (Alaska's Aleutians) are left out. */
const holesOf = (s: AreaShape) => s.polygons.filter((_, k) => s.boxes[k][2] - s.boxes[k][0] < 180);

/** A frame around the area with the area cut out: everything around it is dimmed. */
function maskOf(s: AreaShape): Ring[] {
  const holes = holesOf(s);
  const boxes = s.polygons.map((_, k) => s.boxes[k]).filter((b) => b[2] - b[0] < 180);
  const x0 = Math.min(...boxes.map((b) => b[0]));
  const y0 = Math.min(...boxes.map((b) => b[1]));
  const x1 = Math.max(...boxes.map((b) => b[2]));
  const y1 = Math.max(...boxes.map((b) => b[3]));
  const pad = Math.max(8, (x1 - x0) * 1.5, (y1 - y0) * 1.5);
  const X0 = Math.max(-180, x0 - pad);
  const X1 = Math.min(180, x1 + pad);
  const Y0 = Math.max(-85, y0 - pad);
  const Y1 = Math.min(85, y1 + pad);
  return [
    [
      [X0, Y0],
      [X1, Y0],
      [X1, Y1],
      [X0, Y1],
      [X0, Y0],
    ],
    ...holes.map((p) => pairs(p[0])),
  ];
}

export function areaLayers(fr: Frame): Layer[] {
  const w = fr.files.world as WorldFile | undefined;
  const out: Layer[] = [];
  const ds = fr.coverageOf ? DATASET_BY_ID.get(fr.coverageOf) : undefined;
  if (ds && w) {
    const codes = coverageIso3(ds);
    const shapes = memo("coverageShapes", [w, ds], () => shapesOf(w, codes));
    const c = rgbOf(ds.color);
    out.push(
      new SolidPolygonLayer<{ polygon: Ring[] }>({ id: "coverage-fill", data: shapes, getPolygon: (d) => d.polygon, getFillColor: [...c, 46], parameters: ON_TOP }),
      new PathLayer<Ring>({
        id: "coverage-outline",
        data: memo("coverageRings", [shapes], () => shapes.map((s) => s.polygon[0])),
        getPath: (d) => d,
        getColor: [...c, 150],
        getWidth: 1,
        widthUnits: "pixels",
        parameters: ON_TOP,
      }),
    );
  }
  // the area (not while a country is selected: the country panel outlines its own)
  const shape = fr.selection ? null : shapeOf(fr.area, fr.drawn, w, fr.files.countries as CountriesFile | undefined);
  if (shape) {
    const mask = memo("areaMask", [shape.key], () => [{ polygon: maskOf(shape) }]);
    const rings = memo("areaRings", [shape.key], () => holesOf(shape).map((p) => pairs(p[0])));
    out.push(
      new SolidPolygonLayer<{ polygon: Ring[] }>({ id: "area-mask", data: mask, getPolygon: (d) => d.polygon, getFillColor: [5, 7, 11, 150], parameters: ON_TOP }),
      new PathLayer<Ring>({ id: "area-glow", data: rings, getPath: (d) => d, getColor: [...EDGE, 40], getWidth: 6, widthUnits: "pixels", jointRounded: true, parameters: ON_TOP }),
      new PathLayer<Ring>({ id: "area-outline", data: rings, getPath: (d) => d, getColor: [...EDGE, 210], getWidth: 1.4, widthUnits: "pixels", jointRounded: true, parameters: ON_TOP }),
    );
  }
  // an area being drawn: its edges, closed with a faint one back to the first corner
  const d = fr.drawing;
  if (d && d.length) {
    const open: Ring = d.map((p) => [p[0], p[1]]);
    // from three corners the area fills in as it grows
    if (d.length >= 3)
      out.push(
        new SolidPolygonLayer<{ polygon: Ring }>({
          id: "draw-fill",
          data: [{ polygon: [...open, open[0]] }],
          getPolygon: (x) => x.polygon,
          getFillColor: [120, 190, 255, 55],
          parameters: ON_TOP,
          updateTriggers: { getPolygon: [d.length] },
        }),
      );
    out.push(
      new PathLayer<Ring>({ id: "draw-edges", data: [open], getPath: (x) => x, getColor: [...EDGE, 230], getWidth: 1.6, widthUnits: "pixels", parameters: ON_TOP }),
      ...(d.length >= 3
        ? [new PathLayer<Ring>({ id: "draw-close", data: [[open[open.length - 1], open[0]]], getPath: (x) => x, getColor: [...EDGE, 90], getWidth: 1, widthUnits: "pixels", parameters: ON_TOP })]
        : []),
      new ScatterplotLayer<[number, number]>({
        id: "draw-corners",
        data: open,
        getPosition: (p) => p,
        radiusUnits: "pixels",
        getRadius: (_p, { index }) => (index === 0 ? 5 : 3.5),
        getFillColor: [12, 15, 21, 255],
        getLineColor: [...EDGE, 255],
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}
