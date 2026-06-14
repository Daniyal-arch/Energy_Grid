// Pure chrome: identity + the active use-case switcher. Portfolio numbers and
// data freshness live in the data column (FilterPanel) — the top bar stays quiet.
export default function TopBar() {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-line bg-ink-900 pl-3 pr-4">
      <div className="flex items-center gap-3">
        <div className="grid h-[22px] w-[22px] grid-cols-2 grid-rows-2 gap-[2px] rounded-[3px] border border-accent/40 bg-ink-850 p-[3px]">
          <span className="rounded-[1px] bg-accent" />
          <span className="rounded-[1px] bg-accent/45" />
          <span className="rounded-[1px] bg-accent/45" />
          <span className="rounded-[1px] bg-accent" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight text-slate-100">gridwatch</span>
        <span className="h-4 w-px bg-line-strong" />
        <button className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-dim transition hover:bg-ink-800 hover:text-slate-200">
          Construction monitoring
          <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="m3 4.5 3 3 3-3" />
          </svg>
        </button>
      </div>
    </header>
  );
}
