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
import { STATUS_TEXT, gwhdText, lngDay, type LngTerminal, type LngTerminalsFile } from "../lib/lngTerminals";
import type { GasArc } from "./build";
import { CABLE_STYLE } from "../app/colors";
import { ensure, fileOf } from "../app/data";
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
    return `<b>${name}</b><div>${US_TYPE_LABEL[f.types[p[2]]] ?? f.types[p[2]]} · ${p[4].toLocaleString("en-US")} MW net summer · ${STATUS_LABEL[status] ?? status}${when}</div><div>${p[7]} generator${p[7] > 1 ? "s" : ""} · ${state} · EIA plant ${eia}</div>${SRC(`EIA-860M, ${f.release}`)}`;
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

function tooltipHtml(id: string, object: unknown): string | null {
  if (id === "us-retail") {
    const d = object as { code: string; name: string };
    const us = fileOf<RetailFile>("retail")?.us;
    const n = us ? newestMonth(us.months, us.price[d.code]?.RES) : null;
    if (!us || !n) return `<b>${d.name}</b>${SRC("no EIA retail price")}`;
    const p = us.price[d.code];
    return `<b>${d.name}</b><div>Households pay <b>${usCents(n.v)}/kWh</b> on average</div>
      <div>businesses ${usCents(p.COM[n.k])} · industry ${usCents(p.IND[n.k])}</div>${SRC(`EIA retail sales (EIA-861M), ${n.month}`)}`;
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
      return `<b>${zone}</b><div>${m.label.toLowerCase()} <b>${m.format(m.value(z))}</b></div>${SRC(`${pf.period[0].slice(0, 7)} to ${pf.period[1].slice(0, 7)} · click for the zone`)}`;
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
