import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api, type AgentResult, type ChatTurn, type Site } from "../lib/api";

interface Msg {
  role: "user" | "assistant";
  content: string;
  result?: AgentResult;
}

interface Props {
  open: boolean;
  sitesById: Map<string, Site>;
  onResult: (siteIds: string[]) => void;
  onPickSite: (id: string) => void;
  onClose: () => void;
}

const STARTERS = [
  "Which solar sites are behind their EEG deadline?",
  "Solar parks under construction in Bayern",
  "Show a completed solar site with its evidence",
];

export default function AssistantPanel({ open, sitesById, onResult, onPickSite, onClose }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [msgs, loading]);

  const ask = async (q: string) => {
    if (!q.trim() || loading) return;
    setText("");
    setError(null);
    const history: ChatTurn[] = msgs.map((m) => ({ role: m.role, content: m.content }));
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await api.ask(q, history);
      setMsgs((m) => [...m, { role: "assistant", content: res.answer, result: res }]);
      onResult(res.site_ids);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;
  const lastFollowups = [...msgs].reverse().find((m) => m.role === "assistant")?.result?.follow_ups ?? [];

  return (
    <aside className="flex w-[380px] flex-col border-l border-white/10 bg-[#0a0e15]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-emerald-400">✦</span>
          <span className="text-sm font-semibold text-slate-100">AI Analyst</span>
        </div>
        <div className="flex items-center gap-2">
          {msgs.length > 0 && (
            <button onClick={() => setMsgs([])} className="text-[11px] text-slate-500 hover:text-slate-300">
              new chat
            </button>
          )}
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            ✕
          </button>
        </div>
      </div>

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto p-3">
        {msgs.length === 0 && !loading && (
          <div className="mt-2 text-xs text-slate-500">
            <p className="mb-2">
              Ask about the portfolio — every answer cites stored satellite detections and
              deadlines, and highlights the sites on the map and asset table.
            </p>
            <div className="space-y-1.5">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="block w-full rounded-lg border border-white/10 px-2.5 py-1.5 text-left text-slate-300 hover:border-sky-400/40 hover:text-sky-200"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-8 rounded-xl rounded-br-sm bg-sky-500/15 px-3 py-2 text-sm text-slate-100">
              {m.content}
            </div>
          ) : (
            <div key={i} className="rounded-xl rounded-bl-sm border border-white/10 bg-white/[0.03] p-3">
              <div className="agent-prose text-sm leading-relaxed text-slate-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
              {m.result && (
                <>
                  <div className="mt-1.5 text-[10px] text-slate-500">
                    {m.result.provider} · {m.result.sources.length} sources
                  </div>
                  {m.result.site_ids.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.result.site_ids
                        .map((id) => sitesById.get(id))
                        .filter((s): s is Site => !!s)
                        .slice(0, 12)
                        .map((s) => (
                          <button
                            key={s.id}
                            onClick={() => onPickSite(s.id)}
                            className="rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-300 hover:border-sky-400/40 hover:text-sky-200"
                          >
                            {s.name}
                          </button>
                        ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ),
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span className="h-2 w-2 animate-ping rounded-full bg-emerald-400" />
            Retrieving stored detections & deadlines…
          </div>
        )}
        {error && <div className="text-sm text-red-300">{error}</div>}
      </div>

      {lastFollowups.length > 0 && !loading && (
        <div className="flex flex-wrap gap-1.5 border-t border-white/10 px-3 py-2">
          {lastFollowups.map((f) => (
            <button
              key={f}
              onClick={() => ask(f)}
              className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-400 hover:border-emerald-400/40 hover:text-emerald-200"
            >
              {f}
            </button>
          ))}
        </div>
      )}

      <div className="border-t border-white/10 p-2.5">
        <div className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-3 py-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(text)}
            placeholder="Ask a follow-up…"
            disabled={loading}
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none disabled:opacity-60"
          />
          <button
            onClick={() => ask(text)}
            disabled={loading || !text.trim()}
            className="rounded-lg bg-emerald-500/90 px-3 py-1 text-xs font-medium text-white transition hover:bg-emerald-400 disabled:opacity-40"
          >
            Ask
          </button>
        </div>
      </div>
    </aside>
  );
}
