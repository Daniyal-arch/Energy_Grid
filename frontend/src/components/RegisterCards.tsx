// A national register of generating units (registers/<cc>.json): units and MW by fuel and status
// (summed, computed), or the register's table where it publishes no positions.

import { useFile } from "../app/data";
import { FUEL_COLOR, FUEL_LABEL, power } from "../lib/energy";
import { STATUS_LABEL, registerKey, type RegisterFile } from "../lib/registers";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const label = (g: string) => (g === "wind_offshore" ? "Wind at sea" : (FUEL_LABEL[g] ?? g));
const colour = (g: string) => FUEL_COLOR[g === "wind_offshore" ? "wind" : g] ?? FUEL_COLOR.other;

export function RegisterCard({ cc }: { cc: string }) {
  const f = useFile<RegisterFile>(registerKey(cc));
  if (!f) return null;
  const statuses = Object.keys(STATUS_LABEL).filter((s) => f.totals[s]);
  return (
    <Card title="Every unit (national register)" note={`${f.source.split(",")[0]}${f.updated ? ` · ${f.updated}` : ""}`} accent={[255, 214, 72]}>
      {statuses.map((s) => {
        const rows = Object.entries(f.totals[s]).sort((a, b) => b[1][1] - a[1][1]);
        return (
          <div key={s} className="mb-2">
            <div className={`text-[10px] uppercase tracking-wide ${muted}`}>{STATUS_LABEL[s]}</div>
            {rows.map(([g, [n, mw]]) => (
              <div key={g} className="flex justify-between text-[11px] tabular-nums text-slate-200">
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(colour(g)) }} />
                  {label(g)}
                </span>
                <span>
                  {power(mw)} <span className={muted}>· {n.toLocaleString("en-US")}</span>
                </span>
              </div>
            ))}
          </div>
        );
      })}
      {f.table.length > 0 && (
        <div className="mt-1 space-y-0.5">
          <div className={`grid grid-cols-[1fr_auto] text-[10px] ${muted}`}>
            <span>{f.table_columns.slice(0, -1).join(" · ")}</span>
            <span>{f.table_columns[f.table_columns.length - 1]}</span>
          </div>
          {f.table.slice(0, 12).map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto] gap-2 text-[11px] tabular-nums text-slate-200">
              <span className="truncate">{r.slice(0, -1).filter((v) => v != null).join(" · ")}</span>
              <span>{typeof r[r.length - 1] === "number" ? (r[r.length - 1] as number).toLocaleString("en-US") : (r[r.length - 1] ?? "–")}</span>
            </div>
          ))}
        </div>
      )}
      <div className={`mt-1.5 text-[9px] ${muted}`}>
        {f.note} {f.sum_note}. Source: <a href={f.url} target="_blank" rel="noreferrer" className="underline">{f.source}</a> ({f.licence}).
      </div>
    </Card>
  );
}
