// The area dashboard: what the map's files hold inside an area. For countries, the records the
// files attribute to them (a country code or name on each record, or the file's own per-country
// totals: fast, and it counts the records without a position too); for a drawn polygon or a
// circle, the records whose position lies inside (point-in-polygon; lines by the midpoints of
// their segments). Each card says which and names its source. Nothing is estimated. The work runs
// after the panel has drawn, card by card, so the map stays responsive.

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { useFile } from "../app/data";
import type { CountriesFile, GasFile, GridFile, PlantsFile, ReferenceFile, StatsFile, WorldFile } from "../app/types";
import { inside, kmInside, km2Text, makeShape, pick, readGrid, type AreaShape } from "../lib/area";
import type { AtlasFile } from "../lib/atlas";
import type { HydrogenFile } from "../lib/coming";
import { gbSiteTotals, type ConnectFile } from "../lib/connect";
import { CONNECT_EU, connectEuKey, type ConnectEuFile } from "../lib/connectEu";
import type { ConstraintsFile, ProtectedFile } from "../lib/constraints";
import type { CtraceFile } from "../lib/ctrace";
import { EMBER_COLOR, EMBER_ORDER, FUEL_COLOR, FUEL_LABEL, FUEL_ORDER, power } from "../lib/energy";
import type { EtsFile } from "../lib/ets";
import type { EvChargersFile } from "../lib/evChargers";
import type { EvEuFile } from "../lib/evEu";
import { CLASS_LABEL, type GemPipesFile, type GemPointsFile } from "../lib/gem";
import type { GhgrpFile } from "../lib/ghgrp";
import type { MastrMuniFile } from "../lib/mastr";
import type { OffshoreWindFile } from "../lib/offshoreWind";
import { POP_URL } from "../lib/population";
import type { RegisterFile } from "../lib/registers";
import { rgbCss, type RGB } from "../lib/theme";
import { EUROPE_ISO3, ISO3, type TransitionFile } from "../lib/transition";
import { US_TYPE_COLOR, US_TYPE_LABEL, usTester, type UsPlantsFile, type UsStatesFile, type UsTurbinesFile } from "../lib/us";
import type { UsSolarFile } from "../lib/usSolar";
import type { DataCentresFile } from "../lib/world";
import { PLANT_TYPE_COLOR, PLANT_TYPE_LABEL, type WorldPlantsFile } from "../lib/worldPlants";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const GREY: RGB = [150, 154, 166];
const EUROPE_BOX: [number, number, number, number] = [-32, 26, 46, 72];
const US_BOX: [number, number, number, number] = [-170, 17, -64, 72];
/** Above this size the grids read by range request (people, resources, flood) are not read. */
const GRID_MAX_KM2 = 2_000_000;
const overlaps = (a: [number, number, number, number], b: [number, number, number, number]) => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
const ISO2_OF_3: Record<string, string> = { ...Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a])), CYP: "CY", MLT: "MT" };
const int = (v: number) => Math.round(v).toLocaleString("en-US");
const num = (v: number, d = 1) => (v >= 100 ? int(v) : v.toFixed(d));
const sum = (v: number[]) => v.reduce((a, b) => a + b, 0);
const mt = (t: number) => `${(t / 1e6).toFixed(t >= 1e8 ? 0 : 2)} Mt`;
// GEM's country names that differ from the world outlines'
const GEM_NAMES: Record<string, string[]> = {
  USA: ["united states"],
  GBR: ["united kingdom"],
  CZE: ["czech republic", "czechia"],
  RUS: ["russia"],
  KOR: ["south korea"],
  TUR: ["türkiye", "turkey"],
  COD: ["dr congo"],
  VNM: ["vietnam", "viet nam"],
};

// ---------------------------------------------------------------- small pieces

function Tile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
      <div className={`text-[9.5px] uppercase tracking-[0.14em] ${muted}`}>{label}</div>
      <div className="mt-0.5 text-[17px] font-light tabular-nums text-slate-50">{value}</div>
      {sub && <div className={`text-[10px] leading-snug ${muted}`}>{sub}</div>}
    </div>
  );
}
const Tiles = ({ children }: { children: ReactNode }) => <div className="grid grid-cols-2 gap-1.5">{children}</div>;

export interface Bar {
  key: string;
  label: string;
  value: number;
  color?: RGB;
  text?: string;
}
/** Thin horizontal bars: magnitude by category, the value in text colour beside each. */
export function Bars({ rows, unit }: { rows: Bar[]; unit?: string }) {
  const top = Math.max(1e-9, ...rows.map((r) => r.value));
  return (
    <div className="space-y-[5px]">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2 text-[11px]" title={`${r.label}: ${r.text ?? `${num(r.value)}${unit ? ` ${unit}` : ""}`}`}>
          <span className="w-[104px] shrink-0 truncate text-slate-300">{r.label}</span>
          <span className="relative h-[7px] flex-1 rounded-[4px] bg-white/[0.05]">
            <span className="absolute inset-y-0 left-0 rounded-[4px]" style={{ width: `${Math.max(1.5, (100 * r.value) / top)}%`, background: rgbCss(r.color ?? GREY) }} />
          </span>
          <span className="w-[74px] shrink-0 text-right tabular-nums text-slate-200">{r.text ?? `${num(r.value)}${unit ? ` ${unit}` : ""}`}</span>
        </div>
      ))}
    </div>
  );
}
const Head = ({ children }: { children: ReactNode }) => <div className={`mb-1 mt-2.5 text-[9.5px] uppercase tracking-[0.16em] ${muted}`}>{children}</div>;
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;
const Loading = ({ what }: { what: string }) => <div className={`text-[11px] ${muted}`}>Counting {what}…</div>;
const Line = ({ k, v, sub }: { k: ReactNode; v: ReactNode; sub?: ReactNode }) => (
  <div className="flex items-baseline justify-between gap-3 py-[3px] text-[11.5px]">
    <span className="min-w-0 truncate text-slate-300">{k}</span>
    <span className="shrink-0 text-right tabular-nums text-slate-100">
      {v}
      {sub && <span className={`ml-1.5 text-[10px] ${muted}`}>{sub}</span>}
    </span>
  </div>
);

