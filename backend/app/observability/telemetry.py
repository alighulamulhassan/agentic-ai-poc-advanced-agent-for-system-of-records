"""
Telemetry Decorator — wrap any async function with tracing, metrics, and logging.

This is the primary observability primitive. Applying @instrument to an
agent function captures:
  - Execution time (histogram)
  - Success/failure counts (counter)
  - Input/output metadata (structured log)
  - Distributed trace span (OpenTelemetry)

In production this integrates with:
  - AWS X-Ray (via opentelemetry-sdk-extension-aws-xray)
  - Honeycomb (via opentelemetry-exporter-otlp)
  - CloudWatch Embedded Metrics Format (EMF)

Session for audience:
  - Knowledge fuel: OpenTelemetry architecture, spans, context propagation
  - Lab: add the Honeycomb exporter and visualise agent traces in the UI

Usage:
    @instrument(name="process_refund_tool", category="tool")
    async def process_refund(order_id, amount, reason):
        ...

    # Or as a context manager:
    async with TelemetryContext("validate_input", category="security") as ctx:
        result = validate(text)
        ctx.set_attribute("pii_found", result.pii_found)
"""
import functools
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "")
SERVICE_NAME = os.getenv("SERVICE_NAME", "agent-poc")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# ---------------------------------------------------------------------------
# Span / context
# ---------------------------------------------------------------------------
@dataclass
class SpanContext:
    name: str
    category: str
    trace_id: str
    span_id: str
    start_time: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_error(self, exc: Exception) -> None:
        self.status = "error"
        self.error = f"{type(exc).__name__}: {exc}"

    def to_log_dict(self) -> Dict:
        elapsed = time.time() - self.start_time
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "duration_ms": round(elapsed * 1000, 2),
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
            **self.attributes,
            **({"error": self.error} if self.error else {}),
        }


# ---------------------------------------------------------------------------
# OpenTelemetry integration (graceful degradation if not installed)
# ---------------------------------------------------------------------------
_otel_tracer = None


def _get_otel_tracer():
    global _otel_tracer
    if _otel_tracer is not None:
        return _otel_tracer

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()

        if OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _otel_tracer = trace.get_tracer(SERVICE_NAME)
        logger.info(f"OpenTelemetry tracer initialised | endpoint={OTLP_ENDPOINT or 'none'}")
    except ImportError:
        logger.debug("opentelemetry-sdk not installed — trace spans are local only")
        _otel_tracer = None

    return _otel_tracer


# ---------------------------------------------------------------------------
# TelemetryContext async context manager
# ---------------------------------------------------------------------------
class TelemetryContext:
    """
    Async context manager that records a span.

    Usage:
        async with TelemetryContext("my_operation", category="tool") as ctx:
            result = do_work()
            ctx.set_attribute("result_count", len(result))
    """

    def __init__(self, name: str, category: str = "general", parent_trace_id: str = None):
        self.span = SpanContext(
            name=name,
            category=category,
            trace_id=parent_trace_id or str(uuid.uuid4()).replace("-", ""),
            span_id=str(uuid.uuid4()).replace("-", "")[:16],
        )
        self._otel_span = None
        self._otel_ctx = None

    async def __aenter__(self) -> SpanContext:
        # Try to start an OTel span
        tracer = _get_otel_tracer()
        if tracer:
            try:
                self._otel_ctx = tracer.start_as_current_span(self.span.name)
                self._otel_span = self._otel_ctx.__enter__()
            except Exception:
                pass
        return self.span

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.span.record_error(exc_val)

        log_dict = self.span.to_log_dict()

        if self.span.status == "error":
            logger.error("SPAN | " + _format_structured(log_dict))
        else:
            logger.info("SPAN | " + _format_structured(log_dict))

        # Update metrics
        try:
            from app.observability.metrics import get_metrics
            metrics = get_metrics()
            metrics.record_span(self.span)
        except Exception:
            pass

        # Close OTel span
        if self._otel_span and self._otel_ctx:
            try:
                if exc_val:
                    self._otel_span.record_exception(exc_val)
                self._otel_ctx.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass

        return False  # don't suppress exceptions


def _format_structured(d: Dict) -> str:
    """Format a dict as key=value pairs for structured log parsing."""
    return " ".join(f"{k}={v!r}" for k, v in d.items())


# ---------------------------------------------------------------------------
# @instrument decorator
# ---------------------------------------------------------------------------
def instrument(
    name: Optional[str] = None,
    category: str = "general",
    log_args: bool = False,
    log_result: bool = False,
):
    """
    Decorator that instruments an async function with telemetry.

    Args:
        name: Span name (defaults to function name)
        category: Logical category (tool | security | guardrail | llm | rag)
        log_args: Whether to log function arguments (careful with PII!)
        log_result: Whether to log return value

    Example:
        @instrument(name="execute_refund", category="tool", log_args=False)
        async def process_refund(order_id, amount, reason):
            ...
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with TelemetryContext(span_name, category=category) as ctx:
                if log_args:
                    # Only log kwargs for safety (skip positional which may have self/cls)
                    ctx.set_attribute("kwargs", str(kwargs)[:200])

                try:
                    result = await func(*args, **kwargs)
                    if log_result:
                        ctx.set_attribute("result_preview", str(result)[:200])
                    return result
                except Exception as exc:
                    ctx.record_error(exc)
                    raise

        return wrapper
    return decorator
