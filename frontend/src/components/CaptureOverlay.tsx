import type { GridHistoryPoint, GridSnapshotLatest } from "../lib/api";
import type { CaptureConfig } from "../lib/capture";
import { EXCHANGE_COLOR, PLANT_COLOR, POWER_LINE_COLOR, type PlantGroup } from "../lib/powerScene";
import { rgbCss, type RGB } from "../lib/theme";

// Text and legend layer of the video stage. Rules for this file (see docs/VIDEO.md):
// every number is an Energy-Charts value passed through unchanged, all from one
// interval; nothing is computed or estimated; no dates, times or "live" wording.

const FUELS: Array<{ metric: string; label: string; group: PlantGroup }> = [
  { metric: "gen_wind", label: "Wind", group: "wind" },
  { metric: "gen_solar", label: "Solar", group: "solar" },
  { metric: "gen_lignite", label: "Lignite", group: "fossil" },
  { metric: "gen_hard_coal", label: "Hard coal", group: "fossil" },
  { metric: "gen_gas", label: "Gas", group: "fossil" },
  { metric: "gen_biomass", label: "Biomass", group: "other" },
  { metric: "gen_hydro", label: "Hydro", group: "other" },
];

function LineKey({ color, label }: { color: RGB; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="18" height="6" viewBox="0 0 18 6" aria-hidden>
        <line x1="1" y1="3" x2="17" y2="3" stroke={rgbCss(color)} strokeWidth="1.3" strokeLinecap="round" />
        <circle cx="11" cy="3" r="1.7" fill="#f4f8ff" />
      </svg>
      {label}
    </span>
  );
}

function SymbolKey({ label, ring = false }: { label: string; ring?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden>
        {ring ? (
          <circle cx="4" cy="4" r="2.6" fill="#111721" stroke={rgbCss(POWER_LINE_COLOR.v380)} strokeWidth="1.1" />
        ) : (
          <circle cx="4" cy="4" r="3.2" fill="#c9d3df" />
        )}
      </svg>
      {label}
    </span>
  );
}

function StackedChart({
  wind,
  solar,
  width,
}: {
  wind: GridHistoryPoint[];
  solar: GridHistoryPoint[];
  width: number;
}) {
  const W = width;
  const H = 38;
  const solarAt = new Map(solar.map((p) => [p.ts, p.value]));
  const pts = wind.map((p) => ({ t: Date.parse(p.ts), w: Math.max(0, p.value), s: Math.max(0, solarAt.get(p.ts) ?? 0) }));
  if (pts.length < 2) return null;
  const t0 = pts[0].t;
  const t1 = pts[pts.length - 1].t;
  const top = Math.max(...pts.map((p) => p.w + p.s)) || 1;
  const x = (t: number) => ((t - t0) / (t1 - t0)) * W;
  const y = (v: number) => H - (v / top) * (H - 2);
  // stacking is visual only: solar is drawn on top of wind, no total is shown
  const area = (lower: (p: (typeof pts)[number]) => number, upper: (p: (typeof pts)[number]) => number) =>
    `M${pts.map((p) => `${x(p.t).toFixed(1)},${y(upper(p)).toFixed(1)}`).join("L")}` +
    `L${pts
      .slice()
      .reverse()
      .map((p) => `${x(p.t).toFixed(1)},${y(lower(p)).toFixed(1)}`)
      .join("L")}Z`;
  return (
    <svg width={W} height={H + 2} viewBox={`0 0 ${W} ${H + 2}`} aria-hidden>
      <line x1="0" y1={H + 0.5} x2={W} y2={H + 0.5} stroke="rgba(150,162,182,0.25)" strokeWidth="1" />
      <path d={area(() => 0, (p) => p.w)} fill={rgbCss(PLANT_COLOR.wind, 0.55)} stroke={rgbCss(PLANT_COLOR.wind)} strokeWidth="0.8" />
      <path
        d={area((p) => p.w, (p) => p.w + p.s)}
        fill={rgbCss(PLANT_COLOR.solar, 0.5)}
        stroke={rgbCss(PLANT_COLOR.solar)}
        strokeWidth="0.8"
      />
    </svg>
  );
}

