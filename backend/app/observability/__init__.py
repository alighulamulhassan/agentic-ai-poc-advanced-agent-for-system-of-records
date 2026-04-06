"""
Observability layer for the enterprise agent.

Provides:
  - Telemetry decorator: wrap any async function with trace + metrics
  - Decision logger: structured log of every agent decision
  - Metrics: Prometheus/CloudWatch-compatible counters and histograms
  - Tracer: OpenTelemetry distributed tracing (X-Ray compatible)
"""
from app.observability.telemetry import instrument, TelemetryContext
from app.observability.decision_logger import DecisionLogger, get_decision_logger, DecisionLog
from app.observability.metrics import AgentMetrics, get_metrics
from app.observability.tracer import Tracer, get_tracer

__all__ = [
    "instrument", "TelemetryContext",
    "DecisionLogger", "get_decision_logger", "DecisionLog",
    "AgentMetrics", "get_metrics",
    "Tracer", "get_tracer",
]
