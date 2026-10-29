// Ask: a conversation with the agent (app/agent.ts) in a chat at the side, opened by the top
// bar's Ask button. Each answer streams in with how the agent worked (its plan, every search and
// query, the map design it chose and why), the answer, its maps (each with its key and source,
// shown on the map or side by side in the Maps view), its charts and its sources. The maps on
// screen go back with the next question, so "make it 3D" or "split it into two maps" changes them.

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";

import { ask, clearConversation, removeAgentMap, showAgentMap, useAgent, type ChartMsg, type Msg, type ToolStep } from "../app/agent";
import { useApp } from "../app/store";
import type { Overlay } from "../lib/mapspec";
import { rgbCss } from "../lib/theme";
import { rampCss, useAgentKeys } from "../map/agentLayers";
import { BIVARIATE } from "../map/hexLayers";

const muted = "text-[#8d94a1]";

const EXAMPLES = [
  "Show the 20 largest power plants in Germany as 3D columns, coloured by fuel",
  "Compare coal and nuclear capacity per country in Europe on two maps",
  "Where are wind and solar plants concentrated in Spain? Use hexagons",
  "Map the room to connect new generation in Great Britain",
];

/** The top bar's way to the agent: opens or closes the Ask dock. */
export function AskButton() {
  const open = useAgent((s) => s.open);
  const busy = useAgent((s) => s.busy);
  return (
    <button
      onClick={() => useAgent.setState({ open: !open })}
      className={`shrink-0 rounded-lg border px-2.5 py-1.5 text-[12px] ${open ? "border-sky-400/50 bg-sky-400/15 text-sky-100" : "border-sky-300/30 bg-[#0b0f16]/90 text-sky-200 hover:bg-sky-400/10"}`}
      title="Ask the agent: answers from the atlas's data, with maps"
    >
      ✦ Ask{busy ? " …" : ""}
    </button>
  );
}

/** The input: Enter sends, Shift+Enter a new line. */
function AskInput({ autoFocus = false }: { autoFocus?: boolean }) {
  const busy = useAgent((s) => s.busy);
  const [q, setQ] = useState("");
  const send = (text: string) => {
    if (!text.trim() || busy) return;
    useAgent.setState({ open: true });
    void ask(text);
    setQ("");
  };
  return (
    <div className="flex items-end gap-1.5 rounded-xl border border-sky-300/25 bg-[#0b0f16]/95 px-2.5 py-1.5 shadow-lg shadow-black/40">
      <span className="pb-1 text-[12px] text-sky-300">✦</span>
      <textarea
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => useAgent.setState({ open: true })}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(q);
          }
          if (e.key === "Escape") useAgent.setState({ open: false });
        }}
        rows={1}
        placeholder={busy ? "Answering…" : "Ask the atlas, or ask to change the map"}
        className="min-w-0 flex-1 resize-none bg-transparent py-0.5 text-[12.5px] text-slate-100 placeholder:text-slate-500 focus:outline-none"
      />
      <button
        onClick={() => send(q)}
        disabled={busy || !q.trim()}
        className="shrink-0 rounded-md bg-sky-400/85 px-2.5 py-1 text-[11px] font-medium text-[#06101c] disabled:bg-white/10 disabled:text-slate-500"
      >
        Ask
      </button>
    </div>
  );
}