// ---------------------------------------------------------------- the area's terms

interface Scope {
  s: AreaShape;
  /** countries: by the records' country; else by position */
  byCountry: boolean;
  iso3: Set<string>;
  iso2: Set<string>;
  europe: boolean;
  us: boolean;
  /** a country name (lower case) belongs to the area */
  hasName: (name: string | null | undefined) => boolean;
}

function useScope(s: AreaShape): Scope {
  const world = useFile<WorldFile>(s.countries ? "world" : null);
  return useMemo(() => {
    const byCountry = !!s.countries;
    const iso3 = new Set(s.countries ?? []);
    const iso2 = new Set([...iso3].map((c) => ISO2_OF_3[c]).filter(Boolean));
    const names = new Set<string>();
    for (const f of world?.features ?? []) if (iso3.has(f.properties.iso3)) names.add(f.properties.name.toLowerCase());
    for (const c of iso3) for (const n of GEM_NAMES[c] ?? []) names.add(n);
    const europe = byCountry ? [...iso3].some((c) => EUROPE_ISO3.has(c) || c === "CYP" || c === "MLT") : overlaps(s.bbox, EUROPE_BOX);
    const us = byCountry ? iso3.has("USA") : overlaps(s.bbox, US_BOX);
    return { s, byCountry, iso3, iso2, europe, us, hasName: (n) => !!n && n.split(/[;,]\s*/).some((x) => names.has(x.toLowerCase())) };
  }, [s, world]);
}

