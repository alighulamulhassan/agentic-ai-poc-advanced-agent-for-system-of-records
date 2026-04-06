"""
Constitutional AI Guard — principle-based pre/post-call checks.

Inspired by Anthropic's Constitutional AI (Bai et al., 2022).
Instead of relying solely on RLHF, this module defines explicit
*principles* that are checked against both:
  - Agent inputs (before tool execution)
  - Agent outputs (after LLM response generation)

For a System of Records agent, the constitution enforces:
  - Customer benefit principle: actions must benefit the customer
  - Proportionality: response should match the severity of the issue
  - Transparency: agent must not deceive about what it did
  - Data minimisation: only access data necessary for the task
  - Reversibility preference: prefer reversible actions when possible

Session for audience:
  - Knowledge fuel: Constitutional AI paper, RLHF vs rule-based approaches
  - Lab: define your own 5-principle constitution for your domain
        and implement the _evaluate_principle() scoring function

Reference: https://arxiv.org/abs/2212.08073
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Principle definition
# ---------------------------------------------------------------------------
@dataclass
class Principle:
    name: str
    description: str
    check_input: bool = True       # apply before tool call
    check_output: bool = True      # apply after LLM response
    is_hard_block: bool = False    # if True, violation blocks execution
    weight: float = 1.0            # relative importance (higher = stricter)


# ---------------------------------------------------------------------------
# Constitutional check result
# ---------------------------------------------------------------------------
@dataclass
class ConstitutionalCheckResult:
    passed: bool
    violations: List[Dict] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)
    overall_score: float = 1.0     # 1.0 = fully aligned, 0.0 = major violation

    @property
    def summary(self) -> str:
        if self.passed:
            return f"Constitutional check passed (score={self.overall_score:.2f})"
        violations = [v["principle"] for v in self.violations]
        return f"Constitutional violations: {', '.join(violations)}"


# ---------------------------------------------------------------------------
# Built-in principles
# ---------------------------------------------------------------------------
_CONSTITUTION: List[Principle] = [
    Principle(
        name="customer_benefit",
        description="Agent actions must serve the customer's stated interest.",
        check_input=True,
        check_output=True,
        is_hard_block=False,
        weight=1.5,
    ),
    Principle(
        name="proportionality",
        description="Response magnitude must match the severity of the issue.",
        check_input=True,
        check_output=False,
        is_hard_block=False,
        weight=1.0,
    ),
    Principle(
        name="transparency",
        description="Agent must accurately describe what it did, not deceive.",
        check_input=False,
        check_output=True,
        is_hard_block=True,
        weight=2.0,
    ),
    Principle(
        name="data_minimisation",
        description="Only access customer data necessary for the current task.",
        check_input=True,
        check_output=False,
        is_hard_block=False,
        weight=1.0,
    ),
    Principle(
        name="reversibility_preference",
        description="Prefer reversible actions (e.g. hold) over irreversible ones (e.g. cancel) when in doubt.",
        check_input=True,
        check_output=False,
        is_hard_block=False,
        weight=0.8,
    ),
    Principle(
        name="no_false_promises",
        description="Agent must not promise outcomes it cannot guarantee.",
        check_input=False,
        check_output=True,
        is_hard_block=True,
        weight=2.0,
    ),
]

# Patterns for output-level checks (applied to the LLM response text)
_DECEPTIVE_PATTERNS = [
    re.compile(r"\bi\s+(definitely|guarantee|promise)\s+(that\s+)?(you|your|the)", re.IGNORECASE),
    re.compile(r"(100%|absolutely)\s+(certain|guaranteed|sure)", re.IGNORECASE),
    re.compile(r"don't\s+worry[,.]?\s+I\s+(already|have|will|just)", re.IGNORECASE),
]

_FALSE_PROMISE_PATTERNS = [
    re.compile(r"(I|we)\s+(guarantee|promise|ensure)\s+that\s+.{0,50}(within|by|before)", re.IGNORECASE),
    re.compile(r"will\s+definitely\s+(arrive|ship|process|refund)", re.IGNORECASE),
    re.compile(r"(your|the)\s+refund\s+will\s+(be\s+)?(in\s+your\s+account|process)\s+within\s+\d+\s+hour", re.IGNORECASE),
]

# Tools that access broad data (data minimisation check)
_BROAD_DATA_TOOLS = {"get_customer_order_history", "get_customer_info"}
_NARROW_DATA_TOOLS = {"lookup_order", "find_customer_by_email"}


# ---------------------------------------------------------------------------
# Constitutional Guard
# ---------------------------------------------------------------------------
class ConstitutionalGuard:
    """
    Checks agent inputs and outputs against the defined constitution.

    Usage:
        guard = ConstitutionalGuard()

        # Before tool execution
        result = guard.check_input(
            user_message="What's my order status?",
            tool_name="get_customer_order_history",
            tool_args={"customer_id": "CUST-1001"}
        )

        # After LLM response
        result = guard.check_output(
            user_message="Will my refund come today?",
            agent_response="I guarantee your refund arrives within 2 hours."
        )
    """

    def __init__(self, constitution: Optional[List[Principle]] = None):
        self._principles = constitution or list(_CONSTITUTION)

    def check_input(
        self,
        user_message: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> ConstitutionalCheckResult:
        """
        Check a proposed tool call against input-phase principles.

        Args:
            user_message: The customer's original message
            tool_name: Tool being called
            tool_args: Arguments for the tool

        Returns:
            ConstitutionalCheckResult
        """
        violations = []
        warnings = []
        scores = []

        for principle in self._principles:
            if not principle.check_input:
                continue

            ok, score, detail = self._evaluate_input_principle(
                principle, user_message, tool_name, tool_args
            )
            scores.append(score * principle.weight)

            if not ok:
                entry = {
                    "principle": principle.name,
                    "detail": detail,
                    "score": score,
                    "hard_block": principle.is_hard_block,
                }
                if principle.is_hard_block:
                    violations.append(entry)
                else:
                    warnings.append(entry)

        overall = min(1.0, sum(scores) / max(1, len(scores))) if scores else 1.0
        hard_violations = [v for v in violations if v["hard_block"]]
        passed = len(hard_violations) == 0

        result = ConstitutionalCheckResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            overall_score=round(overall, 3),
        )

        if not passed:
            logger.warning(f"Constitutional violation (input) | {result.summary}")
        elif warnings:
            logger.info(f"Constitutional warnings (input) | count={len(warnings)}")

        return result

    def check_output(
        self,
        user_message: str,
        agent_response: str,
    ) -> ConstitutionalCheckResult:
        """
        Check the LLM-generated response against output-phase principles.

        Args:
            user_message: The customer's original message
            agent_response: The LLM's response text

        Returns:
            ConstitutionalCheckResult

        TODO (Lab):
        Implement an LLM-as-judge version:
          Ask a secondary LLM to score the response against each principle
          and return structured feedback. This catches nuanced violations
          that regex cannot (e.g., implicitly deceptive tone).
        """
        violations = []
        warnings = []
        scores = []

        for principle in self._principles:
            if not principle.check_output:
                continue

            ok, score, detail = self._evaluate_output_principle(
                principle, user_message, agent_response
            )
            scores.append(score * principle.weight)

            if not ok:
                entry = {
                    "principle": principle.name,
                    "detail": detail,
                    "score": score,
                    "hard_block": principle.is_hard_block,
                }
                if principle.is_hard_block:
                    violations.append(entry)
                else:
                    warnings.append(entry)

        overall = min(1.0, sum(scores) / max(1, len(scores))) if scores else 1.0
        hard_violations = [v for v in violations if v["hard_block"]]
        passed = len(hard_violations) == 0

        return ConstitutionalCheckResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            overall_score=round(overall, 3),
        )

    def _evaluate_input_principle(
        self,
        principle: Principle,
        user_message: str,
        tool_name: str,
        tool_args: Dict,
    ) -> Tuple[bool, float, str]:
        """Return (ok, score 0–1, detail string)."""

        if principle.name == "data_minimisation":
            # Flag if we're pulling broad data when a narrow lookup would suffice
            if tool_name in _BROAD_DATA_TOOLS:
                has_specific_order = "order" in user_message.lower() and "ORD-" in user_message
                if has_specific_order:
                    return (
                        False,
                        0.6,
                        f"'{tool_name}' retrieves broad customer data when a specific order lookup may suffice",
                    )
            return True, 1.0, ""

        if principle.name == "proportionality":
            # Flag cancel/refund for minor issues without explicit customer request
            high_impact = {"cancel_order", "process_refund"}
            escalating_words = {"delay", "slow", "late", "question", "wondering", "just asking"}
            if tool_name in high_impact:
                msg_lower = user_message.lower()
                if any(w in msg_lower for w in escalating_words) and "cancel" not in msg_lower and "refund" not in msg_lower:
                    return (
                        False,
                        0.5,
                        f"Proposing '{tool_name}' but customer appears to only be asking a question",
                    )
            return True, 1.0, ""

        if principle.name == "reversibility_preference":
            # Prefer on_hold over cancel when intent is ambiguous
            if tool_name == "cancel_order":
                msg_lower = user_message.lower()
                if "maybe" in msg_lower or "thinking" in msg_lower or "not sure" in msg_lower:
                    return (
                        False,
                        0.6,
                        "Customer seems uncertain — consider on_hold instead of cancel",
                    )
            return True, 1.0, ""

        # Default: principle passes if we have no specific check
        return True, 1.0, ""

    def _evaluate_output_principle(
        self,
        principle: Principle,
        user_message: str,
        agent_response: str,
    ) -> Tuple[bool, float, str]:
        """Return (ok, score 0–1, detail string)."""

        if principle.name == "transparency":
            for pat in _DECEPTIVE_PATTERNS:
                if pat.search(agent_response):
                    return False, 0.3, f"Response may contain misleading certainty claims"
            return True, 1.0, ""

        if principle.name == "no_false_promises":
            for pat in _FALSE_PROMISE_PATTERNS:
                if pat.search(agent_response):
                    return (
                        False,
                        0.2,
                        "Response contains an unverifiable promise about timing or outcome",
                    )
            return True, 1.0, ""

        return True, 1.0, ""
