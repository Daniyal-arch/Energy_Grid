// The Dashboard tab: the dashboard's datasets and their figures for its area. It follows the
// datasets switched on (each adds its card) and the area: one country, a pick among several, or
// the country clicked on the map. Every figure is the dataset card's own (ui/LayerStats.tsx).

import { useState } from "react";

import { DATASETS, partsFor, partsIn, placesText } from "../app/datasets";
import { actions, useApp } from "../app/store";
import { Card } from "../components/CountryCards";
import { areaText, useCountryNames, useDashboardName } from "./Dashboards";
import { LayerStatsTab } from "./LayerStats";

const muted = "text-[#8d94a1]";

export function DashboardTab({ iso3 }: { iso3?: string }) {
  const area = useApp((s) => s.area);
  const layers = useApp((s) => s.layers);
  const mode = useApp((s) => s.mode);
  const { name, edited, mineId } = useDashboardName();
  const names = useCountryNames();
  const [pick, setPick] = useState<string | null>(null);
  const several = !iso3 && area && area.length > 1 ? area : null;
  const one = iso3 ?? (area?.length === 1 ? area[0] : several ? (pick && several.includes(pick) ? pick : several[0]) : undefined);
  const scope = one ? [one] : area;
  const on = DATASETS.filter((d) => partsIn(d, mode).some((p) => layers[p.layer]));
  return (
    <>
      <Card title={name} note={edited ? "edited" : undefined} accent={[120, 190, 255]}>
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <span className="text-slate-300">
            <span className={muted}>Area: </span>
            {iso3 ? names(iso3) : areaText(area, names)}
          </span>
          <button onClick={() => actions.openBuilder({ kind: "save", id: mineId })} className="shrink-0 rounded-md border border-white/10 px-2 py-0.5 text-[10.5px] text-slate-300 hover:bg-white/[0.08]">
            {edited || !mineId ? "Save as dashboard" : "Edit"}
          </button>
        </div>
        <div className="mt-2 space-y-1">
          {on.length === 0 && <div className={`text-[11px] ${muted}`}>No datasets on: switch some on in the Datasets panel, or pick a dashboard at the top.</div>}
          {on.map((d) => {
            const here = partsFor(d, scope ?? null).filter((p) => partsIn(d, mode).includes(p));
            return (
              <div key={d.id} className="flex items-start gap-2 text-[11px] leading-snug">
                <span className="mt-[4px] h-2 w-2 shrink-0 rounded-full" style={{ background: d.color }} />
                <span className="min-w-0 flex-1">
                  <span className="text-slate-200">{d.name}</span>
                  <span className={`block text-[10px] ${muted}`}>
                    {here.length ? here.map((p) => `${placesText(p.where)}: ${p.source}`).join(" · ") : `No data in ${scope ? "this area" : "view"}`}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </Card>
      {several && (
        <div className="flex flex-wrap gap-1 px-1">
          <span className={`py-0.5 text-[10.5px] ${muted}`}>Figures for</span>
          {several.map((c) => (
            <button
              key={c}
              onClick={() => setPick(c)}
              className={`rounded-full border px-2 py-0.5 text-[10.5px] ${c === one ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
            >
              {names(c)}
            </button>
          ))}
        </div>
      )}
      {on.length > 0 && <LayerStatsTab iso3={one} />}
    </>
  );
}
