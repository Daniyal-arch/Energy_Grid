// Hover cards for everything on the map. Values are the files' own; each card names its source.

import type { PickingInfo } from "@deck.gl/core";

import type { DataCentresFile, BrazilFile, OntarioFile, TaiwanFile, UsFile, AemoFile } from "../lib/world";
import { FUEL_LABEL, gw, power } from "../lib/energy";
import { usd, years, type FinanceFile, type FinanceFlow, type FinanceProject } from "../lib/finance";
import { CLASS_LABEL, GEM_PIPES, GEM_POINTS, capacityText, sizeText, type GemPipesFile, type GemPoint, type GemPointsFile } from "../lib/gem";
import { formatGw, irenaK, irenaMetricById, irenaValue, type IrenaFile, type IrenaMetricId } from "../lib/irena";
import { priceMetricById, type PricesFile } from "../lib/prices";
import { ISO3, formatMetric, metricById, type TransitionFile } from "../lib/transition";
import { NEM_NAME, latest, type WorldStatsFile } from "../lib/world";
import { PLANT_TYPE_LABEL, STATUS_LABEL, type WorldPlantsFile } from "../lib/worldPlants";
import { endName, gwhd, latestOf, type GasFlowsFile } from "../lib/gasFlows";
import { ETS_REGISTRY_NAME, mt, type EtsFile, type EtsRow } from "../lib/ets";
import { FLAG_TEXT, euroCents, newestMonth, newestOf, usCents, type RetailFile } from "../lib/retail";
import { isBasin, subsectorLabel, type CtRow, type CtraceFile } from "../lib/ctrace";
import { gwText as connectGw, type ConnectFile, type GbSite, type NlArea } from "../lib/connect";
import { usdMwh, type UsNodesFile } from "../lib/usNodes";
import { STATUS_TEXT, gwhdText, lngDay, type LngTerminal, type LngTerminalsFile } from "../lib/lngTerminals";
import type { GasArc } from "./build";
import { hoursText, newestYear, type UsCountiesFile, type UsOutagesFile, type WaterFile } from "../lib/risk";
import { MASTR_LABEL, mwText, type MastrMuniFile, type MastrUnitsFile } from "../lib/mastr";
import { OFFSHORE_LABEL, offshoreStatus, type OffshoreWindFile } from "../lib/offshoreWind";
import { solarCat, type UsSolarFile } from "../lib/usSolar";
import type { EvChargersFile } from "../lib/evChargers";
import type { EvEuFile } from "../lib/evEu";
import type { UsGasPipesFile } from "../lib/usGas";
import type { EvEuCell } from "./evEuLayers";
import type { GhgrpFile } from "../lib/ghgrp";
import type { TyndpFeature, TyndpFile } from "../lib/tyndp";
import type { NzFile, ZaFile } from "../lib/regionalLive";
import { type GasProjectsFile, type H2Project, type HydrogenFile } from "../lib/coming";
import { SEA_CABLE_SOURCE, type SeaCable, type SeaPipe } from "../lib/seaCables";
import { frValue, itTotals, type FrFile, type FrSite, type IeFile, type IeStation, type ItFile } from "../lib/connectMore";
import { siteHtml } from "./siteLayers";
import { CABLE_STYLE } from "../app/colors";
import { ensure, fileOf } from "../app/data";
import { STATUS_LABEL as REG_STATUS, registerKey, type RegisterFile, type RegisterPoint } from "../lib/registers";
import { connectEuKey, valueText, type ConnectEuFile, type EuArea, type EuPoint } from "../lib/connectEu";
import { clockOf, dayFileKey, dayIndexKey, dayPower, marketTime, unitOutKey, utc } from "../app/day";
import { BEAM_MIN_MW, HEX_KM } from "../app/geo";
import { useApp, motion } from "../app/store";
import type { Arc, Cable, CountriesFile, DayFile, GasSite, Hex, Plant, PlantsFile, Power, Shape, StatsFile, Substation, TowerPiece, Unit, UnitOutputFile } from "../app/types";
import { priceState } from "./priceTerrain";
import type { PlantOutputRow } from "./build";
import { largestType, queueMw } from "./usLayers";
import { US_TYPE_LABEL, gwText, operatingMw, ratioText, type UsPlantsFile, type UsQueueFile, type UsStatesFile, type UsTurbinesFile } from "../lib/us";

export const TIP_STYLE = {
  background: "rgba(8,10,14,0.92)",
  color: "#e2e8f0",
  fontSize: "11px",
  lineHeight: "1.5",
  padding: "8px 10px",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "6px",
  maxWidth: "280px",
};
const SRC = (s: string) => `<div style="color:#8d94a1">${s}</div>`;
const PLANT_LABEL: Record<string, string> = { ...FUEL_LABEL, gas: "Gas & oil" };

function powerHtml(title: string, p: Power | undefined): string {
  if (!p) return `<b>${title}</b>${SRC("no load or generation data from ENTSO-E")}`;
  const rows = Object.entries(p.generation_mw)
    .filter(([, mw]) => mw > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([f, mw]) => `<div style="display:flex;justify-content:space-between;gap:16px"><span>${FUEL_LABEL[f] ?? f}</span><span>${gw(mw)}</span></div>`)
    .join("");
  const share = p.renewable_share_of_generation;
  return `<b style="letter-spacing:.08em">${title}</b>
    <div style="color:#8d94a1;margin:2px 0 6px">interval ${utc(p.ts)} · ENTSO-E</div>
    ${share != null ? `<div>Renewable share of generation <b>${share.toFixed(1)} %</b></div>` : ""}
    <div>Load <b>${gw(p.load_mw)}</b></div>
    <div style="margin-top:6px">${rows}</div>`;
}

