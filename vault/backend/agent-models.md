---
title: Agent models and evals
tags: [backend, agent]
updated: 2026-10-29
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

## Tested providers (2026-10-29, local)
- **Groq** (`uv sync --extra groq`, `GROQ_API_KEY`): `groq-gpt-oss-120b` (analyst) and
  `groq-gpt-oss-20b` (router, cartographer) in the registry ($0.15/$0.60 and $0.075/$0.30 per
  million, console.groq.com/docs/models). Tool calls and streaming work; a map question ran end to
  end (grounding 10/10, $0.0052). Llama 3.3 70B is no longer served to this key.
- **Bedrock** (`uv sync --extra aws`, `BEDROCK_API_KEY` = an Amazon Bedrock API key, set as
  `AWS_BEARER_TOKEN_BEDROCK` for boto3): the key authenticates (model lists), but every model
  answers `ThrottlingException`: the account's quotas are 0 (`probes/probe_bedrock.py`).

> [!warning] Groq free tier
> 8,000 tokens per minute per model. One analyst call is ~4,300 tokens (system prompt ~3,600,
> tool schemas ~670) plus tool results, so a question waits on HTTP 429 retries (150 s for a map
> question). Groq's Developer plan (250K tokens per minute) removes the wait.
