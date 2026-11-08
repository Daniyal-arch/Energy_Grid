// ?compare=France;Germany;Spain (brief 30 Track 6.3, docs/product/compare.md): two to six places
// side by side, one table per measure with the places as columns. The figures are the answer
// service's instant answer `compare` (GET /api/quick/compare) as returned: nothing is computed
// here. Without the service the page says so and shows no figures.

import { useEffect, useMemo, useState } from "react";

import { API_BASE } from "../app/agent";
import { CREDITS } from "./sources";

type Area = { area_id: string; name: string; level: string; iso3: string[] | null };
type Table = { area: string; title: string; columns: string[]; rows: (string | number | null)[][]; method: string; as_of: string; sql: string };
type Source = { dataset?: string; table?: string; licence?: string; retrieved?: string };
type Answer = { template: string; area: Area[]; tables: Table[]; sources: Source[]; text: string };
type State = { kind: "loading" } | { kind: "ok"; data: Answer } | { kind: "error"; text: string } | { kind: "absent" };

const muted = "text-[#8d94a1]";

/** The places in the address: ?compare=a;b;c (";" or "," between names). */
function placesOf(search: string): string[] {
  const raw = new URLSearchParams(search).get("compare") ?? "";
  return raw
    .split(/[;,]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 6);
}

const hrefOf = (places: string[]) => `?compare=${places.map(encodeURIComponent).join(";")}`;

const fmt = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "–" : typeof v === "number" ? v.toLocaleString("en-GB") : String(v));

/** The tables of one measure pivoted: rows by the first column (fuel, voltage), a column group per place. */
function pivot(title: string, tables: Table[], places: string[]) {
  const byPlace = new Map(tables.map((t) => [t.area, t]));
  const first = tables[0];
  const keyed = first.columns.length > 1;
  const valueCols = keyed ? first.columns.slice(1) : first.columns;
  const keys: string[] = [];
  for (const t of tables) for (const r of t.rows) {
    const k = keyed ? fmt(r[0]) : "";
    if (!keys.includes(k)) keys.push(k);
  }
  const cell = (place: string, key: string, ci: number): string => {
    const t = byPlace.get(place);
    if (!t) return "not in this measure";
    const r = t.rows.find((x) => (keyed ? fmt(x[0]) : "") === key);
    if (!r) return "–";
    return fmt(keyed ? r[ci + 1] : r[ci]);
  };
  const methods = [...new Set(tables.map((t) => t.method))];
  const asOf = [...new Set(tables.flatMap((t) => (t.as_of ? t.as_of.split(", ") : [])))].sort();
  return { title, keyed, keyName: keyed ? first.columns[0] : "", valueCols, keys, cell, methods, asOf, places, sqls: tables.map((t) => [t.area, t.sql] as const) };
}

