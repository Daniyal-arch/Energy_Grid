// ?coverage: the coverage registry as an interactive matrix (brief 30 Track 5.6). One row per
// dataset family, one column per place (EU-27, GB, US); a cell's colour is its status and a
// click shows its evidence: source, dataset, licence, the reason a dark cell is dark, the date
// it was checked. Read from coverage.json (scripts/coverage.py renders it from data/coverage.yaml).

import { useEffect, useMemo, useState } from "react";

type Cell = {
  g?: string;
  status?: string;
  source?: string;
  url?: string;
  note?: string;
  dataset?: string;
  licence?: string;
  checked?: string;
};
type CoverageFile = {
  checked: string;
  families: { id: string; name: string; shows?: string }[];
  countries: Record<string, Record<string, Cell>>;
};

const STATUS: Record<string, { label: string; color: string }> = {
  built: { label: "Built", color: "#2f9e6e" },
  partial: { label: "Partial", color: "#c9a227" },
  not_published: { label: "Not published", color: "#3a4150" },
  blocked: { label: "Blocked", color: "#b5543c" },
  left_out: { label: "Left out (licence)", color: "#6b4f8a" },
  unassessed: { label: "Not assessed (neighbour)", color: "#1a1f29" },
};
// EU-27 first, then GB and the US
const rank = (cc: string): number => (cc === "US" ? 2 : cc === "GB" ? 1 : 0);
// "have" (built in an earlier wave) is built: one status, one colour
const statusOf = (c?: Cell): string => {
  const st = c?.status === "have" ? "built" : c?.status;
  return !c ? "unassessed" : st && STATUS[st] ? st : "not_published";
};

export default function CoverageExplorer() {
  const [file, setFile] = useState<CoverageFile | null>(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [pick, setPick] = useState<{ fam: string; cc: string } | null>(null);
  const [only, setOnly] = useState<string>("");

  useEffect(() => {
    fetch("/data/eu/coverage.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setFile)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const places = useMemo(() => (file ? Object.keys(file.countries).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b)) : []), [file]);
  const fams = useMemo(() => {
    if (!file) return [];
    const t = q.trim().toLowerCase();
    return file.families.filter(
      (f) =>
        (!t || f.name.toLowerCase().includes(t) || f.id.includes(t)) &&
        (!only || places.some((cc) => statusOf(file.countries[cc]?.[f.id]) === only)),
    );
  }, [file, q, only, places]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    if (file) for (const cc of places) for (const f of file.families) c[statusOf(file.countries[cc]?.[f.id])] = (c[statusOf(file.countries[cc]?.[f.id])] ?? 0) + 1;
    return c;
  }, [file, places]);

  if (err) return <div className="p-6 text-sm text-slate-300">The coverage registry did not load ({err}).</div>;
  if (!file) return <div className="p-6 text-sm text-slate-400">Loading the coverage registry…</div>;
  // the evidence panel always shows a cell: the first one until another is clicked
  const shown = pick ?? (fams[0] && places[0] ? { fam: fams[0].id, cc: places[0] } : null);
  const cell = shown ? file.countries[shown.cc]?.[shown.fam] : undefined;
  const famName = shown ? file.families.find((f) => f.id === shown.fam)?.name : "";

  return (
    <div className="min-h-screen bg-[#0b0f16] text-slate-200">
      <header className="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3">
        <a href="/" className="text-[12px] font-semibold tracking-[0.2em] text-slate-100">INFRAATLAS</a>
        <h1 className="text-[14px] text-slate-200">Coverage</h1>
        <span className="text-[11px] text-slate-400">checked {file.checked}</span>
      </header>
      <div className="flex flex-wrap items-center gap-2 px-4 py-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Find among ${file.families.length} families…`}
          aria-label="Find a family"
          className="w-64 max-w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1 text-[12px] outline-none focus:border-sky-400/60 focus-visible:ring-2 focus-visible:ring-sky-400/60"
        />
        {Object.entries(STATUS)
          .filter(([k]) => counts[k])
          .map(([k, v]) => (
            <button
              key={k}
              onClick={() => setOnly(only === k ? "" : k)}
              aria-pressed={only === k}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 ${only === k ? "bg-white/10" : ""}`}
            >
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: v.color }} />
              {v.label} {counts[k].toLocaleString("en-US")}
            </button>
          ))}
      </div>
      <div className="flex flex-col gap-3 px-4 pb-6 lg:flex-row">
        <div className="max-h-[78vh] min-w-0 flex-1 overflow-auto rounded border border-white/10">
          <table className="border-collapse text-[11px]">
            <thead className="sticky top-0 z-10 bg-[#0b0f16]">
              <tr>
                <th className="sticky left-0 z-20 bg-[#0b0f16] px-2 py-1 text-left font-normal text-slate-400">Family</th>
                {places.map((cc) => (
                  <th key={cc} className="px-0.5 py-1 font-normal text-slate-400" scope="col">
                    {cc}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fams.map((f) => (
                <tr key={f.id} className="border-t border-white/[0.04]">
                  <th scope="row" className="sticky left-0 max-w-[220px] truncate bg-[#0b0f16] px-2 py-0.5 text-left font-normal text-slate-300" title={f.shows}>
                    {f.name}
                  </th>
                  {places.map((cc) => {
                    const c = file.countries[cc]?.[f.id];
                    const st = statusOf(c);
                    const on = shown?.fam === f.id && shown?.cc === cc;
                    return (
                      <td key={cc} className="p-[1px]">
                        <button
                          onClick={() => setPick({ fam: f.id, cc })}
                          aria-label={`${f.name}, ${cc}: ${STATUS[st].label}`}
                          className={`block h-4 w-5 rounded-[2px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-300 ${on ? "outline outline-2 outline-white" : ""}`}
                          style={{ background: STATUS[st].color }}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <aside className="w-full shrink-0 rounded border border-white/10 p-3 text-[12px] lg:w-[340px]" aria-live="polite">
          {shown && (
            <div className="space-y-1.5">
              <div className="text-[13px] text-slate-100">
                {famName} · {shown.cc}
              </div>
              <div>
                <span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: STATUS[statusOf(cell)].color }} />
                {STATUS[statusOf(cell)].label}
              </div>
              {cell?.source && <div><span className="text-slate-400">Source: </span>{cell.source}</div>}
              {cell?.dataset && <div><span className="text-slate-400">Dataset: </span>{cell.dataset}</div>}
              {cell?.licence && <div><span className="text-slate-400">Licence: </span>{cell.licence}</div>}
              {cell?.note && <div><span className="text-slate-400">Note: </span>{cell.note}</div>}
              {cell?.url && (
                <a className="block break-all text-sky-300 hover:text-sky-200" href={cell.url} target="_blank" rel="noreferrer">
                  {cell.url}
                </a>
              )}
              <div className="text-slate-500">Checked {cell?.checked || file.checked}</div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
