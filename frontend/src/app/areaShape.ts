// The dashboard's area as one shape, whatever it is: countries (Europe's detailed outlines where
// the map has them, the world's coarse ones elsewhere), a drawn polygon or a circle (a city).

import { useMemo } from "react";

import { makeShape, shapeOfSpec, type AreaShape, type AreaSpec } from "../lib/area";
import { ISO3 } from "../lib/transition";
import { useFile } from "./data";
import { useApp } from "./store";
import type { CountriesFile, WorldFile } from "./types";

const ISO2_OF_3 = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));

/** Countries (ISO alpha-3) as one shape; null until the outlines have loaded. */
export function countriesShape(codes: string[], world: WorldFile | undefined, countries: CountriesFile | undefined): AreaShape | null {
  if (!world) return null;
  const polygons: number[][][] = [];
  const names: string[] = [];
  for (const code of codes) {
    const eu = countries?.countries.find((c) => c.iso === ISO2_OF_3[code]);
    const w = world.features.find((f) => f.properties.iso3 === code);
    if (eu) polygons.push(...eu.polygons);
    else if (w) polygons.push(...w.geometry.coordinates.map((poly) => poly.map((ring) => ring.flat())));
    else continue;
    names.push(eu?.name ?? w?.properties.name ?? code);
  }
  if (!polygons.length) return null;
  const label = names.length <= 3 ? names.join(", ") : `${names.length} countries`;
  return makeShape("countries", `k:${codes.join(",")}`, label, polygons, codes);
}

const memo = new Map<string, AreaShape>();
/** The shape of an area (countries list or drawn spec), cached by its key. */
export function shapeOf(area: string[] | null, drawn: AreaSpec | null, world?: WorldFile, countries?: CountriesFile): AreaShape | null {
  const key = drawn ? JSON.stringify(drawn) : area?.length ? `k:${area.join(",")}|${!!countries}` : "";
  if (!key) return null;
  const hit = memo.get(key);
  if (hit) return hit;
  const s = drawn ? shapeOfSpec(drawn) : countriesShape(area!, world, countries);
  if (s) {
    if (memo.size > 40) memo.clear();
    memo.set(key, s);
  }
  return s;
}

/** The area the dashboard counts in: the country shown (a click on the map), else the dashboard's
 *  drawn area or countries; null when there is none. `pending` while outlines load. */
export function useAreaShape(iso3?: string): { shape: AreaShape | null; pending: boolean } {
  const area = useApp((s) => s.area);
  const drawn = useApp((s) => s.drawn);
  const needs = !!iso3 || !!area?.length;
  const world = useFile<WorldFile>(needs ? "world" : null);
  const countries = useFile<CountriesFile>(needs ? "countries" : null);
  return useMemo(() => {
    if (iso3) return { shape: shapeOf([iso3], null, world, countries), pending: !world };
    const shape = shapeOf(area, drawn, world, countries);
    return { shape, pending: !shape && !!area?.length };
  }, [iso3, area, drawn, world, countries]);
}
