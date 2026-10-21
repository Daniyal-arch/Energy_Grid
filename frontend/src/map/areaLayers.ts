// The dashboard's area (its countries outlined) and a dataset's coverage (the countries it holds
// data for, tinted in its colour while the Layers panel shows its details). Calm: no motion,
// outlines over everything else, a light fill under the data.

import type { Layer } from "@deck.gl/core";
import { PathLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { DATASET_BY_ID, coverageIso3 } from "../app/datasets";
import type { WorldFile } from "../app/types";
import type { Frame } from "./build";
import { memo } from "./memo";

type Ring = [number, number][];
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

const rgbOf = (css: string): [number, number, number] => {
  const m = css.match(/\d+/g)?.map(Number) ?? [150, 160, 180];
  return [m[0], m[1], m[2]];
};

function shapesOf(w: WorldFile, codes: Set<string> | null): { polygon: Ring[] }[] {
  return w.features
    .filter((f) => !codes || codes.has(f.properties.iso3))
    .flatMap((f) => f.geometry.coordinates.map((poly) => ({ polygon: poly as Ring[] })));
}

export function areaLayers(fr: Frame): Layer[] {
  const w = fr.files.world as WorldFile | undefined;
  if (!w) return [];
  const out: Layer[] = [];
  const ds = fr.coverageOf ? DATASET_BY_ID.get(fr.coverageOf) : undefined;
  if (ds) {
    const codes = coverageIso3(ds);
    const shapes = memo("coverageShapes", [w, ds], () => shapesOf(w, codes));
    const c = rgbOf(ds.color);
    out.push(
      new SolidPolygonLayer<{ polygon: Ring[] }>({
        id: "coverage-fill",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: [...c, 46],
        parameters: ON_TOP,
      }),
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
  if (fr.area?.length) {
    const key = fr.area.join(",");
    const rings = memo("areaRings", [w, key], () => shapesOf(w, new Set(fr.area)).map((s) => s.polygon[0]));
    out.push(
      new PathLayer<Ring>({
        id: "area-glow",
        data: rings,
        getPath: (d) => d,
        getColor: [255, 246, 230, 40],
        getWidth: 6,
        widthUnits: "pixels",
        jointRounded: true,
        parameters: ON_TOP,
      }),
      new PathLayer<Ring>({
        id: "area-outline",
        data: rings,
        getPath: (d) => d,
        getColor: [255, 246, 230, 200],
        getWidth: 1.4,
        widthUnits: "pixels",
        jointRounded: true,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}
