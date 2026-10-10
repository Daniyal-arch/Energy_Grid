// The app: one map, a top bar (stories, search, time), Layers on the left, the context panel
// on the right, the clock below. Phones get the same pieces as bottom sheets.

import { useEffect, useState } from "react";

import MapCanvas from "../map/MapCanvas";
import { LIVE_KEYS, ensure, useDataStore } from "../app/data";
import { MOBILE_QUERY } from "../app/geo";
import { STORIES, actions, readUrl, useApp, writeUrl } from "../app/store";
import LayersPanel from "./LayersPanel";
import MapLegend from "./MapLegend";
import MapOptions from "./MapOptions";
import Panel from "./Panel";
import Search from "./Search";
import TimeBar, { TimeControl } from "./TimeBar";
import { CREDITS } from "./sources";

readUrl();

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia(MOBILE_QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

function Stories({ onDone }: { onDone?: () => void }) {
  const story = useApp((s) => s.story);
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1">
      {STORIES.map((st) => (
        <button
          key={st.id}
          onClick={() => {
            actions.applyStory(st.id);
            onDone?.();
          }}
          className={`block w-full rounded-lg px-3 py-2 text-left hover:bg-white/[0.07] ${story === st.id ? "bg-white/[0.1]" : ""}`}
        >
          <div className="text-[12.5px] text-slate-100">{st.label}</div>
          <div className="text-[10.5px] text-[#8d94a1]">{st.blurb}</div>
        </button>
      ))}
      <button
        onClick={() => {
          navigator.clipboard?.writeText(window.location.href).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          });
        }}
        className="mt-1 w-full rounded-lg border border-white/10 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.07]"
      >
        {copied ? "Link copied" : "Copy a link to this view"}
      </button>
    </div>
  );
}

function StoriesMenu() {
  const [open, setOpen] = useState(false);
  const story = useApp((s) => s.story);
  const label = STORIES.find((s) => s.id === story)?.label ?? "Stories";
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#0b0f16]/90 px-3 py-1.5 text-[12px] text-slate-200 backdrop-blur hover:bg-white/[0.08]"
        aria-expanded={open}
      >
        {label} <span className="text-[9px] text-slate-400">▼</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-xl border border-white/10 bg-[#0b0f16]/95 p-1.5 shadow-2xl backdrop-blur">
            <Stories onDone={() => setOpen(false)} />
          </div>
        </>
      )}
    </div>
  );
}

const Brand = () => (
  <div className="flex items-baseline gap-2">
    <span className="text-[14px] font-semibold tracking-[0.18em] text-slate-100">INFRAATLAS</span>
  </div>
);

function Desktop() {
  const layersOpen = useApp((s) => s.layersPanel);
  const setLayersOpen = (v: boolean) => useApp.setState({ layersPanel: v });
  return (
    <>
      <header className="absolute inset-x-3 top-3 z-30 flex items-center gap-3">
        <Brand />
        <StoriesMenu />
        <div className="mx-auto w-full max-w-md">
          <Search />
        </div>
        <TimeControl />
      </header>
      <aside className={`absolute left-3 top-16 z-20 flex w-[268px] flex-col ${layersOpen ? "bottom-14" : "pointer-events-none [&>button]:pointer-events-auto"}`}>
        <button
          onClick={() => setLayersOpen(!layersOpen)}
          className="flex items-center justify-between rounded-t-xl border border-b-0 border-white/10 bg-[#0b0f16]/92 px-3 py-2 text-[11px] uppercase tracking-[0.2em] text-slate-300 backdrop-blur"
          style={{ borderRadius: layersOpen ? undefined : 12, borderBottomWidth: layersOpen ? 0 : 1 }}
        >
          Layers <span className="text-[9px]">{layersOpen ? "▲" : "▼"}</span>
        </button>
        {layersOpen ? (
          <div className="min-h-0 flex-1 overflow-y-auto rounded-b-xl border border-t-0 border-white/10 bg-[#0b0f16]/92 backdrop-blur">
            <LayersPanel />
          </div>
        ) : (
          // panel closed: the key to what is on the map, where the map has least to show
          <MapLegend />
        )}
      </aside>
      <aside className="absolute bottom-14 right-3 top-16 z-20 flex w-[372px] flex-col overflow-hidden rounded-xl border border-white/10 bg-[#080b11]/92 backdrop-blur">
        <Panel />
      </aside>
      <div className="absolute bottom-3 left-[290px] right-[396px] z-20">
        <TimeBar />
      </div>
      <MapOptions />
      <div className="pointer-events-none absolute bottom-1 left-3 z-10 max-w-[260px] text-[8.5px] leading-tight text-slate-500">{CREDITS}</div>
    </>
  );
}

