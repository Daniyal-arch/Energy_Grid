// The time control (Live · 24 h · Years) and, below the map, the clock of the chosen mode.

import { rgbCss } from "../lib/theme";
import type { TransitionFile } from "../lib/transition";
import { useFile } from "../app/data";
import { CAPTION_SLOTS, captionText, dayLabel, marketTime } from "../app/day";
import { actions, motion, useApp, type TimeMode } from "../app/store";
import type { CountriesFile, DayFile, FlowsFile } from "../app/types";

const MODES: { id: TimeMode; label: string; title: string }[] = [
  { id: "live", label: "Live", title: "Now: the newest 15-min interval" },
  { id: "day", label: "24 h", title: "Replay a whole day, every 15 minutes" },
  { id: "years", label: "Years", title: "2000 to today, year by year (Ember)" },
];

export function TimeControl({ small = false }: { small?: boolean }) {
  const mode = useApp((s) => s.mode);
  return (
    <div className="flex rounded-lg border border-white/10 bg-[#0b0f16]/90 p-0.5 backdrop-blur" role="tablist" aria-label="Time">
      {MODES.map((m) => (
        <button
          key={m.id}
          role="tab"
          aria-selected={mode === m.id}
          title={m.title}
          onClick={() => actions.setMode(m.id)}
          className={`rounded-md ${small ? "px-2.5 py-1 text-[11.5px]" : "px-3 py-1 text-[12px]"} transition-colors ${
            mode === m.id ? "bg-white/[0.14] text-slate-50" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          {m.id === "live" && <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${mode === "live" ? "bg-emerald-400" : "bg-slate-500"}`} />}
          {m.label}
        </button>
      ))}
    </div>
  );
}

function useDay() {
  const want = useApp((s) => s.day);
  const index = useFile<{ all: string[]; remote: string[] }>("dayIndex");
  const date = want && index?.all.includes(want) ? want : (index?.all[index.all.length - 1] ?? null);
  const day = useFile<DayFile>(date ? `day:${date}` : null);
  return { index, date, day };
}

function DayBar() {
  const slot = useApp((s) => s.slot);
  const playing = useApp((s) => s.playing);
  const { index, date, day } = useDay();
  const countries = useFile<CountriesFile>("countries");
  const name = (iso?: string) => countries?.countries.find((c) => c.iso === iso)?.name ?? iso ?? "";
  if (!day || !date) return <div className="text-[12px] text-[#8d94a1]">Loading the day…</div>;
  const at = (k: number) => new Date(Date.parse(day.start) + k * day.step_s * 1000).toISOString();
  const k = Math.min(day.slots - 1, slot);
  const days = index?.all ?? [];
  const i = days.indexOf(date);
  // the newest key moment on the clock, as one line (several can share a slot: the last)
  const caption = (day.highlights ?? []).filter((h) => slot >= h.slot && slot < h.slot + CAPTION_SLOTS).pop();
  const c = caption ? captionText(caption, name) : null;
  return (
    <div className="w-full">
      {c && (
        <div className="mb-2 flex justify-center">
          <div className="flex max-w-full items-center gap-2 rounded-full border border-white/[0.1] bg-[#05070b]/85 px-3.5 py-1.5 text-[12px] backdrop-blur">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: rgbCss(c.color) }} />
            <span className="shrink-0 text-[10px] uppercase tracking-[0.18em]" style={{ color: rgbCss(c.color) }}>
              {c.title}
            </span>
            <span className="truncate font-light text-slate-100">{c.text}</span>
          </div>
        </div>
      )}
      <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-[#0b0f16]/90 px-3 py-2 backdrop-blur">
        <button
          onClick={() => {
            if (!playing && motion.daySlot >= day.slots - 1) actions.seekDay(0);
            actions.togglePlay();
          }}
          className="w-9 shrink-0 rounded-md border border-white/15 py-1 text-[12px] hover:bg-white/10"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <div className="min-w-0 flex-1">
          <div className="relative">
            {(day.highlights ?? []).map((h) => {
              const t = captionText(h, name);
              return (
                <button
                  key={h.kind}
                  title={`${marketTime(at(h.slot))} · ${t.title}`}
                  onClick={() => {
                    useApp.setState({ playing: false });
                    actions.seekDay(h.slot);
                  }}
                  className="absolute -top-2.5 h-2 w-2 -translate-x-1/2 rounded-full"
                  style={{ left: `${(h.slot / (day.slots - 1)) * 100}%`, background: rgbCss(t.color) }}
                />
              );
            })}
            <input
              type="range"
              min={0}
              max={day.slots - 1}
              value={k}
              onChange={(e) => {
                useApp.setState({ playing: false });
                actions.seekDay(Number(e.target.value));
              }}
              className="w-full accent-sky-300"
              aria-label="Time of day"
            />
          </div>
          <div className="flex justify-between text-[10px] text-[#8d94a1]">
            <span>
              <button disabled={i <= 0} onClick={() => actions.setDay(days[i - 1])} className="mr-1 px-1 hover:text-slate-200 disabled:opacity-30" aria-label="Previous day">
                ‹
              </button>
              {dayLabel(date)}
              <button
                disabled={i < 0 || i >= days.length - 1}
                onClick={() => actions.setDay(days[i + 1])}
                className="ml-1 px-1 hover:text-slate-200 disabled:opacity-30"
                aria-label="Next day"
              >
                ›
              </button>
            </span>
            <span className="tabular-nums text-slate-200">{marketTime(at(k))}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function YearsBar() {
  const yearK = useApp((s) => s.yearK);
  const playing = useApp((s) => s.playing);
  const t = useFile<TransitionFile>("transition");
  if (!t) return <div className="text-[12px] text-[#8d94a1]">Loading Ember's yearly data…</div>;
  const last = t.years.length - 1;
  const k = Math.min(last, yearK);
  return (
    <div className="flex w-full items-center gap-3 rounded-xl border border-white/10 bg-[#0b0f16]/90 px-3 py-2 backdrop-blur">
      <button
        onClick={() => {
          if (!playing && motion.yearPos >= last) actions.seekYear(0);
          actions.togglePlay();
        }}
        className="w-9 shrink-0 rounded-md border border-white/15 py-1 text-[12px] hover:bg-white/10"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <input
        type="range"
        min={0}
        max={last}
        value={k}
        onChange={(e) => {
          useApp.setState({ playing: false });
          actions.seekYear(Number(e.target.value));
        }}
        className="min-w-0 flex-1 accent-teal-300"
        aria-label="Year"
      />
      <span className="w-12 text-right text-[20px] font-light tabular-nums text-slate-100">{t.years[k]}</span>
    </div>
  );
}

function LiveChip() {
  const flows = useFile<FlowsFile>("flows");
  if (!flows) return null;
  return (
    <div className="rounded-full border border-white/10 bg-[#0b0f16]/85 px-3 py-1 text-[10.5px] text-[#8d94a1] backdrop-blur">
      <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 align-middle" />
      ENTSO-E data fetched {new Date(flows.fetched).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZoneName: "short" })} · refreshed every 30 min
    </div>
  );
}

export default function TimeBar() {
  const mode = useApp((s) => s.mode);
  if (mode === "day") return <DayBar />;
  if (mode === "years") return <YearsBar />;
  return (
    <div className="flex justify-center">
      <LiveChip />
    </div>
  );
}
