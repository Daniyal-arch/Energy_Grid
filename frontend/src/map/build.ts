// All deck.gl layers of the map, built from the app state and the loaded files. Called by the
// render loop (not by React); derived data is memoised, so per frame only the animation
// uniforms change.

import { COORDINATE_SYSTEM, type Layer } from "@deck.gl/core";
import { PathStyleExtension, type PathStyleExtensionProps } from "@deck.gl/extensions";
import { BitmapLayer, ColumnLayer, LineLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";

import { FUEL_COLOR, STACK_ORDER, power } from "../lib/energy";
import { FlowArrowLayer } from "../lib/flowArrowLayer";
import { curvedPath, flowDistances } from "../lib/flowLayers";
import { GAS_FLOW, GAS_IDLE_GWH, GAS_NODE_LABEL, GAS_TRANSIT, GAS_TRANSIT_LABEL_GWH, endAt, gasWidth, gwhd, latestOf, type GasFlowsFile, type GasPair } from "../lib/gasFlows";
import { ZONE_POINT, priceMetricById, type PricesFile } from "../lib/prices";
import { MONEY, usd, type FinanceFile, type FinanceFlow, type FinanceProject } from "../lib/finance";
import { GEM_PIPES, GEM_POINTS, IDLE, type GemPipesFile, type GemPointsFile, type GemPoint } from "../lib/gem";
import { ETS_COLOR, etsRadius, newestT, type EtsFile, type EtsRow } from "../lib/ets";
import { RETAIL_STOPS, euroCents, newestOf, type RetailFile } from "../lib/retail";
import { CT_COLOR, ctRadius, type CtRow, type CtraceFile } from "../lib/ctrace";
import { GB_TYPE_COLOR, NL_COLOR, gbSiteTotals, type ConnectFile, type NlArea } from "../lib/connect";
import type { UsNodesFile } from "../lib/usNodes";
import { LNG_SEND, lngDay, lngRadius, type LngTerminal, type LngTerminalsFile } from "../lib/lngTerminals";
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
import { usTester, type UsStatesFile } from "../lib/us";
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
import { TOWER_LABEL_MW, TOWER_M_PER_MW, TOWER_RADIUS_M, NIGHT_BOUNDS, unitOutKey } from "../app/day";
import { ANCHOR, BEAM_MIN_MW, HEX_KM, SMALL, angularDistance, bbox, hexBins, pairs, unitVector } from "../app/geo";
import type { ColourId, LayerId, PlantStatus, Selection, TimeMode } from "../app/store";
import type {
  Arc,
  Cable,
  CapacityFile,
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
  UnitOutputFile,
} from "../app/types";
import { memo, NONE } from "./memo";
import { priceTerrain, rampColour, type Terrain } from "./priceTerrain";
import { usLayers } from "./usLayers";
import { riskLayers } from "./riskLayers";
import type { WaterIndicator } from "../lib/risk";
import { mastrLayers } from "./mastrLayers";
import { siteLayers } from "./siteLayers";
import { inside, makeShape } from "../lib/area";
import { offshoreLayers } from "./offshoreLayers";
import { areaLayers, clipToArea } from "./areaLayers";
import { inAreaCountry } from "../app/datasets";
import { summaryFill, summaryLabels } from "./summaryLayers";
import { hexLayers } from "./hexLayers";
import { styleLayers } from "./styleLayers";
import type { Style } from "../app/maps";
import type { AreaSpec } from "../lib/area";
import { usSolarLayers } from "./usSolarLayers";
import { evLayers } from "./evLayers";
import { evEuLayers } from "./evEuLayers";
import { usGasLayers } from "./usGasLayers";
import { ghgrpLayers } from "./ghgrpLayers";
import { tyndpLayers } from "./tyndpLayers";
import { connectMoreLayers } from "./connectMoreLayers";
import { connectEuLayers } from "./connectEuLayers";
import { registerLayers } from "./registerLayers";
import { comingLayers } from "./comingLayers";
import { NZ_COLOR, NZ_POINT, ZA_COLOR, ZA_POINT, type NzFile, type ZaFile } from "../lib/regionalLive";
import { SEA_CABLE_COLOR, seaPipeLayer, type SeaCable, type SeaCablesFile, type SeaPipe } from "../lib/seaCables";
import type { MastrTech } from "../lib/mastr";

export interface Frame {
  mode: TimeMode;
  layers: Record<LayerId, boolean>;
  colour: ColourId;
  plantStatus: PlantStatus;
  plantStyle: "bars" | "beams";
  connectSide: "offtake" | "feedin";
  waterIndicator: WaterIndicator;
  mastrTech: MastrTech;
  selection: Selection | null;
  /** the dashboard's countries (ISO alpha-3), outlined */
  area: string[] | null;
  /** the dataset whose coverage is tinted */
  coverageOf: string | null;
  /** the datasets drawn in a style of their own (bubbles, hexagons, 3D bars or beams, choropleth,
   *  3D terrain: map/styleLayers.ts); their own layers are off in `layers` */
  styled: [string, Style][];
  /** which map: "main" or one of the Maps view's (keys its legend's figures) */
  scope: string;
  /** the view [west, south, east, north] */
  bounds: [number, number, number, number];
  /** the area as a drawn polygon or a circle, and the corners of one being drawn */
  drawn: AreaSpec | null;
  drawing: [number, number][] | null;
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
  /** the 24 h replay's region (Europe's or the US day files) */
  dayRegion: "eu" | "us";
  sun: { image: HTMLCanvasElement | null; next: HTMLCanvasElement | null; fade: number; bounds: [number, number, number, number] } | null;
  night: ImageBitmap | null;
}

const IDLE_MW = 20;
const LABEL_MW = 1000; // arcs from this size carry a GW label
/** A flow from this share of its border's capacity draws a bright core (where a capacity is published). */
export const FULL_SHARE = 0.9;
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

/** Where a country's (or a US region's) towers and flow ends stand. */
const anchorOf = (iso: string): [number, number] | undefined => ANCHOR[iso] ?? US_POINT[iso];

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
    case "rt_household": {
      const rf = f.retail as RetailFile | undefined;
      const n = rf ? newestOf(rf, rf.eu.series.elec_household[iso]) : null;
      return (n && stopColor(RETAIL_STOPS, n.v * 100)) || TR_NO_DATA;
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
  properties: { kind: "country" | "zone" | "flow" | "gas" | "gasNode" | "region" | "dc" | "money"; text: string; sub: string; rank: number };
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
  // prices: each country a block as high as its price (map/priceTerrain.ts)
  const terrain = facingEurope && isOn("prices") && day?.region !== "us" ? priceTerrain(fr, dayK, shapes) : null;
  const fillKey = [fr.colour, f.stats, f.outages, f.prices, f.transition, f.worldStats, f.irena, f.retail, fr.mode, day, dayK, fr.yearK, sel, Math.round(sunLight(fr) * 20)];
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
  // a dataset's per-country figure at continent scale (map/summaryLayers.ts); the datasets drawn in a
  // style of their own (map/hexLayers.ts, map/styleLayers.ts)
  layers.push(...summaryFill(fr));
  layers.push(...hexLayers(fr), ...styleLayers(fr));

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

  // ---------------------------------------------------------------- US node prices at the clock (A day in the US)
  const usNodes = day?.region === "us" && isOn("usNodePrices") ? (f[`usNodes:${day.date}`] as UsNodesFile | undefined) : undefined;
  if (usNodes && usNodes.nodes.length) {
    const k = Math.min(usNodes.slots - 1, dayK);
    const idx = memo("usNodeIdx", [usNodes], () => usNodes.nodes.map((_, i) => i));
    layers.push(
      new ScatterplotLayer<number>({
        id: "us-node-prices",
        data: idx,
        getPosition: (i) => [usNodes.nodes[i][0], usNodes.nodes[i][1]],
        getRadius: fr.zoom >= 6 ? 3 : fr.zoom >= 4.5 ? 2 : 1.4,
        radiusUnits: "pixels",
        getFillColor: (i) => {
          const p = usNodes.prices[i][k];
          return p == null ? [0, 0, 0, 0] : [...rampColour(usNodes.range, p), 220];
        },
        updateTriggers: { getFillColor: [k, usNodes], getRadius: [fr.zoom >= 6, fr.zoom >= 4.5] },
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ---------------------------------------------------------------- grid capacity: NL areas, GB connection sites
  const connect = f.connect as ConnectFile | undefined;
  if (facingEurope && connect && isOn("connect") && (inAreaCountry(fr.area, "GB") || inAreaCountry(fr.area, "NL"))) {
    const side = fr.connectSide;
    const areas = memo("nlAreas", [connect], () =>
      connect.nl.areas.flatMap((a) => a.polygons.map((polygon) => ({ a, polygon }))),
    );
    const sites = memo("gbSites", [connect], () => gbSiteTotals(connect.gb));
    layers.push(
      new SolidPolygonLayer<{ a: NlArea; polygon: [number, number][][] }>({
        id: "eu-connect-nl",
        data: inAreaCountry(fr.area, "NL") ? areas : NONE,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => [...NL_COLOR[Math.max(0, Math.min(3, side === "offtake" ? d.a.offtake : d.a.feedin))], 150],
        updateTriggers: { getFillColor: [side] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 40],
        parameters: ON_TOP,
      }),
      new ScatterplotLayer<(typeof sites)[number]>({
        id: "eu-connect-gb",
        data: inAreaCountry(fr.area, "GB") ? sites : NONE,
        getPosition: (d) => [d.site[1]!, d.site[2]!],
        getRadius: (d) => Math.min(16, 1.5 + Math.sqrt(d.mw) * 0.16),
        radiusUnits: "pixels",
        getFillColor: (d) => {
          const top = d.byType.indexOf(Math.max(...d.byType));
          return [...(GB_TYPE_COLOR[connect.gb.types[top]] ?? GB_TYPE_COLOR.Other), 170];
        },
        stroked: true,
        getLineColor: [6, 7, 10, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // France, Italy, Ireland (scripts/build_connect_more.py)
  if (facingEurope) layers.push(...connectMoreLayers(fr), ...connectEuLayers(fr), ...registerLayers(fr));
  // hydrogen projects and planned gas infrastructure (scripts/build_coming.py)
  if (facingEurope) layers.push(...comingLayers(fr));

  // ---------------------------------------------------------------- LNG send-out per terminal (GIE ALSI, newest gas day)
  const lng = f.lngTerminals as LngTerminalsFile | undefined;
  if (facingEurope && lng && isOn("lngSendOut")) {
    // the declared send-out as a thin ring, the day's send-out as the disc inside it
    layers.push(
      new ScatterplotLayer<LngTerminal>({
        id: "eu-lng-capacity",
        data: lng.terminals,
        getPosition: (t) => [t.lon, t.lat],
        getRadius: (t) => lngRadius(lngDay(t, lng.date)?.[3] ?? 0),
        radiusUnits: "pixels",
        filled: false,
        stroked: true,
        getLineColor: [...LNG_SEND, 150],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        pickable: true,
        parameters: ON_TOP,
      }),
      new ScatterplotLayer<LngTerminal>({
        id: "eu-lng-sendout",
        data: lng.terminals,
        getPosition: (t) => [t.lon, t.lat],
        getRadius: (t) => lngRadius(lngDay(t, lng.date)?.[1] ?? 0),
        radiusUnits: "pixels",
        getFillColor: [...LNG_SEND, 200],
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }

  // ---------------------------------------------------------------- EU ETS: verified CO2 per installation (placed by ETS id)
  const ets = f.ets as EtsFile | undefined;
  if (facingEurope && ets && isOn("ets")) {
    const zoomStep = fr.zoom >= 6 ? 2 : fr.zoom >= 5 ? 1 : 0;
    const placed = memo("etsPlaced", [ets], () => ets.rows.filter((r) => r[5] != null && (newestT(r) ?? 0) > 0));
    layers.push(
      new ScatterplotLayer<EtsRow>({
        id: "eu-ets",
        data: placed, // largest first, so smaller dots draw on top
        getPosition: (r) => [r[5]!, r[6]!],
        getRadius: (r) => etsRadius(newestT(r) ?? 0, fr.zoom),
        radiusUnits: "pixels",
        getFillColor: (r) => [...ETS_COLOR[r[3]], 165],
        stroked: true,
        getLineColor: [6, 7, 10, 200],
        lineWidthUnits: "pixels",
        getLineWidth: 0.6,
        updateTriggers: { getRadius: [zoomStep] },
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
  layers.push(...riskLayers(fr));
  layers.push(...mastrLayers(fr));
  layers.push(...offshoreLayers(fr));
  layers.push(...usSolarLayers(fr));
  layers.push(...evLayers(fr), ...evEuLayers(fr), ...usGasLayers(fr));
  layers.push(...ghgrpLayers(fr));
  layers.push(...tyndpLayers(fr));
  layers.push(...worldLayers(fr, near));
  layers.push(...usLayers(fr));
  layers.push(...gemLayers(fr));
  layers.push(...ctraceLayers(fr));
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
  // ---------------------------------------------------------------- prices: blocks, towers on top
  if (terrain) layers.push(...terrain.layers);
  // the 24 h replay faces its own region: Europe, or the US (its 13 regions as towers)
  const usDay = day?.region === "us";
  const facingDay = usDay ? angularDistance(fr.centre, [-96, 38]) < 60 : facingEurope;
  // ---------------------------------------------------------------- output per plant (24 h)
  if (day && facingDay && isOn("plantOutput")) layers.push(...plantOutputLayers(fr, dayK));
  const towers = day && (countries || usDay) && isOn("towers") && facingDay;
  if (towers) layers.push(...towerLayers(fr, day, dayK, countries, sel, terrain));

  // ---------------------------------------------------------------- cross-border flows
  if ((day ? facingDay : facingEurope) && isOn("flows")) {
    // a dashboard of a few countries: the flows across their borders
    const own = fr.area && fr.area.length < 5 ? new Set(fr.area) : null;
    const allArcs = flowArcs(fr, dayK);
    const flat = own ? memo("areaArcs", [allArcs, fr.area], () => allArcs.filter((a) => own.has(ISO3[a.from] ?? a.from) || own.has(ISO3[a.to] ?? a.to))) : allArcs;
    // over the price blocks the flows arc from the top of one to the top of the other
    const arcs = terrain ? memo("liftedArcs", [flat, fr.day ? fr.daySlot : 0, f.stats], () => flat.map((a) => liftArc(a, terrain))) : flat;
    const deep = !!day || !!terrain;
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
        parameters: deep ? { depthCompare: "less-equal", depthWriteEnabled: false } : ON_TOP,
      }),
      // a thin bright core where a flow uses 90 % or more of the capacity on offer
      new PathLayer<Arc>({
        id: "eu-flow-full",
        data: memo("fullArcs", [arcs], () => arcs.filter((a) => a.cap != null && a.cap > 0 && a.mw / a.cap >= FULL_SHARE)),
        getPath: (d) => d.path,
        getColor: (d) => [255, 250, 236, !sel || touches(d) ? 235 : 60],
        getWidth: 1.6,
        updateTriggers: { getColor: [sel] },
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        parameters: deep ? { depthCompare: "less-equal", depthWriteEnabled: false } : ON_TOP,
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
        parameters: { ...OVER, depthCompare: deep ? "less-equal" : "always", depthWriteEnabled: false },
      }),
    );
  }

  // ---------------------------------------------------------------- gas flows (ENTSOG, newest gas day)
  if (facingEurope && fr.mode === "live" && isOn("gasFlows")) layers.push(...gasFlowLayers(fr, sel));

  // ---------------------------------------------------------------- price-zone markers, names
  if (facingEurope) layers.push(...zoneMarkers(fr));
  layers.push(...siteLayers(fr));
  layers.push(...areaLayers(fr));
  layers.push(...summaryLabels(fr));
  if (facingEurope && countries) parts.push(countryLabels(fr, countries));
  // under MapLibre's labels (map/labels.ts), which read well on the globe
  // a dashboard's area: its data only (map/areaLayers.ts)
  return clipToArea(fr, layers).map((l) => ((l.props as { beforeId?: string }).beforeId ? l : l.clone({ beforeId: LABELS_BELOW } as never)));
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
  const capFile = fr.files.capacity as CapacityFile | undefined;
  return memo("arcs", [day, dayK, flows, capFile], () => {
    const out: Arc[] = [];
    // capacity a->b and b->a for the flow's own time: the day file's slot, or the live file's
    const liveCap = (a: string, b: string, ts: string): [number | null, number | null, string] => {
      const row = capFile?.borders.find((x) => x.a === a && x.b === b);
      if (!row || !capFile) return [null, null, ""];
      const k = Math.floor((Date.parse(ts) - Date.parse(capFile.start)) / 1000 / capFile.step_s);
      return k >= 0 && k < capFile.slots ? [row.ab[k], row.ba[k], row.doc] : [null, null, ""];
    };
    const rows = day
      ? day.borders.map((b) => ({
          a: b.a,
          b: b.b,
          mw: b.values[dayK],
          ts: new Date(Date.parse(day.start) + dayK * day.step_s * 1000).toISOString(),
          cap: [b.capacity_ab?.[dayK] ?? null, b.capacity_ba?.[dayK] ?? null, b.capacity_doc ?? ""] as [number | null, number | null, string],
        }))
      : (flows?.borders ?? []).map((b) => ({ a: b.a, b: b.b, mw: b.mw, ts: b.ts, cap: liveCap(b.a, b.b, b.ts) }));
    rows.forEach((f, n) => {
      if (f.mw == null || Math.abs(f.mw) < IDLE_MW) return;
      const [from, to] = f.mw > 0 ? [f.a, f.b] : [f.b, f.a];
      const pa = anchorOf(from);
      const pb = anchorOf(to);
      if (!pa || !pb) return;
      const path = curvedPath(pa, pb, 0.16, 40);
      const cap = f.mw > 0 ? f.cap[0] : f.cap[1];
      out.push({ from, to, mw: Math.abs(f.mw), ts: f.ts, path, timestamps: flowDistances(path, false, n * 91_000), cap, capDoc: f.cap[2] });
    });
    return out.sort((x, y) => x.mw - y.mw);
  });
}

export interface GasArc {
  from: string;
  to: string;
  /** the country at the European end (LNG arcs: the country of the terminals) */
  country: string;
  gwh: number;
  pair: GasPair;
  path: [number, number][];
  timestamps: number[];
}

/** Net gas flow of each pair on the newest gas day. Gas entering Europe (pipelines from
 *  outside, LNG) in bright amber and wide; gas moving between European countries in a quieter
 *  sand, thinner, with chevrons only from 50 GWh/d. Each source is labelled with its total.
 *  The arcs bow the other way from the power flows, so the two layers stay apart. */
function gasFlowLayers(fr: Frame, sel: string | null): Layer[] {
  const g = fr.files.gasFlows as GasFlowsFile | undefined;
  if (!g) return [];
  const allArcs = memo("gasArcs", [g], () => {
    const out: GasArc[] = [];
    g.pairs.forEach((p, n) => {
      const net = latestOf(p.net);
      if (net == null || Math.abs(net) < GAS_IDLE_GWH) return;
      const [from, to] = net > 0 ? [p.a, p.b] : [p.b, p.a];
      const a = endAt(from, p.b, ANCHOR);
      const b = endAt(to, p.b, ANCHOR);
      if (!a || !b) return;
      const path = curvedPath(a, b, p.kind === "border" ? -0.16 : -0.1, 40);
      out.push({ from, to, country: p.b, gwh: Math.abs(net), pair: p, path, timestamps: flowDistances(path, false, n * 67_000) });
    });
    // transit first, imports drawn over it
    return out.sort((x, y) => Number(x.pair.kind !== "border") - Number(y.pair.kind !== "border") || x.gwh - y.gwh);
  });
  // a dashboard of a few countries: the gas crossing into or out of them
  const own = fr.area && fr.area.length < 5 ? new Set(fr.area) : null;
  const arcs = own ? memo("gasArcsArea", [allArcs, fr.area], () => allArcs.filter((a) => [a.from, a.to, a.country].some((c) => own.has(ISO3[c] ?? c)))) : allArcs;
  const entry = (a: GasArc) => a.pair.kind !== "border";
  const touches = (a: GasArc) => a.from === sel || a.to === sel || a.country === sel;
  // each source's total into Europe on the gas day (sum of its arcs, computed); LNG per country
  const sources = memo("gasSources", [arcs], () => {
    const by = new Map<string, { key: string; at: [number, number]; gwh: number; name: string }>();
    for (const a of arcs) {
      if (!entry(a)) continue;
      const lng = a.from === "LNG";
      const key = lng ? `LNG:${a.country}` : a.from;
      const at = endAt(a.from, a.country, ANCHOR);
      if (!at) continue;
      const cur = by.get(key) ?? { key, at, gwh: 0, name: lng ? "LNG" : (GAS_NODE_LABEL[a.from] ?? g.nodes[a.from] ?? a.from) };
      cur.gwh += a.gwh;
      by.set(key, cur);
    }
    return [...by.values()].sort((x, y) => y.gwh - x.gwh);
  });
  parts.push(
    memo("lbl-gas", [arcs, sel, fr.isMobile], () =>
      (sel ? arcs.filter(touches) : arcs.filter((a) => !entry(a) && a.gwh >= (fr.isMobile ? 800 : GAS_TRANSIT_LABEL_GWH))).map((a) =>
        label("gas", a.path[20], gwhd(a.gwh), "", -a.gwh),
      ),
    ),
    memo("lbl-gas-nodes", [sources, fr.isMobile], () =>
      sources
        .filter((s) => (s.name !== "LNG" || s.gwh >= 150) && (!fr.isMobile || s.gwh >= 400))
        .map((s) => label("gasNode", s.at, `${s.name} ${gwhd(s.gwh)}`, "", -s.gwh)),
    ),
  );
  const tint = (d: GasArc, a: number) => [...(entry(d) ? GAS_FLOW : GAS_TRANSIT), !sel || touches(d) ? a : 40] as [number, number, number, number];
  return [
    new ScatterplotLayer<(typeof sources)[number]>({
      id: "eu-gas-nodes",
      data: sources,
      getPosition: (d) => d.at,
      getRadius: (d) => 3 + Math.min(7, Math.sqrt(d.gwh) / 8),
      radiusUnits: "pixels",
      getFillColor: [...GAS_FLOW, 235],
      getLineColor: [6, 8, 12, 220],
      lineWidthUnits: "pixels",
      getLineWidth: 1.2,
      stroked: true,
      parameters: ON_TOP,
    }),
    new PathLayer<GasArc>({
      id: "eu-gas-casing",
      data: arcs,
      getPath: (d) => d.path,
      getColor: (d) => [4, 6, 10, !sel || touches(d) ? (entry(d) ? 200 : 150) : 50],
      getWidth: (d) => gasWidth(d.gwh, entry(d)) * 0.4 + 2,
      updateTriggers: { getColor: [sel] },
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      parameters: ON_TOP,
    }),
    new FlowArrowLayer<GasArc>({
      id: "eu-gas-flows",
      data: arcs,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: (d) => tint(d, entry(d) ? 255 : 210),
      getWidth: (d) => gasWidth(d.gwh, entry(d)),
      // [guide line px, chevron half span px, chevron opacity]: small transit flows carry no chevrons
      getArrowStyle: (d) => [entry(d) ? 1.4 + Math.min(2.2, d.gwh / 700) : 0.8 + Math.min(1.4, d.gwh / 900), 3 + Math.min(7, gasWidth(d.gwh, entry(d)) / 3), entry(d) || d.gwh >= 50 ? 1 : 0],
      updateTriggers: { getColor: [sel] },
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      pickable: true,
      phase: fr.clock.phase,
      spacing: fr.clock.spacing,
      strokePx: 2.2,
      lineAlpha: 0.8,
      parameters: { ...OVER, depthCompare: "always", depthWriteEnabled: false },
    }),
  ];
}

/** One plant of the output file, for the layers and the hover card. */
export interface PlantOutputRow {
  k: number;
  at: [number, number];
  fuel: string;
  iso: string;
  capacity: number | null;
  name: string;
  units: number;
}

/** What each large plant produced at the clock (Europe: ENTSO-E per unit, placed with the JRC
 *  database; US: EPA CAMPD's fossil units, hourly): a ring for its capacity, a disc for its output, both in the fuel's colour.
 *  The disc glides between two 15-min values (drawing only); cards show the slot's value. */
function plantOutputLayers(fr: Frame, dayK: number): Layer[] {
  const file = fr.day ? (fr.files[unitOutKey(fr.dayRegion, fr.day.date)] as UnitOutputFile | undefined) : undefined;
  if (!file) return [];
  const rows = memo("plantOutRows", [file], () =>
    file.plants.map((p, k) => ({ k, at: [p[0], p[1]] as [number, number], fuel: file.fuels[p[2]], iso: p[3], capacity: p[4], name: p[5], units: p[6] })),
  );
  const frac = Math.max(0, Math.min(1, fr.daySlot - dayK));
  const next = Math.min(file.slots - 1, dayK + 1);
  const now = (r: PlantOutputRow) => {
    const v = file.output[r.k];
    const a = v[dayK];
    if (a == null) return null;
    const b = v[next] ?? a;
    return Math.max(0, a + (b - a) * frac);
  };
  // pixels for a MW figure: the square root, so area follows power
  const px = (mw: number) => 1.2 + Math.sqrt(Math.max(0, mw)) * (fr.zoom < 5 ? 0.2 : 0.28);
  const colour = (r: PlantOutputRow) => FUEL_COLOR[r.fuel] ?? FUEL_COLOR.other;
  const key = [fr.daySlot, file];
  return [
    new ScatterplotLayer<PlantOutputRow>({
      id: "eu-plant-capacity",
      data: rows,
      getPosition: (r) => r.at,
      getRadius: (r) => px(r.capacity ?? 0),
      radiusUnits: "pixels",
      filled: false,
      stroked: true,
      getLineColor: (r) => [...colour(r), 120],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      updateTriggers: { getRadius: [fr.zoom < 5] },
      parameters: ON_TOP,
    }),
    new ScatterplotLayer<PlantOutputRow>({
      id: "eu-plant-glow",
      data: rows,
      getPosition: (r) => r.at,
      getRadius: (r) => px(now(r) ?? 0) * 1.9,
      radiusUnits: "pixels",
      getFillColor: (r) => [...colour(r), (now(r) ?? 0) > 1 ? 40 : 0],
      updateTriggers: { getRadius: [...key, fr.zoom < 5], getFillColor: key },
      parameters: ADD,
    }),
    new ScatterplotLayer<PlantOutputRow>({
      id: "eu-plant-output",
      data: rows,
      getPosition: (r) => r.at,
      getRadius: (r) => (now(r) == null ? 1 : px(now(r) ?? 0)),
      radiusUnits: "pixels",
      getFillColor: (r) => (now(r) == null ? [120, 124, 136, 120] : [...colour(r), 230]),
      updateTriggers: { getRadius: [...key, fr.zoom < 5], getFillColor: key },
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
}

/** A flow lifted from the top of one price block to the top of the other, bowing upwards. */
function liftArc(a: Arc, terrain: Terrain): Arc {
  const h0 = terrain.height(a.from);
  const h1 = terrain.height(a.to);
  const n = a.path.length - 1;
  const path = a.path.map((p, i) => {
    const t = i / n;
    return [p[0], p[1], h0 + (h1 - h0) * t + 22_000 * Math.sin(Math.PI * t)];
  }) as unknown as [number, number][];
  return { ...a, path };
}

/** Text the tower and price labels may use (deck.gl draws its own glyph atlas). */
const LABEL_CHARS = `${Array.from({ length: 95 }, (_, i) => String.fromCharCode(32 + i)).join("")}€·−`;

function towerLayers(fr: Frame, day: DayFile, dayK: number, countries: CountriesFile | undefined, sel: string | null, terrain: Terrain | null): Layer[] {
  const lifted = (iso: string) => (terrain ? terrain.height(iso) : 0);
  const names = memo("towerNames", [countries, day.names], () => new Map([...(countries?.countries.map((c) => [c.iso, c.name] as const) ?? []), ...Object.entries(day.names ?? {})]));
  // the US regions are large: 1 GW stands 7 km there, 14 km in Europe
  const mPerMw = day.region === "us" ? TOWER_M_PER_MW / 2 : TOWER_M_PER_MW;
  const frac = Math.max(0, Math.min(1, fr.daySlot - dayK));
  const next = Math.min(day.slots - 1, dayK + 1);
  const towers: TowerPiece[] = [];
  for (const [iso, series] of Object.entries(day.countries)) {
    if (!anchorOf(iso) || (sel && sel !== iso)) continue;
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
  // where each tower ends (metres), for the labels
  const tops = new Map<string, number>();
  for (const t of towers) tops.set(t.iso, Math.max(tops.get(t.iso) ?? 0, lifted(t.iso) + (t.base + t.drawn) * mPerMw));
  const labelled = towers
    .filter((t) => t.group === top.get(t.iso) && t.total >= TOWER_LABEL_MW)
    .sort((a, b) => b.total - a.total)
    .slice(0, fr.isMobile ? 5 : 9);
  // US: the day-ahead price at the hub of the region's market (one hub per region)
  const usHub =
    day.region === "us"
      ? memo("towerHubs", [day, dayK], () => new Map(Object.values(day.prices).flatMap((p) => (p.values[dayK] != null ? [[p.country, p.values[dayK] as number] as const] : []))))
      : null;
  const pools = memo("towerPools", [day, dayK, sel], () => {
    const best = new Map<string, TowerPiece>();
    for (const t of towers) if (!best.has(t.iso) || t.mw > best.get(t.iso)!.mw) best.set(t.iso, t);
    return [...best.values()].map((t) => ({ iso: t.iso, total: t.total, group: t.group }));
  });
  return [
    new ScatterplotLayer<{ iso: string; total: number; group: string }>({
      id: "eu-tower-pools",
      data: pools,
      getPosition: (t) => [...anchorOf(t.iso)!, lifted(t.iso) + 600] as [number, number, number],
      getRadius: (t) => 30_000 + Math.sqrt(t.total) * 450,
      updateTriggers: { getPosition: [fr.daySlot, !!terrain] },
      getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 70],
      stroked: false,
      parameters: ADD,
    }),
    new ColumnLayer<TowerPiece>({
      id: "eu-towers",
      data: towers,
      getPosition: (t) => [...anchorOf(t.iso)!, lifted(t.iso) + t.base * mPerMw] as [number, number, number],
      getElevation: (t) => t.drawn * mPerMw,
      getFillColor: (t) => [...(FUEL_COLOR[t.group] ?? FUEL_COLOR.other), 235],
      radius: TOWER_RADIUS_M,
      diskResolution: 24,
      extruded: true,
      pickable: true,
      material: { ambient: 0.55, diffuse: 0.6, shininess: 20, specularColor: [50, 50, 50] },
    }),
    new TextLayer<TowerPiece>({
      id: "eu-tower-labels",
      data: labelled,
      getPosition: (t) => [...anchorOf(t.iso)!, (tops.get(t.iso) ?? 0) + 25_000] as [number, number, number],
      // generation and, with the Prices layer, the price; in the US the region's hub price
      getText: (t) => {
        const gwText = `${t.iso} ${Math.round(t.total / 1000)} GW`;
        if (usHub) {
          const p = usHub.get(t.iso);
          return p != null ? `${gwText} · ${p < 0 ? "−" : ""}$${Math.round(Math.abs(p))}` : gwText;
        }
        const p = terrain?.price(t.iso);
        return `${gwText}${p != null ? ` · ${Math.round(p)} €` : ""}`;
      },
      getSize: 12,
      getColor: [236, 240, 246, 255],
      fontFamily: "Inter, system-ui, sans-serif",
      fontWeight: 700,
      characterSet: LABEL_CHARS,
      background: true,
      getBackgroundColor: [6, 9, 14, 200],
      backgroundPadding: [4, 2],
      updateTriggers: { getText: [dayK, !!terrain, usHub] },
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
  const live = fr.colour === "price" ? "price" : fr.colour === "renewable" ? "renewable" : null;
  const retail = fr.colour === "rt_household" ? (fr.files.retail as RetailFile | undefined) : undefined;
  const day = fr.day;
  const dayK = day ? Math.min(day.slots - 1, Math.floor(fr.daySlot)) : 0;
  const stats = live ? (fr.files.stats as StatsFile | undefined) : undefined;
  const names = memo("lbl-names", [countries, detail, tr, transition, fr.yearK, pr, prices, ir, irena, fr.mode, live, day, dayK, stats, retail], () =>
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
        } else if (retail) {
          const n = newestOf(retail, retail.eu.series.elec_household[c.iso]);
          sub = n ? euroCents(n.v) : "";
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
  // with zones.json (outlines built from NUTS regions): the zones of countries with several, shaded
  const outlines = fr.files.zones as ZonesFile | undefined;
  if (outlines) {
    const shapes = memo("zoneShapes", [outlines, prices], () =>
      zoneMarkerData(prices).flatMap((d) => (outlines.zones[d.zone]?.polygons ?? []).map((rings) => ({ ...d, polygon: rings.map(pairs) }))),
    );
    return [
      new SolidPolygonLayer<ZoneShape>({
        id: "pr-zones",
        data: shapes,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => [...(stopColor(m.stops, m.value(d.z)) ?? NO_DATA), 235],
        updateTriggers: { getFillColor: [pr] },
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 50],
        parameters: ON_TOP,
      }),
      new PathLayer<ZoneShape>({
        id: "pr-zones-lines",
        data: shapes,
        getPath: (d) => d.polygon[0],
        getColor: (d) => (d.zone === zoneSel ? [255, 246, 230, 255] : [8, 10, 14, 200]),
        widthUnits: "pixels",
        getWidth: (d) => (d.zone === zoneSel ? 2 : 0.8),
        updateTriggers: { getColor: [zoneSel], getWidth: [zoneSel] },
        parameters: ON_TOP,
      }),
    ];
  }
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

/** zones.json (scripts/build_shapes.py): each zone's NUTS 3 regions and outline. */
export interface ZonesFile {
  fetched: string;
  source: string;
  zones: Record<string, { nuts3: string[]; exact: boolean; polygons: number[][][] }>;
}
type ZoneShape = ZoneMarker & { polygon: [number, number][][] };

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
        capRounded: true,
        jointRounded: true,
        getColor: (c) => (CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).color,
        getWidth: (c) => (CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).width,
        widthUnits: "pixels",
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  }
  // EMODnet: power cables in European seas (cables layer), pipelines at sea (gas and oil layers)
  const sea = f.seaCables as SeaCablesFile | undefined;
  if (sea && isOn("cables"))
    out.push(
      new PathLayer<SeaCable>({
        id: "w-sea-cables",
        data: memo("seaCablesNear", [sea, fr.camKey], () => sea.cables.filter((c) => near([c[3][0], c[3][1]]))),
        getPath: (c) => pairs(c[3]),
        getColor: [...SEA_CABLE_COLOR, 170],
        getWidth: 1.1,
        widthUnits: "pixels",
        pickable: true,
        parameters: ON_TOP,
      }),
    );
  if (sea && (isOn("gasPipes") || isOn("oilPipes"))) {
    const show = (m: string | null) => seaPipeLayer(m).some((id) => isOn(id));
    out.push(
      new PathLayer<SeaPipe>({
        id: "w-sea-pipes",
        data: memo("seaPipesNear", [sea, fr.camKey, isOn("gasPipes"), isOn("oilPipes")], () => sea.pipelines.filter((p) => show(p[1]) && near([p[6][0], p[6][1]]))),
        getPath: (p) => pairs(p[6]),
        getColor: (p) => [...(seaPipeLayer(p[1])[0] === "gasPipes" ? GEM_PIPES.gasPipes.color : GEM_PIPES.oilPipes.color), 170],
        getWidth: 1,
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
    // with the US plants layer on, EIA-860M wins in the US: GEM's points there are left out
    const usStates = fr.layers.plantsUS ? (f.usStates as UsStatesFile | undefined) : undefined;
    const inUs = memo("gemInUs", [wp, usStates], () => {
      if (!usStates) return null;
      const test = usTester(usStates);
      return wp.points.map((p) => (p[0] < -64 || p[0] > 170) && p[1] > 17 && test(p[0], p[1]));
    });
    // with Europe's plants on, powerplantmatching wins there for operating plants (GEM keeps the
    // building, planned and retired ones, which the European file does not hold)
    const euCountries = fr.layers.plantsEU && fr.plantStatus === "operating" ? (f.countries as CountriesFile | undefined) : undefined;
    const inEu = memo("gemInEurope", [wp, euCountries], () => {
      if (!euCountries) return null;
      const eu = makeShape("countries", "europe", "Europe", euCountries.countries.flatMap((c) => c.polygons));
      return wp.points.map((p) => inside(eu, p[0], p[1]));
    });
    const idx = memo("nearPlants", [wp, st, fr.camKey, inUs, inEu], () => {
      const c = unitVector(fr.centre[0], fr.centre[1]);
      const keep: number[] = [];
      wp.points.forEach((p, k) => {
        const v = vectors[k];
        if (p[3] === st && !inUs?.[k] && !inEu?.[k] && v[0] * c[0] + v[1] * c[1] + v[2] * c[2] > 0.17) keep.push(k);
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
    for (const [key, grid, at, color, text] of [
      ["nz", "nz", NZ_POINT, NZ_COLOR, (v: NzFile) => [v.total_mw, `NZ ${(v.total_mw / 1000).toFixed(1)} GW`]],
      ["za", "za", ZA_POINT, ZA_COLOR, (v: ZaFile) => [3000, v.loadshedding_stage ? `ZA stage ${v.loadshedding_stage}` : "ZA"]],
    ] as const) {
      const v = f[key] as (NzFile & ZaFile) | undefined;
      if (!v || !near(at)) continue;
      const [mw, txt] = text(v) as [number, string];
      const dots = memo(`${key}Dots`, [v], () => [{ id: key.toUpperCase(), at, mw, label: txt }]);
      parts.push(memo(`lbl-${key}`, [dots, fr.zoom >= 2.2], () => (fr.zoom >= 2.2 ? dots.map((d) => label("region", d.at, d.label, "", -d.mw)) : [])));
      out.push(...regionDotLayers(`w-${grid}`, dots, color, false));
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


/** Climate TRACE's modelled emissions per facility (world); the side facing the camera only. */
function ctraceLayers(fr: Frame): Layer[] {
  const ct = fr.layers.ctrace ? (fr.files.ctrace as CtraceFile | undefined) : undefined;
  if (!ct) return [];
  const facing = nearFilter(fr);
  const near = memo("ctrace-near", [ct, fr.camKey], () => ct.rows.filter((r) => facing([r[0], r[1]])));
  const zoomStep = fr.zoom >= 5 ? 2 : fr.zoom >= 4 ? 1 : 0;
  return [
    new ScatterplotLayer<CtRow>({
      id: "w-ctrace",
      data: near, // largest first, so smaller dots draw on top
      getPosition: (r) => [r[0], r[1]],
      getRadius: (r) => ctRadius(r[5], fr.zoom),
      radiusUnits: "pixels",
      getFillColor: (r) => [...CT_COLOR[ct.group_of[r[4]]], 150],
      stroked: true,
      getLineColor: [6, 7, 10, 190],
      lineWidthUnits: "pixels",
      getLineWidth: 0.5,
      updateTriggers: { getRadius: [zoomStep] },
      pickable: true,
      parameters: ON_TOP,
    }),
  ];
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
