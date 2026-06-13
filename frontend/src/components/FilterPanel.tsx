import type { ReactNode } from "react";

import type { Site } from "../lib/api";
import { mw, num } from "../lib/format";
import type { Filter } from "../lib/query";
import {
  STATE_COLOR,
  STATE_LABEL,
  STATE_ORDER,
  TECH_COLOR,
  TECH_LABEL,
  TECH_ORDER,
  rgbCss,
  type ConstructionState,
  type Technology,
} from "../lib/theme";
import type { ColorMode } from "./MapView";

interface Props {
  all: Site[];
  filter: Filter;
  setFilter: (f: Filter) => void;
  colorMode: ColorMode;
  setColorMode: (m: ColorMode) => void;
}

export default function FilterPanel({ all, filter, setFilter, colorMode, setColorMode }: Props) {
  const techStats = (t: Technology) => {
    const rows = all.filter((s) => s.technology === t);
    return { n: rows.length, mw: rows.reduce((a, s) => a + s.capacity_mw, 0) };
  };
  const stateCount = (st: ConstructionState) => all.filter((s) => s.status === st).length;

  const toggle = <T,>(set: Set<T>, v: T): Set<T> => {
    const next = new Set(set);
    next.has(v) ? next.delete(v) : next.add(v);
    return next;
  };

  return (
    <div className="flex w-60 flex-col gap-5 overflow-y-auto border-r border-white/10 bg-[#0b0f17]/90 p-4 backdrop-blur-xl">
      <div>
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Colour map by
        </div>
        <div className="flex rounded-lg border border-white/10 p-0.5 text-xs">
          {(["state", "technology"] as ColorMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setColorMode(m)}
              className={`flex-1 rounded-md py-1 capitalize transition ${
                colorMode === m ? "bg-white/10 text-slate-100" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {m === "state" ? "Build state" : "Technology"}
            </button>
          ))}
        </div>
      </div>

      <Group title="Technology">
        {TECH_ORDER.map((t) => {
          const { n, mw: cap } = techStats(t);
          const on = filter.technologies.has(t);
          return (
            <Row
              key={t}
              color={rgbCss(TECH_COLOR[t])}
              label={TECH_LABEL[t]}
              count={num(n)}
              sub={mw(cap)}
              active={on}
              dim={filter.technologies.size > 0 && !on}
              onClick={() =>
                setFilter({ ...filter, technologies: toggle(filter.technologies, t) })
              }
            />
          );
        })}
      </Group>

      <Group title="Construction state">
        {STATE_ORDER.map((st) => {
          const on = filter.states.has(st);
          return (
            <Row
              key={st}
              color={rgbCss(STATE_COLOR[st])}
              label={STATE_LABEL[st]}
              count={num(stateCount(st))}
              active={on}
              dim={filter.states.size > 0 && !on}
              onClick={() => setFilter({ ...filter, states: toggle(filter.states, st) })}
            />
          );
        })}
      </Group>
    </div>
  );
}

const Group = ({ title, children }: { title: string; children: ReactNode }) => (
  <div>
    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
      {title}
    </div>
    <div className="space-y-0.5">{children}</div>
  </div>
);

const Row = ({
  color,
  label,
  count,
  sub,
  active,
  dim,
  onClick,
}: {
  color: string;
  label: string;
  count: string;
  sub?: string;
  active: boolean;
  dim: boolean;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    className={`flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs transition hover:bg-white/5 ${
      active ? "bg-white/10" : ""
    } ${dim ? "opacity-40" : ""}`}
  >
    <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} />
    <span className="flex-1 text-slate-200">{label}</span>
    <span className="tabular-nums text-slate-400">{count}</span>
    {sub && <span className="w-14 text-right tabular-nums text-[10px] text-slate-500">{sub}</span>}
  </button>
);
