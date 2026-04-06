"""
Decision Logger — structured log of every agent decision.

Records the complete chain from user input → LLM reasoning → tool calls →
results → final response. This enables:
  - Post-hoc audit ("why did the agent issue that refund?")
  - Debugging ("the agent misunderstood the intent because...")
  - Compliance ("prove the agent had human approval for this action")
  - Training data collection (for fine-tuning)

Log format: JSON Lines (one JSON object per line) — compatible with
CloudWatch Logs Insights, Splunk, Datadog, and ELK.

Session for audience:
  - Knowledge fuel: audit logging requirements (SOX, PCI-DSS, GDPR Art. 22)
  - Lab: add a CloudWatch Logs handler and query agent decisions using
        Logs Insights to find all $500+ refunds in the last 30 days
"""
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Structured JSON logger for decisions — separate from app logger
_decision_log = logging.getLogger("agent.decisions")

if not _decision_log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))  # raw JSON only
    _decision_log.addHandler(handler)
    _decision_log.setLevel(logging.INFO)
    _decision_log.propagate = False  # don't bubble up to root logger


# ---------------------------------------------------------------------------
# Decision log data model
# ---------------------------------------------------------------------------
@dataclass
class ToolCallRecord:
    tool_name: str
    args: Dict[str, Any]
    result: Any
    duration_ms: float
    success: bool
    risk_score: float = 0.0
    policy_action: str = "allow"
    hitl_approval_id: Optional[str] = None


@dataclass
class DecisionLog:
    """Complete record of one agent turn (user message → response)."""
    decision_id: str
    conversation_id: str
    timestamp: str
    user_message: str
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    final_response: str = ""
    pii_detected: bool = False
    injection_detected: bool = False
    injection_risk_score: float = 0.0
    reflection_passed: Optional[bool] = None
    constitutional_score: float = 1.0
    total_duration_ms: float = 0.0
    llm_model: str = ""
    environment: str = os.getenv("ENVIRONMENT", "development")
    version: str = "1.0"

    def add_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    def summary(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "conversation_id": self.conversation_id,
            "tool_count": len(self.tool_calls),
            "tools_used": [tc.tool_name for tc in self.tool_calls],
            "total_duration_ms": self.total_duration_ms,
            "pii_detected": self.pii_detected,
            "injection_detected": self.injection_detected,
        }


# ---------------------------------------------------------------------------
# Decision Logger
# ---------------------------------------------------------------------------
class DecisionLogger:
    """
    Manages the creation and persistence of DecisionLog entries.

    Usage:
        logger = get_decision_logger()
        log = logger.start_decision(conversation_id, user_message)
        log.pii_detected = True
        log.add_tool_call(ToolCallRecord(...))
        log.final_response = "I have processed your refund."
        logger.commit(log)  # emits the JSON log line
    """

    def __init__(self):
        self._active: Dict[str, DecisionLog] = {}

    def start_decision(self, conversation_id: str, user_message: str) -> DecisionLog:
        """Create a new DecisionLog and register it as active."""
        log = DecisionLog(
            decision_id=f"DEC-{uuid.uuid4().hex[:12].upper()}",
            conversation_id=conversation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_message=user_message[:500],  # truncate for log safety
        )
        self._active[log.decision_id] = log
        return log

    def commit(self, log: DecisionLog) -> None:
        """
        Finalise and emit the decision log entry.

        Emits a JSON line to the agent.decisions logger which can be
        captured by CloudWatch Logs, Datadog, or any other log shipper.

        TODO (Lab):
            Add a CloudWatch Logs Insights-compatible log group:
              1. Create log group: /agent/decisions
              2. Add CloudWatchLogsHandler from aws_xray_sdk or watchtower
              3. Query: fields @timestamp, tool_count, pii_detected
                        | filter total_duration_ms > 5000
                        | sort @timestamp desc
        """
        self._active.pop(log.decision_id, None)
        _decision_log.info(log.to_json())

    def get_active(self, decision_id: str) -> Optional[DecisionLog]:
        return self._active.get(decision_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_logger_instance: Optional[DecisionLogger] = None


def get_decision_logger() -> DecisionLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = DecisionLogger()
    return _logger_instance
