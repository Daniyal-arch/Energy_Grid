// Who finances coal and gas power (GEM finance trackers): the world's rankings and one country.

import { useState } from "react";

import { MONEY, usd, type FinanceFile } from "../lib/finance";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
type Pick = "both" | 0 | 1;

function FuelPick({ pick, setPick }: { pick: Pick; setPick: (p: Pick) => void }) {
  return (
    <div className="mb-2 flex gap-1">
      {(["both", 0, 1] as Pick[]).map((p) => (
        <button
          key={String(p)}
          onClick={() => setPick(p)}
          className={`rounded-full border px-2.5 py-0.5 text-[10.5px] ${p === pick ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-400"}`}
        >
          {p === "both" ? "Coal + gas" : p === 0 ? "Coal" : "Gas"}
        </button>
      ))}
    </div>
  );
}

const sum = (v: [number, number], pick: Pick) => (pick === "both" ? v[0] + v[1] : v[pick]);

function Bars({ rows, onPick }: { rows: { key: string; label: string; sub?: string; value: number }[]; onPick?: (key: string) => void }) {
  const top = rows[0]?.value || 1;
  return (
    <div className="space-y-[3px]">
      {rows.map((r) => (
        <button
          key={r.key}
          onClick={() => onPick?.(r.key)}
          disabled={!onPick}
          className="flex w-full items-center gap-2 rounded px-1 text-left text-[11px] tabular-nums enabled:hover:bg-white/[0.05]"
        >
          <span className="w-[112px] truncate text-slate-300" title={r.sub ? `${r.label} · ${r.sub}` : r.label}>
            {r.label}
            {r.sub && <span className={muted}> · {r.sub}</span>}
          </span>
          <span className="relative h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
            <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(r.value / top) * 100}%`, background: "linear-gradient(90deg, rgb(255,170,60), rgb(232,204,128))" }} />
          </span>
          <span className="w-14 text-right text-slate-100">{usd(r.value)}</span>
        </button>
      ))}
    </div>
  );
}

/** The world: which countries lend abroad, which financiers lend most, who receives. */
export function FinanceWorldCard({ f, onPick }: { f: FinanceFile; onPick: (iso3: string) => void }) {
  const [pick, setPick] = useState<Pick>("both");
  const name = (iso: string) => f.countries[iso]?.name ?? iso;
  const totals = Object.entries(f.totals);
  const abroad = totals
    .map(([iso, t]) => ({ key: iso, label: name(iso), value: sum(t.out, pick) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
  const received = totals
    .map(([iso, t]) => ({ key: iso, label: name(iso), value: sum(t.in, pick) }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
  const lenders = f.lenders
    .filter((l) => pick === "both" || l[2] === pick)
    .reduce<Map<string, { iso: string; value: number }>>((m, l) => {
      const cur = m.get(l[0]) ?? { iso: l[1], value: 0 };
      cur.value += l[3];
      m.set(l[0], cur);
      return m;
    }, new Map());
  const topLenders = [...lenders.entries()]
    .map(([n, v]) => ({ key: n, label: n, sub: v.iso ? name(v.iso) : "multilateral", value: v.value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
  const world = totals.reduce((a, [, t]) => a + sum(t.out, pick) + sum(t.domestic, pick), 0);
  return (
    <Card title="Who pays for coal and gas power" note="Global Energy Monitor" accent={MONEY[1]}>
      <FuelPick pick={pick} setPick={setPick} />
      <div className="text-[24px] font-light leading-none tabular-nums text-slate-100">{usd(world)}</div>
      <div className={`mt-1 text-[10px] ${muted}`}>financiers' shares with a known home country, at home and abroad, all years</div>
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Lending abroad, by financiers' home country</div>
      <Bars rows={abroad} onPick={onPick} />
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Largest financiers</div>
      <Bars rows={topLenders} />
      <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Receiving money from abroad</div>
      <Bars rows={received} onPick={onPick} />
      <div className={`mt-2 text-[10px] ${muted}`}>Sums of each financier's share as GEM lists it (US$); deals marked stopped are left out.</div>
    </Card>
  );
}

/** One country: money at home, sent abroad and received; where from, where to; its projects. */
export function FinanceCountryCard({ f, iso3, onPick }: { f: FinanceFile; iso3: string; onPick: (iso3: string) => void }) {
  const [pick, setPick] = useState<Pick>("both");
  const name = (iso: string) => f.countries[iso]?.name ?? iso;
  const t = f.totals[iso3];
  const flows = f.flows.filter((fl) => pick === "both" || fl[2] === pick);
  const merge = (list: typeof flows, key: 0 | 1) =>
    [...list.reduce((m, fl) => m.set(fl[key], (m.get(fl[key]) ?? 0) + fl[3]), new Map<string, number>()).entries()]
      .map(([iso, value]) => ({ key: iso, label: name(iso), value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  const from = merge(flows.filter((fl) => fl[1] === iso3), 0);
  const to = merge(flows.filter((fl) => fl[0] === iso3), 1);
  const projects = f.projects.filter((p) => p[6] === iso3 && (pick === "both" || p[2] === pick)).slice(0, 6);
  const based = f.lenders.filter((l) => l[1] === iso3 && (pick === "both" || l[2] === pick)).slice(0, 6);
  if (!t && !projects.length && !based.length) {
    return (
      <Card title="Finance" note="Global Energy Monitor" accent={MONEY[1]}>
        <div className={`text-[11px] ${muted}`}>No coal or gas power finance recorded for this country in GEM's trackers.</div>
      </Card>
    );
  }
  const tile = (label: string, v: [number, number] | undefined, note: string) => (
    <div className="rounded-lg bg-white/[0.035] px-2 py-1.5">
      <div className={`text-[9px] uppercase tracking-[0.14em] ${muted}`}>{label}</div>
      <div className="text-[16px] font-light tabular-nums text-slate-100">{usd(v ? sum(v, pick) : 0)}</div>
      <div className={`text-[9px] ${muted}`}>{note}</div>
    </div>
  );
  return (
    <Card title="Who pays for coal and gas power" note="Global Energy Monitor" accent={MONEY[1]}>
      <FuelPick pick={pick} setPick={setPick} />
      <div className="grid grid-cols-3 gap-1.5">
        {tile("At home", t?.domestic, "its financiers, here")}
        {tile("Abroad", t?.out, "its financiers, elsewhere")}
        {tile("From abroad", t?.in, "foreign financiers")}
      </div>
      {from.length > 0 && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Money from</div>
          <Bars rows={from} onPick={onPick} />
        </>
      )}
      {to.length > 0 && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Money to</div>
          <Bars rows={to} onPick={onPick} />
        </>
      )}
      {projects.length > 0 && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Most financed projects here</div>
          <div className="space-y-1">
            {projects.map((p) => (
              <div key={`${p[5]}-${p[0]}`} className="text-[11px] tabular-nums">
                <div className="flex justify-between gap-2 text-slate-200">
                  <span className="flex items-center gap-1.5 truncate">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: rgbCss(MONEY[p[2]]) }} />
                    {p[5]}
                  </span>
                  <span className="shrink-0">{usd(p[3])}</span>
                </div>
                <div className={`truncate pl-3.5 text-[9.5px] ${muted}`}>{p[8].map(([n]) => n).join(", ")}</div>
              </div>
            ))}
          </div>
        </>
      )}
      {based.length > 0 && (
        <>
          <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>Financiers based here</div>
          <Bars rows={based.map((l) => ({ key: `${l[0]}-${l[2]}`, label: l[0], sub: f.fuels[l[2]], value: l[3] }))} />
        </>
      )}
      <div className={`mt-2 text-[10px] ${muted}`}>
        Sums of financiers' shares as GEM lists them; deals marked stopped left out.
      </div>
    </Card>
  );
}
