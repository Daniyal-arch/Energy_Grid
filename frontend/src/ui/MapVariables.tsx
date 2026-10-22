// The map's variables at country scale: pick one (hexagons coloured by the largest type) or two
// (a 3×3 bivariate map), with the key. Zoomed in to city scale every record is drawn instead.

import { actions, useApp } from "../app/store";
import { Card } from "../components/CountryCards";
import { rgbCss } from "../lib/theme";
import { BIVARIATE, POINTS_ZOOM, mapVariables, pickable, useHexInfo } from "../map/hexLayers";

const muted = "text-[#8d94a1]";

export function MapVariables() {
  const layers = useApp((s) => s.layers);
  const mapVars = useApp((s) => s.mapVars);
  const info = useHexInfo();
  const options = pickable(layers);
  if (!options.length) return null;
  const vars = mapVariables({ layers, mapVars });
  const ids = vars.map((m) => m.id);
  const toggle = (id: string) => actions.setMapVars(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  const [a, b] = vars;
  return (
    <Card title="On the map at country scale" note={info.rKm ? `hexagons of about ${info.rKm * 2} km` : undefined} accent={[120, 190, 255]}>
      <div className={`text-[10.5px] leading-snug ${muted}`}>Pick one variable, or two for a map of both. Zoomed in to city scale (zoom {POINTS_ZOOM}) every record is drawn.</div>
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
        <div className={`mt-2 text-[10px] leading-snug ${muted}`}>
          Each hexagon sums the {a.sums}. Colour: its largest type{a.types ? "" : " (one colour)"}; strength: the square root of its share of the largest hexagon
          {info.max > 0 ? ` (${a.fmt(info.max)})` : ""}. Computed.
        </div>
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
    </Card>
  );
}