/** Name and the coloured value of a country (Europe's detailed shapes or the world's land). */
export function countryHtml(name: string, iso2: string | null, iso3: string | null): string | null {
  const s = useApp.getState();
  const code = iso3 ?? (iso2 ? ISO3[iso2] : undefined);
  if (s.colour.startsWith("tr_")) {
    const t = fileOf<TransitionFile>("transition");
    const m = metricById(s.colour.slice(3) as Parameters<typeof metricById>[0]);
    const v = code ? t?.entities[code]?.[m.id][s.yearK] : null;
    return `<b>${name}</b><div>${m.label} ${t?.years[s.yearK] ?? ""}: <b>${formatMetric(m, v)}</b></div>${SRC("Ember yearly electricity data")}`;
  }
  if (s.colour.startsWith("ir_")) {
    const irena = fileOf<IrenaFile>("irena");
    if (!irena) return null;
    const m = irenaMetricById(s.colour.slice(3) as IrenaMetricId);
    const k = irenaK(irena, s.mode, fileOf<TransitionFile>("transition")?.years, s.yearK);
    return `<b>${name}</b><div>${m.label} ${irena.years[k]}: <b>${formatGw(irenaValue(irena, code ?? undefined, m, k))}</b></div>${SRC(m.note)}`;
  }
  if (s.colour === "rt_household") {
    const rf = fileOf<RetailFile>("retail");
    const row = iso2 ? rf?.eu.series.elec_household[iso2] : undefined;
    const n = rf ? newestOf(rf, row) : null;
    if (!rf || !n || !row) return `<b>${name}</b>${SRC("no household price at Eurostat")}`;
    const flag = n.flag ? ` (${FLAG_TEXT[n.flag] ?? n.flag})` : "";
    return `<b>${name}</b><div>Households pay <b>${euroCents(n.v)}/kWh</b>${flag}</div>
      <div>without VAT ${euroCents(row.X_VAT[n.k])} · without taxes and levies ${euroCents(row.X_TAX[n.k])}</div>${SRC(`Eurostat nrg_pc_204, ${n.period}, band DC (2,500–4,999 kWh a year)`)}`;
  }
  if (s.colour === "access") {
    const ws = fileOf<WorldStatsFile>("worldStats");
    const a = code && ws ? latest(ws.access[code], ws.years) : null;
    return `<b>${name}</b><div>Access to electricity <b>${a ? `${a.value.toFixed(1)} % (${a.year})` : "no figure"}</b></div>${SRC("World Bank WDI")}`;
  }
  if (s.colour.startsWith("pr_") && iso2) {
    const pf = fileOf<PricesFile>("prices");
    if (!pf) return null;
    const m = priceMetricById(s.colour.slice(3) as Parameters<typeof priceMetricById>[0]);
    const zones = Object.entries(pf.zones).filter(([, z]) => z.country === iso2);
    if (!zones.length) return `<b>${name}</b>${SRC("no day-ahead price at ENTSO-E")}`;
    return `<b>${name}</b>${zones
      .map(([zone, z]) => `<div>${zones.length > 1 ? `${zone}: ` : ""}${m.label.toLowerCase()} <b>${m.format(m.value(z))}</b></div>`)
      .join("")}${SRC(`${pf.period[0].slice(0, 7)} to ${pf.period[1].slice(0, 7)} · click for the zone`)}`;
  }
  if (!iso2) return `<b>${name}</b>${SRC("click for its figures")}`;
  if (s.mode === "day") {
    const day = currentDay();
    if (!day) return null;
    const k = Math.min(day.slots - 1, Math.floor(motion.daySlot));
    return powerHtml(name, dayPower(day.countries[iso2], k, new Date(Date.parse(day.start) + k * day.step_s * 1000).toISOString()));
  }
  return powerHtml(name, fileOf<StatsFile>("stats")?.countries[iso2]);
}

export function currentDay(): DayFile | undefined {
  const s = useApp.getState();
  const region = useApp.getState().dayRegion;
  const index = fileOf<{ all: string[] }>(dayIndexKey(region));
  const date = s.day ?? index?.all[index.all.length - 1];
  return date ? fileOf<DayFile>(dayFileKey(region, date)) : undefined;
}

let namesAsked = false;

export function tooltip({ object, layer }: PickingInfo): { html: string; style: typeof TIP_STYLE } | null {
  if (!object || !layer) return null;
  const html = tooltipHtml(layer.id, object);
  return html ? { html, style: TIP_STYLE } : null;
}

function gemHtml(id: string, object: unknown): string | null {
  const key = id.replace(/^gem-/, "").replace(/-glow$/, "");
  const pipe = GEM_PIPES[key];
  if (pipe) {
    const f = fileOf<GemPipesFile>(pipe.file);
    const row = f?.rows[(object as { row: number }).row];
    if (!f || !row) return null;
    const [, st, cap, km, yr, name, countries] = row;
    const bits = [capacityText(f, cap), km != null ? `${km.toLocaleString("en-US")} km` : "", yr ? `from ${yr}` : ""].filter(Boolean).join(" · ");
    return `<b>${name || pipe.noun}</b><div>${pipe.noun} · ${f.statuses[st]}</div>${bits ? `<div>${bits}</div>` : ""}${countries ? `<div>${countries}</div>` : ""}${SRC(f.source)}`;
  }
  const point = GEM_POINTS[key];
  if (point) {
    const f = fileOf<GemPointsFile>(point.file);
    if (!f) return null;
    const p = object as GemPoint;
    const kind = f.kinds[p[2]] ?? "";
    const size = sizeText(f, p[4]);
    const detail = [kind && kind !== "other" ? kind : "", f.statuses[p[7]] ?? CLASS_LABEL[p[3]], size].filter(Boolean).join(" · ");
    const where = [p[8], p[5] ? (key === "methane" ? `seen ${p[5]}` : `from ${p[5]}`) : ""].filter(Boolean).join(" · ");
    return `<b>${p[6] || point.noun}</b><div>${point.noun}${detail ? ` · ${detail}` : ""}</div>${where ? `<div>${where}</div>` : ""}${SRC(f.source)}`;
  }
  return null;
}

function financeHtml(id: string, object: unknown): string | null {
  const f = fileOf<FinanceFile>("gemFinance");
  if (!f) return null;
  const name = (iso: string) => f.countries[iso]?.name ?? iso;
  if (id === "fin-arcs") {
    const fl = (object as { flow: FinanceFlow }).flow;
    return `<b>${name(fl[0])} → ${name(fl[1])}</b><div>${usd(fl[3])} for ${f.fuels[fl[2]]} in ${fl[4]} deal${fl[4] > 1 ? "s" : ""}${years(fl[5], fl[6]) ? `, ${years(fl[5], fl[6])}` : ""}</div><div>financiers based in ${name(fl[0])}</div>${SRC(f.source)}`;
  }
  if (id === "fin-projects") {
    const p = object as FinanceProject;
    const top = p[8].map(([n, v]) => `<div>${n} <span style="color:#8d94a1">${usd(v)}</span></div>`).join("");
    return `<b>${p[5]}</b><div>${f.fuels[p[2]]} · ${p[7] || "status unknown"} · ${name(p[6])}</div><div>${usd(p[3])} from ${p[4]} deal${p[4] > 1 ? "s" : ""}</div><div style="margin-top:4px;color:#8d94a1">largest financiers</div>${top}${SRC(f.source)}`;
  }
  if (id === "fin-lender-halo") {
    const d = object as { iso: string };
    const t = f.totals[d.iso];
    if (!t) return null;
    return `<b>${name(d.iso)}</b><div>Abroad: coal ${usd(t.out[0])} · gas ${usd(t.out[1])}</div><div>At home: coal ${usd(t.domestic[0])} · gas ${usd(t.domestic[1])}</div><div>From abroad: coal ${usd(t.in[0])} · gas ${usd(t.in[1])}</div>${SRC("GEM finance trackers · financiers' shares summed")}`;
  }
  return null;
}

