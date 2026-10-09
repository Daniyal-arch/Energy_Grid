// Derived layer data is rebuilt only when its inputs change. deck.gl compares `data` by
// reference, so an unchanged array means no GPU upload: this is what keeps many layers smooth.

const cache = new Map<string, { deps: unknown[]; value: unknown }>();

export function memo<T>(key: string, deps: unknown[], make: () => T): T {
  const hit = cache.get(key);
  if (hit && hit.deps.length === deps.length && hit.deps.every((d, i) => Object.is(d, deps[i]))) return hit.value as T;
  const value = make();
  cache.set(key, { deps, value });
  return value;
}

/** An empty array that never changes identity (a hidden layer uploads nothing). */
export const NONE: never[] = [];
