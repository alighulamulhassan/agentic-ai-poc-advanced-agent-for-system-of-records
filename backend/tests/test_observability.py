"""
Tests for the Observability Layer.

Covers:
  - Telemetry decorator: span creation, error recording
  - Decision logger: start, add tool call, commit, JSON output
  - Metrics: counter increments, histogram observations, snapshot
  - Tracer: context creation, W3C header propagation

Run: pytest tests/test_observability.py -v
"""
import pytest
import asyncio
import json
from unittest.mock import patch


# ============================================================
# Telemetry Decorator
# ============================================================
class TestTelemetry:

    @pytest.mark.asyncio
    async def test_instrument_decorator_runs_function(self):
        from app.observability.telemetry import instrument

        @instrument(name="test_fn", category="test")
        async def my_fn(x: int) -> int:
            return x * 2

        result = await my_fn(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_instrument_propagates_exception(self):
        from app.observability.telemetry import instrument

        @instrument(name="failing_fn", category="test")
        async def bad_fn():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await bad_fn()

    @pytest.mark.asyncio
    async def test_telemetry_context_records_attributes(self):
        from app.observability.telemetry import TelemetryContext

        async with TelemetryContext("test_span", category="tool") as ctx:
            ctx.set_attribute("order_id", "ORD-1")
            ctx.set_attribute("tool", "lookup_order")

        assert ctx.attributes["order_id"] == "ORD-1"
        assert ctx.attributes["tool"] == "lookup_order"

    @pytest.mark.asyncio
    async def test_telemetry_context_records_error(self):
        from app.observability.telemetry import TelemetryContext

        ctx_ref = None
        try:
            async with TelemetryContext("error_span") as ctx:
                ctx_ref = ctx
                raise RuntimeError("oops")
        except RuntimeError:
            pass

        assert ctx_ref.status == "error"
        assert "RuntimeError" in ctx_ref.error

    def test_span_to_log_dict(self):
        from app.observability.telemetry import SpanContext
        import time

        span = SpanContext(
            name="test",
            category="tool",
            trace_id="abc123",
            span_id="def456",
            start_time=time.time() - 0.5,
        )
        span.set_attribute("key", "value")
        d = span.to_log_dict()

        assert d["name"] == "test"
        assert d["trace_id"] == "abc123"
        assert d["key"] == "value"
        assert d["duration_ms"] >= 500


# ============================================================
# Decision Logger
# ============================================================
class TestDecisionLogger:

    def test_start_decision_creates_log(self):
        from app.observability.decision_logger import DecisionLogger
        logger = DecisionLogger()
        log = logger.start_decision("conv-001", "Cancel my order")
        assert log.decision_id.startswith("DEC-")
        assert log.conversation_id == "conv-001"
        assert log.user_message == "Cancel my order"

    def test_add_tool_call(self):
        from app.observability.decision_logger import DecisionLogger, ToolCallRecord
        logger = DecisionLogger()
        log = logger.start_decision("conv-001", "test")
        log.add_tool_call(ToolCallRecord(
            tool_name="lookup_order",
            args={"order_id": "ORD-1"},
            result={"status": "processing"},
            duration_ms=150.0,
            success=True,
        ))
        assert len(log.tool_calls) == 1
        assert log.tool_calls[0].tool_name == "lookup_order"

    def test_to_json_produces_valid_json(self):
        from app.observability.decision_logger import DecisionLogger, ToolCallRecord
        logger = DecisionLogger()
        log = logger.start_decision("conv-002", "What is my order status?")
        log.final_response = "Your order is processing."
        log.total_duration_ms = 250.0
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed["conversation_id"] == "conv-002"
        assert parsed["final_response"] == "Your order is processing."

    def test_commit_removes_from_active(self):
        from app.observability.decision_logger import DecisionLogger
        logger = DecisionLogger()
        log = logger.start_decision("conv-003", "test")
        assert logger.get_active(log.decision_id) is not None
        logger.commit(log)
        assert logger.get_active(log.decision_id) is None

    def test_user_message_truncated_to_500(self):
        from app.observability.decision_logger import DecisionLogger
        logger = DecisionLogger()
        long_msg = "x" * 1000
        log = logger.start_decision("conv-004", long_msg)
        assert len(log.user_message) == 500


# ============================================================
# Metrics
# ============================================================
class TestMetrics:

    def test_counter_increments(self):
        from app.observability.metrics import Counter
        c = Counter("test_counter", "test")
        c.inc(1, status="success")
        c.inc(2, status="success")
        assert c.get(status="success") == 3

    def test_counter_total(self):
        from app.observability.metrics import Counter
        c = Counter("test_total", "test")
        c.inc(1, status="success")
        c.inc(1, status="error")
        assert c.total() == 2

    def test_histogram_percentiles(self):
        from app.observability.metrics import Histogram
        h = Histogram("test_hist", "test")
        for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            h.observe(v)
        assert 0.4 <= h.p50() <= 0.6
        assert h.p99() >= 0.9
        assert 0.4 <= h.avg() <= 0.6

    def test_agent_metrics_snapshot(self):
        from app.observability.metrics import AgentMetrics
        metrics = AgentMetrics()
        metrics.requests_total.inc(status="success")
        metrics.tool_calls_total.inc(tool_name="lookup_order", status="success")
        snapshot = metrics.snapshot()
        assert snapshot["requests"]["total"] == 1
        assert snapshot["tools"]["total_calls"] == 1

    def test_emf_format(self):
        from app.observability.metrics import AgentMetrics
        metrics = AgentMetrics()
        emf = metrics.emit_cloudwatch_emf()
        assert "_aws" in emf
        assert "CloudWatchMetrics" in emf["_aws"]
        assert "RequestCount" in emf


# ============================================================
# Tracer
# ============================================================
class TestTracer:

    def test_new_context_has_ids(self):
        from app.observability.tracer import TraceContext
        ctx = TraceContext.new()
        assert len(ctx.trace_id) > 10
        assert len(ctx.span_id) > 5

    def test_child_span_inherits_trace_id(self):
        from app.observability.tracer import TraceContext
        root = TraceContext.new()
        child = root.child_span()
        assert child.trace_id == root.trace_id
        assert child.parent_span_id == root.span_id
        assert child.span_id != root.span_id

    def test_w3c_header_roundtrip(self):
        from app.observability.tracer import TraceContext
        ctx = TraceContext.new()
        header = ctx.to_w3c_header()
        assert header.startswith("00-")
        parsed = TraceContext.from_w3c_header(header)
        assert parsed.trace_id == ctx.trace_id

    def test_extract_from_w3c_headers(self):
        from app.observability.tracer import Tracer
        tracer = Tracer()
        trace_id = "a" * 32
        span_id = "b" * 16
        header = f"00-{trace_id}-{span_id}-01"
        ctx = tracer.extract_from_headers({"traceparent": header})
        assert ctx is not None
        assert ctx.trace_id == trace_id

    def test_span_context_manager(self):
        from app.observability.tracer import Tracer
        tracer = Tracer()
        spans = []
        with tracer.start_span("test_span") as span:
            span.set_attribute("key", "value")
            spans.append(span)
        assert spans[0].attributes["key"] == "value"
        assert spans[0].status == "ok"

    def test_span_records_exception(self):
        from app.observability.tracer import Tracer
        tracer = Tracer()
        span_ref = [None]
        try:
            with tracer.start_span("failing") as span:
                span_ref[0] = span
                raise ValueError("boom")
        except ValueError:
            pass
        assert span_ref[0].status == "error"
