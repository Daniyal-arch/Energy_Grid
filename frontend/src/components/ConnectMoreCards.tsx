// Room to connect in France, Italy, Belgium, Portugal, Ireland and Poland: one card per country
// in "On the map" (Grid capacity). Values as the operators publish them; counts and sums say so.

import type { ReactNode } from "react";

import { useFile } from "../app/data";
import { gwText } from "../lib/connect";
import { PT_LABEL, frNumber, itTotals, type BeFile, type FrFile, type IeFile, type ItFile, type PlFile, type PtFile } from "../lib/connectMore";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const ACCENT: [number, number, number] = [206, 138, 72];
const Head = ({ children }: { children: ReactNode }) => <div className={`mt-3 mb-1 text-[9px] uppercase tracking-[0.14em] ${muted}`}>{children}</div>;
const Note = ({ children }: { children: ReactNode }) => <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{children}</div>;
const mw = (v: number, unit = "MW") => `${v.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${unit}`;

/** A ranked list with bars (largest first). */
function Bars({ rows, unit = "MW" }: { rows: { key: string; label: ReactNode; value: number }[]; unit?: string }) {
  const max = rows[0]?.value || 1;
  return (
    <div className="space-y-1">
      {rows.map((r) => (
        <div key={r.key} className="text-[11px]">
          <div className="flex justify-between gap-2">
            <span className="truncate text-slate-200">{r.label}</span>
            <span className="tabular-nums text-slate-100">{unit === "GW" ? gwText(r.value) : mw(r.value, unit)}</span>
          </div>
          <div className="h-1 rounded bg-white/[0.06]">
            <div className="h-1 rounded bg-[rgb(206,138,72)]" style={{ width: `${(100 * r.value) / max}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Big({ value, children }: { value: ReactNode; children: ReactNode }) {
  return (
    <div className="text-[22px] font-light text-slate-50">
      {value} <span className={`text-[11px] ${muted}`}>{children}</span>
    </div>
  );
}

export function FrConnectCard() {
  const f = useFile<FrFile>("connectFR");
  if (!f) return null;
  const left = f.sites.map((s) => ({ s, v: frNumber(f, s, "INFO_NA") })).filter((x): x is { s: (typeof f.sites)[number]; v: number } => x.v != null);
  const free = left.filter((x) => x.v > 0);
  const top = [...free].sort((a, b) => b.v - a.v).slice(0, 8);
  const sum = free.reduce((a, x) => a + x.v, 0);
  return (
    <Card title="Connecting to the grid · France" note={`Capareseau · ${f.fetched.slice(0, 10)}`} accent={ACCENT}>
      <Big value={free.length.toLocaleString("en-US")}>
        of {left.length.toLocaleString("en-US")} substations have S3REnR capacity left to allocate; {gwText(sum)} in all (count and sum, computed)
      </Big>
      <Head>Most capacity left, MW</Head>
      <Bars rows={top.map((x) => ({ key: x.s[0], label: <>{x.s[1]} <span className={muted}>{x.s[2]}</span></>, value: x.v }))} />
      <Note>
        "{f.labels.INFO_NA}" per substation, as RTE and the distribution operators publish it on capareseau.fr: capacity reserved for renewables by each region's S3REnR, for new
        generation only. Indicative; the operators confirm it per request.
      </Note>
    </Card>
  );
}

export function ItConnectCard() {
  const f = useFile<ItFile>("connectIT");
  if (!f) return null;
  const tot = itTotals(f);
  const fer = Object.values(tot).reduce((a, t) => a + t.fer, 0);
  const sto = Object.values(tot).reduce((a, t) => a + t.storage, 0);
  const bySource: Record<string, number> = {};
  for (const by of Object.values(f.renewables.regions)) for (const [src, [v]] of Object.entries(by)) bySource[src] = (bySource[src] ?? 0) + v;
  const regions = Object.entries(tot)
    .map(([r, t]) => ({ key: r, label: r, value: t.fer + t.storage }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
  return (
    <Card title="Connecting to the grid · Italy" note={`Terna Econnextion · ${f.fetched.slice(0, 10)}`} accent={ACCENT}>
      <Big value={gwText(fer)}>of renewables and {gwText(sto)} of storage requested to connect to the transmission grid (sums, computed)</Big>
      <div className={`pb-1 text-[10px] ${muted}`}>
        {Object.entries(bySource)
          .sort((a, b) => b[1] - a[1])
          .map(([s, v]) => `${s} ${gwText(v)}`)
          .join(" · ")}
      </div>
      <Head>By region, renewables and storage</Head>
      <Bars rows={regions} unit="GW" />
      <Note>Requests at every stage of Terna's connection procedure (Econnextion, monthly): requests, most of which will not be built. The map shades each region by the total.</Note>
    </Card>
  );
}

export function BeConnectCard() {
  const f = useFile<BeFile>("connectBE");
  if (!f) return null;
  const sheets = Object.entries(f.sheets).filter(([, s]) => s.rows.length > 0);
  return (
    <Card title="Connecting to the grid · Belgium" note={`Elia · ${f.file}`} accent={ACCENT}>
      {sheets.map(([name, s]) => (
        <div key={name}>
          <Head>{name}</Head>
          <div className="text-[11px] text-slate-300">{s.rows.length.toLocaleString("en-US")} rows</div>
          <div className={`text-[10px] ${muted}`}>{s.columns.slice(0, 8).join(" · ")}</div>
        </div>
      ))}
      <Note>Elia's published capacity of its grid for new decentralised generation, as the file publishes it.</Note>
    </Card>
  );
}

export function PtConnectCard() {
  const f = useFile<PtFile>("connectPT");
  if (!f) return null;
  const k = f.columns.indexOf("capacidade_de_recepcao_mt_at_mva_ultimo_trimestre");
  const rows = f.substations.map((s) => ({ s, v: s[7][k] })).filter((x): x is { s: (typeof f.substations)[number]; v: number } => x.v != null);
  const free = rows.filter((x) => x.v > 0);
  const top = [...free].sort((a, b) => b.v - a.v).slice(0, 8);
  return (
    <Card title="Connecting to the grid · Portugal" note={`E-REDES · ${f.date}`} accent={ACCENT}>
      <Big value={free.length}>of {rows.length} HV/MV substations have reception capacity left (count, computed)</Big>
      <Head>{PT_LABEL[f.columns[k]]}</Head>
      <Bars rows={top.map((x) => ({ key: x.s[0], label: <>{x.s[1]} <span className={muted}>{x.s[4]}</span></>, value: x.v }))} unit="MVA" />
      <Note>Reception capacity of the distribution grid per substation for new generation, the newest quarter, as E-REDES publishes it (CC BY 4.0). E-REDES publishes no positions: not on the map.</Note>
    </Card>
  );
}

export function IeConnectCard() {
  const f = useFile<IeFile>("connectIE");
  if (!f) return null;
  const g = f.columns.indexOf("gen_available_firm_mw");
  const d = f.columns.indexOf("demand_available_mva");
  const genFree = f.stations.filter((s) => (s[5][g] ?? 0) > 0).length;
  const demFree = f.stations.filter((s) => (s[5][d] ?? 0) > 0).length;
  const top = [...f.stations].sort((a, b) => (b[5][g] ?? 0) - (a[5][g] ?? 0)).slice(0, 6);
  return (
    <Card title="Connecting to the grid · Ireland" note={`ESB Networks · ${f.file}`} accent={ACCENT}>
      <Big value={`${genFree} / ${demFree}`}>
        of {f.stations.length} stations (38 kV and 110 kV) and MV transformers have firm generation / demand capacity available (counts, computed)
      </Big>
      <Head>Most firm generation capacity available, MW</Head>
      <Bars rows={top.map((s) => ({ key: s[0], label: s[0], value: s[5][g] ?? 0 }))} />
      <Note>
        Transformer capacity only (not the upstream network), a snapshot as ESB Networks' heatmap publishes it; the {f.transformers_total.toLocaleString("en-US")} transformers including LV are in
        the lake. EirGrid publishes no machine-readable heatmap.
      </Note>
    </Card>
  );
}

export function PlConnectCard() {
  const f = useFile<PlFile>("connectPL");
  if (!f) return null;
  const byStatus: Record<string, [number, number]> = {};
  for (const r of f.requests) {
    const s = r[2] ?? "status not given";
    const row = (byStatus[s] ??= [0, 0]);
    row[0] += 1;
    row[1] += r[4] ?? 0;
  }
  return (
    <Card title="Connecting to the grid · Poland" note={`PSE · as of ${f.date ?? "–"}`} accent={ACCENT}>
      <Big value={f.full.length}>PSE switchgears have no free connection bay</Big>
      <div className={`pb-1 text-[10px] ${muted}`}>{f.full.slice(0, 12).map((s) => `${s[0]} (${s[2].replace("Rozdzielnia ", "")})`).join(" · ")}</div>
      <Head>Requests to PSE, by stage: count, MW to inject</Head>
      <div className="space-y-0.5 text-[11px]">
        {Object.entries(byStatus)
          .sort((a, b) => b[1][1] - a[1][1])
          .map(([s, [n, v]]) => (
            <div key={s} className="flex justify-between gap-2">
              <span className="truncate text-slate-300">{s}</span>
              <span className="tabular-nums text-slate-100">
                {n} · {gwText(v)}
              </span>
            </div>
          ))}
      </div>
      <Note>PSE's list under Art. 7(8l) of the Energy Law (counts and sums of the single-value rows, computed) and its list of switchgears without free bays. PSE publishes no positions.</Note>
    </Card>
  );
}
