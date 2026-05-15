"""
Agent orchestrator — the brain of the voice agent.
Now enhanced with the full enterprise security + guardrails + observability pipeline.

Pipeline for every user message:
  1. PII detection on input
  2. Injection guard check
  3. LLM call → tool plan
  4. Reflection check on plan (if high-risk)
  5. Constitutional input check per tool
  6. Policy engine evaluation per tool
  7. Risk scoring per tool
  8. HITL approval (if risk >= threshold)
  9. Output validation on tool args
  10. Tool execution
  11. Constitutional output check on response
  12. Decision log committed
"""
import logging
import time
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.config import settings
from app.core.llm import get_llm
from app.tools.registry import get_tools, get_tool_schemas
from app.tools.executor import execute_tool
from app.observability.langwatch_setup import get_langwatch

logger = logging.getLogger(__name__)


def _lw():
    """Return the langwatch module if remote tracing is enabled, else None."""
    return get_langwatch()


class _NullContext:
    """No-op context manager used when LangWatch is not installed."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def _lw_span(**kwargs):
    """Return a LangWatch span context, or a no-op if langwatch missing."""
    lw = _lw()
    if lw is None:
        return _NullContext()
    return lw.span(**kwargs)


def _attach_eval(trace_or_span, **kwargs) -> None:
    """Best-effort: attach an evaluation result to the current trace/span."""
    if trace_or_span is None:
        return
    try:
        trace_or_span.add_evaluation(**kwargs)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"add_evaluation skipped: {e}")

SYSTEM_PROMPT = """You are a helpful, knowledgeable customer support agent for an e-commerce company.
You are empathetic, professional, and always aim to resolve customer issues efficiently.

You have FULL AUTHORITY to perform transactions on the system of record (database).

## Your Capabilities:

### READ Operations:
- lookup_order: Check order status, tracking, items, and shipping info
- get_customer_info: Look up customer details, loyalty points, and tier
- find_customer_by_email: Find customer by email address
- get_customer_order_history: Get complete order history
- search_products: Find products in catalog
- search_documents: Search knowledge base, policies, and FAQs

### WRITE/TRANSACTION Operations (MODIFY DATABASE):
- cancel_order: Cancel an order (auto-refunds if not shipped)
- process_refund: Issue partial or full refunds
- update_order_status: Change order status
- update_shipping_address: Change delivery address (before shipment)
- apply_discount_code: Apply coupon codes (WELCOME10, SAVE20, VIP25, FREESHIP, HOLIDAY30)
- add_loyalty_points: Award bonus points to customers
- update_customer_profile: Update customer name, email, phone, or address
- expedite_order_shipping: Upgrade to express shipping (free, as goodwill)

## Transaction Guidelines:
1. Confirm before destructive actions: Cancellations and refunds should be confirmed
2. Use tools liberally: Don't just explain — actually perform the action!
3. Report results: After a transaction, tell the customer exactly what happened
4. Be proactive: Offer expedited shipping or loyalty points for service issues

