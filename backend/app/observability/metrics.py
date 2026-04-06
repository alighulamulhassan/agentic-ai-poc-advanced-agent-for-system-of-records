"""
Agent Metrics — Prometheus/CloudWatch-compatible counters and histograms.

Tracks:
  - agent_requests_total (counter, by status)
  - agent_tool_calls_total (counter, by tool_name, status)
  - agent_tool_duration_seconds (histogram, by tool_name)
  - agent_llm_tokens_total (counter, by model)
  - agent_risk_score (histogram)
  - agent_pii_detections_total (counter, by risk_level)
  - agent_hitl_requests_total (counter, by status)

Backends (select via METRICS_BACKEND env var):
  - "prometheus" — exposes /metrics endpoint (default for containers)
  - "cloudwatch" — EMF structured logs (AWS native)
  - "memory"     — in-process store for testing

Session for audience:
  - Knowledge fuel: RED method (Rate, Errors, Duration), SLI/SLO/SLA
  - Lab: create a CloudWatch dashboard with the agent metrics and set
        alarms for error rate > 5% and p99 latency > 3s
"""
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

METRICS_BACKEND = os.getenv("METRICS_BACKEND", "memory")
CLOUDWATCH_NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "AgentPOC")


# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------
@dataclass
class Counter:
    name: str
    help: str
    labels: List[str] = field(default_factory=list)
    _values: Dict = field(default_factory=lambda: defaultdict(int))

    def inc(self, amount: int = 1, **label_values) -> None:
        key = tuple(sorted(label_values.items()))
        self._values[key] += amount

    def get(self, **label_values) -> int:
        key = tuple(sorted(label_values.items()))
        return self._values[key]

    def total(self) -> int:
        return sum(self._values.values())


@dataclass
class Histogram:
    name: str
    help: str
    buckets: List[float] = field(default_factory=lambda: [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10])
    _observations: List[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self._observations.append(value)

    def p50(self) -> float:
        return self._percentile(50)

    def p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: float) -> float:
        if not self._observations:
            return 0.0
        sorted_obs = sorted(self._observations)
        idx = int(len(sorted_obs) * p / 100)
        return sorted_obs[min(idx, len(sorted_obs) - 1)]

    def avg(self) -> float:
        if not self._observations:
            return 0.0
        return sum(self._observations) / len(self._observations)


