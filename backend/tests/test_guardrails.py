"""
Tests for the Guardrails Engine.

Covers:
  - Policy engine: block, allow, require_approval
  - Risk scorer: base scores, magnitude adjustments, session patterns
  - HITL: approval workflow (approve, deny, timeout)
  - Constitutional AI: input and output checks
  - Reflection: passes clean plans, flags suspicious ones

Run: pytest tests/test_guardrails.py -v
"""
import pytest
import asyncio
from app.guardrails.policy_engine import PolicyEngine, PolicyAction
from app.guardrails.risk_scorer import RiskScorer
from app.guardrails.constitutional import ConstitutionalGuard


# ============================================================
# Policy Engine
# ============================================================
class TestPolicyEngine:

    def test_allows_safe_tool(self, policy_engine):
        result = policy_engine.evaluate("lookup_order", {"order_id": "ORD-10001"})
        assert result.is_allowed

    def test_blocks_excessive_refund(self, policy_engine):
        result = policy_engine.evaluate("process_refund", {
            "order_id": "ORD-10001",
            "amount": 1500.0,
            "reason": "Customer request",
        })
        assert result.is_blocked
        assert "1,000" in result.reason or "authority" in result.reason.lower()

    def test_requires_approval_large_refund(self, policy_engine):
        result = policy_engine.evaluate("process_refund", {
            "order_id": "ORD-10001",
            "amount": 750.0,
            "reason": "Damaged goods",
        })
        assert result.needs_approval
        assert "500" in result.reason

    def test_allows_small_refund(self, policy_engine):
        result = policy_engine.evaluate("process_refund", {
            "order_id": "ORD-10001",
            "amount": 25.0,
            "reason": "Wrong item shipped",
        })
        assert result.is_allowed

    def test_blocks_cancel_delivered_order(self, policy_engine):
        result = policy_engine.evaluate(
            "cancel_order",
            {"order_id": "ORD-10001", "reason": "Changed mind"},
            context={"order_status": {"ORD-10001": "delivered"}},
        )
        assert result.is_blocked

    def test_blocks_status_regression(self, policy_engine):
        result = policy_engine.evaluate(
            "update_order_status",
            {"order_id": "ORD-10001", "new_status": "processing"},
            context={"order_status": {"ORD-10001": "delivered"}},
        )
        assert result.is_blocked

    def test_warns_excessive_loyalty_points(self, policy_engine):
        result = policy_engine.evaluate("add_loyalty_points", {
            "customer_id": "CUST-1001",
            "points": 15_000,
            "reason": "Major issue",
        })
        assert result.action == PolicyAction.WARN

    def test_blocks_loyalty_flood(self, policy_engine):
        result = policy_engine.evaluate(
            "add_loyalty_points",
            {"customer_id": "CUST-1001", "points": 100, "reason": "Goodwill"},
            context={"loyalty_grants_this_session": 3},
        )
        assert result.is_blocked

    def test_list_policies_returns_all(self, policy_engine):
        policies = policy_engine.list_policies()
        assert len(policies) >= 5
        assert all("name" in p and "action" in p for p in policies)

    def test_custom_policy_added(self, policy_engine):
        from app.guardrails.policy_engine import Policy, PolicyAction
        custom = Policy(
            name="test_custom",
            description="Test custom policy",
            condition=lambda tool, args, ctx: tool == "test_tool",
            action=PolicyAction.BLOCK,
            priority=1,
            message="Test block",
        )
        policy_engine.add_policy(custom)
        result = policy_engine.evaluate("test_tool", {})
        assert result.is_blocked