function MeasureTable({ p }: { p: ReturnType<typeof pivot> }) {
  const multi = p.valueCols.length > 1;
  return (
    <section className="rounded-xl border border-white/10 bg-[#0b0f16]/92 p-3">
      <h2 className="text-[13px] font-medium text-slate-100">{p.title}</h2>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-collapse text-[11.5px] tabular-nums">
          <thead>
            <tr className={`text-left ${muted}`}>
              {p.keyed && <th rowSpan={multi ? 2 : 1} className="border-b border-white/10 py-1 pr-3 font-normal">{p.keyName}</th>}
              {p.places.map((pl) => (
                <th key={pl} colSpan={p.valueCols.length} className="border-b border-white/10 px-2 py-1 text-right font-medium text-slate-200">
                  {pl}
                  {!multi && <span className={`ml-1 font-normal ${muted}`}>{p.valueCols[0]}</span>}
                </th>
              ))}
            </tr>
            {multi && (
              <tr className={`text-right ${muted}`}>
                {p.places.flatMap((pl) =>
                  p.valueCols.map((c) => (
                    <th key={`${pl}-${c}`} className="border-b border-white/10 px-2 py-0.5 font-normal">
                      {c}
                    </th>
                  )),
                )}
              </tr>
            )}
          </thead>
          <tbody>
            {p.keys.map((k) => (
              <tr key={k} className="border-b border-white/[0.05] text-slate-200">
                {p.keyed && <td className="py-1 pr-3 text-slate-300">{k || "–"}</td>}
                {p.places.flatMap((pl) =>
                  p.valueCols.map((_, ci) => {
                    const v = p.cell(pl, k, ci);
                    return (
                      <td key={`${pl}-${ci}`} className={`px-2 py-1 text-right ${v === "not in this measure" ? `text-[10px] ${muted}` : ""}`}>
                        {v}
                      </td>
                    );
                  }),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={`mt-2 text-[10.5px] leading-snug ${muted}`}>
        Method: {p.methods.join("; ")} · as of {p.asOf.length ? p.asOf.join(", ") : "n/a"}
      </div>
      <details className={`mt-1 text-[10px] ${muted}`}>
        <summary className="cursor-pointer select-none">SQL</summary>
        {p.sqls.map(([a, sql]) => (
          <div key={a} className="mt-1">
            <span className="text-slate-400">{a}:</span> <code className="break-all font-mono text-slate-400">{sql || "–"}</code>
          </div>
        ))}
      </details>
    </section>
  );
}

export default function ComparePage() {
  const [places, setPlaces] = useState(() => placesOf(window.location.search));
  const [draft, setDraft] = useState(places.join("; "));
  const [state, setState] = useState<State>({ kind: "loading" });
  useEffect(() => {
    const on = () => {
      const p = placesOf(window.location.search);
      setPlaces(p);
      setDraft(p.join("; "));
    };
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  useEffect(() => {
    document.title = places.length ? `${places.join(" vs ")} · InfraAtlas` : "Compare · InfraAtlas";
    if (places.length < 2) {
      setState({ kind: "error", text: "Name two to six places, separated by “;”." });
      return;
    }
    let live = true;
    setState({ kind: "loading" });
    fetch(`${API_BASE}/api/quick/compare?area=${encodeURIComponent(places.join(";"))}`)
      .then(async (r) => {
        const json = (r.headers.get("content-type") ?? "").includes("application/json");
        // a static host answers /api/... with its page or a plain 404: no answer service here
        if (!json) return { kind: "absent" } as State;
        const body = (await r.json()) as Answer & { detail?: unknown };
        if (!r.ok) return { kind: "error", text: typeof body.detail === "string" ? body.detail : `the answer service answered ${r.status}` } as State;
        return { kind: "ok", data: body } as State;
      })
      .catch(() => ({ kind: "absent" }) as State)
      .then((s) => live && setState(s));
    return () => {
      live = false;
    };
  }, [places]);

  const submit = () => {
    const p = draft
      .split(/[;,]/)
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 6);
    window.history.pushState(null, "", hrefOf(p));
    setPlaces(p);
  };

  const data = state.kind === "ok" ? state.data : null;
  const names = data ? data.area.map((a) => a.name) : places;
  const measures = useMemo(() => {
    if (!data) return [];
    const titles = [...new Set(data.tables.map((t) => t.title))];
    return titles.map((title) => pivot(title, data.tables.filter((t) => t.title === title), names));
  }, [data, names]);
  const iso3 = data ? [...new Set(data.area.flatMap((a) => a.iso3 ?? []))] : [];

  return (
    <div className="h-full w-full overflow-y-auto bg-[#05070b] text-slate-200">
      <div className="mx-auto max-w-5xl px-4 py-5">
        <header className="flex flex-wrap items-baseline gap-3">
          <a href="./" className="text-[14px] font-semibold tracking-[0.18em] text-slate-100">
            INFRAATLAS
          </a>
          <span className={`text-[11px] uppercase tracking-[0.2em] ${muted}`}>Compare</span>
          <span className="flex-1" />
          {iso3.length > 0 && (
            <a href={`./?compare=1&area=${iso3.join(",")}`} className="rounded-lg border border-white/10 bg-[#0b0f16]/90 px-2.5 py-1 text-[12px] text-slate-200 hover:bg-white/[0.08]" title="The places on several maps, one theme each">
              Open in the Maps view
            </a>
          )}
        </header>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="France; Germany; Spain"
            aria-label="Places to compare, separated by ;"
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#0b0f16] px-3 py-1.5 text-[12.5px] text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
          />
          <button type="submit" className="rounded-lg border border-sky-400/50 bg-sky-400/15 px-3 py-1.5 text-[12px] text-sky-100 hover:bg-sky-400/25">
            Compare
          </button>
        </form>
        <div className={`mt-1 text-[10.5px] ${muted}`}>Two to six places (countries, groups, regions, cities, zones), separated by “;”. The address is the link to share.</div>

        <main className="mt-4 space-y-3">
          {state.kind === "loading" && <div className={`text-[12px] ${muted}`}>Asking the answer service…</div>}
          {state.kind === "absent" && (
            <div className="rounded-xl border border-white/10 bg-[#0b0f16]/92 p-3 text-[12.5px] text-slate-300">
              The answer service is not set up on this site yet, so there are no figures to compare here. The map itself works:{" "}
              <a href="./" className="text-sky-300 hover:underline">
                open InfraAtlas
              </a>
              .
            </div>
          )}
          {state.kind === "error" && <div className="rounded-xl border border-amber-300/20 bg-amber-300/[0.06] p-3 text-[12.5px] text-amber-100/90">{state.text}</div>}
          {data && (
            <>
              <div className={`text-[11px] ${muted}`}>
                {data.area.map((a) => `${a.name} (${a.level})`).join(" · ")} · the same queries for every place; a whole country or group by its country codes, a smaller area by its outline
              </div>
              {measures.map((p) => (
                <MeasureTable key={p.title} p={p} />
              ))}
              <div className={`text-[10.5px] leading-snug ${muted}`}>
                Sources: {data.sources.map((s) => [s.dataset ?? s.table, [s.licence, s.retrieved].filter(Boolean).join(", ")].filter(Boolean).join(" (") + (s.licence || s.retrieved ? ")" : "")).join(" · ") || "n/a"}
              </div>
            </>
          )}
        </main>
        <footer className="mt-6 text-[8.5px] leading-tight text-slate-500">{CREDITS}</footer>
      </div>
    </div>
  );
}
