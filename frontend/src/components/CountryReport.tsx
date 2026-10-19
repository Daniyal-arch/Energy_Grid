// A country's report: one printable page of what the map's files say about its power system,
// section by section, each figure with its unit and source; the same rows download as CSV.
// Opened from the country panel ("Report"), shared as ?report=DE (Europe) or ?report=BRA.

import { useEffect, useMemo, type ReactNode } from "react";

import { useFile } from "../app/data";
import { actions, useApp } from "../app/store";
import type { CountriesFile, GridFile, ReferenceFile, StatsFile, WorldFile } from "../app/types";
import { coverageRows, type CoverageFile } from "../lib/coverage";
import type { CtraceFile } from "../lib/ctrace";
import { FUEL_LABEL } from "../lib/energy";
import type { EtsFile } from "../lib/ets";
import type { IrenaFile } from "../lib/irena";
import { OFFSHORE_LABEL, offshoreStatus, type OffshoreWindFile } from "../lib/offshoreWind";
import type { PricesFile } from "../lib/prices";
import { newestMonth, newestOf, type RetailFile, type RetailSeries, SERIES_LABEL } from "../lib/retail";
import { ISO3, type TransitionFile } from "../lib/transition";
import type { UsPlantsFile, UsQueueFile } from "../lib/us";
import type { UsSolarFile } from "../lib/usSolar";
import type { DataCentresFile, WorldStatsFile } from "../lib/world";
import { PLANT_TYPE_LABEL, STATUS_LABEL, type WorldPlantsFile } from "../lib/worldPlants";

/** A profile file (scripts/build_profiles.py): rows per ISO alpha-3 (US states by postal code). */
interface ProfileFile {
  title: string;
  source: string;
  rows: Record<string, Row[]>;
}

/** [item, value, unit, note]: one figure, unformatted. */
type Row = [string, number | string | null, string, string];
interface Section {
  title: string;
  source: string;
  rows: Row[];
}

const ISO2_OF: Record<string, string> = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));
const sumOf = (o: Record<string, number> | undefined) => Object.values(o ?? {}).reduce((a, b) => a + b, 0);
const newestK = (v: (number | null)[] | undefined) => {
  if (!v) return -1;
  for (let k = v.length - 1; k >= 0; k--) if (v[k] != null) return k;
  return -1;
};