/** The chat at the side: opened by the top bar's Ask button, over the right side of the map. */
export function AskPanel() {
  const open = useAgent((s) => s.open);
  const messages = useAgent((s) => s.messages);
  const scroller = useRef<HTMLDivElement>(null);
  // follow the answer as it streams: scroll only the conversation, never the page
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, open]);
  if (!open) return null;
  return (
    <aside className="absolute bottom-14 right-3 top-16 z-[24] flex w-[400px] flex-col overflow-hidden rounded-xl border border-sky-300/20 bg-[#080b11]/97 shadow-2xl shadow-black/50 backdrop-blur">
      <div className="flex items-center gap-2 border-b border-white/[0.07] px-3.5 py-2.5">
        <span className="text-[13px] text-sky-200">✦</span>
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-light tracking-wide text-slate-100">Ask the atlas</div>
          <div className={`truncate text-[10px] ${muted}`}>answers from the atlas&apos;s own data, with its steps and maps</div>
        </div>
        {messages.length > 0 && (
          <button onClick={clearConversation} className="rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-white/[0.07]" title="Clears the conversation and the agent's maps">
            New
          </button>
        )}
        <button onClick={() => useAgent.setState({ open: false })} className="rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-white/10" aria-label="Close the chat">
          ✕
        </button>
      </div>
      <div ref={scroller} className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <div className="rounded-xl border border-white/[0.07] bg-[#0b0f16]/90 px-3 py-3">
            <div className="text-[12px] text-slate-200">Ask about the power system: grids, plants, prices, flows, emissions, room to connect.</div>
            <div className={`mt-1 text-[10.5px] leading-snug ${muted}`}>
              Each answer shows how the agent worked (what it searched, the queries it ran, the map design it chose) and every number&apos;s source. It picks the map design for
              the question (flat or 3D, one map or several side by side) and changes a map on request: &ldquo;make it 3D&rdquo;, &ldquo;use hexagons&rdquo;, &ldquo;split into
              two maps&rdquo;.
            </div>
            <div className="mt-2 flex flex-col gap-1">
              {EXAMPLES.map((e) => (
                <button key={e} onClick={() => void ask(e)} className="rounded-md border border-white/10 px-2 py-1 text-left text-[11px] text-slate-300 hover:bg-white/[0.06]">
                  {e}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (m.role === "user" ? <UserMsg key={m.id} m={m} /> : <AgentMsg key={m.id} m={m} />))}
      </div>
      <div className="border-t border-white/[0.07] px-3 py-2.5">
        <AskInput autoFocus />
      </div>
    </aside>
  );
}

function UserMsg({ m }: { m: Msg }) {
  return <div className="ml-6 rounded-xl bg-sky-400/[0.12] px-3 py-2 text-[12px] text-slate-100">{m.text}</div>;
}

const KIND_TEXT: Record<string, string> = {
  answer: "an answer from the data",
  map: "an answer with a map",
  chart: "an answer with a chart",
  explain: "an explanation of the view",
  site: "figures for one site",
  out_of_scope: "outside what the atlas holds",
};

/** One step, in words: what the agent did with the tool and what came back. */
function stepText(t: ToolStep): { what: string; detail?: string } {
  const a = (t.args ?? {}) as Record<string, unknown>;
  switch (t.name) {
    case "search_catalog":
      return { what: `Searched the catalogue for \u201c${String(a.query ?? "")}\u201d` };
    case "describe_table":
      return { what: `Read the columns and units of ${String(a.name ?? "a table")}` };
    case "run_sql":
      return { what: `Queried the data${t.rows != null ? `: ${t.rows.toLocaleString("en-US")} rows` : ""}`, detail: String(a.sql ?? "") };
    case "find_place":
      return { what: `Looked up the place \u201c${String(a.text ?? "")}\u201d` };
    case "site_figures":
      return { what: "Computed the site figures around a point" };
    case "live":
      return { what: `Read live figures (${String(a.source ?? "")})` };
    case "load_skill":
      return { what: `Loaded the rules for ${String(a.name ?? "")}` };
    case "list_skills":
      return { what: "Listed its skills" };
    case "read_skill_file":
      return { what: `Read ${String(a.path ?? "a reference")} of ${String(a.name ?? "a skill")}` };
    default:
      return { what: t.name.replace(/_/g, " ") };
  }
}

