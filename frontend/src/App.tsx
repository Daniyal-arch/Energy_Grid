import { useEffect, useMemo, useState } from "react";

import AgentPanel from "./components/AgentPanel";
import CommandBar from "./components/CommandBar";
import FilterPanel from "./components/FilterPanel";
import MapView, { type ColorMode } from "./components/MapView";
import PulseHeader from "./components/PulseHeader";
import SiteDrawer from "./components/SiteDrawer";
import { api, type AgentResult, type RecentDetection, type Site } from "./lib/api";
import { applyFilter, emptyFilter, type Filter } from "./lib/query";

type Bounds = [[number, number], [number, number]] | null;

function boundsOf(sites: Site[]): Bounds {
  if (sites.length < 1) return null;
  let minLon = 180,
    minLat = 90,
    maxLon = -180,
    maxLat = -90;
  for (const s of sites) {
    minLon = Math.min(minLon, s.lon);
    maxLon = Math.max(maxLon, s.lon);
    minLat = Math.min(minLat, s.lat);
    maxLat = Math.max(maxLat, s.lat);
  }
  // pad a touch so a single point isn't a zero-area box
  return [
    [minLon - 0.15, minLat - 0.15],
    [maxLon + 0.15, maxLat + 0.15],
  ];
}

export default function App() {
  const [sites, setSites] = useState<Site[]>([]);
  const [recent, setRecent] = useState<RecentDetection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>(emptyFilter());
  const [colorMode, setColorMode] = useState<ColorMode>("state");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Bounds>(null);

  // agent state
  const [agent, setAgent] = useState<AgentResult | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);

  useEffect(() => {
    api.sites().then(setSites).catch((e) => setError(String(e)));
    api.recent(60).then(setRecent).catch(() => {});
  }, []);

  const sitesById = useMemo(() => new Map(sites.map((s) => [s.id, s])), [sites]);

  // the map shows the agent's result set when one is active, else the manual filter
  const displayed = useMemo(() => {
    if (agent) {
      const ids = new Set(agent.site_ids);
      return sites.filter((s) => ids.has(s.id));
    }
    return applyFilter(sites, filter);
  }, [sites, filter, agent]);

  const ask = async (text: string) => {
    setAgentLoading(true);
    setAgentError(null);
    setAgent(null);
    try {
      const res = await api.ask(text);
      setAgent(res);
      const b = boundsOf(res.site_ids.map((id) => sitesById.get(id)!).filter(Boolean));
      if (b) setFocus(b);
    } catch (e) {
      setAgentError(e instanceof Error ? e.message : String(e));
    } finally {
      setAgentLoading(false);
    }
  };

  const closeAgent = () => {
    setAgent(null);
    setAgentError(null);
  };

  // manual filter takes over from the agent view
  const setFilterManual = (f: Filter) => {
    setFilter(f);
    setAgent(null);
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#070a10] text-slate-100">
      <MapView
        sites={displayed}
        colorMode={colorMode}
        recent={recent}
        selectedId={selectedId}
        onSelect={setSelectedId}
        focusBounds={focus}
      />

      <header className="pointer-events-none absolute left-0 right-0 top-0 z-10 flex items-start justify-between p-4">
        <div className="pointer-events-auto flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400" />
          <div>
            <div className="text-sm font-semibold leading-none">gridwatch</div>
            <div className="text-[10px] text-slate-500">German energy construction · live</div>
          </div>
        </div>
        <div className="pointer-events-auto">
          <PulseHeader sites={sites} recent={recent} />
        </div>
      </header>

      <div className="pointer-events-none absolute left-1/2 top-20 z-10 -translate-x-1/2">
        <div className="pointer-events-auto">
          <CommandBar loading={agentLoading} onAsk={ask} />
          <AgentPanel
            loading={agentLoading}
            result={agent}
            error={agentError}
            sitesById={sitesById}
            onPick={setSelectedId}
            onClose={closeAgent}
          />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 top-0 z-10 pt-[120px]">
        <FilterPanel
          all={sites}
          filter={filter}
          setFilter={setFilterManual}
          colorMode={colorMode}
          setColorMode={setColorMode}
        />
      </div>

      {selectedId && <SiteDrawer id={selectedId} onClose={() => setSelectedId(null)} />}

      {error && (
        <div className="absolute bottom-4 left-1/2 z-30 -translate-x-1/2 rounded-lg border border-red-500/30 bg-red-950/80 px-4 py-2 text-xs text-red-200">
          Couldn’t reach the API ({error}). Start it with{" "}
          <code className="text-red-100">uv run uvicorn app.main:app --app-dir backend</code>
        </div>
      )}
    </div>
  );
}
