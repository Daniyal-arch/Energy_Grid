// The coverage registry (data/coverage.yaml → scripts/coverage.py → coverage.json): per country
// and dataset family, what the map holds and from which source, or where the operator was checked.

export interface CoverageCell {
  /** ✅ on the map, ◐ partly, — not published, ⛔ blocked (waits for a key) */
  g: string;
  status: "have" | "built" | "not_published" | "blocked";
  source?: string;
  url?: string;
  dataset?: string;
  checked?: string;
  note?: string;
  /** per market or state: [name, glyph, source] */
  parts?: [string, string, string][];
}
export interface CoverageFile {
  checked: string;
  families: { id: string; name: string; shows: string }[];
  countries: Record<string, Record<string, CoverageCell>>;
}

export const STATUS_TEXT: Record<CoverageCell["status"], string> = {
  have: "on the map",
  built: "on the map",
  not_published: "not published",
  blocked: "waits for a key",
};

/** One line per family: the source, or why there is none. */
export function coverageRows(f: CoverageFile, iso2: string): [string, string, string, string][] {
  const c = f.countries[iso2];
  if (!c) return [];
  return f.families.flatMap((fam) => {
    const cell = c[fam.id];
    if (!cell) return []; // a neighbour holds only the families that cover the neighbours
    const what = cell.status === "have" || cell.status === "built" ? (cell.source ?? "") : `${STATUS_TEXT[cell.status]}${cell.note ? `: ${cell.note}` : ""}`;
    return [[fam.name, cell.g, what, cell.checked ?? ""] as [string, string, string, string]];
  });
}