/** The US grid pack: EIA plants, USWTDB turbines, LBNL's queue per state. */
function usHtml(id: string, object: unknown): string | null {
  if (id === "us-plants") {
    const f = fileOf<UsPlantsFile>("usPlants");
    const p = f?.points[object as number];
    if (!f || !p) return null;
    const [name, state, eia] = f.plants[p[6]];
    const status = f.statuses[p[3]];
    const when = p[5] ? ` · ${status === "retired" ? "retired" : status === "operating" ? "since" : "planned for"} ${p[5]}` : "";
    // newest full year's generation and capacity factor (EIA-923 via PUDL), CO2 (eGRID)
    const pf = fileOf<{ year: number; egrid_year: number; plants: Record<string, [number | null, number | null, number, number | null, number | null]> }>("plantsPerf");
    const q = pf?.plants[String(eia)];
    const perf = q
      ? `<div>${q[0] != null ? `${Math.round(q[0] / 1000).toLocaleString("en-US")} GWh in ${pf?.year}` : ""}${q[1] != null ? ` · capacity factor ${Math.round(q[1] * 100)} %${q[2] ? "" : " (computed: generation ÷ nameplate × hours)"}` : ""}</div>${q[4] != null ? `<div>CO₂ ${Math.round(q[4]).toLocaleString("en-US")} short tons, ${q[3] != null ? `${Math.round(q[3]).toLocaleString("en-US")} lb/MWh` : ""} (eGRID${pf?.egrid_year})</div>` : ""}`
      : "";
    return `<b>${name}</b><div>${US_TYPE_LABEL[f.types[p[2]]] ?? f.types[p[2]]} · ${p[4].toLocaleString("en-US")} MW net summer · ${STATUS_LABEL[status] ?? status}${when}</div><div>${p[7]} generator${p[7] > 1 ? "s" : ""} · ${state} · EIA plant ${eia}</div>${perf}${SRC(`EIA-860M, ${f.release}${q ? `; EIA-923 via PUDL, EPA eGRID` : ""}`)}`;
  }
  if (id === "us-turbines") {
    const f = fileOf<UsTurbinesFile>("usTurbines");
    const k = object as number;
    if (!f) return null;
    const [project, state, year, n, mw] = f.projects[f.project[k]];
    const kw = f.kw[k];
    const bits = [f.models[f.model[k]], kw != null ? `${kw.toLocaleString("en-US")} kW` : "", f.hh[k] != null ? `hub ${f.hh[k]} m` : "", f.rd[k] != null ? `rotor ${f.rd[k]} m` : ""].filter(Boolean).join(" · ");
    const proj = [n ? `${n} turbines` : "", mw ? `${mw.toLocaleString("en-US")} MW` : "", year ? `online ${year}` : "", state].filter(Boolean).join(" · ");
    return `<b>${project || "Wind turbine"}</b>${f.offshore[k] ? "<div>offshore</div>" : ""}<div>${bits || "turbine"}</div><div style="color:#8d94a1">project: ${proj}</div>${SRC(`USWTDB ${f.release}`)}`;
  }
  if (id === "us-queue" || id === "us-queue-towers") {
    const q = fileOf<UsQueueFile>("usQueue");
    const code = (object as { code: string }).code;
    const st = q?.states[code];
    if (!q || !st) return null;
    const name = fileOf<UsStatesFile>("usStates")?.states.find((s) => s.code === code)?.name ?? code;
    const rows = q.types
      .map((t, i) => [t, st.active[i]] as [string, number])
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t, v]) => `<div style="display:flex;justify-content:space-between;gap:16px"><span>${t}</span><span>${gwText(v)}</span></div>`)
      .join("");
    const susp = st.suspended.reduce((a, v) => a + v, 0);
    const plants = fileOf<UsPlantsFile>("usPlants");
    const op = operatingMw(plants, code);
    const ratio = plants && op > 0 ? `<div>${ratioText(queueMw(q, code) / op)} the ${gwText(op)} of plants it runs today <span style="color:#8d94a1">(EIA-860M ${plants.release}, computed)</span></div>` : "";
    return `<b>${name}</b><div><b>${gwText(queueMw(q, code))}</b> in ${st.active_n.toLocaleString("en-US")} active requests · most: ${largestType(q, code)}</div>${ratio}<div style="margin-top:4px">${rows}</div>${susp > 0 ? `<div style="color:#8d94a1">suspended: ${gwText(susp)} in ${st.suspended_n}</div>` : ""}${SRC(`LBNL Queued Up, requests active at the ${q.through} · hybrids counted under each type`)}`;
  }
  return null;
}

function riskHtml(id: string, object: unknown): string | null {
  if (id === "us-outages") {
    const code = (object as { code: string }).code;
    const f = fileOf<UsOutagesFile>("usOutages");
    const cty = fileOf<UsCountiesFile>("usCounties")?.counties.find((c) => c.code === code);
    if (!f) return null;
    const { year, k } = newestYear(f);
    const name = f.names[code] ?? (cty ? `${cty.name}, ${cty.state}` : code);
    const ch = f.counties[code]?.[k];
    const n = f.customers[code];
    const per = ch != null && n ? `<div><b>${(ch / n).toFixed(1)} h</b> per customer <span style="color:#8d94a1">(÷ ${n.toLocaleString("en-US")} customers, ORNL's model, computed)</span></div>` : "";
    const years = f.years
      .map((y, i) => [y, f.counties[code]?.[i]] as [number, number | null | undefined])
      .filter(([, v]) => v != null)
      .slice(-4)
      .map(([y, v]) => `${y}: ${hoursText(v!)}`)
      .join(" · ");
    return `<b>${name}</b><div><b>${ch != null ? hoursText(ch) : "0"}</b> customer-hours without power in ${year}</div>${per}${years ? `<div style="color:#8d94a1">${years}</div>` : ""}${SRC("EAGLE-I (ORNL): customers out every 15 min, summed × ¼ h (computed); customers are utility meters, not people")}`;
  }
  if (id === "w-water") {
    const f = fileOf<WaterFile>("water");
    const b = f?.basins[(object as { k: number }).k];
    if (!f || !b) return null;
    const rows = f.order
      .map((ind, i) => {
        const cat = b.c[i];
        const label = cat == null ? "no data" : (f.indicators[ind].labels[String(cat)] ?? String(cat));
        return `<div style="display:flex;justify-content:space-between;gap:16px"><span>${f.indicators[ind].name}</span><span>${label}</span></div>`;
      })
      .join("");
    return `<b>River basin ${b.id}</b>${rows}${SRC(`WRI Aqueduct ${f.version}, baseline, WRI's categories${Object.values(f.mixed).some((n) => n > 0) ? "; where a basin's parts differ, the highest" : ""}`)}`;
  }
  return null;
}

