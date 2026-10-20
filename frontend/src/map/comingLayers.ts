// Hydrogen projects (dots sized by MW, by stage) and planned gas and hydrogen infrastructure
// (ENTSOG publishes no positions: one ring per country at its label point, sized by the number
// of projects, coloured by the most common category). Nothing moves.

import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

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
    out.push(
      new ScatterplotLayer<(typeof rows)[number]>({
        id: "eu-gas-projects",
        data: rows,
        getPosition: (d) => d.at,
        getRadius: (d) => 5 + Math.sqrt(d.n) * 3,
        radiusUnits: "pixels",
        filled: false,
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 1.6,
        getLineColor: (d) => [...gasColor(d.top), 220],
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}
