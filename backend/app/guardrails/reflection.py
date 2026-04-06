"""
Reflection Agent — self-verification loop before execution.

Before the agent executes a plan (sequence of tool calls), this module
prompts the LLM to review its own reasoning and check for:
  - Misunderstanding of user intent
  - Unnecessary or excessive tool calls
  - Actions that conflict with stated customer request
  - Inconsistencies in the plan

This is a lightweight implementation of the "Reflexion" pattern
(Shinn et al., 2023) applied to transactional AI agents.

Session for audience:
  - Knowledge fuel: Reflexion paper, CoT self-consistency, multi-agent debate
  - Lab: implement multi-step reflection where the agent proposes a plan,
        critiques it, then revises before executing
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reflection result
# ---------------------------------------------------------------------------
@dataclass
class ReflectionResult:
    passed: bool
    original_plan: List[Dict]          # list of tool calls
    revised_plan: Optional[List[Dict]] # None if passed without revision
    critique: str
    confidence: float                  # 0.0–1.0 agent's self-assessed confidence
    skipped: bool = False              # True if reflection was bypassed

    @property
    def plan_to_execute(self) -> List[Dict]:
        """Return the revised plan if available, otherwise original."""
        if self.revised_plan is not None:
            return self.revised_plan
        return self.original_plan


_REFLECTION_SYSTEM_PROMPT = """You are a quality assurance reviewer for an AI customer support agent.

Your job is to review a proposed action plan and verify:
1. The actions match what the customer actually asked for
2. The scope is appropriate (not doing more than requested)
3. The tool calls are in the right order
4. There are no obvious errors (wrong order IDs, negative amounts, etc.)
5. No unnecessary or duplicate tool calls

Respond ONLY in this JSON format:
{
  "passed": true/false,
  "confidence": 0.0-1.0,
  "critique": "brief explanation",
  "revised_plan": null or [list of corrected tool calls]
}

Be concise. If the plan is fine, set passed=true and revised_plan=null.
"""

_REFLECTION_PROMPT_TEMPLATE = """Customer request: {user_message}

Proposed action plan:
{plan_description}

Review the plan and respond in JSON."""


# ---------------------------------------------------------------------------
# Reflection Agent
# ---------------------------------------------------------------------------
class ReflectionAgent:
    """
    Wraps the main agent's tool call plan with a self-verification step.

    Usage:
        reflector = ReflectionAgent(llm_client)
        result = await reflector.reflect(
            user_message="Cancel my order ORD-10003",
            proposed_tool_calls=[{"name": "cancel_order", "args": {...}}]
        )
        if result.passed:
            tool_calls_to_execute = result.plan_to_execute
        else:
            # Re-plan or escalate
    """

    def __init__(self, llm_client=None, enabled: bool = True, min_risk_score: float = 0.5):
        """
        Args:
            llm_client: LLMClient instance (if None, reflection is skipped)
            enabled: Master switch for reflection
            min_risk_score: Only reflect when the aggregate tool risk >= this threshold
        """
        self.llm = llm_client
        self.enabled = enabled
        self.min_risk_score = min_risk_score

    async def reflect(
        self,
        user_message: str,
        proposed_tool_calls: List[Dict[str, Any]],
        risk_score: float = 0.0,
    ) -> ReflectionResult:
        """
        Run the self-reflection check on a proposed tool call plan.

        Args:
            user_message: The original user request
            proposed_tool_calls: List of {name, args} dicts
            risk_score: Aggregate risk score (from RiskScorer)

        Returns:
            ReflectionResult — use .plan_to_execute for the final plan

        TODO (Lab — Month 5 Session 2):
        Extend this to a multi-round reflection:
          Round 1: Agent proposes plan
          Round 2: Critic LLM (separate system prompt) critiques it
          Round 3: Agent revises based on critique
          Round 4: Final consistency check
        This is the "Constitutional AI" debate pattern.
        """
        if not self.enabled or not self.llm:
            return ReflectionResult(
                passed=True,
                original_plan=proposed_tool_calls,
                revised_plan=None,
                critique="Reflection disabled",
                confidence=1.0,
                skipped=True,
            )

        if risk_score < self.min_risk_score and len(proposed_tool_calls) <= 1:
            return ReflectionResult(
                passed=True,
                original_plan=proposed_tool_calls,
                revised_plan=None,
                critique="Low risk single-tool call — reflection skipped",
                confidence=0.9,
                skipped=True,
            )

        # Build human-readable plan description
        plan_lines = []
        for i, tc in enumerate(proposed_tool_calls, 1):
            args_str = ", ".join(f"{k}={v!r}" for k, v in tc.get("args", {}).items())
            plan_lines.append(f"  Step {i}: {tc.get('name', '?')}({args_str})")
        plan_description = "\n".join(plan_lines)

        messages = [
            {"role": "system", "content": _REFLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _REFLECTION_PROMPT_TEMPLATE.format(
                    user_message=user_message,
                    plan_description=plan_description,
                ),
            },
        ]

        try:
            import json
            response = await self.llm.chat(messages)
            content = response.get("content", "{}")

            # Extract JSON from response (LLM might add prose around it)
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                content = content[start:end]

            parsed = json.loads(content)
            passed = bool(parsed.get("passed", True))
            confidence = float(parsed.get("confidence", 0.8))
            critique = str(parsed.get("critique", ""))
            revised_plan = parsed.get("revised_plan")

            if not passed:
                logger.warning(
                    f"Reflection FAILED | confidence={confidence:.2f} | "
                    f"critique={critique} | tool_count={len(proposed_tool_calls)}"
                )
            else:
                logger.info(f"Reflection passed | confidence={confidence:.2f}")

            return ReflectionResult(
                passed=passed,
                original_plan=proposed_tool_calls,
                revised_plan=revised_plan if isinstance(revised_plan, list) else None,
                critique=critique,
                confidence=confidence,
            )

        except Exception as exc:
            logger.error(f"Reflection failed with exception: {exc}")
            # Fail open — allow execution if reflection itself errors
            return ReflectionResult(
                passed=True,
                original_plan=proposed_tool_calls,
                revised_plan=None,
                critique=f"Reflection error (fail-open): {exc}",
                confidence=0.5,
            )
