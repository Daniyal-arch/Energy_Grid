// US solar farms (USPVDB): a dot per array sized by its AC capacity, and from zoom 7.5 the
// array's outline as digitised from aerial imagery. Calm: solar yellow, nothing moves.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { pairs, unitVector } from "../app/geo";
import { FUEL_COLOR } from "../lib/energy";
import { SOLAR_OUTLINE_ZOOM, type UsSolarFile, type UsSolarOutlinesFile } from "../lib/usSolar";
import type { Frame } from "./build";
import { memo } from "./memo";

const SUN = FUEL_COLOR.solar;

interface SolarShape {
  k: number;
  polygon: [number, number][][];
}

export function usSolarLayers(fr: Frame): Layer[] {
  const f = fr.layers.solarUS ? (fr.files.usSolar as UsSolarFile | undefined) : undefined;
  if (!f) return [];
  const outlines = fr.zoom >= SOLAR_OUTLINE_ZOOM ? (fr.files.usSolarOutlines as UsSolarOutlinesFile | undefined) : undefined;
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = memo("solarFacing", [f, fr.camKey], () =>
    f.sites.flatMap((s, k) => {
      if (s[0] == null || s[1] == null) return [];
      const v = unitVector(s[0], s[1]);
      return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.1 ? [k] : [];
    }),
  );
  if (outlines && outlines.release === f.release) {
    const shapes = memo("solarShapes", [outlines], () => outlines.polygons.flatMap((polys, k) => polys.map((rings) => ({ k, polygon: rings.map(pairs) }))));
    return [
      new SolidPolygonLayer<SolarShape>({
        id: "us-solar-areas",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: [...SUN, 140],
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 60],
      }),
      new PathLayer<SolarShape>({
        id: "us-solar-lines",
        data: shapes,
        getPath: (d) => d.polygon[0],
        getColor: [...SUN, 220],
        widthUnits: "pixels",
        getWidth: 0.8,
      }),
    ];
  }
  return [
    new ScatterplotLayer<number>({
      id: "us-solar",
      data: facing,
      getPosition: (k) => [f.sites[k][0] as number, f.sites[k][1] as number],
      radiusUnits: "pixels",
      // area follows the AC capacity: 1 MW 1 px, 100 MW 3.5 px, 690 MW 9 px
      getRadius: (k) => Math.max(1, Math.sqrt(f.sites[k][2] ?? 1) * 0.35),
      getFillColor: [...SUN, 190],
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
    }),
  ];
}
