// The Grid capacity layer in one symbology (brief 23): every operator's records from
// connect/harmonised.json, nodes as dots and areas as outlines with a light fill, the same four
// class colours everywhere; dot area by the free MW published for the chosen side (new generation
// or new demand), a fixed small dot where none is published.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { H, H_COLOR, H_NO_CLASS, hRadius, pairsOf, sideOf, type HFile, type HRow } from "../lib/connectH";
import { inAreaCountry } from "../app/datasets";
import type { CountriesFile } from "../app/types";
import type { CoverageFile } from "../lib/coverage";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

/** one outline part: the row and its first ring as [x, y] pairs */
type Part = { r: HRow; ring: [number, number][] };

export function connectHLayers(fr: Frame): Layer[] {
  const f = fr.layers.connect ? (fr.files.connectH as HFile | undefined) : undefined;
  if (!f) return [];
  const side = fr.connectSide;
  const nodes = memo("connectHNodes", [f], () => f.rows.filter((r) => r[H.kind] === "node" && r[H.lon] != null && r[H.lat] != null));
  const parts = memo("connectHParts", [f], () =>
    f.rows.flatMap((r) => (r[H.kind] === "area" && r[H.polygon] ? r[H.polygon]!.map((poly) => ({ r, ring: pairsOf(poly[0]) })) : [])),
  );
  const colour = (r: HRow) => {
    const c = sideOf(r, side).cls;
    return c ? H_COLOR[c] : H_NO_CLASS;
  };
  // nothing published for this side (neither class nor value): a faint dot, so the operator's
  // nodes stay visible without suggesting a value
  const silent = (r: HRow) => {
    const v = sideOf(r, side);
    return v.cls == null && v.mw == null && v.mva == null;
  };
  return [
    new SolidPolygonLayer<Part>({
      id: "eu-connect-h-areas",
      data: parts,
      getPolygon: (d) => d.ring,
      getFillColor: (d) => [...colour(d.r), 60],
      updateTriggers: { getFillColor: [side] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 40],
      parameters: ON_TOP,
    }),
    new PathLayer<Part>({
      id: "eu-connect-h-outlines",
      data: parts,
      getPath: (d) => [...d.ring, d.ring[0]],
      getColor: (d) => [...colour(d.r), 190],
      updateTriggers: { getColor: [side] },
      getWidth: 1,
      widthUnits: "pixels",
      parameters: ON_TOP,
    }),
    new ScatterplotLayer<HRow>({
      id: "eu-connect-h",
      data: nodes,
      getPosition: (r) => [r[H.lon]!, r[H.lat]!],
      getRadius: (r) => (silent(r) ? 1.5 : hRadius(sideOf(r, side).mw)),
      radiusUnits: "pixels",
      getFillColor: (r) => [...colour(r), silent(r) ? 60 : 200],
      stroked: true,
      getLineColor: (r) => [6, 7, 10, silent(r) ? 0 : 200],
      lineWidthUnits: "pixels",
      getLineWidth: 0.5,
      updateTriggers: { getRadius: [side], getFillColor: [side], getLineColor: [side] },
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
      parameters: ON_TOP,
    }),
  ];
}

type Gap = { iso: string; name: string; polygons: [number, number][][][]; at: [number, number] | null; why: string; note: string };

/** Why a country has no rows, from the coverage registry (data/coverage.yaml; EU-27, the UK, the US, the neighbours). */
function gapReason(cov: CoverageFile | undefined, iso: string): { why: string; note: string } {
  const cell = cov?.countries[iso]?.connect;
  if (!cell) return { why: "no published data found", note: "Outside the coverage registry (EU-27, the UK, the US and the EU's neighbours); no operator file found so far." };
  const note = cell.note ?? "";
  if (/(403|451)|Cloudflare|bot check|resets the connection/i.test(note)) return { why: "operators' sites refuse automated downloads", note };
  return { why: "not published by its operators", note };
}
/** Grey for "no data": darker than the land, so it reads as absent, not as a class. */
const GAP_FILL: [number, number, number, number] = [10, 12, 17, 215];

/** Where no grid operator publishes room to connect: Europe's countries without a row in the
 *  harmonised file, darkened and labelled, so an empty country is not read as "no capacity". */
export function capacityGapLayers(fr: Frame): Layer[] {
  const on = fr.layers.connect || fr.styled.some(([d]) => d === "capacity");
  const f = fr.files.connectH as HFile | undefined;
  const c = fr.files.countries as CountriesFile | undefined;
  const cov = fr.files.coverage as CoverageFile | undefined;
  if (!on || !f || !c) return [];
  const gaps = memo("connectHGaps", [f, c, cov], () => {
    const have = new Set(f.operators.map((o) => o.cc));
    return c.countries
      .filter((x) => !have.has(x.iso))
      .map<Gap>((x) => ({
        iso: x.iso,
        name: x.name,
        polygons: x.polygons.map((rings) => rings.map(pairsOf)),
        at: (x.label as [number, number] | undefined) ?? null,
        ...gapReason(cov, x.iso),
      }));
  });
  const shown = memo("connectHGapsShown", [gaps, fr.area], () => (fr.area ? gaps.filter((g) => inAreaCountry(fr.area, g.iso)) : gaps));
  const polys = memo("connectHGapPolys", [shown], () => shown.flatMap((g) => g.polygons.map((polygon) => ({ g, polygon }))));
  return [
    new SolidPolygonLayer<{ g: Gap; polygon: [number, number][][] }>({
      id: "connect-gaps",
      data: polys,
      getPolygon: (d) => d.polygon,
      getFillColor: GAP_FILL,
      pickable: true,
      parameters: ON_TOP,
    }),
    new TextLayer<Gap>({
      id: "connect-gaps-label",
      data: shown.filter((g) => g.at),
      getPosition: (g) => g.at!,
      getText: (g) => g.why,
      getSize: 10,
      getColor: [150, 156, 170, 220],
      getPixelOffset: [0, 14],
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      parameters: ON_TOP,
    }),
  ];
}
