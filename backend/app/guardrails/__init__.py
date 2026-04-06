"""
Guardrails engine for enterprise-grade agent governance.

Provides:
  - Policy DSL: declarative business rules evaluated before tool execution
  - Risk scorer: quantify the risk of each agent action
  - Human-in-the-loop (HITL): pause high-risk actions for human approval
  - Reflection: agent self-checks its plan before acting
  - Constitutional AI: pre/post-call principle enforcement
"""
from app.guardrails.policy_engine import PolicyEngine, PolicyResult, get_policy_engine
from app.guardrails.risk_scorer import RiskScorer, RiskScore, score_tool_call
from app.guardrails.hitl import HITLManager, ApprovalRequest, get_hitl_manager
from app.guardrails.reflection import ReflectionAgent
from app.guardrails.constitutional import ConstitutionalGuard

__all__ = [
    "PolicyEngine", "PolicyResult", "get_policy_engine",
    "RiskScorer", "RiskScore", "score_tool_call",
    "HITLManager", "ApprovalRequest", "get_hitl_manager",
    "ReflectionAgent",
    "ConstitutionalGuard",
]
