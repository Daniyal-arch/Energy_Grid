import type { Meta } from "../lib/api";
import { fmtDate } from "../lib/format";

interface Props {
  meta: Meta | null;
}

// Pure chrome: identity + the active use-case + data freshness. Portfolio numbers
// live in the data column (FilterPanel), not here — the top bar stays quiet.
export default function TopBar({ meta }: Props) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-line bg-ink-900 pl-3 pr-4">
      <div className="flex items-center gap-3">
        <div className="h-6 w-6 rounded-md bg-gradient-to-br from-sky-400 to-emerald-400" />
        <span className="text-[15px] font-semibold tracking-tight text-slate-100">gridwatch</span>
        <span className="h-4 w-px bg-line-strong" />
        <button className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-dim transition hover:bg-ink-800 hover:text-slate-200">
          Construction monitoring
          <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="m3 4.5 3 3 3-3" />
          </svg>
        </button>
      </div>

      <div className="flex items-center gap-2">
        <span className="eyebrow">Data as of</span>
        <span className="flex items-center gap-1.5 font-mono text-xs tabular-nums text-slate-200">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
          {meta?.latest_observation ? fmtDate(meta.latest_observation) : "—"}
        </span>
      </div>
    </header>
  );
}
