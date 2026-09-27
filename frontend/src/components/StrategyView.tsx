import { useEffect, useMemo, useState } from "react";

import { api, type StrategicAspect, type StrategicDataset } from "../lib/api";

const STATUS_LABEL: Record<StrategicDataset["status"], string> = {
  implemented: "Connected",
  partial: "Partial",
  planned: "Planned",
  candidate: "Candidate",
};

const STATUS_STYLE: Record<StrategicDataset["status"], string> = {
  implemented: "border-positive/30 bg-positive/10 text-positive",
  partial: "border-sky-400/30 bg-sky-400/10 text-sky-300",
  planned: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  candidate: "border-line bg-ink-800 text-slate-400",
};

export default function StrategyView() {
  const [aspects, setAspects] = useState<StrategicAspect[]>([]);
  const [datasets, setDatasets] = useState<StrategicDataset[]>([]);
  const [selected, setSelected] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .strategyContext()
      .then((context) => {
        setAspects(context.aspects);
        setDatasets(context.datasets);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const visible = useMemo(() => {
    if (selected === "all") return datasets;
    const ids = new Set(aspects.find((aspect) => aspect.id === selected)?.dataset_ids ?? []);
    return datasets.filter((dataset) => ids.has(dataset.id));
  }, [aspects, datasets, selected]);

  const active = aspects.find((aspect) => aspect.id === selected);

  return (
    <main className="h-full overflow-y-auto bg-ink-950 px-6 pb-8 pt-16">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-line pb-5">
          <p className="eyebrow">Germany InfraAtlas</p>
          <div className="mt-1 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-slate-100">Strategic context</h1>
              <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-400">
                Infrastructure exposure across energy security, trade dependencies, transport,
                industrial resilience, and transition delivery.
              </p>
            </div>
            <div className="flex gap-4 text-right">
              <Kpi label="Sources" value={datasets.length || "-"} />
              <Kpi
                label="Connected"
                value={datasets.filter((dataset) => dataset.status === "implemented").length || "-"}
              />
            </div>
          </div>
        </header>

        <div className="grid gap-8 py-6 lg:grid-cols-[250px_minmax(0,1fr)]">
          <aside>
            <div className="eyebrow mb-2">Analysis lens</div>
            <div className="space-y-1">
              <LensButton
                active={selected === "all"}
                label="All infrastructure"
                count={datasets.length}
                onClick={() => setSelected("all")}
              />
              {aspects.map((aspect) => (
                <LensButton
                  key={aspect.id}
                  active={selected === aspect.id}
                  label={aspect.label}
                  count={aspect.dataset_ids.length}
                  onClick={() => setSelected(aspect.id)}
                />
              ))}
            </div>

            {active && (
              <div className="mt-6 border-t border-line pt-4">
                <div className="eyebrow mb-2">Key questions</div>
                <ul className="space-y-3 text-xs leading-relaxed text-slate-400">
                  {active.questions.map((question) => (
                    <li key={question} className="border-l border-line-strong pl-3">
                      {question}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="eyebrow">Source coverage</div>
                <h2 className="mt-1 text-base font-medium text-slate-200">
                  {active?.label ?? "All researched datasets"}
                </h2>
              </div>
              <span className="font-mono text-xs tabular-nums text-slate-500">
                {visible.length} datasets
              </span>
            </div>

            {error ? (
              <div className="border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : (
              <div className="divide-y divide-line border-y border-line">
                {visible.map((dataset) => (
                  <article key={dataset.id} className="grid gap-3 py-4 md:grid-cols-[1fr_150px]">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <a
                          href={dataset.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-slate-100 hover:text-accent-300"
                        >
                          {dataset.name}
                        </a>
                        <span
                          className={`rounded-sm border px-1.5 py-px text-[10px] font-medium ${STATUS_STYLE[dataset.status]}`}
                        >
                          {STATUS_LABEL[dataset.status]}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{dataset.source}</p>
                      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
                        {dataset.why}
                      </p>
                    </div>
                    <dl className="grid grid-cols-2 gap-2 text-xs md:block md:text-right">
                      <div>
                        <dt className="eyebrow">Cadence</dt>
                        <dd className="mt-0.5 text-slate-300">{dataset.cadence}</dd>
                      </div>
                      <div className="md:mt-3">
                        <dt className="eyebrow">Access</dt>
                        <dd className="mt-0.5 leading-snug text-slate-400">{dataset.access}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

const LensButton = ({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean;
  label: string;
  count: number;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    className={`flex w-full items-center justify-between rounded px-2.5 py-2 text-left text-sm transition ${
      active ? "bg-accent/15 text-accent-300" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
    }`}
  >
    <span>{label}</span>
    <span className="font-mono text-[10px] tabular-nums text-slate-500">{count}</span>
  </button>
);

const Kpi = ({ label, value }: { label: string; value: number | string }) => (
  <div>
    <div className="font-mono text-xl font-semibold tabular-nums text-slate-100">{value}</div>
    <div className="eyebrow mt-0.5">{label}</div>
  </div>
);