function mastrHtml(id: string, object: unknown): string | null {
  if (id === "de-mastr-muni") {
    const f = fileOf<MastrMuniFile>("mastrMuni");
    const g = f?.gemeinden[(object as { k: number }).k];
    if (!f || !g) return null;
    const rows = f.techs
      .map((t, i) => [t, g.mw[i], g.n[i]] as [string, number, number])
      .filter(([, mw]) => mw > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([t, mw, n]) => `<div style="display:flex;justify-content:space-between;gap:16px"><span>${MASTR_LABEL[t] ?? t}</span><span>${mwText(mw)} · ${n.toLocaleString("en-US")}</span></div>`)
      .join("");
    return `<b>${g.name ?? g.ags}</b><div style="color:#8d94a1">AGS ${g.ags} · units in operation, gross MW</div>${rows}${SRC(`Marktstammdatenregister ${f.snapshot}, sums per municipality (computed)`)}`;
  }
  if (id === "de-mastr-units") {
    const f = fileOf<MastrUnitsFile>("mastrUnits");
    const u = object as MastrUnitsFile["units"][number];
    if (!f) return null;
    return `<b>${MASTR_LABEL[f.techs[u[2]]] ?? f.techs[u[2]]}</b><div>${mwText(u[3])} gross${u[4] ? ` · in operation since ${u[4]}` : ""}</div>${SRC(`Marktstammdatenregister ${f.snapshot}`)}`;
  }
  return null;
}

