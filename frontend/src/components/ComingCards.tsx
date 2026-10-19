// What is coming and what it costs: hydrogen projects and planned gas infrastructure ("On the
// map"), renewable auctions (the country's Prices tab), technology costs (World and US panels).
// Counts and sums say they are computed; prices keep the source's units and precision.

import { useState, type ReactNode } from "react";

import { useFile } from "../app/data";
import { GAS_CAT_COLOR, H2_STAGE_COLOR, gasByCountry, type AuctionsFile, type CostsFile, type GasProjectsFile, type HydrogenFile } from "../lib/coming";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const Head = ({ children }: { children: ReactNode }) => <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>{children}</div>;
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;
const mw = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v).toLocaleString("en-US")} MW`);

export function HydrogenCard({ iso3 }: { iso3?: string }) {
  const f = useFile<HydrogenFile>("hydrogen");
  if (!f) return null;
  const rows = f.projects.filter((p) => !iso3 || p[2] === iso3);
  if (!rows.length) return null;
  const byStage: Record<string, [number, number]> = {};
  for (const p of rows) {
    const s = p[10] != null ? f.stages[p[10]] : "stage not given";
    const r = (byStage[s] ??= [0, 0]);
    r[0] += 1;
    r[1] += p[4] ?? 0;
  }
  const top = [...rows].sort((a, b) => (b[4] ?? 0) - (a[4] ?? 0)).slice(0, 6);
  return (
    <Card title="Hydrogen projects" note={f.file} accent={[96, 214, 255]}>
      {Object.entries(byStage).map(([s, [n, v]]) => (
        <div key={s} className="flex justify-between text-[11px]">
          <span className="text-slate-300">
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: rgbCss(H2_STAGE_COLOR[s] ?? [190, 196, 210]) }} />
            {s}
          </span>
          <span className="tabular-nums text-slate-100">
            {n} · {mw(v)}
          </span>
        </div>
      ))}
      <Head>Largest</Head>
      {top.map((p) => (
        <div key={`${p[0]}${p[8]}`} className="flex justify-between gap-2 text-[11px]">
          <span className="truncate text-slate-300">{p[0]}</span>
          <span className="tabular-nums text-slate-100">{p[4] != null ? mw(p[4]) : "–"}</span>
        </div>
      ))}
      <Note>Projects in operation or under construction with their production capacity (MW, as published; electrolysers in MWel), counts and sums computed. European Hydrogen Observatory.</Note>
    </Card>
  );
}

export function GasProjectsCard({ iso3 }: { iso3?: string }) {
  const f = useFile<GasProjectsFile>("gasProjects");
  if (!f) return null;
  const rows = f.projects.filter((p) => !iso3 || p[2] === iso3);
  if (!rows.length) return null;
  const byCat: Record<string, number> = {};
  const byMat: Record<string, number> = {};
  for (const p of rows) {
    byCat[p[5]] = (byCat[p[5]] ?? 0) + 1;
    byMat[p[4] ?? "–"] = (byMat[p[4] ?? "–"] ?? 0) + 1;
  }
  const km = rows.reduce((a, p) => a + (p[5] === "H2T" ? (p[9] ?? 0) : 0), 0);
  const kmGas = rows.reduce((a, p) => a + (p[5] === "TRA" ? (p[9] ?? 0) : 0), 0);
  const countries = iso3 ? null : Object.entries(gasByCountry(f)).sort((a, b) => b[1].n - a[1].n).slice(0, 8);
  return (
    <Card title="Planned gas projects" note={f.file} accent={[255, 196, 96]}>
      <div className="text-[22px] font-light text-slate-50">
        {rows.length} <span className={`text-[11px] ${muted}`}>projects in the TYNDP 2026 ({Object.entries(byMat).map(([m, n]) => `${n} ${m}`).join(", ")})</span>
      </div>
      <div className="mt-1 space-y-0.5">
        {Object.entries(byCat)
          .sort((a, b) => b[1] - a[1])
          .map(([c, n]) => (
            <div key={c} className="flex justify-between text-[11px]">
              <span className="text-slate-300">
                <span className="mr-1.5 inline-block h-2 w-2 rounded-full border" style={{ borderColor: rgbCss(GAS_CAT_COLOR[c] ?? [160, 166, 180]) }} />
                {f.categories[c] ?? c}
              </span>
              <span className="tabular-nums text-slate-100">{n}</span>
            </div>
          ))}
      </div>
      <div className={`mt-1 text-[10px] ${muted}`}>
        Pipeline sections: {Math.round(km).toLocaleString("en-US")} km for hydrogen, {Math.round(kmGas).toLocaleString("en-US")} km for methane (sums of the sections listed, computed)
      </div>
      {countries && <div className={`mt-1 text-[10px] ${muted}`}>{countries.map(([c, r]) => `${c} ${r.n}`).join(" · ")}</div>}
      <Note>ENTSOG's Annex A as the promoters submitted the projects; a cross-border project counts under the one country it lists. ENTSOG publishes no positions: the map shows one ring per country.</Note>
    </Card>
  );
}

export function AuctionsCard({ iso3 }: { iso3: string }) {
  const f = useFile<AuctionsFile>("auctions");
  const rounds = f?.countries[iso3];
  if (!f || !rounds?.length) return null;
  const recent = [...rounds].reverse().slice(0, 8);
  const awarded = rounds.reduce((a, r) => a + (r[3] ?? 0), 0);
  return (
    <Card title="Renewable auctions" note={`AURES II · ${rounds[0][0]?.slice(0, 4)}–${rounds[rounds.length - 1][0]?.slice(0, 4)}`} accent={[120, 222, 160]}>
      <div className="text-[22px] font-light text-slate-50">
        {mw(awarded)} <span className={`text-[11px] ${muted}`}>awarded in {rounds.length} rounds (sum of the rounds that report it, computed)</span>
      </div>
      <Head>Newest rounds · awarded · average price</Head>
      <div className="space-y-0.5">
        {recent.map((r, i) => (
          <div key={i} className="flex justify-between gap-2 text-[11px]">
            <span className="truncate text-slate-300">
              {r[0]} <span className={muted}>{r[1]}</span>
            </span>
            <span className="shrink-0 tabular-nums text-slate-100">
              {r[3] != null ? mw(r[3]) : "–"} · {r[4] != null ? `${r[4]} ct/kWh` : "–"}
            </span>
          </div>
        ))}
      </div>
      <Note>Average awarded price per round in ct/kWh as the database gives it; a round's support scheme (FIT, sliding premium, CfD) decides what the price means. AURES II covers 2011–2021.</Note>
    </Card>
  );
}

export function CostsCard() {
  const f = useFile<CostsFile>("costs");
  const [param, setParam] = useState<"LCOE" | "CAPEX">("LCOE");
  if (!f?.atb && !f?.irena) return null;
  const atb = f.atb;
  const rows = atb
    ? Object.entries(atb.technologies)
        .filter(([, t]) => t.values[param] && Object.keys(t.values[param]).length)
        .sort((a, b) => (a[1].values[param][String(atb.years[0])] ?? 1e9) - (b[1].values[param][String(atb.years[0])] ?? 1e9))
    : [];
  const irena = f.irena ? Object.values(f.irena.tables)[0] : undefined;
  return (
    <Card title="What new capacity costs" note={atb ? `NREL ATB ${atb.edition}` : "IRENA"} accent={[240, 214, 92]}>
      {atb && (
        <>
          <div className="mb-1 flex gap-1.5">
            {(["LCOE", "CAPEX"] as const).map((p) => (
              <button key={p} onClick={() => setParam(p)} className={`rounded-md border px-2 py-0.5 text-[10.5px] ${param === p ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300"}`}>
                {p}
              </button>
            ))}
          </div>
          <div className="grid gap-x-2 text-[10.5px] tabular-nums" style={{ gridTemplateColumns: `1fr repeat(${atb.years.length}, auto)` }}>
            <span className={muted}>United States, {rows[0]?.[1].units[param] ?? ""}</span>
            {atb.years.map((y) => (
              <span key={y} className={`${muted} text-right`}>
                {y}
              </span>
            ))}
            {rows.slice(0, 14).map(([name, t]) => (
              <Line key={name} name={name} years={atb.years} vals={t.values[param]} />
            ))}
          </div>
          <Note>
            NREL's Annual Technology Baseline, {atb.scenario} scenario, {atb.case} case{atb.tax_credits ? ` (tax credits: ${atb.tax_credits})` : ""}, {atb.crp_years}-year cost recovery; the default
            resource class of each technology, in US dollars as published (CC BY 4.0).
          </Note>
        </>
      )}
      {irena && (
        <>
          <Head>World · {irena.title}</Head>
          {Object.entries(irena.rows)
            .slice(0, 10)
            .map(([tech, vals]) => {
              const ys = Object.keys(vals).sort();
              const last = ys[ys.length - 1];
              return (
                <div key={tech} className="flex justify-between gap-2 text-[11px]">
                  <span className="truncate text-slate-300">{tech}</span>
                  <span className="tabular-nums text-slate-100">
                    {vals[ys[0]]} ({ys[0]}) → {vals[last]} ({last})
                  </span>
                </div>
              );
            })}
          <Note>IRENA's global weighted averages as its data file publishes them.</Note>
        </>
      )}
    </Card>
  );
}

function Line({ name, years, vals }: { name: string; years: number[]; vals: Record<string, number> }) {
  return (
    <>
      <span className="truncate text-slate-300">{name}</span>
      {years.map((y) => (
        <span key={y} className="text-right text-slate-100">
          {vals[String(y)] != null ? Math.round(vals[String(y)]).toLocaleString("en-US") : "–"}
        </span>
      ))}
    </>
  );
}
