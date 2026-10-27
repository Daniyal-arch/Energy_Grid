// "On the map": the figures of the layers that are switched on, for the world or for the
// selected country. Every number is the layer file's own or a sum of it, said on the card.

import { useMemo, type ReactNode } from "react";

import { Card, SourcesCard } from "../components/CountryCards";
import { FinanceCountryCard, FinanceWorldCard } from "../components/FinanceCards";
import { UsOutagesCard, WaterCard } from "../components/RiskCards";
import { MastrCountryCard } from "../components/MastrCards";
import { BrazilCard, DataCentresCard, NemCard, OntarioCard, PlantsCard, TaiwanCard, UsCard } from "../components/WorldCards";
import { UsPlantsCard, UsQueueCard, UsQueueStatesCard, UsTurbinesCard, useStateNames } from "../components/UsCards";
import type { UsPlantsFile, UsQueueFile, UsTurbinesFile } from "../lib/us";
import { EV_COLOR, type EvChargersFile } from "../lib/evChargers";
import type { EvEuFile } from "../lib/evEu";
import { EvEuCard } from "../components/EvEuCards";
import { UsGasCard } from "../components/UsGasCards";
import { ghgrpColor, type GhgrpFile } from "../lib/ghgrp";
import { TYNDP_STYLE, type TyndpFile } from "../lib/tyndp";
import type { FinanceFile } from "../lib/finance";
import { CLASS_LABEL, GEM_PIPES, GEM_POINTS, type GemPipesFile, type GemPointsFile } from "../lib/gem";
import { rgbCss } from "../lib/theme";
import { ISO3 } from "../lib/transition";
import type { AemoFile, BrazilFile, DataCentresFile, OntarioFile, TaiwanFile, UsFile } from "../lib/world";
import type { WorldPlantsFile } from "../lib/worldPlants";
import { CABLE_STYLE } from "../app/colors";
import { useFile } from "../app/data";
import { LAYERS, STATS_LAYERS, actions, useApp, type LayerId, type PlantStatus } from "../app/store";
import { dayIndexKey, unitOutKey } from "../app/day";
import type { Cable, UnitOutputFile, WorldFile } from "../app/types";
import { FUEL_COLOR } from "../lib/energy";
import { ETS_COLOR, ETS_REGISTRY_NAME, etsIn, mt, newestT, type EtsFile } from "../lib/ets";
import { LNG_SEND, gwhdText, lngDay, type LngTerminalsFile } from "../lib/lngTerminals";
import { CT_COLOR, subsectorLabel, type CtraceFile } from "../lib/ctrace";
import { GB_TYPE_COLOR, NL_COLOR, gwText, type ConnectFile } from "../lib/connect";
import { ConnectEuCard } from "../components/ConnectEuCards";
import { RoomCard } from "../components/RoomCards";
import { RegisterCard } from "../components/RegisterCards";
import { REGISTER_LAYERS } from "../lib/registers";
import { CONNECT_EU, connectEuCountry } from "../lib/connectEu";
import { BeConnectCard, FrConnectCard, IeConnectCard, ItConnectCard, PlConnectCard, PtConnectCard } from "../components/ConnectMoreCards";
import { ProtectedCard } from "../components/ConstraintCards";
import { GasProjectsCard, HydrogenCard } from "../components/ComingCards";
import { Oe417Card } from "../components/ReliabilityCards";
import { OFFSHORE_LABEL, OFFSHORE_STYLE, offshoreStatus, type OffshoreWindFile } from "../lib/offshoreWind";
import { solarCat, type UsSolarFile } from "../lib/usSolar";

const muted = "text-[#8d94a1]";
const CLASS_COLOR = ["rgb(120,222,160)", "rgb(255,196,96)", "rgb(160,170,190)", "rgb(130,134,146)"];
// GEM's country names that differ from the map's outlines (ISO alpha-3)
const ALIAS: Record<string, string> = {
  russia: "RUS",
  vietnam: "VNM",
  "viet nam": "VNM",
  myanmar: "MMR",
  taiwan: "TWN",
  "czech republic": "CZE",
  czechia: "CZE",
  tanzania: "TZA",
  "dr congo": "COD",
  "democratic republic of the congo": "COD",
  "côte d'ivoire": "CIV",
  "cote d'ivoire": "CIV",
  singapore: "SGP",
  "hong kong": "HKG",
  us: "USA",
  usa: "USA",
  "united states": "USA",
  "united states of america": "USA",
  uk: "GBR",
  "united kingdom": "GBR",
  "south korea": "KOR",
  korea: "KOR",
  "north korea": "PRK",
  türkiye: "TUR",
  turkey: "TUR",
  laos: "LAO",
  iran: "IRN",
  syria: "SYR",
  bolivia: "BOL",
  venezuela: "VEN",
  moldova: "MDA",
  kosovo: "XKX",
  bahamas: "BHS",
  brunei: "BRN",
};

/** Country names in the layer files -> ISO alpha-3 (the map's outlines plus GEM's spellings). */
function useIsoOf() {
  const world = useFile<WorldFile>("world");
  return useMemo(() => {
    const byName = new Map((world?.features ?? []).map((f) => [f.properties.name.toLowerCase(), f.properties.iso3]));
    return (name: string) => {
      const n = name.trim().toLowerCase();
      return ALIAS[n] ?? byName.get(n) ?? "";
    };
  }, [world]);
}

// counts stay whole ("1 items", not "1.0"); measures keep one decimal under 10
const fmt = (v: number) => (Number.isInteger(v) || v >= 1000 ? Math.round(v).toLocaleString("en-US") : v >= 10 ? v.toFixed(0) : v.toFixed(1));

function Rows({ rows, unit }: { rows: { key: string; label: string; value: number; color?: string }[]; unit: string }) {
  const top = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="space-y-[3px]">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2 text-[11px] tabular-nums">
          <span className="flex w-[112px] items-center gap-1.5 truncate text-slate-300">
            {r.color && <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: r.color }} />}
            <span className="truncate">{r.label}</span>
          </span>
          <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
            <span className="absolute inset-y-0 left-0 rounded-sm bg-white/40" style={{ width: `${(r.value / top) * 100}%`, background: r.color }} />
          </span>
          <span className="w-[78px] text-right text-slate-100">
            {fmt(r.value)} {unit}
          </span>
        </div>
      ))}
    </div>
  );
}

const Head = ({ children }: { children: ReactNode }) => <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>{children}</div>;

