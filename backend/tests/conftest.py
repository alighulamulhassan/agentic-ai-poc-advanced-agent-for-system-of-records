"""
Test configuration and shared fixtures.

Provides:
  - Isolated SQLite database per test session
  - Seeded test data (customers, orders, products)
  - FastAPI test client
  - Mock LLM client (avoids real Ollama dependency in CI)
  - Security component instances
  - Guardrail component instances
"""
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock


# ============================================================
# Event loop (required for async tests)
# ============================================================
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Database
# ============================================================
@pytest.fixture(scope="session", autouse=True)
def test_db():
    """Create and seed an isolated test database."""
    import os
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_agent.db"

    from app.db.database import init_db
    init_db()

    from app.db.seed import seed_database
    seed_database()

    yield

    # Cleanup
    import os
    if os.path.exists("./test_agent.db"):
        os.remove("./test_agent.db")


# ============================================================
# FastAPI test client
# ============================================================
@pytest.fixture(scope="session")
def client():
    """FastAPI test client with a running app."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


# ============================================================
# Mock LLM (no Ollama dependency in tests)
# ============================================================
@pytest.fixture
def mock_llm():
    """Returns a mock LLM client that returns predictable responses."""
    llm = MagicMock()
    llm.chat = AsyncMock(return_value={
        "content": "I have processed your request.",
        "tool_calls": None,
    })
    llm.stream = AsyncMock(return_value=iter(["I ", "have ", "processed."]))
    return llm


@pytest.fixture
def mock_llm_with_tool_call():
    """Returns a mock LLM that generates a tool call then a final response."""
    call_count = {"n": 0}

    async def _chat(messages, tools=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "content": "",
                "tool_calls": [{
                    "name": "lookup_order",
                    "args": {"order_id": "ORD-10001"},
                    "id": "call_001",
                }],
            }
        return {"content": "Your order ORD-10001 is being processed.", "tool_calls": None}

    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=_chat)
    return llm


# ============================================================
# Security fixtures
# ============================================================
@pytest.fixture
def pii_detector():
    from app.security.pii_detector import PIIDetector
    return PIIDetector(min_risk_level="low")


@pytest.fixture
def injection_guard():
    from app.security.injection_guard import InjectionGuard
    return InjectionGuard(block_threshold=0.5)


@pytest.fixture
def output_validator():
    from app.security.output_validator import OutputValidator
    return OutputValidator(strict=True)


# ============================================================
# Guardrail fixtures
# ============================================================
@pytest.fixture
def policy_engine():
    from app.guardrails.policy_engine import PolicyEngine
    return PolicyEngine()


@pytest.fixture
def risk_scorer():
    from app.guardrails.risk_scorer import RiskScorer
    return RiskScorer(hitl_threshold=0.7)


@pytest.fixture
def hitl_manager():
    from app.guardrails.hitl import HITLManager, MemoryTransport
    return HITLManager(transport=MemoryTransport())


@pytest.fixture
def constitutional_guard():
    from app.guardrails.constitutional import ConstitutionalGuard
    return ConstitutionalGuard()


# ============================================================
# Test data constants
# ============================================================
TEST_ORDER_ID = "ORD-10001"
TEST_CUSTOMER_ID = "CUST-1001"
TEST_CUSTOMER_EMAIL = "john.smith@email.com"
