// Datasets: every kind of data on the map by category (app/datasets.json), one entry however
// many regions and sources it joins ("Transmission lines" = Europe, the US and the world). A name
// opens where it has data and its sources (the map tints those countries); the switch shows it;
// its key appears while it is on. Datasets that colour the countries are listed with the others
// (one colouring at a time).

import { useState, type ReactNode } from "react";

import { FUEL_COLOR, FUEL_LABEL } from "../lib/energy";
import { GAS_FLOW, GAS_TRANSIT, GAS_TRANSIT_LABEL_GWH, type GasFlowsFile } from "../lib/gasFlows";
import { ETS_COLOR, mt, type EtsFile } from "../lib/ets";
import { LNG_SEND, type LngTerminalsFile } from "../lib/lngTerminals";
import { RETAIL_STOPS, RETAIL_TICKS } from "../lib/retail";
import { CT_COLOR, type CtraceFile } from "../lib/ctrace";
import { OUTAGE_STOPS, OUTAGE_TICKS, WATER_COLOR, WATER_INDICATORS, newestYear, type UsOutagesFile, type WaterFile } from "../lib/risk";
import { MASTR_LABEL, MASTR_STOPS, MASTR_TECHS, MASTR_TICKS, MASTR_UNIT_ZOOM, type MastrMuniFile } from "../lib/mastr";
import { GB_TYPE_COLOR, NL_COLOR, gwText, type ConnectFile } from "../lib/connect";
import { IT_CLASSES, IT_COLOR, ROOM_CLASSES } from "../lib/connectMore";
import { SEA_CABLE_COLOR } from "../lib/seaCables";
import { GAS_CAT_COLOR, H2_STAGE_COLOR } from "../lib/coming";
import { PROTECTED_COLOR, RAIL_COLOR, ROAD_COLOR, floodLabel, type ConstraintsFile } from "../lib/constraints";
import type { UsNodesFile } from "../lib/usNodes";
import { IRENA_METRICS, IRENA_STOPS, IRENA_TICKS } from "../lib/irena";
import { PRICE_METRICS, stopGradient } from "../lib/prices";
import { SUN_MAX_WM2 } from "../lib/sunLayer";
import { rgbCss, type RGB } from "../lib/theme";
import { OFFSHORE_LABEL, OFFSHORE_STYLE, type OffshoreWindFile } from "../lib/offshoreWind";
import { METRICS, metricGradient } from "../lib/transition";
import { ACCESS_STOPS, ACCESS_TICKS, BR_COLOR, DC_COLOR, ON_COLOR, TW_COLOR, US_COLOR } from "../lib/world";
import { HV_STEPS, PLANT_TYPE_COLOR, PLANT_TYPE_LABEL, STATUS_LABEL } from "../lib/worldPlants";
import { QUEUE_COLOR, QUEUE_RATIO_TICKS, US_BANDS, US_TYPE_COLOR, US_TYPE_LABEL, US_TYPE_ORDER, queueRatioCss } from "../lib/us";
import { PLANT_DETAIL_ZOOM, PLANT_MIN_MW, QUEUE_M_PER_GW } from "../map/usLayers";
import { CABLE_STYLE, FLOW, GAS, HVDC, MULTI_ZONE, OFFLINE_STOPS, PRICE_STOPS, SHARE_STOPS, SUBSTATION, VOLTAGE_BANDS, gradientCss } from "../app/colors";
import { BEAM_MIN_MW } from "../app/geo";
import { useDataStore, useFile } from "../app/data";
import type { StatsFile } from "../app/types";
import { priceRange, rampCss } from "../map/priceTerrain";
import { currentDay } from "../map/tooltip";
import { COLOURS, actions, findDashboard, useApp, type ColourId, type LayerGroup, type LayerId, type PlantStatus, type TimeMode } from "../app/store";
import { panelOf, type MapPanel, type Style } from "../app/maps";
import { CATEGORIES, DATASETS, coverageLabel, covers, datasetModes, datasetOn, datasetsOn, partsIn, placesText, toggleDataset, type Dataset } from "../app/datasets";
import { useCountryNames } from "./Dashboards";
import type { CoverageFile } from "../lib/coverage";
import { SUMMARIES, SUMMARY_ALPHA, summaryOf, summaryValues } from "../map/summaryLayers";
import { styleOf, stylesOf } from "../map/styleLayers";
import { StyleChips, StyleKey } from "./StyleControls";

import type { AtlasFile, AtlasId } from "../lib/atlas";
import { ghgrpColor, type GhgrpFile } from "../lib/ghgrp";
import { TYNDP_STYLE, type TyndpFile } from "../lib/tyndp";

const muted = "text-[#8d94a1]";
const MODE_LABEL: Record<TimeMode, string> = { live: "Live", day: "24 h", years: "Years" };

