// Risk layers: US counties shaded by the customer-hours they spent without power in the newest
// year (EAGLE-I), and river basins coloured by WRI Aqueduct's category of the chosen water
// risk. Calm: flat fills, nothing moves; only the side of the globe facing the camera.

import type { Layer } from "@deck.gl/core";
import { PathLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { stopColor } from "../app/colors";
import { pairs, unitVector } from "../app/geo";
import { OUTAGE_STOPS, WATER_COLOR, newestYear, type UsCountiesFile, type UsOutagesFile, type WaterFile, type WaterIndicator } from "../lib/risk";
import type { RGB } from "../lib/theme";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

export interface CountyShape {
  code: string;
  polygon: [number, number][][];
}
export interface BasinShape {
  k: number;
  polygon: [number, number][][];
}

export function riskLayers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = (lon: number, lat: number) => {
    const v = unitVector(lon, lat);
    return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.1;
  };

  // ------------------------------------------------------------ water risk per basin (WRI Aqueduct 4.0)
  const water = fr.layers.water ? (fr.files.water as WaterFile | undefined) : undefined;
  if (water) {
    const ind: WaterIndicator = fr.waterIndicator;
    const col = water.order.indexOf(ind);
    const shapes = memo("waterShapes", [water, fr.camKey], () =>
      water.basins.flatMap((b, k) =>
        b.polygons.filter((rings) => facing(rings[0][0], rings[0][1])).map((rings) => ({ k, polygon: rings.map(pairs) })),
      ),
    );
    out.push(
      new SolidPolygonLayer<BasinShape>({
        id: "w-water",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => {
          const cat = water.basins[d.k].c[col];
          return cat == null ? [0, 0, 0, 0] : [...(WATER_COLOR[String(cat)] ?? ([90, 90, 90] as RGB)), 120];
        },
        updateTriggers: { getFillColor: [ind] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
        parameters: ON_TOP,
      }),
    );
  }

  // ------------------------------------------------------------ US outages per county (EAGLE-I)
  const outages = fr.layers.usOutages ? (fr.files.usOutages as UsOutagesFile | undefined) : undefined;
  const counties = fr.files.usCounties as UsCountiesFile | undefined;
  if (outages && counties) {
    const { k: yk } = newestYear(outages);
    const shapes = memo("countyShapes", [counties], () =>
      counties.counties.flatMap((cty) => cty.polygons.map((rings) => ({ code: cty.code, polygon: rings.map(pairs) }))),
    );
    out.push(
      new SolidPolygonLayer<CountyShape>({
        id: "us-outages",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => {
          const v = outages.counties[d.code]?.[yk];
          return [...((v != null && v > 0 && stopColor(OUTAGE_STOPS, Math.log10(v))) || ([24, 28, 36] as RGB)), 225];
        },
        updateTriggers: { getFillColor: [outages] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
        parameters: ON_TOP,
      }),
      new PathLayer<CountyShape>({
        id: "us-outages-lines",
        data: shapes,
        getPath: (d) => d.polygon[0],
        getColor: [8, 10, 14, 120],
        widthUnits: "pixels",
        getWidth: 0.4,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}
