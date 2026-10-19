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
  const o = v as { pairs?: unknown[]; borders?: unknown[]; countries?: Record<string, unknown>; regions?: Record<string, unknown> };
  if (Array.isArray(o.borders)) return o.borders.length > 0;
  if (Array.isArray(o.pairs)) return o.pairs.length > 0;
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
const bundledUs = (name: string): Loader => (set) => getJson(`/data/us/${name}`).then(set);
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
  // the solar and wind resource atlases: classes, tiles, lookup grid (scripts/build_atlas.py)
  atlas: bundled("atlas.json"),
  // bidding zones built from NUTS regions; cities of 100,000+ for the search (scripts/build_shapes.py)
  zones: bundled("zones.json"),
  // country and state profiles (scripts/build_profiles.py, build_population.py)
  pfEurostat: bundled("profiles/eurostat_balances.json"),
  pfEi: bundled("profiles/ei_review.json"),
  pfEdgar: bundled("profiles/edgar.json"),
  pfPopulation: bundled("profiles/population.json"),
  pfSeds: bundled("profiles/us_seds.json"),
  steo: bundledUs("steo.json"),
  // TYNDP 2024 projects; German redispatch 2013-2020 (scripts/build_tyndp.py, build_germany.py)
  tyndp: bundled("tyndp.json"),
  // Global Renewables Watch per country (scripts/build_grw.py)
  grwCountries: bundled("grw_countries.json"),
  deRedispatch: bundled("de_redispatch.json"),
  // what the map holds per country and dataset family (scripts/coverage.py)
  coverage: bundled("coverage.json"),
  cities: bundled("cities.json"),
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
  // the US grid pack (scripts/fetch_us_grid.py; .github/workflows/us-grid.yml refreshes it on main)
  usPlants: bundledUs("plants.json"),
  usQueue: bundledUs("queue.json"),
  // the markets' own queues, weekly (scripts/fetch_us_queues.py)
  usQueuesLive: bundledUs("queues_live.json"),
  usTurbines: bundledUs("turbines.json"),
  // every large solar array (scripts/fetch_uspvdb.py, USPVDB); outlines only when zoomed in
  usSolar: bundledUs("solar.json"),
  usSolarOutlines: bundledUs("solar_outlines.json"),
  usStates: bundledUs("states.json"),
  // public EV fast chargers (scripts/fetch_ev_chargers.py, NREL AFDC; monthly in us-grid)
  evChargers: bundledUs("ev_chargers.json"),
  // EPA GHGRP direct emitters; per-plant generation and CO2 (scripts/build_us_perf.py)
  ghgrp: bundledUs("ghgrp.json"),
  plantsPerf: bundledUs("plants_perf.json"),
  // CO₂ per kWh per US region, EIA-930 grid monitor (scripts/fetch_live_co2.py us, weekly)
  usCo2: bundledUs("co2.json"),
  flows: snapshot("flows.json"),
  stats: snapshot("stats.json"),
  // transfer capacity per border, today and tomorrow (scripts/fetch_eu_capacity.py)
  capacity: snapshot("capacity.json"),
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
  // Great Britain's carbon intensity (NESO) and Denmark every 5 minutes (Energinet)
  gbCarbon: snapshot("gb_carbon.json"),
  // CO₂ per kWh as France, Spain and Ireland publish it (scripts/fetch_live_co2.py)
  liveCo2: snapshot("live_co2.json"),
  dkLive: snapshot("dk_live.json"),
  prices: archive("prices.json"),
  // lines out of service (ENTSO-E A78), daily on eu-days (scripts/build_transmission_outages.py)
  linesOut: archive("transmission_outages.json"),
  // redispatch, countertrading, congestion costs, GB constraints, CAISO curtailment (scripts/build_congestion.py)
  congestion: archive("congestion.json"),
  // Japan and Mexico day-ahead prices, daily on eu-days (scripts/build_markets.py)
  jepx: archive("jepx.json"),
  cenace: archive("cenace.json"),
  // imbalance prices per zone, the last 30 days (scripts/build_imbalance.py)
  imbalance: archive("imbalance.json"),
  // US day-ahead prices at one hub per market, today and tomorrow (scripts/fetch_us_prices.py)
  usPrices: archive("us_prices.json"),
  worldStats: archive("world_stats.json"),
  datacentres: archive("datacentres.json"),
  irena: archive("irena.json"),
  // ENTSOG gas flows per gas day (scripts/fetch_entsog.py, daily on eu-days)
  gasFlows: archive("gas_flows.json"),
  // LNG send-out per terminal, last 30 gas days (scripts/fetch_alsi.py, GIE ALSI)
  lngTerminals: archive("lng_terminals.json"),
  // EU ETS verified emissions per installation (scripts/fetch_eu_ets.py)
  ets: archive("ets.json"),
  // Climate TRACE modelled emissions per facility (scripts/fetch_climate_trace.py)
  ctrace: archive("ctrace.json"),
  // where new demand or generation can connect: GB, NL, ES (scripts/fetch_connect_here.py)
  connect: archive("connect.json"),
  // France, Italy, Belgium, Portugal, Ireland, Poland (scripts/build_connect_more.py)
  // every unit from the national registers (scripts/build_registers.py)
  registerGB: bundled("registers/gb.json"),
  registerFR: bundled("registers/fr.json"),
  registerDK: bundled("registers/dk.json"),
  registerSE: bundled("registers/se.json"),
  registerIE: bundled("registers/ie.json"),
  registerBE: bundled("registers/be.json"),
  registerFI: bundled("registers/fi.json"),
  registerPT: bundled("registers/pt.json"),
  registerCZ: bundled("registers/cz.json"),
  // room to connect in ten more countries (scripts/build_connect_eu.py)
  connect7AT: bundled("connect/at.json"),
  connect7BG: bundled("connect/bg.json"),
  connect7CZ: bundled("connect/cz.json"),
  connect7DE: bundled("connect/de.json"),
  connect7DK: bundled("connect/dk.json"),
  connect7EE: bundled("connect/ee.json"),
  connect7LT: bundled("connect/lt.json"),
  connect7LU: bundled("connect/lu.json"),
  connect7MT: bundled("connect/mt.json"),
  connect7SE: bundled("connect/se.json"),
  connect7ESDSO: bundled("connect/es_dso.json"),
  connect7GBDSO: bundled("connect/gb_dso.json"),
  connectFR: bundled("connect/fr.json"),
  connectIT: bundled("connect/it.json"),
  connectBE: bundled("connect/be.json"),
  connectPT: bundled("connect/pt.json"),
  connectIE: bundled("connect/ie.json"),
  connectPL: bundled("connect/pl.json"),
  // retail electricity and gas prices (scripts/fetch_retail_prices.py, Eurostat + EIA)
  retail: archive("retail.json"),
  // US outages per county (scripts/build_us_outages.py, EAGLE-I) and their outlines
  usOutages: bundled("us_outages.json"),
  usCounties: bundledUs("counties.json"),
  // water risk per river basin (scripts/build_aqueduct.py, WRI Aqueduct 4.0)
  water: bundled("water.json"),
  // offshore wind farms in European seas (scripts/fetch_emodnet_wind.py, EMODnet)
  offshoreWind: bundled("offshore_wind.json"),
  // every unit in Germany (scripts/build_mastr.py, Marktstammdatenregister)
  mastrUnits: bundled("mastr/units_large.json"),
  mastrMuni: bundled("mastr/municipalities.json"),
  // the grid operator per municipality (MaStR) and US utilities per county (EIA-861) (scripts/build_grid_more.py)
  deGridOperators: bundled("de_grid_operators.json"),
  usUtilities: bundledUs("utilities.json"),
  // EMODnet cables and pipelines at sea (scripts/build_grid_more.py emodnet)
  seaCables: bundled("sea_cables.json"),
  // what stops a build: tiles, flood classes and lookups; protected areas per country (scripts/build_constraints.py)
  constraints: bundled("constraints.json"),
  protected: bundled("protected.json"),
  // what is coming and what it costs (scripts/build_coming.py)
  hydrogen: bundled("hydrogen.json"),
  gasProjects: bundled("gas_projects.json"),
  auctions: bundled("auctions.json"),
  costs: bundled("costs.json"),
  pfGhg: bundled("profiles/ghg_inventory.json"),
  // US disturbances (DOE OE-417) and planning-area demand (FERC 714) (scripts/build_us_reliability.py)
  oe417: bundledUs("oe417.json"),
  ferc714: bundledUs("ferc714.json"),
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
  // the US replay (scripts/build_us_day.py): the archive's days and the bundled ones
  usDayIndex: async (set) => {
    const [remote, local] = await Promise.allSettled([
      fetch(`${ARCHIVE_REMOTE}/usday/index.json?t=${Date.now()}`, { signal: AbortSignal.timeout(RECORDING ? 30_000 : 4000) }).then((r) =>
        r.ok ? (r.json() as Promise<{ days: string[] }>) : Promise.reject(),
      ),
      getJson<{ days: string[] }>("/data/eu/usday/index.json"),
    ]);
    const remoteDays = remote.status === "fulfilled" ? remote.value.days : [];
    const localDays = local.status === "fulfilled" ? local.value.days : [];
    set({ remote: remoteDays, local: localDays, all: [...new Set([...remoteDays, ...localDays])].sort() });
  },
  // US fossil plants hour by hour (scripts/build_us_units.py, EPA CAMPD)
  usUnitIndex: async (set) => {
    const [remote, local] = await Promise.allSettled([
      fetch(`${ARCHIVE_REMOTE}/usunits/index.json?t=${Date.now()}`, { signal: AbortSignal.timeout(RECORDING ? 30_000 : 4000) }).then((r) =>
        r.ok ? (r.json() as Promise<{ days: string[] }>) : Promise.reject(),
      ),
      getJson<{ days: string[] }>("/data/eu/usunits/index.json"),
    ]);
    const ok = [remote, local].flatMap((x) => (x.status === "fulfilled" ? [x.value] : []));
    set({ days: [...new Set(ok.flatMap((x) => x.days))].sort(), remote: remote.status === "fulfilled" ? remote.value.days : [] });
  },
  // output per plant (scripts/build_eu_units.py): the archive's days and the bundled ones
  unitIndex: async (set) => {
    const [remote, local] = await Promise.allSettled([
      fetch(`${ARCHIVE_REMOTE}/units/index.json?t=${Date.now()}`, { signal: AbortSignal.timeout(RECORDING ? 30_000 : 4000) }).then((r) =>
        r.ok ? (r.json() as Promise<{ days: string[]; complete: string[] }>) : Promise.reject(),
      ),
      getJson<{ days: string[]; complete: string[] }>("/data/eu/units/index.json"),
    ]);
    const ok = [remote, local].flatMap((x) => (x.status === "fulfilled" ? [x.value] : []));
    set({
      days: [...new Set(ok.flatMap((x) => x.days))].sort(),
      complete: [...new Set(ok.flatMap((x) => x.complete))].sort(),
      remote: remote.status === "fulfilled" ? remote.value.days : [],
    });
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
  // US node prices for one day (scripts/fetch_us_nodes.py, daily on eu-days)
  if (kind === "usNodes") return archiveFirst(`${ARCHIVE_REMOTE}/us_nodes/${arg}.json`, `/data/eu/us_nodes/${arg}.json`);
  if (kind === "usDay") {
    const idx = useDataStore.getState().files.usDayIndex as { remote: string[]; local: string[] } | undefined;
    const remote = !(RECORDING && idx?.local.includes(arg)) && (idx?.remote.includes(arg) ?? true);
    return remote ? archiveFirst(`${ARCHIVE_REMOTE}/usday/${arg}.json`, `/data/eu/usday/${arg}.json`) : bundled(`usday/${arg}.json`);
  }
  if (kind === "unitOut") {
    const remote = (useDataStore.getState().files.unitIndex as { remote: string[] } | undefined)?.remote.includes(arg) ?? true;
    return remote && !RECORDING ? archiveFirst(`${ARCHIVE_REMOTE}/units/${arg}.json`, `/data/eu/units/${arg}.json`) : bundled(`units/${arg}.json`);
  }
  if (kind === "usUnitOut") {
    const remote = (useDataStore.getState().files.usUnitIndex as { remote: string[] } | undefined)?.remote.includes(arg) ?? true;
    return remote && !RECORDING ? archiveFirst(`${ARCHIVE_REMOTE}/usunits/${arg}.json`, `/data/eu/usunits/${arg}.json`) : bundled(`usunits/${arg}.json`);
  }
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
export const LIVE_KEYS = ["flows", "stats", "outages", "wind", "aemo", "us", "brazil", "taiwan", "ontario", "windWorld", "gbCarbon", "dkLive"];

// development only: lets headless checks read what has loaded
if (import.meta.env.DEV) (window as unknown as { __data: typeof useDataStore }).__data = useDataStore;