function tooltipHtml(id: string, object: unknown): string | null {
  if (id.startsWith("site-")) return siteHtml(id, object);
  if (id === "us-outages" || id === "w-water") return riskHtml(id, object);
  if (id.startsWith("de-mastr-")) return mastrHtml(id, object);
  if (id === "eu-tyndp" || id === "eu-tyndp-areas" || id === "eu-tyndp-points") {
    const f = fileOf<TyndpFile>("tyndp");
    const k = typeof object === "number" ? object : (object as { k: number }).k;
    const x: TyndpFeature | undefined = f?.features[k];
    if (!f || !x) return null;
    const facts = [
      x.capacity_mw ? `${x.capacity_mw.toLocaleString("en-US")} MW` : "",
      x.voltage_kv ? `${x.voltage_kv} kV` : "",
      x.generating_mw ? `${x.generating_mw.toLocaleString("en-US")} MW generating` : "",
      x.element ?? "",
      x.length_km ? `${x.length_km} km` : "",
    ].filter(Boolean);
    return `<b>${x.investment ?? x.project ?? "Project"}</b>${x.investment && x.project ? `<div>${x.project}</div>` : ""}<div>${x.status != null ? f.statuses[x.status] : "status not given"}${x.year ? ` · commissioning ${x.year}` : ""}</div>${facts.length ? `<div>${facts.join(" · ")}</div>` : ""}${x.promoter ? `<div style="color:#8d94a1">${x.promoter}</div>` : ""}${SRC(`ENTSO-E TYNDP 2024 project ${x.type ?? ""} ${x.id ?? ""}`)}`;
  }
  if (id === "us-ghgrp") {
    const f = fileOf<GhgrpFile>("ghgrp");
    const p = typeof object === "number" ? f?.points[object] : undefined;
    if (!f || !p) return null;
    return `<b>${p[4]}</b><div>${f.sectors[p[3]]} · ${p[5]}</div><div><b>${Math.round(p[2]).toLocaleString("en-US")}</b> t CO₂e in ${f.year}, reported</div>${SRC(`EPA GHGRP ${f.year} (AR4 GWP)`)}`;
  }
  if (id === "us-ev") {
    const f = fileOf<EvChargersFile>("evChargers");
    const p = typeof object === "number" ? f?.points[object] : undefined;
    if (!f || !p) return null;
    const name = f.names[object as number] || "Unnamed station";
    return `<b>${name}</b><div>${f.networks[p[3]]}</div><div><b>${p[2]}</b> DC fast port${p[2] === 1 ? "" : "s"}${p[4] ? ` · opened ${p[4]}` : ""}</div>${SRC(`NREL Alternative Fuels Data Center, ${f.fetched.slice(0, 10)}`)}`;
  }
  if (id === "us-solar" || id === "us-solar-areas") {
    const f = fileOf<UsSolarFile>("usSolar");
    const k = typeof object === "number" ? object : (object as { k: number }).k;
    const s = f?.sites[k];
    if (!f || !s) return null;
    const axis = solarCat(f, "p_axis", s[8]);
    const sys = solarCat(f, "p_sys_type", s[9]);
    const site = solarCat(f, "p_type", s[10]);
    const agri = solarCat(f, "p_agrivolt", s[11]);
    const mw = (v: number | null) => (v == null ? "–" : `${v.toLocaleString("en-US")} MW`);
    const facts = [axis, sys && sys !== "ground" ? sys : "", site && site !== "greenfield" ? site : "", agri && agri !== "non-agrivoltaic" ? `agrivoltaic (${agri})` : "", s[13] ? `battery: ${s[13]}` : ""].filter(Boolean);
    return `<b>${s[5] ?? "Unnamed array"}</b><div>${s[7] ? `${s[7]}, ` : ""}${s[6] ?? ""}${s[4] ? ` · since ${s[4]}` : ""}</div><div><b>${mw(s[2])}</b> AC · ${mw(s[3])} DC</div>${facts.length ? `<div style="color:#8d94a1">${facts.join(" · ")}</div>` : ""}${SRC(`USPVDB ${f.release} (USGS, LBNL)${s[15] ? `, outline from imagery of ${String(s[15]).slice(0, 4)}` : ""}`)}`;
  }
  if (id === "eu-offshore-wind" || id === "eu-offshore-wind-points") {
    const f = fileOf<OffshoreWindFile>("offshoreWind");
    const k = typeof object === "number" ? object : (object as { k: number }).k;
    const farm = f?.farms[k];
    if (!f || !farm) return null;
    const status = offshoreStatus(f, farm);
    const facts = [
      farm.mw != null ? `<b>${farm.mw.toLocaleString("en-US")} MW</b>` : "capacity not given",
      farm.turbines != null ? `${farm.turbines} turbines` : "",
      farm.year != null ? (status === "Production" || status === "Dismantled" ? `since ${farm.year}` : `year ${farm.year}`) : "",
    ].filter(Boolean);
    return `<b>${farm.name ?? "Unnamed farm"}</b><div>${farm.country ?? ""} · ${OFFSHORE_LABEL[status] ?? status}</div><div>${facts.join(" · ")}</div>${farm.coast_km != null ? `<div style="color:#8d94a1">${farm.coast_km} km from the coast</div>` : ""}${SRC(`EMODnet Human Activities (CETMAR), ${farm.polygons ? "farm area" : "point record, no area published"}`)}`;
  }
  if (id === "us-retail") {
    const d = object as { code: string; name: string };
    const us = fileOf<RetailFile>("retail")?.us;
    const n = us ? newestMonth(us.months, us.price[d.code]?.RES) : null;
    if (!us || !n) return `<b>${d.name}</b>${SRC("no EIA retail price")}`;
    const p = us.price[d.code];
    return `<b>${d.name}</b><div>Households pay <b>${usCents(n.v)}/kWh</b> on average</div>
      <div>businesses ${usCents(p.COM[n.k])} · industry ${usCents(p.IND[n.k])}</div>${SRC(`EIA retail sales (EIA-861M), ${n.month}`)}`;
  }
  if (id.startsWith("eu-connect7")) {
    // eu-connect7:<id> (points) or eu-connect7-areas:<id> (areas): every published column
    const cc = id.split(":")[1];
    const f = fileOf<ConnectEuFile>(connectEuKey(cc));
    if (!f) return null;
    const isArea = id.startsWith("eu-connect7-areas");
    const row = isArea ? (object as { a: EuArea }).a : (object as EuPoint);
    const vals = isArea ? (row as EuArea)[2] : (row as EuPoint)[4];
    const kv = !isArea && (row as EuPoint)[3] != null ? ` · ${(row as EuPoint)[3]} kV` : "";
    const lines = f.columns.map(([, label, unit], i) => (vals[i] == null || vals[i] === "" ? "" : `<div>${label}: <b>${valueText(vals[i], unit)}</b></div>`)).join("");
    const cls = isArea ? (row as EuArea)[3] : (row as EuPoint)[5];
    return `<b>${row[0]}</b><div style="color:#8d94a1">${f.classes[cls] ?? ""}${kv}</div>${lines}${SRC(`${f.source}${f.updated ? `, ${f.updated}` : ""}`)}`;
  }
  if (id === "us-gas-pipes") {
    const g = fileOf<UsGasPipesFile>("usGasPipes");
    const l = g?.lines[(object as [unknown, number])[1]];
    if (!l) return null;
    return `<b>${l[2] ?? "Operator not given"}</b><div>${l[1] ?? ""}${l[3] ? ` · ${l[3]}` : ""}</div>${SRC("EIA, natural gas pipelines (U.S. Energy Atlas)")}`;
  }
  if (id === "eu-ev") {
    const c = object as EvEuCell;
    const m = fileOf<EvEuFile>("evEu")?.maps[c[3]];
    return `<b>${c[2].toLocaleString("en-US")} ${m?.unit ?? "chargers"}</b><div style="color:#8d94a1">in this 0.1° cell (sum, computed) · ${c[3]}</div>${SRC(m ? `${m.source}, ${m.fetched}` : "")}`;
  }
  if (id.startsWith("reg:")) {
    const p = object as RegisterPoint;
    const f = fileOf<RegisterFile>(registerKey(id.slice(4)));
    const mw = p[4] != null ? `${p[4].toLocaleString("en-US", { maximumFractionDigits: 2 })} ${f?.unit ?? "MW"}` : "capacity not given";
    return `<b>${p[0]}</b><div>${FUEL_LABEL[p[3] === "wind_offshore" ? "wind" : p[3]] ?? p[3]}${p[3] === "wind_offshore" ? " at sea" : ""} · ${mw}</div><div style="color:#8d94a1">${REG_STATUS[p[5]] ?? p[5]}${p[6] ? ` · ${p[6]}` : ""}</div>${SRC(f ? `${p[7]} (${f.source})` : p[7])}`;
  }
  if (id.startsWith("gem-")) return gemHtml(id, object);
  if (id.startsWith("us-")) return usHtml(id, object);
  if (id.startsWith("fin-")) return financeHtml(id, object);
  const plants = fileOf<PlantsFile>("plants");
  switch (id) {
    case "eu-countries": {
      const s = object as Shape;
      return countryHtml(s.name, s.iso, null);
    }
    case "w-cables": {
      const c = object as Cable;
      return `<b>${c[2] ?? "Undersea power cable"}</b><div>${(CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).label}${c[1] ? ` · ${c[1]} kV` : ""}</div>${SRC("OpenStreetMap")}`;
    }
    case "w-plants": {
      const k = object as number;
      const wp = fileOf<WorldPlantsFile>("worldPlants");
      if (!wp) return null;
      if (!namesAsked) {
        namesAsked = true;
        ensure("plantNames");
      }
      const names = fileOf<{ names: string[] }>("plantNames")?.names;
      const pt = wp.points[k];
      const status = wp.statuses[pt[3]];
      const year = pt[5] ? ` · ${status === "retired" ? "retired" : "from"} ${pt[5]}` : "";
      return `<b>${names?.[k] || "Power plant"}</b><div>${PLANT_TYPE_LABEL[wp.types[pt[2]]] ?? wp.types[pt[2]]} · ${pt[4].toLocaleString("en-US")} MW · ${STATUS_LABEL[status] ?? status}${year}</div>${SRC("Global Energy Monitor, Sep 2026")}`;
    }
    case "w-dc-clusters": {
      const c = object as DataCentresFile["clusters"][number];
      return `<b>${c[2]} data centres</b><div>mapped in OpenStreetMap within this 1° cell</div>`;
    }
    case "w-datacentres": {
      const d = object as DataCentresFile["points"][number];
      return `<b>${d[2] ?? "Data centre"}</b>${d[3] ? `<div>${d[3]}</div>` : ""}${SRC("OpenStreetMap")}`;
    }
    case "w-br-flows": {
      const a = object as Arc;
      return `<b>${a.from} → ${a.to}</b> ${power(a.mw)}${SRC(`ONS interchange, ${a.ts.slice(11, 16)} BRT`)}`;
    }
    case "w-br-regions": {
      const sub = fileOf<BrazilFile>("brazil")?.subsystems[(object as { id: string }).id];
      return sub ? `<b>${sub.name}</b><div>Load ${power(sub.load ?? 0)}</div>${SRC("ONS, live · click for details")}` : null;
    }
    case "w-us-flows": {
      const a = object as Arc;
      return `<b>${a.from} → ${a.to}</b> ${power(a.mw)}${SRC(`EIA-930 interchange, ${a.ts.replace("T", " ")}:00 UTC`)}`;
    }
    case "w-us-regions": {
      const rid = (object as { id: string }).id;
      const rg = fileOf<UsFile>("us")?.regions[rid];
      if (!rg) return null;
      const net = rg.interchange
        ? `<div>${rg.interchange[1] >= 0 ? "Net export" : "Net import"} ${power(rg.interchange[1])} (${rg.interchange[0].replace("T", " ")}:00 UTC)</div>`
        : "";
      return `<b>${rg.name}</b> (${rid})<div>Demand ${rg.demand ? power(rg.demand[1]) : "–"} · ${rg.demand ? rg.demand[0].replace("T", " ") : ""}:00 UTC</div>${net}${SRC("EIA-930 · click for details")}`;
    }
    case "w-au-flows": {
      const a = object as Arc;
      return `<b>${a.from} → ${a.to}</b> ${power(a.mw)}${SRC("AEMO interconnector flow, 5-min dispatch")}`;
    }
    case "w-au-regions": {
      const rid = (object as { id: string }).id;
      const r = fileOf<AemoFile>("aemo")?.regions[rid];
      if (!r) return null;
      return `<b>${NEM_NAME[rid] ?? rid}</b><div>Price <b>${r.price != null ? `${r.price.toFixed(0)} A$/MWh` : "–"}</b> · demand ${r.demand != null ? power(r.demand) : "–"}</div>${SRC("AEMO, 5-min dispatch · click for details")}`;
    }
    case "w-tw-regions": {
      const tw = fileOf<TaiwanFile>("taiwan");
      if (!tw) return null;
      const solar = tw.types.filter((t) => t.group === "solar" || t.group === "wind").reduce((a, t) => a + (t.net_mw ?? 0), 0);
      return `<b>Taiwan</b><div>Net generation ${power(tw.total_mw)} · wind and solar ${power(solar)}</div>${SRC(`Taipower, every unit, ${tw.at.slice(11, 16)} Taipei time · click for details`)}`;
    }
    case "w-nz-regions": {
      const nz = fileOf<NzFile>("nz");
      if (!nz) return null;
      return `<b>New Zealand</b><div>Generation ${power(nz.total_mw)}</div>${SRC(`Transpower (em6), ${nz.at} · click for details`)}`;
    }
    case "w-za-regions": {
      const za = fileOf<ZaFile>("za");
      if (!za) return null;
      return `<b>South Africa</b><div>Load-shedding: <b>${za.loadshedding_stage ? `stage ${za.loadshedding_stage}` : "none"}</b></div>${SRC("Eskom · click for details")}`;
    }
    case "w-on-regions": {
      const on = fileOf<OntarioFile>("ontario");
      if (!on) return null;
      return `<b>Ontario</b><div>Demand ${on.demand ? power(on.demand.mw) : "–"} · price ${on.price ? `${on.price.cad_mwh.toFixed(1)} CAD/MWh` : "–"}</div>${SRC("IESO, 5-min · click for details")}`;
    }
    case "w-on-flows": {
      const a = object as Arc;
      return `<b>${a.from} → ${a.to}</b> ${power(a.mw)}${SRC(`IESO actual intertie flow, ${a.ts.slice(11, 16)} EST`)}`;
    }
    case "price-terrain": {
      const iso = (object as Shape).iso;
      const st = priceState;
      const zones = st.zones.of[iso] ?? [];
      const list = zones.map((z) => `<div>${z}: <b>${st.prices[z] != null ? `${st.prices[z].toFixed(2)} €/MWh` : "–"}</b></div>`).join("");
      const note = zones.length > 1 ? `<div style="color:#8d94a1">height: the median of its zones</div>` : "";
      return `<b>${(object as Shape).name}</b>${list}${note}${SRC("ENTSO-E day-ahead auction, 15 min · click for the country")}`;
    }
    case "pr-zones": {
      const zone = (object as { zone: string }).zone;
      const pf = fileOf<PricesFile>("prices");
      const z = pf?.zones[zone];
      if (!pf || !z) return null;
      const m = priceMetricById(useApp.getState().colour.slice(3) as Parameters<typeof priceMetricById>[0]);
      const shaped = "polygon" in (object as object) ? `<div style="color:#8d94a1">approximate outline (NUTS regions)</div>` : "";
      return `<b>${zone}</b><div>${m.label.toLowerCase()} <b>${m.format(m.value(z))}</b></div>${shaped}${SRC(`${pf.period[0].slice(0, 7)} to ${pf.period[1].slice(0, 7)} · click for the zone`)}`;
    }
    case "eu-flows": {
      const a = object as Arc;
      const cap =
        a.cap != null && a.cap > 0
          ? `<div>uses <b>${Math.round((100 * a.mw) / a.cap)} %</b> of the ${gw(a.cap)} on offer <span style="color:#8d94a1">(${a.capDoc === "A31" ? "offered capacity, day-ahead auction" : "forecast transfer capacity, day-ahead"}; share computed)</span></div>`
          : `<div style="color:#8d94a1">no capacity published for this border${["AT", "BE", "CZ", "DE", "FR", "HR", "HU", "NL", "PL", "RO", "SI", "SK"].includes(a.from) && ["AT", "BE", "CZ", "DE", "FR", "HR", "HU", "NL", "PL", "RO", "SI", "SK"].includes(a.to) ? " (Central Europe sets its limits jointly, flow-based)" : ""}</div>`;
      return `<b>${a.from} → ${a.to}</b> ${gw(a.mw)}${cap}${SRC(`physical flow, interval ${utc(a.ts)} · ENTSO-E`)}`;
    }
    case "eu-gas-flows": {
      const a = object as GasArc;
      const g = fileOf<GasFlowsFile>("gasFlows");
      if (!g) return null;
      const cname = (iso: string) => fileOf<CountriesFile>("countries")?.countries.find((c) => c.iso === iso)?.name ?? iso;
      const p = a.pair;
      const pts = p.points.filter((x) => x[3]).slice(0, 4).map((x) => `<div style="color:#8d94a1">${x[0]} ${gwhd(x[3])}</div>`).join("");
      const two = p.kind === "border" && latestOf(p.ab) && latestOf(p.ba) ? `<div>${gwhd(latestOf(p.ab))} ${p.a}→${p.b}, ${gwhd(latestOf(p.ba))} back</div>` : "";
      return `<b>${endName(a.from, g, cname, a.country)} → ${endName(a.to, g, cname, a.country)}</b> ${gwhd(a.gwh)}${two}${pts}${SRC(`net physical flow, gas day ${g.gas_day} · ENTSOG, sum of ${cname(p.read_from)}'s operators' reports`)}`;
    }
    case "eu-lng-capacity":
    case "eu-lng-sendout": {
      const t = object as LngTerminal;
      const lf = fileOf<LngTerminalsFile>("lngTerminals");
      if (!lf) return null;
      const d = lngDay(t, lf.date);
      const status = d?.[4] ? ` · ${STATUS_TEXT[d[4]] ?? d[4]}` : "";
      return `<b>${t.name}</b><div>${t.operator} · ${t.type === "FSRU" ? "floating (FSRU)" : "onshore"}</div>
        <div>Send-out <b>${gwhdText(d?.[1])}</b> of ${gwhdText(d?.[3])} declared</div>
        ${d?.[2] != null ? `<div>LNG in tanks ${d[2].toLocaleString("en-US")} GWh</div>` : ""}${SRC(`gas day ${lf.date}${status} · GIE ALSI`)}`;
    }
    case "us-node-prices": {
      const i = object as number;
      const day = currentDay();
      const f = day ? fileOf<UsNodesFile>(`usNodes:${day.date}`) : undefined;
      if (!f) return null;
      const k = Math.min(f.slots - 1, Math.floor(motion.daySlot));
      const [, , name, area] = f.nodes[i];
      const vals = f.prices[i].filter((v): v is number => v != null);
      const hour = clockOf(f.timezone)(new Date(Date.parse(f.start) + k * f.step_s * 1000).toISOString());
      return `<b>${name}</b><div>${area} · CAISO day-ahead market</div>
        <div>${hour}: <b>${usdMwh(f.prices[i][k])}/MWh</b></div>
        ${vals.length ? `<div style="color:#8d94a1">day: ${usdMwh(Math.min(...vals))} to ${usdMwh(Math.max(...vals))}</div>` : ""}${SRC(`CAISO day-ahead LMP, ${f.date}; position from CAISO's price map`)}`;
    }
    case "eu-connect-nl": {
      const a = (object as { a: NlArea }).a;
      const cf = fileOf<ConnectFile>("connect");
      if (!cf) return null;
      const st = cf.nl.status;
      const q = (mw: number | null, n: number | null) => (mw ? ` · queue ${mw.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW${n ? ` (${n} requests)` : ""}` : "");
      return `<b>${a.name}</b><div>${a.operator ?? ""}</div>
        <div>New demand: <b>${st[a.offtake] ?? "–"}</b>${q(a.queue_offtake_mw, a.requests_offtake)}</div>
        <div>New generation: <b>${st[a.feedin] ?? "–"}</b>${q(a.queue_feedin_mw, a.requests_feedin)}</div>${SRC("Netbeheer Nederland, capaciteitskaart (regional operators)")}`;
    }
    case "eu-connect-gb": {
      const d = object as { k: number; site: GbSite; mw: number; byType: number[] };
      const cf = fileOf<ConnectFile>("connect");
      if (!cf) return null;
      const parts = d.byType
        .map((mw, i) => [cf.gb.types[i], mw] as const)
        .filter(([, mw]) => mw > 0)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([t, mw]) => `${t} ${connectGw(mw)}`)
        .join(" · ");
      return `<b>${d.site[0]}</b><div>${d.site[3]} · <b>${connectGw(d.mw)}</b> waiting to connect</div><div>${parts}</div>${SRC(`NESO TEC register, ${cf.gb.date} · placed at the GSP of that name (NESO lookup)`)}`;
    }
    case "eu-hydrogen": {
      const p = object as H2Project;
      const hf = fileOf<HydrogenFile>("hydrogen");
      if (!hf) return null;
      const part = (i: number | null, list: string[]) => (i != null ? list[i] : null);
      return `<b>${p[0]}</b><div>${[p[1], part(p[10], hf.stages), p[3]].filter(Boolean).join(" · ")}</div>
        <div>${p[4] != null ? `<b>${p[4].toLocaleString("en-US")} MW</b> · ` : ""}${[part(p[5], hf.processes), part(p[6], hf.end_uses)].filter(Boolean).join(" · ")}</div>
        ${p[7] != null ? `<div>${p[7].toLocaleString("en-US")} t/year</div>` : ""}${SRC(`European Hydrogen Observatory (${hf.file})`)}`;
    }
    case "eu-gas-projects": {
      const d = object as { name: string; n: number; byCat: Record<string, number> };
      const gf = fileOf<GasProjectsFile>("gasProjects");
      if (!gf) return null;
      const parts = Object.entries(d.byCat)
        .sort((a, b) => b[1] - a[1])
        .map(([c, n]) => `${n} ${gf.categories[c] ?? c}`)
        .join(" · ");
      return `<b>${d.name}</b><div><b>${d.n}</b> projects in the TYNDP 2026</div><div>${parts}</div>${SRC("ENTSOG TYNDP 2026 Annex A (counted per country, computed)")}`;
    }
    case "w-sea-cables": {
      const c = object as SeaCable;
      return `<b>${c[1] ?? "Power cable"}</b>${c[2] ? `<div>${c[2]}</div>` : ""}${SRC(`EMODnet Human Activities, power cables from ${SEA_CABLE_SOURCE[c[0]] ?? c[0]}`)}`;
    }
    case "w-sea-pipes": {
      const p = object as SeaPipe;
      return `<b>${p[0] ?? "Pipeline"}</b><div>${[p[1], p[2], p[3], p[5] != null ? `${p[5]} in` : null].filter(Boolean).join(" · ")}</div>${SRC(`EMODnet Human Activities, pipelines at sea${p[4] ? ` (${p[4]})` : ""}`)}`;
    }
    case "eu-connect-fr": {
      const st = object as FrSite;
      const cf = fileOf<FrFile>("connectFR");
      if (!cf) return null;
      const row = (code: string, unit = "MW") => {
        const v = frValue(cf, st, code);
        return v == null ? "" : `<div>${cf.labels[code] ?? code}: <b>${typeof v === "number" ? `${v.toLocaleString("en-US")} ${unit}` : v}</b></div>`;
      };
      return `<b>${st[1]}</b><div>${st[2]}${st[5] ? ` · up to ${st[5]} kV` : ""}</div>${row("INFO_NA")}${row("RTE_CDR")}${row("GRD1_CDR")}${row("INFO_FAS3R")}${row("INFO_QP", "")}${SRC(`Capareseau (RTE and the distribution operators), updated ${st[6] ?? "–"}`)}`;
    }
    case "eu-connect-ie": {
      const st = object as IeStation;
      const cf = fileOf<IeFile>("connectIE");
      if (!cf) return null;
      const v = (c: string) => st[5][cf.columns.indexOf(c)];
      const n = (x: number | null | undefined, u: string) => (x == null ? "–" : `${x.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${u}`);
      return `<b>${st[0]}</b><div>installed ${n(v("installed_mva"), "MVA")}</div>
        <div>Demand available: <b>${n(v("demand_available_mva"), "MVA")}</b></div>
        <div>Generation available: <b>${n(v("gen_available_firm_mw"), "MW")}</b> firm, ${n(v("gen_available_nonfirm_mw"), "MW")} non-firm</div>
        ${st[6] ? `<div style="color:#8d94a1">${st[6]}</div>` : ""}${SRC(`ESB Networks capacity heatmap (${cf.file}); transformer capacity only`)}`;
    }
    case "eu-connect-it": {
      const d = object as { reg: string };
      const cf = fileOf<ItFile>("connectIT");
      if (!cf) return null;
      const t = itTotals(cf)[d.reg];
      const top = Object.entries(cf.renewables.regions[d.reg] ?? {})
        .sort((a, b) => b[1][0] - a[1][0])
        .slice(0, 3)
        .map(([src, [mw]]) => `${src} ${connectGw(mw)}`)
        .join(" · ");
      return `<b>${d.reg}</b><div>Renewables requested: <b>${connectGw(t?.fer ?? 0)}</b></div><div>${top}</div><div>Storage requested: <b>${connectGw(t?.storage ?? 0)}</b></div>${SRC("Terna Econnextion: requests to connect to the transmission grid (sums over sources, computed); requests, not plants")}`;
    }
    case "w-ctrace": {
      const r = object as CtRow;
      const ct = fileOf<CtraceFile>("ctrace");
      if (!ct) return null;
      const before = r[6] != null ? ` · ${ct.year - 1}: ${mt(r[6])}` : "";
      return `<b>${r[3] || "Facility"}</b><div>${subsectorLabel(ct.subsectors[r[4]])} · ${r[2]}${r[7] ? ` · ${r[7]}` : ""}</div>
        <div>CO₂e ${ct.year} <b>${mt(r[5])}</b>${before}</div>${isBasin(ct, r) ? `<div style="color:#8d94a1">a whole basin's production, placed at its centre</div>` : ""}${SRC("modelled by Climate TRACE (CO₂e, 100-year)")}`;
    }
    case "eu-ets": {
      const r = object as EtsRow;
      const ef = fileOf<EtsFile>("ets");
      if (!ef) return null;
      const yrs = r[4]
        .map((t, i) => [ef.years[i], t] as const)
        .filter(([, t]) => t != null)
        .slice(-3)
        .map(([y, t]) => `${y} ${mt(t!)}`)
        .join(" · ");
      const where = ETS_REGISTRY_NAME[r[0]] ?? r[0];
      return `<b>${r[2]}</b><div>${ef.groups[r[3]]} · ${where}</div><div>Verified CO₂ <b>${yrs}</b></div>${SRC(`EU Union Registry, verified emissions (t CO₂e) · placed by its ETS id in the EEA industrial register`)}`;
    }
    case "eu-lng":
    case "eu-gas-storage": {
      const g = object as GasSite;
      const lng = id === "eu-lng";
      const cap = g[5] != null ? (lng ? ` · send-out ${g[5]} M m³/day` : ` · working gas ${g[5].toLocaleString("en-US")} M m³`) : "";
      return `<b>${g[0]}</b><div>${lng ? "LNG terminal" : "Gas storage"}${cap}${g[4] ? ` · since ${g[4]}` : ""}</div>${SRC("SciGRID_gas 2021")}`;
    }
    case "eu-plant-output": {
      const r = object as PlantOutputRow;
      const day = currentDay();
      const region = useApp.getState().dayRegion;
      const f = day ? fileOf<UnitOutputFile>(unitOutKey(region, day.date)) : undefined;
      if (!f || !day) return null;
      const k = Math.min(f.slots - 1, Math.floor(motion.daySlot));
      const mw = f.output[r.k]?.[k];
      const t = new Date(Date.parse(day.start) + k * day.step_s * 1000).toISOString();
      const share = mw != null && r.capacity ? ` · ${Math.round((100 * mw) / r.capacity)} % of its capacity` : "";
      if (region === "us") {
        const co2 = f.co2_t?.[r.k]?.[k];
        const names = (day.names ?? {}) as Record<string, string>;
        return `<b>${r.name}</b><div>${FUEL_LABEL[r.fuel] ?? r.fuel} · ${r.iso ? (names[r.iso] ?? r.iso) : "no EIA region"} · ${r.units} unit${r.units > 1 ? "s" : ""}</div><div><b>${mw != null ? power(mw) : "no value"}</b> in the hour from ${clockOf(f.timezone)(t)}${share}</div>${co2 != null ? `<div>CO₂ <b>${Math.round(co2).toLocaleString("en-US")} t</b> in that hour</div>` : ""}${r.capacity ? `<div style="color:#8d94a1">capacity ${power(r.capacity)} (nameplate of the generators its units drive)</div>` : ""}${SRC("EPA CAMPD, hourly gross load and CO₂ per unit, summed per plant; CO₂ from short tons (× 0.907)")}`;
      }
      return `<b>${r.name}</b><div>${FUEL_LABEL[r.fuel] ?? r.fuel} · ${r.iso} · ${r.units} unit${r.units > 1 ? "s" : ""}</div><div><b>${mw != null ? power(mw) : "no value"}</b> at ${marketTime(t)}${share}</div>${r.capacity ? `<div style="color:#8d94a1">capacity ${power(r.capacity)} (JRC, sum of its units)</div>` : ""}${SRC("ENTSO-E output per generation unit (A73), 15 min or hourly; placed with the JRC Open Power Plants Database")}`;
    }
    case "eu-towers": {
      const t = object as TowerPiece;
      return `<b>${t.name}</b><div>${FUEL_LABEL[t.group] ?? t.group} ${power(t.mw)} of ${power(t.total)} generated</div>${SRC("ENTSO-E, 15-min interval")}`;
    }
    case "eu-substations":
      return `Substation · ${(object as Substation)[0]} kV${SRC("OpenStreetMap")}`;
    case "eu-hex-fields": {
      const h = object as Hex;
      const groups = plants?.groups ?? [];
      const mix = [...h.mix.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([g, mw]) => `${PLANT_LABEL[groups[g] ?? "other"]} ${power(mw)}`)
        .join(" · ");
      return `<b>${power(h.mw)}</b> in ${h.units.toLocaleString("en-US")} units under ${BEAM_MIN_MW} MW<div>${mix}</div>${SRC(`sum over a ${HEX_KM * 2} km hexagon`)}`;
    }
    case "eu-plants": {
      const p = object as Plant;
      return `<b>${p[5]}</b><div>${PLANT_LABEL[plants?.groups[p[0]] ?? "other"]} · ${p[1].toLocaleString("en-US")} MW installed${p[6] ? ` · since ${p[6]}` : ""}</div>${SRC("powerplantmatching")}`;
    }
  }
  if (id === "eu-plant-columns" || id === "eu-focus-small" || id.startsWith("eu-beam")) {
    // beam segments wrap their unit; the glow, bars and dots are units themselves
    const u = (Array.isArray(object) ? object : (object as { unit: Unit }).unit) as Unit;
    return `<b>${u[4]}</b><div>${PLANT_LABEL[plants?.groups[u[0]] ?? "other"]} · ${u[1].toLocaleString("en-US")} MW installed${u[5] ? ` · since ${u[5]}` : ""}</div>`;
  }
  return null;
}