function Phone() {
  const sheet = useApp((s) => s.sheet);
  const set = (v: typeof sheet) => useApp.setState({ sheet: sheet === v ? "none" : v });
  return (
    <>
      <header className="absolute inset-x-2 top-2 z-30 flex items-center gap-2">
        <button onClick={() => set("search")} className="rounded-lg border border-white/10 bg-[#0b0f16]/90 px-2.5 py-1.5 text-[12px] text-slate-200" aria-label="Search">
          ⌕
        </button>
        <div className="flex-1" />
        <TimeControl small />
      </header>
      {sheet === "search" && (
        <div className="absolute inset-x-2 top-12 z-40">
          <Search autoFocus onDone={() => useApp.setState({ sheet: "none" })} />
          <div className="mt-2 rounded-xl border border-white/10 bg-[#0b0f16]/95 p-1.5">
            <div className="px-2 pb-1 text-[9px] uppercase tracking-[0.2em] text-[#8d94a1]">Stories</div>
            <Stories onDone={() => useApp.setState({ sheet: "none" })} />
          </div>
        </div>
      )}
      <MapOptions />
      <div className="absolute inset-x-2 bottom-14 z-20">
        <TimeBar />
      </div>
      {(sheet === "layers" || sheet === "panel") && (
        <div className="absolute inset-x-0 bottom-12 z-30 flex max-h-[68vh] flex-col overflow-hidden rounded-t-2xl border-t border-white/10 bg-[#080b11]/97 backdrop-blur">
          <div className="mx-auto mt-1.5 h-1 w-10 shrink-0 rounded-full bg-white/20" />
          <div className="min-h-0 flex-1 overflow-y-auto">{sheet === "layers" ? <LayersPanel /> : <Panel />}</div>
        </div>
      )}
      <nav className="absolute inset-x-0 bottom-0 z-40 flex h-12 border-t border-white/10 bg-[#080b11]/95 backdrop-blur">
        {(
          [
            ["layers", "Layers"],
            ["panel", "Figures"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => set(id)} className={`flex-1 text-[12.5px] ${sheet === id ? "text-sky-300" : "text-slate-300"}`}>
            {label}
          </button>
        ))}
      </nav>
    </>
  );
}

export default function App() {
  const narrow = useNarrow();
  // live files again every 10 minutes (the workflow refreshes them every 30)
  useEffect(() => {
    const t = setInterval(() => {
      const have = useDataStore.getState().files;
      for (const k of LIVE_KEYS) if (have[k]) ensure(k, true);
    }, 10 * 60 * 1000);
    return () => clearInterval(t);
  }, []);
  // the address bar follows the view; the title names the selection
  useEffect(
    () =>
      useApp.subscribe((s, prev) => {
        if (s.story !== prev.story || s.mode !== prev.mode || s.colour !== prev.colour || s.layers !== prev.layers || s.selection !== prev.selection || s.tab !== prev.tab || s.day !== prev.day || s.plantStatus !== prev.plantStatus || s.plantStyle !== prev.plantStyle || s.layersPanel !== prev.layersPanel)
          writeUrl();
      }),
    [],
  );
  return (
    <div className="relative h-full w-full overflow-hidden bg-[#05070b]">
      <MapCanvas />
      {narrow ? <Phone /> : <Desktop />}
    </div>
  );
}