Remember: You have real power to help customers. Use your tools to actually solve their problems!"""


class Agent:
    """
    Main agent class with full enterprise guardrails pipeline.

    Each process_message() call runs through:
      Security → LLM → Reflection → Guardrails → Tools → Observability
    """

    def __init__(self, use_rag: bool = True, conversation_id: str = "default"):
        self.use_rag = use_rag
        self.conversation_id = conversation_id
        self.llm = get_llm()
        self.tools = get_tool_schemas()
        self.conversation_history: List[Dict] = []

        # Lazy-init enterprise components (avoids import errors if optional deps missing)
        self._pii_detector = None
        self._injection_guard = None
        self._output_validator = None
        self._policy_engine = None
        self._risk_scorer = None
        self._hitl_manager = None
        self._decision_logger = None
        self._reflector = None
        self._constitutional_guard = None

    # ------------------------------------------------------------------
    # Lazy component accessors
    # ------------------------------------------------------------------
    def _pii(self):
        if self._pii_detector is None:
            from app.security.pii_detector import PIIDetector
            self._pii_detector = PIIDetector(min_risk_level="medium")
        return self._pii_detector

    def _guard(self):
        if self._injection_guard is None:
            from app.security.injection_guard import InjectionGuard
            self._injection_guard = InjectionGuard(block_threshold=0.5)
        return self._injection_guard

    def _validator(self):
        if self._output_validator is None:
            from app.security.output_validator import OutputValidator
            self._output_validator = OutputValidator()
        return self._output_validator

    def _policy(self):
        if self._policy_engine is None:
            from app.guardrails.policy_engine import get_policy_engine
            self._policy_engine = get_policy_engine()
        return self._policy_engine

    def _risk(self):
        if self._risk_scorer is None:
            from app.guardrails.risk_scorer import RiskScorer
            self._risk_scorer = RiskScorer()
        return self._risk_scorer

    def _hitl(self):
        if self._hitl_manager is None:
            from app.guardrails.hitl import get_hitl_manager
            self._hitl_manager = get_hitl_manager()
        return self._hitl_manager

    def _dlog(self):
        if self._decision_logger is None:
            from app.observability.decision_logger import get_decision_logger
            self._decision_logger = get_decision_logger()
        return self._decision_logger

    def _reflector_instance(self):
        if self._reflector is None:
            from app.guardrails.reflection import ReflectionAgent
            self._reflector = ReflectionAgent(
                llm_client=self.llm,
                enabled=True,
                min_risk_score=0.5,
            )
        return self._reflector

    def _constitutional(self):
        if self._constitutional_guard is None:
            from app.guardrails.constitutional import ConstitutionalGuard
            self._constitutional_guard = ConstitutionalGuard()
        return self._constitutional_guard

    # ------------------------------------------------------------------
    # Main processing pipeline
    # ------------------------------------------------------------------
    async def process_message(
        self,
        user_message: str,
        conversation_id: str = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the full enterprise pipeline.

        Returns a dict with: content, tool_calls, tool_results,
        pii_detected, injection_checked, decision_id
        """
        start = time.time()
        conv_id = conversation_id or self.conversation_id

        # Start decision log
        dec_log = self._dlog().start_decision(conv_id, user_message)

        # LangWatch trace for the full pipeline (no-op if langwatch missing)
        lw = _lw()
        lw_trace_cm = (
            lw.trace(
                name="agent.process_message",
                type="agent",
                input=user_message,
                metadata={
                    "conversation_id": conv_id,
                    "decision_id": dec_log.decision_id,
                    "llm_model": settings.llm_model,
                },
            )
            if lw is not None
            else _NullContext()
        )

        with lw_trace_cm as lw_trace:
            return await self._run_pipeline(
                user_message, conv_id, dec_log, start, lw_trace
            )

    async def _run_pipeline(
        self,
        user_message: str,
        conv_id: str,
        dec_log,
        start: float,
        lw_trace,
    ) -> Dict[str, Any]:
        # ------ Step 1: PII detection on input ------
        with _lw_span(name="guardrail.pii_detection", type="guardrail", input=user_message) as pii_span:
            pii_result = self._pii().detect(user_message)
            dec_log.pii_detected = pii_result.pii_found
            _attach_eval(
                pii_span,
                name="PII Detection",
                type="security/pii_detection",
                is_guardrail=True,
                status="processed",
                passed=not pii_result.pii_found,
                label=pii_result.risk_level,
                details=pii_result.summary,
            )
        if pii_result.pii_found:
            logger.info(f"PII detected in input [{pii_result.risk_level}]: {pii_result.summary}")
            user_message_to_llm = pii_result.masked
        else:
            user_message_to_llm = user_message

        # ------ Step 2: Injection guard ------
        with _lw_span(name="guardrail.injection_check", type="guardrail", input=user_message) as inj_span:
            injection_result = self._guard().check(user_message)
            dec_log.injection_detected = not injection_result.is_safe
            dec_log.injection_risk_score = injection_result.risk_score
            _attach_eval(
                inj_span,
                name="Prompt Injection Guard",
                type="security/injection",
                is_guardrail=True,
                status="processed",
                passed=injection_result.is_safe,
                score=injection_result.risk_score,
                details=injection_result.reason or "",
            )
            _attach_eval(
                lw_trace,
                name="Prompt Injection Guard",
                type="security/injection",
                is_guardrail=True,
                status="processed",
                passed=injection_result.is_safe,
                score=injection_result.risk_score,
                details=injection_result.reason or "",
            )

        if injection_result.should_block:
            logger.warning(f"Injection attempt blocked: {injection_result.reason}")
            response_content = (
                "I'm sorry, but I couldn't process that request. "
                "Please rephrase your question and try again."
            )
            dec_log.final_response = response_content
            dec_log.total_duration_ms = (time.time() - start) * 1000
            self._dlog().commit(dec_log)
            return {
                "content": response_content,
                "blocked": True,
                "block_reason": "injection_guard",
                "decision_id": dec_log.decision_id,
            }

        # ------ Step 3: LLM call ------
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message_to_llm})

        with _lw_span(
            name="llm.plan",
            type="llm",
            model=settings.llm_model,
            input=user_message_to_llm,
        ) as llm_span:
            response = await self.llm.chat(messages, tools=self.tools if self.tools else None)
            if llm_span is not None:
                try:
                    llm_span.update(output=response.get("content") or "")
                except Exception:  # noqa: BLE001
                    pass

        # ------ Step 4: Handle tool calls ------
        tool_results = []
        executed_tool_calls = []

        if response.get("tool_calls"):
            tool_calls = response["tool_calls"]

            # Step 4a: Reflection check on the full plan
            aggregate_risk = 0.0
            for tc in tool_calls:
                rs = self._risk().score(tc.get("name", ""), tc.get("args", {}))
                aggregate_risk = max(aggregate_risk, rs.score)

            reflection = await self._reflector_instance().reflect(
                user_message=user_message,
                proposed_tool_calls=tool_calls,
                risk_score=aggregate_risk,
            )
            dec_log.reflection_passed = reflection.passed
            tool_calls_to_run = reflection.plan_to_execute

            _attach_eval(
                lw_trace,
                name="Reflection Check",
                type="guardrail/reflection",
                is_guardrail=True,
                status="processed",
                passed=reflection.passed,
                score=aggregate_risk,
                details=getattr(reflection, "reasoning", "") or "",
            )

            # Step 4b: Per-tool guardrails + execution
            for tool_call in tool_calls_to_run:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"call_{tool_name}")
                call_start = time.time()

                tool_span_cm = _lw_span(
                    name=f"tool.{tool_name}",
                    type="tool",
                    input=tool_args,
                )
                tool_span = tool_span_cm.__enter__()

                # Constitutional input check
                const_result = self._constitutional().check_input(
                    user_message, tool_name, tool_args
                )
                dec_log.constitutional_score = min(
                    dec_log.constitutional_score, const_result.overall_score
                )
                _attach_eval(
                    tool_span,
                    name="Constitutional Input Check",
                    type="guardrail/constitutional",
                    is_guardrail=True,
                    status="processed",
                    passed=const_result.passed,
                    score=const_result.overall_score,
                    details=const_result.summary,
                )

                # Output validation
                validation = self._validator().validate(tool_name, tool_args)
                if not validation.is_valid:
                    logger.warning(f"Tool args validation failed: {validation.summary}")
                    result = {"error": validation.summary, "blocked_by": "output_validator"}
                else:
                    tool_args = validation.sanitized_args or tool_args

                    # Policy engine
                    policy_result = self._policy().evaluate(tool_name, tool_args)

                    if policy_result.is_blocked:
                        logger.warning(f"Tool blocked by policy: {policy_result.reason}")
                        result = {"error": policy_result.reason, "blocked_by": "policy_engine"}
                    elif policy_result.needs_approval:
                        # Risk score
                        risk_score = self._risk().score(tool_name, tool_args)
                        dec_log.injection_risk_score = max(
                            dec_log.injection_risk_score, risk_score.score
                        )

                        # Request HITL approval
                        approval_req = await self._hitl().request_approval(
                            tool_name=tool_name,
                            args=tool_args,
                            reason=policy_result.reason,
                            risk_score=risk_score.score,
                            requested_by=conv_id,
                        )
                        approved = await self._hitl().wait_for_approval(approval_req.approval_id)

                        if approved:
                            result = await execute_tool(tool_name, tool_args)
                        else:
                            result = {
                                "error": "Action requires supervisor approval and was not approved.",
                                "approval_id": approval_req.approval_id,
                                "blocked_by": "hitl",
                            }
                    else:
                        # Execute the tool
                        result = await execute_tool(tool_name, tool_args)

                duration_ms = (time.time() - call_start) * 1000
                executed_tool_calls.append(tool_call)

                # Log tool call to decision log
                from app.observability.decision_logger import ToolCallRecord
                dec_log.add_tool_call(ToolCallRecord(
                    tool_name=tool_name,
                    args=tool_args,
                    result=result,
                    duration_ms=round(duration_ms, 2),
                    success="error" not in str(result).lower(),
                    risk_score=aggregate_risk,
                    policy_action=policy_result.action.value if 'policy_result' in dir() else "allow",
                ))

                # Close the LangWatch tool span with the result + eval
                if tool_span is not None:
                    try:
                        tool_span.update(output=result)
                    except Exception:  # noqa: BLE001
                        pass
                _attach_eval(
                    tool_span,
                    name="Tool Execution",
                    type="tool/execution",
                    status="processed",
                    passed="error" not in str(result).lower(),
                    score=aggregate_risk,
                    details=f"tool={tool_name} duration_ms={round(duration_ms, 2)}",
                )
                tool_span_cm.__exit__(None, None, None)

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": str(result),
                })

            # Get final response after all tools ran
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": tool_calls,
            })
            messages.extend(tool_results)
            with _lw_span(
                name="llm.final_response",
                type="llm",
                model=settings.llm_model,
            ) as final_span:
                final_response = await self.llm.chat(messages)
                content = final_response["content"]
                if final_span is not None:
                    try:
                        final_span.update(output=content)
                    except Exception:  # noqa: BLE001
                        pass

        else:
            content = response["content"]

        # ------ Step 5: Constitutional output check ------
        const_out = self._constitutional().check_output(user_message, content)
        if not const_out.passed:
            logger.warning(f"Constitutional output violation: {const_out.summary}")
        _attach_eval(
            lw_trace,
            name="Constitutional Output Check",
            type="guardrail/constitutional",
            is_guardrail=True,
            status="processed",
            passed=const_out.passed,
            score=const_out.overall_score,
            details=const_out.summary,
        )

        # Stamp the trace output for the dashboard
        if lw_trace is not None:
            try:
                lw_trace.update(output=content)
            except Exception:  # noqa: BLE001
                pass

        # ------ Step 6: Update conversation history ------
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": content})

        # ------ Step 7: Commit decision log ------
        dec_log.final_response = content[:500]
        dec_log.total_duration_ms = (time.time() - start) * 1000
        dec_log.llm_model = settings.llm_model
        self._dlog().commit(dec_log)

        return {
            "content": content,
            "tool_calls": executed_tool_calls if executed_tool_calls else None,
            "tool_results": tool_results if tool_results else None,
            "pii_detected": pii_result.pii_found,
            "injection_risk": injection_result.risk_score,
            "decision_id": dec_log.decision_id,
        }

    async def stream_response(self, user_message: str) -> AsyncGenerator[str, None]:
        """Stream response tokens (bypasses guardrail pipeline for speed — use for read-only queries)."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        async for token in self.llm.stream(messages):
            full_response += token
            yield token

        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": full_response})

    def clear_history(self) -> None:
        self.conversation_history = []
        if self._risk_scorer:
            self._risk_scorer.reset_session()

    def get_history(self) -> List[Dict]:
        return self.conversation_history


# ---------------------------------------------------------------------------
# Agent cache
# ---------------------------------------------------------------------------
_agents: Dict[str, Agent] = {}


def get_agent(conversation_id: str = "default") -> Agent:
    if conversation_id not in _agents:
        _agents[conversation_id] = Agent(conversation_id=conversation_id)
    return _agents[conversation_id]


def clear_agent(conversation_id: str = "default") -> None:
    if conversation_id in _agents:
        del _agents[conversation_id]
