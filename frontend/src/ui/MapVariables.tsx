// The map's variables at country scale: pick one (hexagons, bubbles or 3D columns, coloured by
// the largest type) or two (a 3×3 bivariate map), with the key; or open them side by side, one
// small map each. Zoomed in to city scale every record is drawn instead.

import { actions, useApp } from "../app/store";
import { Card } from "../components/CountryCards";
import { rgbCss } from "../lib/theme";
import { BIVARIATE, MAP_STYLES, POINTS_ZOOM, mapVariables, pickable, useHexInfo } from "../map/hexLayers";

const muted = "text-[#8d94a1]";

export function MapVariables() {
  const layers = useApp((s) => s.layers);
  const mapVars = useApp((s) => s.mapVars);
  const styles = useApp((s) => s.mapStyles);
  const compare = useApp((s) => s.compare);
  const info = useHexInfo();
  const options = pickable(layers);
  if (!options.length) return null;
  const vars = mapVariables({ layers, mapVars });
  const ids = vars.map((m) => m.id);
  const toggle = (id: string) => actions.setMapVars(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  const [a, b] = vars;
  const later = info.later.length;
  return (
    <Card title="On the map at country scale" note={info.rKm ? `hexagons of about ${info.rKm * 2} km` : undefined} accent={[120, 190, 255]}>
      <div className={`text-[10.5px] leading-snug ${muted}`}>
        One variable, or two for a map of both; zoomed in to city scale (zoom {POINTS_ZOOM}) every record is drawn. Colours follow what is in view.
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {options.map((m) => {
          const on = ids.includes(m.id);
          return (
            <button
              key={m.id}
              onClick={() => toggle(m.id)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] ${on ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: rgbCss(m.color) }} />
              {m.label}
              {on && vars.length === 2 && <span className="text-[9px] text-sky-200/80">{m.id === a.id ? "→" : "↑"}</span>}
            </button>
          );
        })}
      </div>
      {a && !b && (
        <>
          <div className="mt-2 flex items-center gap-1">
            <span className={`text-[10px] ${muted}`}>Draw as</span>
            {MAP_STYLES.map(([st, label]) => (
              <button
                key={st}
                onClick={() => actions.setMapStyle(a.id, st)}
                className={`rounded-md border px-2 py-0.5 text-[10.5px] ${(styles[a.id] ?? "hex") === st ? "border-white/30 bg-white/15 text-slate-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
            Each {styles[a.id] === "bubbles" ? "bubble" : styles[a.id] === "columns" ? "column" : "hexagon"} sums the {a.sums}. Colour: its largest type
            {a.types ? "" : " (one colour)"}; {styles[a.id] === "bubbles" ? "area" : styles[a.id] === "columns" ? "height" : "strength"}: the square root of its share of the largest in view
            {info.max > 0 ? ` (${a.fmt(info.max)})` : ""}. Computed.
          </div>
        </>
      )}
      {a && b && info.breaks && (
        <div className="mt-2.5 flex items-start gap-3">
          <div>
            <div className="grid grid-cols-3 gap-[2px]" style={{ transform: "scaleY(-1)" }}>
              {[0, 1, 2].flatMap((y) => [0, 1, 2].map((x) => <span key={`${x}${y}`} className="h-4 w-4 rounded-[2px]" style={{ background: rgbCss(BIVARIATE[y][x]) }} />))}
            </div>
            <div className={`mt-0.5 text-[9px] ${muted}`}>{a.label} →</div>
          </div>
          <div className={`text-[10px] leading-snug ${muted}`}>
            <div>
              <span className="text-slate-300">→ {a.label}:</span> low under {a.fmt(info.breaks[0][0])}, high from {a.fmt(info.breaks[0][1])}
            </div>
            <div>
              <span className="text-slate-300">↑ {b.label}:</span> low under {b.fmt(info.breaks[1][0])}, high from {b.fmt(info.breaks[1][1])}
            </div>
            <div className="mt-1">Classes: thirds of the hexagons with a value (computed). Light: high on both; dark: low on both.</div>
          </div>
        </div>
      )}
      <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-white/[0.06] pt-2">
        <span className={`text-[10px] leading-snug ${muted}`}>
          {later > 0 ? `${later} more ${later === 1 ? "dataset waits" : "datasets wait"} for city scale on this map.` : "Each variable in a map of its own:"}
        </span>
        <button
          onClick={() => actions.setCompare(!compare)}
          className={`shrink-0 rounded-md border px-2 py-0.5 text-[10.5px] ${compare ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-200 hover:bg-white/[0.08]"}`}
        >
          {compare ? "Back to one map" : `Side by side (${Math.min(6, options.length)})`}
        </button>
      </div>
    </Card>
  );
}
