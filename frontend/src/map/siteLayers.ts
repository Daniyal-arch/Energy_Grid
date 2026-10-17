// "Check a site" on the map: the place, the radius the panel sums over, and a thin link to the
// nearest high-voltage line found in the tiles (lib/site.ts).

import type { Layer } from "@deck.gl/core";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";

import { SITE_RADIUS_KM, siteKey, useSiteLines, type LonLat, type NearLine } from "../lib/site";
import type { Frame } from "./build";

const SITE: [number, number, number] = [226, 232, 240];
const LINE: [number, number, number] = [236, 178, 120];

export function siteLayers(fr: Frame): Layer[] {
  const sel = fr.selection;
  if (sel?.kind !== "site") return [];
  const site: LonLat = [sel.lon, sel.lat];
  const { world, us } = useSiteLines.getState();
  const key = siteKey(site);
  const near = [us.key === key ? us.result?.nearest : null, world.key === key ? world.result?.nearest : null].filter((l): l is NearLine => !!l).sort((a, b) => a.km - b.km)[0];
  return [
    new ScatterplotLayer({
      id: "site-radius",
      data: [site],
      getPosition: (d: LonLat) => d,
      getRadius: SITE_RADIUS_KM * 1000,
      radiusUnits: "meters",
      filled: false,
      stroked: true,
      getLineColor: [...SITE, 70],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
    }),
    ...(near
      ? [
          new LineLayer({
            id: "site-link",
            data: [{ from: site, to: near.at }],
            getSourcePosition: (d: { from: LonLat }) => d.from,
            getTargetPosition: (d: { to: LonLat }) => d.to,
            getColor: [...LINE, 200],
            getWidth: 1.5,
            widthUnits: "pixels",
          }),
          new ScatterplotLayer({
            id: "site-line-point",
            data: [near.at],
            getPosition: (d: LonLat) => d,
            getRadius: 3,
            radiusUnits: "pixels",
            getFillColor: [...LINE, 255],
          }),
        ]
      : []),
    new ScatterplotLayer({
      id: "site-point",
      data: [site],
      getPosition: (d: LonLat) => d,
      getRadius: 6,
      radiusUnits: "pixels",
      filled: true,
      stroked: true,
      getFillColor: [8, 11, 17, 220],
      getLineColor: [...SITE, 255],
      lineWidthUnits: "pixels",
      getLineWidth: 2,
    }),
  ];
}
