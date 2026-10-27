---
name: atlas-vault
description: The project's knowledge vault (vault/, Obsidian notes) that replaces re-reading the repository at the start of a task. Use at the start of every task in this repository (read vault/index.md first, then only the notes and files the task needs) and at the end of every task (update the notes the work changed, append to vault/log.md). Also use when asked where something lives, how a part works, or what was decided.
---

# InfraAtlas vault

`vault/` is a compiled map of this repository: what each part does, where it lives, what was
decided and why, what breaks. It is kept current by every session, so a session reads a few
short notes instead of scanning the code. Notes are Obsidian Flavored Markdown
(`.claude/skills/obsidian-markdown/SKILL.md`): YAML properties, `[[wikilinks]]` between notes,
callouts for warnings. The owner can open `vault/` in Obsidian to browse it as a graph.

## At the start of a task

1. Read `vault/index.md` (one line per note).
2. Read only the notes the task touches, then only the files those notes point to.
3. Trust a note's file paths and facts as of its `updated` date; when the code disagrees, the
   code wins and the note gets fixed at the end of the task.
4. Do not read whole directories to orient yourself when a note covers them.

## At the end of a task (before the commit or the pull request)

1. For each part the work changed, update its note: what it does now, file paths, entry points,
   the decisions taken and why, new gotchas. Set `updated: YYYY-MM-DD`.
2. A new part (module, workflow, dataset family, service) gets a new note and a line in
   `vault/index.md`.
3. A decision the owner made goes to `vault/decisions.md` (dated, one paragraph: decision, why,
   what it rules out).
4. Append one entry to `vault/log.md`: date, branch or commit, two or three lines on what changed,
   the notes touched.
5. Lint: every `[[link]]` resolves to a note; every note is in the index; no note over ~150 lines
   (split it); no secrets, keys or personal data.
6. Commit the vault changes with the work they describe.

## Note format

```markdown
---
title: Map rendering
tags: [frontend, map]
updated: 2026-10-27
paths: [frontend/src/map/MapCanvas.tsx, frontend/src/map/build.ts]
---

# Map rendering

One paragraph: what it is and how it fits. Link the neighbours: [[state-and-datasets]].

## Where
- `frontend/src/map/build.ts`: every deck.gl layer; `buildLayers(frame)`.

## How it works
Short bullets, the facts a newcomer needs.

> [!warning] Gotcha
> What breaks and why.
```

- One note per part; facts, not narration; file paths in backticks; link, do not repeat.
- The vault describes; `docs/` holds the owner-facing documents (DATA_SOURCES, AGENT, briefs).
  Link to them instead of copying them.
- Notes are written in normal English (the caveman style is for chat replies only).
