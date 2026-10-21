// "What we have for <country>": one compact line per dataset family (coverage.json).

import { useFile } from "../app/data";
import { coverageRows, type CoverageFile } from "../lib/coverage";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

export function CoverageCard({ iso2, name }: { iso2: string; name: string }) {
  const f = useFile<CoverageFile>("coverage");
  const rows = f ? coverageRows(f, iso2) : [];
  if (!rows.length) return null;
  return (
    <Card title={`What we have for ${name}`} note={`coverage registry · ${f!.checked}`} accent={[150, 160, 175]}>
      <div className="space-y-1">
        {rows.map(([fam, g, what]) => (
          <div key={fam} className="grid grid-cols-[1rem_7.5rem_1fr] gap-1 text-[11px] leading-snug">
            <span>{g}</span>
            <span className="text-slate-200">{fam}</span>
            <span className={`truncate ${muted}`} title={what}>
              {what}
            </span>
          </div>
        ))}
      </div>
      <div className={`mt-1.5 text-[9px] ${muted}`}>✅ on the map · ◐ partly · — not published as data · ⛔ waits for a key</div>
    </Card>
  );
}
