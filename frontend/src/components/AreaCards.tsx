// The area dashboard: what the map's files hold inside an area (countries, a drawn polygon, a
// circle around a city). Every figure is a file's value, or a count, sum or length over the
// records inside the area (point-in-polygon on the record's position; lines by the midpoints of
// their segments), said on each card with its source. Nothing is estimated.

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { useFile } from "../app/data";
import { iso3Of } from "../app/datasets";
import type { CountriesFile, GasFile, GridFile, PlantsFile, ReferenceFile, StatsFile } from "../app/types";
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
const overlaps = (a: [number, number, number, number], b: [number, number, number, number]) => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
const ISO2_OF_3 = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));
const int = (v: number) => Math.round(v).toLocaleString("en-US");
const num = (v: number, d = 1) => (v >= 100 ? int(v) : v.toFixed(d));
const sum = (v: number[]) => v.reduce((a, b) => a + b, 0);

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
/** Thin horizontal bars: magnitude by category, value in text colour beside each. */
export function Bars({ rows, unit, max }: { rows: Bar[]; unit?: string; max?: number }) {
  const top = max ?? Math.max(1e-9, ...rows.map((r) => r.value));
  return (
    <div className="space-y-[5px]">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2 text-[11px]" title={`${r.label}: ${r.text ?? `${num(r.value)}${unit ? ` ${unit}` : ""}`}`}>
          <span className="w-[104px] shrink-0 truncate text-slate-300">{r.label}</span>
          <span className="relative h-[7px] flex-1 rounded-[4px] bg-white/[0.05]">
            <span className="absolute inset-y-0 left-0 rounded-[4px]" style={{ width: `${Math.max(1.5, (100 * r.value) / top)}%`, background: rgbCss(r.color ?? GREY) }} />
          </span>
          <span className="w-[70px] shrink-0 text-right tabular-nums text-slate-200">{r.text ?? `${num(r.value)}${unit ? ` ${unit}` : ""}`}</span>
        </div>
      ))}
    </div>
  );
}
const Head = ({ children }: { children: ReactNode }) => <div className={`mb-1 mt-2.5 text-[9.5px] uppercase tracking-[0.16em] ${muted}`}>{children}</div>;
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;
const Loading = ({ what }: { what: string }) => <div className={`text-[11px] ${muted}`}>Reading {what}…</div>;
const Line = ({ k, v, sub }: { k: ReactNode; v: ReactNode; sub?: ReactNode }) => (
  <div className="flex items-baseline justify-between gap-3 py-[3px] text-[11.5px]">
    <span className="min-w-0 truncate text-slate-300">{k}</span>
    <span className="shrink-0 text-right tabular-nums text-slate-100">
      {v}
      {sub && <span className={`ml-1.5 text-[10px] ${muted}`}>{sub}</span>}
    </span>
  </div>
);

/** Where the area lies: which regional files apply (bounding boxes decide what to load). */
function useRegions(s: AreaShape) {
  const europe = s.countries ? s.countries.some((c) => EUROPE_ISO3.has(c)) : overlaps(s.bbox, EUROPE_BOX);
  const us = s.countries ? s.countries.includes("USA") : overlaps(s.bbox, US_BOX);
  const elsewhere = s.countries ? s.countries.some((c) => !EUROPE_ISO3.has(c) && c !== "USA") : !(s.bbox[0] >= EUROPE_BOX[0] && s.bbox[2] <= EUROPE_BOX[2] && s.bbox[1] >= EUROPE_BOX[1] && s.bbox[3] <= EUROPE_BOX[3]) && !(s.bbox[0] >= US_BOX[0] && s.bbox[2] <= US_BOX[2] && s.bbox[1] >= US_BOX[1] && s.bbox[3] <= US_BOX[3]);
  return { europe, us, elsewhere };
}