/** Every section the files hold for the country (code: Europe's ISO alpha-2 or ISO alpha-3). */
function useSections(code: string) {
  const iso3 = code.length === 2 ? (ISO3[code] ?? code) : code;
  const iso2 = code.length === 2 ? code : (ISO2_OF[code] ?? null);
  const countries = useFile<CountriesFile>("countries");
  const europe = !!iso2 && !!countries?.countries.some((c) => c.iso === iso2);
  const us = iso3 === "USA";
  const world = useFile<WorldFile>("world");
  const t = useFile<TransitionFile>("transition");
  const gem = useFile<WorldPlantsFile>("worldPlants");
  const irena = useFile<IrenaFile>("irena");
  const ctrace = useFile<CtraceFile>("ctrace");
  const access = useFile<WorldStatsFile>("worldStats");
  const dc = useFile<DataCentresFile>("datacentres");
  const retail = useFile<RetailFile>("retail");
  const coverage = useFile<CoverageFile>("coverage");
  const offshore = useFile<OffshoreWindFile>(europe ? "offshoreWind" : null);
  const stats = useFile<StatsFile>(europe ? "stats" : null);
  const prices = useFile<PricesFile>(europe ? "prices" : null);
  const reference = useFile<ReferenceFile>(europe ? "reference" : null);
  const ets = useFile<EtsFile>(europe ? "ets" : null);
  const grid = useFile<GridFile>(europe ? "grid" : null);
  const gas = useFile<{ gas: Record<string, { date: string; full: number; in_storage_twh: number; capacity_twh: number }> }>(europe ? "dossier" : null);
  const usPlants = useFile<UsPlantsFile>(us ? "usPlants" : null);
  const usQueue = useFile<UsQueueFile>(us ? "usQueue" : null);
  const usSolar = useFile<UsSolarFile>(us ? "usSolar" : null);
  // profiles (scripts/build_profiles.py, build_population.py): sections keyed by ISO alpha-3
  const profiles = [
    useFile<ProfileFile>(europe ? "pfEurostat" : null),
    useFile<ProfileFile>("pfEi"),
    useFile<ProfileFile>("pfEdgar"),
    useFile<ProfileFile>("pfPopulation"),
    useFile<ProfileFile>(us ? "pfSeds" : null),
  ];

  const name = (europe ? countries?.countries.find((c) => c.iso === iso2)?.name : null) ?? t?.entities[iso3]?.name ?? world?.features.find((f) => f.properties.iso3 === iso3)?.properties.name ?? code;
  const ready = !!countries && !!t && !!gem && !!irena && !!ctrace && !!access && !!dc && !!retail && (!europe || (!!stats && !!prices && !!reference && !!ets && !!grid && !!gas && !!offshore)) && (!us || (!!usPlants && !!usQueue && !!usSolar));

  const sections = useMemo<Section[]>(() => {
    if (!ready) return [];
    const out: Section[] = [];
    // ---- generation in the newest year (Ember)
    const e = t?.entities[iso3];
    if (e && t) {
      const k = newestK(e.total_twh);
      if (k >= 0) {
        const total = e.total_twh[k] as number;
        const rows: Row[] = [["Total generation", total, "TWh", t.years[k]]];
        for (const [src, v] of Object.entries(e.series).sort((a, b) => (b[1][k] ?? 0) - (a[1][k] ?? 0)))
          if (v[k] != null && (v[k] as number) > 0) rows.push([src, v[k], "TWh", `${((100 * (v[k] as number)) / total).toFixed(1)} % of the total (computed)`]);
        rows.push(["Renewable share", e.renewables[k], "%", t.years[k]], ["Wind and solar share", e.wind_solar[k], "%", t.years[k]], ["Coal share", e.coal[k], "%", t.years[k]]);
        if (e.intensity[k] != null) rows.push(["Carbon intensity of generation", e.intensity[k], "gCO2/kWh", t.years[k]]);
        const k0 = t.years.indexOf(String(Number(t.years[k]) - 10));
        if (k0 >= 0 && e.renewables[k0] != null) rows.push([`Renewable share, ${t.years[k0]}`, e.renewables[k0], "%", "ten years earlier"]);
        if (k0 >= 0 && e.intensity[k0] != null) rows.push([`Carbon intensity, ${t.years[k0]}`, e.intensity[k0], "gCO2/kWh", "ten years earlier"]);
        out.push({ title: `Electricity generation, ${t.years[k]}`, source: "Ember yearly electricity data (CC BY 4.0); shares as published", rows });
      }
    }
    // ---- now (ENTSO-E, Europe)
    const now = europe && iso2 ? stats?.countries[iso2] : undefined;
    if (now) {
      const rows: Row[] = [["Load", Math.round(now.load_mw), "MW", now.ts.slice(0, 16).replace("T", " ") + " UTC"]];
      for (const [g, mw] of Object.entries(now.generation_mw).sort((a, b) => b[1] - a[1])) if (mw > 0) rows.push([`Generation, ${FUEL_LABEL[g] ?? g}`, Math.round(mw), "MW", ""]);
      if (now.renewable_share_of_generation != null) rows.push(["Renewable share of generation", now.renewable_share_of_generation, "%", "computed from the values above"]);
      for (const [zone, p] of Object.entries(stats?.day_ahead_prices ?? {})) if (p.country === iso2) rows.push([`Day-ahead price, ${zone}`, p.eur_mwh, "EUR/MWh", p.ts.slice(0, 16).replace("T", " ") + " UTC"]);
      out.push({ title: "Now", source: `ENTSO-E Transparency Platform${iso2 === "GB" ? " and Elexon" : ""}, newest complete interval (fetched ${stats?.fetched.slice(0, 16).replace("T", " ")} UTC)`, rows });
    }
    // ---- prices over twelve months (ENTSO-E)
    const zones = europe && prices ? Object.entries(prices.zones).filter(([, z]) => z.country === iso2) : [];
    if (zones.length && prices) {
      const rows: Row[] = [];
      for (const [id, z] of zones) {
        rows.push([`${id}: average`, z.mean, "EUR/MWh", ""], [`${id}: hours below zero`, z.negative_hours, "hours", ""]);
        rows.push([`${id}: lowest`, z.min[0], "EUR/MWh", z.min[1].slice(0, 16).replace("T", " ")], [`${id}: highest`, z.max[0], "EUR/MWh", z.max[1].slice(0, 16).replace("T", " ")]);
        if (z.solar_capture_rate != null) rows.push([`${id}: solar capture rate`, z.solar_capture_rate, "%", "solar-weighted price ÷ average"]);
        if (z.wind_capture_rate != null) rows.push([`${id}: wind capture rate`, z.wind_capture_rate, "%", "wind-weighted price ÷ average"]);
      }
      out.push({ title: `Day-ahead prices, ${prices.period[0]} to ${prices.period[1]}`, source: "ENTSO-E day-ahead prices and generation per bidding zone; statistics computed (scripts/build_prices.py)", rows });
    }
    // ---- what consumers pay
    if (retail) {
      const rows: Row[] = [];
      if (iso2)
        for (const s of Object.keys(SERIES_LABEL) as RetailSeries[]) {
          const n = newestOf(retail, retail.eu.series[s][iso2]);
          if (n) rows.push([`${SERIES_LABEL[s].title} (${SERIES_LABEL[s].band})`, n.v, "EUR/kWh", `${n.period}, all taxes${n.flag ? `, ${n.flag}` : ""}`]);
        }
      if (rows.length) out.push({ title: "What consumers pay", source: "Eurostat nrg_pc_204/205 (electricity), nrg_pc_202/203 (gas), half-yearly", rows });
      const usp = us ? retail.us?.price.US : undefined;
      if (usp && retail.us) {
        const m = retail.us.months;
        const r2: Row[] = [];
        for (const [kk, label] of [["RES", "Residential"], ["COM", "Commercial"], ["IND", "Industrial"]] as const) {
          const n = newestMonth(m, usp[kk]);
          if (n) r2.push([`Electricity, ${label.toLowerCase()}`, n.v, "US cents/kWh", n.month]);
        }
        if (r2.length) out.push({ title: "What consumers pay", source: "EIA retail sales (EIA-861M), US average", rows: r2 });
      }
    }
    // ---- installed capacity
    const ref = europe && iso2 ? reference?.capacity[iso2] : undefined;
    if (ref)
      out.push({
        title: `Installed capacity, ${ref.year}`,
        source: ref.source ?? "ENTSO-E A68",
        rows: Object.entries(ref.gw)
          .sort((a, b) => b[1] - a[1])
          .map(([g, v]) => [FUEL_LABEL[g] ?? g, v, "GW", ""] as Row),
      });
    const cap = irena?.capacity_mw[iso3];
    if (cap && irena) {
      const want = ["Total Renewable", "Solar photovoltaic", "Onshore wind energy", "Offshore wind energy", "Renewable hydropower", "Mixed hydropower", "Mechanical storage (Pumped hydro)", "Nuclear energy", "Total Non-Renewable"];
      const rows: Row[] = [];
      for (const label of want) {
        const id = Object.keys(irena.techs).find((x) => irena.techs[x] === label);
        const v = id ? cap[id] : undefined;
        const k = newestK(v);
        if (v && k >= 0) rows.push([label, v[k], "MW", irena.years[k]]);
      }
      if (rows.length) out.push({ title: "Installed capacity (IRENA)", source: `IRENA renewable capacity statistics (${irena.table})`, rows });
    }
    // ---- power plants (GEM; EIA in the US)
    const g = gem?.countries[iso3];
    if (g && gem) {
      const rows: Row[] = [];
      for (const st of ["operating", "construction", "planned"]) {
        const by = g[st];
        if (!by) continue;
        rows.push([STATUS_LABEL[st] ?? st, Math.round(sumOf(by)), "MW", "all types"]);
        for (const [ty, mw] of Object.entries(by).sort((a, b) => b[1] - a[1])) rows.push([`${STATUS_LABEL[st] ?? st}, ${PLANT_TYPE_LABEL[ty] ?? ty}`, Math.round(mw), "MW", ""]);
      }
      out.push({ title: "Power plants by status", source: "Global Energy Monitor, Global Integrated Power Tracker (CC BY 4.0); sums computed", rows });
    }
    if (us && usPlants && usQueue && usSolar) {
      const op = usPlants.totals.operating ?? {};
      out.push({
        title: "United States: generators, queue, solar arrays",
        source: `EIA-860M (${usPlants.release}), LBNL Queued Up (through ${usQueue.through}), USPVDB ${usSolar.release}`,
        rows: [
          ["Operating generators, net summer capacity", Math.round(sumOf(op)), "MW", "EIA-860M, 50 states and DC"],
          ["Active interconnection requests", Math.round(usQueue.total.active.reduce((a, b) => a + b, 0)), "MW", `${usQueue.total.active_n.toLocaleString("en-US")} requests; each part of a hybrid under its own type`],
          ["Large solar arrays", Math.round(usSolar.sites.reduce((a, s) => a + (s[2] ?? 0), 0)), "MW AC", `${usSolar.sites.length.toLocaleString("en-US")} arrays (USPVDB)`],
        ],
      });
    }
    // ---- emissions
    const etc = europe && iso2 ? ets?.countries[iso2] : undefined;
    const ct = ctrace ? ctrace.rows.filter((r) => r[2] === iso3) : [];
    if (etc || ct.length) {
      const rows: Row[] = [];
      if (etc && ets) rows.push(["EU ETS verified emissions", etc.t[etc.t.length - 1], "t CO2", `${ets.newest}; ${etc.n.toLocaleString("en-US")} installations (sum computed)`]);
      if (ct.length && ctrace) {
        rows.push(["Facilities over the Climate TRACE threshold", ct.length, "count", `${(ctrace.threshold_t / 1e6).toFixed(1)} Mt CO2e and more, ${ctrace.year}`]);
        rows.push(["Their emissions", ct.reduce((a, r) => a + r[5], 0), "t CO2e", "modelled, sum computed"]);
        for (const r of ct.slice(0, 5)) rows.push([r[3] || "unnamed", r[5], "t CO2e", "largest modelled emitters"]);
      }
      out.push({ title: "Emissions", source: `${etc ? `EU Union Registry (${ets?.snapshot}); ` : ""}${ct.length ? "Climate TRACE (modelled, CC BY 4.0)" : ""}`, rows });
    }
    // ---- grid, gas, offshore wind (Europe)
    if (europe && iso2 && grid) {
      const subs = grid.substations.filter((s) => s[3] === iso2);
      const byKv = new Map<number, number>();
      for (const s of subs) byKv.set(s[0], (byKv.get(s[0]) ?? 0) + 1);
      if (subs.length)
        out.push({
          title: "Transmission grid",
          source: "PyPSA-Eur network from OpenStreetMap (ODbL); counts computed",
          rows: [["Substations, 220 kV and more", subs.length, "count", ""], ...[...byKv.entries()].sort((a, b) => b[0] - a[0]).map(([kv, n]) => [`Substations, ${kv} kV`, n, "count", ""] as Row)],
        });
    }
    const gs = europe && iso2 ? gas?.gas[iso2] : undefined;
    if (gs)
      out.push({
        title: "Gas storage",
        source: "GIE AGSI+",
        rows: [
          ["Full", gs.full, "%", gs.date],
          ["In storage", gs.in_storage_twh, "TWh", gs.date],
          ["Working capacity", gs.capacity_twh, "TWh", ""],
        ],
      });
    const off = europe && offshore ? offshore.farms.filter((x) => x.iso3 === iso3 && x.polygons) : [];
    if (off.length && offshore) {
      const counts = new Map<string, number>();
      for (const x of off) counts.set(offshoreStatus(offshore, x), (counts.get(offshoreStatus(offshore, x)) ?? 0) + 1);
      out.push({
        title: "Offshore wind farm areas",
        source: "EMODnet Human Activities (CETMAR, CC BY 4.0); counts computed, capacity not summed (the source repeats some farms per phase)",
        rows: offshore.statuses.filter((s) => counts.has(s)).map((s) => [OFFSHORE_LABEL[s] ?? s, counts.get(s) ?? 0, "areas", ""] as Row),
      });
    }
    // ---- access, data centres
    const acc = access?.access[iso3];
    const ak = newestK(acc);
    const dcs = dc?.by_country[iso3];
    if ((acc && ak >= 0) || dcs) {
      const rows: Row[] = [];
      if (acc && ak >= 0 && access) rows.push(["People with access to electricity", acc[ak], "%", `${access.years[ak]} (World Bank)`]);
      if (dcs) rows.push(["Data centres mapped in OpenStreetMap", dcs, "count", "a subset that follows mapping effort"]);
      out.push({ title: "Access and data centres", source: "World Bank WDI EG.ELC.ACCS.ZS; OpenStreetMap (ODbL)", rows });
    }
    const cov = coverage && iso2 ? coverageRows(coverage, iso2) : [];
    if (cov.length)
      out.push({
        title: "What we have",
        source: `Coverage registry (data/coverage.yaml, docs/COVERAGE.md), checked ${coverage!.checked}`,
        rows: cov.map(([fam, g, what, checked]) => [fam, g, "", `${what}${checked ? ` (checked ${checked})` : ""}`] as Row),
      });
    for (const pf of profiles) {
      const rows = pf?.rows[iso3];
      if (pf && rows?.length) out.push({ title: pf.title, source: pf.source, rows });
    }
    return out;
  }, [ready, t, iso3, iso2, europe, us, stats, prices, retail, reference, irena, gem, usPlants, usQueue, usSolar, ets, ctrace, grid, gas, offshore, access, dc, coverage, ...profiles]); // eslint-disable-line react-hooks/exhaustive-deps
  return { name, sections, ready, iso3 };
}

