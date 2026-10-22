// The Dashboard tab: the dashboard's area and what the map's files hold inside it (components/
// AreaCards.tsx: plants, grid, room to connect, registers, demand, emissions, fuels, land and risk,
// electricity for countries), then the figures of the datasets switched on. The area is the country
// clicked on the map, else the dashboard's countries, drawn polygon or circle around a city.

import { DATASETS, covers, datasetOn, partsFor, partsIn, placesText, toggleDataset } from "../app/datasets";
import { useAreaShape } from "../app/areaShape";
import { actions, useApp } from "../app/store";
import { AreaCards } from "../components/AreaCards";
import { Card } from "../components/CountryCards";
import { km2Text } from "../lib/area";
import { useDashboardName } from "./Dashboards";
import { LayerStatsTab } from "./LayerStats";

const muted = "text-[#8d94a1]";
const RADII = [5, 10, 25, 50, 100];

function AreaControls() {
  const drawn = useApp((s) => s.drawn);
  const area = useApp((s) => s.area);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      {drawn?.kind === "circle" &&
        RADII.map((r) => (
          <button
            key={r}
            onClick={() => actions.setDrawn({ ...drawn, r })}
            className={`rounded-full border px-2 py-0.5 text-[10.5px] ${drawn.r === r ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
          >
            {r} km
          </button>
        ))}
      <button onClick={() => actions.startDrawing()} className="rounded-full border border-white/10 px-2 py-0.5 text-[10.5px] text-slate-300 hover:bg-white/[0.07]">
        ⬠ Draw another area
      </button>
      {(drawn || area) && (
        <button onClick={() => (drawn ? actions.setDrawn(null) : actions.setArea(null))} className="rounded-full border border-white/10 px-2 py-0.5 text-[10.5px] text-slate-400 hover:bg-white/[0.07] hover:text-slate-100">
          Clear the area
        </button>
      )}
    </div>
  );
}

/** The datasets with data in the area that are not on the map: one click adds one. */
function AlsoHere({ area }: { area: string[] }) {
  const layers = useApp((s) => s.layers);
  const mode = useApp((s) => s.mode);
  const colour = useApp((s) => s.colour);
  const more = DATASETS.filter((d) => partsIn(d, mode).length > 0 && !datasetOn(d, layers, colour) && covers(d, area) && !d.colour);
  if (!more.length) return null;
  return (
    <div className="mt-2.5 border-t border-white/[0.06] pt-2">
      <div className={`mb-1 text-[9.5px] uppercase tracking-[0.16em] ${muted}`}>Also with data here · add to the map</div>
      <div className="flex flex-wrap gap-1">
        {more.map((d) => (
          <button
            key={d.id}
            onClick={() => toggleDataset(d)}
            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 py-0.5 pl-2 pr-2 text-[10.5px] text-slate-300 hover:border-white/25 hover:text-slate-100"
            title={d.description}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />+ {d.name}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DashboardTab({ iso3 }: { iso3?: string }) {
  const layers = useApp((s) => s.layers);
  const mode = useApp((s) => s.mode);
  const { name, edited, mineId } = useDashboardName();
  const { shape, pending } = useAreaShape(iso3);
  const colour = useApp((s) => s.colour);
  const on = DATASETS.filter((d) => partsIn(d, mode).length > 0 && datasetOn(d, layers, colour));
  const scope = shape?.countries ?? null;
  return (
    <>
      <Card title={name} note={edited ? "edited" : undefined} accent={[120, 190, 255]}>
        <div className="flex items-start justify-between gap-2 text-[11px]">
          <span className="min-w-0 text-slate-300">
            <span className={muted}>Area: </span>
            {shape ? (
              <>
                {shape.label} <span className={muted}>· {km2Text(shape.km2)}</span>
              </>
            ) : pending ? (
              "reading the outlines…"
            ) : (
              "none yet"
            )}
          </span>
          <button onClick={() => actions.openBuilder({ kind: "save", id: mineId })} className="shrink-0 rounded-md border border-white/10 px-2 py-0.5 text-[10.5px] text-slate-300 hover:bg-white/[0.08]">
            {edited || !mineId ? "Save as dashboard" : "Edit"}
          </button>
        </div>
        {!iso3 && <AreaControls />}
        {!shape && !pending && (
          <div className={`mt-2 text-[11px] leading-snug ${muted}`}>
            Pick an area for its figures: click a country, <span className="text-slate-200">⬠ Draw an area</span> on the map, or search a city (25 km around it). Below: the datasets on the map, worldwide.
          </div>
        )}
        {on.length > 0 && (
          <div className="mt-2.5 space-y-1 border-t border-white/[0.06] pt-2">
            {on.map((d) => {
              const here = partsFor(d, scope).filter((p) => partsIn(d, mode).includes(p));
              return (
                <div key={d.id} className="flex items-start gap-2 text-[11px] leading-snug">
                  <span className="mt-[4px] h-2 w-2 shrink-0 rounded-full" style={{ background: d.color }} />
                  <span className="min-w-0 flex-1">
                    <span className="text-slate-200">{d.name}</span>
                    <span className={`block text-[10px] ${muted}`}>{here.length ? here.map((p) => `${placesText(p.where)}: ${p.source}`).join(" · ") : "No data in this area"}</span>
                  </span>
                </div>
              );
            })}
          </div>
        )}
        {shape?.countries && <AlsoHere area={shape.countries} />}
      </Card>
      {shape && <AreaCards s={shape} />}
      {(!shape || iso3) && on.length > 0 && <LayerStatsTab iso3={iso3} />}
    </>
  );
}