/** Does the area reach a European country (ISO alpha-2)? Its list, or the box of its outline. */
function useReaches(s: AreaShape): (cc: string) => boolean {
  const countries = useFile<CountriesFile>("countries");
  const boxes = useMemo(() => {
    const m = new Map<string, [number, number, number, number]>();
    for (const c of countries?.countries ?? []) {
      let [x0, y0, x1, y1] = [180, 90, -180, -90];
      for (const poly of c.polygons)
        for (let i = 0; i < poly[0].length; i += 2) {
          x0 = Math.min(x0, poly[0][i]);
          x1 = Math.max(x1, poly[0][i]);
          y0 = Math.min(y0, poly[0][i + 1]);
          y1 = Math.max(y1, poly[0][i + 1]);
        }
      m.set(c.iso, [x0, y0, x1, y1]);
    }
    return m;
  }, [countries]);
  return (cc: string) => (s.countries ? s.countries.includes(iso3Of(cc)) : !!boxes.get(cc) && overlaps(s.bbox, boxes.get(cc)!));
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

// ---------------------------------------------------------------- overview: size, people, resources

export function AreaOverviewCard({ s }: { s: AreaShape }) {
  const atlas = useFile<AtlasFile>("atlas");
  const people = useAsync(`pop|${s.key}`, async () => {
    let n = 0;
    // every row: a sum must not skip cells (areas taller than 90° are not summed)
    const r = await readGrid({ url: POP_URL, bytes: 4, width: 3600, height: 1800, origin: [-180, 90], cell: 0.1 }, s, (v, off) => (n += v.getInt32(off, true)), 900);
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
      });
      return { mean: n ? t / n : null, cells: n, step: r.step, unit: atlas![k].unit };
    };
    const [pv, wind] = await Promise.all([mean("pvout"), mean("wind")]);
    return { pv, wind };
  });
  const p = people.v;
  return (
    <Card title="The area" note={s.kind === "countries" ? "country outlines" : s.kind === "circle" ? "a circle" : "drawn on the map"} accent={[120, 190, 255]}>
      <Tiles>
        <Tile label="Size" value={km2Text(s.km2)} sub="computed from the outline" />
        <Tile
          label="People"
          value={people.failed ? "–" : p ? (p.whole ? (p.people >= 1e6 ? `${(p.people / 1e6).toFixed(2)} M` : int(p.people)) : "–") : "…"}
          sub={p ? (p.whole ? `${int(p.people / Math.max(1, s.km2))} per km² · GHSL 2025, ${int(p.cells)} cells of 0.1°` : "area too tall to sum") : people.failed ? "grid not reachable" : "GHSL 2025"}
        />
        <Tile
          label="Solar resource"
          value={res.v?.pv.mean != null ? `${num(res.v.pv.mean, 2)}` : res.failed ? "–" : "…"}
          sub={res.v ? `${res.v.pv.unit}, mean of ${int(res.v.pv.cells)} cells${res.v.pv.step > 1 ? ` (every ${res.v.pv.step}th row and column)` : ""} · Global Solar Atlas` : "Global Solar Atlas"}
        />
        <Tile
          label="Wind at 100 m"
          value={res.v?.wind.mean != null ? `${num(res.v.wind.mean, 2)}` : res.failed ? "–" : "…"}
          sub={res.v ? `${res.v.wind.unit}, mean of ${int(res.v.wind.cells)} cells${res.v.wind.step > 1 ? ` (every ${res.v.wind.step}th row and column)` : ""} · Global Wind Atlas` : "Global Wind Atlas"}
        />
      </Tiles>
      <Note>
        People: the sum of the 0.1° cells whose centre lies inside (computed). Resources: the mean of the atlases' 0.1° lookup cells inside (computed), long-term averages.
      </Note>
    </Card>
  );
}

// ---------------------------------------------------------------- electricity (European countries)

