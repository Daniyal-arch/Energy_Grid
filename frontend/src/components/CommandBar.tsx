import { useState } from "react";

const EXAMPLES = [
  "Which solar parks are under construction?",
  "Show a completed solar site with its evidence",
  "Largest sites being built in Bayern",
];

interface Props {
  loading: boolean;
  onAsk: (text: string) => void;
}

export default function CommandBar({ loading, onAsk }: Props) {
  const [text, setText] = useState("");
  const submit = (q: string) => {
    if (!q.trim() || loading) return;
    setText(q);
    onAsk(q);
  };

  return (
    <div className="w-[520px]">
      <div className="flex items-center gap-2 rounded-xl border border-white/15 bg-[#0b0f17]/90 px-3 py-2.5 shadow-lg backdrop-blur-xl">
        <span className={loading ? "animate-pulse text-sky-400" : "text-sky-400"}>✦</span>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit(text)}
          placeholder="Ask the agent about your portfolio…"
          disabled={loading}
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none disabled:opacity-60"
        />
        <button
          onClick={() => submit(text)}
          disabled={loading || !text.trim()}
          className="rounded-lg bg-sky-500/90 px-3 py-1 text-xs font-medium text-white transition hover:bg-sky-400 disabled:opacity-40"
        >
          {loading ? "…" : "Ask"}
        </button>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 px-1">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => submit(ex)}
            className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-400 hover:border-white/25 hover:text-slate-200"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
