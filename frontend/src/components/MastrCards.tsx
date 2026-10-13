// Germany's every unit (Marktstammdatenregister): units and MW by technology, the newest
// additions per month. Sums of the register's operating units, said on the card.

import { Card } from "./CountryCards";
import { useFile } from "../app/data";
import { MASTR_COLOR, MASTR_LABEL, mwText, type MastrMuniFile } from "../lib/mastr";
import { rgbCss } from "../lib/theme";

const muted = "text-[#8d94a1]";

/** `entsoeGw`: ENTSO-E A68 installed capacity by type (the panel's other figure), for comparison. */
export function MastrCountryCard({ entsoeGw }: { entsoeGw?: Record<string, number> }) {
  const f = useFile<MastrMuniFile>("mastrMuni");
  if (!f) return <Card title="Every unit · Germany">Loading the Marktstammdatenregister…</Card>;
  const rows = f.techs.map((t) => [t, ...f.national[t]] as [string, number, number]).sort((a, b) => b[2] - a[2]);
  const top = Math.max(...rows.map((r) => r[2]));
  const compare: Record<string, string> = { solar: "solar", wind: "wind", storage: "storage" };
  return (
    <>
      <Card title="Every unit · Germany" note={`Marktstammdatenregister · ${f.snapshot}`}>
        <div className={`mb-1 text-[10px] ${muted}`}>Units in operation and their gross capacity (sums over the register, computed)</div>
        {rows.map(([t, n, mw]) => (
          <div key={t} className="mb-1">
            <div className="flex justify-between text-[11px] tabular-nums text-slate-200">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(MASTR_COLOR[t]) }} />
                {MASTR_LABEL[t] ?? t}
              </span>
              <span>
                {mwText(mw)} <span className={muted}>· {n.toLocaleString("en-US")} units</span>
              </span>
            </div>
            <div className="mt-0.5 h-[3px] rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full" style={{ width: `${(mw / top) * 100}%`, background: rgbCss(MASTR_COLOR[t]) }} />
            </div>
            {entsoeGw && compare[t] && entsoeGw[compare[t]] != null && (
              <div className={`text-[9.5px] ${muted}`}>ENTSO-E (A68): {entsoeGw[compare[t]].toFixed(1)} GW</div>
            )}
          </div>
        ))}
        {f.offshore.wind && <div className={`text-[10px] ${muted}`}>of the wind: {mwText(f.offshore.wind[1])} at sea ({f.offshore.wind[0]} turbines)</div>}
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          Gross capacity as registered (kW summed). The register lists wind per turbine and solar down to balcony panels, so sums differ from ENTSO-E's, which each grid operator reports by type.
        </div>
      </Card>
      <MastrAdditionsCard f={f} />
    </>
  );
}

function MastrAdditionsCard({ f }: { f: MastrMuniFile }) {
  const techs = ["solar", "wind", "storage"].filter((t) => f.additions[t]);
  const totals = f.months.map((_, i) => techs.reduce((a, t) => a + f.additions[t][i][1], 0));
  const top = Math.max(1, ...totals);
  const last = f.months.length - 1;
  return (
    <Card title="New units per month" note={`Marktstammdatenregister · ${f.snapshot}`}>
      <div className="flex h-[70px] items-end gap-[2px]">
        {f.months.map((m, i) => (
          <div key={m} className="flex flex-1 flex-col-reverse" title={`${m}: ${techs.map((t) => `${MASTR_LABEL[t]} ${mwText(f.additions[t][i][1])}`).join(", ")}`}>
            {techs.map((t) => (
              <div key={t} style={{ height: `${(70 * f.additions[t][i][1]) / top}px`, background: rgbCss(MASTR_COLOR[t]) }} />
            ))}
          </div>
        ))}
      </div>
      <div className={`mt-0.5 flex justify-between text-[9px] ${muted}`}>
        <span>{f.months[0]}</span>
        <span>{f.months[last]}</span>
      </div>
      <div className={`mt-1 text-[11px] text-slate-200`}>
        {f.months[last - 1]}:{" "}
        {techs.map((t) => (
          <span key={t} className="mr-2">
            {MASTR_LABEL[t]} {mwText(f.additions[t][last - 1][1])} <span className={muted}>({f.additions[t][last - 1][0].toLocaleString("en-US")})</span>
          </span>
        ))}
      </div>
      <div className={`mt-1 text-[10px] leading-snug ${muted}`}>
        MW by commissioning month (sum of gross capacity, computed). Units are registered up to a month after they start, so the newest months are still growing.
      </div>
    </Card>
  );
}
