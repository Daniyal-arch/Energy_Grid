// Colour helpers. RGB tuples feed deck.gl directly; rgbCss turns them into CSS.

export type RGB = [number, number, number];

export const rgbCss = (c: RGB, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