export default function CaptureOverlay({
  capture,
  latest,
  windHistory,
  solarHistory,
}: {
  capture: CaptureConfig;
  latest: GridSnapshotLatest;
  windHistory: GridHistoryPoint[];
  solarHistory: GridHistoryPoint[];
}) {
  // all generation figures come from one interval: metrics from any other are dropped
  const genTs = latest.gen_wind?.ts;
  const value = (metric: string) => {
    const row = latest[metric];
    return row && row.ts === genTs ? Number(row.value) : undefined;
  };
  const rows = FUELS.map((f) => ({ ...f, mw: value(f.metric) }));
  const maxMw = Math.max(1, ...rows.map((r) => r.mw ?? 0));
  const tall = capture.format === "9x16";
  const band = tall ? 250 : 150;

  const keys = (
    <div className={`space-y-1 text-[7px] text-slate-300 ${tall ? "" : "flex flex-col items-end"}`}>
      <div className="flex gap-3">
        <LineKey color={POWER_LINE_COLOR.v380} label="380 kV" />
        <LineKey color={POWER_LINE_COLOR.v220} label="220 kV" />
        <LineKey color={EXCHANGE_COLOR} label="Cross-border flow" />
      </div>
      <div className="flex gap-3">
        <SymbolKey label="Power plant (size = capacity)" />
        <SymbolKey label="Substation" ring />
      </div>
    </div>
  );

  return (
    <div className="pointer-events-none absolute inset-0 z-10 select-none text-slate-100">
      {/* scrims: the map fades out under the text bands instead of fighting them */}
      <div
        className="absolute inset-x-0 top-0"
        style={{ height: band, background: "linear-gradient(to bottom, rgba(7,9,14,0.92) 35%, rgba(7,9,14,0))" }}
      />
      <div
        className="absolute inset-x-0 bottom-0"
        style={{ height: tall ? 190 : 118, background: "linear-gradient(to top, rgba(7,9,14,0.95) 50%, rgba(7,9,14,0))" }}
      />

      {/* title card: says what the frame shows, no headline number (a single
          snapshot figure reads like a national statistic) */}
      <div className="absolute left-5 top-4">
        <div className="font-serif text-[30px] uppercase leading-none tracking-[0.2em]">Germany</div>
        <div className="mt-2 text-[9px] uppercase tracking-[0.32em] text-[#aab3c0]">Power grid &amp; plants</div>
      </div>

      {/* 48 h wind + solar generation, with the map keys underneath */}
      <div className={tall ? "absolute left-5" : "absolute right-4 top-4 flex flex-col items-end"} style={{ top: tall ? 116 : undefined }}>
        {windHistory.length > 1 && (
          <>
            <div className="mb-1 text-[7px] uppercase tracking-[0.24em] text-[#8d94a1]">Wind + solar generation · last 48 h</div>
            <StackedChart wind={windHistory} solar={solarHistory} width={tall ? 300 : 168} />
          </>
        )}
        <div className="mt-2.5">{keys}</div>
      </div>

      {/* generation strip: label, GW, bar; generous spacing so it reads at phone size */}
      <div className="absolute inset-x-5 bottom-[30px]">
        <div className="mb-1.5 text-[7px] uppercase tracking-[0.24em] text-[#8d94a1]">Generation by source · GW</div>
        <div className="grid grid-cols-7 gap-x-4">
          {rows.map((r) => {
            const c = PLANT_COLOR[r.group];
            return (
              <div key={r.metric}>
                <div className="flex items-center gap-1 text-[7.5px] uppercase tracking-[0.08em] text-[#9aa3b1]">
                  <span className="h-[5px] w-[5px] shrink-0 rounded-full" style={{ background: rgbCss(c) }} />
                  <span className="truncate">{r.label}</span>
                </div>
                <div className="mt-0.5 text-[14px] font-light leading-none tabular-nums text-slate-50">
                  {r.mw == null ? "–" : (r.mw / 1000).toFixed(1)}
                </div>
                <div className="mt-1.5 h-[2.5px] w-full rounded-full bg-white/[0.07]">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${((r.mw ?? 0) / maxMw) * 100}%`, background: rgbCss(c) }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* sources + disclosure (basemap attribution is required), brand on the right */}
      <div className="absolute inset-x-5 bottom-[8px] flex items-end justify-between gap-4 text-[5.5px] leading-[1.5] tracking-[0.02em] text-[#5d6574]">
        <div>
          <div>
            Energy-Charts (Fraunhofer ISE) · © OpenStreetMap contributors · MaStR (open-mastr), plants grouped by ~28 km ·
            © EuroGeographics · © CARTO
          </div>
          <div>Dot direction on lines inside Germany is illustrative: per-line flows are not published</div>
        </div>
        <div className="shrink-0 text-[6px] uppercase tracking-[0.24em] text-[#8d94a1]">Germany InfraAtlas</div>
      </div>
    </div>
  );
}
