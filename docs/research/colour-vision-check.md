# Colour-vision check of the agent palettes and fuel colours (brief 30 Track 5.5, 2026-11-06)

Method: each colour simulated for protanopia, deuteranopia and tritanopia (Machado, Oliveira and
Fernandes 2009, severity 1.0, linear RGB), then the smallest CIELAB distance (ΔE76) between any two
colours of a palette, and the lightness step between neighbouring stops of a ramp. ΔE below ~10
reads as "hard to tell apart".

| Palette | Normal | Protan | Deutan | Tritan |
|---|---|---|---|---|
| Agent categorical (before) | 31.7 | 9.6 | **1.7** (blue vs lavender) | 9.9 |
| Agent categorical (after: lavender to teal `[60,160,145]`) | 9.2 worst over all four | | | |
| Fuel colours (the map's own) | 16.7 | 16.6 | **5.6** (nuclear pink vs coal grey) | 10.0 |

Ramps (lightness steps, deutan / protan): `neutral`, `share` rise evenly (15-25 per step);
`price` has one short protan step (4.2, grey to orange) but rises throughout; `room` (before)
fell at its green end (-7.9 / -2.4), so the best and the third class looked alike: its green end
is now `[150,230,210]` and every step rises (7.6 / 12.9 at the end).

Changed: `frontend/src/map/agentLayers.ts` (categorical 6th colour, `room` ramp end). Not
changed: the fuel colours (the map's established key; a change is the owner's design call):
nuclear and coal are hard to tell apart for deuteranopes; the fuel name is always in the key
and the hover card.
