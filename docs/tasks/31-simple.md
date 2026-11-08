# 31. Simple: one purpose per screen, nothing that needs explaining

## Goal

Make InfraAtlas as calm and obvious as Linear's website or Apple Notes: simple purpose, simple
architecture, simple design, simple implementation. Every change should make the experience
better for three readers at once, without breaking anything:

- **UX**: the person looking at the map and the panels.
- **DX**: the developer reading and changing the code.
- **AX**: the agent (our own LangGraph agent, MCP clients, a coding agent working in this
  repository) reading tool descriptions, catalogues and docs.

## The rule

Cut taglines, helper text and secondary labels. If a screen needs them to make sense, fix the
layout instead: a clearer order, a name that says what it is, a control placed where it is
used, one fewer step.

## What stays (the hard rules still apply)

- **Every figure names its source**, and computed values say how (CLAUDE.md hard rule 1). This
  is not helper text: it moves, it is never deleted. Sources live in one place per panel (the
  card's own "Sources & method" disclosure, the tooltip's source line, the dataset's details in
  the Layers panel), not repeated in paragraphs around it.
- Map attribution that a licence requires (OpenStreetMap, ODbL) stays visible.
- Units, as-of dates and "estimate" marks stay next to the number they qualify.
- No new floating panels, no colour or palette changes, the grid stays the hero.

## How to work

- One screen or one module at a time; one small commit each.
- Before and after screenshots of the screen (Playwright, never committed); the after must
  show every figure the before showed, with its source reachable in one click.
- `npm run build`, `uv run pytest`, `cd backend && uv run pytest` green before every push.
- Record each cut in the PR: what was removed, where its information lives now.

## Tracks

### 1. UX: the main screens

1. Top bar: one word per control; no label before a value the control already shows.
2. Layers panel: a row is a name and a switch; region tags, counts and instructions move into
   the dataset's details. Names are never truncated by secondary labels.
3. Context panel, Dashboard tab: no instruction paragraphs ("Pick an area...", "Figures for
   the datasets..."); empty states are a single action, not a sentence.
4. Cards: a title, the figure, its unit and as-of; method and source lines collapse into the
   card's sources disclosure when they are longer than one line.
5. Ask tab, the coverage explorer, the catalogue, the Maps view: the same pass.

### 2. DX: the code

1. One way to do each thing: remove duplicated helpers, dead exports and unused props
   (`npx knip` or `tsc --noUnusedLocals`, ruff `F401`, `F841`).
2. Name modules for what they hold; split files over about 1,500 lines only where a clear seam
   exists (no churn for its own sake).
3. `scripts/wave9.py` readers: one table in the module docstring naming every kind and custom
   reader and its options.

### 3. AX: what agents read

1. Tool descriptions: one sentence on what the tool returns, one on when to use it; no marketing.
2. The catalogue (`agent/catalog/*.yaml`): titles say what the data is, units always present.
3. `CLAUDE.md` and the vault index: shortest path to the right file.

## Done when

- Every main screen passes the rule (no tagline, no helper paragraph, no secondary label that
  could go), with before/after screenshots in the PR description's notes (described, not
  committed).
- Every figure still names its source within one click.
- All checks green; no figure, layer or route lost (the screenshots and tests show it).
