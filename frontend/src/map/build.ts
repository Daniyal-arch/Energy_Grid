// All deck.gl layers of the map, built from the app state and the loaded files. Called by the
// render loop (not by React); derived data is memoised, so per frame only the animation
// uniforms change.

import { COORDINATE_SYSTEM, type Layer } from "@deck.gl/core";
import { PathStyleExtension, type PathStyleExtensionProps } from "@deck.gl/extensions";
import { BitmapLayer, ColumnLayer, LineLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { FUEL_COLOR, STACK_ORDER, power } from "../lib/energy";
import { FlowArrowLayer } from "../lib/flowArrowLayer";
import { curvedPath, flowDistances } from "../lib/flowLayers";
import { ZONE_POINT, priceMetricById, type PricesFile } from "../lib/prices";
import { MONEY, usd, type FinanceFile, type FinanceFlow, type FinanceProject } from "../lib/finance";
import { GEM_PIPES, GEM_POINTS, IDLE, type GemPipesFile, type GemPointsFile, type GemPoint } from "../lib/gem";
import { IRENA_STOPS, irenaK, irenaMetricById, irenaScale, irenaValue, formatGw, type IrenaFile, type IrenaMetricId } from "../lib/irena";
import { regionArcs, regionDotLayers, regionFlowLayers } from "../lib/regionLayers";
import type { RGB } from "../lib/theme";
import { ISO3, formatMetric, metricById, metricColor, type MetricId, type TransitionFile } from "../lib/transition";
import type { WindField, WindPaths } from "../lib/windParticles";
import {
  BR_COLOR,
  BR_POINT,
  DC_COLOR,
  NEM_POINT,
  ON_COLOR,
  ON_POINT,
  TW_COLOR,
  TW_POINT,
  US_COLOR,
  US_POINT,
  latest,
  type AemoFile,
  type BrazilFile,
  type DataCentresFile,
  type OntarioFile,
  type TaiwanFile,
  type UsFile,
  type WorldStatsFile,
} from "../lib/world";
import { ACCESS_STOPS } from "../lib/world";
import { PLANT_TYPE_COLOR, type WorldPlantsFile } from "../lib/worldPlants";
import {
  BORDER,
  CABLE_STYLE,
  COAST,
  FLOW,
  GAS,
  GAS_PIPE,
  HVDC,
  MULTI_ZONE,
  NO_DATA,
  OFFLINE_STOPS,
  PLAIN_LAND,
  PRICE_STOPS,
  SHARE_STOPS,
  SUBSTATION,
  TR_NO_DATA,
  VOLTAGE_BANDS,
  band,
  dim,
  lift,
  stopColor,
} from "../app/colors";
import { TOWER_LABEL_MW, TOWER_M_PER_MW, TOWER_RADIUS_M, NIGHT_BOUNDS } from "../app/day";
import { PRICE_GLOW_STOPS } from "../app/colors";
import { ANCHOR, BEAM_MIN_MW, HEX_KM, SMALL, angularDistance, bbox, hexBins, pairs, unitVector } from "../app/geo";
import type { ColourId, LayerId, PlantStatus, Selection, TimeMode } from "../app/store";
import type {
  Arc,
  Cable,
  CountriesFile,
  Country,
  DayFile,
  FlowsFile,
  GasFile,
  GasSite,
  GridFile,
  Hex,
  OutagesFile,
  Plant,
  PlantsFile,
  Shape,
  StatsFile,
  Substation,
  TowerPiece,
  Unit,
} from "../app/types";
import { memo, NONE } from "./memo";

export interface Frame {
  mode: TimeMode;
  layers: Record<LayerId, boolean>;
  colour: ColourId;
  plantStatus: PlantStatus;
  plantStyle: "bars" | "beams";
  selection: Selection | null;
  files: Record<string, unknown>;
  zoom: number;
  centre: [number, number];
  /** rounded camera centre: far-side filtering is redone only when it changes */
  camKey: string;
  clock: { phase: number; spacing: number };
  day: DayFile | null;
  /** fractional slot of the 24 h clock */
  daySlot: number;
  yearK: number;
  isMobile: boolean;
  wind: { field: WindField | null; paths: WindPaths } | null;
  /** sun altitude over Central Europe (24 h mode), degrees */
  sunAlt: number;
  /** milliseconds, for pulses and ripples (drawing only) */
  now: number;
  sun: { image: HTMLCanvasElement | null; next: HTMLCanvasElement | null; fade: number; bounds: [number, number, number, number] } | null;
  night: ImageBitmap | null;
}

const IDLE_MW = 20;
const LABEL_MW = 1000; // arcs from this size carry a GW label
const DETAIL_ZOOM = 5; // below: plants >= 50 MW only
const GAS_DETAIL_ZOOM = 5.5;
const COLUMN_MIN_MW = 10;
const COLUMN_M_PER_SQRT_MW = 3100;
const HEX_M_PER_SQRT_MW = 450;
const BEAM_BANDS = [
  [0, 0.4, 255],
  [0.4, 0.72, 175],
  [0.72, 1, 80],
] as const;
const ON_TOP = { depthCompare: "always", depthWriteEnabled: false } as const;
const ADD = {
  ...ON_TOP,
  blend: true,
  blendColorSrcFactor: "src-alpha",
  blendColorDstFactor: "one",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;
const OVER = {
  blend: true,
  blendColorSrcFactor: "one",
  blendColorDstFactor: "one-minus-src-alpha",
  blendAlphaSrcFactor: "one",
  blendAlphaDstFactor: "one-minus-src-alpha",
} as const;

const TR_METRIC: Partial<Record<ColourId, MetricId>> = {
  tr_renewables: "renewables",
  tr_wind_solar: "wind_solar",
  tr_coal: "coal",
  tr_intensity: "intensity",
};
const IR_METRIC: Partial<Record<ColourId, IrenaMetricId>> = { ir_solar: "solar", ir_wind: "wind" };
const PR_METRIC: Partial<Record<ColourId, "negative" | "mean" | "solar" | "wind">> = {
  pr_negative: "negative",
  pr_mean: "mean",
  pr_solar: "solar",
  pr_wind: "wind",
};

export const selectedIso2 = (sel: Selection | null) => (sel?.kind === "country" ? (sel.iso2 ?? null) : null);

/** Fill colour of a mapped European country for the chosen colour. */
export function countryColour(fr: Frame, iso: string): RGB {
  const f = fr.files;
  const k = Math.floor(fr.daySlot);
  switch (fr.colour) {
    case "renewable": {
      const share = fr.day ? fr.day.countries[iso]?.renewable_share[k] : (f.stats as StatsFile | undefined)?.countries[iso]?.renewable_share_of_generation;
      return stopColor(SHARE_STOPS, share) ?? NO_DATA;
    }
    case "price": {
      const zones = fr.day
        ? Object.values(fr.day.prices).filter((z) => z.country === iso).map((z) => z.values[k])
        : Object.values((f.stats as StatsFile | undefined)?.day_ahead_prices ?? {})
            .filter((z) => z.country === iso)
            .map((z) => z.eur_mwh);
      if (zones.length > 1) return MULTI_ZONE;
      return stopColor(PRICE_STOPS, zones[0] == null ? null : Math.max(0, Math.min(250, zones[0]))) ?? NO_DATA;
    }
    case "offline": {
      const o = f.outages as OutagesFile | undefined;
      return o ? (stopColor(OFFLINE_STOPS, (o.countries[iso]?.offline_mw ?? 0) / 1000) ?? NO_DATA) : NO_DATA;
    }
    case "access": {
      const ws = f.worldStats as WorldStatsFile | undefined;
      const code = ISO3[iso];
      return (ws && code && stopColor(ACCESS_STOPS, latest(ws.access[code], ws.years)?.value)) || TR_NO_DATA;
    }
    case "none": {
      if (!fr.day) return PLAIN_LAND;
      const light = sunLight(fr);
      return [PLAIN_LAND[0] - 8 + 14 * light, PLAIN_LAND[1] - 8 + 16 * light, PLAIN_LAND[2] - 8 + 20 * light].map(Math.round) as RGB;
    }
    default: {
      const tr = TR_METRIC[fr.colour];
      if (tr) {
        const t = f.transition as TransitionFile | undefined;
        const m = metricById(tr);
        return metricColor(m, t?.entities[ISO3[iso]]?.[m.id][fr.yearK]) ?? TR_NO_DATA;
      }
      const ir = IR_METRIC[fr.colour];
      if (ir) {
        const irena = f.irena as IrenaFile | undefined;
        if (!irena) return TR_NO_DATA;
        const k = irenaK(irena, fr.mode, (f.transition as TransitionFile | undefined)?.years, fr.yearK);
        return stopColor(IRENA_STOPS, irenaScale(irenaValue(irena, ISO3[iso], irenaMetricById(ir), k))) ?? TR_NO_DATA;
      }
      const pr = PR_METRIC[fr.colour];
      if (pr) {
        const p = f.prices as PricesFile | undefined;
        const zones = Object.values(p?.zones ?? {}).filter((z) => z.country === iso);
        if (zones.length > 1) return MULTI_ZONE;
        const m = priceMetricById(pr);
        return (zones[0] && stopColor(m.stops, m.value(zones[0]))) || NO_DATA;
      }
      return PLAIN_LAND;
    }
  }
}

/** 0 at night .. 1 at full day over Central Europe (24 h mode). */
export const sunLight = (fr: Frame) => (fr.day ? Math.max(0, Math.min(1, (fr.sunAlt + 4) / 24)) : 0);

/** A label MapLibre draws (map/style.ts): kind picks its style, sub is a second line. */
export interface LabelFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: { kind: "country" | "zone" | "flow" | "region" | "dc" | "money"; text: string; sub: string; rank: number };
}
export interface LabelCollection {
  type: "FeatureCollection";
  features: LabelFeature[];
}
const label = (kind: LabelFeature["properties"]["kind"], at: [number, number], text: string, sub = "", rank = 0): LabelFeature => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: at },
  properties: { kind, text, sub, rank },
});
/** This frame's label groups (each memoised), joined into one collection by `labelsOf`. */
let parts: LabelFeature[][] = [];
export const labelsOf = (): LabelCollection =>
  memo("labels", parts, () => ({ type: "FeatureCollection", features: parts.flat() }));

