// ?downloads: the download centre (brief 30 Track 6.7, docs/product/download-centre.md). One row
// per dataset of the Layers panel (app/datasets.ts DATASETS) with its files, licence, attribution
// and "as of" date from data/downloads.json (scripts/build_downloads.py). A file is offered only
// when every part of its licence allows redistribution (ALLOWED below); the others are listed as
// "view only: <licence>" with no link.

import { useEffect, useMemo, useState } from "react";
import { DATASETS, type Dataset } from "../app/datasets";

type FileEntry = {
  path: string;
  url: string | null;
  remote: string | null;
  licence: string | null;
  attribution: string;
  as_of: string | null;
  /** a project rule that keeps the file view only whatever its licence */
  hold: string | null;
};
type Entry = { files: FileEntry[]; lake: string[]; licence?: string | null };
type Index = { built: string; datasets: Record<string, Entry> };

// Licences that allow redistribution (with attribution where they ask for it).
const ALLOWED: RegExp[] = [
  /\bCC[ -]BY\b/i,
  /\bCC0\b/i,
  /\bODbL\b/i,
  /\bOGL\b|Open Government Licen[cs]e/i,
  /Licence Ouverte|Etalab/i,
  /public domain|federal government work/i,
  /dl-de\/(by|zero)/i,
  /\bNLOD\b/i,
  /NESO Open Data Licence/i,
  /\bMIT\b/,
  /2011\/833\/EU/,
];
// Words that withdraw it: non-commercial or no-derivatives terms, or no licence at all.
const DENIED = /non-commercial|\bNC\b|-NC\b|-ND\b|no licence|not stated|not found|^check$/i;
const SHARE_ALIKE = /\bODbL\b|BY-SA/i;

