# Enterprise Agent — Architecture Document

## Overview

This document describes the target-state architecture for the Enterprise Agentic AI
system for System of Records, developed as the Month 5–6 capstone of the
6-Month Agentic AI Series.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                    │
│                                                                      │
│  ┌───────────┐   ┌─────────────────────────────────────────────┐   │
│  │  Cognito  │──▶│     WAF + ALB (rate limit, TLS, auth)       │   │
│  │ User Pool │   └──────────────────────┬──────────────────────┘   │
│  └───────────┘                          │                            │
│                                         │                            │
│              ┌──────────────────────────▼──────────────────────┐   │
│              │            ECS Fargate Service (2+ tasks)         │   │
│              │                                                    │   │
│              │  ┌─────────────────────────────────────────────┐ │   │
│              │  │           Security Layer                      │ │   │
│              │  │  PII mask → Injection guard → JWT auth        │ │   │
│              │  └─────────────────┬───────────────────────────┘ │   │
│              │                    │                               │   │
│              │  ┌─────────────────▼───────────────────────────┐ │   │
│              │  │         Agent Orchestrator                    │ │   │
│              │  │    (Supervisor → route → Specialist)          │ │   │
│              │  │                                               │ │   │
│              │  │  ┌─────────────┐   ┌──────────────────────┐ │ │   │
│              │  │  │ Query Agent │   │ Transaction Agent     │ │ │   │
│              │  │  │ (read-only) │   │ (write + guardrails)  │ │ │   │
│              │  │  └─────────────┘   └──────────────────────┘ │ │   │
│              │  └─────────────────┬───────────────────────────┘ │   │
│              │                    │                               │   │
│              │  ┌─────────────────▼───────────────────────────┐ │   │
│              │  │          Guardrails Engine                    │ │   │
│              │  │  Policy DSL → Risk Score → HITL → Reflect    │ │   │
│              │  └─────────────────┬───────────────────────────┘ │   │
│              │                    │                               │   │
│              │  ┌─────────────────▼───────────────────────────┐ │   │
│              │  │           MCP Tool Registry                   │ │   │
│              │  │  16 tools: lookup, refund, cancel, discount…  │ │   │
│              │  └──────────┬────────────────────────────────────┘ │   │
│              └─────────────┼──────────────────────────────────────┘   │
│                            │                                           │
│         ┌──────────────────┼──────────────────┐                      │
│         │                  │                   │                      │
│  ┌──────▼──────┐  ┌────────▼─────┐  ┌────────▼──────┐             │
│  │ Aurora PG   │  │  OpenSearch  │  │  ElastiCache  │             │
│  │ (SoR data)  │  │ (RAG vectors)│  │    Redis      │             │
│  └─────────────┘  └──────────────┘  └───────────────┘             │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Observability: X-Ray + CloudWatch Logs + CloudWatch Metrics  │  │
│  │  Honeycomb traces + Grafana dashboards + EventBridge alerts   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### 1. Security Layer
| Component | File | Purpose |
|-----------|------|---------|
| PII Detector | `app/security/pii_detector.py` | Mask emails, phones, SSNs, card numbers before LLM |
| Injection Guard | `app/security/injection_guard.py` | Block prompt injection attempts |
| Output Validator | `app/security/output_validator.py` | Schema + business rule validation on LLM outputs |
| Auth | `app/security/auth.py` | JWT bearer + API key auth, RBAC for tool access |

### 2. Agent Orchestration
| Component | File | Purpose |
|-----------|------|---------|
| Supervisor | `app/core/orchestrator.py` | Routes to Query or Transaction specialist |
| Query Agent | `app/core/orchestrator.py` | Read-only lookups (6 tools) |
| Transaction Agent | `app/core/orchestrator.py` | Write operations (16 tools + full guardrails) |
| Main Agent | `app/core/agent.py` | Single-agent mode with full pipeline |

### 3. Guardrails Engine
| Component | File | Purpose |
|-----------|------|---------|
| Policy Engine | `app/guardrails/policy_engine.py` | Declarative business rules (allow/block/approve) |
| Risk Scorer | `app/guardrails/risk_scorer.py` | 0.0–1.0 risk score per tool call |
| HITL Manager | `app/guardrails/hitl.py` | Pause → notify → wait → execute |
| Reflection Agent | `app/guardrails/reflection.py` | Self-verification of tool call plan |
| Constitutional Guard | `app/guardrails/constitutional.py` | Principle-based input/output checks |

### 4. Observability
| Component | File | Purpose |
|-----------|------|---------|
| Telemetry | `app/observability/telemetry.py` | `@instrument` decorator, span tracking |
| Decision Logger | `app/observability/decision_logger.py` | JSON Lines audit log per agent turn |
| Metrics | `app/observability/metrics.py` | Counters, histograms, CloudWatch EMF |
| Tracer | `app/observability/tracer.py` | OpenTelemetry, X-Ray, W3C header propagation |