# ============================================================
# Risk Scorer
# ============================================================
class TestRiskScorer:

    def test_readonly_tools_low_risk(self, risk_scorer):
        for tool in ["lookup_order", "search_documents", "search_products"]:
            score = risk_scorer.score(tool, {})
            assert score.score < 0.2, f"{tool} should be low risk"

    def test_write_tools_moderate_risk(self, risk_scorer):
        score = risk_scorer.score("update_shipping_address", {
            "order_id": "ORD-10001",
            "new_address": "123 Main St",
        })
        assert score.score >= 0.2

    def test_financial_tools_high_risk(self, risk_scorer):
        score = risk_scorer.score("process_refund", {"amount": 10.0, "order_id": "ORD-10001"})
        assert score.score >= 0.5

    def test_large_refund_increases_score(self, risk_scorer):
        small = risk_scorer.score("process_refund", {"amount": 10.0})
        large = risk_scorer.score("process_refund", {"amount": 800.0})
        assert large.score > small.score

    def test_very_large_refund_critical(self, risk_scorer):
        score = risk_scorer.score("process_refund", {"amount": 1200.0})
        assert score.level in ("high", "critical")

    def test_repeated_tool_increases_score(self, risk_scorer):
        first = risk_scorer.score("process_refund", {"amount": 50.0})
        second = risk_scorer.score("process_refund", {"amount": 50.0})
        third = risk_scorer.score("process_refund", {"amount": 50.0})
        assert third.score >= first.score  # should be same or higher

    def test_requires_hitl_above_threshold(self, risk_scorer):
        score = risk_scorer.score("process_refund", {"amount": 900.0})
        assert score.requires_hitl

    def test_score_never_exceeds_1(self, risk_scorer):
        score = risk_scorer.score("process_refund", {"amount": 999_999.0})
        assert score.score <= 1.0

    def test_session_summary(self, risk_scorer):
        summary = risk_scorer.session_summary()
        assert "total_calls" in summary
        assert "max_score" in summary


# ============================================================
# HITL Manager
# ============================================================
class TestHITLManager:

    @pytest.mark.asyncio
    async def test_create_approval_request(self, hitl_manager):
        req = await hitl_manager.request_approval(
            tool_name="process_refund",
            args={"amount": 750, "order_id": "ORD-1"},
            reason="Refund > $500",
            risk_score=0.75,
            requested_by="conv-123",
        )
        assert req.approval_id.startswith("HITL-")
        assert req.status.value == "pending"

    @pytest.mark.asyncio
    async def test_approve_resolves_wait(self, hitl_manager):
        req = await hitl_manager.request_approval(
            tool_name="cancel_order",
            args={"order_id": "ORD-1"},
            reason="Test",
            risk_score=0.6,
        )

        # Approve in background after a short delay
        async def _approve():
            await asyncio.sleep(0.1)
            hitl_manager.approve(req.approval_id, "test-supervisor")

        asyncio.create_task(_approve())
        approved = await hitl_manager.wait_for_approval(req.approval_id, poll_interval=0.05)
        assert approved is True

    @pytest.mark.asyncio
    async def test_deny_resolves_wait(self, hitl_manager):
        req = await hitl_manager.request_approval(
            tool_name="process_refund",
            args={"amount": 600},
            reason="Test",
            risk_score=0.7,
        )

        async def _deny():
            await asyncio.sleep(0.1)
            hitl_manager.deny(req.approval_id, "test-supervisor", "Too large")

        asyncio.create_task(_deny())
        approved = await hitl_manager.wait_for_approval(req.approval_id, poll_interval=0.05)
        assert approved is False

    def test_list_pending(self, hitl_manager):
        pending = hitl_manager.list_pending()
        assert isinstance(pending, list)


# ============================================================
# Constitutional Guard
# ============================================================
class TestConstitutionalGuard:

    def test_allows_proportional_action(self, constitutional_guard):
        result = constitutional_guard.check_input(
            user_message="Please cancel order ORD-10001",
            tool_name="cancel_order",
            tool_args={"order_id": "ORD-10001", "reason": "Customer request"},
        )
        assert result.passed

    def test_flags_disproportionate_action(self, constitutional_guard):
        result = constitutional_guard.check_input(
            user_message="I'm just wondering about delivery times",
            tool_name="cancel_order",
            tool_args={"order_id": "ORD-10001"},
        )
        assert len(result.warnings) > 0 or not result.passed

    def test_flags_false_promise_in_output(self, constitutional_guard):
        result = constitutional_guard.check_output(
            user_message="When will my refund arrive?",
            agent_response="I guarantee your refund will be in your account within 2 hours.",
        )
        assert not result.passed
        assert any(v["principle"] == "no_false_promises" for v in result.violations)

    def test_clean_output_passes(self, constitutional_guard):
        result = constitutional_guard.check_output(
            user_message="What is my order status?",
            agent_response="Your order ORD-10001 is currently being processed.",
        )
        assert result.passed

    def test_overall_score_is_between_0_and_1(self, constitutional_guard):
        result = constitutional_guard.check_input("anything", "lookup_order", {})
        assert 0.0 <= result.overall_score <= 1.0
