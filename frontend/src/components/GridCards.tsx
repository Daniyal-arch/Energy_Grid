import { useState } from "react";

import type { LinesOutFile, RedispatchFile } from "../lib/grid";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";
const fmtDate = (iso: string | null) => (iso ? iso.slice(0, 16).replace("T", " ") : "–");

/** Germany: redispatch energy per year 2013-2020, by direction (netztransparenz.de open archive). */
export function RedispatchCard({ f }: { f: RedispatchFile }) {
  const years = [...new Set(f.months.map((m) => m.slice(0, 4)))];
  const sumYear = (series: number[] | undefined, y: string) => (series ?? []).reduce((a, v, i) => (f.months[i].startsWith(y) ? a + v : a), 0);
  const rows = years.map((y) => ({ y, down: sumYear(f.by_direction.reduce, y), up: sumYear(f.by_direction.increase, y) }));
  const top = Math.max(1, ...rows.map((r) => Math.max(r.down, r.up)));
  const last = years[years.length - 1];
  const tso = Object.entries(f.by_requesting_tso)
    .map(([k, v]) => [k, sumYear(v, last)] as const)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  return (
    <Card title="Redispatch" note="netztransparenz.de · 2013–2020">
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.y} className="flex items-center gap-2 text-[10.5px] tabular-nums">
            <span className={`w-8 ${muted}`}>{r.y}</span>
            <div className="flex-1 space-y-[2px]">
              <div className="h-[5px] rounded-sm bg-[#ff8a5c]/80" style={{ width: `${(r.down / top) * 100}%` }} />
              <div className="h-[5px] rounded-sm bg-[#5cc8ff]/80" style={{ width: `${(r.up / top) * 100}%` }} />
            </div>
            <span className="w-[86px] text-right text-slate-200">{(r.down / 1e6).toFixed(1)} / {(r.up / 1e6).toFixed(1)} TWh</span>
          </div>
        ))}
      </div>
      <div className={`mt-1 text-[9.5px] ${muted}`}>orange: output reduced · blue: output raised (TWh per year)</div>
      {tso.length > 0 && (
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          Requested in {last} by: {tso.map(([k, v]) => `${k} ${(v / 1e6).toFixed(1)} TWh`).join(" · ")}
        </div>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        {f.measures.toLocaleString("en-US")} measures as the four TSOs publish them; energy summed per year by each measure&apos;s start (computed). Measures since 2021, costs and
        curtailment (EinsMan) are only in netztransparenz.de&apos;s API, which needs a registration.
      </div>
    </Card>
  );
}

/** Lines and other grid elements out of service in a country (ENTSO-E A78), the last and next 30 days. */
export function LinesOutCard({ f, iso2 }: { f: LinesOutFile; iso2: string }) {
  const [all, setAll] = useState(false);
  const now = Date.now();
  const items = f.items.filter((r) => r[0].split("-").includes(iso2)); // a border "AT-DE": either side
  if (!items.length) return null;
  const current = items.filter((r) => (!r[4] || Date.parse(r[4]) <= now) && (!r[5] || Date.parse(r[5]) >= now));
  const shown = all ? items : current.slice(0, 8);
  return (
    <Card title="Lines out of service" note={`ENTSO-E A78 · ${f.fetched.slice(0, 10)}`}>
      <div className="text-[11px] text-slate-200">
        {current.length} out now · {items.length} in the window ({f.window[0].slice(0, 10)} to {f.window[1].slice(0, 10)})
      </div>
      <div className="mt-1.5 space-y-1">
        {shown.map((r, i) => (
          <div key={i} className="text-[10.5px] leading-snug">
            <div className="flex justify-between gap-2">
              <span className="truncate text-slate-200">{r[1] ?? "unnamed element"}</span>
              <span className={r[6] === "forced" ? "text-[#ff8a5c]" : muted}>{r[6]}</span>
            </div>
            <div className={muted}>
              {fmtDate(r[4])} → {fmtDate(r[5])} UTC{r[3] ? ` · ${r[3]} kV` : ""}
              {r[8] ? ` · ${r[8]}` : ""}
            </div>
          </div>
        ))}
      </div>
      {items.length > shown.length || all ? (
        <button className={`mt-1.5 text-[10px] ${muted} hover:text-slate-200`} onClick={() => setAll(!all)}>
          {all ? "only those out now" : `all ${items.length}`}
        </button>
      ) : null}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        Unavailability of transmission infrastructure as the TSOs report it to ENTSO-E (planned and forced), newest revision of each report; voltage only where the report names
        one.
      </div>
    </Card>
  );
}
