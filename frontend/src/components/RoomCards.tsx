// Room to connect, the card for a country or Europe (brief 23): free MW for new generation and new
// demand (sums of what the operators publish, computed), the nodes and areas by class as a donut,
// and every operator with its date. Reads connect/harmonised.json.

import { useFile } from "../app/data";
import { useApp } from "../app/store";
import { H_CLASSES, H_COLOR, H_LABEL, countryRoom, mwText, type CountryRoom, type HClass, type HFile } from "../lib/connectH";
import { rgbCss } from "../lib/theme";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

function Donut({ counts }: { counts: Record<HClass, number> }) {
  const total = H_CLASSES.reduce((a, c) => a + counts[c], 0);
  if (!total) return null;
  let at = 0;
  const R = 15;
  const C = 2 * Math.PI * R;
  return (
    <svg viewBox="0 0 40 40" className="h-14 w-14 shrink-0 -rotate-90">
      {H_CLASSES.map((c) => {
        const len = (counts[c] / total) * C;
        const el = <circle key={c} cx="20" cy="20" r={R} fill="none" stroke={rgbCss(H_COLOR[c])} strokeWidth="7" strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-at} />;
        at += len;
        return el;
      })}
    </svg>
  );
}

/** One country (iso2; "US" for the US utilities) or Europe (no iso2: every European country summed). */
export function RoomCard({ iso2, name }: { iso2?: string; name?: string }) {
  const f = useFile<HFile>("connectH");
  const side = useApp((s) => s.connectSide);
  if (!f) return <Card title="Room to connect">Loading…</Card>;
  const room = countryRoom(f);
  let c: CountryRoom | undefined;
  if (iso2) c = room[iso2];
  else {
    const eu = Object.entries(room).filter(([cc]) => cc !== "US");
    c = eu.reduce<CountryRoom>(
      (a, [, x]) => {
        a.gen += x.gen;
        a.load += x.load;
        a.genRows += x.genRows;
        a.loadRows += x.loadRows;
        for (const k of H_CLASSES) {
          a.byClass[k] += x.byClass[k];
          a.byClassLoad[k] += x.byClassLoad[k];
        }
        a.operators.push(...x.operators);
        return a;
      },
      { gen: 0, load: 0, genRows: 0, loadRows: 0, byClass: { available: 0, limited: 0, queue: 0, none: 0 }, byClassLoad: { available: 0, limited: 0, queue: 0, none: 0 }, operators: [] },
    );
  }
  if (!c) return <Card title="Room to connect">No operator publishes room to connect {name ? `in ${name}` : "here"} as data (see the coverage card).</Card>;
  const counts = side === "feedin" ? c.byClass : c.byClassLoad;
  return (
    <Card title="Room to connect" note={iso2 ? `${c.operators.length} operator${c.operators.length === 1 ? "" : "s"}` : `${c.operators.length} operators, Europe`}>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-[20px] font-light text-slate-50">{c.genRows ? mwText(c.gen) : "–"}</div>
          <div className={`text-[10px] ${muted}`}>free for new generation{c.genRows ? `, ${c.genRows.toLocaleString("en-US")} nodes` : ", no MW published"}</div>
        </div>
        <div>
          <div className="text-[20px] font-light text-slate-50">{c.loadRows ? mwText(c.load) : "–"}</div>
          <div className={`text-[10px] ${muted}`}>free for new demand{c.loadRows ? `, ${c.loadRows.toLocaleString("en-US")} nodes` : ", no MW published"}</div>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <Donut counts={counts} />
        <div className="space-y-[1px] text-[10.5px]">
          {H_CLASSES.map((k) => (
            <div key={k} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(H_COLOR[k]) }} />
              <span className={muted}>{H_LABEL[k]}</span>
              <span className="tabular-nums text-slate-200">{counts[k].toLocaleString("en-US")}</span>
            </div>
          ))}
          <div className={`text-[9.5px] ${muted}`}>{side === "feedin" ? "new generation" : "new demand"} (switch in the key)</div>
        </div>
      </div>
      <div className="mt-2 space-y-[2px] text-[10px] leading-snug">
        {c.operators.slice(0, iso2 ? 12 : 40).map((o) => (
          <div key={o.cc + o.operator} className="flex justify-between gap-2">
            <span className="truncate text-slate-300">
              {iso2 ? "" : `${o.cc} · `}
              {o.operator}
            </span>
            <span className={`shrink-0 ${muted}`}>{o.as_of ?? "date not given"}</span>
          </div>
        ))}
      </div>
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        MW as each operator publishes them, summed (computed); operators that publish classes or MVA only, or say their nodes share capacity, are not in the sums. Classes: each
        operator&apos;s own, mapped to these four (see the tooltip).
      </div>
    </Card>
  );
}
