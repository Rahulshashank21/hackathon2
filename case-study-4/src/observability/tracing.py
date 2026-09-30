"""
Arize Phoenix instrumentation (mandated). Wires a real OpenTelemetry
tracer provider, instrumented via openinference-instrumentation-langchain,
so every LangGraph node and LLM/tool call is traced automatically —
called from src/pipeline.py's run entry point, not just imported.

Deliberately does NOT import the `arize-phoenix` package itself: this
process sends spans over plain OTLP/HTTP to a Phoenix collector run
from the separate .venv-phoenix environment (see README "Why two
virtual environments" — arize-phoenix's fastmcp dependency needs
mcp>=2, which conflicts with this app's own MCP server/client stack).
If no collector is listening, span export fails silently in the
background (BatchSpanProcessor) rather than crashing the agent
(NFR-04 graceful degradation) — the agent runs identically with or
without Phoenix up.
"""

from __future__ import annotations

import logging

from src.config import load_config

logger = logging.getLogger("copilot.observability")

_instrumented = False


def init_tracing() -> bool:
    """Idempotent. Returns True if instrumentation was (already) applied."""
    global _instrumented
    if _instrumented:
        return True

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from openinference.semconv.resource import ResourceAttributes
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        cfg = load_config()["observability"]
        resource = Resource.create({ResourceAttributes.PROJECT_NAME: cfg["project_name"]})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=cfg["otlp_endpoint"], timeout=2)
        logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(logging.CRITICAL)
        provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=500))

        LangChainInstrumentor().instrument(tracer_provider=provider)
        _instrumented = True
        logger.info("OpenInference/OTel tracing initialized -> %s", cfg["otlp_endpoint"])
        return True
    except Exception as exc:  # noqa: BLE001 - tracing must never break the agent
        logger.warning("Tracing initialization failed (%s); continuing untraced.", exc)
        return False
