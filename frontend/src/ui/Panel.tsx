// The context panel: what is selected (or the overview of where the camera looks), in tabs.
// Every card is the existing one from components/; this file only picks what to show.

import { useMemo, type ReactNode } from "react";

import {
  Card,
  GasCard,
  HistoryCard,
  LngCard,
  NowCard,
  OutageCard,
  SourcesCard,
  TradeCard,
  WeekCard,
  type EmberRow,
  type GasRow,
  type LngRow,
  type WeekFile,
} from "../components/CountryCards";
import { CaptureCard, MonthsCard, TimeOfDayCard, ZoneCard, ZoneRankingCard } from "../components/PriceCards";
import { FinanceCountryCard, FinanceWorldCard } from "../components/FinanceCards";
import { IrenaCountryCard, IrenaRankingCard } from "../components/IrenaCards";
import type { FinanceFile } from "../lib/finance";
import { AggregateCard, RankingCard, type RankRow } from "../components/TransitionCards";
import type { IrenaFile } from "../lib/irena";
import { AccessCard, BrazilCard, DataCentresCard, NemCard, OntarioCard, PlantsCard, TaiwanCard, UsCard, WorldCountryCard } from "../components/WorldCards";
import { FUEL_COLOR, FUEL_LABEL, STACK_ORDER, gw, power } from "../lib/energy";
import { priceMetricById, type PriceMetricId, type PricesFile } from "../lib/prices";
import { rgbCss } from "../lib/theme";
import { ISO3, metricById, type MetricId, type TransitionFile } from "../lib/transition";
import { NEM_NAME, latest, type AemoFile, type BrazilFile, type DataCentresFile, type OntarioFile, type TaiwanFile, type UsFile, type WorldStatsFile } from "../lib/world";
import type { WorldPlantsFile } from "../lib/worldPlants";
import { PRICE_STOPS, stopColor } from "../app/colors";
import { useFile } from "../app/data";
import { dayPower, marketTime, utc } from "../app/day";
import { BEAM_MIN_MW, HEX_KM } from "../app/geo";
import { actions, useApp } from "../app/store";
import type { CountriesFile, DayFile, FlowsFile, GasFile, OutagesFile, PlantsFile, ReferenceFile, StatsFile, WorldFile } from "../app/types";
import { LayerStatsTab, useStatsLayers } from "./LayerStats";
import { GAS_SOURCES, LIVE_SOURCES, PLANT_SOURCES, PRICE_SOURCES, WORLD_SOURCES, YEAR_SOURCES } from "./sources";

interface Dossier {
  fetched: string;
  gas: Record<string, GasRow>;
  lng?: Record<string, LngRow>;
  ember: Record<string, EmberRow>;
}
interface Monthly {
  months: string[];
  entities: Record<string, { renewables: (number | null)[]; wind_solar: (number | null)[]; coal: (number | null)[] }>;
}
interface Tab {
  id: string;
  label: string;
  body: () => ReactNode;
}
const PLANT_LABEL: Record<string, string> = { ...FUEL_LABEL, gas: "Gas & oil" };
const muted = "text-[#8d94a1]";

