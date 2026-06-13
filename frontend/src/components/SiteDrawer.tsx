import { type ReactNode, useEffect, useState } from "react";

import { api, type Deadline, type Detection, type Series, type SiteDetail } from "../lib/api";
import { fmtDate, mw } from "../lib/format";
import { STATE_COLOR, STATE_LABEL, TECH_LABEL, rgbCss } from "../lib/theme";
import MetricChart from "./MetricChart";

const confColor = { high: "#34d399", medium: "#f4b740", low: "#94a3b8" } as const;

function Schedule({ deadlines, status }: { deadlines: Deadline[]; status: string }) {
  const legal = deadlines.find((d) => d.type === "legal_completion");
  const planned = deadlines.find((d) => d.type === "planned_commissioning");
  if (!legal && !planned) return null;
  const today = new Date().toISOString().slice(0, 10);
  const overdue = legal && legal.deadline_date < today && status !== "complete";
  return (
    <div className="space-y-2">
      {legal && (
        <div
          className={`rounded-lg border px-3 py-2 ${
            overdue ? "border-red-500/40 bg-red-500/10" : "border-white/10 bg-white/[0.03]"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300">EEG legal completion</span>
            <span className={`text-sm font-medium ${overdue ? "text-red-300" : "text-slate-100"}`}>
              {fmtDate(legal.deadline_date)}
              {overdue && " · overdue"}
            </span>
          </div>
          <div className="mt-0.5 text-[10px] leading-snug text-slate-500">{legal.source}</div>
        </div>
      )}
      {planned && (
        <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
          <span className="text-xs text-slate-300">Planned commissioning</span>
          <span className="text-sm text-slate-100">{fmtDate(planned.deadline_date)}</span>
        </div>
      )}
    </div>
  );
}

function Timeline({ detections }: { detections: Detection[] }) {
  if (!detections.length)
    return (
      <p className="text-xs text-slate-500">
        Not yet analysed — no satellite history processed for this site.
      </p>
    );
  return (
    <div className="space-y-2.5">
      {detections.map((d) => (
        <div key={d.id} className="flex gap-3">
          <div className="mt-1 flex flex-col items-center">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: rgbCss(STATE_COLOR[d.to_state]) }}
            />
            <span className="mt-0.5 w-px flex-1 bg-white/10" />
          </div>
          <div className="pb-1">
            <div className="text-sm text-slate-100">{STATE_LABEL[d.to_state]}</div>
            <div className="text-[11px] text-slate-400">
              {fmtDate(d.detected_at)} ·{" "}
              <span style={{ color: confColor[d.confidence] }}>{d.confidence} confidence</span>
              {d.evidence.length > 0 && ` · ${d.evidence.length} scenes cited`}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function SiteDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [detail, setDetail] = useState<SiteDetail | null>(null);
  const [series, setSeries] = useState<Series | null>(null);

  useEffect(() => {
    setDetail(null);
    setSeries(null);
    api.site(id).then(setDetail);
    api.timeseries(id).then(setSeries);
  }, [id]);

  if (!detail) return null;
  const s = detail.site;
  const hasSeries = series && (series.ndvi.length || series.vh_db.length);
  const chipBefore = (s.chip_before_url as string | null) ?? null;
  const chipAfter = (s.chip_after_url as string | null) ?? null;
  const chipBeforeDate = (s.chip_before_date as string | null) ?? "";
  const chipAfterDate = (s.chip_after_date as string | null) ?? "";

  return (
    <aside className="absolute right-0 top-0 z-20 flex h-full w-[380px] flex-col gap-4 overflow-y-auto border-l border-white/10 bg-[#0b0f17]/95 p-5 backdrop-blur-xl">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: rgbCss(STATE_COLOR[s.status]) }}
            />
            <span className="text-xs uppercase tracking-wide text-slate-400">
              {STATE_LABEL[s.status]}
            </span>
          </div>
          <h2 className="mt-1 text-base font-semibold leading-tight text-slate-100">{s.name}</h2>
          <p className="text-xs text-slate-500">
            {s.technology ? TECH_LABEL[s.technology] : "—"} · {s.district ?? s.state}
          </p>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
          ✕
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <Fact label="Capacity" value={mw(s.capacity_mw)} />
        <Fact label="Registry status" value={s.mastr_status ?? "—"} />
        <Fact label="Commissioned" value={fmtDate(s.commissioning_date)} />
        <Fact label="Planned" value={fmtDate(s.planned_commissioning_date)} />
        {s.unit_count > 1 && <Fact label="Units" value={`${s.unit_count} (clustered)`} />}
        <Fact label="Owner" value={s.owner ?? "—"} mono />
      </div>

      {(chipBefore || chipAfter) && (
        <Section title="Satellite — before / after">
          <div className="grid grid-cols-2 gap-2">
            <Chip url={chipBefore} label={`Before · ${chipBeforeDate}`} />
            <Chip url={chipAfter} label={`After · ${chipAfterDate}`} />
          </div>
          <p className="mt-1 text-[10px] text-slate-500">
            True-colour Sentinel-2, framed to the site footprint.
          </p>
        </Section>
      )}

      {detail.deadlines.length > 0 && (
        <Section title="Schedule & deadline">
          <Schedule deadlines={detail.deadlines} status={s.status} />
        </Section>
      )}

      <Section title="Construction timeline">
        <Timeline detections={detail.detections} />
      </Section>

      {hasSeries && series && (
        <Section title="Satellite signal">
          <MetricChart metric="ndvi" points={series.ndvi} detections={detail.detections} />
          <MetricChart metric="bsi" points={series.bsi} detections={detail.detections} />
          <MetricChart metric="vh_db" points={series.vh_db} detections={detail.detections} />
          <p className="text-[10px] leading-relaxed text-slate-500">
            Dashed lines mark detected state changes. Each is backed by the satellite scenes
            cited above — the agent narrates only what is stored here.
          </p>
        </Section>
      )}
    </aside>
  );
}

const Chip = ({ url, label }: { url: string | null; label: string }) =>
  url ? (
    <figure className="overflow-hidden rounded-lg border border-white/10">
      <img src={url} alt={label} className="aspect-square w-full object-cover" loading="lazy" />
      <figcaption className="bg-black/40 px-2 py-1 text-[10px] text-slate-300">{label}</figcaption>
    </figure>
  ) : (
    <div className="flex aspect-square items-center justify-center rounded-lg border border-white/10 bg-white/[0.02] text-[10px] text-slate-600">
      no image
    </div>
  );

const Fact = ({ label, value, mono }: { label: string; value: string; mono?: boolean }) => (
  <div className="rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-1.5">
    <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    <div className={`text-slate-200 ${mono ? "font-mono text-[11px]" : ""}`}>{value}</div>
  </div>
);

const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <div>
    <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
      {title}
    </h3>
    {children}
  </div>
);
