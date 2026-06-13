import { useState } from "react";

const EXAMPLES = [
  "solar parks over 20 MW in Bayern",
  "wind farms in planning",
  "sites under construction",
];

interface Props {
  understood: string[];
  resultCount: number | null;
  onSubmit: (text: string) => void;
  onClear: () => void;
}

export default function CommandBar({ understood, resultCount, onSubmit, onClear }: Props) {
  const [text, setText] = useState("");

  const submit = (q: string) => {
    setText(q);
    onSubmit(q);
  };

  return (
    <div className="w-[520px]">
      <div className="flex items-center gap-2 rounded-xl border border-white/15 bg-[#0b0f17]/90 px-3 py-2 shadow-lg backdrop-blur-xl">
        <span className="text-sky-400">⌕</span>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit(text)}
          placeholder="Ask anything about your portfolio…"
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none"
        />
        {understood.length > 0 && (
          <button onClick={() => { setText(""); onClear(); }} className="text-xs text-slate-500 hover:text-slate-200">
            clear
          </button>
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 px-1">
        {understood.length > 0 ? (
          <>
            <span className="text-[11px] text-slate-500">
              {resultCount != null ? `${resultCount} sites ·` : ""} understood:
            </span>
            {understood.map((u) => (
              <span
                key={u}
                className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2 py-0.5 text-[11px] text-sky-200"
              >
                {u}
              </span>
            ))}
          </>
        ) : (
          EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => submit(ex)}
              className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-400 hover:border-white/25 hover:text-slate-200"
            >
              {ex}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
