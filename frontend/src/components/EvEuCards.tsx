// EV charging in Europe (scripts/build_ev_eu.py): EAFO's public recharging points per country, AC and
// DC by year and by power class, and where the map's dots come from (a register or OpenStreetMap).

import { Card } from "./CountryCards";
import { EV_EU_COLOR, isRegister, type EvEuFile } from "../lib/evEu";
import { rgbCss } from "../lib/theme";

const muted = "text-[#8d94a1]";
const n = (v: number | null | undefined) => (v == null ? "–" : v.toLocaleString("en-US"));
const AC = "rgb(150,196,214)";
const DC = rgbCss(EV_EU_COLOR);

/** One country (iso2) or Europe (no iso2): EAFO's counts and the map's source. */
export function EvEuCard({ f, iso2, name }: { f: EvEuFile; iso2?: string; name?: string }) {
  if (!iso2) {
    const rows = Object.entries(f.eafo.countries)
      .map(([cc, c]) => ({ cc, ac: c.ac[c.ac.length - 1] ?? 0, dc: c.dc[c.dc.length - 1] ?? 0, year: c.years[c.years.length - 1] }))
      .sort((a, b) => b.ac + b.dc - (a.ac + a.dc));
    const top = rows[0] ? rows[0].ac + rows[0].dc : 1;
    return (
      <Card title="EV charging · Europe" note={`EAFO · ${rows[0]?.year ?? ""}`}>
        <div className="space-y-[3px]">
          {rows.map((r) => (
            <div key={r.cc} className="flex items-center gap-2 text-[11px] tabular-nums">
              <span className="w-6 text-slate-300">{r.cc}</span>
              <span className="flex h-[6px] flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
                <span style={{ width: `${(100 * r.ac) / top}%`, background: AC }} />
                <span style={{ width: `${(100 * r.dc) / top}%`, background: DC }} />
              </span>
              <span className="w-[64px] text-right text-slate-100">{n(r.ac + r.dc)}</span>
            </div>
          ))}
        </div>
        <Legend />
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          Public recharging points per country, newest year so far ({f.eafo.source}); AC + DC summed (computed). On the map: points from the national registers in{" "}
          {Object.entries(f.maps).filter(([, m]) => isRegister(m)).map(([cc]) => cc).join(", ")}, mapped stations from OpenStreetMap elsewhere, summed per {f.cell_deg}° cell.
        </div>
      </Card>
    );
  }
  const c = f.eafo.countries[iso2];
  const m = f.maps[iso2];
  if (!c && !m) return null;
  const k = c ? c.years.length - 1 : 0;
  const top = c ? Math.max(1, ...c.years.map((_, i) => (c.ac[i] ?? 0) + (c.dc[i] ?? 0))) : 1;
  return (
    <Card title="EV charging" note={`EAFO · ${c?.years[k] ?? ""}`}>
      {c && (
        <>
          <div className="text-[22px] font-light text-slate-50">
            {n((c.ac[k] ?? 0) + (c.dc[k] ?? 0))} <span className={`text-[11px] ${muted}`}>public recharging points in {name ?? iso2}, {c.years[k]} so far</span>
          </div>
          <div className={`text-[10.5px] ${muted}`}>
            AC {n(c.ac[k])} · DC {n(c.dc[k])}
          </div>
          <div className="mt-2 flex h-12 items-end gap-[3px]">
            {c.years.map((y, i) => (
              <div key={y} className="flex flex-1 flex-col justify-end" style={{ height: "100%" }} title={`${y}: AC ${n(c.ac[i])}, DC ${n(c.dc[i])}`}>
                <div style={{ height: `${(100 * (c.dc[i] ?? 0)) / top}%`, background: DC }} />
                <div className="rounded-b-sm" style={{ height: `${(100 * (c.ac[i] ?? 0)) / top}%`, background: AC }} />
              </div>
            ))}
          </div>
          <div className={`flex justify-between text-[9.5px] ${muted}`}>
            <span>{c.years[0]}</span>
            <span>{c.years[k]}</span>
          </div>
          <Legend />
          {c.classes && (
            <div className="mt-2 space-y-[2px] text-[10.5px]">
              {f.eafo.classes.map((label, i) => (
                <div key={label} className="flex justify-between gap-2">
                  <span className={`truncate ${muted}`}>{label}</span>
                  <span className="tabular-nums text-slate-200">{n(c.classes?.[i])}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
        {c ? `${f.eafo.source}, yearly; the newest year is the year so far. ` : ""}
        {m ? `On the map: ${n(m.n)} ${m.unit} from ${m.source} (${m.licence}), summed per ${f.cell_deg}° cell. ${m.note}.` : "No point data on the map for this country."}
      </div>
    </Card>
  );
}

function Legend() {
  return (
    <div className={`mt-1.5 flex gap-3 text-[10px] ${muted}`}>
      <span className="inline-flex items-center gap-1">
        <span className="h-1.5 w-2.5 rounded-sm" style={{ background: AC }} />
        AC
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-1.5 w-2.5 rounded-sm" style={{ background: DC }} />
        DC
      </span>
    </div>
  );
}
