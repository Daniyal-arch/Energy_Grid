"""Langfuse: the LangChain callback handler on every graph run when LANGFUSE_* is set.

Session id = the browser's conversation id; tags: model, route, version. Scores (grounding,
eval results) are attached to the trace by id.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)


def _env(settings: Any) -> None:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key or "")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key or "")
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


def callbacks(settings: Any, trace_id: str) -> list[Any]:
    if not settings.langfuse_configured:
        return []
    try:
        _env(settings)
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler(trace_context={"trace_id": trace_id})]
    except Exception:
        log.exception("langfuse handler not created")
        return []


def run_metadata(conversation_id: str | None, tags: list[str]) -> dict[str, Any]:
    md: dict[str, Any] = {"langfuse_tags": tags}
    if conversation_id:
        md["langfuse_session_id"] = conversation_id
    return md


def score(settings: Any, trace_id: str, name: str, value: float, comment: str = "") -> None:
    if not settings.langfuse_configured:
        return
    try:
        _env(settings)
        from langfuse import get_client

        get_client().create_score(trace_id=trace_id, name=name, value=value, comment=comment)
    except Exception:
        log.exception("langfuse score not sent")


def flush(settings: Any) -> None:
    if not settings.langfuse_configured:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        log.exception("langfuse flush failed")
