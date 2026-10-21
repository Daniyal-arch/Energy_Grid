// Room to connect in ten more countries (connect/<cc>.json, scripts/build_connect_eu.py): one card
// per country, its rows by class and the most room first, every value as the operator publishes it.

import { useFile } from "../app/data";
import { classColor, connectEuKey, valueText, type ConnectEuFile } from "../lib/connectEu";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

export function ConnectEuCard({ cc }: { cc: string }) {
  const f = useFile<ConnectEuFile>(connectEuKey(cc));
  if (!f) return null;
  const rows = [...f.points.map((p) => ({ name: p[0], v: p[4], k: p[5] })), ...f.areas.map((a) => ({ name: a[0], v: a[2], k: a[3] })), ...f.table.map((t) => ({ name: t[0], v: t[2], k: t[3] }))];
  const counts = f.classes.map((_, i) => rows.filter((r) => r.k === i).length);
  const shown = [...rows].sort((a, b) => (a.k < 0 ? 9 : a.k) - (b.k < 0 ? 9 : b.k)).slice(0, 8);
  const cols = f.columns.slice(0, 3);
  return (
    <Card title="Room to connect" note={`${f.source.split(",")[0]}${f.updated ? ` · ${f.updated}` : ""}`} accent={[206, 138, 72]}>
      <div className="space-y-0.5">
        {f.classes.map((c, i) => (
          <div key={c} className="flex justify-between text-[11px] text-slate-200">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(classColor(f, i)) }} />
              {c}
            </span>
            <span className="tabular-nums">{counts[i]}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 space-y-0.5">
        {shown.map((r) => (
          <div key={r.name} className="text-[10px] leading-snug text-slate-300">
            <span className="text-slate-100">{r.name}</span>
            <span className={muted}> · {cols.map(([key, label, unit]) => `${label}: ${valueText(r.v[f.columns.findIndex((c) => c[0] === key)], unit)}`).join(" · ")}</span>
          </div>
        ))}
      </div>
      <div className={`mt-1.5 text-[9px] ${muted}`}>
        {f.note} Source: <a href={f.url} target="_blank" rel="noreferrer" className="underline">{f.source}</a>.
      </div>
    </Card>
  );
}