const fmt = (v: number | string | null) => (v == null ? "–" : typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 1 ? 4 : 2 }) : v);
const csvCell = (v: unknown) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function Button({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} className="rounded-md border border-slate-300 px-2.5 py-1 text-[12px] text-slate-700 hover:bg-slate-100">
      {children}
    </button>
  );
}

export default function CountryReport({ code }: { code: string }) {
  const { name, sections, ready } = useSections(code);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && actions.openReport(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const today = new Date().toISOString().slice(0, 10);
  const download = () => {
    const rows = [["section", "item", "value", "unit", "note", "source"], ...sections.flatMap((s) => s.rows.map((r) => [s.title, ...r, s.source]))];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + rows.map((r) => r.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = `infraatlas-${code.toLowerCase()}-${today}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <div className="report fixed inset-0 z-[60] overflow-y-auto bg-white text-slate-800 print:static print:overflow-visible">
      <div className="mx-auto max-w-3xl px-5 py-6 print:max-w-none print:p-0">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">InfraAtlas · power system report</div>
            <h1 className="mt-1 text-[26px] font-light text-slate-900">{name}</h1>
            <div className="text-[11px] text-slate-500">
              {today} · every figure from a named source; computed values say how · {window.location.host}
            </div>
          </div>
          <div className="flex gap-1.5 print:hidden">
            <Button onClick={() => window.print()}>Print / PDF</Button>
            <Button onClick={download}>CSV</Button>
            <Button onClick={() => navigator.clipboard?.writeText(window.location.href)}>Copy link</Button>
            <Button onClick={() => actions.openReport(null)}>Close</Button>
          </div>
        </div>
        {!ready && <p className="mt-6 text-[13px] text-slate-500">Reading the files…</p>}
        {ready && !sections.length && <p className="mt-6 text-[13px] text-slate-500">The map&apos;s files hold nothing for this country.</p>}
        <div className="mt-2 columns-1 gap-6 md:columns-2 print:columns-2">
          {sections.map((s) => (
            <section key={s.title} className="mb-5 break-inside-avoid">
              <h2 className="mt-3 border-b border-slate-200 pb-1 text-[12px] font-semibold uppercase tracking-[0.14em] text-slate-700">{s.title}</h2>
              <table className="mt-1 w-full text-[11.5px]">
                <tbody>
                  {s.rows.map((r, i) => (
                    <tr key={i} className="align-baseline">
                      <td className="py-[2px] pr-2 text-slate-700">
                        {r[0]}
                        {r[3] && <div className="text-[9.5px] text-slate-400">{r[3]}</div>}
                      </td>
                      <td className="whitespace-nowrap py-[2px] text-right tabular-nums text-slate-900">
                        {fmt(r[1])} <span className="text-[10px] text-slate-500">{r[2]}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-1 text-[9.5px] leading-snug text-slate-500">Source: {s.source}</div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

/** The panel's button that opens the report. */
export function ReportButton({ code }: { code: string }) {
  const open = useApp((s) => s.report);
  return (
    <button
      onClick={() => actions.openReport(open ? null : code)}
      className="shrink-0 rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/10"
      title="A printable report of this country's figures, with CSV"
    >
      Report
    </button>
  );
}
