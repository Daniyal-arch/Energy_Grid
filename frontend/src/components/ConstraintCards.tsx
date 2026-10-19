// What stops a build: the protected-areas card in "On the map" (counts and areas as the
// publishers give them, summed per country or state).

import { useFile } from "../app/data";
import type { ProtectedFile } from "../lib/constraints";
import { ISO3 } from "../lib/transition";
import { Card } from "./CountryCards";

const muted = "text-[#8d94a1]";

export function ProtectedCard({ iso3 }: { iso3?: string }) {
  const f = useFile<ProtectedFile>("protected");
  if (!f) return null;
  const n2k = Object.entries(f.natura2000.by_country).filter(([iso2]) => !iso3 || ISO3[iso2] === iso3);
  const showUs = !iso3 || iso3 === "USA";
  const sites = n2k.reduce((a, [, v]) => a + v[0], 0);
  const km2 = n2k.reduce((a, [, v]) => a + v[1], 0);
  const us = Object.values(f.padus.by_state);
  return (
    <Card title="Protected areas" note={f.fetched.slice(0, 10)} accent={[96, 186, 120]}>
      {n2k.length > 0 && (
        <div className="text-[22px] font-light text-slate-50">
          {sites.toLocaleString("en-US")}{" "}
          <span className={`text-[11px] ${muted}`}>
            Natura 2000 sites, {Math.round(km2).toLocaleString("en-US")} km² as published (sums, computed; land and sea, sites may overlap)
          </span>
        </div>
      )}
      {!iso3 && (
        <div className={`pb-1 text-[10px] ${muted}`}>
          {n2k
            .sort((a, b) => b[1][1] - a[1][1])
            .slice(0, 8)
            .map(([c, v]) => `${c} ${Math.round(v[1]).toLocaleString("en-US")} km²`)
            .join(" · ")}
        </div>
      )}
      {showUs && (
        <div className="mt-1 text-[11px] text-slate-300">
          PAD-US Fee: {us.reduce((a, v) => a + v[0], 0).toLocaleString("en-US")} areas, {Math.round(us.reduce((a, v) => a + v[1], 0) / 247.105).toLocaleString("en-US")} km² (acres ÷ 247.105,
          computed)
        </div>
      )}
      <div className={`mt-2 text-[10px] leading-snug ${muted}`}>{f.natura2000.source}; {f.padus.source}. Check a site lists the areas near a place and the share they cover.</div>
    </Card>
  );
}
