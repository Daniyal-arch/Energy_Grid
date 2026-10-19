// Room to connect, more countries (the "Grid capacity" layer): French substations by the S3REnR
// capacity still to allocate, Irish stations by the demand or generation capacity available,
// Italian regions by the GW requested to connect. Nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";

import { pairs } from "../app/geo";
import { IT_COLOR, frNumber, ieRoom, itClass, itTotals, roomColor, type FrFile, type FrSite, type IeFile, type IeStation, type ItFile } from "../lib/connectMore";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

export function connectMoreLayers(fr: Frame): Layer[] {
  if (!fr.layers.connect) return [];
  const side = fr.connectSide;
  const out: Layer[] = [];
  const it = fr.files.connectIT as ItFile | undefined;
  if (it && side === "feedin") {
    const areas = memo("itAreas", [it], () => {
      const tot = itTotals(it);
      return Object.entries(it.nuts2).flatMap(([reg, ids]) =>
        ids.flatMap((id) => (it.shapes[id] ?? []).map((rings) => ({ reg, mw: (tot[reg]?.fer ?? 0) + (tot[reg]?.storage ?? 0), polygon: rings.map(pairs) }))),
      );
    });
    out.push(
      new SolidPolygonLayer<(typeof areas)[number]>({
        id: "eu-connect-it",
        data: areas,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => [...IT_COLOR[itClass(d.mw)], 120],
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
        parameters: ON_TOP,
      }),
    );
  }
  const frf = fr.files.connectFR as FrFile | undefined;
  if (frf && side === "feedin")
    out.push(
      new ScatterplotLayer<FrSite>({
        id: "eu-connect-fr",
        data: frf.sites,
        getPosition: (s) => [s[3], s[4]],
        getRadius: 3,
        radiusUnits: "pixels",
        radiusMinPixels: 2,
        getFillColor: (s) => [...roomColor(frNumber(frf, s, "INFO_NA")), 210],
        stroked: true,
        getLineColor: [6, 7, 10, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.5,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  const ie = fr.files.connectIE as IeFile | undefined;
  if (ie)
    out.push(
      new ScatterplotLayer<IeStation>({
        id: "eu-connect-ie",
        data: ie.stations,
        getPosition: (s) => [s[3], s[4]],
        getRadius: (s) => (s[1] === "110 kV" ? 5 : s[1] === "38 kV" ? 3.5 : 2.5),
        radiusUnits: "pixels",
        getFillColor: (s) => [...roomColor(ieRoom(ie, s, side)), 210],
        updateTriggers: { getFillColor: [side] },
        stroked: true,
        getLineColor: [6, 7, 10, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.5,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  return out;
}
