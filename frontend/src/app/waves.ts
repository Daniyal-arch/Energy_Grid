// The registry waves (scripts/wave9.py, run with WAVE=9, 10, ...): each writes app/wave<N>.json
// with its layers (ids w<N>_<source>), colourings (w<N>c_<source>) and dataset entries, and
// its files under data/eu/w<N>/ and data/eu/w<N>c/. Everything below reads them as one list.

import WAVE9 from "./wave9.json";
import WAVE10 from "./wave10.json";

const ALL = [WAVE9, WAVE10] as { layers: unknown[]; colours: unknown[]; datasets: unknown[] }[];

export const WAVES = {
  layers: ALL.flatMap((w) => w.layers),
  colours: ALL.flatMap((w) => w.colours),
  datasets: ALL.flatMap((w) => w.datasets),
};

/** A wave colouring id (w9c_<source>, w10c_<source>). */
export const isWaveColour = (id: string): boolean => /^w\d+c_/.test(id);
/** The loader key of a wave layer or colouring id: w10_x -> w10:x, w10c_x -> w10c:x. */
export const waveKey = (id: string): string => id.replace(/^(w\d+c?)_/, "$1:");
/** The deck.gl layer id of a wave id (w10_x -> w10-x), and back. */
export const deckId = (id: string): string => id.replace(/^(w\d+c?)_/, "$1-");
export const fromDeckId = (id: string): string => id.replace(/-lines$/, "").replace(/^(w\d+c?)-/, "$1_");