/** Work done after the panel has drawn (one task per card), cached by key. */
function useLater<T>(key: string | null, run: () => T): T | null {
  const [st, setSt] = useState<{ key: string; v: T } | null>(null);
  useEffect(() => {
    if (!key) return;
    let live = true;
    const t = setTimeout(() => {
      const v = run();
      if (live) setSt({ key, v });
    }, 30);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return st && st.key === key ? st.v : null;
}
type Async<T> = { key: string; v: T | null; failed: boolean };
function useAsync<T>(key: string | null, run: () => Promise<T>): Async<T> {
  const [st, setSt] = useState<Async<T>>({ key: "", v: null, failed: false });
  useEffect(() => {
    if (!key) return;
    let live = true;
    setSt({ key, v: null, failed: false });
    run()
      .then((v) => live && setSt({ key, v, failed: false }))
      .catch(() => live && setSt({ key, v: null, failed: true }));
    return () => {
      live = false;
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return st.key === key ? st : { key: key ?? "", v: null, failed: false };
}
/** Does the area reach a European country (ISO alpha-2)? Its list, or the box of its outline. */
function useReaches(sc: Scope): (cc: string) => boolean {
  const countries = useFile<CountriesFile>(sc.byCountry ? null : "countries");
  const boxes = useMemo(() => {
    const m = new Map<string, [number, number, number, number]>();
    for (const c of countries?.countries ?? []) {
      const b: [number, number, number, number] = [180, 90, -180, -90];
      for (const poly of c.polygons)
        for (let i = 0; i < poly[0].length; i += 2) {
          b[0] = Math.min(b[0], poly[0][i]);
          b[2] = Math.max(b[2], poly[0][i]);
          b[1] = Math.min(b[1], poly[0][i + 1]);
          b[3] = Math.max(b[3], poly[0][i + 1]);
        }
      m.set(c.iso, b);
    }
    return m;
  }, [countries]);
  return (cc: string) => (sc.byCountry ? sc.iso2.has(cc) : !!boxes.get(cc) && overlaps(sc.s.bbox, boxes.get(cc)!));
}
const how = (sc: Scope) => (sc.byCountry ? "the records the file gives to these countries" : "the records placed inside the area");
const fkey = (...f: unknown[]) => f.map((x) => (x ? 1 : 0)).join("");

// ---------------------------------------------------------------- the area: size, people, resources

export function AreaOverviewCard({ s }: { s: AreaShape }) {
  const small = s.km2 <= GRID_MAX_KM2;
  const atlas = useFile<AtlasFile>(small ? "atlas" : null);
  const people = useAsync(small ? `pop|${s.key}` : null, async () => {
    let n = 0;
    const r = await readGrid({ url: POP_URL, bytes: 4, width: 3600, height: 1800, origin: [-180, 90], cell: 0.1 }, s, (v, off) => (n += v.getInt32(off, true)), 400);
    return { people: n, cells: r.cells, whole: r.step === 1 };
  });
  const res = useAsync(atlas ? `atlas|${s.key}` : null, async () => {
    const mean = async (k: "pvout" | "wind") => {
      const l = atlas![k].lookup;
      let t = 0;
      let n = 0;
      const r = await readGrid({ url: l.url, bytes: 2, width: l.width, height: l.height, origin: l.origin, cell: l.cell_deg }, s, (v, off) => {
        const x = v.getInt16(off, true);
        if (x !== l.nodata) {
          t += x / atlas![k].scale;
          n++;
        }
      }, 60);
      return { mean: n ? t / n : null, cells: n, step: r.step, unit: atlas![k].unit };
    };
    const [pv, wind] = await Promise.all([mean("pvout"), mean("wind")]);
    return { pv, wind };
  });
  const p = people.v;
  const big = "–";
  return (
    <Card title="The area" note={s.kind === "countries" ? "country outlines" : s.kind === "circle" ? "a circle" : "drawn on the map"} accent={[120, 190, 255]}>
      <Tiles>
        <Tile label="Size" value={km2Text(s.km2)} sub="computed from the outline" />
        <Tile
          label="People"
          value={!small ? big : people.failed ? "–" : p ? (p.whole ? (p.people >= 1e6 ? `${(p.people / 1e6).toFixed(2)} M` : int(p.people)) : "–") : "…"}
          sub={!small ? "pick an area under 2 million km²" : p ? (p.whole ? `${int(p.people / Math.max(1, s.km2))} per km² · GHSL 2025` : "area too tall to sum") : "GHSL 2025"}
        />
        <Tile
          label="Solar resource"
          value={!small ? big : res.v?.pv.mean != null ? num(res.v.pv.mean, 2) : res.failed ? "–" : "…"}
          sub={res.v ? `${res.v.pv.unit} · mean of ${int(res.v.pv.cells)} cells${res.v.pv.step > 1 ? `, every ${res.v.pv.step}th` : ""}` : "Global Solar Atlas"}
        />
        <Tile
          label="Wind at 100 m"
          value={!small ? big : res.v?.wind.mean != null ? num(res.v.wind.mean, 2) : res.failed ? "–" : "…"}
          sub={res.v ? `${res.v.wind.unit} · mean of ${int(res.v.wind.cells)} cells${res.v.wind.step > 1 ? `, every ${res.v.wind.step}th` : ""}` : "Global Wind Atlas"}
        />
      </Tiles>
      <Note>
        People: the sum of the GHSL 0.1° cells whose centre lies inside (computed). Resources: the mean of the atlases' 0.1° lookup cells inside (computed; every n-th row and column for larger areas, as
        said), long-term averages. {!small && "These grids are read for areas under 2 million km²: draw a smaller area or pick a country."}
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- electricity (countries)

export function AreaElectricityCard({ s }: { s: AreaShape }) {
  const stats = useFile<StatsFile>(s.countries ? "stats" : null);
  const ref = useFile<ReferenceFile>(s.countries ? "reference" : null);
  const t = useFile<TransitionFile>(s.countries ? "transition" : null);
  if (!s.countries) return null;
  const codes = s.countries;
  const iso2s = codes.map((c) => ISO2_OF_3[c]).filter(Boolean);
  const now = stats ? iso2s.map((c) => [c, stats.countries[c]] as const).filter(([, p]) => !!p) : [];
  const gen: Record<string, number> = {};
  let load = 0;
  let green = 0;
  let total = 0;
  for (const [, p] of now) {
    load += p.load_mw;
    const g = sum(Object.values(p.generation_mw));
    total += g;
    if (p.renewable_share_of_generation != null) green += (p.renewable_share_of_generation / 100) * g;
    for (const [k, v] of Object.entries(p.generation_mw)) gen[k] = (gen[k] ?? 0) + v;
  }
  const cap: Record<string, number> = {};
  const capOf = ref ? iso2s.filter((c) => ref.capacity[c]) : [];
  for (const c of capOf) for (const [k, v] of Object.entries(ref!.capacity[c].gw)) cap[k] = (cap[k] ?? 0) + v;
  const ents = t ? codes.map((c) => t.entities[c]).filter(Boolean) : [];
  const yk = t && ents.length ? [...t.years.keys()].reverse().find((k) => ents.every((e) => e.total_twh[k] != null)) : undefined;
  const ember: Record<string, number> = {};
  if (t && yk != null) for (const e of ents) for (const [k, ser] of Object.entries(e.series)) ember[k] = (ember[k] ?? 0) + (ser[yk] ?? 0);
  if (!now.length && !capOf.length && !ents.length) return null;
  return (
    <Card title="Electricity" note={codes.length > 1 ? `sums over the countries with data` : undefined} accent={[255, 214, 72]}>
      {now.length > 0 && (
        <>
          <Tiles>
            <Tile label="Demand now" value={power(load)} sub={`sum of ${now.length} ${now.length === 1 ? "country" : "countries"} · ENTSO-E`} />
            <Tile label="Renewable share now" value={total > 0 ? `${((100 * green) / total).toFixed(1)} %` : "–"} sub="each country's share × its generation, summed" />
          </Tiles>
          <Head>Generation now by source</Head>
          <Bars rows={FUEL_ORDER.filter((k) => gen[k] > 0).map((k) => ({ key: k, label: FUEL_LABEL[k] ?? k, value: gen[k], color: FUEL_COLOR[k], text: power(gen[k]) }))} />
          <Note>ENTSO-E, each country's newest complete interval ({[...new Set(now.map(([, p]) => p.ts.slice(11, 16)))].slice(0, 4).join(", ")} UTC).</Note>
        </>
      )}
      {capOf.length > 0 && (
        <>
          <Head>Installed capacity</Head>
          <Bars rows={Object.entries(cap).sort((a, b) => b[1] - a[1]).slice(0, 9).map(([k, v]) => ({ key: k, label: FUEL_LABEL[k] ?? k, value: v, color: FUEL_COLOR[k], text: `${v.toFixed(1)} GW` }))} />
          <Note>ENTSO-E installed capacity per production type (A68), summed over {capOf.length} {capOf.length === 1 ? "country" : "countries"}.</Note>
        </>
      )}
      {t && yk != null && sum(Object.values(ember)) > 0 && (
        <>
          <Head>Generation in {t.years[yk]}</Head>
          <Bars rows={EMBER_ORDER.filter((k) => (ember[k] ?? 0) > 0).map((k) => ({ key: k, label: k, value: ember[k], color: EMBER_COLOR[k], text: `${num(ember[k])} TWh` }))} />
          <Note>Ember yearly data, TWh, summed over {ents.length} {ents.length === 1 ? "country" : "countries"} (the newest year all of them have).</Note>
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- power plants

interface PlantSums {
  op: Bar[];
  coming: Bar[];
  opMw: number;
  buildMw: number;
  planMw: number;
  largest: { name: string; mw: number; label: string }[];
}
function addBar(m: Map<string, Bar>, label: string, color: RGB, mw: number) {
  const b = m.get(label) ?? { key: label, label, value: 0, color };
  b.value += mw;
  m.set(label, b);
}
const bars = (m: Map<string, Bar>) => [...m.values()].sort((a, b) => b.value - a.value).map((b) => ({ ...b, text: power(b.value) }));

export function AreaPlantsCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const eu = useFile<PlantsFile>(sc.europe ? "plants" : null);
  const countries = useFile<CountriesFile>(sc.europe ? "countries" : null);
  const usp = useFile<UsPlantsFile>(sc.us ? "usPlants" : null);
  const states = useFile<UsStatesFile>(sc.us && !sc.byCountry ? "usStates" : null);
  const gem = useFile<WorldPlantsFile>("worldPlants");
  const ready = !!gem && (!sc.europe || (!!eu && !!countries)) && (!sc.us || (!!usp && (sc.byCountry || !!states)));
  const data = useLater<PlantSums>(ready ? `plants|${s.key}` : null, () => {
    const op = new Map<string, Bar>();
    const coming = new Map<string, Bar>();
    let opMw = 0;
    let buildMw = 0;
    let planMw = 0;
    const largest: PlantSums["largest"] = [];
    const euIso = new Set(countries?.countries.map((c) => c.iso) ?? []);
    // Europe's file: operating units of 20 MW and more
    if (eu) {
      const rows = sc.byCountry ? eu.plants.filter((p) => sc.iso2.has(p[4])) : pick(eu.plants, (x) => [x[2], x[3]], s);
      for (const p of rows) {
        addBar(op, FUEL_LABEL[eu.groups[p[0]]] ?? eu.groups[p[0]], FUEL_COLOR[eu.groups[p[0]]] ?? GREY, p[1]);
        opMw += p[1];
        largest.push({ name: p[5], mw: p[1], label: FUEL_LABEL[eu.groups[p[0]]] ?? eu.groups[p[0]] });
      }
    }
    // the EIA's file: every US generator of 1 MW and more, every status
    if (usp) {
      const rows = sc.byCountry ? usp.points : pick(usp.points, (x) => [x[0], x[1]], s);
      for (const p of rows) {
        const st = usp.statuses[p[3]];
        const label = US_TYPE_LABEL[usp.types[p[2]]] ?? usp.types[p[2]];
        const color = US_TYPE_COLOR[usp.types[p[2]]] ?? GREY;
        if (st === "operating") {
          addBar(op, label, color, p[4]);
          opMw += p[4];
          const name = usp.plants[p[6]]?.[0];
          if (name) largest.push({ name, mw: p[4], label });
        } else if (st === "construction" || st === "planned") {
          addBar(coming, label, color, p[4]);
          if (st === "construction") buildMw += p[4];
          else planMw += p[4];
        }
      }
    }
    // Global Energy Monitor elsewhere, and building or planned in Europe
    if (gem) {
      if (sc.byCountry) {
        for (const c of sc.iso3) {
          if (c === "USA") continue;
          const byStatus = gem.countries[c] ?? {};
          for (const [st, types] of Object.entries(byStatus)) {
            if (st === "operating" && euIso.has(ISO2_OF_3[c] ?? "")) continue;
            for (const [t, mw] of Object.entries(types)) {
              const label = PLANT_TYPE_LABEL[t] ?? t;
              const color = PLANT_TYPE_COLOR[t] ?? GREY;
              if (st === "operating") {
                addBar(op, label, color, mw);
                opMw += mw;
              } else if (st === "construction" || st === "planned") {
                addBar(coming, label, color, mw);
                if (st === "construction") buildMw += mw;
                else planMw += mw;
              }
            }
          }
        }
      } else {
        const euShape = sc.europe && countries ? makeShape("countries", "europe", "Europe", countries.countries.flatMap((c) => c.polygons)) : null;
        const usTest = states ? usTester(states) : null;
        for (const p of pick(gem.points, (x) => [x[0], x[1]], s)) {
          const st = gem.statuses[p[3]];
          if (st !== "operating" && st !== "construction" && st !== "planned") continue;
          if (usTest && (p[0] < -64 || p[0] > 170) && p[1] > 17 && usTest(p[0], p[1])) continue;
          if (st === "operating" && euShape && inside(euShape, p[0], p[1])) continue;
          const label = PLANT_TYPE_LABEL[gem.types[p[2]]] ?? gem.types[p[2]];
          const color = PLANT_TYPE_COLOR[gem.types[p[2]]] ?? GREY;
          if (st === "operating") {
            addBar(op, label, color, p[4]);
            opMw += p[4];
          } else {
            addBar(coming, label, color, p[4]);
            if (st === "construction") buildMw += p[4];
            else planMw += p[4];
          }
        }
      }
    }
    return { op: bars(op), coming: bars(coming), opMw, buildMw, planMw, largest: largest.sort((a, b) => b.mw - a.mw).slice(0, 5) };
  });
  if (!data)
    return (
      <Card title="Power plants" accent={[255, 128, 72]}>
        <Loading what="power plants" />
      </Card>
    );
  const sources = [sc.europe && "Europe, operating: powerplantmatching (units of 20 MW and more)", sc.us && `the US: EIA-860M (${usp?.release ?? ""})`, "elsewhere, and building or planned outside the US: Global Energy Monitor"].filter(Boolean).join("; ");
  return (
    <Card title="Power plants" accent={[255, 128, 72]}>
      <Tiles>
        <Tile label="Operating" value={power(data.opMw)} sub="capacity" />
        <Tile label="Building · planned" value={`${power(data.buildMw)} · ${power(data.planMw)}`} sub="capacity" />
      </Tiles>
      {data.op.length > 0 && (
        <>
          <Head>Operating, by type</Head>
          <Bars rows={data.op.slice(0, 9)} />
        </>
      )}
      {data.coming.length > 0 && (
        <>
          <Head>Under construction and planned, by type</Head>
          <Bars rows={data.coming.slice(0, 7)} />
        </>
      )}
      {data.largest.length > 0 && (
        <>
          <Head>Largest operating</Head>
          {data.largest.map((p, i) => (
            <Line key={i} k={p.name} v={power(p.mw)} sub={p.label} />
          ))}
        </>
      )}
      <Note>
        Capacity summed over {how(sc)} (computed); {sc.byCountry ? "Global Energy Monitor's own per-country totals" : "map points"}. Sources: {sources}.
        {sc.europe ? " In Europe's file units under 20 MW (most wind and solar) are left out: the Electricity card gives installed capacity." : ""}
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- the grid

const BANDS: [number, string][] = [
  [380, "380 kV and more"],
  [275, "275–379 kV"],
  [220, "220–274 kV"],
  [0, "under 220 kV"],
];

export function AreaGridCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const grid = useFile<GridFile>(sc.europe ? "grid" : null);
  const data = useLater(grid ? `grid|${s.key}` : null, () => {
    const km: Record<string, number> = {};
    for (const [kv, path] of grid!.lines) {
      const band = BANDS.find(([min]) => kv >= min)![1];
      const k = kmInside(path, s);
      if (k > 0) km[band] = (km[band] ?? 0) + k;
    }
    const hvdc = sum(grid!.links.map(([, path]) => kmInside(path, s)));
    const subs = sc.byCountry ? grid!.substations.filter((x) => sc.iso2.has(x[3])) : pick(grid!.substations, (x) => [x[1], x[2]], s);
    return { km, hvdc, subs: subs.length };
  });
  if (!sc.europe)
    return (
      <Card title="Transmission grid" accent={[236, 178, 120]}>
        <Note>Line lengths are counted from Europe's grid file. Outside Europe the lines come from the map's tiles: "Check a site" reads them around a place.</Note>
      </Card>
    );
  if (!data)
    return (
      <Card title="Transmission grid" accent={[236, 178, 120]}>
        <Loading what="lines and substations" />
      </Card>
    );
  const total = sum(Object.values(data.km));
  return (
    <Card title="Transmission grid" note="Europe" accent={[236, 178, 120]}>
      <Tiles>
        <Tile label="AC lines" value={`${int(total)} km`} sub="220 kV and more" />
        <Tile label="Substations" value={int(data.subs)} sub={data.hvdc > 0 ? `HVDC links ${int(data.hvdc)} km` : "220 kV and more"} />
      </Tiles>
      {total > 0 && (
        <>
          <Head>Line length by voltage</Head>
          <Bars rows={BANDS.filter(([, b]) => data.km[b]).map(([min, b]) => ({ key: b, label: b, value: data.km[b], color: min >= 380 ? [236, 178, 120] : min >= 275 ? [214, 150, 96] : [176, 120, 82], text: `${int(data.km[b])} km` }))} />
        </>
      )}
      <Note>PyPSA-Eur's network from OpenStreetMap: length of the line segments whose midpoint lies inside (computed; a line's circuits count once). Substations of 220 kV and more: {how(sc)}.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- room to connect

export function AreaCapacityCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const reaches = useReaches(sc);
  const connect = useFile<ConnectFile>(sc.europe && reaches("GB") ? "connect" : null);
  const euFiles = CONNECT_EU.map((id) => [id, useFile<ConnectEuFile>(sc.europe && reaches(id.slice(0, 2)) ? connectEuKey(id) : null)] as const); // eslint-disable-line react-hooks/rules-of-hooks
  const data = useLater(sc.europe ? `cap|${s.key}|${fkey(connect, ...euFiles.map(([, f]) => f))}` : null, () => {
    const gb = connect ? (sc.byCountry ? gbSiteTotals(connect.gb) : pick(gbSiteTotals(connect.gb), (t) => [t.site[1] as number, t.site[2] as number], s)) : [];
    const eu = euFiles.flatMap(([id, f]) => (f ? [{ id, f, n: sc.byCountry ? f.points.length + f.areas.length : pick(f.points, (p) => [p[1], p[2]], s).length }] : [])).filter((x) => x.n);
    return { gb, eu };
  });
  if (!sc.europe || !data || (!data.gb.length && !data.eu.length)) return null;
  return (
    <Card title="Room to connect" accent={[206, 138, 72]}>
      {data.gb.length > 0 && connect && (
        <>
          <Tiles>
            <Tile label="GB: waiting to connect" value={power(sum(data.gb.map((g) => g.mw)))} sub={`${data.gb.length} transmission sites · NESO TEC register`} />
          </Tiles>
          <Head>Waiting, by type</Head>
          <Bars rows={connect.gb.types.map((t, i) => ({ key: t, label: t, value: sum(data.gb.map((g) => g.byType[i])) })).filter((b) => b.value > 0).sort((a, b) => b.value - a.value).slice(0, 7).map((b) => ({ ...b, text: power(b.value) }))} />
        </>
      )}
      {data.eu.map(({ id, f, n }) => (
        <Line key={id} k={`${id}: points and areas published`} v={int(n)} sub={f.source} />
      ))}
      <Note>Each operator's own map or register, as published; the values per point stay on the map (Grid capacity layer). GB: MW of projects not yet connected, summed per site (computed).</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- every unit in national registers

const REGISTERS = ["GB", "FR", "DK", "SE", "IE", "BE", "FI", "PT", "CZ"] as const;

export function AreaRegistersCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const reaches = useReaches(sc);
  const files = REGISTERS.map((cc) => [cc, useFile<RegisterFile>(sc.europe && reaches(cc) ? `register${cc}` : null)] as const); // eslint-disable-line react-hooks/rules-of-hooks
  const muni = useFile<MastrMuniFile>(sc.europe && reaches("DE") ? "mastrMuni" : null);
  const turbines = useFile<UsTurbinesFile>(sc.us ? "usTurbines" : null);
  const solar = useFile<UsSolarFile>(sc.us ? "usSolar" : null);
  const rows = useLater(`reg|${s.key}|${fkey(muni, turbines, solar, ...files.map(([, f]) => f))}`, () => {
    const out: { key: string; label: string; n: number; mw: number; src: string }[] = [];
    for (const [cc, f] of files) {
      if (!f) continue;
      const by = new Map<string, [number, number]>();
      if (sc.byCountry) for (const [g, [n, mw]] of Object.entries(f.totals.operating ?? {})) by.set(g, [n, mw]);
      else
        for (const p of pick(f.points, (x) => [x[1], x[2]], s)) {
          const b = by.get(p[3]) ?? [0, 0];
          b[0]++;
          b[1] += p[4] ?? 0;
          by.set(p[3], b);
        }
      for (const [g, [n, mw]] of by) if (n) out.push({ key: `${cc}${g}`, label: `${cc} ${g.replace(/_/g, " ")}`, n, mw, src: f.source });
    }
    if (muni) {
      if (sc.byCountry) for (const [t, [n, mw]] of Object.entries(muni.national)) out.push({ key: `DE${t}`, label: `DE ${t}`, n, mw, src: muni.source });
      else {
        const gs = muni.gemeinden.filter((g) => g.label && inside(s, g.label[0], g.label[1]));
        muni.techs.forEach((t, i) => {
          const n = sum(gs.map((g) => g.n[i] ?? 0));
          if (n > 0) out.push({ key: `DE${t}`, label: `DE ${t}`, n, mw: sum(gs.map((g) => g.mw[i] ?? 0)), src: `${muni.source}, municipalities by their label point` });
        });
      }
    }
    if (turbines) {
      if (sc.byCountry) out.push({ key: "USwind", label: "US wind turbines", n: turbines.count, mw: turbines.mw, src: turbines.source });
      else {
        let n = 0;
        let kw = 0;
        for (let i = 0; i < turbines.lon.length; i++)
          if (inside(s, turbines.lon[i], turbines.lat[i])) {
            n++;
            kw += turbines.kw[i] ?? 0;
          }
        if (n) out.push({ key: "USwind", label: "US wind turbines", n, mw: kw / 1000, src: turbines.source });
      }
    }
    if (solar) {
      const sites = sc.byCountry ? solar.sites : pick(solar.sites, (x) => [x[0] ?? 999, x[1] ?? 999], s);
      if (sites.length) out.push({ key: "USsolar", label: "US solar farms (MW AC)", n: sites.length, mw: sum(sites.map((x) => x[2] ?? 0)), src: solar.source });
    }
    return out.sort((a, b) => b.mw - a.mw);
  });
  if (!rows || !rows.length) return null;
  return (
    <Card title="Every unit (national registers)" accent={[255, 214, 72]}>
      <Bars rows={rows.slice(0, 12).map((x) => ({ key: x.key, label: x.label, value: x.mw, color: [255, 214, 72], text: `${power(x.mw)} · ${int(x.n)}` }))} />
      <Note>
        MW and units: {sc.byCountry ? "each register's own operating totals" : "summed over the entries inside the area (computed)"}; a register's own groups. Sources: {[...new Set(rows.map((x) => x.src))].join("; ")}.
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- demand and industry, fuels

const GEM_INDUSTRY: [string, string][] = [
  ["gemSteel", "Steel plants"],
  ["gemCement", "Cement plants"],
  ["gemChemicals", "Chemical plants"],
  ["gemIronOre", "Iron ore mines"],
];
const GEM_FUELS: [string, string][] = [
  ["gemLng", "LNG terminals"],
  ["gemCoalTerminals", "Coal ports"],
  ["gemFields", "Oil and gas fields"],
  ["gemCoalMines", "Coal mines"],
  ["gemMethane", "Methane plumes"],
];

function useGemRows(list: [string, string][], sc: Scope) {
  const files = list.map(([k]) => useFile<GemPointsFile>(k)); // eslint-disable-line react-hooks/rules-of-hooks
  return useLater(`gem${list[0][0]}|${sc.s.key}|${fkey(...files)}`, () =>
    list.flatMap(([, label], i) => {
      const f = files[i];
      if (!f) return [];
      const pts = sc.byCountry ? f.points.filter((p) => sc.hasName(p[8])) : pick(f.points, (p) => [p[0], p[1]], sc.s);
      const op = pts.filter((p) => CLASS_LABEL[p[3]] === "operating");
      return [{ label, n: pts.length, op: op.length, size: sum(op.map((p) => p[4] ?? 0)), unit: f.unit }];
    }),
  );
}

export function AreaDemandCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const dc = useFile<DataCentresFile>("datacentres");
  const evEu = useFile<EvEuFile>(sc.europe ? "evEu" : null);
  const evUs = useFile<EvChargersFile>(sc.us ? "evChargers" : null);
  const h2 = useFile<HydrogenFile>(sc.europe ? "hydrogen" : null);
  const gem = useGemRows(GEM_INDUSTRY, sc);
  const d = useLater(`dem|${s.key}|${fkey(dc, evEu, evUs, h2)}`, () => ({
    dcs: dc ? (sc.byCountry ? sum([...sc.iso3].map((c) => dc.by_country[c] ?? 0)) : pick(dc.points, (p) => [p[0], p[1]], s).length) : null,
    ev: evEu ? sum(Object.entries(evEu.cells).flatMap(([cc, cells]) => (sc.byCountry ? (sc.iso2.has(cc) ? cells.map((c) => c[2]) : []) : pick(cells, (c) => [c[0], c[1]], s).map((c) => c[2])))) : null,
    us: evUs ? (sc.byCountry ? evUs.points : pick(evUs.points, (p) => [p[0], p[1]], s)) : null,
    h: h2 ? (sc.byCountry ? h2.projects.filter((p) => !!p[2] && sc.iso3.has(p[2])) : pick(h2.projects, (p) => [p[8], p[9]], s)) : null,
  }));
  return (
    <Card title="Demand and industry" accent={[196, 150, 255]}>
      <Tiles>
        <Tile label="Data centres" value={d?.dcs != null ? int(d.dcs) : "…"} sub="mapped in OpenStreetMap" />
        {sc.europe && <Tile label="EV charging points" value={d?.ev != null ? int(d.ev) : "…"} sub="registers, OpenStreetMap" />}
        {sc.us && <Tile label="US DC fast stations" value={d?.us ? int(d.us.length) : "…"} sub={d?.us ? `${int(sum(d.us.map((p) => p[2])))} ports · NREL AFDC` : "NREL AFDC"} />}
        {sc.europe && h2 && <Tile label="Hydrogen projects" value={d?.h ? int(d.h.length) : "…"} sub={d?.h ? `${power(sum(d.h.map((p) => p[4] ?? 0)))} electrolysis where given · EHO` : "EHO"} />}
      </Tiles>
      {gem?.some((g) => g.n > 0) && (
        <>
          <Head>Heavy industry (Global Energy Monitor)</Head>
          {gem
            .filter((g) => g.n > 0)
            .map((g) => (
              <Line key={g.label} k={g.label} v={int(g.n)} sub={g.op && g.size > 0 ? `${int(g.op)} operating, ${num(g.size)} ${g.unit}` : `${int(g.op)} operating`} />
            ))}
        </>
      )}
      <Note>Counts and sums over {how(sc)} (computed). EV charging in Europe: points per 0.1° cell{sc.byCountry ? " of these countries" : ", cells whose centre lies inside"}.</Note>
    </Card>
  );
}

export function AreaEmissionsCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const ets = useFile<EtsFile>(sc.europe ? "ets" : null);
  const ghg = useFile<GhgrpFile>(sc.us ? "ghgrp" : null);
  const ct = useFile<CtraceFile>("ctrace");
  const d = useLater(`em|${s.key}|${fkey(ets, ghg, ct)}`, () => {
    const k = ets ? ets.years.indexOf(ets.newest) : -1;
    const etsRows = ets ? (sc.byCountry ? ets.rows.filter((r) => sc.iso2.has(r[0])) : pick(ets.rows, (x) => [x[5] ?? 999, x[6] ?? 999], s)) : [];
    const etsT = ets ? (sc.byCountry ? sum([...sc.iso2].map((c) => ets.countries[c]?.t[k] ?? 0)) : sum(etsRows.map((r) => r[4][k] ?? 0))) : null;
    const etsN = ets ? (sc.byCountry ? sum([...sc.iso2].map((c) => ets.countries[c]?.n ?? 0)) : etsRows.length) : 0;
    const g = ghg ? (sc.byCountry ? ghg.points : pick(ghg.points, (p) => [p[0], p[1]], s)) : null;
    const c = ct ? (sc.byCountry ? ct.rows.filter((x) => sc.iso3.has(x[2])) : pick(ct.rows, (x) => [x[0], x[1]], s)) : null;
    return { etsT, etsN, largest: [...etsRows].sort((a, b) => (b[4][k] ?? 0) - (a[4][k] ?? 0)).slice(0, 5), k, g, c };
  });
  return (
    <Card title="Emissions per facility" accent={[236, 128, 92]}>
      <Tiles>
        {sc.europe && <Tile label={`EU ETS, verified ${ets?.newest ?? ""}`} value={d?.etsT != null ? mt(d.etsT) : "…"} sub={d ? `${int(d.etsN)} installations${sc.byCountry ? ", all (the registry's country totals)" : " placed inside"}` : "EU ETS"} />}
        {sc.us && <Tile label={`US EPA GHGRP ${ghg?.year ?? ""}`} value={d?.g ? mt(sum(d.g.map((p) => p[2]))) : "…"} sub={d?.g ? `${int(d.g.length)} facilities, CO₂e reported` : "EPA"} />}
        <Tile label={`Climate TRACE ${ct?.year ?? ""}`} value={d?.c ? mt(sum(d.c.map((x) => x[5]))) : "…"} sub={d?.c ? `${int(d.c.length)} facilities, CO₂e modelled` : "Climate TRACE"} />
      </Tiles>
      {d && d.largest.length > 0 && ets && (
        <>
          <Head>Largest EU ETS installations</Head>
          {d.largest.map((x) => (
            <Line key={x[1]} k={x[2]} v={mt(x[4][d.k] ?? 0)} sub={`${x[0]}${x[5] == null ? ", not placed" : ""}`} />
          ))}
        </>
      )}
      <Note>
        Sums over {how(sc)} (computed). Reported (EU ETS verified, EPA GHGRP) and modelled (Climate TRACE) figures kept apart.
        {sc.europe && !sc.byCountry ? " The map places only the installations the EEA links to a position (Germany: 78 of 1,818): a country's dashboard counts them all." : ""}
      </Note>
    </Card>
  );
}

export function AreaFuelsCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const gem = useGemRows(GEM_FUELS, sc);
  const gasPipes = useFile<GemPipesFile>("gemGas");
  const oilPipes = useFile<GemPipesFile>("gemOil");
  const gas = useFile<GasFile>(sc.europe ? "gas" : null);
  const d = useLater(`fuel|${s.key}|${fkey(gasPipes, oilPipes, gas)}`, () => {
    const pipes = (f: GemPipesFile | undefined) => {
      if (!f) return null;
      if (sc.byCountry) {
        const rows = f.rows.filter((r) => CLASS_LABEL[r[0]] === "operating" && sc.hasName(r[6]));
        return { n: rows.length, km: sum(rows.map((r) => r[3] ?? 0)), whole: true };
      }
      let km = 0;
      for (const p of f.paths) {
        if (CLASS_LABEL[f.rows[p[0]]?.[0]] !== "operating") continue;
        km += kmInside(p.slice(1), s);
      }
      return { n: null, km, whole: false };
    };
    return { gas: pipes(gasPipes), oil: pipes(oilPipes), storages: gas ? (sc.byCountry ? gas.storages.filter((x) => sc.iso2.has(x[1])).length : pick(gas.storages, (x) => [x[2], x[3]], s).length) : null };
  });
  const pipeTile = (label: string, v: { n: number | null; km: number; whole: boolean } | null | undefined) => (
    <Tile label={label} value={v ? `${int(v.km)} km` : "…"} sub={v ? (v.whole ? `${int(v.n ?? 0)} pipelines touching, their whole length` : "length inside") : "Global Energy Monitor"} />
  );
  return (
    <Card title="Gas, oil and coal" accent={[255, 178, 62]}>
      <Tiles>
        {pipeTile("Gas pipelines, operating", d?.gas)}
        {pipeTile("Oil pipelines, operating", d?.oil)}
      </Tiles>
      {gem
        ?.filter((g) => g.n > 0)
        .map((g) => (
          <Line key={g.label} k={g.label} v={int(g.n)} sub={`${int(g.op)} operating${g.size > 0 ? `, ${num(g.size)} ${g.unit}` : ""}`} />
        ))}
      {sc.europe && d?.storages != null && <Line k="Gas storage sites" v={int(d.storages)} sub="SciGRID_gas (2021)" />}
      <Note>
        Global Energy Monitor: {sc.byCountry ? "pipelines whose country list names one of these countries, with GEM's length of the whole pipeline; other records by their country" : "pipelines by the length of the segments whose midpoint lies inside; other records by position"} (computed).
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- land and risk

export function AreaRiskCard({ s }: { s: AreaShape }) {
  const sc = useScope(s);
  const small = s.km2 <= GRID_MAX_KM2;
  const cf = useFile<ConstraintsFile>(small ? "constraints" : null);
  const pf = useFile<ProtectedFile>(sc.byCountry ? "protected" : null);
  const off = useFile<OffshoreWindFile>(sc.europe ? "offshoreWind" : null);
  const flood = useAsync(cf ? `flood|${s.key}` : null, async () => {
    const map = sc.europe && !sc.us && (sc.byCountry ? [...sc.iso3].every((c) => EUROPE_ISO3.has(c)) : true) ? cf!.flood.maps.eu : cf!.flood.maps.world;
    const l = map.lookup;
    let n = 0;
    let wet = 0;
    const res = await readGrid(
      { url: l.url, bytes: 1, width: l.width, height: l.height, origin: l.origin, cell: l.cell_deg },
      s,
      (v, o) => {
        const c = v.getUint8(o);
        if (c === 255) return;
        n++;
        if (c > 0) wet++;
      },
      60,
    );
    return { share: n ? wet / n : null, cells: n, step: res.step, cell: l.cell_deg };
  });
  const n2k = pf && sc.byCountry ? [...sc.iso2].map((c) => pf.natura2000.by_country[c]).filter(Boolean) : [];
  const farms = useLater(off ? `off|${s.key}` : null, () => (sc.byCountry ? off!.farms.filter((f) => !!f.iso3 && sc.iso3.has(f.iso3)) : pick(off!.farms, (f) => f.at, s)));
  return (
    <Card title="Land and risk" accent={[96, 186, 120]}>
      <Tiles>
        <Tile
          label="River flood, 100-year"
          value={!small ? "–" : flood.v?.share != null ? `${(100 * flood.v.share).toFixed(1)} %` : flood.failed ? "–" : "…"}
          sub={!small ? "pick an area under 2 million km²" : flood.v ? `of ${int(flood.v.cells)} cells of ${flood.v.cell}°${flood.v.step > 1 ? `, every ${flood.v.step}th` : ""} have water mapped · JRC` : "JRC"}
        />
        {n2k.length > 0 && <Tile label="Natura 2000" value={`${int(sum(n2k.map((x) => x[0])))} sites`} sub={`${int(sum(n2k.map((x) => x[1])))} km² as published (EEA), land and sea, may overlap`} />}
        {farms && farms.length > 0 && <Tile label="Offshore wind farm areas" value={int(farms.length)} sub="EMODnet, every status" />}
      </Tiles>
      <Note>
        Flood: the share of the hazard map's lookup cells inside with any water depth mapped in a 100-year flood (computed), a hazard map, not a risk assessment.{" "}
        {sc.byCountry ? "Natura 2000: the EEA's counts and areas per country, summed." : "Protected areas for a drawn area: Check a site gives the share around a place."}
      </Note>
    </Card>
  );
}

const CARDS = [AreaOverviewCard, AreaElectricityCard, AreaEmissionsCard, AreaPlantsCard, AreaGridCard, AreaCapacityCard, AreaRegistersCard, AreaDemandCard, AreaFuelsCard, AreaRiskCard];

/** Every area card, in reading order, one after another (each loads its files and counts in turn,
 *  so the map keeps drawing meanwhile). */
export function AreaCards({ s }: { s: AreaShape }) {
  const [shown, setShown] = useState<{ key: string; n: number }>({ key: s.key, n: 2 });
  const n = shown.key === s.key ? shown.n : 2;
  useEffect(() => {
    if (n >= CARDS.length) return;
    const t = setTimeout(() => setShown({ key: s.key, n: n + 1 }), 450);
    return () => clearTimeout(t);
  }, [n, s.key]);
  return (
    <>
      {CARDS.slice(0, n).map((Card, i) => (
        <Card key={i} s={s} />
      ))}
      {n < CARDS.length && <div className={`px-1 text-[10.5px] ${muted}`}>More figures follow…</div>}
    </>
  );
}

