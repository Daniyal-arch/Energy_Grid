// US public EV fast chargers (NREL AFDC): a calm dot per DC fast station, area by its DC
// fast ports. Level-2-only stations are counted in the card, not drawn.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

import { unitVector } from "../app/geo";
import { EV_COLOR, type EvChargersFile } from "../lib/evChargers";
import type { Frame } from "./build";
import { memo } from "./memo";

export function evLayers(fr: Frame): Layer[] {
  const f = fr.layers.evChargersUS ? (fr.files.evChargers as EvChargersFile | undefined) : undefined;
  if (!f) return [];
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = memo("evFacing", [f, fr.camKey], () =>
    f.points.flatMap((p, k) => {
      const v = unitVector(p[0], p[1]);
      return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.1 ? [k] : [];
    }),
  );
  return [
    new ScatterplotLayer<number>({
      id: "us-ev",
      data: facing,
      getPosition: (k) => [f.points[k][0], f.points[k][1]],
      radiusUnits: "pixels",
      // area follows the DC fast ports: 1 port 1.2 px, 8 ports 2.5 px, 40 ports 5.7 px
      getRadius: (k) => Math.max(1.2, Math.sqrt(f.points[k][2]) * 0.9),
      radiusMinPixels: 1,
      getFillColor: [...EV_COLOR, 170],
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
    }),
  ];
}
