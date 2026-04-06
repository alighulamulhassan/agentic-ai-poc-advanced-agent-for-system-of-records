"""
Hierarchical Agent Orchestrator — Supervisor + Specialist agent pattern.

Instead of a single flat agent handling everything, this implements a
two-level hierarchy:

  ┌─────────────────────────────────┐
  │      Supervisor Agent           │
  │  - Routes to specialist         │
  │  - Aggregates results           │
  │  - Handles escalations          │
  └────┬──────────────┬─────────────┘
       │              │
  ┌────▼────┐   ┌─────▼──────┐
  │  Query  │   │ Transaction │
  │  Agent  │   │   Agent     │
  │(readonly)│  │(write tools)│
  └─────────┘   └────────────┘

Benefits:
  - Least-privilege tool access (Query agent has no write tools)
  - Clearer audit trail (which specialist made the transaction)
  - Independent scaling (transaction agent can have stricter guardrails)
  - Easier testing (test each specialist independently)

Session for audience:
  - Knowledge fuel: AutoGen, CrewAI, LangGraph multi-agent patterns
  - Lab: add a third specialist (ComplianceAgent) that runs after every
        transaction and verifies it meets policy requirements
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.llm import get_llm
from app.tools.registry import ALL_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool partitioning
# ---------------------------------------------------------------------------
_READONLY_TOOL_NAMES = {
    "lookup_order", "get_customer_info", "find_customer_by_email",
    "get_customer_order_history", "search_products", "search_documents",
}

_WRITE_TOOL_NAMES = {
    "cancel_order", "process_refund", "update_order_status",
    "update_shipping_address", "apply_discount_code",
    "add_loyalty_points", "update_customer_profile", "expedite_order_shipping",
}

_tool_map = {t.name: t for t in ALL_TOOLS}

READONLY_TOOLS = [t for t in ALL_TOOLS if t.name in _READONLY_TOOL_NAMES]
WRITE_TOOLS = [t for t in ALL_TOOLS if t.name in _WRITE_TOOL_NAMES]


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------
@dataclass
class RoutingDecision:
    specialist: str          # "query" | "transaction" | "escalate"
    confidence: float
    rationale: str
    requires_info_first: bool = False


_SUPERVISOR_SYSTEM_PROMPT = """You are a supervisor that routes customer support requests
to the right specialist agent.

Available specialists:
- "query": handles read-only lookups (order status, customer info, product search, FAQs)
- "transaction": handles write operations (cancellations, refunds, address changes, discounts)
- "escalate": for complex cases needing human support (legal disputes, fraud, repeated failures)

Rules:
1. If the customer only wants information → route to "query"
2. If the customer wants to change something → route to "transaction"
3. If the request is ambiguous, route to "query" first (least privilege)
4. If multiple operations are needed, choose based on the primary intent

Respond ONLY in JSON:
{"specialist": "query|transaction|escalate", "confidence": 0.0-1.0, "rationale": "brief reason", "requires_info_first": true/false}
"""


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------
class QueryAgent:
    """
    Read-only specialist agent.
    Has access only to lookup tools — cannot modify any data.
    """

    SYSTEM_PROMPT = """You are a read-only customer support agent.
You can look up information about orders, customers, products, and policies.
You CANNOT modify any data. If the customer needs a change made, tell them
you'll connect them with our support team who can help with that.

Be concise, accurate, and helpful. Always cite the source of your information."""

    def __init__(self):
        self.llm = get_llm()
        self.tools = READONLY_TOOLS

    async def run(self, messages: List[Dict], user_message: str) -> Dict[str, Any]:
        """Execute the query agent loop."""
        from app.tools.executor import execute_tool

        msgs = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        msgs.extend(messages)
        msgs.append({"role": "user", "content": user_message})

        response = await self.llm.chat(msgs, tools=self.tools)

        if response.get("tool_calls"):
            tool_results = []
            for tc in response["tool_calls"]:
                result = await execute_tool(tc["name"], tc.get("args", {}))
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", tc["name"]),
                    "name": tc["name"],
                    "content": str(result),
                })

            msgs.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response["tool_calls"],
            })
            msgs.extend(tool_results)

            final = await self.llm.chat(msgs)
            return {"content": final["content"], "specialist": "query", "tool_calls": response["tool_calls"]}

        return {"content": response["content"], "specialist": "query"}


class TransactionAgent:
    """
    Write-access specialist agent.
    Has access to all tools (read + write) to complete transactions.
    Runs with full guardrails pipeline.
    """

    SYSTEM_PROMPT = """You are a transaction specialist agent with authority to modify customer data.
