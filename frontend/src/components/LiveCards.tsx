import { useState } from "react";

import { FUEL_COLOR } from "../lib/energy";
import type { DkLiveFile, GbCarbonFile } from "../lib/live";
import { rgbCss, type RGB } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const W = 300;
const clock = (tz: string) =>
  new Intl.DateTimeFormat("en-GB", { timeZone: tz, weekday: "short", hour: "2-digit", minute: "2-digit" });
const LONDON = clock("Europe/London");
const COPENHAGEN = clock("Europe/Copenhagen");
const london = (iso: string) => LONDON.format(new Date(iso));
const copenhagen = (iso: string) => COPENHAGEN.format(new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`));

function Big({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-white/[0.035] px-2.5 py-2">
      <div className={`text-[9px] uppercase tracking-[0.16em] ${muted}`}>{label}</div>
      <div className="mt-0.5 text-[19px] font-light leading-tight tabular-nums text-slate-100">{value}</div>
      {sub && <div className={`text-[9.5px] leading-snug ${muted}`}>{sub}</div>}
    </div>
  );
}

interface Line {
  key: string;
  color: RGB;
  values: (number | null)[];
  dashed?: boolean;
}

/** A small line chart over n slots; hover reads every line at one slot. */
function Lines({ lines, n, label, unit }: { lines: Line[]; n: number; label: (k: number) => string; unit: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const vals = lines.flatMap((l) => l.values).filter((v): v is number => v != null);
  const top = Math.max(1, ...vals);
  const H = 90;
  const x = (k: number) => (k / Math.max(1, n - 1)) * W;
  const y = (v: number) => 4 + ((top - v) / top) * (H - 8);
  const path = (vs: (number | null)[]) => {
    let d = "";
    let pen = false;
    vs.forEach((v, k) => {
      if (v == null) return void (pen = false);
      d += `${pen ? "L" : "M"}${x(k).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  return (
    <>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="rgba(255,255,255,0.15)" strokeWidth={0.6} />
        {lines.map((l) => (
          <path key={l.key} d={path(l.values)} fill="none" stroke={rgbCss(l.color)} strokeWidth={1} strokeDasharray={l.dashed ? "3 2" : undefined} />
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={0} y2={H} stroke="rgba(255,255,255,0.35)" strokeWidth={0.6} />}
      </svg>
      <div className={`flex flex-wrap justify-between gap-x-2 text-[9.5px] tabular-nums ${muted}`}>
        {hover != null ? (
          <span>
            {label(hover)} · {lines.map((l) => `${l.key} ${l.values[hover] ?? "–"}`).join(" · ")} {unit}
          </span>
        ) : (
          lines.map((l) => (
            <span key={l.key} className="flex items-center gap-1">
              <span className="inline-block h-[2px] w-3" style={{ background: rgbCss(l.color) }} />
              {l.key}
            </span>
          ))
        )}
      </div>
    </>
  );
}

const GB_FUEL: Record<string, string> = { biomass: "bio", imports: "other", other: "other" };
const GB_LABEL: Record<string, string> = {
  biomass: "Biomass",
  coal: "Coal",
  imports: "Imports",
  gas: "Gas",
  nuclear: "Nuclear",
  other: "Other",
  hydro: "Hydro",
  solar: "Solar",
  wind: "Wind",
};

/** Great Britain: carbon intensity now, the last 24 h and the next 48 h, the mix, the regions. */
export function GbCarbonCard({ gb }: { gb: GbCarbonFile }) {
  const [all, setAll] = useState(false);
  // one time axis: the 24 h past, then the 48 h ahead (the forecast's first period may repeat the last past one)
  const from = [...gb.past.map((p) => p[0]), ...gb.ahead.map((a) => a[0]).filter((t) => !gb.past.some((p) => p[0] === t))];
  const idx = new Map(from.map((t, k) => [t, k]));
  const actual: (number | null)[] = from.map(() => null);
  const forecast: (number | null)[] = from.map(() => null);
  for (const [t, f, a] of gb.past) {
    actual[idx.get(t) as number] = a;
    forecast[idx.get(t) as number] = f;
  }
  for (const [t, f] of gb.ahead) forecast[idx.get(t) as number] = f;
  const mix = Object.entries(gb.mix.pct)
    .filter(([, p]) => p > 0)
    .sort((a, b) => b[1] - a[1]);
  const color = (f: string) => FUEL_COLOR[GB_FUEL[f] ?? f] ?? FUEL_COLOR.other;
  const regions = gb.regions.rows.filter((r) => r[0] <= 14);
  const shown = all ? regions : [...regions].sort((a, b) => (a[3] ?? 0) - (b[3] ?? 0)).slice(0, 5);
  return (
    <Card title="Carbon intensity · Great Britain" note={`NESO · ${london(gb.now.from)}`} accent={[120, 200, 160]}>
      <div className="grid grid-cols-2 gap-1.5">
        <Big
          label={gb.now.kind === "actual" ? "Now (actual)" : "Now (forecast)"}
          value={`${gb.now.gco2_kwh} g`}
          sub={`CO₂ per kWh, ${london(gb.now.from)}–${london(gb.now.to).slice(-5)}${gb.now.index ? ` · ${gb.now.index}` : ""}`}
        />
        <Big
          label="Lowest ahead"
          value={(() => {
            const f = gb.ahead.filter((a) => a[1] != null);
            if (!f.length) return "–";
            return `${Math.min(...f.map((a) => a[1] as number))} g`;
          })()}
          sub={(() => {
            const f = gb.ahead.filter((a) => a[1] != null);
            if (!f.length) return undefined;
            const low = f.reduce((m, a) => ((a[1] as number) < (m[1] as number) ? a : m));
            return `forecast, from ${london(low[0])}`;
          })()}
        />
      </div>
      <div className="mt-2.5">
        <Lines
          n={from.length}
          unit="gCO₂/kWh"
          label={(k) => london(from[k])}
          lines={[
            { key: "actual", color: [120, 200, 160], values: actual },
            { key: "forecast", color: [190, 196, 210], values: forecast, dashed: true },
          ]}
        />
        <div className={`text-[9.5px] ${muted}`}>the last 24 h and the next 48 h, every 30 min (UK time)</div>
      </div>
      <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.14em] ${muted}`}>
        <span>Generation mix</span>
        <span className="normal-case tracking-normal">{london(gb.mix.from)}</span>
      </div>
      <div className="flex h-[8px] overflow-hidden rounded-sm bg-white/[0.05]">
        {mix.map(([f, p]) => (
          <div key={f} title={`${GB_LABEL[f] ?? f} ${p} %`} style={{ width: `${p}%`, background: rgbCss(color(f)) }} />
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5">
        {mix.map(([f, p]) => (
          <div key={f} className="flex justify-between text-[11px] tabular-nums text-slate-200">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(color(f)) }} />
              {GB_LABEL[f] ?? f}
            </span>
            <span>{p} %</span>
          </div>
        ))}
      </div>
      <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.14em] ${muted}`}>
        <span>Regions (forecast)</span>
        <button className="normal-case tracking-normal hover:text-slate-200" onClick={() => setAll(!all)}>
          {all ? "cleanest 5" : `all ${regions.length}`}
        </button>
      </div>
      <div className="space-y-0.5">
        {shown.map((r) => (
          <div key={r[0]} className="flex justify-between text-[11px] tabular-nums text-slate-200">
            <span title={r[2] ?? undefined}>{r[1]}</span>
            <span>
              {r[3] ?? "–"} g <span className={muted}>{r[4] ?? ""}</span>
            </span>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        NESO Carbon Intensity API (CC BY 4.0), gCO₂ per kWh. Actual where NESO has published it, otherwise its forecast, labelled. The
        regional values are forecasts only (the API publishes no regional actual).
      </div>
    </Card>
  );
}

const DK_ROWS: [string, string, RGB][] = [
  ["OffshoreWindPower", "Offshore wind", FUEL_COLOR.wind],
  ["OnshoreWindPower", "Onshore wind", [120, 230, 200]],
  ["SolarPower", "Solar", FUEL_COLOR.solar],
  ["ProductionGe100MW", "Plants ≥ 100 MW", FUEL_COLOR.gas],
  ["ProductionLt100MW", "Plants < 100 MW", FUEL_COLOR.bio],
];
const DK_EXCHANGE: [string, string][] = [
  ["ExchangeGermany", "Germany"],
  ["ExchangeNetherlands", "Netherlands"],
  ["ExchangeGreatBritain", "Great Britain"],
  ["ExchangeNorway", "Norway"],
  ["ExchangeSweden", "Sweden"],
  ["ExchangeGreatBelt", "Great Belt (DK1–DK2)"],
];

/** Denmark every 5 minutes: CO2 intensity per area (24 h) and production by type now. */
export function DkLiveCard({ dk }: { dk: DkLiveFile }) {
  const n = dk.co2.DK1.length;
  const t0 = Date.parse(dk.co2.start);
  const at = (k: number) => copenhagen(new Date(t0 + k * dk.co2.step_s * 1000).toISOString());
  const newest = (vs: (number | null)[]) => {
    for (let k = vs.length - 1; k >= 0; k--) if (vs[k] != null) return [vs[k] as number, k] as const;
    return null;
  };
  const areas = (["DK1", "DK2"] as const).map((a) => ({ a, now: newest(dk.co2[a]) }));
  return (
    <Card title="Denmark · every 5 minutes" note={`Energinet · ${copenhagen(dk.fetched)}`} accent={[120, 200, 160]}>
      <div className="grid grid-cols-2 gap-1.5">
        {areas.map(({ a, now }) => (
          <Big key={a} label={`${a} CO₂ now`} value={now ? `${now[0]} g` : "–"} sub={now ? `per kWh consumed, ${at(now[1])}` : "no value published"} />
        ))}
      </div>
      <div className="mt-2.5">
        <Lines
          n={n}
          unit="gCO₂/kWh"
          label={at}
          lines={[
            { key: "DK1", color: [120, 200, 160], values: dk.co2.DK1 },
            { key: "DK2", color: [110, 170, 240], values: dk.co2.DK2 },
          ]}
        />
        <div className={`text-[9.5px] ${muted}`}>the last 24 h, every 5 min (Danish time)</div>
      </div>
      {(["DK1", "DK2"] as const).map((a) => {
        const p = dk.production[a];
        if (!p) return null;
        const rows = DK_ROWS.filter(([c]) => p.mw[c] != null);
        const ex = DK_EXCHANGE.filter(([c]) => p.mw[c] != null);
        return (
          <div key={a}>
            <div className={`mt-3 mb-1 flex justify-between text-[9px] uppercase tracking-[0.14em] ${muted}`}>
              <span>{a} production now</span>
              <span className="normal-case tracking-normal">{copenhagen(p.at)}</span>
            </div>
            <div className="space-y-0.5">
              {rows.map(([c, label, col]) => (
                <div key={c} className="flex justify-between text-[11px] tabular-nums text-slate-200">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(col) }} />
                    {label}
                  </span>
                  <span>{(p.mw[c] as number).toLocaleString("en-GB", { maximumFractionDigits: 2 })} MW</span>
                </div>
              ))}
            </div>
            {ex.length > 0 && (
              <div className={`mt-1 text-[10px] leading-snug tabular-nums ${muted}`}>
                Exchange (positive = into {a}):{" "}
                {ex.map(([c, label]) => `${label} ${(p.mw[c] as number).toLocaleString("en-GB", { maximumFractionDigits: 2 })}`).join(" · ")} MW
              </div>
            )}
          </div>
        );
      })}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Energinet, every 5 minutes (Energi Data Service: CO2Emis, ElectricityProdex5MinRealtime; CC BY 4.0). Values as published: initial figures from
        upscaled real-time measurements, which Energinet does not correct.
      </div>
    </Card>
  );
}
