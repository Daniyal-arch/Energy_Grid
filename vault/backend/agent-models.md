---
title: Agent models and evals
tags: [backend, agent]
updated: 2026-10-27
paths: [agent/models.yaml, backend/agent/models.py, backend/agent/fake.py, backend/evals/, agent/evals/]
---

# Agent models and evals

Any chat model by configuration for [[agent-graph]].

## Where
- `agent/models.yaml`: id, `provider:model`, prices per million (input, output, cache read,
  cache write) with the pricing page and date, context, tool calling, caching kind, effort.
- `backend/agent/models.py`: `Registry`, `chat_model()` (`init_chat_model`; Anthropic effort via
  `output_config`, no sampling parameters), `system_message()` (cache breakpoint),
  `stop_reason()` (refusal/length across providers), `text_of()`.
- `backend/agent/fake.py`: scripted model (router/analyst/cartographer told apart by the system
  prompt; `script=[...]` for tests; `FAKE_STREAM_DELAY_S` for the streaming probe).
- `AGENT_MODEL`, `AGENT_MODEL_FAST`, `AGENT_MODELS_ALLOWED` (a request's `model` must be listed).
- Evals: `backend/scripts/build_eval_questions.py` -> `agent/evals/questions.yaml` (catalogue
  examples, app-table questions, map questions); `backend/evals/run.py` + `scorers.py`;
  workflow `agent-evals.yml`.

> [!info] Not measured yet
> No model key in the 2026-10-27 session: real cost and latency per model come from the first
> eval run with `ANTHROPIC_API_KEY`.