export function buildLayers(fr: Frame): Layer[] {
  parts = [];
  const f = fr.files;
  const countries = f.countries as CountriesFile | undefined;
  const grid = f.grid as GridFile | undefined;
  const plants = f.plants as PlantsFile | undefined;
  const sel = selectedIso2(fr.selection);
  const day = fr.day;
  const dayK = day ? Math.min(day.slots - 1, Math.floor(fr.daySlot)) : 0;
  const near = nearFilter(fr);
  const facingEurope = angularDistance(fr.centre, [12, 50]) < 78;
  const layers: Layer[] = [];
  const isOn = (id: LayerId) => fr.layers[id];

  // ---------------------------------------------------------------- Europe's countries
  const shapes = memo("shapes", [countries], () =>
    countries ? countries.countries.flatMap((c) => c.polygons.map((rings) => ({ iso: c.iso, name: c.name, polygon: rings.map(pairs) }))) : [],
  );
  const fillKey = [fr.colour, f.stats, f.outages, f.prices, f.transition, f.worldStats, f.irena, fr.mode, day, dayK, fr.yearK, sel, Math.round(sunLight(fr) * 20)];
  if (facingEurope) {
    layers.push(
      new SolidPolygonLayer<Shape>({
        id: "eu-countries",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => {
          const c = countryColour(fr, d.iso);
          return [...(!sel ? c : d.iso === sel ? lift(c, 0.05) : dim(c, 0.45)), 255];
        },
        updateTriggers: { getFillColor: fillKey },
        transitions: { getFillColor: fr.mode === "years" ? 450 : day ? 320 : 600 },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 22],
        parameters: ON_TOP,
        // below MapLibre's world grid lines, which draw over the land
        ...({ beforeId: "deck-anchor" } as object),
      }),
    );
  }

  // the night shadow (24 h mode)
  if (day && isOn("night") && fr.night) {
    layers.push(
      new BitmapLayer({
        id: "eu-night",
        image: fr.night,
        bounds: NIGHT_BOUNDS,
        _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
        parameters: ON_TOP,
      }),
    );
  }
  // sunshine: this hour's image fading into the next one's (drawing only)
  if (fr.sun && isOn("sun")) {
    const { image, next, fade, bounds } = fr.sun;
    for (const [n, img, a] of [
      [0, image, 1 - fade],
      [1, next, fade],
    ] as const) {
      if (img && a > 0.01)
        layers.push(
          new BitmapLayer({
            id: `eu-sun-${n}`,
            image: img,
            bounds,
            _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
            opacity: a,
            textureParameters: { minFilter: "linear", magFilter: "linear" },
            parameters: ON_TOP,
          }),
        );
    }
  }

  if (facingEurope && countries) {
    layers.push(
      new PathLayer<number[]>({
        id: "eu-coast",
        data: countries.coast,
        getPath: (d) => pairs(d),
        getColor: COAST,
        getWidth: 0.7,
        widthUnits: "pixels",
        parameters: ON_TOP,
      }),
      new PathLayer<number[]>({
        id: "eu-borders",
        data: countries.borders,
        getPath: (d) => pairs(d),
        getColor: BORDER,
        getWidth: 0.9,
        widthUnits: "pixels",
        parameters: ON_TOP,
      }),
    );
    // the selected country's outline
    const focus = sel ? countries.countries.find((c) => c.iso === sel) : null;
    const rings = memo("focusRings", [focus], () => (focus ? focus.polygons.map((r) => pairs(r[0])) : []));
    layers.push(
      new PathLayer<[number, number][]>({
        id: "eu-focus-glow",
        data: rings,
        getPath: (d) => d,
        getColor: [255, 246, 230, 45],
        getWidth: 7,
        widthUnits: "pixels",
        jointRounded: true,
        parameters: ON_TOP,
      }),
      new PathLayer<[number, number][]>({
        id: "eu-focus-outline",
        data: rings,
        getPath: (d) => d,
        getColor: [255, 246, 230, 235],
        getWidth: 1.8,
        widthUnits: "pixels",
        jointRounded: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ---------------------------------------------------------------- Europe's grid
  if (facingEurope && grid) {
    if (isOn("gridEU")) {
      const bands = memo("lineBands", [grid], () =>
        VOLTAGE_BANDS.map((b) => ({ ...b, paths: grid.lines.filter(([kv]) => band(kv) === b).map(([, flat]) => pairs(flat)) })).reverse(),
      );
      for (const b of bands)
        layers.push(
          new PathLayer<[number, number][]>({
            id: `eu-grid-${b.min}`,
            data: b.paths,
            getPath: (d) => d,
            getColor: [...b.color, day ? Math.round(b.alpha * 0.35) : b.alpha],
            updateTriggers: { getColor: [!!day] },
            getWidth: b.width,
            widthUnits: "pixels",
            parameters: ON_TOP,
          }),
        );
    }
    if (isOn("hvdc")) {
      const links = memo("links", [grid], () => grid.links.map(([mw, flat]) => ({ mw, path: pairs(flat) })));
      layers.push(
        new PathLayer<{ mw: number; path: [number, number][] }, PathStyleExtensionProps>({
          id: "eu-hvdc",
          data: links,
          getPath: (d) => d.path,
          getColor: [...HVDC, 190],
          getWidth: 1,
          widthUnits: "pixels",
          getDashArray: [4, 3],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          parameters: ON_TOP,
        }),
      );
    }
    if (isOn("substations") && (fr.zoom >= 4.8 || sel)) {
      layers.push(
        new ScatterplotLayer<Substation>({
          id: "eu-substations",
          data: grid.substations,
          getPosition: (b) => [b[1], b[2]],
          getRadius: (b) => (b[0] >= 380 ? 1.9 : 1.3),
          radiusUnits: "pixels",
          getFillColor: [...SUBSTATION, 150],
          pickable: true,
          parameters: ON_TOP,
        }),
      );
    }
  }

  // ---------------------------------------------------------------- gas storage (Europe; pipelines and LNG come from GEM worldwide)
  const gas = f.gas as GasFile | undefined;
  if (facingEurope && gas && isOn("gas")) {
    layers.push(
      new ScatterplotLayer<GasSite>({
        id: "eu-gas-storage",
        data: memo("storages", [gas], () => gas.storages),
        getPosition: (g) => [g[2], g[3]],
        getRadius: fr.zoom >= GAS_DETAIL_ZOOM ? 4 : 2.6,
        radiusUnits: "pixels",
        getFillColor: [...GAS, 60],
        stroked: true,
        getLineColor: [...GAS, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 1.2,
        updateTriggers: { getRadius: [fr.zoom >= GAS_DETAIL_ZOOM] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ---------------------------------------------------------------- Europe's plants
  if (facingEurope && plants && isOn("plantsEU")) {
    const coarse = fr.zoom < DETAIL_ZOOM;
    const visible = memo("visiblePlants", [plants, coarse, sel], () => plants.plants.filter((p) => p[4] !== sel && (!coarse || p[1] >= 50)));
    layers.push(
      new ScatterplotLayer<Plant>({
        id: "eu-plants",
        data: visible,
        getPosition: (p) => [p[2], p[3]],
        getRadius: (p) => Math.min(coarse ? 4.2 : 6.5, 1 + Math.sqrt(p[1]) * (coarse ? 0.06 : 0.085)),
        radiusUnits: "pixels",
        getFillColor: (p) => [...FUEL_COLOR[plants.groups[p[0]]], coarse ? 200 : 235],
        stroked: true,
        getLineColor: [6, 7, 10, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 0.7,
        updateTriggers: { getRadius: [coarse], getFillColor: [coarse] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
    // the selected country: every unit >= 1 MW as 3D columns or beams & fields (live mode)
    const units = sel ? (f[`units:${sel}`] as Unit[] | undefined) : undefined;
    if (sel && fr.mode === "live") {
      const all = memo("focusUnits", [units, plants, sel], () =>
        units ?? plants.plants.filter((p) => p[4] === sel).map((p) => [p[0], p[1], p[2], p[3], p[5], p[6]] as Unit),
      );
      if (fr.plantStyle === "bars") {
        layers.push(
          new ScatterplotLayer<Unit>({
            id: "eu-focus-small",
            data: memo("focusSmall", [all], () => all.filter((u) => u[1] < COLUMN_MIN_MW)),
            getPosition: (u) => [u[2], u[3]],
            getRadius: 1.8,
            radiusUnits: "pixels",
            getFillColor: (u) => [...FUEL_COLOR[plants.groups[u[0]] ?? "other"], 200],
            pickable: true,
            parameters: ON_TOP,
          }),
          new ColumnLayer<Unit>({
            id: "eu-plant-columns",
            data: memo("focusColumns", [all], () => all.filter((u) => u[1] >= COLUMN_MIN_MW)),
            getPosition: (p) => [p[2], p[3]],
            getElevation: (p) => Math.sqrt(p[1]) * COLUMN_M_PER_SQRT_MW,
            getFillColor: (p) => [...FUEL_COLOR[plants.groups[p[0]]], 235],
            radius: 3800,
            diskResolution: 12,
            extruded: true,
            pickable: true,
            material: { ambient: 0.55, diffuse: 0.6, shininess: 24, specularColor: [60, 60, 60] },
          }),
        );
      } else {
        const hexes = memo("focusHexes", [all], () => hexBins(all.filter((u) => u[1] < BEAM_MIN_MW)));
        const peak = memo("hexPeak", [hexes], () => Math.max(1, ...hexes.map((h) => h.mw)));
        const beams = memo("focusBeams", [all], () => all.filter((u) => u[1] >= BEAM_MIN_MW));
        const segments = memo("beamSegments", [beams], () =>
          BEAM_BANDS.map(([a, b, alpha]) => ({
            alpha,
            rows: beams.map((u) => {
              const h = Math.sqrt(u[1]) * COLUMN_M_PER_SQRT_MW * 1.15;
              return { unit: u, from: [u[2], u[3], h * a] as [number, number, number], to: [u[2], u[3], h * b] as [number, number, number] };
            }),
          })),
        );
        layers.push(
          new ColumnLayer<Hex>({
            id: "eu-hex-fields",
            data: hexes,
            getPosition: (h) => h.position,
            getElevation: (h) => Math.sqrt(h.mw) * HEX_M_PER_SQRT_MW,
            getFillColor: (h) => [...FUEL_COLOR[plants.groups[h.dominant] ?? "other"], Math.round(40 + 170 * Math.min(1, Math.sqrt(h.mw / peak)))],
            updateTriggers: { getFillColor: [peak] },
            radius: HEX_KM * 1000,
            coverage: 0.84,
            diskResolution: 6,
            extruded: true,
            pickable: true,
            material: { ambient: 0.8, diffuse: 0.35, shininess: 8, specularColor: [30, 30, 30] },
          }),
          new ScatterplotLayer<Unit>({
            id: "eu-beam-glow",
            data: beams,
            getPosition: (u) => [u[2], u[3]],
            getRadius: (u) => 5 + Math.sqrt(u[1]) * 0.18,
            radiusUnits: "pixels",
            getFillColor: (u) => [...FUEL_COLOR[plants.groups[u[0]] ?? "other"], 70],
            pickable: true,
            parameters: ON_TOP,
          }),
          ...segments.map(
            (bandRows, i) =>
              new LineLayer<{ unit: Unit; from: [number, number, number]; to: [number, number, number] }>({
                id: `eu-beam-${i}`,
                data: bandRows.rows,
                getSourcePosition: (d) => d.from,
                getTargetPosition: (d) => d.to,
                getColor: (d) => [...FUEL_COLOR[plants.groups[d.unit[0]] ?? "other"], bandRows.alpha],
                getWidth: (d) => 3.5 + Math.min(4.5, d.unit[1] / 800),
                widthUnits: "pixels",
                pickable: true,
                parameters: ON_TOP,
              }),
          ),
        );
      }
    }
  }

  // ---------------------------------------------------------------- the world (MapLibre draws the land, grid tiles)
  layers.push(...worldLayers(fr, near));
  layers.push(...gemLayers(fr));
  layers.push(...financeLayers(fr));

  // ---------------------------------------------------------------- wind particles
  if (fr.wind?.field && isOn("wind")) {
    layers.push(
      new PathLayer({
        id: "eu-wind",
        data: fr.wind.paths as never,
        _pathType: "open",
        getWidth: fr.isMobile ? 1.1 : 1.3,
        widthUnits: "pixels",
        parameters: { ...ADD, depthCompare: day ? "less-equal" : "always" },
      }),
    );
  }

  // ---------------------------------------------------------------- generation towers (24 h)
  if (day && countries && isOn("towers") && facingEurope) layers.push(...towerLayers(fr, day, dayK, countries, sel));

  // ---------------------------------------------------------------- prices: a glow per country
  if (facingEurope && isOn("prices")) layers.push(...priceLayers(fr, dayK));

  // ---------------------------------------------------------------- cross-border flows
  if (facingEurope && isOn("flows")) {
    const arcs = flowArcs(fr, dayK);
    const touches = (a: Arc) => a.from === sel || a.to === sel;
    parts.push(
      memo("lbl-flows", [arcs, sel, !!day, fr.isMobile], () =>
        (day && !sel ? [] : sel ? arcs.filter(touches) : fr.isMobile ? [...arcs].sort((a, b) => b.mw - a.mw).slice(0, 4) : arcs.filter((a) => a.mw >= LABEL_MW)).map((a) =>
          label("flow", a.path[20], power(a.mw), "", -a.mw),
        ),
      ),
    );
    layers.push(
      new PathLayer<Arc>({
        id: "eu-flow-casing",
        data: arcs,
        getPath: (d) => d.path,
        getColor: (d) => [4, 6, 10, !sel || touches(d) ? (day ? 120 : 190) : 60],
        getWidth: (d) => (day ? 3.5 : 5) + Math.min(4, d.mw / 700),
        updateTriggers: { getColor: [sel, !!day], getWidth: [!!day] },
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        parameters: day ? { depthCompare: "less-equal", depthWriteEnabled: false } : ON_TOP,
      }),
      new FlowArrowLayer<Arc>({
        id: "eu-flows",
        data: arcs,
        getPath: (d) => d.path,
        getTimestamps: (d) => d.timestamps,
        getColor: (d) => [...FLOW, !sel || touches(d) ? (day ? 165 : 255) : 45],
        getWidth: (d) => (day ? 14 : 20) + Math.min(12, d.mw / 250),
        getArrowStyle: (d) => [1.4 + Math.min(1.8, d.mw / 1500), 4.5 + Math.min(5, d.mw / 500), 1],
        updateTriggers: { getColor: [sel, !!day], getWidth: [!!day] },
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        pickable: true,
        phase: fr.clock.phase,
        spacing: fr.clock.spacing,
        strokePx: 2.4,
        lineAlpha: 0.85,
        parameters: { ...OVER, depthCompare: day ? "less-equal" : "always", depthWriteEnabled: false },
      }),
    );
  }

  // ---------------------------------------------------------------- price-zone markers, names
  if (facingEurope) layers.push(...zoneMarkers(fr));
  if (facingEurope && countries) parts.push(countryLabels(fr, countries));
  // under MapLibre's labels (map/labels.ts), which read well on the globe
  return layers.map((l) => ((l.props as { beforeId?: string }).beforeId ? l : l.clone({ beforeId: LABELS_BELOW } as never)));
}

/** Items on the side of the globe that faces the camera (redone when the camera turns). */
function nearFilter(fr: Frame) {
  const c = unitVector(fr.centre[0], fr.centre[1]);
  return (p: [number, number]) => {
    const v = unitVector(p[0], p[1]);
    return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.17;
  };
}

function flowArcs(fr: Frame, dayK: number): Arc[] {
  const day = fr.day;
  const flows = fr.files.flows as FlowsFile | undefined;
  return memo("arcs", [day, dayK, flows], () => {
    const out: Arc[] = [];
    const rows = day
      ? day.borders.map((b) => ({ a: b.a, b: b.b, mw: b.values[dayK], ts: new Date(Date.parse(day.start) + dayK * day.step_s * 1000).toISOString() }))
      : (flows?.borders ?? []).map((b) => ({ a: b.a, b: b.b, mw: b.mw, ts: b.ts }));
    rows.forEach((f, n) => {
      if (f.mw == null || Math.abs(f.mw) < IDLE_MW) return;
      const [from, to] = f.mw > 0 ? [f.a, f.b] : [f.b, f.a];
      if (!ANCHOR[from] || !ANCHOR[to]) return;
      const path = curvedPath(ANCHOR[from], ANCHOR[to], 0.16, 40);
      out.push({ from, to, mw: Math.abs(f.mw), ts: f.ts, path, timestamps: flowDistances(path, false, n * 91_000) });
    });
    return out.sort((x, y) => x.mw - y.mw);
  });
}

function towerLayers(fr: Frame, day: DayFile, dayK: number, countries: CountriesFile, sel: string | null): Layer[] {
  const names = memo("towerNames", [countries], () => new Map(countries.countries.map((c) => [c.iso, c.name])));
  const frac = Math.max(0, Math.min(1, fr.daySlot - dayK));
  const next = Math.min(day.slots - 1, dayK + 1);
  const towers: TowerPiece[] = [];
  for (const [iso, series] of Object.entries(day.countries)) {
    if (!ANCHOR[iso] || (sel && sel !== iso)) continue;
    let base = 0;
    let total = 0;
    const pieces: TowerPiece[] = [];
    for (const g of STACK_ORDER) {
      const now = series.generation[g]?.[dayK];
      const then = series.generation[g]?.[next] ?? now;
      if (now != null && now > 0) total += now;
      if (now == null || then == null) continue;
      // heights glide between the 15-min values (drawing only); labels show the slot's value
      const drawn = now + (then - now) * frac;
      if (drawn <= 0) continue;
      pieces.push({ iso, name: names.get(iso) ?? iso, group: g, base, mw: now, drawn, total: 0 });
      base += drawn;
    }
    for (const p of pieces) p.total = total;
    towers.push(...pieces);
  }
  const top = new Map(towers.map((t) => [t.iso, t.group]));
  const pools = memo("towerPools", [day, dayK, sel], () => {
    const best = new Map<string, TowerPiece>();
    for (const t of towers) if (!best.has(t.iso) || t.mw > best.get(t.iso)!.mw) best.set(t.iso, t);
    return [...best.values()].map((t) => ({ iso: t.iso, total: t.total, group: t.group }));
  });
  return [
    new ScatterplotLayer<{ iso: string; total: number; group: string }>({
      id: "eu-tower-pools",
      data: pools,
      getPosition: (t) => ANCHOR[t.iso],
      getRadius: (t) => 30_000 + Math.sqrt(t.total) * 450,
      getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 70],
      stroked: false,
      parameters: ADD,
    }),
    new ColumnLayer<TowerPiece>({
      id: "eu-towers",
      data: towers,
      getPosition: (t) => [...ANCHOR[t.iso], t.base * TOWER_M_PER_MW] as [number, number, number],
      getElevation: (t) => t.drawn * TOWER_M_PER_MW,
      getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 235],
      radius: TOWER_RADIUS_M,
      diskResolution: 24,
      extruded: true,
      pickable: true,
      material: { ambient: 0.55, diffuse: 0.6, shininess: 20, specularColor: [50, 50, 50] },
    }),
    new TextLayer<TowerPiece>({
      id: "eu-tower-labels",
      data: towers
        .filter((t) => t.group === top.get(t.iso) && t.total >= TOWER_LABEL_MW)
        .sort((a, b) => b.total - a.total)
        .slice(0, fr.isMobile ? 5 : 9),
      getPosition: (t) => [...ANCHOR[t.iso], (t.base + t.drawn) * TOWER_M_PER_MW + 25_000] as [number, number, number],
      getText: (t) => `${t.iso} ${Math.round(t.total / 1000)} GW`,
      getSize: 12,
      getColor: [236, 240, 246, 255],
      fontFamily: "Inter, system-ui, sans-serif",
      fontWeight: 700,
      background: true,
      getBackgroundColor: [6, 9, 14, 200],
      backgroundPadding: [4, 2],
      parameters: ON_TOP,
    }),
  ];
}

export const LABELS_BELOW = "label-names";

/** Country names, with the coloured figure below where the colour has one per country. */
function countryLabels(fr: Frame, countries: CountriesFile): LabelFeature[] {
  const detail = fr.zoom >= DETAIL_ZOOM;
  const tr = TR_METRIC[fr.colour];
  const pr = PR_METRIC[fr.colour];
  const transition = tr ? (fr.files.transition as TransitionFile | undefined) : undefined;
  const prices = pr ? (fr.files.prices as PricesFile | undefined) : undefined;
  const ir = IR_METRIC[fr.colour];
  const irena = ir ? (fr.files.irena as IrenaFile | undefined) : undefined;
  const live = fr.colour === "price" || fr.layers.prices ? "price" : fr.colour === "renewable" ? "renewable" : null;
  const day = fr.day;
  const dayK = day ? Math.min(day.slots - 1, Math.floor(fr.daySlot)) : 0;
  const stats = live ? (fr.files.stats as StatsFile | undefined) : undefined;
  const names = memo("lbl-names", [countries, detail, tr, transition, fr.yearK, pr, prices, ir, irena, fr.mode, live, day, dayK, stats], () =>
    countries.countries
      .filter((c) => detail || !SMALL.has(c.iso))
      .map((c) => {
        let sub = "";
        if (tr && transition) {
          const m = metricById(tr);
          sub = formatMetric(m, transition.entities[ISO3[c.iso]]?.[m.id][fr.yearK]);
        } else if (live === "price") {
          const v = day
            ? Object.values(day.prices).flatMap((z) => (z.country === c.iso && z.values[dayK] != null ? [z.values[dayK] as number] : []))
            : Object.values(stats?.day_ahead_prices ?? {}).flatMap((p) => (p.country === c.iso ? [p.eur_mwh] : []));
          if (v.length) sub = v.length === 1 ? `${Math.round(v[0])} €` : `${Math.round(Math.min(...v))}–${Math.round(Math.max(...v))} €`;
        } else if (live === "renewable") {
          const v = day ? day.countries[c.iso]?.renewable_share[dayK] : stats?.countries[c.iso]?.renewable_share_of_generation;
          if (v != null) sub = `${Math.round(v)} %`;
        } else if (ir && irena) {
          const k = irenaK(irena, fr.mode, (fr.files.transition as TransitionFile | undefined)?.years, fr.yearK);
          const v = irenaValue(irena, ISO3[c.iso], irenaMetricById(ir), k);
          sub = v != null ? formatGw(v) : "";
        } else if (pr && prices) {
          const zones = Object.values(prices.zones).filter((z) => z.country === c.iso);
          if (zones.length === 1) sub = priceMetricById(pr).format(priceMetricById(pr).value(zones[0]));
        }
        return label("country", c.label, c.name.toUpperCase(), sub);
      }),
  );
  if (!pr || !prices) return names;
  // zones of the countries with several, beside their markers
  const zones = memo("lbl-zones", [prices, pr, fr.zoom >= 3.6], () => {
    if (fr.zoom < 3.6) return [];
    const m = priceMetricById(pr);
    return zoneMarkerData(prices).map((d) => label("zone", d.at, `${d.short} ${m.format(m.value(d.z))}`));
  });
  return memo("lbl-countries", [names, zones], () => [...names, ...zones]);
}

/** Price zones (12-month colours): a marker per zone, where countries have several. */
function zoneMarkers(fr: Frame): Layer[] {
  const pr = PR_METRIC[fr.colour];
  const prices = fr.files.prices as PricesFile | undefined;
  if (!pr || !prices) return [];
  const m = priceMetricById(pr);
  const zoneSel = fr.selection?.kind === "zone" ? fr.selection.id : null;
  return [
    new ScatterplotLayer<ZoneMarker>({
      id: "pr-zones",
      data: zoneMarkerData(prices),
      getPosition: (d) => d.at,
      getRadius: (d) => (d.zone === zoneSel ? 9 : 7),
      radiusUnits: "pixels",
      getFillColor: (d) => [...(stopColor(m.stops, m.value(d.z)) ?? NO_DATA), 245],
      stroked: true,
      getLineColor: (d) => (d.zone === zoneSel ? [255, 246, 230, 255] : [8, 10, 14, 230]),
      lineWidthUnits: "pixels",
      getLineWidth: (d) => (d.zone === zoneSel ? 2 : 1.2),
      updateTriggers: { getFillColor: [pr], getRadius: [zoneSel], getLineColor: [zoneSel], getLineWidth: [zoneSel] },
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
}

export interface ZoneMarker {
  zone: string;
  z: PricesFile["zones"][string];
  at: [number, number];
  short: string;
}
export const zoneMarkerData = (prices: PricesFile): ZoneMarker[] =>
  memo("zoneMarkers", [prices], () =>
    Object.entries(prices.zones).flatMap(([zone, z]) => (ZONE_POINT[zone] ? [{ zone, z, at: ZONE_POINT[zone].at, short: ZONE_POINT[zone].short }] : [])),
  );

function worldLayers(fr: Frame, near: (p: [number, number]) => boolean): Layer[] {
  const f = fr.files;
  const out: Layer[] = [];
  const isOn = (id: LayerId) => fr.layers[id];
  // undersea cables
  const cables = (f.cables as { cables: Cable[] } | undefined)?.cables;
  if (isOn("cables") && cables) {
    out.push(
      new PathLayer<Cable>({
        id: "w-cables",
        data: memo("nearCables", [cables, fr.camKey], () => cables.filter((c) => near([c[3][0], c[3][1]]))),
        getPath: (c) => pairs(c[3]),
        getColor: (c) => (CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).color,
        getWidth: (c) => (CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).width,
        widthUnits: "pixels",
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }
  // GEM's plants of the chosen status, sized by capacity, coloured by fuel
  const wp = f.worldPlants as WorldPlantsFile | undefined;
  if (isOn("plantsWorld") && wp) {
    const st = wp.statuses.indexOf(fr.plantStatus);
    const vectors = memo("plantVectors", [wp], () => wp.points.map((p) => unitVector(p[0], p[1])));
    const idx = memo("nearPlants", [wp, st, fr.camKey], () => {
      const c = unitVector(fr.centre[0], fr.centre[1]);
      const keep: number[] = [];
      wp.points.forEach((p, k) => {
        const v = vectors[k];
        if (p[3] === st && v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.17) keep.push(k);
      });
      return keep;
    });
    const status = fr.plantStatus;
    out.push(
      new ScatterplotLayer<number>({
        id: "w-plants",
        data: idx,
        getPosition: (k) => [wp.points[k][0], wp.points[k][1]],
        getRadius: (k) => Math.min(9, 0.6 + Math.sqrt(wp.points[k][4]) * (fr.zoom < 3 ? 0.07 : 0.11)),
        radiusUnits: "pixels",
        getFillColor: (k) => {
          const c = PLANT_TYPE_COLOR[wp.types[wp.points[k][2]]] ?? [150, 150, 150];
          return status === "retired" ? [110, 110, 120, 170] : status === "planned" ? [...c, 60] : [...c, 210];
        },
        stroked: status !== "operating",
        getLineColor: (k) => [...(PLANT_TYPE_COLOR[wp.types[wp.points[k][2]]] ?? [150, 150, 150]), 230],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        updateTriggers: { getRadius: [fr.zoom < 3], getFillColor: [status], getLineColor: [status] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }
  // data centres: glowing hubs zoomed out, single sites zoomed in
  const dc = f.datacentres as DataCentresFile | undefined;
  if (isOn("dataCentres") && dc) {
    if (fr.zoom < 4.5) {
      const hubs = memo("nearHubs", [dc, fr.camKey], () => dc.clusters.filter((c) => near([c[0], c[1]])));
      parts.push(memo("lbl-dc", [hubs, fr.zoom >= 2.4], () => (fr.zoom >= 2.4 ? hubs.filter((c) => c[2] >= 25).map((c) => label("dc", [c[0], c[1]], String(c[2]), "", -c[2])) : [])));
      out.push(
        new ScatterplotLayer<DataCentresFile["clusters"][number]>({
          id: "w-dc-glow",
          data: hubs,
          getPosition: (c) => [c[0], c[1]],
          getRadius: (c) => 6 + Math.sqrt(c[2]) * 3.2,
          radiusUnits: "pixels",
          getFillColor: [...DC_COLOR, 45],
          parameters: ADD,
        }),
        new ScatterplotLayer<DataCentresFile["clusters"][number]>({
          id: "w-dc-clusters",
          data: hubs,
          getPosition: (c) => [c[0], c[1]],
          getRadius: (c) => 1.6 + Math.sqrt(c[2]) * 0.9,
          radiusUnits: "pixels",
          getFillColor: [236, 220, 255, 235],
          stroked: true,
          getLineColor: [...DC_COLOR, 255],
          lineWidthUnits: "pixels",
          getLineWidth: 1.2,
          pickable: true,
          parameters: ON_TOP,
        }),
      );
    } else {
      out.push(
        new ScatterplotLayer<DataCentresFile["points"][number]>({
          id: "w-datacentres",
          data: memo("nearDc", [dc, fr.camKey], () => dc.points.filter((d) => near([d[0], d[1]]))),
          getPosition: (d) => [d[0], d[1]],
          getRadius: 3.2,
          radiusUnits: "pixels",
          getFillColor: [236, 220, 255, 235],
          stroked: true,
          getLineColor: [...DC_COLOR, 255],
          lineWidthUnits: "pixels",
          getLineWidth: 1.4,
          pickable: true,
          parameters: ON_TOP,
        }),
      );
    }
  }
  // live grids beyond Europe
  if (isOn("liveGrids")) {
    const us = f.us as UsFile | undefined;
    const br = f.brazil as BrazilFile | undefined;
    const au = f.aemo as AemoFile | undefined;
    if (us) {
      const arcs = memo("usArcs", [us, fr.camKey], () =>
        regionArcs(us.flows.pairs.map((p) => ({ id: `${p.a}-${p.b}`, from: p.a, to: p.b, mw: p.mw })), US_POINT, us.flows.hour ?? "").filter((a) => near(a.path[15])),
      );
      const dots = memo("usDots", [us, fr.camKey], () =>
        Object.entries(us.regions).flatMap(([id, r]) =>
          US_POINT[id] && r.demand && near(US_POINT[id]) ? [{ id, at: US_POINT[id], mw: r.demand[1], label: `${id} ${Math.round(r.demand[1] / 1000)} GW` }] : [],
        ),
      );
      parts.push(memo("lbl-us", [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers("w-us", dots, US_COLOR, false), ...regionFlowLayers("w-us", arcs, fr.clock, FLOW, 500));
    }
    if (br) {
      const arcs = memo("brArcs", [br, fr.camKey], () => regionArcs(br.flows, BR_POINT, br.at ?? "").filter((a) => near(a.path[15])));
      const dots = memo("brDots", [br, fr.camKey], () =>
        Object.entries(br.subsystems).flatMap(([id, s]) =>
          BR_POINT[id] && s.load != null && near(BR_POINT[id]) ? [{ id, at: BR_POINT[id], mw: s.load, label: `${id} ${(s.load / 1000).toFixed(0)} GW` }] : [],
        ),
      );
      parts.push(memo("lbl-br", [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers("w-br", dots, BR_COLOR, false), ...regionFlowLayers("w-br", arcs, fr.clock, FLOW, 300));
    }
    if (au) {
      const arcs = memo("auArcs", [au, fr.camKey], () =>
        regionArcs(au.interconnectors.map((c) => ({ id: c.id, from: c.from, to: c.to, mw: c.mw })), NEM_POINT, au.settlement).filter((a) => near(a.path[15])),
      );
      const dots = memo("auDots", [au, fr.camKey], () =>
        Object.entries(au.regions).flatMap(([id, r]) =>
          NEM_POINT[id] && r.demand != null && near(NEM_POINT[id])
            ? [{ id, at: NEM_POINT[id], mw: r.demand, label: `${id.replace(/1$/, "")} ${r.price != null ? Math.round(r.price) : "–"} A$` }]
            : [],
        ),
      );
      parts.push(memo("lbl-au", [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers("w-au", dots, [120, 222, 255], false), ...regionFlowLayers("w-au", arcs, fr.clock, FLOW, 80));
    }
    const tw = f.taiwan as TaiwanFile | undefined;
    if (tw && near(TW_POINT)) {
      const dots = memo("twDots", [tw], () => [{ id: "TW", at: TW_POINT, mw: tw.total_mw, label: `TW ${(tw.total_mw / 1000).toFixed(0)} GW` }]);
      parts.push(memo("lbl-tw", [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers("w-tw", dots, TW_COLOR, false));
    }
    const on = f.ontario as OntarioFile | undefined;
    if (on && near(ON_POINT.ON)) {
      const arcs = memo("onArcs", [on], () =>
        regionArcs((on.interties?.flows ?? []).map((x) => ({ id: x.to, from: "ON", to: x.to, mw: x.mw })), ON_POINT, on.interties?.at ?? ""),
      );
      const mw = on.demand?.mw ?? on.generation?.total_mw ?? 0;
      const dots = memo("onDots", [on], () => [{ id: "ON", at: ON_POINT.ON, mw, label: `ON ${(mw / 1000).toFixed(0)} GW` }]);
      parts.push(memo("lbl-on", [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers("w-on", dots, ON_COLOR, false), ...regionFlowLayers("w-on", arcs, fr.clock, FLOW, 150));
    }
  }
  return out;
}


/** Global Energy Monitor's pipelines and points; the side of the globe facing the camera only. */
function gemLayers(fr: Frame): Layer[] {
  const out: Layer[] = [];
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = (lon: number, lat: number) => {
    const v = unitVector(lon, lat);
    return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.1;
  };
  for (const [id, style] of Object.entries(GEM_PIPES)) {
    const file = fr.layers[id as LayerId] ? (fr.files[style.file] as GemPipesFile | undefined) : undefined;
    if (!file) continue;
    const all = memo(`gem-${id}-paths`, [file], () => file.paths.map((p) => ({ row: p[0], path: pairs(p.slice(1)) })));
    const near = memo(`gem-${id}-near`, [all, fr.camKey], () => all.filter((d) => facing(d.path[0][0], d.path[0][1])));
    out.push(
      new PathLayer<{ row: number; path: [number, number][] }, PathStyleExtensionProps<{ row: number; path: [number, number][] }>>({
        id: `gem-${id}`,
        data: near,
        getPath: (d) => d.path,
        getColor: (d) => {
          const cls = file.rows[d.row][0];
          return cls === 3 ? [...IDLE, 90] : [...style.color, cls === 0 ? 200 : cls === 1 ? 230 : 110];
        },
        getWidth: (d) => style.width(file.rows[d.row][2]) * (file.rows[d.row][0] === 2 ? 0.7 : 1),
        getDashArray: (d) => (file.rows[d.row][0] === 0 ? [0, 0] : [4, 3]),
        dashJustified: true,
        widthUnits: "pixels",
        jointRounded: true,
        capRounded: true,
        pickable: true,
        extensions: [new PathStyleExtension({ dash: true })],
        parameters: ON_TOP,
      }),
    );
  }
  for (const [id, style] of Object.entries(GEM_POINTS)) {
    const file = fr.layers[id as LayerId] ? (fr.files[style.file] as GemPointsFile | undefined) : undefined;
    if (!file) continue;
    const near = memo(`gem-${id}-near`, [file, fr.camKey], () => file.points.filter((p) => facing(p[0], p[1])));
    const colorOf = (p: GemPoint): RGB => (p[3] === 3 ? IDLE : style.color(file.kinds[p[2]] ?? ""));
    if (style.glow)
      out.push(
        new ScatterplotLayer<GemPoint>({
          id: `gem-${id}-glow`,
          data: near,
          getPosition: (p) => [p[0], p[1]],
          getRadius: (p) => style.radius(p[4]) * 2.2,
          radiusUnits: "pixels",
          getFillColor: (p) => [...colorOf(p), 45],
          parameters: ADD,
        }),
      );
    out.push(
      new ScatterplotLayer<GemPoint>({
        id: `gem-${id}`,
        data: near,
        getPosition: (p) => [p[0], p[1]],
        getRadius: (p) => style.radius(p[4]) * (p[3] === 2 ? 0.85 : 1),
        radiusUnits: "pixels",
        // operating: filled; under construction: half-filled ring; planned: ring; idle: grey
        getFillColor: (p) => [...colorOf(p), p[3] === 0 ? 215 : p[3] === 1 ? 70 : p[3] === 3 ? 140 : 0],
        stroked: true,
        getLineColor: (p) => (p[3] === 0 ? [8, 10, 14, 200] : [...colorOf(p), p[3] === 2 ? 150 : 230]),
        lineWidthUnits: "pixels",
        getLineWidth: (p) => (p[3] === 0 ? 0.6 : 1.3),
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }
  return out;
}

/** The part of a path on the side of the globe facing the camera (the longest such run). */
function visiblePart(path: [number, number][], facing: (lon: number, lat: number) => boolean): [number, number][] {
  let best: [number, number][] = [];
  let run: [number, number][] = [];
  for (const p of path) {
    if (facing(p[0], p[1])) run.push(p);
    else {
      if (run.length > best.length) best = run;
      run = [];
    }
  }
  return run.length > best.length ? run : best;
}

/** Money flows from this size (US$ million) are drawn as arrows; smaller ones count in the panel. */
export const MIN_FLOW_USD_M = 300;

/** Money flows: gold arcs from the financiers' countries to the projects they paid for,
 *  coins on the projects, a halo on each lending country. */
function financeLayers(fr: Frame): Layer[] {
  const f = fr.files.gemFinance as FinanceFile | undefined;
  const fuels = [fr.layers.financeCoal, fr.layers.financeGas];
  if (!f || !fuels.some(Boolean)) return [];
  const c = unitVector(fr.centre[0], fr.centre[1]);
  const facing = (lon: number, lat: number) => {
    const v = unitVector(lon, lat);
    return v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.08;
  };
  const on = (fuel: number) => fuels[fuel];
  // whole arcs once per file; the visible part per camera position
  const arcs = memo("fin-arcs", [f], () =>
    f.flows.flatMap((fl, n) => {
      const from = f.countries[fl[0]]?.at;
      if (!from) return [];
      let [ex, ey] = fl[7];
      if (ex - from[0] > 180) ex -= 360;
      if (from[0] - ex > 180) ex += 360;
      const span = Math.hypot(ex - from[0], ey - from[1]);
      return [{ flow: fl, n, path: curvedPath(from, [ex, ey], span > 40 ? 0.22 : 0.3, Math.max(24, Math.round(span))) }];
    }),
  );
  const shown = memo("fin-arcs-near", [arcs, fr.camKey, fuels[0], fuels[1]], () =>
    arcs.flatMap((a) => {
      if (!on(a.flow[2]) || a.flow[3] < MIN_FLOW_USD_M) return [];
      const path = visiblePart(a.path, facing);
      return path.length >= 2 ? [{ ...a, path, timestamps: flowDistances(path, false, a.n * 73_000) }] : [];
    }),
  );
  type Arc2 = (typeof shown)[number];
  const width = (m: number) => 1.5 + Math.min(9, Math.sqrt(m) / 22);
  const projects = memo("fin-projects", [f, fr.camKey, fuels[0], fuels[1]], () => f.projects.filter((p) => on(p[2]) && facing(p[0], p[1])));
  const lenders = memo("fin-lenders", [f, fr.camKey, fuels[0], fuels[1]], () =>
    Object.entries(f.totals)
      .map(([iso, t]) => ({ iso, at: f.countries[iso]?.at, out: (on(0) ? t.out[0] : 0) + (on(1) ? t.out[1] : 0) }))
      .filter((d): d is { iso: string; at: [number, number]; out: number } => !!d.at && d.out > 0 && facing(d.at[0], d.at[1])),
  );
  parts.push(
    memo("lbl-money", [lenders, f], () =>
      [...lenders]
        .sort((a, b) => b.out - a.out)
        .slice(0, 10)
        .map((d) => label("money", d.at, `${f.countries[d.iso]?.name ?? d.iso} ${usd(d.out)}`, "", -d.out)),
    ),
  );
  const colorOf = (fuel: number) => MONEY[fuel] ?? MONEY[0];
  return [
    new ScatterplotLayer<{ iso: string; at: [number, number]; out: number }>({
      id: "fin-lender-halo",
      data: lenders,
      getPosition: (d) => d.at,
      getRadius: (d) => 8 + Math.sqrt(d.out) / 8,
      radiusUnits: "pixels",
      getFillColor: [255, 214, 120, 38],
      stroked: true,
      getLineColor: [255, 214, 120, 150],
      lineWidthUnits: "pixels",
      getLineWidth: 1.2,
      pickable: true,
      parameters: ADD,
    }),
    new PathLayer<Arc2>({
      id: "fin-arc-glow",
      data: shown,
      getPath: (d) => d.path,
      getColor: (d) => [...colorOf(d.flow[2]), 22],
      getWidth: (d) => width(d.flow[3]) * 2.2,
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      parameters: ADD,
    }),
    new FlowArrowLayer<Arc2>({
      id: "fin-arcs",
      data: shown,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: (d) => [...colorOf(d.flow[2]), 235],
      getWidth: (d) => 12 + width(d.flow[3]) * 2.2,
      getArrowStyle: (d) => [1.2 + Math.min(2, width(d.flow[3]) / 4), 4 + Math.min(5, width(d.flow[3])), 1],
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      pickable: true,
      phase: fr.clock.phase,
      spacing: fr.clock.spacing,
      strokePx: 2,
      lineAlpha: 0.55,
      parameters: { ...OVER, depthCompare: "always", depthWriteEnabled: false },
    }),
    new ScatterplotLayer<FinanceProject>({
      id: "fin-projects",
      data: projects,
      getPosition: (p) => [p[0], p[1]],
      getRadius: (p) => Math.min(10, 2 + Math.sqrt(p[3]) / 9),
      radiusUnits: "pixels",
      getFillColor: (p) => [...colorOf(p[2]), 190],
      stroked: true,
      getLineColor: [20, 16, 8, 220],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
}

/** A country's day-ahead price at the clock: its zone's, or the middle of its zones (€/MWh). */
function countryPrice(fr: Frame, iso: string, dayK: number): number | null {
  const v = fr.day
    ? Object.values(fr.day.prices).flatMap((z) => (z.country === iso && z.values[dayK] != null ? [z.values[dayK] as number] : []))
    : Object.values((fr.files.stats as StatsFile | undefined)?.day_ahead_prices ?? {}).flatMap((p) => (p.country === iso ? [p.eur_mwh] : []));
  if (!v.length) return null;
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Prices on the map: a glowing disc at each country in the colour of its price, breathing
 *  slowly; where power costs less than nothing, cyan ripples run outwards. */
function priceLayers(fr: Frame, dayK: number): Layer[] {
  const countries = (fr.files.countries as CountriesFile | undefined)?.countries ?? [];
  const rows = memo("price-rows", [countries, fr.day, dayK, fr.files.stats], () =>
    countries.flatMap((c) => {
      const p = ANCHOR[c.iso] ? countryPrice(fr, c.iso, dayK) : null;
      return p == null ? [] : [{ iso: c.iso, at: ANCHOR[c.iso], price: p, color: stopColor(PRICE_GLOW_STOPS, Math.max(-50, Math.min(350, p))) ?? [200, 200, 200] }];
    }),
  );
  type Row = (typeof rows)[number];
  const t = fr.now / 1000;
  const breathe = 1 + 0.06 * Math.sin(t * 1.6);
  const base = fr.day ? 95_000 : 70_000; // metres: under the towers in 24 h, smaller on the globe
  const negative = rows.filter((r) => r.price < 0);
  // 24 h: towers hide the glow behind them
  const blend = fr.day ? { ...ADD, depthCompare: "less-equal" as const } : ADD;
  const ripples = negative.flatMap((r) => [0, 1, 2].map((n) => ({ r, k: (t / 2.4 + n / 3) % 1 })));
  return [
    new ScatterplotLayer<Row>({
      id: "price-glow",
      data: rows,
      getPosition: (r) => r.at,
      getRadius: (r) => base * (0.95 + Math.min(0.5, Math.abs(r.price) / 300)) * breathe,
      getFillColor: (r) => [...r.color, 70],
      updateTriggers: { getRadius: [breathe] },
      transitions: { getFillColor: 320 },
      parameters: blend,
    }),
    new ScatterplotLayer<Row>({
      id: "price-disc",
      data: rows,
      getPosition: (r) => r.at,
      getRadius: base * 0.42,
      getFillColor: (r) => [...r.color, 150],
      stroked: true,
      getLineColor: (r) => [...r.color, 240],
      lineWidthUnits: "pixels",
      getLineWidth: 1.6,
      transitions: { getFillColor: 320, getLineColor: 320 },
      pickable: true,
      parameters: blend,
    }),
    new ScatterplotLayer<{ r: Row; k: number }>({
      id: "price-ripples",
      data: ripples,
      getPosition: (d) => d.r.at,
      getRadius: (d) => base * (0.5 + 1.8 * d.k),
      filled: false,
      stroked: true,
      getLineColor: (d) => [90, 235, 255, Math.round(220 * (1 - d.k))],
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      updateTriggers: { getRadius: [t], getLineColor: [t] },
      parameters: blend,
    }),
  ];
}
