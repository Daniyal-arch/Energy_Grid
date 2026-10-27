// Hydrogen projects (dots sized by MW, by stage) and planned gas and hydrogen infrastructure
// (ENTSOG publishes no positions: one ring per country at its label point, sized by the number
// of projects and split by kind like a donut, the count under the country's name). Nothing moves.

import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";

import type { CountriesFile } from "../app/types";
import { gasByCountry, gasColor, h2Color, h2Radius, type GasProjectsFile, type H2Project, type HydrogenFile } from "../lib/coming";
import { ISO3 } from "../lib/transition";
import type { Frame } from "./build";
import { memo } from "./memo";

const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;

export function comingLayers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  const h2 = fr.layers.hydrogen ? (fr.files.hydrogen as HydrogenFile | undefined) : undefined;
  if (h2)
    out.push(
      new ScatterplotLayer<H2Project>({
        id: "eu-hydrogen",
        data: h2.projects,
        getPosition: (p) => [p[8], p[9]],
        getRadius: (p) => h2Radius(p[4]),
        radiusUnits: "pixels",
        getFillColor: (p) => [...h2Color(h2, p), 190],
        stroked: true,
        getLineColor: [6, 7, 10, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  const gp = fr.layers.gasProjects ? (fr.files.gasProjects as GasProjectsFile | undefined) : undefined;
  const countries = fr.files.countries as CountriesFile | undefined;
  if (gp && countries) {
    const rows = memo("gasProjectRows", [gp, countries], () => {
      const by = gasByCountry(gp);
      return countries.countries.flatMap((c) => {
        const r = by[ISO3[c.iso] ?? ""];
        return r ? [{ iso3: ISO3[c.iso], name: c.name, at: c.label, ...r }] : [];
      });
    });
    // a donut per country: its ring split by kind in proportion to the projects (counted), drawn
    // as arcs whose radius in degrees follows the zoom so the ring keeps its size on screen
    const mpp = (40_075_016.686 * Math.cos((fr.centre[1] * Math.PI) / 180)) / (512 * 2 ** fr.zoom);
    const zk = Math.round(fr.zoom * 4) / 4;
    const arcs = memo("gasProjectArcs", [rows, zk], () =>
      rows.flatMap((d) => {
        const rPx = 6 + Math.sqrt(d.n) * 3;
        const rLat = (rPx * mpp) / 111_320;
        const rLon = rLat / Math.max(0.2, Math.cos((d.at[1] * Math.PI) / 180));
        const cats = Object.entries(d.byCat).sort((a, b) => b[1] - a[1]);
        let a0 = 0;
        return cats.map(([cat, n]) => {
          const a1 = a0 + (2 * Math.PI * n) / d.n;
          const steps = Math.max(2, Math.ceil(((a1 - a0) / (2 * Math.PI)) * 48));
          const gap = cats.length > 1 ? 0.06 : 0;
          const path: [number, number][] = [];
          for (let k = 0; k <= steps; k++) {
            const a = a0 + gap / 2 + ((a1 - a0 - gap) * k) / steps;
            path.push([d.at[0] + rLon * Math.sin(a), d.at[1] + rLat * Math.cos(a)]);
          }
          a0 = a1;
          return { d, cat, n, path };
        });
      }),
    );
    out.push(
      new PathLayer<(typeof arcs)[number]>({
        id: "eu-gas-projects",
        data: arcs,
        getPath: (x) => x.path,
        getColor: (x) => [...gasColor(x.cat), 235],
        getWidth: 4,
        widthUnits: "pixels",
        capRounded: false,
        pickable: true,
        parameters: ON_TOP,
      }),
      new TextLayer<(typeof rows)[number]>({
        id: "eu-gas-projects-count",
        data: rows,
        getPosition: (d) => d.at,
        getText: (d) => `${d.n} ${d.n === 1 ? "project" : "projects"}`,
        getSize: 10,
        getColor: [226, 232, 240, 230],
        getPixelOffset: [0, 13],
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        background: true,
        getBackgroundColor: [8, 10, 14, 170],
        backgroundPadding: [3, 1],
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}
