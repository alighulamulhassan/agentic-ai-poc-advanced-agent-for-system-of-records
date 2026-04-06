"""
Risk Scorer — quantifies the risk level of each agent action.

Assigns a numeric risk score (0.0–1.0) to every tool call based on:
  - Tool category (read vs write vs financial)
  - Argument magnitude (refund amount, point count)
  - Conversation context (repeated same action, escalating amounts)
  - User role (readonly agents have higher base risk for write operations)

The score is used to:
  1. Route to HITL when score > threshold
  2. Add to decision log for post-hoc auditing
  3. Trigger alerts when aggregated risk exceeds daily limits

Session for audience:
  - Knowledge fuel: risk scoring in banking/fintech, fraud detection basics
  - Lab: implement session_risk_trend() to detect escalating patterns
        within a single conversation (e.g., multiple refunds, increasing amounts)
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk score result
# ---------------------------------------------------------------------------
@dataclass
class RiskScore:
    tool_name: str
    score: float                  # 0.0 (safe) → 1.0 (critical)
    level: str                    # none | low | medium | high | critical
    factors: List[str] = field(default_factory=list)
    requires_hitl: bool = False
    requires_logging: bool = True

    @classmethod
    def from_score(cls, tool_name: str, score: float, factors: List[str]) -> "RiskScore":
        score = round(min(1.0, max(0.0, score)), 3)
        if score >= 0.8:
            level = "critical"
        elif score >= 0.6:
            level = "high"
        elif score >= 0.4:
            level = "medium"
        elif score >= 0.1:
            level = "low"
        else:
            level = "none"
        return cls(
            tool_name=tool_name,
            score=score,
            level=level,
            factors=factors,
            requires_hitl=score >= 0.7,
            requires_logging=score >= 0.2,
        )

    def __str__(self) -> str:
        return f"RiskScore({self.tool_name}, {self.level}, {self.score:.2f})"


# ---------------------------------------------------------------------------
# Base risk scores by tool
# ---------------------------------------------------------------------------
_BASE_SCORES: Dict[str, float] = {
    # Read-only — low risk
    "lookup_order": 0.0,
    "get_customer_info": 0.05,
    "find_customer_by_email": 0.05,
    "get_customer_order_history": 0.0,
    "search_products": 0.0,
    "search_documents": 0.0,
    # Write — moderate risk
    "update_shipping_address": 0.25,
    "update_order_status": 0.30,
    "update_customer_profile": 0.25,
    "expedite_order_shipping": 0.15,
    "apply_discount_code": 0.20,
    # Financial — high risk
    "add_loyalty_points": 0.40,
    "cancel_order": 0.55,
    "process_refund": 0.60,
}

_DEFAULT_BASE = 0.50  # unknown tools get high base score


# ---------------------------------------------------------------------------
# Risk scorer
# ---------------------------------------------------------------------------
class RiskScorer:
    """
    Computes risk scores for tool calls.

    Usage:
        scorer = RiskScorer()
        score = scorer.score("process_refund", {"amount": 750})
        if score.requires_hitl:
            await hitl_manager.request_approval(...)
    """

    def __init__(self, hitl_threshold: float = 0.7):
        self.hitl_threshold = hitl_threshold
        self._session_history: List[Dict] = []

    def score(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskScore:
        """
        Compute risk score for a tool call.

        Scoring layers:
          1. Base score by tool category
          2. Argument magnitude adjustments
          3. Session pattern adjustments
          4. Role-based adjustments
          5. TODO (Lab): ML-based anomaly score
        """
        ctx = context or {}
        factors: List[str] = []
        score = _BASE_SCORES.get(tool_name, _DEFAULT_BASE)

        if score > 0:
            factors.append(f"base score for '{tool_name}': {score:.2f}")

        # --- Layer 2: Argument magnitude ---
        score, factors = self._adjust_for_magnitude(tool_name, args, score, factors)

        # --- Layer 3: Session pattern ---
        score, factors = self._adjust_for_session_pattern(tool_name, args, score, factors)

        # --- Layer 4: Role-based adjustment ---
        user_role = ctx.get("user_role", "agent")
        if user_role == "readonly" and tool_name in _BASE_SCORES and _BASE_SCORES[tool_name] > 0.1:
            score = min(1.0, score + 0.2)
            factors.append("role 'readonly' attempting write operation (+0.20)")

        result = RiskScore.from_score(tool_name, score, factors)

        # Record in session history
        self._session_history.append({
            "tool": tool_name,
            "score": result.score,
            "args": args,
        })

        if result.score >= 0.5:
            logger.warning(f"Risk score {result.level.upper()} | {result}")
        elif result.score > 0:
            logger.info(f"Risk score {result.level} | {result}")

        return result

    def _adjust_for_magnitude(
        self,
        tool: str,
        args: Dict,
        score: float,
        factors: List[str],
    ) -> Tuple[float, List[str]]:
        """Increase score for large financial values."""
        if tool == "process_refund":
            amount = float(args.get("amount", 0))
            if amount > 1000:
                score += 0.30
                factors.append(f"refund amount ${amount:.2f} > $1,000 (+0.30)")
            elif amount > 500:
                score += 0.20
                factors.append(f"refund amount ${amount:.2f} > $500 (+0.20)")
            elif amount > 100:
                score += 0.10
                factors.append(f"refund amount ${amount:.2f} > $100 (+0.10)")

        if tool == "add_loyalty_points":
            points = int(args.get("points", 0))
            if points > 10_000:
                score += 0.30
                factors.append(f"loyalty grant {points} points > 10,000 (+0.30)")
            elif points > 5_000:
                score += 0.15
                factors.append(f"loyalty grant {points} points > 5,000 (+0.15)")

        return score, factors

    def _adjust_for_session_pattern(
        self,
        tool: str,
        args: Dict,
        score: float,
        factors: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Detect suspicious patterns within the session.

        TODO (Lab — Month 5):
        Implement session_risk_trend() that:
          1. Detects multiple refunds in one conversation (possible fraud)
          2. Detects rapidly increasing refund amounts (escalation pattern)
          3. Flags if the same order_id is acted on multiple times

        Current implementation: basic repeat-action detection.
        """
        if not self._session_history:
            return score, factors

        # Count how many times this same tool has been called this session
        same_tool_count = sum(1 for h in self._session_history if h["tool"] == tool)

        if same_tool_count >= 3:
            score = min(1.0, score + 0.25)
            factors.append(f"tool '{tool}' called {same_tool_count + 1}x in session (+0.25)")
        elif same_tool_count >= 1:
            score = min(1.0, score + 0.10)
            factors.append(f"tool '{tool}' called {same_tool_count + 1}x in session (+0.10)")

        return score, factors

    def session_summary(self) -> Dict[str, Any]:
        """Return an aggregated risk summary for the current session."""
        if not self._session_history:
            return {"total_calls": 0, "max_score": 0.0, "avg_score": 0.0}
        scores = [h["score"] for h in self._session_history]
        return {
            "total_calls": len(self._session_history),
            "max_score": max(scores),
            "avg_score": round(sum(scores) / len(scores), 3),
            "high_risk_calls": sum(1 for s in scores if s >= 0.6),
        }

    def reset_session(self) -> None:
        """Clear session history (call when conversation ends)."""
        self._session_history = []


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_default_scorer: Optional[RiskScorer] = None


def score_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> RiskScore:
    """Convenience function using the default per-process scorer."""
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = RiskScorer()
    return _default_scorer.score(tool_name, args, context)