export function AreaElectricityCard({ s }: { s: AreaShape }) {
  const codes = s.countries ?? [];
  const stats = useFile<StatsFile>(s.countries ? "stats" : null);
  const ref = useFile<ReferenceFile>(s.countries ? "reference" : null);
  const t = useFile<TransitionFile>(s.countries ? "transition" : null);
  if (!s.countries) return null;
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
  // Ember, yearly: the newest year every country in the area has
  const ents = t ? codes.map((c) => t.entities[c]).filter(Boolean) : [];
  const yk = t && ents.length ? [...t.years.keys()].reverse().find((k) => ents.every((e) => e.total_twh[k] != null)) : undefined;
  const ember: Record<string, number> = {};
  if (t && yk != null) for (const e of ents) for (const [k, ser] of Object.entries(e.series)) ember[k] = (ember[k] ?? 0) + (ser[yk] ?? 0);
  const emberTotal = sum(Object.values(ember));
  if (!now.length && !capOf.length && !ents.length) return null;
  return (
    <Card title="Electricity" note={codes.length > 1 ? `sums over ${codes.length} countries` : undefined} accent={[255, 214, 72]}>
      {now.length > 0 && (
        <>
          <Tiles>
            <Tile label="Demand now" value={power(load)} sub={`sum of ${now.length} ${now.length === 1 ? "country" : "countries"} · ENTSO-E`} />
            <Tile label="Renewable share now" value={total > 0 ? `${((100 * green) / total).toFixed(1)} %` : "–"} sub="each country's share × its generation, summed" />
          </Tiles>
          <Head>Generation now by source</Head>
          <Bars
            unit=""
            rows={FUEL_ORDER.filter((k) => gen[k] > 0).map((k) => ({ key: k, label: FUEL_LABEL[k] ?? k, value: gen[k], color: FUEL_COLOR[k], text: power(gen[k]) }))}
          />
          <Note>ENTSO-E, each country's newest complete interval ({[...new Set(now.map(([, p]) => p.ts.slice(11, 16)))].join(", ")} UTC).</Note>
        </>
      )}
      {capOf.length > 0 && (
        <>
          <Head>Installed capacity</Head>
          <Bars rows={Object.entries(cap).sort((a, b) => b[1] - a[1]).slice(0, 9).map(([k, v]) => ({ key: k, label: FUEL_LABEL[k] ?? k, value: v, color: FUEL_COLOR[k], text: `${v.toFixed(1)} GW` }))} />
          <Note>ENTSO-E installed capacity per production type (A68), summed over {capOf.length} {capOf.length === 1 ? "country" : "countries"}.</Note>
        </>
      )}
      {t && yk != null && emberTotal > 0 && (
        <>
          <Head>Generation in {t.years[yk]}</Head>
          <Bars rows={EMBER_ORDER.filter((k) => (ember[k] ?? 0) > 0).map((k) => ({ key: k, label: k, value: ember[k], color: EMBER_COLOR[k], text: `${num(ember[k])} TWh` }))} />
          <Note>Ember yearly data, TWh, summed over the {ents.length} {ents.length === 1 ? "country" : "countries"} (the newest year all of them have).</Note>
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- power plants

interface PlantRow {
  label: string;
  color: RGB;
  mw: number;
  status: "operating" | "construction" | "planned";
  name: string | null;
}

export function AreaPlantsCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const eu = useFile<PlantsFile>(r.europe ? "plants" : null);
  const countries = useFile<CountriesFile>(r.europe ? "countries" : null);
  const usp = useFile<UsPlantsFile>(r.us ? "usPlants" : null);
  const states = useFile<UsStatesFile>(r.us ? "usStates" : null);
  const gem = useFile<WorldPlantsFile>("worldPlants");
  const ready = !!gem && (!r.europe || (!!eu && !!countries)) && (!r.us || (!!usp && !!states));
  const data = useMemo(() => {
    if (!ready) return null;
    const rows: PlantRow[] = [];
    const euShape = r.europe && countries ? makeShape("countries", "europe", "Europe", countries.countries.flatMap((c) => c.polygons)) : null;
    const inEu = (lon: number, lat: number) => !!euShape && inside(euShape, lon, lat);
    const usTest = r.us && states ? usTester(states) : null;
    const inUs = (lon: number, lat: number) => !!usTest && (lon < -64 || lon > 170) && lat > 17 && usTest(lon, lat);
    if (eu) for (const p of pick(eu.plants, (x) => [x[2], x[3]], s)) rows.push({ label: FUEL_LABEL[eu.groups[p[0]]] ?? eu.groups[p[0]], color: FUEL_COLOR[eu.groups[p[0]]] ?? GREY, mw: p[1], status: "operating", name: p[5] });
    if (usp)
      for (const p of pick(usp.points, (x) => [x[0], x[1]], s)) {
        const st = usp.statuses[p[3]];
        if (st !== "operating" && st !== "construction" && st !== "planned") continue;
        rows.push({ label: US_TYPE_LABEL[usp.types[p[2]]] ?? usp.types[p[2]], color: US_TYPE_COLOR[usp.types[p[2]]] ?? GREY, mw: p[4], status: st, name: usp.plants[p[6]]?.[0] ?? null });
      }
    for (const p of pick(gem!.points, (x) => [x[0], x[1]], s)) {
      const st = gem!.statuses[p[3]];
      if (st !== "operating" && st !== "construction" && st !== "planned") continue;
      // Europe's own file wins for operating plants there, the EIA everywhere in the US
      if (inUs(p[0], p[1]) || (st === "operating" && inEu(p[0], p[1]))) continue;
      rows.push({ label: PLANT_TYPE_LABEL[gem!.types[p[2]]] ?? gem!.types[p[2]], color: PLANT_TYPE_COLOR[gem!.types[p[2]]] ?? GREY, mw: p[4], status: st, name: null });
    }
    return rows;
  }, [ready, eu, usp, gem, countries, states, s, r.europe, r.us]);
  if (!data)
    return (
      <Card title="Power plants" accent={[255, 128, 72]}>
        <Loading what="the plant files" />
      </Card>
    );
  const of = (st: PlantRow["status"]) => data.filter((p) => p.status === st);
  const byType = (rows: PlantRow[]) => {
    const m = new Map<string, Bar>();
    for (const p of rows) {
      const b = m.get(p.label) ?? { key: p.label, label: p.label, value: 0, color: p.color };
      b.value += p.mw;
      m.set(p.label, b);
    }
    return [...m.values()].sort((a, b) => b.value - a.value).map((b) => ({ ...b, text: power(b.value) }));
  };
  const op = of("operating");
  const building = of("construction");
  const planned = of("planned");
  const largest = op.filter((p) => p.name).sort((a, b) => b.mw - a.mw).slice(0, 5);
  const sources = [r.europe && "Europe, operating: powerplantmatching (units of 20 MW and more)", r.us && `the US: EIA-860M (${usp?.release ?? ""}), units of 1 MW and more`, "elsewhere, and building or planned outside the US: Global Energy Monitor"].filter(Boolean).join("; ");
  return (
    <Card title="Power plants" accent={[255, 128, 72]}>
      <Tiles>
        <Tile label="Operating" value={power(sum(op.map((p) => p.mw)))} sub={`${int(op.length)} map points`} />
        <Tile label="Building · planned" value={`${power(sum(building.map((p) => p.mw)))} · ${power(sum(planned.map((p) => p.mw)))}`} sub={`${int(building.length)} · ${int(planned.length)} map points`} />
      </Tiles>
      {op.length > 0 && (
        <>
          <Head>Operating, by type</Head>
          <Bars rows={byType(op).slice(0, 9)} />
        </>
      )}
      {building.length + planned.length > 0 && (
        <>
          <Head>Under construction and planned, by type</Head>
          <Bars rows={byType([...building, ...planned]).slice(0, 7)} />
        </>
      )}
      {largest.length > 0 && (
        <>
          <Head>Largest operating</Head>
          {largest.map((p, i) => (
            <Line key={i} k={p.name} v={power(p.mw)} sub={p.label} />
          ))}
        </>
      )}
      <Note>
        Capacity summed over the map points inside the area (computed). Sources: {sources}.
        {r.europe ? " In Europe units under 20 MW (most wind and solar) are not in the file: the Electricity card gives each country's installed capacity." : ""}
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
  const r = useRegions(s);
  const grid = useFile<GridFile>(r.europe ? "grid" : null);
  const data = useMemo(() => {
    if (!grid) return null;
    const km: Record<string, number> = {};
    for (const [kv, path] of grid.lines) {
      const band = BANDS.find(([min]) => kv >= min)![1];
      const k = kmInside(path, s);
      if (k > 0) km[band] = (km[band] ?? 0) + k;
    }
    const hvdc = sum(grid.links.map(([, path]) => kmInside(path, s)));
    const subs = pick(grid.substations, (x) => [x[1], x[2]], s);
    const subBands: Record<string, number> = {};
    for (const x of subs) {
      const band = BANDS.find(([min]) => x[0] >= min)![1];
      subBands[band] = (subBands[band] ?? 0) + 1;
    }
    return { km, hvdc, subs: subs.length, subBands };
  }, [grid, s]);
  if (!r.europe)
    return (
      <Card title="Transmission grid" accent={[236, 178, 120]}>
        <Note>Line lengths are counted from Europe's grid file. Outside Europe the lines come from the map's tiles: "Check a site" reads them for a place and its surroundings.</Note>
      </Card>
    );
  if (!data)
    return (
      <Card title="Transmission grid" accent={[236, 178, 120]}>
        <Loading what="the grid" />
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
      <Note>PyPSA-Eur's network from OpenStreetMap: length of the line segments whose midpoint lies inside (computed; a line's circuits count once). Substations of 220 kV and more inside.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- room to connect

export function AreaCapacityCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const reaches = useReaches(s);
  const connect = useFile<ConnectFile>(r.europe && reaches("GB") ? "connect" : null);
  const euFiles = CONNECT_EU.map((id) => [id, useFile<ConnectEuFile>(r.europe && reaches(id.slice(0, 2)) ? connectEuKey(id) : null)] as const); // eslint-disable-line react-hooks/rules-of-hooks
  const gb = useMemo(() => (connect ? pick(gbSiteTotals(connect.gb), (t) => [t.site[1] as number, t.site[2] as number], s) : []), [connect, s]);
  const eu = useMemo(() => euFiles.flatMap(([id, f]) => (f ? [{ id, f, pts: pick(f.points, (p) => [p[1], p[2]], s) }] : [])).filter((x) => x.pts.length), [s, ...euFiles.map(([, f]) => f)]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!r.europe) return null;
  if (!gb.length && !eu.length) return null;
  return (
    <Card title="Room to connect" accent={[206, 138, 72]}>
      {gb.length > 0 && connect && (
        <>
          <Tiles>
            <Tile label="GB: waiting to connect" value={power(sum(gb.map((g) => g.mw)))} sub={`${gb.length} transmission sites · NESO TEC register`} />
          </Tiles>
          <Head>Waiting, by type</Head>
          <Bars rows={connect.gb.types.map((t, i) => ({ key: t, label: t, value: sum(gb.map((g) => g.byType[i])) })).filter((b) => b.value > 0).sort((a, b) => b.value - a.value).slice(0, 7).map((b) => ({ ...b, text: power(b.value) }))} />
        </>
      )}
      {eu.map(({ id, f, pts }) => (
        <div key={id} className="mt-2">
          <Line k={`${id}: capacity points published`} v={int(pts.length)} sub={f.source} />
        </div>
      ))}
      <Note>Each operator's own map or register, as published; the values per point stay on the map (Grid capacity layer). GB: MW of projects not yet connected, summed per site inside the area (computed).</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- every unit in national registers

const REGISTERS = ["GB", "FR", "DK", "SE", "IE", "BE", "FI", "PT", "CZ"] as const;

export function AreaRegistersCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const reaches = useReaches(s);
  const files = REGISTERS.map((cc) => [cc, useFile<RegisterFile>(r.europe && reaches(cc) ? `register${cc}` : null)] as const); // eslint-disable-line react-hooks/rules-of-hooks
  const muni = useFile<MastrMuniFile>(r.europe && reaches("DE") ? "mastrMuni" : null);
  const turbines = useFile<UsTurbinesFile>(r.us ? "usTurbines" : null);
  const solar = useFile<UsSolarFile>(r.us ? "usSolar" : null);
  const rows = useMemo(() => {
    const out: { key: string; label: string; n: number; mw: number; src: string }[] = [];
    for (const [cc, f] of files) {
      if (!f) continue;
      const pts = pick(f.points, (p) => [p[1], p[2]], s);
      if (!pts.length) continue;
      const by = new Map<string, [number, number]>();
      for (const p of pts) {
        const b = by.get(p[3]) ?? [0, 0];
        b[0]++;
        b[1] += p[4] ?? 0;
        by.set(p[3], b);
      }
      for (const [g, [n, mw]] of by) out.push({ key: `${cc}${g}`, label: `${cc} ${g}`, n, mw, src: f.source });
    }
    if (muni) {
      const gs = muni.gemeinden.filter((g) => g.label && inside(s, g.label[0], g.label[1]));
      muni.techs.forEach((t, i) => {
        const mw = sum(gs.map((g) => g.mw[i] ?? 0));
        const n = sum(gs.map((g) => g.n[i] ?? 0));
        if (n > 0) out.push({ key: `DE${t}`, label: `DE ${t}`, n, mw, src: `${muni.source}, ${gs.length} municipalities by their label point` });
      });
    }
    if (turbines) {
      let n = 0;
      let kw = 0;
      for (let i = 0; i < turbines.lon.length; i++)
        if (inside(s, turbines.lon[i], turbines.lat[i])) {
          n++;
          kw += turbines.kw[i] ?? 0;
        }
      if (n) out.push({ key: "USwind", label: "US wind turbines", n, mw: kw / 1000, src: turbines.source });
    }
    if (solar) {
      const sites = pick(solar.sites, (x) => [x[0] ?? 999, x[1] ?? 999], s);
      if (sites.length) out.push({ key: "USsolar", label: "US solar farms (MW AC)", n: sites.length, mw: sum(sites.map((x) => x[2] ?? 0)), src: solar.source });
    }
    return out.sort((a, b) => b.mw - a.mw);
  }, [s, muni, turbines, solar, ...files.map(([, f]) => f)]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!rows.length) return null;
  return (
    <Card title="Every unit (national registers)" accent={[255, 214, 72]}>
      <Bars rows={rows.slice(0, 12).map((x) => ({ key: x.key, label: x.label, value: x.mw, color: [255, 214, 72], text: `${power(x.mw)} · ${int(x.n)}` }))} />
      <Note>MW and units summed over the register entries inside the area (computed); a register's own groups. Sources: {[...new Set(rows.map((x) => x.src))].join("; ")}.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- demand and industry

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

function useGemRows(list: [string, string][], s: AreaShape) {
  const files = list.map(([k]) => useFile<GemPointsFile>(k)); // eslint-disable-line react-hooks/rules-of-hooks
  return useMemo(
    () =>
      list.flatMap(([, label], i) => {
        const f = files[i];
        if (!f) return [];
        const pts = pick(f.points, (p) => [p[0], p[1]], s);
        const op = pts.filter((p) => CLASS_LABEL[p[3]] === "operating");
        return [{ label, n: pts.length, op: op.length, size: sum(op.map((p) => p[4] ?? 0)), unit: f.unit, sizeLabel: f.size_label }];
      }),
    [s, ...files], // eslint-disable-line react-hooks/exhaustive-deps
  );
}

export function AreaDemandCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const dc = useFile<DataCentresFile>("datacentres");
  const evEu = useFile<EvEuFile>(r.europe ? "evEu" : null);
  const evUs = useFile<EvChargersFile>(r.us ? "evChargers" : null);
  const h2 = useFile<HydrogenFile>(r.europe ? "hydrogen" : null);
  const gem = useGemRows(GEM_INDUSTRY, s);
  const dcs = useMemo(() => pick(dc?.points, (p) => [p[0], p[1]], s), [dc, s]);
  const ev = useMemo(() => (evEu ? sum(Object.values(evEu.cells).flatMap((cells) => pick(cells, (c) => [c[0], c[1]], s).map((c) => c[2]))) : null), [evEu, s]);
  const us = useMemo(() => (evUs ? pick(evUs.points, (p) => [p[0], p[1]], s) : []), [evUs, s]);
  const h = useMemo(() => (h2 ? pick(h2.projects, (p) => [p[8], p[9]], s) : []), [h2, s]);
  return (
    <Card title="Demand and industry" accent={[196, 150, 255]}>
      <Tiles>
        <Tile label="Data centres" value={dc ? int(dcs.length) : "…"} sub="mapped in OpenStreetMap" />
        {r.europe && <Tile label="EV charging points" value={ev == null ? "…" : int(ev)} sub={evEu ? `cells of ${evEu.cell_deg}° inside · registers, OSM` : "Europe"} />}
        {r.us && <Tile label="US DC fast stations" value={evUs ? int(us.length) : "…"} sub={evUs ? `${int(sum(us.map((p) => p[2])))} ports · NREL AFDC` : "NREL AFDC"} />}
        {r.europe && h2 && <Tile label="Hydrogen projects" value={int(h.length)} sub={`${power(sum(h.map((p) => p[4] ?? 0)))} electrolysis where given · EHO`} />}
      </Tiles>
      {gem.some((g) => g.n > 0) && (
        <>
          <Head>Heavy industry (Global Energy Monitor)</Head>
          {gem
            .filter((g) => g.n > 0)
            .map((g) => (
              <Line key={g.label} k={g.label} v={int(g.n)} sub={g.op && g.size > 0 ? `${int(g.op)} operating, ${num(g.size)} ${g.unit}` : `${int(g.op)} operating`} />
            ))}
        </>
      )}
      <Note>Counts and sums over the records inside the area (computed). EV charging in Europe: the points per 0.1° cell, cells whose centre lies inside.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- emissions

export function AreaEmissionsCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const ets = useFile<EtsFile>(r.europe ? "ets" : null);
  const ghg = useFile<GhgrpFile>(r.us ? "ghgrp" : null);
  const ct = useFile<CtraceFile>("ctrace");
  const e = useMemo(() => (ets ? pick(ets.rows, (x) => [x[5] ?? 999, x[6] ?? 999], s) : []), [ets, s]);
  const g = useMemo(() => (ghg ? pick(ghg.points, (p) => [p[0], p[1]], s) : []), [ghg, s]);
  const c = useMemo(() => (ct ? pick(ct.rows, (x) => [x[0], x[1]], s) : []), [ct, s]);
  const mt = (t: number) => `${(t / 1e6).toFixed(2)} Mt`;
  return (
    <Card title="Emissions per facility" accent={[236, 128, 92]}>
      <Tiles>
        {r.europe && <Tile label={`EU ETS, verified ${ets?.newest ?? ""}`} value={ets ? mt(sum(e.map((x) => x[3] ?? 0))) : "…"} sub={`${int(e.length)} installations with a position`} />}
        {r.us && <Tile label={`US EPA GHGRP ${ghg?.year ?? ""}`} value={ghg ? mt(sum(g.map((p) => p[2]))) : "…"} sub={`${int(g.length)} facilities, CO₂e reported`} />}
        <Tile label={`Climate TRACE ${ct?.year ?? ""}`} value={ct ? mt(sum(c.map((x) => x[5]))) : "…"} sub={`${int(c.length)} facilities, CO₂e modelled`} />
      </Tiles>
      {e.length > 0 && ets && (
        <>
          <Head>Largest EU ETS installations</Head>
          {[...e]
            .sort((a, b) => (b[3] ?? 0) - (a[3] ?? 0))
            .slice(0, 4)
            .map((x) => (
              <Line key={x[1]} k={x[2]} v={mt(x[3] ?? 0)} sub={x[0]} />
            ))}
        </>
      )}
      <Note>Sums over the facilities placed inside the area (computed). Reported (EU ETS verified, EPA GHGRP) and modelled (Climate TRACE) figures are kept apart.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- fuels: gas, oil, coal

export function AreaFuelsCard({ s }: { s: AreaShape }) {
  const r = useRegions(s);
  const gem = useGemRows(GEM_FUELS, s);
  const gasPipes = useFile<GemPipesFile>("gemGas");
  const oilPipes = useFile<GemPipesFile>("gemOil");
  const gas = useFile<GasFile>(r.europe ? "gas" : null);
  const pipeKm = (f: GemPipesFile | undefined) => (f ? sum(f.paths.filter((p) => CLASS_LABEL[f.rows[p[0]]?.[0]] === "operating").map((p) => kmInside(p.slice(1), s))) : null);
  const km = useMemo(() => ({ gas: pipeKm(gasPipes), oil: pipeKm(oilPipes) }), [gasPipes, oilPipes, s]); // eslint-disable-line react-hooks/exhaustive-deps
  const storages = useMemo(() => (gas ? pick(gas.storages, (x) => [x[2], x[3]], s) : []), [gas, s]);
  return (
    <Card title="Gas, oil and coal" accent={[255, 178, 62]}>
      <Tiles>
        <Tile label="Gas pipelines, operating" value={km.gas == null ? "…" : `${int(km.gas)} km`} sub="Global Energy Monitor" />
        <Tile label="Oil pipelines, operating" value={km.oil == null ? "…" : `${int(km.oil)} km`} sub="Global Energy Monitor" />
      </Tiles>
      {gem
        .filter((g) => g.n > 0)
        .map((g) => (
          <Line key={g.label} k={g.label} v={int(g.n)} sub={`${int(g.op)} operating${g.size > 0 ? `, ${num(g.size)} ${g.unit}` : ""}`} />
        ))}
      {r.europe && gas && <Line k="Gas storage sites" v={int(storages.length)} sub="SciGRID_gas (2021)" />}
      <Note>Pipelines: length of the segments whose midpoint lies inside (computed). Other counts over the records inside.</Note>
    </Card>
  );
}

// ---------------------------------------------------------------- land and risk

export function AreaRiskCard({ s }: { s: AreaShape }) {
  const cf = useFile<ConstraintsFile>("constraints");
  const pf = useFile<ProtectedFile>(s.countries ? "protected" : null);
  const off = useFile<OffshoreWindFile>("offshoreWind");
  const flood = useAsync(cf ? `flood|${s.key}` : null, async () => {
    const r = regionsOf(s);
    const map = r.europe && !r.elsewhere && !r.us ? cf!.flood.maps.eu : cf!.flood.maps.world;
    const l = map.lookup;
    let n = 0;
    let wet = 0;
    const res = await readGrid({ url: l.url, bytes: 1, width: l.width, height: l.height, origin: l.origin, cell: l.cell_deg }, s, (v, o) => {
      const c = v.getUint8(o);
      if (c === 255) return;
      n++;
      if (c > 0) wet++;
    }, 120);
    return { share: n ? wet / n : null, cells: n, step: res.step, title: map.title, cell: l.cell_deg };
  });
  const n2k = pf && s.countries ? s.countries.map((c) => pf.natura2000.by_country[ISO2_OF_3[c] ?? ""] ?? (c === "CYP" ? pf.natura2000.by_country.CY : c === "MLT" ? pf.natura2000.by_country.MT : undefined)).filter(Boolean) : [];
  const farms = useMemo(() => (off ? pick(off.farms, (f) => f.at, s) : []), [off, s]);
  return (
    <Card title="Land and risk" accent={[96, 186, 120]}>
      <Tiles>
        <Tile
          label="River flood, 100-year"
          value={flood.v?.share != null ? `${(100 * flood.v.share).toFixed(1)} %` : flood.failed ? "–" : "…"}
          sub={flood.v ? `of ${int(flood.v.cells)} lookup cells of ${flood.v.cell}°${flood.v.step > 1 ? ` (every ${flood.v.step}th row and column)` : ""} with water mapped · JRC` : "JRC"}
        />
        {n2k.length > 0 && <Tile label="Natura 2000" value={`${int(sum(n2k.map((x) => x![0])))} sites`} sub={`${int(sum(n2k.map((x) => x![1])))} km² as published (EEA), land and sea, may overlap`} />}
        {farms.length > 0 && <Tile label="Offshore wind farm areas" value={int(farms.length)} sub="EMODnet, every status" />}
      </Tiles>
      <Note>
        Flood: the share of the hazard map's lookup cells inside that have any water depth mapped in a 100-year flood (computed), a hazard map, not a risk assessment.{" "}
        {s.countries ? "Natura 2000: the EEA's counts and areas per country, summed." : "Protected areas for a drawn area: Check a site gives the share around a place."}
      </Note>
    </Card>
  );
}
/** The same regions without hooks (inside async work). */
function regionsOf(s: AreaShape) {
  const europe = s.countries ? s.countries.some((c) => EUROPE_ISO3.has(c)) : overlaps(s.bbox, EUROPE_BOX);
  const us = s.countries ? s.countries.includes("USA") : overlaps(s.bbox, US_BOX);
  const elsewhere = s.countries ? s.countries.some((c) => !EUROPE_ISO3.has(c) && c !== "USA") : !europe && !us;
  return { europe, us, elsewhere };
}

/** Every area card, in reading order. */
export function AreaCards({ s }: { s: AreaShape }) {
  return (
    <>
      <AreaOverviewCard s={s} />
      <AreaElectricityCard s={s} />
      <AreaPlantsCard s={s} />
      <AreaGridCard s={s} />
      <AreaCapacityCard s={s} />
      <AreaRegistersCard s={s} />
      <AreaDemandCard s={s} />
      <AreaEmissionsCard s={s} />
      <AreaFuelsCard s={s} />
      <AreaRiskCard s={s} />
    </>
  );
}

