"""
Policy Engine — declarative business rule enforcement.

Instead of burying business rules in the system prompt (which the LLM can
ignore), this module expresses them as code-level policies that are evaluated
BEFORE tool execution. The LLM cannot override them.

Policy DSL concepts:
  - Condition: a predicate over (tool_name, args, context)
  - Action: ALLOW | BLOCK | REQUIRE_APPROVAL | WARN
  - Priority: lower number = higher priority

Example policies:
  - "Refunds over $500 require supervisor approval"
  - "Cannot cancel an order that is already delivered"
  - "Maximum 3 loyalty point grants per conversation"

Session for audience:
  - Knowledge fuel: policy-as-code, open policy agent (OPA), Rego DSL
  - Lab: add 3 domain-specific policies for your use case and write tests
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy action enum
# ---------------------------------------------------------------------------
class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"
    WARN = "warn"


# ---------------------------------------------------------------------------
# Policy result
# ---------------------------------------------------------------------------
@dataclass
class PolicyResult:
    action: PolicyAction
    tool_name: str
    args: Dict[str, Any]
    triggered_policies: List[str] = field(default_factory=list)
    reason: str = ""
    approval_id: Optional[str] = None

    @property
    def is_blocked(self) -> bool:
        return self.action == PolicyAction.BLOCK

    @property
    def needs_approval(self) -> bool:
        return self.action == PolicyAction.REQUIRE_APPROVAL

    @property
    def is_allowed(self) -> bool:
        return self.action == PolicyAction.ALLOW


# ---------------------------------------------------------------------------
# Policy definition
# ---------------------------------------------------------------------------
PolicyConditionFn = Callable[[str, Dict[str, Any], Dict[str, Any]], bool]


@dataclass
class Policy:
    name: str
    description: str
    condition: PolicyConditionFn   # (tool_name, args, context) → bool (True = applies)
    action: PolicyAction
    priority: int = 100            # lower = evaluated first
    message: str = ""


# ---------------------------------------------------------------------------
# Built-in policies
# ---------------------------------------------------------------------------
def _refund_over_500(tool: str, args: Dict, ctx: Dict) -> bool:
    return tool == "process_refund" and float(args.get("amount", 0)) > 500


def _refund_over_1000(tool: str, args: Dict, ctx: Dict) -> bool:
    return tool == "process_refund" and float(args.get("amount", 0)) > 1000


def _cancel_delivered_order(tool: str, args: Dict, ctx: Dict) -> bool:
    if tool != "cancel_order":
        return False
    # Check order status from context if available
    order_status = ctx.get("order_status", {}).get(args.get("order_id", ""))
    return order_status == "delivered"


def _loyalty_points_excessive(tool: str, args: Dict, ctx: Dict) -> bool:
    return tool == "add_loyalty_points" and int(args.get("points", 0)) > 10_000


def _loyalty_grant_count(tool: str, args: Dict, ctx: Dict) -> bool:
    """Block if more than 3 loyalty grants in this conversation."""
    if tool != "add_loyalty_points":
        return False
    return ctx.get("loyalty_grants_this_session", 0) >= 3


def _status_regression(tool: str, args: Dict, ctx: Dict) -> bool:
    """Block nonsensical status regressions, e.g. delivered → processing."""
    if tool != "update_order_status":
        return False
    order_id = args.get("order_id", "")
    new_status = args.get("new_status", "")
    current = ctx.get("order_status", {}).get(order_id, "")
    terminal = {"delivered", "cancelled"}
    return current in terminal and new_status == "processing"


def _address_change_after_shipped(tool: str, args: Dict, ctx: Dict) -> bool:
    if tool != "update_shipping_address":
        return False
    order_id = args.get("order_id", "")
    status = ctx.get("order_status", {}).get(order_id, "")
    return status in {"shipped", "delivered"}


_DEFAULT_POLICIES: List[Policy] = [
    Policy(
        name="block_address_after_shipped",
        description="Cannot change address after order has shipped",
        condition=_address_change_after_shipped,
        action=PolicyAction.BLOCK,
        priority=10,
        message="Address cannot be changed — order has already shipped.",
    ),
    Policy(
        name="block_cancel_delivered",
        description="Cannot cancel a delivered order",
        condition=_cancel_delivered_order,
        action=PolicyAction.BLOCK,
        priority=10,
        message="Cancellation blocked — order is already delivered. Process a return instead.",
    ),
    Policy(
        name="block_status_regression",
        description="Cannot move a terminal order back to processing",
        condition=_status_regression,
        action=PolicyAction.BLOCK,
        priority=10,
        message="Invalid status transition — order is in a terminal state.",
    ),
    Policy(
        name="approve_large_refund",
        description="Refunds over $500 require human approval",
        condition=_refund_over_500,
        action=PolicyAction.REQUIRE_APPROVAL,
        priority=20,
        message="Refund exceeds $500 — supervisor approval required.",
    ),
    Policy(
        name="block_excessive_refund",
        description="Block refunds over $1,000 (likely hallucination)",
        condition=_refund_over_1000,
        action=PolicyAction.BLOCK,
        priority=15,
        message="Refund amount exceeds $1,000. This is outside agent authority.",
    ),
    Policy(
        name="warn_excessive_loyalty_points",
        description="Warn when granting more than 10,000 points at once",
        condition=_loyalty_points_excessive,
        action=PolicyAction.WARN,
        priority=30,
        message="Large loyalty point grant — verify with customer intent.",
    ),
    Policy(
        name="block_loyalty_grant_flood",
        description="Block more than 3 loyalty grants per session",
        condition=_loyalty_grant_count,
        action=PolicyAction.BLOCK,
        priority=20,
        message="Maximum loyalty grants per conversation reached (3).",
    ),
]


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------
class PolicyEngine:
    """
    Evaluates all registered policies against a proposed tool call.

    The engine respects priority ordering and short-circuits on BLOCK.
    REQUIRE_APPROVAL takes precedence over WARN but not over BLOCK.

    Usage:
        engine = PolicyEngine()
        result = engine.evaluate("process_refund", {"amount": 750, "order_id": "ORD-1"})
        if result.is_blocked:
            return {"error": result.reason}
        if result.needs_approval:
            approval_id = await hitl_manager.request_approval(result)
    """

    def __init__(self, policies: Optional[List[Policy]] = None):
        self._policies: List[Policy] = sorted(
            (policies or []) + _DEFAULT_POLICIES,
            key=lambda p: p.priority,
        )

    def add_policy(self, policy: Policy) -> None:
        """Register a custom policy and re-sort by priority."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority)

    def evaluate(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyResult:
        """
        Evaluate all policies for a tool call.

        Args:
            tool_name: The tool being called
            args: The LLM-generated arguments
            context: Runtime context (order statuses, session counters, user role, etc.)

        Returns:
            PolicyResult — check .is_blocked and .needs_approval before executing

        TODO (Lab):
            Load policies from a YAML/JSON config file so non-engineers can
            define business rules without modifying Python code.
            Bonus: integrate with AWS AppConfig for live policy updates.
        """
        ctx = context or {}
        triggered: List[str] = []
        final_action = PolicyAction.ALLOW
        final_message = ""

        for policy in self._policies:
            try:
                applies = policy.condition(tool_name, args, ctx)
            except Exception as exc:
                logger.error(f"Policy '{policy.name}' raised an exception: {exc}")
                continue

            if not applies:
                continue

            triggered.append(policy.name)
            logger.info(
                f"Policy triggered | tool={tool_name} | policy={policy.name} | "
                f"action={policy.action.value}"
            )

            # BLOCK is terminal — no need to evaluate further
            if policy.action == PolicyAction.BLOCK:
                return PolicyResult(
                    action=PolicyAction.BLOCK,
                    tool_name=tool_name,
                    args=args,
                    triggered_policies=triggered,
                    reason=policy.message or f"Blocked by policy: {policy.name}",
                )

            # REQUIRE_APPROVAL takes precedence over WARN
            if policy.action == PolicyAction.REQUIRE_APPROVAL:
                final_action = PolicyAction.REQUIRE_APPROVAL
                final_message = policy.message

            elif policy.action == PolicyAction.WARN and final_action == PolicyAction.ALLOW:
                final_action = PolicyAction.WARN
                final_message = policy.message

        return PolicyResult(
            action=final_action,
            tool_name=tool_name,
            args=args,
            triggered_policies=triggered,
            reason=final_message,
        )

    def list_policies(self) -> List[Dict]:
        """Return a summary of registered policies."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "action": p.action.value,
                "priority": p.priority,
            }
            for p in self._policies
        ]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
