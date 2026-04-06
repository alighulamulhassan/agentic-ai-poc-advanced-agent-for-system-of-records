"""
Distributed Tracer — OpenTelemetry trace context management.

Provides a lightweight wrapper around OpenTelemetry that:
  - Propagates trace context across async boundaries
  - Integrates with AWS X-Ray (via OTLP exporter or X-Ray SDK)
  - Supports Honeycomb, Jaeger, and Zipkin via OTLP
  - Gracefully degrades to log-based tracing when OTel is not available

Trace propagation for the agent pipeline:
  HTTP request → [trace_id generated]
    → Security checks [child span]
    → LLM call [child span]
    → Tool execution [child span per tool]
    → Policy evaluation [child span]
    → Response generation [child span]

Session for audience:
  - Knowledge fuel: distributed tracing concepts, W3C trace context spec
  - Lab: instrument the LLM call with a span and visualise in Honeycomb
        to see token count, latency, and model breakdown per request
"""
import logging
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "")
SERVICE_NAME = os.getenv("SERVICE_NAME", "agent-poc")
XRAY_ENABLED = os.getenv("XRAY_ENABLED", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Trace context (propagated through the call stack)
# ---------------------------------------------------------------------------
@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def new(cls) -> "TraceContext":
        return cls(
            trace_id=str(uuid.uuid4()).replace("-", ""),
            span_id=str(uuid.uuid4()).replace("-", "")[:16],
        )

    def child_span(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()).replace("-", "")[:16],
            parent_span_id=self.span_id,
            baggage=dict(self.baggage),
        )

    def to_w3c_header(self) -> str:
        """W3C traceparent header format for propagation."""
        return f"00-{self.trace_id}-{self.span_id}-01"

    @classmethod
    def from_w3c_header(cls, header: str) -> Optional["TraceContext"]:
        """Parse a W3C traceparent header."""
        try:
            parts = header.split("-")
            if len(parts) >= 3:
                return cls(trace_id=parts[1], span_id=parts[2])
        except Exception:
            pass
        return None

    def to_xray_header(self) -> str:
        """
        AWS X-Ray trace header format.
        Format: Root=1-{epoch_hex}-{random_96bit};Parent={span_id};Sampled=1
        """
        import time
        epoch_hex = format(int(time.time()), "x")
        random_part = self.trace_id[8:32]  # 96 bits from trace_id
        return f"Root=1-{epoch_hex}-{random_part};Parent={self.span_id};Sampled=1"


# ---------------------------------------------------------------------------
# Span record
# ---------------------------------------------------------------------------
@dataclass
class Span:
    name: str
    context: TraceContext
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: list = field(default_factory=list)
    status: str = "ok"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Dict = None) -> None:
        self.events.append({"name": name, "attributes": attributes or {}})

    def record_exception(self, exc: Exception) -> None:
        self.status = "error"
        self.add_event("exception", {
            "exception.type": type(exc).__name__,
            "exception.message": str(exc),
        })


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------
class Tracer:
    """
    Lightweight distributed tracer with OTel/X-Ray support.

    Usage:
        tracer = get_tracer()

        with tracer.start_span("llm_call", parent_ctx=request_ctx) as span:
            span.set_attribute("model", "llama3.2")
            response = await llm.chat(messages)
            span.set_attribute("response_tokens", count_tokens(response))
    """

    def __init__(self):
        self._otel_tracer = self._init_otel()

    def _init_otel(self):
        if not OTLP_ENDPOINT and not XRAY_ENABLED:
            return None
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": SERVICE_NAME})
            provider = TracerProvider(resource=resource)

            if OTLP_ENDPOINT:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info(f"OTel OTLP exporter configured: {OTLP_ENDPOINT}")

            if XRAY_ENABLED:
                try:
                    from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    # X-Ray via OTLP collector
                    xray_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
                    provider.add_span_processor(BatchSpanProcessor(xray_exporter))
                    logger.info("AWS X-Ray tracing configured via OTel collector")
                except ImportError:
                    logger.warning("aws-opentelemetry-distro not installed — X-Ray disabled")

            trace.set_tracer_provider(provider)
            return trace.get_tracer(SERVICE_NAME)

        except ImportError:
            logger.debug("opentelemetry-sdk not installed — using log-based tracing")
            return None

    @contextmanager
    def start_span(
        self,
        name: str,
        parent_ctx: Optional[TraceContext] = None,
        attributes: Optional[Dict] = None,
    ) -> Generator[Span, None, None]:
        """
        Start a new span as a context manager.

        Args:
            name: Span name (e.g. "llm_call", "tool:process_refund")
            parent_ctx: Parent TraceContext for correlation
            attributes: Initial span attributes

        Yields:
            Span object — call .set_attribute() to annotate

        TODO (Lab):
            Add Honeycomb-specific attributes using the OTel semantic conventions:
              span.set_attribute("gen_ai.system", "ollama")
              span.set_attribute("gen_ai.request.model", model_name)
              span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
              span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
            These are parsed by Honeycomb's GenAI semantic conventions dashboard.
        """
        ctx = parent_ctx.child_span() if parent_ctx else TraceContext.new()
        span = Span(name=name, context=ctx, attributes=attributes or {})

        # Try OTel native span
        otel_span = None
        if self._otel_tracer:
            try:
                otel_ctx = self._otel_tracer.start_as_current_span(name)
                otel_span = otel_ctx.__enter__()
                if attributes:
                    for k, v in attributes.items():
                        otel_span.set_attribute(k, str(v))
            except Exception:
                pass

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            if otel_span:
                try:
                    otel_span.record_exception(exc)
                except Exception:
                    pass
            raise
        finally:
            # Log span to structured logs (always — OTel is additive)
            log_entry = {
                "trace_id": ctx.trace_id,
                "span_id": ctx.span_id,
                "parent_span_id": ctx.parent_span_id,
                "name": name,
                "status": span.status,
                **span.attributes,
            }
            if span.status == "error":
                logger.error("TRACE | " + str(log_entry))
            else:
                logger.debug("TRACE | " + str(log_entry))

            if otel_span:
                try:
                    otel_span.__exit__(None, None, None)
                except Exception:
                    pass

    def new_context(self) -> TraceContext:
        """Create a fresh root trace context (e.g. at request ingress)."""
        return TraceContext.new()

    def extract_from_headers(self, headers: Dict[str, str]) -> Optional[TraceContext]:
        """Extract trace context from HTTP request headers."""
        # W3C traceparent
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        if traceparent:
            return TraceContext.from_w3c_header(traceparent)

        # X-Ray
        xray = headers.get("X-Amzn-Trace-Id") or headers.get("x-amzn-trace-id")
        if xray:
            # Parse Root=...; Parent=...; Sampled=...
            parts = dict(kv.split("=") for kv in xray.split(";") if "=" in kv)
            root = parts.get("Root", "").replace("1-", "").replace("-", "")
            parent = parts.get("Parent", "")
            if root and parent:
                return TraceContext(trace_id=root, span_id=parent)

        return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_tracer_instance: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = Tracer()
    return _tracer_instance
