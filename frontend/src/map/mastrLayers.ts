// Germany's every unit (Marktstammdatenregister): municipalities shaded by the operating MW of
// the chosen technology, and units of 1 MW and more as dots from zoom 6. Calm, nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { stopColor } from "../app/colors";
import { pairs } from "../app/geo";
import { MASTR_COLOR, MASTR_STOPS, MASTR_UNIT_ZOOM, type MastrMuniFile, type MastrTech, type MastrUnitsFile } from "../lib/mastr";
import type { RGB } from "../lib/theme";
import { inAreaCountry } from "../app/datasets";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

export interface GemeindeShape {
  k: number;
  polygon: [number, number][][];
}

export function mastrLayers(fr: Frame): Layer[] {
  if (!fr.layers.mastrDE || !inAreaCountry(fr.area, "DE")) return [];
  const out: Layer[] = [];
  const muni = fr.files.mastrMuni as MastrMuniFile | undefined;
  const tech: MastrTech = fr.mastrTech;
  if (muni) {
    const col = muni.techs.indexOf(tech);
    const shapes = memo("mastrShapes", [muni], () =>
      muni.gemeinden.flatMap((g, k) => g.polygons.map((rings) => ({ k, polygon: rings.map(pairs) }))),
    );
    out.push(
      new SolidPolygonLayer<GemeindeShape>({
        id: "de-mastr-muni",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => {
          const mw = col >= 0 ? muni.gemeinden[d.k].mw[col] : 0;
          return [...((mw > 0 && stopColor(MASTR_STOPS, Math.log10(mw))) || ([22, 25, 32] as RGB)), 210];
        },
        updateTriggers: { getFillColor: [tech] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
        parameters: ON_TOP,
      }),
    );
  }
  const units = fr.files.mastrUnits as MastrUnitsFile | undefined;
  if (units && fr.zoom >= MASTR_UNIT_ZOOM) {
    out.push(
      new ScatterplotLayer<MastrUnitsFile["units"][number]>({
        id: "de-mastr-units",
        data: units.units,
        getPosition: (u) => [u[0], u[1]],
        getRadius: (u) => Math.min(10, 1.2 + Math.sqrt(u[3]) * 0.5),
        radiusUnits: "pixels",
        getFillColor: (u) => [...(MASTR_COLOR[units.techs[u[2]]] ?? MASTR_COLOR.other), 200],
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