function Scale({ gradient, ticks, note }: { gradient: string; ticks: string[]; note?: ReactNode }) {
  return (
    <div>
      <div className="h-2 rounded-sm" style={{ background: gradient }} />
      <div className={`mt-0.5 flex justify-between text-[9px] ${muted}`}>
        {ticks.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      {note && <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>{note}</div>}
    </div>
  );
}

const Swatch = ({ color, label, kind = "dot" }: { color: string; label: string; kind?: "dot" | "line" | "dash" | "ring" | "half" }) => (
  <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-300">
    {kind === "dot" && <span className="h-2 w-2 rounded-full" style={{ background: color }} />}
    {kind === "ring" && <span className="h-2 w-2 rounded-full border" style={{ borderColor: color }} />}
    {kind === "half" && <span className="h-2 w-2 rounded-full border" style={{ borderColor: color, background: `color-mix(in srgb, ${color} 35%, transparent)` }} />}
    {kind === "line" && <span className="h-[2px] w-4 rounded" style={{ background: color }} />}
    {kind === "dash" && <span className="w-4 border-t border-dashed" style={{ borderColor: color }} />}
    {label}
  </span>
);
const Swatches = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap gap-x-3 gap-y-1">{children}</div>;
const fuelSwatches = (groups: string[], color: Record<string, RGB>, label: Record<string, string>) => (
  <Swatches>
    {groups.map((g) => (
      <Swatch key={g} color={rgbCss(color[g] ?? [150, 150, 150])} label={label[g] ?? g} />
    ))}
  </Swatches>
);
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>{children}</div>;

/** The status key shared by GEM's point layers. */
const pointStatus = (color: string) => (
  <Swatches>
    <Swatch color={color} label="operating" />
    <Swatch color={color} kind="half" label="building" />
    <Swatch color={color} kind="ring" label="planned" />
    <Swatch color="rgb(130,134,146)" label="idle" />
  </Swatches>
);
const pipeStatus = (color: string) => (
  <Swatches>
    <Swatch color={color} kind="line" label="operating" />
    <Swatch color={color} kind="dash" label="building or planned" />
  </Swatches>
);

export function ColourLegend({ colour }: { colour: ColourId }) {
  if (colour === "renewable") return <Scale gradient={gradientCss(SHARE_STOPS)} ticks={["0 %", "50 %", "100 % renewable"]} note="share of generation, newest 15-min interval (ENTSO-E)" />;
  if (colour === "price")
    return (
      <Scale
        gradient={gradientCss(PRICE_STOPS)}
        ticks={["0", "125", "≥ 250 €/MWh"]}
        note={
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm" style={{ background: rgbCss(MULTI_ZONE) }} /> several price zones (see the panel)
          </span>
        }
      />
    );
  if (colour === "offline") return <Scale gradient={gradientCss(OFFLINE_STOPS)} ticks={["0", "15", "≥ 30 GW offline"]} note="generating units unavailable now (ENTSO-E A80)" />;
  if (colour.startsWith("ir_")) {
    const m = IRENA_METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={gradientCss(IRENA_STOPS)} ticks={IRENA_TICKS} note={`${m.note}; the years mode shows each year, live the newest`} />;
  }
  if (colour === "rt_household")
    return (
      <Scale
        gradient={gradientCss(RETAIL_STOPS)}
        ticks={RETAIL_TICKS}
        note="What households pay per kWh, all taxes included. Europe: euro cents, Eurostat's newest half-year, band DC (2,500–4,999 kWh a year). US states: US cents, EIA's average residential price, newest month."
      />
    );
  if (colour === "access") return <Scale gradient={gradientCss(ACCESS_STOPS)} ticks={ACCESS_TICKS} note="newest year per country (World Bank)" />;
  if (colour.startsWith("pr_")) {
    const m = PRICE_METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={stopGradient(m.stops)} ticks={m.ticks} note={`${m.note} · 12 months · zone markers where a country has several zones`} />;
  }
  if (colour.startsWith("tr_")) {
    const m = METRICS.find((x) => x.id === colour.slice(3))!;
    return <Scale gradient={metricGradient(m)} ticks={m.ticks} note={`${m.note} (Ember)`} />;
  }
  return null;
}

/** The Prices layer's key: the colour runs over the replayed day's own range. */
function PriceKey() {
  const mode = useApp((s) => s.mode);
  const files = useDataStore((d) => d.files);
  const range = priceRange(mode === "day" && currentDay()?.region !== "us" ? currentDay() : null, files.stats as StatsFile | undefined);
  const ticks = range ? [`${Math.round(range[0])}`, `${Math.round((range[0] + range[1]) / 2)}`, `${Math.round(range[1])} €/MWh`] : ["cheapest", "", "dearest"];
  return (
    <Scale
      gradient={rampCss}
      ticks={ticks}
      note={`Slab height: day-ahead price (100 €/MWh stands 50 km; several zones: their median). Colour: cheapest to dearest ${mode === "day" ? "of this day" : "right now"}; below zero lies flat in cyan. Towers on the slabs: generation. ENTSO-E.`}
    />
  );
}

/** Gas flows: the newest complete gas day, sources outside Europe placed for reading. */
function LngKey() {
  const day = useDataStore((d) => (d.files.lngTerminals as LngTerminalsFile | undefined)?.date);
  return (
    <>
      <Swatches>
        <Swatch color={rgbCss(LNG_SEND)} label="send-out into the grid" />
        <Swatch color={rgbCss(LNG_SEND)} kind="ring" label="declared send-out" />
      </Swatches>
      <Note>Gas day {day ?? "…"} (GWh/d); area follows the flow. Each EU terminal reporting to GIE ALSI; hover for the day's figures.</Note>
    </>
  );
}

function UsNodesKey() {
  const files = useDataStore((d) => d.files);
  const day = currentDay();
  const f = day?.region === "us" ? (files[`usNodes:${day.date}`] as UsNodesFile | undefined) : undefined;
  const r = f?.range;
  const ca = f?.markets.CAISO;
  return (
    <Scale
      gradient={rampCss}
      ticks={r ? [`$${Math.round(r[0])}`, `$${Math.round((r[0] + r[1]) / 2)}`, `$${Math.round(r[1])}/MWh`] : ["cheapest", "", "dearest"]}
      note={`Day-ahead price at the clock's hour; colour from the day's 2nd to 98th percentile (computed), below zero in cyan. CAISO's nodes placed by CAISO's price map${ca ? ` (${ca.placed.toLocaleString("en-US")} of ${ca.nodes.toLocaleString("en-US")})` : ""}, California and the Western utilities in its market. ERCOT, MISO, SPP, NYISO and ISO-NE publish no node positions: their spread is in the panel.`}
    />
  );
}

function ConnectKey() {
  const cf = useDataStore((d) => d.files.connect as ConnectFile | undefined);
  const side = useApp((s) => s.connectSide);
  const gb = cf?.gb;
  const total = gb ? gb.projects.reduce((a, p) => a + Math.max(0, p[2] - p[3]), 0) : 0;
  const placed = gb ? gb.projects.reduce((a, p) => a + (gb.sites[p[1]][1] != null ? Math.max(0, p[2] - p[3]) : 0), 0) : 0;
  return (
    <>
      <div className="mb-1 flex items-center gap-1.5">
        <span className="text-[10px] text-slate-400">Netherlands, Ireland:</span>
        {(["offtake", "feedin"] as const).map((s) => (
          <button
            key={s}
            onClick={() => actions.setConnectSide(s)}
            className={`rounded-md border px-2 py-0.5 text-[10.5px] ${side === s ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
          >
            {s === "offtake" ? "new demand" : "new generation"}
          </button>
        ))}
      </div>
      <Swatches>
        {(cf?.nl.status ?? ["available", "limited", "under study", "shortage"]).map((label, i) => (
          <Swatch key={label} color={rgbCss(NL_COLOR[i])} label={label} />
        ))}
      </Swatches>
      <Swatches>
        {["Storage", "Solar", "Wind onshore", "Wind offshore", "Demand"].map((t) => (
          <Swatch key={t} color={rgbCss(GB_TYPE_COLOR[t])} label={t.toLowerCase()} />
        ))}
      </Swatches>
      <Note>
        Netherlands: each supply area as the regional operators' capacity map shows it. Great Britain: MW waiting to connect at each site (TEC register, {gb?.date ?? "…"}), coloured by the largest
        type; {gwText(placed)} of {gwText(total)} placed, at sites named after a GSP in NESO's lookup; the rest are in the panel. Spain publishes no positions: see the panel.
      </Note>
      <Swatches>
        {ROOM_CLASSES.map((label, i) => (
          <Swatch key={label} color={rgbCss(NL_COLOR[i])} label={label} kind="dot" />
        ))}
      </Swatches>
      {side === "feedin" && (
        <Swatches>
          {IT_CLASSES.map((label, i) => (
            <Swatch key={label} color={rgbCss(IT_COLOR[i])} label={label} />
          ))}
        </Swatches>
      )}
      <Note>
        Dots, MW (MVA) left as published: France (new generation), each substation's S3REnR capacity still to allocate (Capareseau); Ireland, each 38 kV and 110 kV station's
        and MV transformer's demand or firm generation capacity available (ESB Networks heatmap). Italy (new generation): GW requested to connect per region, renewables and storage
        (Terna Econnextion). Portugal and Poland publish no positions: see the panel. Also Bulgaria (ESO), Czechia (ČEPS, suitability in 2031), Denmark (Energinet and the DSOs),
        Estonia (Elering, expandable or not), Lithuania (Litgrid), Luxembourg (Creos), Malta (Enemalta) and Sweden (Svenska kraftnät, per county); Austria (APG) and Baden-Württemberg
        (TransnetBW) publish no positions: see the panel.
      </Note>
    </>
  );
}

const GAS_LABEL: Record<string, string> = { TRA: "gas pipeline", LNG: "LNG", UGS: "gas storage", H2T: "H₂ pipeline", H2S: "H₂ storage", H2E: "electrolyser", H2L: "H₂ import" };

function FloodKey() {
  const cf = useDataStore((d) => d.files.constraints as ConstraintsFile | undefined);
  return (
    <>
      <Swatches>
        {(cf?.flood.classes ?? []).map((c, i) => (
          <Swatch key={i} color={rgbCss(c[2])} label={cf ? floodLabel(cf, i + 1) : ""} />
        ))}
      </Swatches>
      <Note>Water depth where rivers flood once in 100 years on average, as JRC maps it: Europe at 100 m, the world at about 1 km. A hazard map: defences are not modelled everywhere.</Note>
    </>
  );
}

function OutagesKey() {
  const f = useDataStore((d) => d.files.usOutages as UsOutagesFile | undefined);
  return (
    <Scale
      gradient={gradientCss(OUTAGE_STOPS)}
      ticks={OUTAGE_TICKS}
      note={`Each county by the customer-hours its customers spent without power in ${f ? newestYear(f).year : "…"} (EAGLE-I, ORNL: customers out every 15 minutes × ¼ h, summed). Customers are utility meters, not people. Hover for hours per customer.`}
    />
  );
}

function WaterKey() {
  const f = useDataStore((d) => d.files.water as WaterFile | undefined);
  const ind = useApp((s) => s.waterIndicator);
  const labels = f?.indicators[ind]?.labels ?? {};
  return (
    <>
      <div className="mb-1 flex flex-wrap items-center gap-1">
        {WATER_INDICATORS.map((w) => (
          <button
            key={w.id}
            onClick={() => actions.setWaterIndicator(w.id)}
            className={`rounded-md border px-2 py-0.5 text-[10.5px] ${ind === w.id ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
          >
            {w.short}
          </button>
        ))}
      </div>
      <Swatches>
        {Object.entries(labels)
          .filter(([c]) => Number(c) >= -1)
          .map(([c, label]) => (
            <Swatch key={c} color={rgbCss(WATER_COLOR[c] ?? [90, 90, 90])} label={label} />
          ))}
      </Swatches>
      <Note>
        WRI Aqueduct 4.0, baseline, with WRI's own categories, per river basin (HydroBASINS level 6). Where WRI rates a basin's parts differently (by province or aquifer), the highest is shown
        {f && f.mixed[ind] ? ` (${f.mixed[ind].toLocaleString("en-US")} basins)` : ""}. For site screening, not engineering.
      </Note>
    </>
  );
}

function MastrKey() {
  const f = useDataStore((d) => d.files.mastrMuni as MastrMuniFile | undefined);
  const tech = useApp((s) => s.mastrTech);
  return (
    <>
      <div className="mb-1 flex flex-wrap items-center gap-1">
        {MASTR_TECHS.map((t) => (
          <button
            key={t}
            onClick={() => actions.setMastrTech(t)}
            className={`rounded-md border px-2 py-0.5 text-[10.5px] ${tech === t ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
          >
            {MASTR_LABEL[t].toLowerCase()}
          </button>
        ))}
      </div>
      <Scale
        gradient={gradientCss(MASTR_STOPS)}
        ticks={MASTR_TICKS}
        note={`Each municipality by the gross MW of its ${MASTR_LABEL[tech].toLowerCase()} units in operation (sum, computed). From zoom ${MASTR_UNIT_ZOOM}: every unit of 1 MW and more with a published position, coloured by type. Marktstammdatenregister ${f?.snapshot ?? "…"}.`}
      />
    </>
  );
}

function OffshoreKey() {
  const f = useDataStore((d) => d.files.offshoreWind as OffshoreWindFile | undefined);
  return (
    <>
      <Swatches>
        {(f?.statuses ?? Object.keys(OFFSHORE_STYLE)).map((s) => (
          <Swatch key={s} color={rgbCss(OFFSHORE_STYLE[s]?.[0] ?? [120, 128, 140])} label={OFFSHORE_LABEL[s] ?? s} />
        ))}
      </Swatches>
      <Note>Farm areas as EMODnet Human Activities publishes them (CETMAR, yearly, CC BY 4.0); rings: farms published as a point only. Planned areas are zones, not projects.</Note>
    </>
  );
}

function CtraceKey() {
  const ct = useDataStore((d) => d.files.ctrace as CtraceFile | undefined);
  return (
    <>
      <Swatches>
        {(ct?.groups ?? []).map((g, i) => (
          <Swatch key={g} color={rgbCss(CT_COLOR[i])} label={g} />
        ))}
      </Swatches>
      <Note>
        Dot area = CO₂e in {ct?.year ?? "…"} (100-year GWP), facilities of {ct ? (ct.threshold_t / 1e6).toFixed(1) : "0.1"} Mt and more. Modelled by Climate TRACE from satellites
        and other data, not reported; oil and gas production is one estimate per basin.
      </Note>
    </>
  );
}

function EtsKey() {
  const ets = useDataStore((d) => d.files.ets as EtsFile | undefined);
  const c = ets ? Object.values(ets.countries) : [];
  const n = c.reduce((a, x) => a + x.n, 0);
  const placed = c.reduce((a, x) => a + x.placed, 0);
  const t = c.reduce((a, x) => a + x.t[x.t.length - 1], 0);
  const tp = c.reduce((a, x) => a + x.t_placed, 0);
  return (
    <>
      <Swatches>
        {(ets?.groups ?? []).map((g, i) => g.includes("UK ETS") ? null : (
          <Swatch key={g} color={rgbCss(ETS_COLOR[i])} label={g.replace(" (power, heat, industry)", "")} />
        ))}
      </Swatches>
      <Note>
        Dot area = verified CO₂ in {ets?.newest ?? "…"}. Shown: {placed.toLocaleString("en-US")} of {n.toLocaleString("en-US")} installations ({mt(tp)} of {mt(t)}, sums
        computed), the ones the EEA industrial register gives an ETS id for; the rest are in the panel only. Combustion includes power, heat and industrial boilers. EU Union Registry, {ets?.snapshot ?? "…"}.{ets?.uk ? " Great Britain: the UK ETS registry's compliance report, listed in the panel (no positions or activities published)." : ""}
      </Note>
    </>
  );
}

function GasFlowKey() {
  const day = useDataStore((d) => (d.files.gasFlows as GasFlowsFile | undefined)?.gas_day);
  return (
    <>
      <Swatches>
        <Swatch color={rgbCss(GAS_FLOW)} kind="line" label="into Europe: pipelines from outside, LNG" />
        <Swatch color={rgbCss(GAS_TRANSIT)} kind="line" label="between European countries" />
      </Swatches>
      <Note>
        Net flow on gas day {day ?? "…"} (06:00–06:00 CET); wider = more GWh/d. Each source is labelled with its total into Europe (sum of its points, computed); flows between countries labelled from {GAS_TRANSIT_LABEL_GWH} GWh/d. Sources and each country's LNG terminals are placed for reading. ENTSOG, physical flow.
      </Note>
    </>
  );
}

/** The status buttons shared by the plants layers (GEM worldwide, EIA in the US). */
function StatusButtons() {
  const status = useApp((s) => s.plantStatus);
  return (
    <div className="mb-1.5 flex flex-wrap gap-1">
      {(["operating", "construction", "planned", "retired"] as PlantStatus[]).map((st) => (
        <button
          key={st}
          onClick={() => actions.setPlantStatus(st)}
          className={`rounded-full border px-2 py-0.5 text-[10px] ${st === status ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400 hover:text-slate-200"}`}
        >
          {STATUS_LABEL[st]}
        </button>
      ))}
    </div>
  );
}

function LayerLegend({ id }: { id: LayerId }) {
  const usPlantsOn = useApp((s) => s.layers.plantsUS);
  switch (id) {
    case "prices":
      return <PriceKey />;
    case "flows":
      return (
        <Note>
          Arrows point the way the power goes; labels from 1 GW. A thin bright core: the flow uses 90 % or more of the capacity offered on that border (where ENTSO-E publishes one; Central Europe and the Nordics set limits jointly and publish none per border). ENTSO-E, every 15 minutes.
        </Note>
      );
    case "gasFlows":
      return <GasFlowKey />;
    case "lngSendOut":
      return <LngKey />;
    case "ets":
      return <EtsKey />;
    case "ctrace":
      return <CtraceKey />;
    case "connect":
      return <ConnectKey />;
    case "usNodePrices":
      return <UsNodesKey />;
    case "usOutages":
      return <OutagesKey />;
    case "water":
      return <WaterKey />;
    case "protectedAreas":
      return (
        <>
          <Swatches>
            <Swatch color={rgbCss(PROTECTED_COLOR)} label="Natura 2000 site / PAD-US area" />
          </Swatches>
          <Note>Natura 2000 (EEA, end 2024) and PAD-US 4.1 Fee (USGS), generalised to about 50 m by the publishers' services. Check a site lists those near it.</Note>
        </>
      );
    case "flood":
      return <FloodKey />;
    case "hydrogen":
      return (
        <>
          <Swatches>
            {Object.entries(H2_STAGE_COLOR).map(([k, c]) => (
              <Swatch key={k} color={rgbCss(c)} label={k.toLowerCase()} />
            ))}
          </Swatches>
          <Note>Sized by production capacity (MW as published). European Hydrogen Observatory.</Note>
        </>
      );
    case "gasProjects":
      return (
        <>
          <Swatches>
            {(["TRA", "LNG", "UGS", "H2T", "H2S", "H2E", "H2L"] as const).map((k) => (
              <Swatch key={k} color={rgbCss(GAS_CAT_COLOR[k])} kind="ring" label={GAS_LABEL[k]} />
            ))}
          </Swatches>
          <Note>ENTSOG publishes no positions: one ring per country, sized by its number of projects, coloured by the most common kind. The panel lists them.</Note>
        </>
      );
    case "roadsRail":
      return (
        <>
          <Swatches>
            <Swatch color={rgbCss(ROAD_COLOR)} kind="line" label="motorway, trunk, primary" />
            <Swatch color={rgbCss(RAIL_COLOR)} kind="dash" label="railway (standard gauge)" />
          </Swatches>
          <Note>OpenStreetMap via Overture Maps; Europe and the US.</Note>
        </>
      );
    case "mastrDE":
      return <MastrKey />;
    case "regGB":
    case "regDK":
    case "regSE":
    case "regIE":
    case "regPT":
      return (
        <>
          <Swatches>
            {["solar", "wind", "bio", "hydro", "storage", "gas", "nuclear"].map((g) => (
              <Swatch key={g} color={rgbCss(FUEL_COLOR[g])} label={FUEL_LABEL[g]} kind="dot" />
            ))}
          </Swatches>
          <Note>One dot per unit or project, sized by √MW; paler from operating to being built, permitted and in planning. The national register as published (see the card for its source).</Note>
        </>
      );
    case "offshoreWind":
      return <OffshoreKey />;
    case "grw":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(255,214,72)" label="Solar arrays" />
            <Swatch color="rgb(72,222,184)" label="Wind turbines" />
          </Swatches>
          <Note>Found in Planet satellite images by Microsoft&apos;s models, up to 2024 Q2 (Global Renewables Watch v1.0, MIT). Small arrays appear when zoomed in.</Note>
        </>
      );
    case "tyndp":
      return <TyndpKey />;
    case "ghgrpUS":
      return <GhgrpKey />;
    case "gasPipesUS":
      return <Note>Natural gas pipelines, interstate brighter than intrastate; lines generalised to about 1 km. EIA, U.S. Energy Atlas.</Note>;
    case "evChargersEU":
      return (
        <Note>
          Dot area = public charging points (registers: DE, FR) or mapped stations (OpenStreetMap, paler) summed per 0.1° cell. Counts per country: European Alternative Fuels Observatory.
        </Note>
      );
    case "evChargersUS":
      return (
        <Note>
          Public DC fast charging stations in operation; dot area = DC fast ports. Stations with only level 2 ports are counted in the card, not drawn. NREL Alternative Fuels
          Data Center, monthly.
        </Note>
      );
    case "solarUS":
      return (
        <Note>
          Dot area = AC capacity; from zoom 7.5 the array&apos;s outline, digitised from aerial imagery (simplified to about 30 m). Ground-mounted PV of 1 MW (DC) and more. USPVDB (USGS, LBNL).
        </Note>
      );
    case "plantOutput":
      return (
        <>
          {fuelSwatches(["nuclear", "coal", "gas", "hydro", "wind", "bio", "oil"], FUEL_COLOR, FUEL_LABEL)}
          <Note>
            Ring: the plant's capacity (JRC, sum of its units); disc: its output at the clock (ENTSO-E, per unit of 100 MW and more). Grey dots: no value at this time. Germany, the Nordics, Austria and Switzerland publish about five days late; Italy, Denmark, Great Britain and Croatia publish none. US replay: EPA's fossil units over 25 MW, gross load per hour, ring = nameplate of their generators; EPA's newest complete quarter.
          </Note>
        </>
      );
    case "liveGrids":
      return (
        <Swatches>
          <Swatch color={rgbCss(US_COLOR)} label="US" kind="ring" />
          <Swatch color={rgbCss(BR_COLOR)} label="Brazil" kind="ring" />
          <Swatch color="rgb(120,222,255)" label="Australia" kind="ring" />
          <Swatch color={rgbCss(TW_COLOR)} label="Taiwan" kind="ring" />
          <Swatch color={rgbCss(ON_COLOR)} label="Ontario" kind="ring" />
        </Swatches>
      );
    case "towers":
      return <Note>Stacked by source; 1 GW = 14 km tall.</Note>;
    case "gridEU":
      return (
        <Swatches>
          {VOLTAGE_BANDS.map((b) => (
            <Swatch key={b.min} color={rgbCss(b.color)} kind="line" label={b.label} />
          ))}
        </Swatches>
      );
    case "hvdc":
      return <Swatches><Swatch color={rgbCss(HVDC)} kind="dash" label="HVDC link" /></Swatches>;
    case "substations":
      return <Swatches><Swatch color={rgbCss(SUBSTATION)} label="from zoom 5" /></Swatches>;
    case "gridWorld":
      return (
        <Swatches>
          {HV_STEPS.map(([kv, c], i) => (
            <Swatch key={kv} color={c} kind="line" label={i === 0 ? "220 kV" : `${kv} kV`} />
          ))}
        </Swatches>
      );
    case "cables":
      return (
        <>
          <Swatches>
            {Object.entries(CABLE_STYLE).map(([k, s]) => (
              <Swatch key={k} color={`rgba(${s.color.join(",")})`} kind="line" label={s.label} />
            ))}
            <Swatch color={rgbCss(SEA_CABLE_COLOR)} kind="line" label="European seas (EMODnet)" />
          </Swatches>
          <Note>OpenStreetMap worldwide; EMODnet adds the power cables the German, Dutch, French and Norwegian authorities publish (both may show one cable).</Note>
        </>
      );
    case "predicted":
      return <Note>Predicted from night-time lights and roads, not surveyed.</Note>;
    case "plantsEU":
      return (
        <>
          {fuelSwatches(["nuclear", "coal", "gas", "hydro", "wind", "solar", "bio"], FUEL_COLOR, { ...FUEL_LABEL, gas: "Gas & oil" })}
          <Note>Size grows with capacity. Pick a country to see every unit (beams from {BEAM_MIN_MW} MW).</Note>
        </>
      );
    case "plantsWorld":
      return (
        <>
          <StatusButtons />
          {fuelSwatches(Object.keys(PLANT_TYPE_COLOR), PLANT_TYPE_COLOR, PLANT_TYPE_LABEL)}
          {usPlantsOn && <Note>In the US, EIA's inventory is shown instead (US power plants is on).</Note>}
        </>
      );
    case "plantsUS":
      return (
        <>
          <StatusButtons />
          {fuelSwatches(US_TYPE_ORDER, US_TYPE_COLOR, US_TYPE_LABEL)}
          <Note>
            EIA-860M, every generator of 1 MW and more, summed per plant; size grows with net summer capacity. Zoomed out, plants of {PLANT_MIN_MW} MW and more; from zoom {PLANT_DETAIL_ZOOM} every one. In the US,
            EIA wins over GEM: GEM's points there are hidden while this is on.
          </Note>
        </>
      );
    case "gridUS":
      return (
        <>
          <Swatches>
            {US_BANDS.map((b) => (
              <Swatch key={b.min} color={`rgba(${b.color.join(",")},${Math.min(1, (b.alpha + 60) / 255)})`} kind="line" label={b.label} />
            ))}
            <Swatch color="rgb(178,146,255)" kind="dash" label="direct current" />
          </Swatches>
          <Note>Europe's voltage colours. OpenStreetMap via Overture: HIFLD's layer is no longer public.</Note>
        </>
      );
    case "turbinesUS":
      return <Note>Every turbine from zoom 5; zoomed out they are hidden. U.S. Wind Turbine Database.</Note>;
    case "usQueue":
      return (
        <>
          <Swatches>
            {["Solar", "Battery", "Wind", "Gas", "Offshore Wind", "Other"].map((t) => (
              <Swatch key={t} color={rgbCss(QUEUE_COLOR[t])} label={t} />
            ))}
          </Swatches>
          <div className="mt-1.5">
            <Scale
              gradient={queueRatioCss}
              ticks={QUEUE_RATIO_TICKS}
              note={`Towers: GW of active requests to connect, stacked by type (1 GW = ${(QUEUE_M_PER_GW / 1000).toFixed(1)} km). State shade: GW waiting ÷ GW of plants it runs today (EIA-860M, computed). LBNL Queued Up, end of 2025: requests, not plants being built.`}
            />
          </div>
        </>
      );
    case "gasPipes":
      return <>{pipeStatus("rgb(255,196,96)")}<Note>Thicker = more capacity. Global Energy Monitor; thin lines at sea: EMODnet's gas pipelines in European seas.</Note></>;
    case "oilPipes":
      return <>{pipeStatus("rgb(222,110,82)")}<Note>Thicker = more capacity. Global Energy Monitor; thin lines at sea: EMODnet's oil and condensate pipelines in European seas.</Note></>;
    case "lngTerminals":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(255,150,92)" label="export" />
            <Swatch color="rgb(255,215,150)" label="import" />
          </Swatches>
          {pointStatus("rgb(255,150,92)")}
        </>
      );
    case "coalTerminals":
      return pointStatus("rgb(196,182,166)");
    case "oilGasFields":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(214,96,64)" label="oil" />
            <Swatch color="rgb(255,150,92)" label="gas" />
            <Swatch color="rgb(235,120,80)" label="both" />
          </Swatches>
          {pointStatus("rgb(214,96,64)")}
        </>
      );
    case "coalMines":
      return pointStatus("rgb(160,146,132)");
    case "methane":
      return <Note>Each glow is one satellite observation; bigger = more methane per hour.</Note>;
    case "gas":
      return <Swatches><Swatch color={rgbCss(GAS)} kind="ring" label="storage site (SciGRID_gas)" /></Swatches>;
    case "financeCoal":
    case "financeGas":
      return (
        <>
          <Swatches>
            <Swatch color={id === "financeCoal" ? "rgb(232,204,128)" : "rgb(255,170,60)"} kind="line" label="money abroad, thicker = more" />
            <Swatch color={id === "financeCoal" ? "rgb(232,204,128)" : "rgb(255,170,60)"} label="project, by money received" />
          </Swatches>
          <Note>Arrows run from the financiers' home country, for flows of $300 m or more. Smaller flows and lending at home count in the panel's totals. Global Energy Monitor.</Note>
        </>
      );
    case "steel":
      return (
        <>
          <Swatches>
            <Swatch color="rgb(120,200,255)" label="electric arc furnace" />
            <Swatch color="rgb(200,205,215)" label="blast furnace and other" />
          </Swatches>
          {pointStatus("rgb(120,200,255)")}
        </>
      );
    case "cement":
      return pointStatus("rgb(206,192,166)");
    case "chemicals":
      return <Note>Plant locations; the inventory gives no capacity.</Note>;
    case "ironOre":
      return pointStatus("rgb(206,112,88)");
    case "dataCentres":
      return <Note>Zoomed out: count per area. A mapped subset, not every site.</Note>;
    case "wind":
      return <Note>Brighter = stronger. ECMWF forecast (live), Open-Meteo (24 h).</Note>;
    case "sun":
      return <Scale gradient="linear-gradient(90deg, rgba(255,214,72,0), rgba(255,214,72,0.8))" ticks={["0", `${SUN_MAX_WM2} W/m²`]} />;
    case "night":
      return <Note>Darkness at the time on the clock.</Note>;
    case "solarResource":
      return <AtlasKey id="pvout" />;
    case "windResource":
      return <AtlasKey id="wind" />;
  }
  return null;
}

function TyndpKey() {
  const f = useDataStore((d) => d.files.tyndp as TyndpFile | undefined);
  return (
    <>
      <Swatches>
        {(f?.statuses ?? Object.keys(TYNDP_STYLE)).filter((s) => s !== "Completed").map((s) => (
          <Swatch key={s} color={rgbCss(TYNDP_STYLE[s]?.[0] ?? [120, 128, 140])} label={s} kind="line" />
        ))}
      </Swatches>
      <Note>Projects of ENTSO-E&apos;s Ten-Year Network Development Plan 2024 as its project map draws them (lines, areas; rings: storage and point projects). Capacity and commissioning year on hover, as the promoters submitted them.</Note>
    </>
  );
}

function GhgrpKey() {
  const f = useDataStore((d) => d.files.ghgrp as GhgrpFile | undefined);
  return (
    <>
      <Swatches>
        {(f?.sectors ?? []).map((s) => (
          <Swatch key={s} color={rgbCss(ghgrpColor(s))} label={s} />
        ))}
      </Swatches>
      <Note>Dot area = t CO₂e reported for {f?.year ?? "…"} (AR4 GWP), direct emitters (the program's reporting threshold is 25,000 t a year). EPA Greenhouse Gas Reporting Program; positions from Envirofacts.</Note>
    </>
  );
}

/** A resource atlas: its classes as drawn, the unit and the source. */
function AtlasKey({ id }: { id: AtlasId }) {
  const atlas = useFile<AtlasFile>("atlas");
  const a = atlas?.[id];
  if (!a) return null;
  const cls = a.classes;
  const gradient = `linear-gradient(90deg, ${cls.map((c, i) => `${rgbCss(c[2])} ${(i / cls.length) * 100}% ${((i + 1) / cls.length) * 100}%`).join(", ")})`;
  const first = cls[0][1] as number;
  const last = cls[cls.length - 1][0] as number;
  const mid = cls[Math.floor(cls.length / 2)][0] as number;
  return (
    <Scale
      gradient={gradient}
      ticks={id === "pvout" ? [`${first}`, `${mid}`, `${last} kWh/kWp a day`] : [`${first}`, `${mid}`, `${last} m/s`]}
      note={
        id === "pvout" ? (
          <>
            Long-term average daily PV output per kWp (×365 for a year, as the atlas gives it: 2.0 = 730 kWh/kWp), in the atlas&apos;s 0.2 steps. Over Europe, colour the countries &quot;Plain&quot; to see it. {a.source}.
          </>
        ) : (
          <>
            Mean wind speed at 100 m above ground, in 1 m/s classes over the atlas&apos;s 0–10 m/s scale. Over Europe, colour the countries &quot;Plain&quot; to see it.{" "}
            {a.source}.
          </>
        )
      }
    />
  );
}

function Toggle({ on }: { on: boolean }) {
  return (
    <span className={`relative h-[16px] w-[28px] shrink-0 rounded-full transition-colors ${on ? "bg-sky-400/80" : "bg-white/15"}`}>
      <span className={`absolute top-[2px] h-[12px] w-[12px] rounded-full bg-white shadow transition-all ${on ? "left-[14px]" : "left-[2px]"}`} />
    </span>
  );
}

const DOCS = "https://github.com/Daniyal-arch/Energy_Grid/blob/main/docs/DATA_SOURCES.md";
const STATUS_ORDER: [string, string][] = [
  ["have", "On the map"],
  ["built", "On the map"],
  ["partly", "Partly"],
  ["not_published", "Not published by the operator"],
  ["blocked", "Waits for a key"],
];

/** The coverage registry's countries for a dataset's family (coverage.json): EU-27, the UK, the US. */
function FamilyCoverage({ family }: { family: string }) {
  const f = useFile<CoverageFile>("coverage");
  if (!f) return null;
  const fam = f.families.find((x) => x.id === family);
  if (!fam) return null;
  const by = new Map<string, string[]>();
  for (const [cc, cells] of Object.entries(f.countries)) {
    const cell = cells[family];
    if (!cell) continue;
    const k = cell.g === "◐" ? "partly" : cell.status;
    by.set(k, [...(by.get(k) ?? []), cc]);
  }
  const rows = STATUS_ORDER.filter(([k]) => by.get(k)?.length).reduce<[string, string[]][]>((acc, [k, label]) => {
    const prev = acc.find(([l]) => l === label);
    if (prev) prev[1].push(...by.get(k)!);
    else acc.push([label, [...by.get(k)!]]);
    return acc;
  }, []);
  return (
    <div className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-1.5">
      <div className={`text-[9.5px] uppercase tracking-[0.14em] ${muted}`}>
        Coverage registry · {fam.name} · checked {f.checked}
      </div>
      {rows.map(([label, codes]) => (
        <div key={label} className="mt-1 text-[10.5px] leading-snug">
          <span className="text-slate-300">{label}:</span> <span className={muted}>{codes.join(", ")}</span>
        </div>
      ))}
    </div>
  );
}

/** Where a dataset has data and where it comes from; the map tints the countries meanwhile. */
export function DatasetDetails({ d, tinted = true }: { d: Dataset; tinted?: boolean }) {
  return (
    <div className="mx-2 mb-2 rounded-lg border border-white/[0.07] bg-[#0d1119] px-2.5 py-2">
      <div className="text-[11px] leading-snug text-slate-300">{d.description}</div>
      <div className="mt-2 space-y-1.5">
        {d.parts.map((p, i) => (
          <div key={i} className="text-[10.5px] leading-snug">
            <div className="text-slate-200">{placesText(p.where)}</div>
            <div className={muted}>
              {p.what}. Source: {p.source}.
            </div>
          </div>
        ))}
      </div>
      {d.updates && <div className={`mt-1.5 text-[10.5px] ${muted}`}>Updated: {d.updates}.</div>}
      {d.family && <FamilyCoverage family={d.family} />}
      <div className={`mt-2 flex items-center justify-between text-[10px] ${muted}`}>
        <span>{tinted ? "Tinted on the map: where it has data" : ""}</span>
        <a href={`${DOCS}`} target="_blank" rel="noreferrer" className="text-sky-300/80 hover:text-sky-200" title={`docs/DATA_SOURCES.md, section "${d.parts[0].doc}"`}>
          How it is built ↗
        </a>
      </div>
    </div>
  );
}

/** The scale of a dataset's per-country figure, as the map shades it (map/summaryLayers.ts). */
function SummaryKey({ d, files }: { d: Dataset; files: Record<string, unknown> }) {
  const values = summaryValues(d.id, files);
  const s = SUMMARIES[d.id];
  const top = values?.size ? [...values.entries()].sort((a, b) => b[1] - a[1]) : [];
  const max = top[0]?.[1] ?? 0;
  const rgb = d.color.replace("rgb(", "rgba(").replace(")", "");
  return (
    <div className="px-2 pb-2 pl-[30px]">
      <div className={`text-[10px] leading-snug ${muted}`}>Zoomed out, the countries carry its figure: {s.text(files)}.</div>
      {max > 0 && (
        <>
          <div className="mt-1.5 h-2 rounded-sm" style={{ background: `linear-gradient(90deg, ${rgb},${(SUMMARY_ALPHA[0] / 255).toFixed(2)}), ${rgb},${(SUMMARY_ALPHA[1] / 255).toFixed(2)}))` }} />
          <div className={`mt-0.5 flex justify-between text-[9px] ${muted}`}>
            <span>{s.label(0)}</span>
            <span>{s.label(max / 4)}</span>
            <span>{s.label(max)}</span>
          </div>
          <div className={`mt-1 text-[9.5px] leading-snug ${muted}`}>
            Strength: square root of the share of the largest. Largest: {top.slice(0, 3).map(([c, v]) => `${c} ${s.label(v)}`).join(" · ")}
          </div>
        </>
      )}
    </div>
  );
}

/** Where a dataset just switched on goes: onto this map (on top of what is there; two as
 *  hexagons make a bivariate map) or a map of its own beside the others (six maps at most). */
function AddChoice({ d, onDone }: { d: Dataset; onDone: () => void }) {
  const compare = useApp((s) => s.compare);
  const maps = useApp((s) => s.maps);
  const style = (): Style => styleOf(useApp.getState().mapStyles, d.id) ?? stylesOf(d.id)[0] ?? "lines";
  const asNewMap = () => {
    const s = useApp.getState();
    if (!compare) {
      // this map becomes the first of the Maps view, the dataset the next
      const others = datasetsOn(s.layers, s.colour).filter((x) => x.id !== d.id && !x.colour);
      const first: MapPanel | null = others.length
        ? { title: s.title ?? findDashboard(s.dashboard)?.label ?? "This map", items: others.map((x) => ({ dataset: x.id, style: styleOf(s.mapStyles, x.id) ?? stylesOf(x.id)[0] ?? "lines" })) }
        : null;
      actions.setMaps([...(s.maps.length ? s.maps : first ? [first] : []), panelOf(d.id, style())].slice(-6));
      actions.setCompare(true);
    } else actions.addMap(panelOf(d.id, style()));
    onDone();
  };
  const onMap = (k: number) => {
    actions.setMaps(maps.map((m, i) => (i === k && !m.items.some((x) => x.dataset === d.id) ? { ...m, items: [...m.items, { dataset: d.id, style: style() }] } : m)));
    onDone();
  };
  return (
    <div className="mx-2 mb-2 rounded-lg border border-sky-400/25 bg-sky-400/[0.06] px-2.5 py-2 text-[10.5px] text-slate-300">
      <div>Show {d.name.toLowerCase()}:</div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {!compare ? (
          <button onClick={onDone} className="rounded-md border border-white/15 px-2 py-0.5 text-slate-100 hover:bg-white/[0.08]" title="On top of the datasets on the map now">
            On this map
          </button>
        ) : (
          maps.map((m, k) => (
            <button key={k} onClick={() => onMap(k)} className="rounded-md border border-white/15 px-2 py-0.5 text-slate-100 hover:bg-white/[0.08]" title={`On top of “${m.title}”`}>
              On map {k + 1}
            </button>
          ))
        )}
        <button
          onClick={asNewMap}
          className="rounded-md border border-white/15 px-2 py-0.5 text-slate-100 hover:bg-white/[0.08]"
          title={maps.length >= 6 ? "A map of its own: the oldest of the six maps goes" : "A map of its own beside the others, one camera (six at most)"}
        >
          As a new map{compare ? ` (${Math.min(6, maps.length + 1)} of 6)` : ""}
        </button>
      </div>
    </div>
  );
}

function DatasetRow({ d }: { d: Dataset }) {
  const mode = useApp((s) => s.mode);
  const layers = useApp((s) => s.layers);
  const coverageOf = useApp((s) => s.coverageOf);
  const colour = useApp((s) => s.colour);
  const [ask, setAsk] = useState(false);
  const on = datasetOn(d, layers, colour);
  const open = coverageOf === d.id;
  const shownParts = partsIn(d, mode).filter((p) => !!p.layer && layers[p.layer]);
  const where = coverageLabel(d);
  const selection = useApp((s) => s.selection);
  const files = useDataStore((s) => s.files);
  const area = useApp((s) => s.area);
  const drawn = useApp((s) => s.drawn);
  const mapStyles = useApp((s) => s.mapStyles);
  const compare = useApp((s) => s.compare);
  const own = styleOf(mapStyles, d.id);
  const ownDrawing = !own || own === "points" || own === "raster";
  const carried = on && ownDrawing && summaryOf({ colour, layers, selection, area, drawn })?.id === d.id;
  return (
    <div className={`rounded-lg transition-colors ${on ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"}`}>
      <div className="flex w-full items-center gap-2.5 px-2 py-1.5">
        <button onClick={() => actions.showCoverage(open ? null : d.id)} className="flex min-w-0 flex-1 items-center gap-2.5 text-left" aria-expanded={open} title="Where it has data and its sources">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.color, opacity: on ? 1 : 0.45 }} />
          <span className="min-w-0 flex-1">
            <span className={`flex items-baseline gap-1.5 text-[12.5px] ${on ? "text-slate-50" : "text-slate-300"}`}>
              <span className="truncate">{d.name}</span>
              {where && <span className="shrink-0 text-[9.5px] uppercase tracking-wider text-slate-500">{where}</span>}
            </span>
            <span className={`block truncate text-[10.5px] ${muted}`}>{d.description}</span>
          </span>
          <span className={`shrink-0 text-[10px] text-slate-500 transition-transform ${open ? "rotate-90" : ""}`}>›</span>
        </button>
        <button
          onClick={() => {
            // a dataset joining others: on this map, or a map of its own beside them
            const before = datasetsOn(layers, colour).filter((x) => !x.colour).length;
            toggleDataset(d);
            setAsk(!on && !d.colour && (before > 0 || compare));
          }}
          aria-pressed={on}
          title={on ? `Hide ${d.name.toLowerCase()}` : `Show ${d.name.toLowerCase()}`}
        >
          <Toggle on={on} />
        </button>
      </div>
      {ask && on && <AddChoice d={d} onDone={() => setAsk(false)} />}
      {on && stylesOf(d.id).length > 0 && (
        <div className="px-2 pb-1.5 pl-[30px]">
          <StyleChips dataset={d.id} value={styleOf(mapStyles, d.id)} onChange={(st) => actions.setMapStyle(d.id, st)} />
          <StyleKey scope="main" dataset={d.id} style={styleOf(mapStyles, d.id)} />
        </div>
      )}
      {open && <DatasetDetails d={d} />}
      {carried && <SummaryKey d={d} files={files} />}
      {on && d.colour && (
        <div className="px-2 pb-2 pl-[30px]">
          <ColourLegend colour={d.colour} />
        </div>
      )}
      {on && shownParts.length > 0 && (
        <div className="space-y-2 px-2 pb-2 pl-[30px]">
          {shownParts.map((p) => (
            <div key={p.layer}>
              {shownParts.length > 1 && <div className="mb-0.5 text-[9.5px] uppercase tracking-[0.12em] text-slate-500">{placesText(p.where)}</div>}
              <LayerLegend id={p.layer!} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const matches = (d: Dataset, t: string) => !t || norm(`${d.name} ${d.description} ${d.category} ${d.parts.map((p) => `${p.source} ${p.what} ${p.where.join(" ")}`).join(" ")}`).includes(t);

function Category({ group, open, onToggle, q, show }: { group: LayerGroup; open: boolean; onToggle: () => void; q: string; show: (d: Dataset) => boolean }) {
  const mode = useApp((s) => s.mode);
  const layers = useApp((s) => s.layers);
  const colour = useApp((s) => s.colour);
  const inGroup = DATASETS.filter((d) => d.category === group && matches(d, q) && show(d));
  const shown = inGroup.filter((d) => partsIn(d, mode).length > 0);
  const elsewhere = inGroup.filter((d) => !partsIn(d, mode).length);
  const active = shown.filter((d) => datasetOn(d, layers, colour)).length;
  if (!shown.length && !elsewhere.length) return null;
  const isOpen = open || !!q;
  return (
    <section className="border-t border-white/[0.06] first:border-t-0">
      <button onClick={onToggle} className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-white/[0.03]" aria-expanded={isOpen}>
        <span className={`text-[10px] text-slate-500 transition-transform ${isOpen ? "rotate-90" : ""}`}>▶</span>
        <span className="flex-1 text-[12px] font-medium text-slate-200">{group}</span>
        <span className={`text-[10.5px] ${active ? "text-sky-300" : "text-slate-500"}`}>{active ? `${active} on` : `${shown.length}`}</span>
      </button>
      {isOpen && (
        <div className="px-1.5 pb-2">
          {shown.map((d) => (
            <DatasetRow key={d.id} d={d} />
          ))}
          {elsewhere.length > 0 && (
            <div className={`px-2 pt-1 text-[10px] ${muted}`}>
              In {[...new Set(elsewhere.flatMap((d) => datasetModes(d)))].map((m) => MODE_LABEL[m]).join(" and ")} only: {elsewhere.map((d) => d.name.toLowerCase()).join(", ")}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default function LayersPanel() {
  const colour = useApp((s) => s.colour);
  const mode = useApp((s) => s.mode);
  const layers = useApp((s) => s.layers);
  const [open, setOpen] = useState<Partial<Record<LayerGroup, boolean>>>({});
  const [q, setQ] = useState("");
  const t = norm(q.trim());
  const area = useApp((s) => s.area);
  const [onlyHere, setOnlyHere] = useState(true);
  const names = useCountryNames();
  const active = DATASETS.filter((d) => partsIn(d, mode).length > 0 && datasetOn(d, layers, colour));
  const groupHasActive = (g: LayerGroup) => active.some((d) => d.category === g);
  const found = t ? DATASETS.filter((d) => matches(d, t)).length : 0;
  // the categories list what is not on the map yet; with an area, what has data there
  const here = (d: Dataset) => !area || !onlyHere || covers(d, area);
  const show = (d: Dataset) => !datasetOn(d, layers, colour) && here(d);
  const elsewhere = area ? DATASETS.filter((d) => !covers(d, area)).length : 0;
  const areaName = area ? (area.length <= 2 ? area.map(names).join(" and ") : `${area.length} countries`) : "";
  return (
    <div>
      <section className="px-3 pb-2 pt-2.5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Find among ${DATASETS.length} datasets…`}
          className="w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1.5 text-[12px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
          aria-label="Find a dataset"
        />
        {t && <div className={`mt-1 text-[10px] ${muted}`}>{found ? `${found} found: by name, source or country code` : "Nothing found"}</div>}
      </section>

      <div className="flex items-center justify-between border-t border-white/[0.06] px-3 pb-1.5 pt-2.5">
        <span className="text-[10px] uppercase tracking-[0.18em] text-[#8d94a1]">On the map</span>
        {active.length > 0 && (
          <button
            onClick={() => useApp.setState((s) => ({ layers: Object.fromEntries(Object.keys(s.layers).map((k) => [k, false])) as typeof s.layers, colour: "none", edited: true, coverageOf: null }))}
            className="text-[10.5px] text-slate-400 hover:text-slate-100"
          >
            Clear all
          </button>
        )}
      </div>
      {/* what the map shows now, each with its key */}
      <div className="px-1.5 pb-2">
        {active.length === 0 && <div className={`px-1.5 text-[11px] ${muted}`}>Nothing yet: switch a dataset on below, or pick a dashboard.</div>}
        {active.map((d) => (
          <DatasetRow key={d.id} d={d} />
        ))}
      </div>



      <div className="flex items-center justify-between border-t border-white/[0.06] px-3 pb-1 pt-2.5">
        <span className="text-[10px] uppercase tracking-[0.18em] text-[#8d94a1]">Browse by category</span>
        <button onClick={() => useApp.setState({ catalogue: true })} className="text-[10.5px] text-sky-300/90 hover:text-sky-200" title="Every dataset with its sources and coverage">
          Data catalogue ↗
        </button>
      </div>
      <div className={`px-3 pb-1.5 text-[10px] ${muted}`}>
        {area ? (
          <>
            {onlyHere ? `With data in ${areaName}` : "Every dataset"}
            {elsewhere > 0 && (
              <button onClick={() => setOnlyHere(!onlyHere)} className="ml-1 text-sky-300/90 hover:text-sky-200">
                {onlyHere ? `· show all (${elsewhere} more)` : `· only those with data in ${areaName}`}
              </button>
            )}
            . Click a name for where it has data and its sources.
          </>
        ) : (
          "Click a name for where it has data (tinted on the map) and its sources."
        )}
      </div>
      {CATEGORIES.map((g) => (
        <Category key={g} group={g} q={t} show={show} open={open[g] ?? false} onToggle={() => setOpen((o) => ({ ...o, [g]: !(o[g] ?? false) }))} />
      ))}
      <div className="h-2" />
    </div>
  );
}
