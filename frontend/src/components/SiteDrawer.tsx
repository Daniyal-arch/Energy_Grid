import { useEffect, useState } from "react";

import { api, type Site, type SiteDetail } from "../lib/api";
import { fmtDate, mw } from "../lib/format";
import { TECH_COLOR, TECH_LABEL, rgbCss } from "../lib/theme";

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink-850 px-2.5 py-2">
      <div className="eyebrow">{label}</div>
      <div className="mt-0.5 break-words text-sm text-slate-200">{value}</div>
    </div>
  );
}

export default function SiteDrawer({ id, site, onClose }: { id: string; site: Site | null; onClose: () => void }) {
  const [detail, setDetail] = useState<SiteDetail | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setDetail(null);
    setLoaded(false);
    api.site(id).then(setDetail).catch(() => {}).finally(() => setLoaded(true));
  }, [id]);

  const s = detail?.site ?? site;
  if (!s || (!loaded && !site)) return null;
  const techColor = s.technology ? TECH_COLOR[s.technology] : ([120, 130, 148] as [number, number, number]);

  return (
    <aside className="absolute right-0 top-0 z-20 flex h-full w-[360px] flex-col gap-4 overflow-y-auto border-l border-line bg-ink-900/95 p-5 backdrop-blur-xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: rgbCss(techColor) }} />
            <span className="eyebrow text-accent-300">Energy infrastructure</span>
          </div>
          <h2 className="mt-1 break-words text-base font-semibold leading-tight text-slate-100">{s.name}</h2>
          <p className="text-xs text-slate-500">
            {s.technology ? TECH_LABEL[s.technology] : "Energy asset"} - {s.district ?? s.state ?? "Germany"}
          </p>
        </div>
        <button onClick={onClose} title="Close" className="text-slate-500 hover:text-slate-200">
          x
        </button>
      </div>

      <div
        className="rounded-md px-3.5 py-3"
        style={{ background: rgbCss(techColor, 0.14), border: `1px solid ${rgbCss(techColor, 0.35)}` }}
      >
        <div className="text-2xl font-semibold tabular-nums text-slate-50">{mw(s.capacity_mw)}</div>
        <div className="eyebrow mt-0.5">Installed capacity</div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <Fact label="Technology" value={s.technology ? TECH_LABEL[s.technology] : "-"} />
        <Fact label="Registry status" value={s.mastr_status ?? "-"} />
        <Fact label="Commissioned" value={fmtDate(s.commissioning_date)} />
        <Fact label="Planned" value={fmtDate(s.planned_commissioning_date)} />
        {s.unit_count > 1 && <Fact label="Units" value={`${s.unit_count}`} />}
        <Fact label="Operator" value={s.owner ?? "-"} />
      </div>

      {detail?.grid_unit && (
        <div className="rounded-md border border-accent/25 bg-accent/10 px-3 py-2.5 text-xs leading-snug text-slate-300">
          <div className="font-medium text-accent-200">Grid-linked generation unit</div>
          <div className="mt-1 text-slate-400">
            {detail.grid_unit.name}
            {detail.grid_unit.capacity_mw ? ` - ${Math.round(detail.grid_unit.capacity_mw)} MW` : ""}
            {detail.grid_unit.psr_type ? ` - ${detail.grid_unit.psr_type.replace(/-/g, " ")}` : ""}
          </div>
        </div>
      )}

      <div className="border-t border-line pt-3 text-[11px] leading-relaxed text-slate-400">
        <div className="mb-1 font-medium text-slate-200">Source context</div>
        <div>
          Energy sites come from the project registry and power-system context. The atlas treats them as infrastructure
          geography, alongside rail, gas, logistics, industry, and transmission layers.
        </div>
      </div>
    </aside>
  );
}
