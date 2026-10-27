"""OpenTelemetry: one tracer, exporters chosen by the environment.

- OTLP over HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` (any collector), or to Langfuse's OTLP
  endpoint (`<LANGFUSE_HOST>/api/public/otel`, basic auth with the Langfuse keys) when its keys
  are set and no other endpoint is given;
- the console exporter when `OTEL_CONSOLE=true` (development).

Spans follow the GenAI semantic conventions for model calls (`gen_ai.system`,
`gen_ai.request.model`, `gen_ai.usage.input_tokens`, ...); see agent/graph.py and tools/.
"""

from __future__ import annotations

import base64
import contextlib
from collections.abc import Iterator
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_provider: TracerProvider | None = None
memory_exporter: InMemorySpanExporter | None = None


def setup_tracing(settings: Any, *, in_memory: bool = False) -> TracerProvider:
    """Install the tracer provider once; `in_memory` keeps spans for tests and evals."""
    global _provider, memory_exporter
    if _provider is not None:
        return _provider
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "infraatlas-backend",
                "service.version": settings.version,
                "deployment.environment": settings.environment,
            }
        )
    )
    exporter: SpanExporter | None = None
    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    elif settings.langfuse_configured:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}"},
        )
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    if settings.otel_console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    if in_memory:
        memory_exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def tracer() -> trace.Tracer:
    return trace.get_tracer("infraatlas")


@contextlib.contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[trace.Span]:
    with tracer().start_as_current_span(name) as sp:
        for k, v in (attributes or {}).items():
            if v is not None:
                sp.set_attribute(k, v)
        yield sp


def current_trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.trace_id else ""


def flush() -> None:
    if _provider is not None:
        _provider.force_flush(timeout_millis=3000)