# ---------------------------------------------------------------------------
# Agent Metrics
# ---------------------------------------------------------------------------
class AgentMetrics:
    """
    Central metrics registry for the agent system.

    Usage:
        metrics = get_metrics()
        metrics.requests_total.inc(status="success")
        metrics.tool_duration.observe(0.234)
        with metrics.time_tool("process_refund") as timer:
            result = execute_refund(...)
    """

    def __init__(self):
        # Counters
        self.requests_total = Counter(
            "agent_requests_total",
            "Total agent request count",
            labels=["status"],
        )
        self.tool_calls_total = Counter(
            "agent_tool_calls_total",
            "Total tool call count by tool and status",
            labels=["tool_name", "status"],
        )
        self.llm_tokens_total = Counter(
            "agent_llm_tokens_total",
            "Total LLM tokens consumed",
            labels=["model", "type"],
        )
        self.pii_detections_total = Counter(
            "agent_pii_detections_total",
            "PII detection count by risk level",
            labels=["risk_level"],
        )
        self.injection_detections_total = Counter(
            "agent_injection_detections_total",
            "Injection attempt detection count",
            labels=["blocked"],
        )
        self.hitl_requests_total = Counter(
            "agent_hitl_requests_total",
            "HITL approval request count by outcome",
            labels=["outcome"],
        )
        self.policy_evaluations_total = Counter(
            "agent_policy_evaluations_total",
            "Policy evaluation count by action",
            labels=["action"],
        )

        # Histograms
        self.request_duration = Histogram(
            "agent_request_duration_seconds",
            "End-to-end request duration",
        )
        self.tool_duration = Histogram(
            "agent_tool_duration_seconds",
            "Individual tool execution duration",
        )
        self.risk_score_distribution = Histogram(
            "agent_risk_score",
            "Distribution of risk scores",
            buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        self.llm_latency = Histogram(
            "agent_llm_latency_seconds",
            "LLM inference latency",
        )

        self._backend = self._init_backend()

    def _init_backend(self):
        """Initialise the metrics export backend."""
        if METRICS_BACKEND == "prometheus":
            return self._init_prometheus()
        if METRICS_BACKEND == "cloudwatch":
            return "cloudwatch"
        return "memory"

    def _init_prometheus(self):
        try:
            import prometheus_client  # type: ignore
            logger.info("Prometheus metrics backend initialised")
            return "prometheus"
        except ImportError:
            logger.info("prometheus_client not installed — using memory backend")
            return "memory"

    def record_span(self, span) -> None:
        """Called by TelemetryContext to update metrics from a span."""
        elapsed = time.time() - span.start_time
        if span.category == "tool":
            self.tool_calls_total.inc(
                tool_name=span.name.split(".")[-1],
                status=span.status,
            )
            self.tool_duration.observe(elapsed)
        elif span.category == "request":
            self.requests_total.inc(status=span.status)
            self.request_duration.observe(elapsed)
        elif span.category == "llm":
            self.llm_latency.observe(elapsed)

    class _Timer:
        """Context manager for timing a block."""
        def __init__(self, histogram: Histogram):
            self._h = histogram
            self._start = None

        def __enter__(self):
            self._start = time.time()
            return self

        def __exit__(self, *_):
            self._h.observe(time.time() - self._start)

    def time_tool(self, tool_name: str = "unknown") -> "_Timer":
        """Context manager that times a tool call and records the histogram."""
        return self._Timer(self.tool_duration)

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time metrics snapshot (useful for /metrics endpoint)."""
        return {
            "requests": {
                "total": self.requests_total.total(),
                "p50_duration_s": self.request_duration.p50(),
                "p99_duration_s": self.request_duration.p99(),
            },
            "tools": {
                "total_calls": self.tool_calls_total.total(),
                "p50_duration_s": self.tool_duration.p50(),
                "p99_duration_s": self.tool_duration.p99(),
                "avg_duration_s": self.tool_duration.avg(),
            },
            "security": {
                "pii_detections": self.pii_detections_total.total(),
                "injection_detections": self.injection_detections_total.total(),
                "avg_risk_score": self.risk_score_distribution.avg(),
            },
            "hitl": {
                "total_requests": self.hitl_requests_total.total(),
            },
            "llm": {
                "total_tokens": self.llm_tokens_total.total(),
                "p99_latency_s": self.llm_latency.p99(),
            },
        }

    def emit_cloudwatch_emf(self) -> Dict:
        """
        Emit metrics in CloudWatch Embedded Metrics Format (EMF).
        This JSON, when logged to stdout in Lambda/ECS, is automatically
        parsed by CloudWatch as custom metrics — no SDK needed.

        TODO (Lab):
            Call this method at the end of each request and log the output.
            CloudWatch will auto-extract the metrics into a dashboard.
            See: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html
        """
        snap = self.snapshot()
        emf = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": CLOUDWATCH_NAMESPACE,
                        "Dimensions": [["Environment"]],
                        "Metrics": [
                            {"Name": "RequestCount", "Unit": "Count"},
                            {"Name": "ToolCallCount", "Unit": "Count"},
                            {"Name": "PIIDetectionCount", "Unit": "Count"},
                            {"Name": "P99RequestDuration", "Unit": "Seconds"},
                            {"Name": "AvgRiskScore", "Unit": "None"},
                        ],
                    }
                ],
            },
            "Environment": os.getenv("ENVIRONMENT", "development"),
            "RequestCount": snap["requests"]["total"],
            "ToolCallCount": snap["tools"]["total_calls"],
            "PIIDetectionCount": snap["security"]["pii_detections"],
            "P99RequestDuration": snap["requests"]["p99_duration_s"],
            "AvgRiskScore": snap["security"]["avg_risk_score"],
        }
        return emf


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_metrics_instance: Optional[AgentMetrics] = None


def get_metrics() -> AgentMetrics:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = AgentMetrics()
    return _metrics_instance
