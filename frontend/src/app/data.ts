// Every data file the app reads, loaded once on first use and shared by map and panels.
// Bundled copies ship with the site; the GitHub Actions workflows keep newer copies on the
// eu-data (every 30 min) and eu-days (daily) branches, and the newer one wins.

import { useEffect } from "react";
import { create } from "zustand";

export const SNAPSHOT_REMOTE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-data/eu";
export const ARCHIVE_REMOTE = "https://raw.githubusercontent.com/Daniyal-arch/Energy_Grid/eu-days/eu";
// recordings (frontend/scripts/record-video.mjs) wait for the archive instead of falling back
const RECORDING = new URLSearchParams(window.location.search).has("record");

export async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return (await r.json()) as T;
}

/** A refresh with nothing in it (a failed run) must never replace good data. */
function hasData(v: unknown): boolean {
  const o = v as { borders?: unknown[]; countries?: Record<string, unknown>; regions?: Record<string, unknown> };
  if (Array.isArray(o.borders)) return o.borders.length > 0;
  if (o.countries && typeof o.countries === "object") return Object.keys(o.countries).length > 0;
  if (o.regions && typeof o.regions === "object") return Object.keys(o.regions).length > 0;
  return true;
}

/** The bundled copy at once, then the remote one if it is newer and not empty. */
function newer<T extends { fetched: string }>(name: string, remoteBase: string, use: (v: T) => void): Promise<void> {
  let bundled: T | null = null;
  const local = getJson<T>(`/data/eu/${name}`)
    .then((v) => {
      bundled = v;
      use(v);
    })
    .catch(() => {});
  const remote = fetch(`${remoteBase}/${name}?t=${Date.now()}`, { signal: AbortSignal.timeout(8000) })
    .then((r) => (r.ok ? (r.json() as Promise<T>) : Promise.reject()))
    .then((v) => {
      if (hasData(v) && (!bundled || v.fetched > bundled.fetched)) use(v);
    })
    .catch(() => {});
  return Promise.all([local, remote]).then(() => undefined);
}

type Loader = (set: (v: unknown) => void) => Promise<unknown>;
const bundled = (name: string): Loader => (set) => getJson(`/data/eu/${name}`).then(set);
const snapshot = (name: string): Loader => (set) => newer(name, SNAPSHOT_REMOTE, set);
const archive = (name: string): Loader => (set) => newer(name, ARCHIVE_REMOTE, set);

const STATIC: Record<string, Loader> = {
  grid: bundled("grid.json"),
  plants: bundled("plants.json"),
  countries: bundled("countries.json"),
  gas: bundled("gas.json"),
  world: bundled("world.json"),
  transition: bundled("transition.json"),
  monthly: bundled("monthly.json"),
  worldPlants: bundled("world_plants.json"),
  plantNames: bundled("world_plant_names.json"),
  cables: bundled("cables.json"),
  // Global Energy Monitor trackers (scripts/build_gem_layers.py)
  gemGas: bundled("gem/pipelines_gas.json"),
  gemOil: bundled("gem/pipelines_oil.json"),
  gemLng: bundled("gem/lng.json"),
  gemCoalTerminals: bundled("gem/coal_terminals.json"),
  gemFields: bundled("gem/fields.json"),
  gemCoalMines: bundled("gem/coal_mines.json"),
  gemMethane: bundled("gem/methane.json"),
  gemSteel: bundled("gem/steel.json"),
  gemCement: bundled("gem/cement.json"),
  gemChemicals: bundled("gem/chemicals.json"),
  gemIronOre: bundled("gem/iron_ore.json"),
  gemFinance: bundled("gem/finance.json"),
  flows: snapshot("flows.json"),
  stats: snapshot("stats.json"),
  reference: snapshot("reference.json"),
  dossier: snapshot("dossier.json"),
  outages: snapshot("outages.json"),
  wind: snapshot("wind.json"),
  windWorld: snapshot("wind_world.json"),
  aemo: snapshot("aemo.json"),
  us: snapshot("us.json"),
  brazil: snapshot("brazil.json"),
  taiwan: snapshot("taiwan.json"),
  ontario: snapshot("ontario.json"),
  prices: archive("prices.json"),
  worldStats: archive("world_stats.json"),
  datacentres: archive("datacentres.json"),
  irena: archive("irena.json"),
  dayIndex: async (set) => {
    // days from the cloud archive plus any bundled with the site (one answer, so the
    // replay does not start on a bundled day and then jump to a newer one)
    const [remote, local] = await Promise.allSettled([
      fetch(`${ARCHIVE_REMOTE}/day/index.json?t=${Date.now()}`, { signal: AbortSignal.timeout(RECORDING ? 30_000 : 4000) }).then((r) =>
        r.ok ? (r.json() as Promise<{ days: string[] }>) : Promise.reject(),
      ),
      getJson<{ days: string[] }>("/data/eu/day/index.json"),
    ]);
    const remoteDays = remote.status === "fulfilled" ? remote.value.days : [];
    const localDays = local.status === "fulfilled" ? local.value.days : [];
    set({ remote: remoteDays, local: localDays, all: [...new Set([...remoteDays, ...localDays])].sort() });
  },
};

