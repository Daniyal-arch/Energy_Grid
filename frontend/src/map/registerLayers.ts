// Every unit from the national registers (GB, DK, SE, IE): one dot per unit or project, coloured by
// fuel and paler from operating to planning, sized by √MW. Nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

import { FUEL_COLOR } from "../lib/energy";
import { REGISTER_LAYERS, STATUS_ALPHA, registerKey, type RegisterFile, type RegisterPoint } from "../lib/registers";
import { inAreaCountry } from "../app/datasets";
import type { Frame } from "./build";

const colourOf = (g: string) => FUEL_COLOR[g === "wind_offshore" ? "wind" : g] ?? FUEL_COLOR.other;

export function registerLayers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  for (const [layer, cc] of Object.entries(REGISTER_LAYERS)) {
    if (!fr.layers[layer as keyof typeof fr.layers]) continue;
    const f = fr.files[registerKey(cc)] as RegisterFile | undefined;
    if (!f || !inAreaCountry(fr.area, cc)) continue;
    out.push(
      new ScatterplotLayer<RegisterPoint>({
        id: `reg:${cc}`,
        data: f.points,
        getPosition: (p) => [p[1], p[2]],
        getRadius: (p) => 2 + Math.sqrt(Math.max(0, p[4] ?? 0)) * 0.9,
        radiusUnits: "pixels",
        radiusMaxPixels: 16,
        getFillColor: (p) => [...colourOf(p[3]), STATUS_ALPHA[p[5]] ?? 160],
        stroked: true,
        getLineColor: [6, 7, 10, 160],
        lineWidthUnits: "pixels",
        getLineWidth: 0.4,
        pickable: true,
      }),
    );
  }
  return out;
}
