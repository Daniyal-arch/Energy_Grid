// Regional and live grids: France's regions and Spain's communities (the country's Now tab),
// New Zealand and South Africa (World live grids and their region panels).

import type { ReactNode } from "react";

import { useFile } from "../app/data";
import { FR_LABEL, type EsRegionsFile, type FrRegionsFile, type NzFile, type ZaFile } from "../lib/regionalLive";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;
const gw = (mw: number | null | undefined) => (mw == null ? "–" : mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw).toLocaleString("en-US")} MW`);
const Line = ({ k, v, sub }: { k: ReactNode; v: ReactNode; sub?: ReactNode }) => (
  <div className="flex justify-between gap-2 text-[11px] tabular-nums">
    <span className="truncate text-slate-300">{k}</span>
    <span className="shrink-0 text-slate-100">
      {v} {sub && <span className={muted}>{sub}</span>}
    </span>
  </div>
);

export function FrRegionsCard() {
  const f = useFile<FrRegionsFile>("frRegions");
  if (!f) return null;
  const rows = Object.values(f.regions).sort((a, b) => (b.mw.consommation ?? 0) - (a.mw.consommation ?? 0));
  const ts = rows[0]?.ts;
  return (
    <Card title="Regions" note={`RTE éCO2mix · ${ts?.slice(11, 16)} UTC`} accent={[120, 222, 255]}>
      <div className={`mb-1 grid grid-cols-[1fr_auto_auto] gap-x-3 text-[9px] uppercase tracking-[0.14em] ${muted}`}>
        <span>Region</span>
        <span className="text-right">Consumption</span>
        <span className="text-right">Largest source</span>
      </div>
      {rows.map((r) => {
        const top = Object.entries(r.mw)
          .filter(([k, v]) => FR_LABEL[k] && k !== "pompage" && k !== "stockage_batterie" && (v ?? 0) > 0)
          .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
        return (
          <div key={r.name} className="grid grid-cols-[1fr_auto_auto] gap-x-3 text-[11px] tabular-nums">
            <span className="truncate text-slate-300">{r.name}</span>
            <span className="text-right text-slate-100">{gw(r.mw.consommation)}</span>
            <span className={`text-right ${muted}`}>{top ? `${FR_LABEL[top[0]]} ${gw(top[1])}` : "–"}</span>
          </div>
        );
      })}
      <Note>Each region's newest 15-minute values as RTE publishes them (real-time data, Licence Ouverte); Corsica is not in the real-time set.</Note>
    </Card>
  );
}

export function EsRegionsCard() {
  const f = useFile<EsRegionsFile>("esRegions");
  if (!f) return null;
  const months = [...new Set(Object.values(f.regions).flatMap((r) => Object.values(r.mwh).flatMap((v) => Object.keys(v))))].sort();
  const m = months[months.length - 2] ?? months[months.length - 1];
  const rows = Object.values(f.regions)
    .map((r) => {
      const gen = Object.entries(r.mwh).filter(([t]) => !/total|generación total/i.test(t));
      const total = gen.reduce((a, [, v]) => a + Math.max(0, v[m] ?? 0), 0);
      const top = gen.sort((a, b) => (b[1][m] ?? 0) - (a[1][m] ?? 0))[0];
      return { name: r.name, total, top };
    })
    .sort((a, b) => b.total - a.total);
  return (
    <Card title="Generation by region" note={`REE REData · ${m}`} accent={[255, 196, 90]}>
      {rows.map((r) => (
        <Line key={r.name} k={r.name} v={`${(r.total / 1000).toLocaleString("en-US", { maximumFractionDigits: 0 })} GWh`} sub={r.top ? r.top[0] : undefined} />
      ))}
      <Note>Generation per autonomous community in {m} (the last full month), summed over REE's technologies (computed; MWh as published), and the largest of them.</Note>
    </Card>
  );
}

export function NzCard({ nz }: { nz: NzFile }) {
  const fuels = Object.entries(nz.fuels).sort((a, b) => (b[1].mw ?? 0) - (a[1].mw ?? 0));
  const load = nz.load.nzPoints?.[nz.load.nzPoints.length - 1];
  return (
    <Card title="New Zealand · live" note={`Transpower · ${nz.at}`} accent={[120, 222, 200]}>
      <div className="text-[26px] font-light leading-none tabular-nums text-slate-100">{gw(nz.total_mw)}</div>
      <div className={`mt-1 text-[10px] ${muted}`}>generation now{load ? `; demand ${gw(load[1])} at ${load[0].slice(11)} NZ time` : ""}</div>
      <div className="mt-2 space-y-0.5">
        {fuels.map(([k, v]) => (
          <Line key={k} k={k} v={gw(v.mw)} sub={v.capacity_mw != null ? `of ${gw(v.capacity_mw)}` : undefined} />
        ))}
      </div>
      <Note>Generation and capacity by fuel as Transpower's System Operator page publishes them (generation from em6), and 5-minute demand.</Note>
    </Card>
  );
}

export function ZaCard({ za }: { za: ZaFile }) {
  const d = za.demand;
  const lastD = d?.rows[d.rows.length - 1];
  const s = za.supply;
  const lastS = s?.rows[s.rows.length - 1];
  return (
    <Card title="South Africa · live" note={`Eskom · ${za.fetched.slice(0, 16).replace("T", " ")} UTC`} accent={[255, 180, 110]}>
      <Line k="Load-shedding stage" v={za.loadshedding_stage == null ? "–" : za.loadshedding_stage === 0 ? "none" : `stage ${za.loadshedding_stage}`} />
      {d && lastD && d.columns.map((c, i) => (i > 0 && lastD[i] ? <Line key={c} k={c} v={lastD[i]} sub={i === 1 ? lastD[0] : undefined} /> : null))}
      {s && lastS && s.columns.map((c, i) => (i > 0 && lastS[i] ? <Line key={`s${c}`} k={c} v={lastS[i]} /> : null))}
      <Note>Eskom's data portal files (the newest hour, MW as published) and its load-shedding status.</Note>
    </Card>
  );
}