const medianOf = (v: number[]) => {
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** The replayed day and the slot on the clock (24 h mode), else nulls. */
function useDayNow() {
  const mode = useApp((s) => s.mode);
  const want = useApp((s) => s.day);
  const slot = useApp((s) => s.slot);
  const index = useFile<{ all: string[] }>(mode === "day" ? "dayIndex" : null);
  const date = mode === "day" ? (want && index?.all.includes(want) ? want : (index?.all[index.all.length - 1] ?? null)) : null;
  const day = useFile<DayFile>(date ? `day:${date}` : null) ?? null;
  const k = day ? Math.min(day.slots - 1, slot) : 0;
  const ts = (i: number) => (day ? new Date(Date.parse(day.start) + i * day.step_s * 1000).toISOString() : "");
  return { day, k, ts, timeOf: day ? marketTime : utc };
}

/** The year on the slider in the years mode, else the newest. */
function useYear(t: TransitionFile | undefined) {
  const mode = useApp((s) => s.mode);
  const yearK = useApp((s) => s.yearK);
  const colour = useApp((s) => s.colour);
  const k = t ? (mode === "years" ? Math.min(yearK, t.years.length - 1) : t.years.length - 1) : 0;
  const metric = metricById(colour.startsWith("tr_") ? (colour.slice(3) as MetricId) : "renewables");
  return { k, metric, year: t?.years[k] ?? "" };
}

/** The year the years mode shows (Ember's list), else none (= the newest). */
function useYearLabel(): string | undefined {
  const mode = useApp((s) => s.mode);
  const yearK = useApp((s) => s.yearK);
  const t = useFile<TransitionFile>(mode === "years" ? "transition" : null);
  return mode === "years" ? t?.years[yearK] : undefined;
}

function useNames() {
  const world = useFile<WorldFile>("world");
  const t = useFile<TransitionFile>("transition");
  return useMemo(() => {
    const m = new Map((world?.features ?? []).map((f) => [f.properties.iso3, f.properties.name]));
    return (code: string) => t?.entities[code]?.name ?? m.get(code) ?? code;
  }, [world, t]);
}

export default function Panel() {
  const sel = useApp((s) => s.selection);
  const region = useApp((s) => s.region);
  const countries = useFile<CountriesFile>("countries");
  const european = sel?.kind === "country" && !!sel.iso2 && !!countries?.countries.some((c) => c.iso === sel.iso2);
  if (sel?.kind === "zone") return <ZonePanel zone={sel.id} />;
  if (sel?.kind === "region") return <RegionPanel grid={sel.grid} id={sel.id} />;
  if (sel?.kind === "country" && european) return <CountryPanel iso={sel.iso2!} />;
  if (sel?.kind === "country" && sel.iso3) return <WorldCountryPanel code={sel.iso3} />;
  return region === "world" ? <WorldPanel /> : <EuropePanel />;
}

/** "On the map" first, while layers with figures are on. */
const withStats = (tabs: Tab[], on: boolean, iso3?: string): Tab[] =>
  on ? [{ id: "layers", label: "On the map", body: () => <LayerStatsTab iso3={iso3} /> }, ...tabs] : tabs;

function Frame({ title, sub, tabs, close = true }: { title: string; sub?: ReactNode; tabs: Tab[]; close?: boolean }) {
  const tab = useApp((s) => s.tab);
  const current = tabs.find((t) => t.id === tab) ?? tabs[0];
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start justify-between gap-2 px-4 pb-2 pt-3">
        <div className="min-w-0">
          <h2 className="truncate text-[17px] font-light tracking-wide text-slate-100">{title}</h2>
          {sub && <div className={`mt-0.5 text-[10.5px] ${muted}`}>{sub}</div>}
        </div>
        {close && (
          <button
            onClick={() => actions.select(null)}
            className="shrink-0 rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/10"
            aria-label="Back to the overview"
          >
            ✕
          </button>
        )}
      </div>
      {tabs.length > 1 && (
        <div className="flex gap-1 overflow-x-auto px-3 pb-2 [scrollbar-width:none]">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => useApp.setState({ tab: t.id })}
              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                t.id === current.id ? "bg-white/[0.14] text-slate-100" : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 pb-4">{current.body()}</div>
    </div>
  );
}

const Empty = ({ children }: { children: ReactNode }) => (
  <div className={`rounded-xl border border-white/[0.07] bg-[#0b0f16]/90 px-4 py-3 text-[11px] ${muted}`}>{children}</div>
);

// ---------------------------------------------------------------- Europe, no selection

function EuropePanel() {
  const mode = useApp((s) => s.mode);
  const colour = useApp((s) => s.colour);
  const stats = useFile<StatsFile>("stats");
  const outages = useFile<OutagesFile>(mode === "live" ? "outages" : null);
  const dossier = useFile<Dossier>("dossier");
  const { day, k, ts, timeOf } = useDayNow();
  // the EU figures carry the start of their interval (hourly in older archives)
  const euStep = day?.eu?.step_s ?? 3600;
  const euSlot = day ? Math.floor((k * day.step_s) / euStep) * (euStep / day.step_s) : 0;
  const eu = day ? (dayPower(day.eu, k, ts(euSlot)) ?? null) : (stats?.eu ?? null);
  // members without load at this slot (why the EU total is missing there)
  const late =
    day?.eu?.sum_of?.filter((iso) => {
      const c = day.countries[iso];
      return c?.load[k] == null || !Object.values(c.generation).some((col) => col[k] != null);
    }) ?? [];
  const ranking = useMemo(() => {
    if (!day) return [];
    return Object.entries(day.countries)
      .map(([iso, c]) => {
        const parts = STACK_ORDER.map((g) => [g, c.generation[g]?.[k] ?? 0] as [string, number]).filter(([, v]) => v > 0);
        return { iso, total: parts.reduce((a, [, v]) => a + v, 0), parts };
      })
      .filter((x) => x.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
  }, [day, k]);
  const zonePrices = day
    ? Object.values(day.prices).flatMap((z) => (z.values[k] != null ? [z.values[k] as number] : []))
    : Object.values(stats?.day_ahead_prices ?? {}).map((p) => p.eur_mwh);
  const euPrice = zonePrices.length ? { label: `median of ${zonePrices.length} zones`, value: medianOf(zonePrices) } : null;
  const statsOn = useStatsLayers().length > 0;
  const tabs: Tab[] = [
    {
      id: "now",
      label: "Now",
      body: () => (
        <>
          {eu ? (
            <NowCard
              now={eu}
              time={timeOf(eu.ts)}
              price={euPrice}
              footnote={`${eu.sum_of ? `EU figures: sum of the ${eu.sum_of.length} member states with data at this time. ` : ""}Price: the median of the bidding zones' day-ahead prices (computed).`}
            />
          ) : day ? (
            <Empty>
              No EU total at {timeOf(ts(k))}: {late.length ? `${late.join(", ")} had not reported this interval to ENTSO-E when the day was built` : "a member state's report is missing"}.
              The total counts only where every member reports, so it never jumps when one is late. The archive rebuilds the last two days every morning.
            </Empty>
          ) : (
            <Empty>Loading the newest interval…</Empty>
          )}
          {ranking.length > 0 && (
            <Card title="Largest producers now">
              <div className="space-y-1">
                {ranking.map((c) => (
                  <button
                    key={c.iso}
                    onClick={() => actions.select({ kind: "country", iso2: c.iso, iso3: ISO3[c.iso] })}
                    className="flex w-full items-center gap-2 text-[11px] tabular-nums hover:opacity-80"
                  >
                    <span className="w-6 text-left text-slate-300">{c.iso}</span>
                    <div className="flex h-[7px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
                      {c.parts.map(([g, v]) => (
                        <div key={g} style={{ width: `${(v / ranking[0].total) * 100}%`, background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }} />
                      ))}
                    </div>
                    <span className="w-12 text-right text-slate-200">{gw(c.total)}</span>
                  </button>
                ))}
              </div>
            </Card>
          )}
          {!day && outages && outages.units.length > 0 && <OutageCard totals={outages.total} units={outages.units} at={outages.at} />}
          <Hint>Click a country for its figures, a flow for its size.</Hint>
          <SourcesCard items={LIVE_SOURCES} />
        </>
      ),
    },
    { id: "week", label: "7 days", body: () => <WeekTab iso="EU" /> },
    { id: "prices", label: "Prices", body: () => <PriceOverview metricId={colour.startsWith("pr_") ? (colour.slice(3) as PriceMetricId) : "negative"} /> },
    {
      id: "gas",
      label: "Gas & LNG",
      body: () => (
        <>
          {dossier?.gas.EU && <GasCard gas={dossier.gas.EU} />}
          {dossier?.lng?.EU && <LngCard lng={dossier.lng.EU} />}
          {!dossier && <Empty>Loading GIE figures…</Empty>}
          <SourcesCard items={GAS_SOURCES} />
        </>
      ),
    },
    { id: "years", label: "25 years", body: () => <YearsTab code="EU" scope="europe" /> },
  ];
  return <Frame title="European Union" sub={mode === "day" && day ? `${day.date} · ${timeOf(ts(k))}` : "Live · ENTSO-E"} tabs={withStats(tabs, statsOn)} close={false} />;
}

function Hint({ children }: { children: ReactNode }) {
  return <div className={`px-1 text-[10.5px] ${muted}`}>{children}</div>;
}

function WeekTab({ iso }: { iso: string }) {
  const week = useFile<WeekFile & { country: string }>(`week:${iso}`);
  const { day, k, ts } = useDayNow();
  const marker = week && day && week.days.includes(day.date) ? Math.round((Date.parse(ts(k)) - Date.parse(week.start)) / (week.step_s * 1000)) : null;
  if (!week) return <Empty>Loading the last days…</Empty>;
  if (!week.load.some((v) => v != null)) return <Empty>No archived days for this country yet.</Empty>;
  return (
    <>
      <WeekCard week={week} marker={marker} />
      <SourcesCard items={[["Last days", "The daily archive (ENTSO-E, built every morning by .github/workflows/eu-days.yml): load, generation by source and day-ahead prices per 15-min interval."]]} />
    </>
  );
}

function PriceOverview({ metricId }: { metricId: PriceMetricId }) {
  const pf = useFile<PricesFile>("prices");
  if (!pf) return <Empty>Loading twelve months of prices…</Empty>;
  const metric = priceMetricById(metricId);
  return (
    <>
      <Hint>Colour the map by a price figure in the Layers panel; click a zone for its year.</Hint>
      <ZoneRankingCard zones={pf.zones} metric={metric} selected="" onPick={(zone) => actions.select({ kind: "zone", id: zone }, "prices")} />
      <SourcesCard items={PRICE_SOURCES(periodLabel(pf))} />
    </>
  );
}

const periodLabel = (pf: PricesFile) =>
  `${new Date(`${pf.period[0]}T12:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric" })} – ${new Date(`${pf.period[1]}T12:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}`;

function YearsTab({ code, scope }: { code: string; scope: "europe" | "world" | "one" }) {
  const t = useFile<TransitionFile>("transition");
  const names = useNames();
  const { k, metric, year } = useYear(t);
  const rows = useMemo<RankRow[]>(() => {
    if (!t || scope === "one") return [];
    const codes =
      scope === "europe"
        ? Object.values(ISO3)
        : Object.entries(t.entities)
            .filter(([, e]) => !e.aggregate)
            .sort((a, b) => (b[1].total_twh[k] ?? 0) - (a[1].total_twh[k] ?? 0))
            .slice(0, 30)
            .map(([c]) => c);
    return codes.flatMap((c) => {
      const e = t.entities[c];
      const v = e?.[metric.id][k];
      return e && v != null ? [{ key: c, name: e.name, value: v }] : [];
    });
  }, [t, scope, metric, k]);
  if (!t) return <Empty>Loading Ember's yearly data…</Empty>;
  const entity = t.entities[code];
  return (
    <>
      {entity ? <AggregateCard entity={entity} years={t.years} k={k} metric={metric} /> : <Empty>No Ember yearly figures for {names(code)}.</Empty>}
      {scope !== "one" && (
        <RankingCard
          title={scope === "world" ? `Largest power systems · ${year}` : `Europe · ${year}`}
          note={metric.label}
          rows={rows}
          metric={metric}
          selected={null}
          onPick={(c) => {
            const iso2 = Object.entries(ISO3).find(([, v]) => v === c)?.[0];
            actions.select({ kind: "country", iso3: c, iso2 }, "years");
          }}
        />
      )}
      <Hint>Press Years in the time control to play 2000 → today.</Hint>
      <SourcesCard items={YEAR_SOURCES} />
    </>
  );
}

// ---------------------------------------------------------------- one European country

function CountryPanel({ iso }: { iso: string }) {
  const mode = useApp((s) => s.mode);
  const plantStyle = useApp((s) => s.plantStyle);
  const countries = useFile<CountriesFile>("countries");
  const stats = useFile<StatsFile>("stats");
  const flows = useFile<FlowsFile>("flows");
  const outages = useFile<OutagesFile>(mode === "live" ? "outages" : null);
  const dossier = useFile<Dossier>("dossier");
  const reference = useFile<ReferenceFile>("reference");
  const plants = useFile<PlantsFile>("plants");
  const gas = useFile<GasFile>("gas");
  const irena = useFile<IrenaFile>("irena");
  const yearLabel = useYearLabel();
  const { day, k, ts, timeOf } = useDayNow();
  const name = countries?.countries.find((c) => c.iso === iso)?.name ?? iso;
  const now = day ? dayPower(day.countries[iso], k, ts(k)) : stats?.countries[iso];
  // the borders of this country, positive = import into it
  const trade = useMemo(() => {
    const rows = day
      ? day.borders.map((b) => ({ a: b.a, b: b.b, mw: b.values[k], ts: ts(k) }))
      : (flows?.borders ?? []).map((b) => ({ a: b.a, b: b.b, mw: b.mw, ts: b.ts }));
    return rows
      .filter((r) => (r.a === iso || r.b === iso) && r.mw != null && Math.abs(r.mw) >= 20)
      .map((r) => ({ other: r.a === iso ? r.b : r.a, mw: r.b === iso ? (r.mw as number) : -(r.mw as number), ts: r.ts }))
      .sort((a, b) => Math.abs(b.mw) - Math.abs(a.mw));
  }, [day, k, flows, iso]); // eslint-disable-line react-hooks/exhaustive-deps
  const zones = day
    ? Object.entries(day.prices)
        .filter(([, z]) => z.country === iso && z.values[k] != null)
        .map(([zone, z]) => [zone, z.values[k] as number] as [string, number])
    : Object.entries(stats?.day_ahead_prices ?? {})
        .filter(([, p]) => p.country === iso)
        .map(([zone, p]) => [zone, p.eur_mwh] as [string, number]);
  const priceTs = day ? ts(k) : Object.values(stats?.day_ahead_prices ?? {}).find((p) => p.country === iso)?.ts;
  const net = trade.length ? trade.reduce((a, t) => a + t.mw, 0) : null;
  const capacity = reference?.capacity[iso];
  const reservoir = reference?.reservoirs[iso];
  const byGroup = plants ? Object.entries(plants.by_country[iso] ?? {}).sort((x, y) => y[1][1] - x[1][1]) : [];
  const lng = gas?.lng.filter((g) => g[1] === iso) ?? [];
  const storages = gas?.storages.filter((g) => g[1] === iso) ?? [];
  const statsOn = useStatsLayers().length > 0;
  const tabs: Tab[] = [
    {
      id: "now",
      label: "Now",
      body: () => (
        <>
          {now ? (
            <NowCard
              now={now}
              time={timeOf(now.ts)}
              price={zones.length === 1 ? { label: zones[0][0], value: zones[0][1] } : null}
              netMw={net}
              footnote={iso === "GB" ? "Great Britain: Elexon, transmission-connected generation and national demand. Rooftop solar and small wind are not metered here." : undefined}
            />
          ) : (
            <Empty>No load or generation data from ENTSO-E for this country.</Empty>
          )}
          {zones.length > 1 && (
            <Card title="Day-ahead price" note={priceTs ? timeOf(priceTs) : undefined}>
              <div className="space-y-0.5">
                {zones.map(([zone, eur]) => (
                  <button
                    key={zone}
                    onClick={() => actions.select({ kind: "zone", id: zone }, "prices")}
                    className="flex w-full justify-between text-[11px] tabular-nums text-slate-200 hover:opacity-80"
                  >
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-sm" style={{ background: rgbCss(stopColor(PRICE_STOPS, Math.max(0, Math.min(250, eur))) ?? [60, 60, 60]) }} />
                      {zone}
                    </span>
                    <span>{eur.toFixed(1)} €/MWh</span>
                  </button>
                ))}
              </div>
            </Card>
          )}
          {trade.length > 0 && <TradeCard rows={trade} time={timeOf(trade[0].ts)} />}
          {!day && outages?.countries[iso] && (
            <OutageCard totals={outages.countries[iso]} units={outages.units.filter((u) => u.country === iso)} at={outages.at} />
          )}
          <SourcesCard items={LIVE_SOURCES} />
        </>
      ),
    },
    { id: "week", label: "7 days", body: () => <WeekTab iso={iso} /> },
    { id: "prices", label: "Prices", body: () => <CountryPrices iso={iso} /> },
    {
      id: "gas",
      label: "Gas & LNG",
      body: () => (
        <>
          {dossier?.gas[iso] && <GasCard gas={dossier.gas[iso]} />}
          {dossier?.lng?.[iso] && <LngCard lng={dossier.lng[iso]} />}
          {(lng.length > 0 || storages.length > 0) && (
            <Card title="Gas infrastructure" note="SciGRID_gas · 2021" accent={[255, 150, 92]}>
              {lng.length > 0 && (
                <div className="text-[11px] text-slate-200">
                  LNG terminals: <span className={muted}>{lng.map((g) => g[0]).join(", ")}</span>
                </div>
              )}
              {storages.length > 0 && <div className="mt-0.5 text-[11px] text-slate-200">Gas storage sites: {storages.length}</div>}
            </Card>
          )}
          {!dossier?.gas[iso] && !dossier?.lng?.[iso] && !lng.length && !storages.length && <Empty>No gas storage or LNG reported for {name}.</Empty>}
          <SourcesCard items={GAS_SOURCES} />
        </>
      ),
    },
    {
      id: "plants",
      label: "Plants",
      body: () => (
        <>
          {byGroup.length > 0 && (
            <Card title="Plants on the map" note="powerplantmatching">
              <div className="mb-2 flex gap-1">
                {(["bars", "beams"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => useApp.setState({ plantStyle: m })}
                    className={`rounded border px-2 py-0.5 text-[10px] ${plantStyle === m ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400"}`}
                  >
                    {m === "bars" ? "Columns" : "Beams & fields"}
                  </button>
                ))}
              </div>
              <div className={`mb-1.5 text-[10px] ${muted}`}>
                {plantStyle === "bars"
                  ? "Columns: units ≥ 10 MW, height ∝ √ installed capacity (not current output)"
                  : `Beams: plants ≥ ${BEAM_MIN_MW} MW. Fields: smaller units summed per ${HEX_KM * 2} km hexagon.`}
              </div>
              <div className="space-y-0.5">
                {byGroup.map(([g, [n, mw]]) => (
                  <div key={g} className="flex justify-between text-[11px] tabular-nums text-slate-200">
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(FUEL_COLOR[g]) }} />
                      {PLANT_LABEL[g]}
                    </span>
                    <span>
                      {power(mw)} <span className={muted}>· {n} units</span>
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {capacity && (
            <Card title="Installed capacity" note={`Energy-Charts · ${capacity.year}`}>
              <div className="space-y-1">
                {Object.entries(capacity.gw)
                  .filter(([, v]) => v > 0)
                  .sort((x, y) => y[1] - x[1])
                  .map(([g, v], _, all) => (
                    <div key={g}>
                      <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
                        <span>{FUEL_LABEL[g] ?? g}</span>
                        <span>{v.toFixed(1)} GW</span>
                      </div>
                      <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full" style={{ width: `${(v / all[0][1]) * 100}%`, background: rgbCss(FUEL_COLOR[g] ?? FUEL_COLOR.other) }} />
                      </div>
                    </div>
                  ))}
              </div>
            </Card>
          )}
          {irena && <IrenaCountryCard f={irena} iso3={ISO3[iso]} year={yearLabel} />}
          {reservoir && (
            <Card title="Hydro reservoirs" note={`ENTSO-E · week of ${reservoir.week}`} accent={[84, 156, 255]}>
              <div className="text-[22px] font-light tabular-nums text-slate-100">{reservoir.twh.toFixed(1)} TWh</div>
              {reservoir.year_ago_twh != null && <div className={`text-[10px] ${muted}`}>same week last year: {reservoir.year_ago_twh.toFixed(1)} TWh</div>}
            </Card>
          )}
          <SourcesCard items={PLANT_SOURCES} />
        </>
      ),
    },
    { id: "finance", label: "Finance", body: () => <FinanceTab iso3={ISO3[iso]} /> },
    {
      id: "years",
      label: "25 years",
      body: () => (
        <>
          {dossier?.ember[iso] && <HistoryCard ember={dossier.ember[iso]} />}
          <YearsTab code={ISO3[iso]} scope="one" />
        </>
      ),
    },
  ];
  return <Frame title={name} sub={mode === "day" && day ? `${day.date} · ${timeOf(ts(k))}` : undefined} tabs={withStats(tabs, statsOn, ISO3[iso])} />;
}

function CountryPrices({ iso }: { iso: string }) {
  const pf = useFile<PricesFile>("prices");
  if (!pf) return <Empty>Loading twelve months of prices…</Empty>;
  const zones = Object.keys(pf.zones).filter((z) => pf.zones[z].country === iso);
  if (!zones.length) return <Empty>No day-ahead price at ENTSO-E for this country.</Empty>;
  return (
    <>
      {zones.length > 1 && (
        <div className="flex flex-wrap gap-1">
          {zones.map((z) => (
            <button key={z} onClick={() => actions.select({ kind: "zone", id: z }, "prices")} className="rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-white/10">
              {z}
            </button>
          ))}
        </div>
      )}
      <ZoneBody pf={pf} zone={zones[0]} />
    </>
  );
}

function ZoneBody({ pf, zone }: { pf: PricesFile; zone: string }) {
  const z = pf.zones[zone];
  const colour = useApp((s) => s.colour);
  if (!z) return <Empty>No figures for {zone}.</Empty>;
  return (
    <>
      <ZoneCard zone={zone} z={z} period={periodLabel(pf)} />
      <TimeOfDayCard z={z} months={pf.months} />
      <MonthsCard months={pf.months} values={z.negative_by_month} />
      <CaptureCard z={z} />
      <ZoneRankingCard
        zones={pf.zones}
        metric={priceMetricById(colour.startsWith("pr_") ? (colour.slice(3) as PriceMetricId) : "negative")}
        selected={zone}
        onPick={(id) => actions.select({ kind: "zone", id }, "prices")}
      />
      <SourcesCard items={PRICE_SOURCES(periodLabel(pf))} />
    </>
  );
}

function ZonePanel({ zone }: { zone: string }) {
  const pf = useFile<PricesFile>("prices");
  const countries = useFile<CountriesFile>("countries");
  const country = countries?.countries.find((c) => c.iso === pf?.zones[zone]?.country)?.name;
  return (
    <Frame
      title={zone}
      sub={country && country !== zone ? `price zone of ${country}` : "price zone"}
      tabs={[{ id: "prices", label: "Prices", body: () => (pf ? <ZoneBody pf={pf} zone={zone} /> : <Empty>Loading twelve months of prices…</Empty>) }]}
    />
  );
}

// ---------------------------------------------------------------- the world

function WorldPanel() {
  const us = useFile<UsFile>("us");
  const br = useFile<BrazilFile>("brazil");
  const au = useFile<AemoFile>("aemo");
  const tw = useFile<TaiwanFile>("taiwan");
  const on = useFile<OntarioFile>("ontario");
  const wp = useFile<WorldPlantsFile>("worldPlants");
  const ws = useFile<WorldStatsFile>("worldStats");
  const dc = useFile<DataCentresFile>("datacentres");
  const status = useApp((s) => s.plantStatus);
  const liveOn = useApp((s) => s.layers.liveGrids);
  const irena = useFile<IrenaFile>("irena");
  const yearLabel = useYearLabel();
  const names = useNames();
  const access = ws ? latest(ws.access.WLD, ws.years) : null;
  const statsOn = useStatsLayers().length > 0;
  const tabs: Tab[] = [
    {
      id: "now",
      label: "Live grids",
      body: () => (
        <>
          {!liveOn && (
            <button onClick={() => actions.toggleLayer("liveGrids")} className="w-full rounded-lg border border-sky-400/30 px-3 py-1.5 text-left text-[11px] text-sky-200 hover:bg-sky-400/10">
              Show these grids' flows on the map
            </button>
          )}
          {us && <UsCard us={us} />}
          {br && <BrazilCard br={br} />}
          {au && <NemCard aemo={au} />}
          {tw && <TaiwanCard tw={tw} />}
          {on && <OntarioCard on={on} />}
          <SourcesCard items={WORLD_SOURCES.filter(([k]) => ["United States", "Brazil", "Australia", "Taiwan", "Ontario"].includes(k))} />
        </>
      ),
    },
    {
      id: "plants",
      label: "Plants",
      body: () => (
        <>
          {wp ? <PlantsCard title="World power plants" data={wp.world} status={status} onStatus={(st) => actions.setPlantStatus(st as typeof status)} /> : <Empty>Loading 183,000 plant units…</Empty>}
          <SourcesCard items={WORLD_SOURCES.filter(([k]) => k === "Power plants")} />
        </>
      ),
    },
    {
      id: "access",
      label: "Access",
      body: () => (
        <>
          {ws && <AccessCard stats={ws} names={names} onPick={(c) => actions.select({ kind: "country", iso3: c })} />}
          {dc && <DataCentresCard dc={dc} names={names} />}
          <SourcesCard items={WORLD_SOURCES.filter(([k]) => ["Access to electricity", "Data centres"].includes(k))} />
        </>
      ),
    },
    {
      id: "capacity",
      label: "Capacity",
      body: () =>
        irena ? (
          <>
            <IrenaRankingCard f={irena} year={yearLabel} names={names} onPick={(c) => actions.select({ kind: "country", iso3: c }, "capacity")} />
            <SourcesCard items={WORLD_SOURCES.filter(([k]) => k === "Installed capacity")} />
          </>
        ) : (
          <Empty>Loading IRENA's capacity statistics…</Empty>
        ),
    },
    { id: "finance", label: "Finance", body: () => <FinanceTab /> },
    { id: "years", label: "25 years", body: () => <YearsTab code="World" scope="world" /> },
  ];
  return <Frame title="World" sub={access ? `${access.value.toFixed(1)} % of people have electricity (${access.year}, World Bank)` : undefined} tabs={withStats(tabs, statsOn)} close={false} />;
}

function WorldCountryPanel({ code }: { code: string }) {
  const ws = useFile<WorldStatsFile>("worldStats");
  const dc = useFile<DataCentresFile>("datacentres");
  const t = useFile<TransitionFile>("transition");
  const monthly = useFile<Monthly>("monthly");
  const wp = useFile<WorldPlantsFile>("worldPlants");
  const status = useApp((s) => s.plantStatus);
  const irena = useFile<IrenaFile>("irena");
  const yearLabel = useYearLabel();
  const names = useNames();
  const name = names(code);
  const renewables = t?.entities[code] ? latest(t.entities[code].renewables, t.years) : null;
  const statsOn = useStatsLayers().length > 0;
  const tabs: Tab[] = [
    {
      id: "now",
      label: "Overview",
      body: () => (
        <>
          <WorldCountryCard
            code={code}
            name={name}
            stats={ws ?? null}
            dc={dc ?? null}
            renewables={renewables}
            monthly={monthly?.entities[code] ? { months: monthly.months, ...monthly.entities[code] } : null}
          />
          <SourcesCard items={WORLD_SOURCES.filter(([k]) => ["Access to electricity", "Data centres", "Renewables"].includes(k))} />
        </>
      ),
    },
    {
      id: "plants",
      label: "Plants",
      body: () =>
        wp ? (
          <PlantsCard title={`Power plants · ${name}`} data={wp.countries[code] ?? {}} status={status} onStatus={(st) => actions.setPlantStatus(st as typeof status)} />
        ) : (
          <Empty>Loading plants…</Empty>
        ),
    },
    {
      id: "capacity",
      label: "Capacity",
      body: () => (irena ? <IrenaCountryCard f={irena} iso3={code} year={yearLabel} /> : <Empty>Loading IRENA's capacity statistics…</Empty>),
    },
    { id: "finance", label: "Finance", body: () => <FinanceTab iso3={code} /> },
    { id: "years", label: "25 years", body: () => <YearsTab code={code} scope="one" /> },
  ];
  return <Frame title={name} tabs={withStats(tabs, statsOn, code)} />;
}

function RegionPanel({ grid, id }: { grid: "us" | "br" | "au" | "tw" | "on"; id: string }) {
  const us = useFile<UsFile>(grid === "us" ? "us" : null);
  const br = useFile<BrazilFile>(grid === "br" ? "brazil" : null);
  const au = useFile<AemoFile>(grid === "au" ? "aemo" : null);
  const tw = useFile<TaiwanFile>(grid === "tw" ? "taiwan" : null);
  const on = useFile<OntarioFile>(grid === "on" ? "ontario" : null);
  const title = grid === "us" ? (us?.regions[id]?.name ?? id) : grid === "br" ? (br?.subsystems[id]?.name ?? id) : grid === "tw" ? "Taiwan" : grid === "on" ? "Ontario" : (NEM_NAME[id] ?? id);
  const sub = grid === "us" ? "United States · EIA-930" : grid === "br" ? "Brazil · ONS" : grid === "tw" ? "Taipower · every unit" : grid === "on" ? "IESO · Canada" : "Australia · AEMO";
  const body = () => (
    <>
      {us && <UsCard us={us} />}
      {br && <BrazilCard br={br} />}
      {au && <NemCard aemo={au} />}
      {tw && <TaiwanCard tw={tw} />}
      {on && <OntarioCard on={on} />}
      <SourcesCard items={WORLD_SOURCES.filter(([k]) => k === (grid === "us" ? "United States" : grid === "br" ? "Brazil" : grid === "tw" ? "Taiwan" : grid === "on" ? "Ontario" : "Australia"))} />
    </>
  );
  return <Frame title={title} sub={sub} tabs={[{ id: "now", label: "Now", body }]} />;
}

/** Who finances coal and gas power: the world's rankings, or one country's money. */
function FinanceTab({ iso3 }: { iso3?: string }) {
  const f = useFile<FinanceFile>("gemFinance");
  const showing = useApp((s) => s.layers.financeCoal || s.layers.financeGas);
  if (!f) return <Empty>Loading GEM's finance trackers…</Empty>;
  const pick = (c: string) => actions.select({ kind: "country", iso3: c, iso2: Object.entries(ISO3).find(([, v]) => v === c)?.[0] }, "finance");
  return (
    <>
      {!showing && (
        <button
          onClick={() => useApp.setState((s) => ({ layers: { ...s.layers, financeCoal: true, financeGas: true }, story: null }))}
          className="w-full rounded-lg border border-amber-300/30 px-3 py-1.5 text-left text-[11px] text-amber-200 hover:bg-amber-300/10"
        >
          Show the money flows on the map
        </button>
      )}
      {iso3 ? <FinanceCountryCard f={f} iso3={iso3} onPick={pick} /> : <FinanceWorldCard f={f} onPick={pick} />}
      <SourcesCard
        items={[
          [
            "Finance",
            "Global Energy Monitor: Global Coal Project Finance Tracker and Gas Finance Tracker (CC BY 4.0). Each row is one financier's share of one deal for a coal unit, a gas plant or an LNG terminal. Computed: amounts in US$ million, summed per project, per financier, and per financier's home country and project country; deals marked stopped left out. Arrows on the map show money crossing borders, from the middle of the lending country to the money-weighted middle of the projects it financed (map placement).",
          ],
        ]}
      />
    </>
  );
}