/** A GEM point layer: by status, by kind, and by country (or the country's largest). */
function GemPointsCard({ id, iso3 }: { id: LayerId; iso3?: string }) {
  const style = GEM_POINTS[id];
  const f = useFile<GemPointsFile>(style.file);
  const isoOf = useIsoOf();
  const info = LAYERS.find((l) => l.id === id)!;
  if (!f) return <Card title={info.label} note="loading">…</Card>;
  const pts = iso3 ? f.points.filter((p) => isoOf(p[8]) === iso3) : f.points;
  const sized = !!f.unit;
  const val = (p: (typeof pts)[number]) => (sized ? (p[4] ?? 0) : 1);
  const unit = sized ? f.unit : "";
  const byClass = [0, 1, 2, 3].map((c) => ({ key: String(c), label: CLASS_LABEL[c], value: pts.filter((p) => p[3] === c).reduce((a, p) => a + val(p), 0), color: CLASS_COLOR[c] })).filter((r) => r.value > 0);
  const kinds = [...pts.reduce((m, p) => m.set(p[2], (m.get(p[2]) ?? 0) + val(p)), new Map<number, number>()).entries()]
    .map(([k, v]) => ({ key: String(k), label: f.kinds[k] ?? "other", value: v, color: rgbCss(style.color(f.kinds[k] ?? "")) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
  const places = iso3
    ? [...pts]
        .filter((p) => p[3] <= 1)
        .sort((a, b) => val(b) - val(a))
        .slice(0, 8)
        .map((p, i) => ({ key: `${p[6]}-${i}`, label: p[6] || style.noun, value: val(p), color: rgbCss(style.color(f.kinds[p[2]] ?? "")) }))
    : [...pts.reduce((m, p) => m.set(p[8], (m.get(p[8]) ?? 0) + (p[3] === 0 ? val(p) : 0)), new Map<string, number>()).entries()]
        .filter(([c]) => c)
        .map(([c, v]) => ({ key: c, label: c, value: v }))
        .sort((a, b) => b.value - a.value)
        .slice(0, 8);
  const operating = byClass.find((r) => r.key === "0")?.value ?? 0;
  return (
    <Card title={info.label} note="Global Energy Monitor" accent={style.color(f.kinds[0] ?? "") as [number, number, number]}>
      {pts.length === 0 ? (
        <div className={`text-[11px] ${muted}`}>None in GEM's tracker for this country.</div>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="text-[22px] font-light tabular-nums text-slate-100">{sized ? `${fmt(operating)} ${unit}` : pts.length.toLocaleString("en-US")}</span>
            <span className={`text-[10.5px] ${muted}`}>{sized ? `operating ${f.size_label}` : `${style.noun.toLowerCase()}s on the map`}</span>
          </div>
          <Head>By status{sized ? ` (${f.size_label})` : ""}</Head>
          <Rows rows={byClass} unit={unit} />
          {kinds.length > 1 && (
            <>
              <Head>By type</Head>
              <Rows rows={kinds} unit={unit} />
            </>
          )}
          {places.length > 0 && (
            <>
              <Head>{iso3 ? "Largest here (operating or building)" : `Largest countries (operating${sized ? `, ${f.size_label}` : ", count"})`}</Head>
              <Rows rows={places} unit={unit} />
            </>
          )}
        </>
      )}
      <div className={`mt-2 text-[10px] ${muted}`}>
        {sized ? `Sums of GEM's ${f.size_label} per status, type and country.` : "Counts of the sites on the map."} Cancelled, shelved and retired ones are not on the map.
      </div>
    </Card>
  );
}

/** A GEM pipeline layer: length by status, and by country. */
function GemPipesCard({ id, iso3 }: { id: LayerId; iso3?: string }) {
  const style = GEM_PIPES[id];
  const f = useFile<GemPipesFile>(style.file);
  const isoOf = useIsoOf();
  const info = LAYERS.find((l) => l.id === id)!;
  if (!f) return <Card title={info.label} note="loading">…</Card>;
  const countriesOf = (row: (typeof f.rows)[number]) => row[6].split(/[,;]\s*/).filter(Boolean);
  const rows = iso3 ? f.rows.filter((r) => countriesOf(r).some((c) => isoOf(c) === iso3)) : f.rows;
  const km = (r: (typeof rows)[number]) => r[3] ?? 0;
  const byClass = [0, 1, 2, 3].map((c) => ({ key: String(c), label: CLASS_LABEL[c], value: rows.filter((r) => r[0] === c).reduce((a, r) => a + km(r), 0), color: CLASS_COLOR[c] })).filter((r) => r.value > 0);
  const building = [...rows]
    .filter((r) => r[0] === 1)
    .sort((a, b) => km(b) - km(a))
    .slice(0, 6)
    .map((r, i) => ({ key: `${r[5]}-${i}`, label: r[5], value: km(r), color: rgbCss(style.color) }));
  const byCountry = iso3
    ? []
    : [...f.rows.filter((r) => r[0] === 0 && countriesOf(r).length === 1).reduce((m, r) => m.set(r[6], (m.get(r[6]) ?? 0) + km(r)), new Map<string, number>()).entries()]
        .map(([c, v]) => ({ key: c, label: c, value: v }))
        .sort((a, b) => b.value - a.value)
        .slice(0, 8);
  const operating = byClass.find((r) => r.key === "0")?.value ?? 0;
  return (
    <Card title={info.label} note="Global Energy Monitor" accent={style.color}>
      {rows.length === 0 ? (
        <div className={`text-[11px] ${muted}`}>None in GEM's tracker for this country.</div>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="text-[22px] font-light tabular-nums text-slate-100">{fmt(operating)} km</span>
            <span className={`text-[10.5px] ${muted}`}>operating, {rows.length.toLocaleString("en-US")} pipelines on the map</span>
          </div>
          <Head>Length by status</Head>
          <Rows rows={byClass} unit="km" />
          {building.length > 0 && (
            <>
              <Head>Longest under construction</Head>
              <Rows rows={building} unit="km" />
            </>
          )}
          {byCountry.length > 0 && (
            <>
              <Head>Operating, inside one country</Head>
              <Rows rows={byCountry} unit="km" />
            </>
          )}
        </>
      )}
      <div className={`mt-2 text-[10px] ${muted}`}>Sums of GEM's merged length per pipeline. {iso3 ? "A pipeline crossing this country counts in full." : "Cross-border pipelines are left out of the country list."}</div>
    </Card>
  );
}

/** Undersea power cables: how many and how long, by class (lengths measured on the drawn routes). */
function CablesCard() {
  const f = useFile<{ cables: Cable[] }>("cables");
  if (!f) return <Card title="Undersea power cables" note="loading">…</Card>;
  const R = 6371;
  const length = (flat: number[]) => {
    let km = 0;
    for (let i = 2; i < flat.length; i += 2) {
      const [lo1, la1, lo2, la2] = [flat[i - 2], flat[i - 1], flat[i], flat[i + 1]].map((v) => (v * Math.PI) / 180);
      const h = Math.sin((la2 - la1) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin((lo2 - lo1) / 2) ** 2;
      km += 2 * R * Math.asin(Math.sqrt(h));
    }
    return km;
  };
  const byClass = Object.entries(CABLE_STYLE)
    .map(([k, s]) => {
      const list = f.cables.filter((c) => c[0] === k);
      return { key: k, label: s.label, value: list.reduce((a, c) => a + length(c[3]), 0), n: list.length, color: `rgba(${s.color.join(",")})` };
    })
    .filter((r) => r.n > 0);
  const longest = [...f.cables]
    .filter((c) => c[2])
    .map((c) => ({ key: `${c[2]}-${c[3][0]}`, label: c[2] as string, value: length(c[3]), color: `rgba(${(CABLE_STYLE[c[0]] ?? CABLE_STYLE.other).color.join(",")})` }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
  return (
    <Card title="Undersea power cables" note="OpenStreetMap" accent={[110, 190, 255]}>
      <div className="text-[22px] font-light tabular-nums text-slate-100">{f.cables.length.toLocaleString("en-US")}</div>
      <div className={`text-[10.5px] ${muted}`}>cables mapped at sea</div>
      <Head>Length by type (km, measured on the map)</Head>
      <Rows rows={byClass} unit="km" />
      <Head>Longest named cables</Head>
      <Rows rows={longest} unit="km" />
      <div className={`mt-2 text-[10px] ${muted}`}>Lengths are measured along the mapped routes (great-circle, computed here); a mapped subset, well covered around Europe.</div>
    </Card>
  );
}

function PlantsWorldCard({ iso3 }: { iso3?: string }) {
  const wp = useFile<WorldPlantsFile>("worldPlants");
  const status = useApp((s) => s.plantStatus);
  if (!wp) return <Card title="Power plants worldwide" note="loading">…</Card>;
  return (
    <PlantsCard
      title={iso3 ? "Power plants here (GEM)" : "World power plants"}
      data={iso3 ? (wp.countries[iso3] ?? {}) : wp.world}
      status={status}
      onStatus={(st) => actions.setPlantStatus(st as PlantStatus)}
    />
  );
}

/** The US layers: only for the US (or no country selected). */
function UsStats({ id, iso3 }: { id: LayerId; iso3?: string }) {
  const plants = useFile<UsPlantsFile>(id === "plantsUS" ? "usPlants" : null);
  const turbines = useFile<UsTurbinesFile>(id === "turbinesUS" ? "usTurbines" : null);
  const queue = useFile<UsQueueFile>(id === "usQueue" ? "usQueue" : null);
  const status = useApp((s) => s.plantStatus);
  const names = useStateNames();
  if (iso3 && iso3 !== "USA") return null;
  if (plants) return <UsPlantsCard f={plants} status={status} onStatus={(st) => actions.setPlantStatus(st as PlantStatus)} />;
  if (turbines) return <UsTurbinesCard t={turbines} names={names} />;
  if (queue)
    return (
      <>
        <UsQueueCard q={queue} />
        <UsQueueStatesCard q={queue} names={names} />
      </>
    );
  return null;
}

function LiveGridsCards() {
  const us = useFile<UsFile>("us");
  const br = useFile<BrazilFile>("brazil");
  const au = useFile<AemoFile>("aemo");
  const tw = useFile<TaiwanFile>("taiwan");
  const on = useFile<OntarioFile>("ontario");
  return (
    <>
      {us && <UsCard us={us} />}
      {br && <BrazilCard br={br} />}
      {au && <NemCard aemo={au} />}
      {tw && <TaiwanCard tw={tw} />}
      {on && <OntarioCard on={on} />}
    </>
  );
}

function DataCentresStats({ iso3 }: { iso3?: string }) {
  const dc = useFile<DataCentresFile>("datacentres");
  const world = useFile<WorldFile>("world");
  const names = useMemo(() => {
    const m = new Map((world?.features ?? []).map((f) => [f.properties.iso3, f.properties.name]));
    return (c: string) => m.get(c) ?? c;
  }, [world]);
  if (!dc) return null;
  if (iso3)
    return (
      <Card title="Data centres" note="OpenStreetMap" accent={[196, 150, 255]}>
        <div className="text-[22px] font-light tabular-nums text-slate-100">{dc.by_country[iso3] ?? 0}</div>
        <div className={`text-[10.5px] ${muted}`}>mapped here: a mapped subset, not a census</div>
      </Card>
    );
  return <DataCentresCard dc={dc} names={names} />;
}

function FinanceStats({ iso3 }: { iso3?: string }) {
  const f = useFile<FinanceFile>("gemFinance");
  if (!f) return null;
  const pick = (c: string) => actions.select({ kind: "country", iso3: c, iso2: Object.entries(ISO3).find(([, v]) => v === c)?.[0] }, "dashboard");
  return iso3 ? <FinanceCountryCard f={f} iso3={iso3} onPick={pick} /> : <FinanceWorldCard f={f} onPick={pick} />;
}

/** The cards of the layers that are on (in the current time mode), in the Layers panel's order. */
export function useStatsLayers(): LayerId[] {
  const layers = useApp((s) => s.layers);
  const mode = useApp((s) => s.mode);
  return LAYERS.filter((l) => STATS_LAYERS.has(l.id) && layers[l.id] && (!l.modes || l.modes.includes(mode))).map((l) => l.id);
}

/** Output per plant at the clock (24 h): the largest producers now and what the file covers. */
function PlantOutputCard({ iso3 }: { iso3?: string }) {
  const slot = useApp((s) => s.slot);
  const want = useApp((s) => s.day);
  const region = useApp((s) => s.dayRegion);
  const index = useFile<{ all: string[] }>(dayIndexKey(region));
  const date = want && index?.all.includes(want) ? want : (index?.all[index.all.length - 1] ?? null);
  const f = useFile<UnitOutputFile>(date ? unitOutKey(region, date) : null);
  const iso2 = iso3 ? Object.entries(ISO3).find(([, v]) => v === iso3)?.[0] : undefined;
  if (!f) return <Card title="Plant output">{date ? "Loading…" : "No day chosen."}</Card>;
  const k = Math.min(f.slots - 1, slot);
  const rows = f.plants
    .map((p, i) => ({ name: p[5], iso: p[3], fuel: f.fuels[p[2]], cap: p[4], mw: f.output[i][k] }))
    .filter((r) => (!iso2 || r.iso === iso2) && r.mw != null) as { name: string; iso: string; fuel: string; cap: number | null; mw: number }[];
  const total = rows.reduce((a, r) => a + r.mw, 0);
  const top = [...rows].sort((a, b) => b.mw - a.mw).slice(0, 10);
  const counts = Object.entries(f.countries).filter(([c]) => !iso2 || c === iso2);
  const units = counts.reduce((a, [, c]) => a + (c.units ?? 0), 0);
  const placed = counts.reduce((a, [, c]) => a + (c.placed ?? 0), 0);
  const max = top[0]?.mw || 1;
  return (
    <Card title="Plant output" note={`${region === "us" ? "EPA CAMPD, hourly" : "ENTSO-E per unit"} · ${f.date}`}>
      <div className="text-[22px] font-light text-slate-50">
        {(total / 1000).toFixed(1)} GW <span className={`text-[11px] ${muted}`}>from {rows.length} plants at the clock (sum, computed)</span>
      </div>
      <div className="mt-2 space-y-1">
        {top.map((r) => (
          <div key={r.name + r.iso} className="text-[11px]">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">
                {r.name} <span className={muted}>{r.iso}</span>
              </span>
              <span className="tabular-nums text-slate-100">{Math.round(r.mw).toLocaleString("en-US")} MW</span>
            </div>
            <div className="h-1 rounded bg-white/[0.06]">
              <div className="h-1 rounded" style={{ width: `${(100 * r.mw) / max}%`, background: rgbCss(FUEL_COLOR[r.fuel] ?? FUEL_COLOR.other) }} />
            </div>
          </div>
        ))}
      </div>
      {region === "us" ? (
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          Fossil units in EPA's trading programmes (over 25 MW): {units.toLocaleString("en-US")} units at {f.plants.length.toLocaleString("en-US")} plants, each plant's units summed (computed). Gross
          load, hour by hour; EPA publishes a quarter within 30 days after it ends, so the newest day is months back.
        </div>
      ) : (
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Units of 100 MW and more: {placed.toLocaleString("en-US")} of {units.toLocaleString("en-US")} placed on the map with the JRC Open Power Plants Database.
        {f.areas_without_data.length ? ` No output per unit this day from ${f.areas_without_data.join(", ")}.` : ""} Germany, the Nordics, Austria and Switzerland publish about five days late.
      </div>
      )}
    </Card>
  );
}

const iso2Of = (iso3?: string) => (iso3 ? Object.entries(ISO3).find(([, v]) => v === iso3)?.[0] : undefined);

/** EU ETS: verified CO2 of the installations in scope, the largest emitters and the activities. */
function EtsCard({ iso3 }: { iso3?: string }) {
  const f = useFile<EtsFile>("ets");
  const iso2 = iso2Of(iso3);
  if (!f) return <Card title="CO₂ per installation">Loading…</Card>;
  if (iso3 && !iso2) return null;
  const rows = iso2 ? f.rows.filter((r) => etsIn(iso2, r[0])) : f.rows;
  if (!rows.length) return <Card title="CO₂ per installation">No installation in the EU ETS here.</Card>;
  const k = f.years.length - 1;
  const total = rows.reduce((a, r) => a + (r[4][k] ?? 0), 0);
  const prev = rows.reduce((a, r) => a + (r[4][k - 1] ?? 0), 0);
  const placed = rows.filter((r) => r[5] != null).length;
  const byGroup = f.groups
    .map((g, i) => ({ key: g, label: g.replace(" (power, heat, industry)", ""), value: rows.filter((r) => r[3] === i).reduce((a, r) => a + (r[4][k] ?? 0), 0) / 1e6, color: rgbCss(ETS_COLOR[i]) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  const top = rows.slice(0, 10); // the file is sorted by the newest year
  const max = newestT(top[0]) || 1;
  return (
    <Card title="CO₂ per installation" note={`${iso2 === "GB" ? "UK ETS and EU ETS (NI)" : "EU ETS"}, verified · ${f.newest}`}>
      <div className="text-[22px] font-light text-slate-50">
        {mt(total)}{" "}
        <span className={`text-[11px] ${muted}`}>
          from {rows.length.toLocaleString("en-US")} installations (sum, computed){prev > 0 ? ` · ${f.newest - 1}: ${mt(prev)}` : ""}
        </span>
      </div>
      <Head>Largest emitters</Head>
      <div className="space-y-1">
        {top.map((r) => (
          <div key={r[0] + r[1]} className="text-[11px]">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">
                {r[2]} <span className={muted}>{iso2 ? (ETS_REGISTRY_NAME[r[0]] ?? "") : r[0]}{r[5] == null ? " · not on the map" : ""}</span>
              </span>
              <span className="tabular-nums text-slate-100">{mt(newestT(r) ?? 0)}</span>
            </div>
            <div className="h-1 rounded bg-white/[0.06]">
              <div className="h-1 rounded" style={{ width: `${(100 * (newestT(r) ?? 0)) / max}%`, background: rgbCss(ETS_COLOR[r[3]]) }} />
            </div>
          </div>
        ))}
      </div>
      <Head>By activity, Mt</Head>
      <Rows rows={byGroup} unit="Mt" />
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Verified emissions (t CO₂e) as the EU Union Registry lists them on {f.snapshot}; aircraft, shipping and the ETS2 fuel suppliers left out. {placed.toLocaleString("en-US")} of{" "}
        {rows.length.toLocaleString("en-US")} installations are on the map: those the EEA industrial register gives an ETS id for (no placing by name or address).
        {f.uk && (!iso2 || iso2 === "GB") ? ` Great Britain: ${f.uk.source}, recorded emissions per installation; the report gives no position or activity.` : ""}
      </div>
    </Card>
  );
}

/** Grid capacity: GB's TEC register, the Dutch capacity map, Spain's node capacities, and six more countries. */
function ConnectCards({ iso3 }: { iso3?: string }) {
  const f = useFile<ConnectFile>("connect");
  if (!f) return <Card title="Connecting to the grid">Loading…</Card>;
  const show = (code: string) => !iso3 || iso3 === code;
  const any = ["GBR", "NLD", "ESP", "FRA", "ITA", "BEL", "PRT", "IRL", "POL", ...CONNECT_EU.map((c) => ISO3[connectEuCountry(c)])].some(show);
  if (!any) return null;
  return (
    <>
      {show("GBR") && <GbConnectCard f={f} />}
      {show("NLD") && <NlConnectCard f={f} />}
      {show("ESP") && <EsConnectCard f={f} />}
      {show("FRA") && <FrConnectCard />}
      {show("ITA") && <ItConnectCard />}
      {show("BEL") && <BeConnectCard />}
      {show("PRT") && <PtConnectCard />}
      {show("IRL") && <IeConnectCard />}
      {show("POL") && <PlConnectCard />}
      {CONNECT_EU.filter((c) => show(ISO3[connectEuCountry(c)])).map((c) => (
        <ConnectEuCard key={c} cc={c} />
      ))}
    </>
  );
}

function GbConnectCard({ f }: { f: ConnectFile }) {
  const g = f.gb;
  const waiting = (p: (typeof g.projects)[number]) => Math.max(0, p[2] - p[3]);
  const total = g.projects.reduce((a, p) => a + waiting(p), 0);
  const connected = g.projects.reduce((a, p) => a + p[3], 0);
  const byType = g.types
    .map((t, i) => ({ key: t, label: t, value: g.projects.filter((p) => p[4] === i).reduce((a, p) => a + waiting(p), 0) / 1000, color: rgbCss(GB_TYPE_COLOR[t] ?? GB_TYPE_COLOR.Other) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  const byStatus = g.statuses
    .map((st, i) => ({ key: st, label: st, value: g.projects.filter((p) => p[5] === i).reduce((a, p) => a + waiting(p), 0) / 1000 }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  const years = new Map<string, number>();
  for (const p of g.projects) if (p[6] && waiting(p) > 0) years.set(p[6].slice(0, 4), (years.get(p[6].slice(0, 4)) ?? 0) + waiting(p));
  const ys = [...years.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  const top = Math.max(1, ...ys.map(([, v]) => v));
  return (
    <Card title="Connecting to the grid · Great Britain" note={`NESO TEC register · ${g.date}`}>
      <div className="text-[22px] font-light text-slate-50">
        {gwText(total)} <span className={`text-[11px] ${muted}`}>waiting to connect to the transmission grid; {gwText(connected)} of these projects already connected (sums, computed)</span>
      </div>
      <Head>Waiting, by type (first listed), GW</Head>
      <Rows rows={byType} unit="GW" />
      <Head>By status, GW</Head>
      <Rows rows={byStatus} unit="GW" />
      <Head>By the year the capacity takes effect</Head>
      <div className="flex h-14 items-end gap-[2px]">
        {ys.map(([y, v]) => (
          <div key={y} className="flex-1" title={`${y}: ${gwText(v)}`}>
            <div className="rounded-t-sm bg-[rgb(206,138,72)]" style={{ height: `${(100 * v) / top}%` }} />
          </div>
        ))}
      </div>
      <div className={`flex justify-between text-[9.5px] ${muted}`}>
        <span>{ys[0]?.[0]}</span>
        <span>{ys[ys.length - 1]?.[0]}</span>
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Each project's cumulative capacity minus what is connected; a hybrid counts under its first listed type. Requests, not plants being built. Sites are placed only where named after a GSP in
        NESO's lookup.
      </div>
    </Card>
  );
}

function NlConnectCard({ f }: { f: ConnectFile }) {
  const areas = f.nl.areas.filter((a, i, all) => all.findIndex((b) => b.id === a.id) === i); // multi-part areas once
  const count = (side: "offtake" | "feedin", k: number) => areas.filter((a) => a[side] === k).length;
  const q = (side: "queue_offtake_mw" | "queue_feedin_mw") => areas.reduce((a, x) => a + (x[side] ?? 0), 0);
  return (
    <Card title="Connecting to the grid · Netherlands" note="Netbeheer Nederland capaciteitskaart">
      {(["offtake", "feedin"] as const).map((side) => (
        <div key={side} className="mb-2">
          <div className="text-[11px] text-slate-200">{side === "offtake" ? "New demand" : "New generation"}</div>
          <div className="mt-0.5 flex h-[8px] overflow-hidden rounded-sm">
            {[0, 1, 2, 3].map((k) => (
              <div key={k} title={`${f.nl.status[k]}: ${count(side, k)} areas`} style={{ width: `${(100 * count(side, k)) / areas.length}%`, background: rgbCss(NL_COLOR[k]) }} />
            ))}
          </div>
          <div className={`text-[10px] ${muted}`}>
            {count(side, 3)} of {areas.length} areas short of capacity · queue {gwText(q(side === "offtake" ? "queue_offtake_mw" : "queue_feedin_mw"))} (sum over the areas, computed)
          </div>
        </div>
      ))}
      <div className={`text-[10px] leading-snug ${muted}`}>The regional operators' supply areas (Liander, Stedin, Enexis and others); TenneT's own high-voltage map is not included.</div>
    </Card>
  );
}

function EsConnectCard({ f }: { f: ConnectFile }) {
  const nodes = f.es.nodes.filter((n) => n[5] != null);
  const free = nodes.filter((n) => (n[5] ?? 0) > 0);
  const top = [...free].sort((a, b) => (b[5] ?? 0) - (a[5] ?? 0)).slice(0, 10);
  const max = top[0]?.[5] || 1;
  return (
    <Card title="Connecting to the grid · Spain" note={`Red Eléctrica · ${f.es.date}`}>
      <div className="text-[22px] font-light text-slate-50">
        {free.length} <span className={`text-[11px] ${muted}`}>of {nodes.length} transmission nodes have room for new demand (count, computed)</span>
      </div>
      <Head>Most room for new demand, MW</Head>
      <div className="space-y-1">
        {top.map((n) => (
          <div key={n[0]} className="text-[11px]">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">
                {n[0]} <span className={muted}>{n[2]}</span>
              </span>
              <span className="tabular-nums text-slate-100">{Math.round(n[5] ?? 0).toLocaleString("en-US")} MW</span>
            </div>
            <div className="h-1 rounded bg-white/[0.06]">
              <div className="h-1 rounded bg-[rgb(52,120,108)]" style={{ width: `${(100 * (n[5] ?? 0)) / max}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Access capacity available for new requests at the node for demand without a power-electronics interface (REE's "no CEP" column); nodes sharing a zone share it, so the values do not add up.
        REE publishes no positions: the nodes are not drawn. {f.es.nodes.filter((n) => n[8]).length} nodes go to a capacity tender.
      </div>
    </Card>
  );
}

/** Global Renewables Watch per country: turbines and solar arrays found, solar area (computed). */
function GrwCard({ iso3 }: { iso3?: string }) {
  const f = useFile<{ release: string; countries: Record<string, Record<string, Record<string, [number, number, number | null]>>> }>("grwCountries");
  const names = useFile<{ features: { properties: { iso3: string; name: string } }[] }>("world");
  if (!f) return <Card title="Wind and solar seen from space">Loading…</Card>;
  const latest = (d?: Record<string, [number, number, number | null]>) => {
    if (!d) return [0, 0] as const;
    const v = Object.values(d).reduce((a, x) => [a[0] + x[0], a[1] + x[1]] as [number, number], [0, 0] as [number, number]);
    return v;
  };
  const rows = Object.entries(f.countries)
    .filter(([k]) => k !== "none" && (!iso3 || k === iso3))
    .map(([k, v]) => ({ k, wind: latest(v.wind)[0], solar: latest(v.solar)[0], km2: latest(v.solar)[1] }));
  const tot = rows.reduce((a, r) => [a[0] + r.wind, a[1] + r.solar, a[2] + r.km2], [0, 0, 0]);
  const name = (k: string) => names?.features.find((x) => x.properties.iso3 === k)?.properties.name ?? k;
  const top = [...rows].sort((a, b) => b.wind - a.wind).slice(0, 6);
  const topSolar = [...rows].sort((a, b) => b.km2 - a.km2).slice(0, 6);
  return (
    <Card title="Wind and solar seen from space" note={`Global Renewables Watch · ${f.release}`}>
      <div className="text-[13px] text-slate-100 tabular-nums">
        {tot[0].toLocaleString("en-US")} turbines · {tot[1].toLocaleString("en-US")} solar arrays ({Math.round(tot[2]).toLocaleString("en-US")} km²)
      </div>
      {!iso3 && (
        <>
          <Head>Most turbines</Head>
          <Rows rows={top.map((r) => ({ key: r.k, label: name(r.k), value: r.wind, color: "rgb(72,222,184)" }))} unit="" />
          <Head>Most solar area (km²)</Head>
          <Rows rows={topSolar.map((r) => ({ key: r.k, label: name(r.k), value: r.km2, color: "rgb(255,214,72)" }))} unit="km²" />
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Counted as found in satellite images by Microsoft&apos;s models (not registers); country = the outline holding each feature&apos;s centre; offshore features outside every
        outline are counted in the total only; solar area computed from the polygons.
      </div>
    </Card>
  );
}

/** TYNDP 2024 projects: counts by status (as drawn), commissioning years, the largest by capacity. */
function TyndpCard({ iso3 }: { iso3?: string }) {
  const f = useFile<TyndpFile>("tyndp");
  if (!f) return <Card title="Planned grid projects">Loading…</Card>;
  const iso2 = iso3 ? Object.entries(ISO3).find(([, b]) => b === iso3)?.[0] : undefined;
  const xs = iso2 ? f.features.filter((x) => x.country === iso2) : f.features;
  if (!xs.length) return <Card title="Planned grid projects">No TYNDP 2024 investment drawn here.</Card>;
  const rows = f.statuses
    .map((s, i) => ({ key: s, label: s, value: xs.filter((x) => x.status === i).length, color: rgbCss(TYNDP_STYLE[s]?.[0] ?? [120, 128, 140]) }))
    .filter((r) => r.value > 0);
  const big = [...xs].filter((x) => x.capacity_mw).sort((a, b) => (b.capacity_mw ?? 0) - (a.capacity_mw ?? 0)).slice(0, 6);
  return (
    <Card title="Planned grid projects" note="ENTSO-E TYNDP 2024">
      <Rows rows={rows} unit="items" />
      {big.length > 0 && (
        <>
          <Head>Largest by capacity</Head>
          {big.map((x, i) => (
            <div key={i} className="flex justify-between gap-2 text-[11px]">
              <span className="truncate text-slate-200">
                {x.investment ?? x.project} <span className={muted}>{x.year}</span>
              </span>
              <span className="tabular-nums text-slate-100">{(x.capacity_mw ?? 0).toLocaleString("en-US")} MW</span>
            </div>
          ))}
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        One item per investment of a transmission project (and per storage project) as the TYNDP map publishes it; capacities as the promoters submitted them, not summed.
      </div>
    </Card>
  );
}

/** US industrial emitters (EPA GHGRP): total, by sector, the largest. */
function EvEuStats({ iso3 }: { iso3?: string }) {
  const f = useFile<EvEuFile>("evEu");
  if (!f) return <Card title="EV charging">Loading…</Card>;
  const iso2 = iso2Of(iso3);
  if (iso3 && !iso2) return null;
  return <EvEuCard f={f} iso2={iso2} />;
}

function GhgrpCard() {
  const f = useFile<GhgrpFile>("ghgrp");
  if (!f) return <Card title="US industrial emitters">Loading…</Card>;
  const total = f.points.reduce((a, p) => a + p[2], 0);
  const rows = f.sectors
    .map((s, i) => ({ key: s, label: s, value: f.points.filter((p) => p[3] === i).reduce((a, p) => a + p[2], 0) / 1e6, color: rgbCss(ghgrpColor(s)) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  return (
    <Card title="US industrial emitters" note={`EPA GHGRP · ${f.year}`}>
      <div className="text-[22px] font-light text-slate-50">
        {(total / 1e6).toFixed(0)} Mt <span className={`text-[11px] ${muted}`}>CO₂e from {f.points.length.toLocaleString("en-US")} facilities (sum, computed)</span>
      </div>
      <Head>By sector (first listed)</Head>
      <Rows rows={rows} unit="Mt" />
      <Head>Largest</Head>
      {f.points.slice(0, 6).map((p, i) => (
        <div key={i} className="flex justify-between gap-2 text-[11px]">
          <span className="truncate text-slate-200">
            {p[4]} <span className={muted}>{p[5]}</span>
          </span>
          <span className="tabular-nums text-slate-100">{(p[2] / 1e6).toFixed(1)} Mt</span>
        </div>
      ))}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>Reported direct emissions (AR4 GWP) of the direct emitters (reporting threshold 25,000 t CO₂e a year); suppliers and oil and gas onshore production are reported apart and not drawn.</div>
    </Card>
  );
}

/** US public EV fast chargers: the total, by state and the largest networks (sums, computed). */
function EvChargersCard() {
  const f = useFile<EvChargersFile>("evChargers");
  const names = useStateNames();
  if (!f) return <Card title="EV fast chargers">Loading…</Card>;
  const [stations, dcStations, l2, dc] = f.total;
  const col = rgbCss(EV_COLOR);
  const states = Object.entries(f.states)
    .filter(([, v]) => v[3] > 0)
    .sort((a, b) => b[1][3] - a[1][3]);
  return (
    <Card title="EV fast chargers · US" note={`NREL AFDC · ${f.fetched.slice(0, 10)}`}>
      <div className="text-[22px] font-light text-slate-50">
        {dc.toLocaleString("en-US")} <span className={`text-[11px] ${muted}`}>DC fast ports at {dcStations.toLocaleString("en-US")} stations</span>
      </div>
      <div className={`text-[10.5px] ${muted}`}>
        {stations.toLocaleString("en-US")} public charging stations in all, {l2.toLocaleString("en-US")} level 2 ports
      </div>
      <Head>DC fast ports by state</Head>
      <Rows rows={states.slice(0, 8).map(([code, v]) => ({ key: code, label: names(code), value: v[3], color: col }))} unit="" />
      <Head>Largest networks</Head>
      <Rows rows={f.by_network.slice(0, 6).map(([n, , ports]) => ({ key: n, label: n, value: ports, color: col }))} unit="" />
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Public, open stations in NREL&apos;s Alternative Fuels Data Center; ports as published, totals per state and network are sums (computed).
      </div>
    </Card>
  );
}

/** Climate TRACE: modelled CO2e of the facilities in scope, the largest and the sum per group. */
function UsSolarCard() {
  const f = useFile<UsSolarFile>("usSolar");
  const names = useStateNames();
  const data = useMemo(() => {
    if (!f) return null;
    const byState = new Map<string, number>();
    const byAxis = new Map<string, number>();
    let total = 0;
    for (const s of f.sites) {
      const mw = s[2] ?? 0;
      total += mw;
      if (s[6]) byState.set(s[6], (byState.get(s[6]) ?? 0) + mw);
      const axis = solarCat(f, "p_axis", s[8]) ?? "not given";
      byAxis.set(axis, (byAxis.get(axis) ?? 0) + mw);
    }
    const largest = [...f.sites].sort((a, b) => (b[2] ?? 0) - (a[2] ?? 0)).slice(0, 6);
    return { total, byState: [...byState.entries()].sort((a, b) => b[1] - a[1]), byAxis: [...byAxis.entries()].sort((a, b) => b[1] - a[1]), largest };
  }, [f]);
  if (!f || !data) return <Card title="US solar farms">Loading…</Card>;
  const sun = rgbCss(FUEL_COLOR.solar);
  return (
    <Card title="US solar farms" note={`USPVDB ${f.release}`}>
      <div className="text-[22px] font-light text-slate-50">
        {(data.total / 1000).toFixed(1)} GW <span className={`text-[11px] ${muted}`}>AC in {f.sites.length.toLocaleString("en-US")} arrays (sum, computed)</span>
      </div>
      <Head>By state</Head>
      <Rows rows={data.byState.slice(0, 8).map(([code, mw]) => ({ key: code, label: names(code), value: mw / 1000, color: sun }))} unit="GW" />
      <Head>By tracking</Head>
      <div className="text-[11px] text-slate-300">{data.byAxis.slice(0, 3).map(([a, mw]) => `${a} ${Math.round((100 * mw) / data.total)} %`).join(" · ")}</div>
      <Head>Largest</Head>
      {data.largest.map((s, i) => (
        <div key={i} className="flex justify-between gap-2 text-[11px]">
          <span className="truncate text-slate-200">
            {s[5] ?? "Unnamed"} <span className={muted}>{s[6]}</span>
          </span>
          <span className="tabular-nums text-slate-100">{s[2] != null ? `${s[2].toLocaleString("en-US")} MW` : "–"}</span>
        </div>
      ))}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Ground-mounted PV of 1 MW (DC) and more, mapped from aerial imagery; AC capacity as published, sums and shares computed. Its own count, not EIA&apos;s: the US power
        plants layer lists generators.
      </div>
    </Card>
  );
}

function OffshoreWindCard({ iso3 }: { iso3?: string }) {
  const f = useFile<OffshoreWindFile>("offshoreWind");
  if (!f) return <Card title="Offshore wind farms">Loading…</Card>;
  const farms = iso3 ? f.farms.filter((x) => x.iso3 === iso3) : f.farms;
  const areas = farms.filter((x) => x.polygons);
  if (!farms.length) return <Card title="Offshore wind farms">No farm listed here by EMODnet.</Card>;
  const rows = f.statuses
    .map((s) => ({ key: s, label: OFFSHORE_LABEL[s] ?? s, value: areas.filter((x) => offshoreStatus(f, x) === s).length, color: rgbCss(OFFSHORE_STYLE[s]?.[0] ?? [120, 128, 140]) }))
    .filter((r) => r.value > 0);
  const byCountry = new Map<string, number>();
  for (const x of areas) if (offshoreStatus(f, x) === "Production") byCountry.set(x.country ?? "?", (byCountry.get(x.country ?? "?") ?? 0) + 1);
  const countries = [...byCountry.entries()].sort((a, b) => b[1] - a[1]);
  const pts = farms.length - areas.length;
  return (
    <Card title="Offshore wind farms" note="EMODnet Human Activities">
      <Rows rows={rows} unit="areas" />
      {!iso3 && countries.length > 0 && (
        <>
          <Head>Operating areas by country</Head>
          <div className="text-[11px] text-slate-300">{countries.slice(0, 8).map(([c, n]) => `${c} ${n}`).join(" · ")}</div>
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Farm areas counted as published. Capacity is shown per farm on hover and not summed: EMODnet lists some farms once per phase with the whole farm&apos;s MW (Hornsea
        Project 2 four times at 1,386 MW). {pts > 0 ? `${pts} more farms are published as points only (mostly planned), drawn as rings and not counted here. ` : ""}Planned
        areas include zones offered for tender. CETMAR for EMODnet, CC BY 4.0.
      </div>
    </Card>
  );
}

function CtraceCard({ iso3 }: { iso3?: string }) {
  const f = useFile<CtraceFile>("ctrace");
  if (!f) return <Card title="Emissions per facility">Loading…</Card>;
  const rows = iso3 ? f.rows.filter((r) => r[2] === iso3) : f.rows;
  if (!rows.length) return <Card title="Emissions per facility">No facility of {(f.threshold_t / 1e6).toFixed(1)} Mt or more here.</Card>;
  const total = rows.reduce((a, r) => a + r[5], 0);
  const byGroup = f.groups
    .map((g, i) => ({ key: g, label: g, value: rows.filter((r) => f.group_of[r[4]] === i).reduce((a, r) => a + r[5], 0) / 1e6, color: rgbCss(CT_COLOR[i]) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  const top = rows.slice(0, 10);
  const max = top[0]?.[5] || 1;
  return (
    <Card title="Emissions per facility" note={`Climate TRACE, modelled · ${f.year}`}>
      <div className="text-[22px] font-light text-slate-50">
        {mt(total)} <span className={`text-[11px] ${muted}`}>CO₂e from {rows.length.toLocaleString("en-US")} facilities (sum, computed)</span>
      </div>
      <Head>Largest emitters</Head>
      <div className="space-y-1">
        {top.map((r, i) => (
          <div key={i} className="text-[11px]">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">
                {r[3] || subsectorLabel(f.subsectors[r[4]])} <span className={muted}>{iso3 ? subsectorLabel(f.subsectors[r[4]]) : r[2]}</span>
              </span>
              <span className="tabular-nums text-slate-100">{mt(r[5])}</span>
            </div>
            <div className="h-1 rounded bg-white/[0.06]">
              <div className="h-1 rounded" style={{ width: `${(100 * r[5]) / max}%`, background: rgbCss(CT_COLOR[f.group_of[r[4]]]) }} />
            </div>
          </div>
        ))}
      </div>
      <Head>By sector, Mt CO₂e</Head>
      <Rows rows={byGroup} unit="Mt" />
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Climate TRACE models each asset's emissions (CO₂e, 100-year GWP) from satellites and other data; these are estimates, not reported figures. Facilities of{" "}
        {(f.threshold_t / 1e6).toFixed(1)} Mt and more in power, manufacturing, fossil-fuel operations and mining; oil and gas production is one figure per basin.
      </div>
    </Card>
  );
}

/** LNG send-out per terminal on the newest gas day, with each terminal's last 30 days. */
export function LngTerminalsCard({ iso2 }: { iso2?: string }) {
  const f = useFile<LngTerminalsFile>("lngTerminals");
  if (!f) return <Card title="LNG terminals">Loading…</Card>;
  const ts = f.terminals.filter((t) => !iso2 || t.country === iso2);
  if (!ts.length) return iso2 ? null : <Card title="LNG terminals">No terminal data.</Card>;
  const rows = ts
    .map((t) => ({ t, d: lngDay(t, f.date) }))
    .sort((a, b) => (b.d?.[1] ?? -1) - (a.d?.[1] ?? -1));
  const total = rows.reduce((a, r) => a + (r.d?.[1] ?? 0), 0);
  const top = Math.max(1, ...ts.flatMap((t) => t.series.map((s) => Math.max(s[1] ?? 0, s[3] ?? 0))));
  return (
    <Card title="LNG terminals" note={`GIE ALSI · gas day ${f.date}`} accent={LNG_SEND}>
      <div className="text-[22px] font-light text-slate-50">
        {gwhdText(total)} <span className={`text-[11px] ${muted}`}>sent out by {rows.length} terminals (sum, computed)</span>
      </div>
      <div className="mt-2 space-y-1.5">
        {rows.map(({ t, d }) => (
          <div key={t.eic} className="text-[11px]">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">
                {t.name.replace(/ LNG Terminal/, "")} {!iso2 && <span className={muted}>{t.country}</span>}
              </span>
              <span className="tabular-nums text-slate-100">
                {gwhdText(d?.[1])}
                <span className={muted}> / {d?.[3] != null ? Math.round(d[3]).toLocaleString("en-US") : "–"}</span>
              </span>
            </div>
            <svg viewBox={`0 0 ${t.series.length - 1 || 1} 10`} preserveAspectRatio="none" className="block h-[14px] w-full">
              <polyline
                fill="none"
                stroke={rgbCss(LNG_SEND)}
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                points={t.series.map((s, i) => (s[1] == null ? null : `${i},${10 - (10 * s[1]) / top}`)).filter(Boolean).join(" ")}
              />
            </svg>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Send-out into the grid / declared send-out (GWh/d); the line is each terminal's last {f.terminals[0]?.series.length ?? 30} gas days on one scale. Gas days run 06:00–06:00 CET. Terminals that reported no
        send-out are left out.
      </div>
    </Card>
  );
}

export function LayerStatsTab({ iso3 }: { iso3?: string }) {
  const ids = useStatsLayers();
  const seen = new Set<string>();
  return (
    <>
      <div className={`px-1 text-[10.5px] ${muted}`}>
        Figures for the datasets on the map{iso3 ? ", in this country" : ", worldwide"}. Switch datasets in the Datasets panel.
      </div>
      {ids.map((id) => {
        if (id in GEM_POINTS) return <GemPointsCard key={id} id={id} iso3={iso3} />;
        if (id in GEM_PIPES) return <GemPipesCard key={id} id={id} iso3={iso3} />;
        if (id === "financeCoal" || id === "financeGas") {
          if (seen.has("finance")) return null;
          seen.add("finance");
          return <FinanceStats key="finance" iso3={iso3} />;
        }
        if (id === "plantsWorld") return <PlantsWorldCard key={id} iso3={iso3} />;
        if (id === "plantOutput") return <PlantOutputCard key={id} iso3={iso3} />;
        if (id === "plantsUS" || id === "turbinesUS" || id === "usQueue") return <UsStats key={id} id={id} iso3={iso3} />;
        if (id === "liveGrids") return iso3 ? null : <LiveGridsCards key={id} />;
        if (id === "dataCentres") return <DataCentresStats key={id} iso3={iso3} />;
        if (id === "cables") return iso3 ? null : <CablesCard key={id} />;
        if (id === "ets") return <EtsCard key={id} iso3={iso3} />;
        if (id === "ctrace") return <CtraceCard key={id} iso3={iso3} />;
        if (id === "connect")
          return (
            <div key={id} className="contents">
              <RoomCard iso2={iso3 === "USA" ? "US" : iso2Of(iso3)} />
              <ConnectCards iso3={iso3} />
            </div>
          );
        if (id === "usOutages")
          return iso3 && iso3 !== "USA" ? null : (
            <div key={id} className="space-y-3">
              <UsOutagesCard />
              <Oe417Card />
            </div>
          );
        if (id === "water") return <WaterCard key={id} iso3={iso3} />;
        if (id === "protectedAreas") return <ProtectedCard key={id} iso3={iso3} />;
        if (id === "hydrogen") return <HydrogenCard key={id} iso3={iso3} />;
        if (id === "gasProjects") return <GasProjectsCard key={id} iso3={iso3} />;
        if (id === "mastrDE") return iso3 && iso3 !== "DEU" ? null : <MastrCountryCard key={id} />;
        if (id === "offshoreWind") return <OffshoreWindCard key={id} iso3={iso3} />;
        if (id in REGISTER_LAYERS) {
          const cc = REGISTER_LAYERS[id as keyof typeof REGISTER_LAYERS];
          return iso3 && iso3 !== ISO3[cc] ? null : <RegisterCard key={id} cc={cc} />;
        }
        if (id === "solarUS") return iso3 && iso3 !== "USA" ? null : <UsSolarCard key={id} />;
        if (id === "grw") return <GrwCard key={id} iso3={iso3} />;
        if (id === "tyndp") return <TyndpCard key={id} iso3={iso3} />;
        if (id === "ghgrpUS") return iso3 && iso3 !== "USA" ? null : <GhgrpCard key={id} />;
        if (id === "gasPipesUS") return iso3 && iso3 !== "USA" ? null : <UsGasCard key={id} />;
        if (id === "evChargersEU") return <EvEuStats key={id} iso3={iso3} />;
        if (id === "evChargersUS") return iso3 && iso3 !== "USA" ? null : <EvChargersCard key={id} />;
        if (id === "lngSendOut") return <LngTerminalsCard key={id} iso2={iso2Of(iso3)} />;
        return null;
      })}
      <SourcesCard
        items={[
          ["Layers", "Each card sums the file its layer draws (see the layer's own source on the card); docs/DATA_SOURCES.md lists every file and rule."],
        ]}
      />
    </>
  );
}
