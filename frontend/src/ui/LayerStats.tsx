// "On the map": the figures of the layers that are switched on, for the world or for the
// selected country. Every number is the layer file's own or a sum of it, said on the card.

import { useMemo, type ReactNode } from "react";

import { Card, SourcesCard } from "../components/CountryCards";
import { FinanceCountryCard, FinanceWorldCard } from "../components/FinanceCards";
import { BrazilCard, DataCentresCard, NemCard, OntarioCard, PlantsCard, TaiwanCard, UsCard } from "../components/WorldCards";
import { UsPlantsCard, UsQueueCard, UsQueueStatesCard, UsTurbinesCard, useStateNames } from "../components/UsCards";
import type { UsPlantsFile, UsQueueFile, UsTurbinesFile } from "../lib/us";
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

const fmt = (v: number) => (v >= 1000 ? Math.round(v).toLocaleString("en-US") : v >= 10 ? v.toFixed(0) : v.toFixed(1));

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
  const pick = (c: string) => actions.select({ kind: "country", iso3: c, iso2: Object.entries(ISO3).find(([, v]) => v === c)?.[0] }, "layers");
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
    <Card title="CO₂ per installation" note={`EU ETS, verified · ${f.newest}`}>
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
        Figures for the layers on the map{iso3 ? ", in this country" : ", worldwide"}. Switch layers in the Layers panel.
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