/** Split "A (x; y); B" into ["A (x; y)", "B"]: semicolons inside brackets stay. */
function licenceParts(text: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of text) {
    if (ch === "(") depth++;
    if (ch === ")") depth = Math.max(0, depth - 1);
    if (ch === ";" && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

export function redistributable(licence: string | null | undefined): boolean {
  if (!licence) return false;
  const parts = licenceParts(licence);
  return parts.length > 0 && parts.every((p) => !DENIED.test(p) && ALLOWED.some((r) => r.test(p)));
}

const uniq = <T,>(xs: T[]): T[] => [...new Set(xs)];
const placesOf = (d: Dataset): string => uniq(d.parts.flatMap((p) => p.where)).join(", ");

type Row = { d: Dataset; e: Entry; offered: number; text: string };

export default function Downloads() {
  const [index, setIndex] = useState<Index | null>(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [onlyOpen, setOnlyOpen] = useState(false);

  useEffect(() => {
    fetch("/data/downloads.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setIndex)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const rows: Row[] = useMemo(() => {
    if (!index) return [];
    return DATASETS.map((d) => {
      const e = index.datasets[d.id] ?? { files: [], lake: [] };
      const offered = e.files.filter((f) => (f.url || f.remote) && !f.hold && redistributable(f.licence)).length;
      const text = [d.name, d.category, d.description, placesOf(d), ...d.parts.map((p) => p.source), ...e.files.flatMap((f) => [f.path, f.licence ?? "", f.attribution]), ...e.lake, e.licence ?? ""]
        .join(" ")
        .toLowerCase();
      return { d, e, offered, text };
    });
  }, [index]);

  const shown = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return rows.filter((r) => (!onlyOpen || r.offered > 0) && words.every((w) => r.text.includes(w)));
  }, [rows, q, onlyOpen]);

  if (err) return <div className="p-6 text-sm text-slate-300">The download index did not load ({err}).</div>;
  if (!index) return <div className="p-6 text-sm text-slate-400">Loading the download index…</div>;
  const nOpen = rows.filter((r) => r.offered > 0).length;

  return (
    <div className="min-h-screen bg-[#0b0f16] text-slate-200">
      <header className="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3">
        <a href="/" className="text-[12px] font-semibold tracking-[0.2em] text-slate-100">
          INFRAATLAS
        </a>
        <h1 className="text-[14px] text-slate-200">Downloads: the files behind each layer, with licence and attribution</h1>
        <span className="text-[11px] text-slate-400">index built {index.built.slice(0, 10)}</span>
      </header>
      <div className="flex flex-wrap items-center gap-3 px-4 py-2 text-[12px]">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Filter ${rows.length} datasets by name, source, licence or place…`}
          aria-label="Filter the datasets"
          className="w-80 max-w-full rounded-md border border-white/10 bg-[#0d1119] px-2 py-1 text-[12px] outline-none focus:border-sky-400/60 focus-visible:ring-2 focus-visible:ring-sky-400/60"
        />
        <label className="flex items-center gap-1.5 text-slate-300">
          <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
          Downloadable only ({nOpen})
        </label>
        <span className="text-slate-500">{shown.length} shown</span>
      </div>
      <p className="max-w-[900px] px-4 pb-2 text-[11px] leading-relaxed text-slate-400">
        A file is offered when its licence allows redistribution (CC BY, CC0, ODbL, OGL, Licence Ouverte, dl-de/by, NESO Open Data Licence, MIT, public
        domain). Name the source as given under Attribution. Others are view only on the map. Dates are each file's own; files marked live are refreshed on
        the data branches and newer than the bundled copy. Lake tables hold the full data for the agent; the lake is private.
      </p>
      <div className="mx-4 mb-6 overflow-x-auto rounded border border-white/10">
        <table className="w-full border-collapse text-[11px]">
          <thead className="sticky top-0 z-10 bg-[#0b0f16] text-left text-slate-400">
            <tr>
              <th className="px-2 py-1 font-normal">Dataset</th>
              <th className="px-2 py-1 font-normal">Where</th>
              <th className="px-2 py-1 font-normal">Files</th>
              <th className="px-2 py-1 font-normal">Attribution</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ d, e }) => (
              <tr key={d.id} className="border-t border-white/[0.05] align-top">
                <td className="max-w-[220px] px-2 py-1">
                  <div className="text-slate-100">{d.name}</div>
                  <div className="text-slate-500">{d.category}</div>
                </td>
                <td className="max-w-[140px] px-2 py-1 text-slate-400">{placesOf(d)}</td>
                <td className="px-2 py-1">
                  {e.files.length === 0 && (
                    <div className="text-slate-500">
                      {e.lake.length ? "lake only" : d.id === "night" ? "computed in the app (no data file)" : "no file listed"}
                      {e.licence ? ` · ${redistributable(e.licence) ? "" : "view only: "}${e.licence}` : ""}
                    </div>
                  )}
                  {e.files.map((f) => (
                    <FileLine key={f.path} f={f} />
                  ))}
                  {e.lake.length > 0 && <div className="text-slate-500">lake: {e.lake.join(", ")}</div>}
                </td>
                <td className="max-w-[320px] px-2 py-1 text-slate-400">{uniq(e.files.map((f) => f.attribution)).join(" · ") || d.parts.map((p) => p.source).join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FileLine({ f }: { f: FileEntry }) {
  const open = !f.hold && redistributable(f.licence);
  const href = f.url ?? f.remote;
  const date = f.as_of ? ` · as of ${f.as_of}` : "";
  return (
    <div className="py-[1px]">
      {open && href ? (
        <a href={href} download className="font-mono text-sky-300 hover:underline">
          {f.path}
        </a>
      ) : (
        <span className="font-mono text-slate-300">{f.path}</span>
      )}
      {open && f.url && f.remote && (
        <>
          {" "}
          <a href={f.remote} className="text-sky-300/80 hover:underline">
            (live)
          </a>
        </>
      )}
      <span className="text-slate-500">{date}</span>
      <span className={open ? "text-emerald-300/80" : "text-amber-300/80"}>
        {" · "}
        {open ? f.licence : f.hold ? `view only: ${f.licence} (${f.hold})` : `view only: ${f.licence ?? "licence not recorded"}`}
      </span>
      {open && SHARE_ALIKE.test(f.licence ?? "") && <span className="text-slate-500"> · share-alike: what you build from it stays under the same licence</span>}
      {open && !href && <span className="text-slate-500"> · one file per day, see the day archive</span>}
    </div>
  );
}
