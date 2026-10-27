// How a dataset is drawn: the same style menu on the main map and in the Maps view (points,
// bubbles, hexagons, 3D bars, 3D beams; raster, choropleth, 3D terrain), and the key of what the
// style shows in view, with what each figure is and where it comes from. `compact` keeps a key to
// one or two lines (the Maps view's small maps); the explanation then shows on request.

import type { Style } from "../app/maps";
import { measureOfDataset, RASTER_BY_DATASET } from "../lib/measures";
import { rgbCss } from "../lib/theme";
import { BIVARIATE, hexInfoKey, useHexInfo } from "../map/hexLayers";
import { STYLE_LABEL, stylesOf, useStyleInfo } from "../map/styleLayers";

const muted = "text-[#8d94a1]";
const NOTE = "text-[#e0b070]";

/** The style buttons of a dataset (none for a dataset drawn one way only). */
export function StyleChips({ dataset, value, onChange }: { dataset: string; value: Style | undefined; onChange: (st: Style) => void }) {
  const styles = stylesOf(dataset);
  if (!styles.length) return null;
  const current = value && styles.includes(value) ? value : styles[0];
  return (
    <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Draw as">
      {styles.map((st) => (
        <button
          key={st}
          role="radio"
          aria-checked={current === st}
          onClick={() => onChange(st)}
          className={`rounded-md border px-1.5 py-[1px] text-[10px] ${current === st ? "border-sky-300/50 bg-sky-400/15 text-sky-50" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
        >
          {STYLE_LABEL[st]}
        </button>
      ))}
    </div>
  );
}

/** The same menu as a small drop-down (one line on a small map). */
export function StyleSelect({ dataset, value, onChange }: { dataset: string; value: Style | undefined; onChange: (st: Style) => void }) {
  const styles = stylesOf(dataset);
  if (!styles.length) return null;
  const current = value && styles.includes(value) ? value : styles[0];
  return (
    <select
      value={current}
      onChange={(e) => onChange(e.target.value as Style)}
      className="rounded border border-white/10 bg-[#0b0f16] px-0.5 py-0 text-[10px] text-slate-200"
      aria-label="Draw as"
      title="Draw as"
    >
      {styles.map((st) => (
        <option key={st} value={st}>
          {STYLE_LABEL[st]}
        </option>
      ))}
    </select>
  );
}

/** A figure with its unit, unless the format already carries one (GW, Mt...). */
const unitText = (fmt: (v: number) => string, unit: string, v: number) => {
  const t = fmt(v);
  return unit && /^[\d.,\s−-]+$/.test(t) ? `${t} ${unit}` : t;
};

/** What a styled dataset shows in view: the scale, its largest figure, what it sums and the source. */
export function StyleKey({ scope, dataset, style, compact = false }: { scope: string; dataset: string; style: Style | undefined; compact?: boolean }) {
  const info = useStyleInfo((s) => s[`${scope}:${dataset}`]);
  const hex = useHexInfo((s) => s[hexInfoKey(scope, [dataset])]);
  const r = RASTER_BY_DATASET.get(dataset);
  const m = measureOfDataset(dataset);
  if (!style || style === "points" || style === "raster" || style === "lines") return null;
  const bar = compact ? "w-24" : "w-40";
  if (r && (style === "choropleth" || style === "terrain")) {
    if (info?.note) return <div className={`mt-0.5 text-[9.5px] leading-snug ${NOTE}`}>{info.note}</div>;
    const ramp = `linear-gradient(90deg, ${r.ramp.map((c) => rgbCss(c)).join(", ")})`;
    return (
      <div className={compact ? "mt-0.5 flex items-center gap-1.5" : "mt-1.5"}>
        <div className={`h-1.5 ${bar} rounded-sm`} style={{ background: ramp }} />
        <div className={`flex ${compact ? "gap-1" : `${bar} justify-between`} text-[9px] ${muted}`}>
          <span>{info ? r.fmt(info.min) : "reading…"}</span>
          {compact && info && <span>–</span>}
          <span>{info ? `${r.fmt(info.max)} ${r.unit}` : ""}</span>
        </div>
        {!compact && (
          <div className={`mt-0.5 text-[9.5px] leading-snug ${muted}`}>
            {style === "terrain" ? "Height and colour" : "Colour"}: the mean of the grid's cells in each hexagon{info ? ` of about ${info.rKm * 2} km` : ""}, stretched over the range in view (computed). {r.sums}.
          </div>
        )}
      </div>
    );
  }
  if (!m) return null;
  if (style === "hex") {
    if (!hex) return <div className={`mt-0.5 text-[9.5px] ${muted}`}>Loading…</div>;
    if (!hex.total) return <div className={`mt-0.5 text-[9.5px] leading-snug ${NOTE}`}>No record in the file has a position in this area.</div>;
    return (
      <div className={compact ? "mt-0.5 flex items-center gap-1.5" : "mt-1.5"}>
        <div className={`h-1.5 ${bar} rounded-sm`} style={{ background: `linear-gradient(90deg, ${rgbCss(m.color, 0.18)}, ${rgbCss(m.color)})` }} />
        <div className={`flex ${compact ? "gap-1" : `${bar} justify-between`} text-[9px] ${muted}`}>
          <span>0</span>
          {compact && <span>–</span>}
          <span>{unitText(m.fmt, m.unit, hex.max)}</span>
        </div>
        {!compact && (
          <div className={`mt-0.5 text-[9.5px] leading-snug ${muted}`}>
            Each hexagon of about {hex.rKm * 2} km sums the {m.sums}. Colour: its largest type; strength: the square root of its share of the largest in view (computed).
          </div>
        )}
      </div>
    );
  }
  if (info && !info.total) return <div className={`mt-0.5 text-[9.5px] leading-snug ${NOTE}`}>No record in the file has a position in this area.</div>;
  const what = style === "bubbles" ? "Area" : "Height";
  const types = info?.types.slice(0, compact ? 4 : 6) ?? [];
  return (
    <div className="mt-0.5">
      {types.length > 0 && (
        <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9.5px] text-slate-300">
          {types.map(([t, c]) => (
            <span key={t} className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: rgbCss(c) }} />
              {t}
            </span>
          ))}
        </div>
      )}
      <div className={`text-[9.5px] leading-snug ${muted}`}>
        {compact ? (
          info ? (
            `${what} by value · largest in view ${unitText(m.fmt, m.unit, info.max)} · ${info.count.toLocaleString("en-US")} in view`
          ) : (
            "Loading…"
          )
        ) : (
          <>
            One {style === "bubbles" ? "bubble" : style === "bars" ? "bar" : "beam"} per record. {what}: the square root of its share of the largest in view
            {info ? ` (${unitText(m.fmt, m.unit, info.max)}, ${info.count.toLocaleString("en-US")} in view)` : ""}. {m.sums}.
          </>
        )}
      </div>
    </div>
  );
}

/** The explanation of a styled dataset's key, for the compact keys' details. */
export function StyleText({ dataset, style }: { dataset: string; style: Style | undefined }) {
  const r = RASTER_BY_DATASET.get(dataset);
  const m = measureOfDataset(dataset);
  if (!style || style === "points" || style === "raster" || style === "lines") return null;
  if (r) return <>{style === "terrain" ? "Height and colour" : "Colour"}: the mean of the grid's cells in each hexagon, stretched over the range in view (computed). {r.sums}.</>;
  if (!m) return null;
  if (style === "hex") return <>Each hexagon sums the {m.sums}; strength: the square root of its share of the largest in view (computed).</>;
  return (
    <>
      One {style === "bubbles" ? "bubble" : style === "bars" ? "bar" : "beam"} per record; {style === "bubbles" ? "area" : "height"}: the square root of its share of the largest in view (computed). {m.sums}.
    </>
  );
}

/** Two datasets as hexagons on one map: the 3×3 key and each one's class breaks. */
export function BivariateKey({ scope, a, b, compact = false }: { scope: string; a: string; b: string; compact?: boolean }) {
  const info = useHexInfo((s) => s[hexInfoKey(scope, [a, b])]);
  const ma = measureOfDataset(a);
  const mb = measureOfDataset(b);
  if (!ma || !mb) return null;
  const cell = compact ? "h-2.5 w-2.5" : "h-3.5 w-3.5";
  return (
    <div className="flex items-start gap-2">
      <div className="grid shrink-0 grid-cols-3 gap-[2px]" style={{ transform: "scaleY(-1)" }}>
        {[0, 1, 2].flatMap((y) => [0, 1, 2].map((x) => <span key={`${x}${y}`} className={`${cell} rounded-[2px]`} style={{ background: rgbCss(BIVARIATE[y][x]) }} />))}
      </div>
      <div className={`text-[9.5px] leading-snug ${muted}`}>
        {info?.breaks ? (
          <>
            <div>
              <span className="text-slate-300">→ {ma.label}:</span> low under {ma.fmt(info.breaks[0][0])}, high from {ma.fmt(info.breaks[0][1])}
            </div>
            <div>
              <span className="text-slate-300">↑ {mb.label}:</span> low under {mb.fmt(info.breaks[1][0])}, high from {mb.fmt(info.breaks[1][1])}
            </div>
            {!compact && (
              <div className="mt-0.5">
                Hexagons of about {info.rKm * 2} km; classes: thirds of the hexagons in view with a value (computed). Light: high on both; dark: low on both.
              </div>
            )}
          </>
        ) : (
          "Loading…"
        )}
      </div>
    </div>
  );
}
