import type { Site } from "./api";

let cache: Promise<Site[]> | null = null;

export function loadEnergySites(): Promise<Site[]> {
  if (cache) return cache;
  cache = fetch("/data/energy_sites.json").then((response) => {
    if (!response.ok) throw new Error(`energy_sites.json -> ${response.status}`);
    return response.json() as Promise<Site[]>;
  });
  return cache;
}
