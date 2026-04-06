"""
Enterprise Agent — Main FastAPI Application
Enhanced with Security, Guardrails, Observability, and MCP support.

Stack:
- LLM: Ollama (local) / Bedrock (production)
- Security: PII detection, injection guard, JWT auth, output validation
- Guardrails: Policy engine, risk scorer, HITL, reflection, constitutional AI
- Observability: OpenTelemetry, decision logger, CloudWatch metrics
- RAG: LangChain + ChromaDB → OpenSearch (production)
- DB: SQLite (dev) → RDS PostgreSQL (production)
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.routes import chat, documents, voice
from app.config import settings

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — init all subsystems."""
    logger.info("Starting Enterprise Agent...")
    logger.info(f"  LLM: {settings.llm_model} @ {settings.ollama_base_url}")
    logger.info(f"  Environment: {os.getenv('ENVIRONMENT', 'development')}")

    # Init database
    from app.db.database import init_db
    init_db()
    logger.info("  DB: initialized")

    # Seed if empty
    try:
        from app.db.seed import seed_database
        seed_database()
    except Exception as e:
        logger.warning(f"  Seed skipped: {e}")

    # Pre-load Whisper
    import threading
    def _preload_whisper():
        try:
            from app.voice.stt import get_whisper_model
            get_whisper_model()
            logger.info("  Whisper: loaded")
        except Exception as e:
            logger.warning(f"  Whisper preload failed: {e}")
    threading.Thread(target=_preload_whisper, daemon=True).start()

    # Log loaded guardrail policies
    try:
        from app.guardrails.policy_engine import get_policy_engine
        engine = get_policy_engine()
        policies = engine.list_policies()
        logger.info(f"  Guardrails: {len(policies)} policies loaded")
    except Exception as e:
        logger.warning(f"  Guardrails init failed: {e}")

    logger.info("Enterprise Agent ready.")
    yield
    logger.info("Shutting down Enterprise Agent...")


app = FastAPI(
    title="Enterprise Agent — System of Records",
    description="""
## Enterprise-Grade Agentic AI for System of Records

A capstone project demonstrating production-ready agent development:

### Security
- PII detection & masking
- Prompt injection detection
- JWT authentication & RBAC
- Output validation

### Guardrails
- Policy engine (business rule DSL)
- Risk scorer (0.0–1.0 per tool call)
- Human-in-the-loop (HITL) approval
- Constitutional AI checks
- Reflection / self-verification

### Observability
- OpenTelemetry distributed tracing
- Structured decision logging (JSON Lines)
- CloudWatch/Prometheus metrics
- Full audit trail

### Advanced Patterns
- Hierarchical orchestrator (Supervisor → Specialist)
- Agent-to-Agent (A2A) protocol
- Model Context Protocol (MCP) server
- Reflection loops

### Deployment
- Docker + AWS CDK
- ECS Fargate + RDS + OpenSearch
- CI/CD via GitHub Actions
    """,
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routes
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])

# MCP routes
try:
    from app.core.mcp_server import router as mcp_router
    app.include_router(mcp_router, tags=["MCP"])
    logger.info("MCP server enabled at /mcp")
except Exception as e:
    logger.warning(f"MCP server not available: {e}")


# ---------------------------------------------------------------------------
# HITL approval endpoints
# ---------------------------------------------------------------------------
class ApprovalAction(BaseModel):
    approved_by: str = "supervisor"
    reason: str = ""


@app.post("/api/hitl/approve/{approval_id}", tags=["HITL"])
async def approve_action(approval_id: str, action: ApprovalAction):
    """
    Approve a pending HITL action.

    Called by a supervisor to allow a high-risk agent action to proceed.
    In production this is triggered by a Lambda function after the
    supervisor clicks Approve in a Slack message or web UI.
    """
    from app.guardrails.hitl import get_hitl_manager
    manager = get_hitl_manager()
    success = manager.approve(approval_id, action.approved_by)
    if not success:
        return {"success": False, "error": "Approval request not found or already resolved"}
    return {"success": True, "approval_id": approval_id, "status": "approved"}


@app.post("/api/hitl/deny/{approval_id}", tags=["HITL"])
async def deny_action(approval_id: str, action: ApprovalAction):
    """Deny a pending HITL action."""
    from app.guardrails.hitl import get_hitl_manager
    manager = get_hitl_manager()
    success = manager.deny(approval_id, action.approved_by, action.reason)
    if not success:
        return {"success": False, "error": "Approval request not found or already resolved"}
    return {"success": True, "approval_id": approval_id, "status": "denied"}


@app.get("/api/hitl/pending", tags=["HITL"])
async def list_pending_approvals():
    """List all pending HITL approval requests."""
    from app.guardrails.hitl import get_hitl_manager
    return {"pending": get_hitl_manager().list_pending()}


# ---------------------------------------------------------------------------
# Observability endpoints
# ---------------------------------------------------------------------------
@app.get("/api/metrics", tags=["Observability"])
async def get_metrics():
    """Return current agent metrics snapshot."""
    from app.observability.metrics import get_metrics as _get_metrics
    return _get_metrics().snapshot()


@app.get("/api/policies", tags=["Guardrails"])
async def list_policies():
    """List all registered guardrail policies."""
    from app.guardrails.policy_engine import get_policy_engine
    return {"policies": get_policy_engine().list_policies()}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    from app.observability.metrics import get_metrics as _get_metrics
    metrics = _get_metrics().snapshot()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "llm": settings.llm_model,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "metrics": {
            "requests_total": metrics["requests"]["total"],
            "tool_calls_total": metrics["tools"]["total_calls"],
        },
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "name": "Enterprise Agent — System of Records",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "mcp": "/mcp",
        "hitl": "/api/hitl/pending",
        "metrics": "/api/metrics",
        "policies": "/api/policies",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