You can: cancel orders, process refunds, update addresses, apply discounts, add loyalty points.

Before any transaction:
1. Confirm you have the right order/customer ID
2. State clearly what you're about to do
3. Execute using the appropriate tool
4. Report the exact result

You are responsible for accurate, careful transactions. When in doubt, use the lookup tools first."""

    def __init__(self):
        self.llm = get_llm()
        self.tools = ALL_TOOLS

    async def run(self, messages: List[Dict], user_message: str) -> Dict[str, Any]:
        """Execute the transaction agent loop with guardrails."""
        from app.tools.executor import execute_tool

        msgs = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        msgs.extend(messages)
        msgs.append({"role": "user", "content": user_message})

        response = await self.llm.chat(msgs, tools=self.tools)

        if response.get("tool_calls"):
            tool_results = []
            for tc in response["tool_calls"]:
                result = await execute_tool(tc["name"], tc.get("args", {}))
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", tc["name"]),
                    "name": tc["name"],
                    "content": str(result),
                })

            msgs.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response["tool_calls"],
            })
            msgs.extend(tool_results)

            final = await self.llm.chat(msgs)
            return {"content": final["content"], "specialist": "transaction", "tool_calls": response["tool_calls"]}

        return {"content": response["content"], "specialist": "transaction"}


# ---------------------------------------------------------------------------
# Supervisor Orchestrator
# ---------------------------------------------------------------------------
class AgentOrchestrator:
    """
    Hierarchical orchestrator that routes requests to specialist agents.

    Usage:
        orchestrator = AgentOrchestrator()
        result = await orchestrator.process(
            user_message="Cancel my order ORD-10003",
            conversation_history=[...]
        )
    """

    def __init__(self):
        self.llm = get_llm()
        self.query_agent = QueryAgent()
        self.transaction_agent = TransactionAgent()

    async def route(self, user_message: str, history: List[Dict]) -> RoutingDecision:
        """Use the supervisor LLM to decide which specialist to invoke."""
        import json

        messages = [
            {"role": "system", "content": _SUPERVISOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Route this request: {user_message}"},
        ]

        try:
            response = await self.llm.chat(messages)
            content = response.get("content", "{}")
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0:
                content = content[start:end]
            parsed = json.loads(content)

            return RoutingDecision(
                specialist=parsed.get("specialist", "query"),
                confidence=float(parsed.get("confidence", 0.8)),
                rationale=parsed.get("rationale", ""),
                requires_info_first=bool(parsed.get("requires_info_first", False)),
            )
        except Exception as exc:
            logger.warning(f"Routing failed, defaulting to query agent: {exc}")
            return RoutingDecision(specialist="query", confidence=0.5, rationale="routing error fallback")

    async def process(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Route and execute a user request through the appropriate specialist.

        TODO (Lab — Month 6):
        Add a third specialist: ComplianceAgent that:
          1. Runs AFTER every transaction
          2. Reviews what the TransactionAgent did
          3. Flags any policy violations for audit
          4. Records to the compliance log
        This implements a "monitor" pattern common in regulated industries.
        """
        history = conversation_history or []

        # Step 1: Route
        routing = await self.route(user_message, history)
        logger.info(
            f"Routed to specialist='{routing.specialist}' "
            f"confidence={routing.confidence:.2f} "
            f"rationale='{routing.rationale}'"
        )

        # Step 2: If transaction agent needs info first, get it
        if routing.specialist == "transaction" and routing.requires_info_first:
            info_result = await self.query_agent.run(history, user_message)
            # Inject the gathered info into history for the transaction agent
            history = history + [
                {"role": "assistant", "content": info_result["content"]}
            ]

        # Step 3: Dispatch to specialist
        if routing.specialist == "transaction":
            result = await self.transaction_agent.run(history, user_message)
        elif routing.specialist == "escalate":
            result = {
                "content": (
                    "I'm connecting you with a senior support specialist who can "
                    "best assist with your situation. You'll receive a follow-up "
                    "within 2 business hours."
                ),
                "specialist": "escalate",
                "escalated": True,
            }
        else:
            result = await self.query_agent.run(history, user_message)

        result["routing"] = {
            "specialist": routing.specialist,
            "confidence": routing.confidence,
            "rationale": routing.rationale,
        }

        return result