/** The archive first, then the bundled copy (day files, their wind, week and unit files). */
function archiveFirst(remote: string, local: string): Loader {
  return (set) =>
    fetch(remote, { signal: AbortSignal.timeout(RECORDING ? 60_000 : 8000) })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .catch(() => getJson(local))
      .then(set);
}

function loaderFor(key: string): Loader | null {
  if (STATIC[key]) return STATIC[key];
  const [kind, arg] = key.split(":");
  // a day only in the bundle loads from the bundle (no wait for the archive)
  const index = () => useDataStore.getState().files.dayIndex as { remote: string[]; local: string[] } | undefined;
  // recordings take a bundled copy first (the archive can be slow to answer)
  const inArchive = () => !(RECORDING && index()?.local.includes(arg)) && (index()?.remote.includes(arg) ?? true);
  if (kind === "day") return inArchive() ? archiveFirst(`${ARCHIVE_REMOTE}/day/${arg}.json`, `/data/eu/day/${arg}.json`) : bundled(`day/${arg}.json`);
  if (kind === "dayWind") return inArchive() ? archiveFirst(`${ARCHIVE_REMOTE}/wind/${arg}.json`, `/data/eu/wind/${arg}.json`) : bundled(`wind/${arg}.json`);
  if (kind === "week")
    return (set) =>
      Promise.allSettled([
        getJson<{ days: string[] }>(`${ARCHIVE_REMOTE}/week/${arg}.json`),
        getJson<{ days: string[] }>(`/data/eu/week/${arg}.json`),
      ]).then((res) => {
        // whichever holds more days
        const ok = res.flatMap((x) => (x.status === "fulfilled" ? [x.value] : []));
        set(ok.sort((a, b) => b.days.length - a.days.length)[0] ?? null);
      });
  if (kind === "units") return (set) => getJson<{ plants: unknown[] }>(`/data/eu/plants/${arg}.json`).then((d) => set(d.plants));
  return null;
}

interface DataStore {
  files: Record<string, unknown>;
  failed: Record<string, true>;
}
export const useDataStore = create<DataStore>(() => ({ files: {}, failed: {} }));
const started = new Set<string>();

/** Start loading a file (once); `force` reloads it (live files on a timer). */
export function ensure(key: string, force = false): void {
  if (started.has(key) && !force) return;
  const load = loaderFor(key);
  if (!load) return;
  started.add(key);
  load((v) => useDataStore.setState((s) => ({ files: { ...s.files, [key]: v } }))).catch(() =>
    useDataStore.setState((s) => ({ failed: { ...s.failed, [key]: true } })),
  );
}

/** A file's content (undefined until it arrives); loading starts on first use. */
export function useFile<T>(key: string | null): T | undefined {
  useEffect(() => {
    if (key) ensure(key);
  }, [key]);
  return useDataStore((s) => (key ? (s.files[key] as T | undefined) : undefined));
}

/** Read a file outside React (the map's render loop). */
export const fileOf = <T,>(key: string): T | undefined => useDataStore.getState().files[key] as T | undefined;

/** Live files, reloaded every 10 minutes while the page is open. */
export const LIVE_KEYS = ["flows", "stats", "outages", "wind", "aemo", "us", "brazil", "taiwan", "ontario", "windWorld"];

// development only: lets headless checks read what has loaded
if (import.meta.env.DEV) (window as unknown as { __data: typeof useDataStore }).__data = useDataStore;