### 5. Advanced Patterns
| Component | File | Purpose |
|-----------|------|---------|
| A2A Protocol | `app/core/a2a_protocol.py` | Standardised inter-agent messaging |
| MCP Server | `app/core/mcp_server.py` | Tools, resources, prompts via MCP spec |

---

## Data Flow: Single Request

```
User Message
    │
    ▼
1. PII Detection → mask sensitive data
    │
    ▼
2. Injection Guard → block if attack detected
    │
    ▼
3. LLM Call (Bedrock/Ollama) → generates tool call plan
    │
    ▼
4. Reflection → LLM reviews its own plan
    │
    ▼
For each tool call:
    ├── Constitutional input check
    ├── Output validation (schema + business rules)
    ├── Policy engine evaluation → ALLOW / BLOCK / REQUIRE_APPROVAL
    ├── Risk scoring
    ├── If risk >= 0.7 → HITL approval request → wait
    └── Tool execution
    │
    ▼
5. Final LLM response generation
    │
    ▼
6. Constitutional output check
    │
    ▼
7. Decision log committed (JSON Lines → CloudWatch)
    │
    ▼
Response to User
```

---

## Infrastructure

### CDK Stacks

| Stack | Resources | Deploy Order |
|-------|-----------|-------------|
| `AgentSecurityStack` | Cognito, WAF, Secrets Manager | 1 |
| `AgentDataStack` | VPC, RDS Aurora PG, Redis, OpenSearch, S3 | 2 |
| `AgentAppStack` | ECR, ECS Fargate, ALB, CloudWatch, X-Ray, SNS | 3 |

### Environment Progression

```
Local Development          Staging                  Production
─────────────────          ───────                  ──────────
SQLite                     RDS (small)              RDS (auto-scaling)
ChromaDB                   OpenSearch               OpenSearch (HA)
Ollama (local LLM)         Ollama / Bedrock         Bedrock
MemoryTransport (HITL)     WebhookTransport         SNSTransport
Log files                  CloudWatch (basic)        CloudWatch + X-Ray + Honeycomb
docker compose up          cdk deploy (staging)     cdk deploy (prod) + blue/green
```

---

## API Reference

### Core Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat/completions` | Main chat endpoint (full guardrail pipeline) |
| GET | `/health` | Health check |
| GET | `/api/metrics` | Metrics snapshot |
| GET | `/api/policies` | List registered guardrail policies |

### HITL Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/hitl/pending` | List pending approval requests |
| POST | `/api/hitl/approve/{id}` | Approve an action |
| POST | `/api/hitl/deny/{id}` | Deny an action |

### MCP Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcp/tools` | List all tools in MCP format |
| POST | `/mcp/tools/{name}` | Invoke a tool via MCP |
| GET | `/mcp/resources` | List available resources |
| GET | `/mcp/prompts` | List available prompts |

---

## Security Architecture

### Authentication
- **External users**: Cognito User Pool → JWT token → `Authorization: Bearer <token>`
- **Internal services**: API key → `X-API-Key: <key>` header
- **Development**: Dev fallback (no auth required, set `ENVIRONMENT=development`)

### Authorization (RBAC)
| Role | Allowed Operations |
|------|--------------------|
| `readonly` | All lookup/search tools |
| `agent` | All tools (read + write) |
| `supervisor` | All tools + HITL approval |
| `admin` | All tools + admin operations |

### Data Protection
- PII masking before LLM context
- Encrypted secrets via Secrets Manager (never in env vars in production)
- RDS encrypted at rest (AES-256)
- TLS in transit (ALB → ECS, ECS → RDS)
- WAF blocks malicious traffic before it reaches the agent

---

## Compliance & Audit

### Audit Trail
Every agent action is recorded in two places:
1. **DB audit_logs table**: old_value / new_value for every transaction
2. **CloudWatch /agent/decisions**: full JSON decision log per agent turn

### Retention
| Log Type | Retention |
|----------|-----------|
| Application logs | 30 days |
| Decision logs | 90 days |
| Audit DB table | Indefinite (RETAIN) |
| CloudTrail | 365 days |

### Compliance Mapping
| Regulation | Relevant Controls |
|-----------|------------------|
| GDPR Art. 25 | PII masking, data minimisation principle |
| GDPR Art. 22 | Human-in-the-loop for automated decisions |
| PCI-DSS | Credit card PII detection and masking |
| SOX | Immutable audit trail, approval workflows |
| HIPAA | PII masking, encrypted data, access controls |
