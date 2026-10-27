// How the map draws each dataset with figures: the style menu (points, bubbles, hexagons, 3D bars
// or beams; raster, choropleth, 3D terrain), the same for every dataset, place and zoom, with its
// key. Two datasets as hexagons make a bivariate map. The Maps view shows the place in several maps.

import { DATASET_BY_ID, datasetsOn } from "../app/datasets";
import type { Style } from "../app/maps";
import { actions, useApp } from "../app/store";
import { Card } from "../components/CountryCards";
import { STYLE_LABEL, applyStyles, styleOf, stylesOf } from "../map/styleLayers";
import { openMaps } from "./MapsView";
import { BivariateKey, StyleChips, StyleKey } from "./StyleControls";

const muted = "text-[#8d94a1]";
const POINTS: Style[] = ["points", "bubbles", "hex", "bars", "beams"];

export function MapVariables() {
  const layers = useApp((s) => s.layers);
  const colour = useApp((s) => s.colour);
  const styles = useApp((s) => s.mapStyles);
  const compare = useApp((s) => s.compare);
  const maps = useApp((s) => s.maps);
  const on = datasetsOn(layers, colour).filter((d) => stylesOf(d.id).length > 0);
  // in the order they were picked, as the map draws them (map/hexLayers.ts)
  const hexes = applyStyles(layers, styles)
    .styled.filter(([, st]) => st === "hex")
    .map(([d]) => d)
    .slice(0, 2);
  const points = on.filter((d) => stylesOf(d.id).includes("bubbles"));
  return (
    <Card title="On the map" note="the same styles at every scale" accent={[120, 190, 255]}>
      {on.length === 0 && <div className={`text-[10.5px] leading-snug ${muted}`}>Switch on a dataset with figures (plants, emitters, registers, resources...) to choose how it is drawn.</div>}
      <div className="space-y-2.5">
        {on.map((d) => (
          <div key={d.id}>
            <div className="mb-1 flex items-center gap-1.5 text-[11px] text-slate-200">
              <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
              {d.name}
            </div>
            <StyleChips dataset={d.id} value={styleOf(styles, d.id)} onChange={(st) => actions.setMapStyle(d.id, st)} />
            {!(hexes.length === 2 && hexes.includes(d.id)) && <StyleKey scope="main" dataset={d.id} style={styleOf(styles, d.id)} />}
          </div>
        ))}
      </div>
      {hexes.length === 2 && (
        <div className="mt-2.5 border-t border-white/[0.06] pt-2">
          <div className="mb-1 text-[10.5px] text-slate-300">
            {DATASET_BY_ID.get(hexes[0])?.name} × {DATASET_BY_ID.get(hexes[1])?.name}: a map of both
          </div>
          <BivariateKey scope="main" a={hexes[0]} b={hexes[1]} />
        </div>
      )}
      {points.length > 1 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1 border-t border-white/[0.06] pt-2">
          <span className={`mr-1 text-[10px] ${muted}`}>All as</span>
          {POINTS.map((st) => (
            <button
              key={st}
              onClick={() => actions.setMapStyles(Object.fromEntries(points.map((d) => [d.id, st])))}
              className="rounded-md border border-white/10 px-1.5 py-[1px] text-[10px] text-slate-300 hover:bg-white/[0.07]"
            >
              {STYLE_LABEL[st]}
            </button>
          ))}
        </div>
      )}
      <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-white/[0.06] pt-2">
        <span className={`text-[10px] leading-snug ${muted}`}>Several maps of this place, one camera (six at most):</span>
        <button
          onClick={() => (compare ? actions.setCompare(false) : openMaps())}
          className={`shrink-0 rounded-md border px-2 py-0.5 text-[10.5px] ${compare ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-200 hover:bg-white/[0.08]"}`}
        >
          {compare ? "Back to one map" : maps.length ? `Maps (${maps.length})` : "Maps"}
        </button>
      </div>
    </Card>
  );
}
