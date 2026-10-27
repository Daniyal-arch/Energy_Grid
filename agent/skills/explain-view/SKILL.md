---
name: explain-view
description: Explaining what the map shows now ("explain this map") from the current view (URL state) - which layers are on, what they measure, and what stands out. Use when the question refers to the view, the screen or "this map".
---
# Explaining the view

Relies on: `frontend/src/app/datasets.json` (layers and what they show), the catalogue.

1. The current view arrives with the question (layers, colouring, mode, selection, camera).
   Name each layer that is on and what it measures, from `search_catalog` hits of kind
   "map dataset".
2. What stands out: query the figures behind the visible layers for the area in view (top
   values, extremes, the selected country) and state them with their sources.
3. Explain encodings in words: sizes, colours and their palettes, the period (live, a day, a
   year). Colours are relative to what is in view.
4. Do not describe what you cannot see in the data (no guessing at the picture).
