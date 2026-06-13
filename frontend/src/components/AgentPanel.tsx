import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AgentResult, Site } from "../lib/api";

interface Props {
  loading: boolean;
  result: AgentResult | null;
  error: string | null;
  sitesById: Map<string, Site>;
  onPick: (id: string) => void;
  onClose: () => void;
}

export default function AgentPanel({ loading, result, error, sitesById, onPick, onClose }: Props) {
  if (!loading && !result && !error) return null;
  const citedSites = (result?.site_ids ?? [])
    .map((id) => sitesById.get(id))
    .filter((s): s is Site => !!s);

  return (
    <div className="mt-2 w-[520px] rounded-xl border border-white/10 bg-[#0b0f17]/95 p-4 shadow-2xl backdrop-blur-xl">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          gridwatch agent
        </span>
        <div className="flex items-center gap-2">
          {result && (
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-200">
              {result.provider} · {result.sources.length} sources
            </span>
          )}
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            ✕
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-3 text-sm text-slate-400">
          <span className="h-2 w-2 animate-ping rounded-full bg-sky-400" />
          Retrieving stored detections and evidence…
        </div>
      )}

      {error && <div className="py-2 text-sm text-red-300">{error}</div>}

      {result && (
        <>
          <div className="agent-prose max-h-[46vh] overflow-y-auto text-sm leading-relaxed text-slate-200">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
          </div>
          {citedSites.length > 0 && (
            <div className="mt-3 border-t border-white/10 pt-2">
              <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
                Sites referenced — click to inspect evidence
              </div>
              <div className="flex flex-wrap gap-1.5">
                {citedSites.slice(0, 30).map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onPick(s.id)}
                    className="rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-slate-300 hover:border-sky-400/40 hover:text-sky-200"
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
