// The US panel's cards: EIA-860M capacity, additions and retirements, LBNL's queue, USWTDB
// turbines. Every figure is the file's own or a sum of it, said on the card.

import { useMemo, type ReactNode } from "react";

import { rgbCss, type RGB } from "../lib/theme";
import { US_TYPE_COLOR, US_TYPE_LABEL, US_TYPE_ORDER, gwText, queueColor, type UsPlantsFile, type UsQueueFile, type UsStatesFile, type UsTurbinesFile } from "../lib/us";
import { useFile } from "../app/data";
import { Card } from "./CountryCards";
import { PlantsCard } from "./WorldCards";

const muted = "text-[#8d94a1]";
const sum = (v: Record<string, number> | number[] | undefined) => Object.values(v ?? {}).reduce((a: number, x: number) => a + x, 0);
const Head = ({ children }: { children: ReactNode }) => <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>{children}</div>;
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;

/** State names from the Census outlines (codes until they arrive). */
export function useStateNames() {
  const states = useFile<UsStatesFile>("usStates");
  return useMemo(() => {
    const m = new Map((states?.states ?? []).map((s) => [s.code, s.name]));
    return (code: string) => m.get(code) ?? code;
  }, [states]);
}

interface Part {
  key: string;
  value: number;
  color: RGB;
  faint?: boolean;
  /** the fuel group, for the key under a chart */
  type?: string;
}
/** One labelled row: a bar of coloured parts, scaled to the largest row. */
function StackRow({ label, parts, max, total, onClick }: { label: string; parts: Part[]; max: number; total?: number; onClick?: () => void }) {
  const t = total ?? parts.reduce((a, p) => a + p.value, 0);
  const body = (
    <>
      <span className="w-[86px] shrink-0 truncate text-left text-slate-300">{label}</span>
      <span className="flex h-[7px] flex-1 overflow-hidden rounded-sm bg-white/[0.04]">
        <span className="flex h-full" style={{ width: `${(t / Math.max(1, max)) * 100}%` }}>
          {parts
            .filter((p) => p.value > 0)
            .map((p) => (
              <span key={p.key} title={`${p.key} ${gwText(p.value)}`} style={{ width: `${(p.value / (t || 1)) * 100}%`, background: rgbCss(p.color, p.faint ? 0.4 : 1) }} />
            ))}
        </span>
      </span>
      <span className="w-[58px] shrink-0 text-right text-slate-100">{gwText(t)}</span>
    </>
  );
  return onClick ? (
    <button onClick={onClick} className="flex w-full items-center gap-2 text-[11px] tabular-nums hover:opacity-80">
      {body}
    </button>
  ) : (
    <div className="flex items-center gap-2 text-[11px] tabular-nums">{body}</div>
  );
}

const fuelParts = (d: Record<string, number> | undefined, faint = false): Part[] =>
  US_TYPE_ORDER.map((k) => ({ key: `${US_TYPE_LABEL[k] ?? k}${faint ? " (planned)" : ""}`, value: d?.[k] ?? 0, color: US_TYPE_COLOR[k] ?? [150, 150, 150], faint, type: k }));

function FuelKey({ types }: { types: string[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[9px] text-slate-400">
      {types.map((k) => (
        <span key={k} className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: rgbCss(US_TYPE_COLOR[k] ?? [150, 150, 150]) }} />
          {US_TYPE_LABEL[k] ?? k}
        </span>
      ))}
    </div>
  );
}

/** Capacity by status and fuel (the status rows switch the map). */
export function UsPlantsCard({ f, state, status, onStatus }: { f: UsPlantsFile; state?: string; status: string; onStatus: (s: string) => void }) {
  return (
    <PlantsCard
      title={state ? `Power plants · ${state}` : "US power plants"}
      data={state ? (f.states[state] ?? {}) : f.totals}
      status={status}
      onStatus={onStatus}
      colors={US_TYPE_COLOR}
      labels={US_TYPE_LABEL}
      source={`EIA-860M · ${f.release}`}
      note={`Net summer capacity, EIA's measure. Operating = EIA's operating inventory (incl. standby and out of service); under construction = EIA's U, V and TS; planned = P, L and T; canceled or postponed units left out. ${state ? "" : "50 states and DC; Puerto Rico is on the map but not in this total. "}Click a row to show it on the map.`}
    />
  );
}