/** How the agent worked: its plan, every step with the query, the map design and why. */
function Reasoning({ m }: { m: Msg }) {
  const [open, setOpen] = useState(true);
  const steps = m.tools.length + (m.plan ? 1 : 0) + (m.design ? 1 : 0);
  // open while it works, folded once the answer is there
  useEffect(() => {
    if (m.done) setOpen(false);
  }, [m.done]);
  if (!steps) return null;
  return (
    <div className="mb-2 rounded-lg border border-white/[0.06] bg-white/[0.015]">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-1.5 px-2 py-1 text-left" aria-expanded={open}>
        <span className={`text-[9px] text-slate-500 transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        <span className="flex-1 text-[10.5px] text-slate-300">How the agent worked</span>
        <span className={`text-[9.5px] ${muted}`}>{m.pending ? "working…" : `${steps} steps`}</span>
      </button>
      {open && (
        <ol className="space-y-1 px-2 pb-2 text-[10.5px] leading-snug text-slate-300">
          {m.plan && (
            <li>
              <span className="text-slate-500">1.</span> Understood the question as {KIND_TEXT[m.plan.kind ?? ""] ?? m.plan.kind}
              {m.plan.edit ? ", a change to the map on screen" : ""}
              {m.plan.skills?.length ? `; rules loaded: ${m.plan.skills.join(", ")}` : ""}.
            </li>
          )}
          {m.tools.map((t, i) => {
            const s = stepText(t);
            return (
              <li key={i}>
                <span className="text-slate-500">{i + (m.plan ? 2 : 1)}.</span> {t.status === "running" ? <span className="text-sky-300">…</span> : t.error ? <span className="text-red-300">✕</span> : null} {s.what}
                {t.ms != null ? <span className={muted}> ({Math.round(t.ms)} ms)</span> : null}
                {s.detail && <pre className="mt-0.5 overflow-x-auto whitespace-pre-wrap rounded bg-black/30 px-1.5 py-1 text-[9.5px] text-slate-400">{s.detail}</pre>}
                {t.error && <div className="text-[9.5px] text-red-300">{t.error}</div>}
              </li>
            );
          })}
          {m.design && (
            <li>
              <span className="text-slate-500">{m.tools.length + (m.plan ? 2 : 1)}.</span> {m.design.edit ? "Changed the map: " : "Designed "}
              {m.design.maps > 1 ? `${m.design.maps} maps side by side` : "one map"} as {m.design.styles.map((x) => STYLE_NAME[x] ?? x).join(" + ")}
              {m.design.note ? <span className={muted}>: {m.design.note}</span> : null}
            </li>
          )}
        </ol>
      )}
    </div>
  );
}

function AgentMsg({ m }: { m: Msg }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#0b0f16]/90 px-3 py-2.5">
      <Reasoning m={m} />
      {m.text ? <Markdown text={m.text} /> : m.pending ? <div className={`text-[11px] ${muted}`}>Thinking…</div> : null}
      {m.maps.map((id) => (
        <MapCard key={id} id={id} />
      ))}
      {m.charts.map((c, i) => (
        <ChartCard key={i} c={c} />
      ))}
      {m.sources.length > 0 && (
        <div className={`mt-2 border-t border-white/[0.06] pt-1.5 text-[9.5px] leading-snug ${muted}`}>
          Sources: {m.sources.map((s) => [s.retrieved, s.licence].filter(Boolean).join(", ") || s.dataset).filter((x, i, a) => a.indexOf(x) === i).join("; ")}
        </div>
      )}
      {m.done && (
        <div className={`mt-1 text-[9px] ${muted}`}>
          {m.done.grounding?.numbers ? `${m.done.grounding.grounded} of ${m.done.grounding.numbers} numbers found in the tool results · ` : ""}
          {m.done.latency_ms != null ? `${(m.done.latency_ms / 1000).toFixed(1)} s` : ""}
          {m.done.cost_usd != null ? ` · $${m.done.cost_usd.toFixed(4)}` : ""}
          {m.done.model ? ` · ${m.done.model}` : ""}
          {m.done.grounding?.ungrounded?.length ? <span className="text-amber-300/80"> · not found: {m.done.grounding.ungrounded.join(", ")}</span> : null}
        </div>
      )}
      {m.error && <div className="mt-1 text-[11px] text-red-300">{m.error}</div>}
    </div>
  );
}

/** An agent map: its title, its keys, and where it is shown. */
function MapCard({ id }: { id: string }) {
  const map = useAgent((s) => s.maps[id]);
  const onMap = useAgent((s) => s.onMap === id);
  const inPanels = useApp((s) => s.compare && s.maps.some((p) => p.agent?.mapId === id));
  if (!map) return <div className={`mt-2 text-[10.5px] ${muted}`}>Loading the map…</div>;
  const shown = onMap || inPanels;
  const spec = map.spec;
  return (
    <div className="mt-2 rounded-lg border border-white/[0.08] bg-white/[0.02] px-2.5 py-2">
      <div className="flex items-center gap-2">
        <span className="flex-1 text-[11.5px] font-medium text-slate-100">{spec.title}</span>
        <button
          onClick={() => (shown ? removeAgentMap(id) : showAgentMap(id))}
          className={`rounded-md border px-1.5 py-[1px] text-[10px] ${shown ? "border-sky-300/50 bg-sky-400/15 text-sky-100" : "border-white/10 text-slate-300 hover:bg-white/[0.07]"}`}
        >
          {shown ? "On the map" : "Show"}
        </button>
      </div>
      {spec.panels?.length ? (
        <div className="mt-1 space-y-1.5">
          <div className={`text-[10px] ${muted}`}>{spec.panels.length} maps side by side (Maps view), one camera</div>
          {spec.panels.map((p, i) => (
            <div key={i}>
              <div className="text-[10.5px] text-slate-300">{p.title}</div>
              {(p.overlays ?? []).map((o) => (
                <AgentLegend key={o.id} mapId={id} o={o} />
              ))}
            </div>
          ))}
        </div>
      ) : (
        (spec.overlays ?? []).map((o) => <AgentLegend key={o.id} mapId={id} o={o} />)
      )}
      {spec.notes && <div className={`mt-1 text-[10px] leading-snug ${muted}`}>{spec.notes}</div>}
    </div>
  );
}

const STYLE_NAME: Record<string, string> = {
  dots: "dots",
  points: "dots",
  bubbles: "bubbles",
  choropleth: "choropleth",
  hexbin: "hexagons",
  grid: "grid",
  heatmap: "heatmap",
  contour: "contours",
  lines: "lines",
  flows: "flows",
  labels: "labels",
  bivariate: "bivariate",
  pies: "donuts",
  columns: "3D columns",
  beams: "3D beams",
  spikes: "3D spikes",
  lollipops: "3D lollipops",
  hex_columns: "3D hexagons",
  grid_columns: "3D grid",
  prisms: "3D prisms",
  arcs_3d: "3D arcs",
  arcs: "3D arcs",
  terrain: "3D terrain",
  point_cloud: "3D point cloud",
};

const fmt = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toLocaleString("en-US", { maximumFractionDigits: 2 }));

/** One overlay's key: style, colour scale or categories, what it shows, the source. */
export function AgentLegend({ mapId, o, compact = false }: { mapId: string; o: Overlay; compact?: boolean }) {
  const k = useAgentKeys((s) => s[`${mapId}:${o.id}`]);
  const unit = o.value?.unit ?? o.size?.unit ?? "";
  return (
    <div className="mt-1">
      <div className="flex items-baseline gap-1.5 text-[10.5px] text-slate-200">
        <span>{o.legend.title}</span>
        <span className={`text-[9px] uppercase tracking-wider ${muted}`}>{STYLE_NAME[o.kind] ?? o.kind}</span>
      </div>
      {o.kind === "bivariate" ? (
        <div className="mt-0.5 flex items-center gap-1.5">
          <div className="grid grid-cols-3 gap-[1px]" style={{ transform: "scaleY(-1)" }}>
            {[0, 1, 2].flatMap((y) => [0, 1, 2].map((x) => <span key={`${x}${y}`} className="h-2.5 w-2.5" style={{ background: rgbCss(BIVARIATE[y][x]) }} />))}
          </div>
          <span className={`text-[9.5px] ${muted}`}>
            → {o.value?.column}, ↑ {o.value2?.column}
          </span>
        </div>
      ) : k && k.categories.length > 0 ? (
        <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[9.5px] text-slate-300">
          {k.categories.slice(0, compact ? 5 : 10).map(([c, col]) => (
            <span key={c} className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: rgbCss(col) }} />
              {c}
            </span>
          ))}
        </div>
      ) : (
        <div className="mt-0.5 flex items-center gap-1.5">
          <div className="h-1.5 w-24 rounded-sm" style={{ background: rampCss(o.value?.palette) }} />
          <span className={`text-[9px] ${muted}`}>{k ? `${fmt(k.min)} – ${fmt(k.max)} ${unit}` : "…"}</span>
        </div>
      )}
      {!compact && (
        <div className={`mt-0.5 text-[9.5px] leading-snug ${muted}`}>
          {k?.note ? `${k.note}. ` : ""}
          {o.legend.how}. Source: {o.source}.{k?.missing ? ` ${k.missing} rows without a place are not drawn.` : ""}
        </div>
      )}
    </div>
  );
}

/** The key of one panel of an agent map (the Maps view's small maps). */
export function AgentPanelKey({ mapId, panel, compact }: { mapId: string; panel: number; compact?: boolean }) {
  const p = useAgent((s) => s.maps[mapId]?.spec.panels?.[panel]);
  if (!p) return null;
  return (
    <div>
      {(p.overlays ?? []).map((o) => (
        <AgentLegend key={o.id} mapId={mapId} o={o} compact={compact} />
      ))}
    </div>
  );
}

/** A small chart: bars or lines of one or two series. */
function ChartCard({ c }: { c: ChartMsg }) {
  const s = c.spec;
  const xs = c.rows.map((r) => String(r[s.x.column] ?? ""));
  const series = s.series.map((se, i) => ({ ...se, vals: c.rows.map((r) => Number(r[se.column]) || 0), color: i === 0 ? "rgb(96,170,255)" : "rgb(255,150,92)" }));
  const all = series.flatMap((x) => x.vals);
  const max = Math.max(1e-9, ...all);
  const min = Math.min(0, ...all);
  const W = 320;
  const H = 120;
  const n = Math.max(1, xs.length);
  const y = (v: number) => H - 14 - ((v - min) / (max - min || 1)) * (H - 24);
  return (
    <div className="mt-2 rounded-lg border border-white/[0.08] bg-white/[0.02] px-2.5 py-2">
      <div className="text-[11px] text-slate-100">{s.title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full">
        {s.kind === "line"
          ? series.map((se) => <polyline key={se.column} fill="none" stroke={se.color} strokeWidth={1.6} points={se.vals.map((v, i) => `${(i / Math.max(1, n - 1)) * (W - 8) + 4},${y(v)}`).join(" ")} />)
          : series.map((se, si) =>
              se.vals.map((v, i) => {
                const bw = (W - 8) / n / series.length;
                return <rect key={`${se.column}${i}`} x={4 + i * ((W - 8) / n) + si * bw} y={Math.min(y(v), y(0))} width={Math.max(1, bw - 1)} height={Math.abs(y(v) - y(0))} fill={se.color} />;
              }),
            )}
        <text x={4} y={H - 2} className="fill-slate-500 text-[8px]">
          {xs[0]}
        </text>
        <text x={W - 4} y={H - 2} textAnchor="end" className="fill-slate-500 text-[8px]">
          {xs[xs.length - 1]}
        </text>
      </svg>
      <div className={`text-[9.5px] ${muted}`}>
        {series.map((se) => `${se.label} (${se.unit})`).join(" · ")} · max {fmt(max)}. {s.how ? `${s.how}. ` : ""}Source: {s.source}.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the answer's text

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-slate-50">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k++} className="rounded bg-white/[0.07] px-1 text-[10.5px]">{t.slice(1, -1)}</code>);
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Paragraphs, bullet lists, tables, headings, bold, code: what the answers use. */
function Markdown({ text }: { text: string }) {
  // code blocks and result ids are the agent's plumbing, not part of the answer
  const lines = text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\s*[【[(]?\br_[0-9a-f]{12}\b[】\])]?/g, "")
    .split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^\s*\|/.test(l)) {
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        if (!/^\s*\|\s*:?-+/.test(lines[i])) rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
        i++;
      }
      blocks.push(
        <table key={i} className="my-1.5 w-full border-collapse text-[11px]">
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} className={ri === 0 ? "text-slate-400" : "text-slate-200"}>
                {r.map((c, ci) => (
                  <td key={ci} className={`border-b border-white/[0.06] px-1 py-0.5 ${ci > 0 ? "text-right tabular-nums" : ""}`}>
                    {inline(c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      );
      continue;
    }
    if (/^\s*[-*•]\s+/.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*•]\s+/, ""));
      blocks.push(
        <ul key={i} className="my-1 list-disc space-y-0.5 pl-4 text-[11.5px] text-slate-200">
          {items.map((t, k) => (
            <li key={k}>{inline(t)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^#{1,4}\s/.test(l)) blocks.push(<div key={i} className="mt-1.5 text-[12px] font-semibold text-slate-100">{inline(l.replace(/^#+\s/, ""))}</div>);
    else if (l.trim()) blocks.push(<p key={i} className="my-1 text-[11.5px] leading-relaxed text-slate-200">{inline(l)}</p>);
    i++;
  }
  return <Fragment>{blocks}</Fragment>;
}
