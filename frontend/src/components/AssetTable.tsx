import { useMemo, useState } from "react";

import type { Site } from "../lib/api";
import { fmtDate, mw } from "../lib/format";
import {
  STATE_COLOR,
  STATE_LABEL,
  TECH_COLOR,
  TECH_LABEL,
  rgbCss,
  type ConstructionState,
  type Technology,
} from "../lib/theme";

type SortKey = "name" | "capacity_mw" | "status" | "state" | "deadline";

interface Props {
  sites: Site[];
  deadlines: Record<string, string>;
  highlight: Set<string> | null;
  onSelect: (id: string) => void;
}

const TODAY = new Date().toISOString().slice(0, 10);

export default function AssetTable({ sites, deadlines, highlight, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [tech, setTech] = useState<string>("");
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [sort, setSort] = useState<SortKey>("capacity_mw");
  const [dir, setDir] = useState<1 | -1>(-1);

  const isOverdue = (s: Site) =>
    deadlines[s.id] && deadlines[s.id] < TODAY && s.status !== "complete" && s.status !== "unknown";

  const rows = useMemo(() => {
    let r = sites;
    if (highlight) r = r.filter((s) => highlight.has(s.id));
    if (q) {
      const t = q.toLowerCase();
      r = r.filter(
        (s) =>
          s.name.toLowerCase().includes(t) ||
          s.state.toLowerCase().includes(t) ||
          (s.district ?? "").toLowerCase().includes(t),
      );
    }
    if (tech) r = r.filter((s) => s.technology === tech);
    if (onlyOverdue) r = r.filter(isOverdue);
    const val = (s: Site) =>
      sort === "deadline" ? (deadlines[s.id] ?? "9999") : (s[sort as keyof Site] as string | number);
    return [...r].sort((a, b) => (val(a) > val(b) ? dir : val(a) < val(b) ? -dir : 0));
  }, [sites, highlight, q, tech, onlyOverdue, sort, dir, deadlines]);

  const setSortKey = (k: SortKey) => {
    if (k === sort) setDir((d) => (d === 1 ? -1 : 1));
    else {
      setSort(k);
      setDir(k === "name" || k === "state" ? 1 : -1);
    }
  };

  const exportCsv = () => {
    const head = ["name", "technology", "capacity_mw", "build_status", "registry_status", "region", "commissioned", "legal_deadline"];
    const lines = rows.map((s) =>
      [s.name, s.technology, s.capacity_mw, s.status, s.mastr_status, s.state, s.commissioning_date ?? "", deadlines[s.id] ?? ""]
        .map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`)
        .join(","),
    );
    const blob = new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "gridwatch-assets.csv";
    a.click();
  };

  const Th = ({ k, label, right }: { k: SortKey; label: string; right?: boolean }) => (
    <th
      onClick={() => setSortKey(k)}
      className={`cursor-pointer select-none px-3 py-2 font-medium text-slate-400 hover:text-slate-200 ${
        right ? "text-right" : "text-left"
      }`}
    >
      {label}
      {sort === k && <span className="ml-1 text-sky-400">{dir === 1 ? "▲" : "▼"}</span>}
    </th>
  );

  return (
    <div className="flex h-full flex-col bg-ink-950">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, district, region…"
          className="w-64 rounded-lg border border-line bg-ink-850 px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-sky-400/40"
        />
        <select
          value={tech}
          onChange={(e) => setTech(e.target.value)}
          className="rounded-lg border border-line bg-ink-900 px-2 py-1.5 text-sm text-slate-300"
        >
          <option value="">All technologies</option>
          {Object.entries(TECH_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-slate-400">
          <input type="checkbox" checked={onlyOverdue} onChange={(e) => setOnlyOverdue(e.target.checked)} />
          Behind deadline only
        </label>
        {highlight && (
          <span className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2 py-0.5 text-[11px] text-sky-200">
            agent result · {rows.length}
          </span>
        )}
        <div className="flex-1" />
        <span className="text-xs text-slate-500">{rows.length.toLocaleString()} sites</span>
        <button
          onClick={exportCsv}
          className="rounded-lg border border-line px-2.5 py-1.5 text-xs text-slate-300 hover:border-line-strong hover:text-slate-100"
        >
          Export CSV
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-ink-900 text-xs">
            <tr className="border-b border-line">
              <Th k="name" label="Site" />
              <th className="px-3 py-2 text-left font-medium text-slate-400">Tech</th>
              <Th k="capacity_mw" label="Capacity" right />
              <Th k="status" label="Build state" />
              <th className="px-3 py-2 text-left font-medium text-slate-400">Registry</th>
              <Th k="state" label="Region" />
              <Th k="deadline" label="Legal deadline" right />
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 600).map((s) => {
              const overdue = isOverdue(s);
              return (
                <tr
                  key={s.id}
                  onClick={() => onSelect(s.id)}
                  className="cursor-pointer border-b border-line hover:bg-ink-850"
                >
                  <td className="max-w-[220px] truncate px-3 py-1.5 text-slate-200">{s.name}</td>
                  <td className="px-3 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-slate-300">
                      <span
                        className="h-2 w-2 rounded-sm"
                        style={{ background: s.technology ? rgbCss(TECH_COLOR[s.technology as Technology]) : "#555" }}
                      />
                      {s.technology ? TECH_LABEL[s.technology as Technology] : "—"}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{mw(s.capacity_mw)}</td>
                  <td className="px-3 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-slate-300">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: rgbCss(STATE_COLOR[s.status as ConstructionState]) }}
                      />
                      {STATE_LABEL[s.status as ConstructionState]}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-slate-400">{s.mastr_status ?? "—"}</td>
                  <td className="px-3 py-1.5 text-slate-400">{s.state}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">
                    {deadlines[s.id] ? (
                      <span className={overdue ? "text-red-300" : "text-slate-300"}>
                        {fmtDate(deadlines[s.id])}
                        {overdue && " ⚠"}
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length > 600 && (
          <div className="px-4 py-2 text-center text-xs text-slate-500">
            Showing first 600 of {rows.length.toLocaleString()} — refine filters or export CSV for all.
          </div>
        )}
      </div>
    </div>
  );
}