/** Installed capacity by fuel: the operating inventory. */
export function UsCapacityCard({ f }: { f: UsPlantsFile }) {
  const op = f.totals.operating ?? {};
  const rows = US_TYPE_ORDER.filter((k) => (op[k] ?? 0) > 0).sort((a, b) => (op[b] ?? 0) - (op[a] ?? 0));
  const detail = f.status_detail.operating ?? {};
  const standby = sum(detail.SB);
  const out = sum(detail.OA) + sum(detail.OS);
  return (
    <Card title="Installed capacity" note={`EIA-860M · ${f.release}`} accent={[255, 128, 72]}>
      <div className="flex items-baseline gap-2">
        <span className="text-[22px] font-light tabular-nums text-slate-100">{gwText(sum(op))}</span>
        <span className={`text-[10.5px] ${muted}`}>net summer, {f.units.operating?.toLocaleString("en-US")} generators</span>
      </div>
      <div className="mt-2 space-y-[3px]">
        {rows.map((k) => (
          <StackRow key={k} label={US_TYPE_LABEL[k] ?? k} parts={[{ key: k, value: op[k], color: US_TYPE_COLOR[k] }]} max={op[rows[0]]} />
        ))}
      </div>
      <Note>
        Of the total, {gwText(standby)} is on standby and {gwText(out)} out of service (EIA's SB, OA, OS). 50 states and DC, generators of 1 MW and more; fuel = EIA's energy source code, pumped storage and batteries as storage. Sums of EIA's units.
      </Note>
    </Card>
  );
}

/** Planned additions by year (under construction and planned) and retirements, past and planned. */
export function UsPipelineCard({ f }: { f: UsPlantsFile }) {
  const now = new Date().getUTCFullYear();
  const addYears = Object.keys(f.additions).filter((y) => Number(y) <= now + 6);
  const later = Object.keys(f.additions).filter((y) => Number(y) > now + 6);
  const laterSum = (st: string) => {
    const o: Record<string, number> = {};
    for (const y of later) for (const [k, v] of Object.entries(f.additions[y][st] ?? {})) o[k] = (o[k] ?? 0) + v;
    return o;
  };
  const adds = addYears.map((y) => ({ y, parts: [...fuelParts(f.additions[y].construction), ...fuelParts(f.additions[y].planned, true)] }));
  if (later.length) adds.push({ y: `${now + 7}+`, parts: [...fuelParts(laterSum("construction")), ...fuelParts(laterSum("planned"), true)] });
  const maxAdd = Math.max(1, ...adds.map((a) => a.parts.reduce((s, p) => s + p.value, 0)));
  const planned = Object.keys(f.retirements_planned).filter((y) => Number(y) >= now && Number(y) <= now + 9);
  const past = Object.keys(f.retired).filter((y) => Number(y) >= now - 9);
  const ret = [
    ...past.map((y) => ({ y, label: `${y}${Number(y) === now ? " so far" : ""}`, parts: fuelParts(f.retired[y]) })),
    ...planned.map((y) => ({ y: `p${y}`, label: `${y} planned`, parts: fuelParts(f.retirements_planned[y], true) })),
  ];
  const maxRet = Math.max(1, ...ret.map((a) => a.parts.reduce((s, p) => s + p.value, 0)));
  const used = US_TYPE_ORDER.filter((k) => [...adds, ...ret].some((a) => a.parts.some((p) => p.type === k && p.value > 0)));
  return (
    <>
      <Card title="Coming online" note={`EIA-860M · ${f.release}`} accent={[120, 222, 160]}>
        <div className={`mb-1.5 text-[10px] ${muted}`}>By planned operation year; solid = under construction, pale = planned.</div>
        <div className="space-y-[3px]">
          {adds.map((a) => (
            <StackRow key={a.y} label={a.y} parts={a.parts} max={maxAdd} />
          ))}
        </div>
        <FuelKey types={used} />
        <Note>
          Under construction {gwText(sum(f.totals.construction))}, planned {gwText(sum(f.totals.planned))} (net summer). EIA's monthly inventory lists only projects reported to it; the interconnection queue holds far more requests, most of which are never built.
        </Note>
      </Card>
      <Card title="Retiring" note={`EIA-860M · ${f.release}`} accent={[160, 146, 132]}>
        <div className={`mb-1.5 text-[10px] ${muted}`}>Retired by year (EIA's retired inventory), then the retirement years operators have reported (pale).</div>
        <div className="space-y-[3px]">
          {ret.map((a) => (
            <StackRow key={a.y} label={a.label} parts={a.parts} max={maxRet} />
          ))}
        </div>
        <Note>Planned retirements are operators' plans as reported to EIA; they change often. Net summer capacity.</Note>
      </Card>
    </>
  );
}

/** The queue nationally: by type, by phase, by proposed online year. */
export function UsQueueCard({ q }: { q: UsQueueFile }) {
  const t = q.total;
  const types = q.types.map((k, i) => ({ k, v: t.active[i] })).filter((x) => x.v > 0);
  const maxType = Math.max(1, ...types.map((x) => x.v));
  const phases = q.phases.map((p, i) => ({ p, v: t.phase[i] })).filter((x) => x.v > 0);
  const maxPhase = Math.max(1, ...phases.map((x) => x.v));
  const years = Object.entries(q.by_year)
    .filter(([y]) => y !== "not given" && Number(y) >= 2024 && Number(y) <= 2032)
    .map(([y, v]) => ({ y, parts: q.types.map((k, i) => ({ key: k, value: v[i], color: queueColor(k) })) }));
  const maxYear = Math.max(1, ...years.map((y) => y.parts.reduce((a, p) => a + p.value, 0)));
  return (
    <Card title="Interconnection queue" note={`LBNL Queued Up · ${q.edition}`} accent={[196, 196, 214]}>
      <div className="flex items-baseline gap-2">
        <span className="text-[22px] font-light tabular-nums text-slate-100">{gwText(t.generation_mw + t.storage_mw)}</span>
        <span className={`text-[10.5px] ${muted}`}>in {t.active_n.toLocaleString("en-US")} active requests, {q.through}</span>
      </div>
      <div className="mt-1 text-[11px] tabular-nums text-slate-200">
        generation <b>{gwText(t.generation_mw)}</b> · storage <b>{gwText(t.storage_mw)}</b>
      </div>
      <Head>By type</Head>
      <div className="space-y-[3px]">
        {types.map((x) => (
          <StackRow key={x.k} label={x.k} parts={[{ key: x.k, value: x.v, color: queueColor(x.k) }]} max={maxType} />
        ))}
      </div>
      <Head>By study phase</Head>
      <div className="space-y-[3px]">
        {phases.map((x) => (
          <StackRow key={x.p} label={x.p} parts={[{ key: x.p, value: x.v, color: [150, 170, 200] }]} max={maxPhase} />
        ))}
      </div>
      <Head>By proposed online year</Head>
      <div className="space-y-[3px]">
        {years.map((x) => (
          <StackRow key={x.y} label={x.y} parts={x.parts} max={maxYear} />
        ))}
      </div>
      <Note>
        Sums of the request-level data of Lawrence Berkeley National Laboratory and GridTracker (CC BY 4.0): a hybrid counts under each of its types. LBNL's headline, 1,312 GW of generation, is the same sum; its ~749 GW of storage adds LBNL's
        estimate for hybrids that report no storage size, which is not in the request data and not shown here. Suspended: {gwText(sum(t.suspended))} in {t.suspended_n} requests. Most requests are withdrawn
        before they are built.
      </Note>
    </Card>
  );
}

/** The states with the most waiting, stacked by type. */
export function UsQueueStatesCard({ q, names, onPick }: { q: UsQueueFile; names: (code: string) => string; onPick?: (code: string) => void }) {
  const rows = Object.entries(q.states)
    .map(([code, s]) => ({ code, total: sum(s.active), parts: q.types.map((k, i) => ({ key: k, value: s.active[i], color: queueColor(k) })) }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total)
    .slice(0, 15);
  const used = q.types.filter((k, i) => q.total.active[i] > 0).slice(0, 8);
  return (
    <Card title="Waiting, by state" note={`LBNL · ${q.edition}`} accent={[196, 196, 214]}>
      <div className="space-y-[3px]">
        {rows.map((r) => (
          <StackRow key={r.code} label={names(r.code)} parts={r.parts} max={rows[0]?.total ?? 1} total={r.total} onClick={onPick ? () => onPick(r.code) : undefined} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[9px] text-slate-400">
        {used.map((k) => (
          <span key={k} className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: rgbCss(queueColor(k)) }} />
            {k}
          </span>
        ))}
      </div>
      <Note>
        Active requests by the state LBNL gives for each project; {q.no_state.active_n} active requests ({gwText(sum(q.no_state.active))}) name no state and count only in the national total.
      </Note>
    </Card>
  );
}

/** Every wind turbine: how many, how much, where. */
export function UsTurbinesCard({ t, names }: { t: UsTurbinesFile; names: (code: string) => string }) {
  const rows = Object.entries(t.states)
    .sort((a, b) => b[1][1] - a[1][1])
    .slice(0, 8);
  return (
    <Card title="Wind turbines" note={`USWTDB ${t.release}`} accent={[72, 222, 184]}>
      <div className="flex items-baseline gap-2">
        <span className="text-[22px] font-light tabular-nums text-slate-100">{t.count.toLocaleString("en-US")}</span>
        <span className={`text-[10.5px] ${muted}`}>turbines, {t.offshore_n} offshore</span>
      </div>
      <div className="mt-0.5 text-[11px] tabular-nums text-slate-200">
        {gwText(t.mw)} <span className={muted}>summed over the {t.with_capacity.toLocaleString("en-US")} turbines with a capacity</span>
      </div>
      <Head>Largest states (MW summed)</Head>
      <div className="space-y-[3px]">
        {rows.map(([code, [n, mw]]) => (
          <StackRow key={code} label={`${names(code)} · ${n.toLocaleString("en-US")}`} parts={[{ key: code, value: mw, color: [72, 222, 184] }]} max={rows[0][1][1]} />
        ))}
      </div>
      <Note>U.S. Wind Turbine Database (USGS, LBNL, American Clean Power; public domain): every turbine's position checked on aerial imagery. Shown on the map from zoom 5.</Note>
    </Card>
  );
}
