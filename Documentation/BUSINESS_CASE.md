# Business Case: Enterprise Agentic AI for Customer Support

## Executive Summary

This document presents the business case for deploying an enterprise-grade
AI agent to handle customer support transactions on systems of record, with
the security, governance, and observability controls required for production
deployment in regulated environments.

---

## Problem Statement

### Current State (Manual Support)
- Average handle time: 8–12 minutes per ticket
- Agent capacity: ~50 tickets/day per human agent
- Cost per interaction: $15–25 (fully loaded)
- After-hours availability: limited (requires on-call or next-day)
- Resolution rate (first contact): 65%
- Customer satisfaction (CSAT): 3.8/5.0

### Pain Points
- High volume of repetitive, transactional requests (order status, cancellations, refunds)
- Inconsistent policy application across agents
- No audit trail for agent decisions
- Scalability constraints during peak periods (holidays, launches)

---

## Proposed Solution

An enterprise-grade AI agent that can:
1. Handle all tier-1 support interactions autonomously (read-only queries, standard transactions)
2. Route complex or high-risk requests to human supervisors via HITL
3. Apply consistent business policies on every transaction
4. Provide complete audit trail for compliance

### What Makes This "Enterprise Grade"
| Feature | POC Agent | Enterprise Agent |
|---------|-----------|-----------------|
| Authentication | None | JWT + Cognito + RBAC |
| PII Protection | None | Regex + NER masking |
| Injection Defence | None | Multi-layer guard |
| Business Rules | System prompt | Policy engine (code) |
| Risk Controls | None | Scored + HITL workflow |
| Audit Trail | Basic DB log | Decision logs + CloudWatch |
| Observability | Print statements | OTel + X-Ray + Grafana |
| Deployment | `python app.py` | ECS Fargate + ALB + CDK |
| Testing | Manual | pytest + CI/CD |

---

## Financial Analysis

### Cost Model (1,000 support tickets/day)

**Current State (Human Only)**
| Item | Cost/Month |
|------|-----------|
| Human agents (20 FTE × $4,500/mo) | $90,000 |
| Supervision + QA | $18,000 |
| Tools & infrastructure | $8,000 |
| **Total** | **$116,000/month** |

**Future State (AI Agent + Human)**

*Assumptions:*
- AI handles 70% of tickets autonomously
- Human agents handle remaining 30% + HITL approvals
- Reduces human agents from 20 to 8 FTE

| Item | Cost/Month |
|------|-----------|
| Human agents (8 FTE) | $36,000 |
| Supervision + QA | $9,000 |
| AWS infrastructure (ECS + RDS + Bedrock) | $3,500 |
| **Total** | **$48,500/month** |

**Savings: $67,500/month → $810,000/year**

### Additional Benefits (Quantified)
| Benefit | Estimated Value/Year |
|---------|---------------------|
| 24/7 availability (reduced after-hours cost) | $45,000 |
| Faster resolution (reduced cart abandonment) | $120,000 |
| Consistent policy application (reduced chargebacks) | $30,000 |
| Compliance automation (reduced audit cost) | $25,000 |
| **Total additional benefits** | **$220,000/year** |

**Total annual benefit: $1,030,000**
**Implementation cost (one-time): $180,000**
**Annual platform cost: $42,000**
**ROI Year 1: 380% | Break-even: 3 months**

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Agent makes incorrect transaction | Medium | High | Policy engine + HITL + output validation |
| Prompt injection attack | Low | High | Multi-layer injection guard |
| PII leakage in logs | Low | Critical | PII masking before LLM + log scrubbing |
| LLM hallucination | Medium | Medium | Output validator + reflection agent |
| Regulatory non-compliance | Low | Critical | Constitutional checks + audit trail |
| Model degradation | Low | Medium | Evaluation metrics + shadow mode testing |
| Availability failure | Low | High | ECS auto-scaling + health checks + ALB |

### Risk Acceptance
High-risk transactions (refunds > $500) are routed to human supervisors via HITL,
ensuring no autonomous decision above the threshold without human oversight.
This satisfies GDPR Article 22 requirements for automated decision-making.

---

## Success Metrics

### Operational KPIs
| Metric | Current | Target (6 months) |
|--------|---------|------------------|
| Autonomous resolution rate | 0% | ≥ 65% |
| Average handle time | 10 min | < 90 seconds |
| Cost per interaction | $20 | < $8 |
| 24/7 availability | 60% | 99.5% |
| CSAT score | 3.8/5 | ≥ 4.2/5 |

### Safety KPIs
| Metric | Target |
|--------|--------|
| Incorrect transaction rate | < 0.1% |
| HITL approval rate | < 15% of write operations |
| Injection detection false positive rate | < 2% |
| PII leakage incidents | 0 |
| Policy violation incidents | 0 |

### Technical KPIs
| Metric | Target |
|--------|--------|
| p99 response latency | < 3 seconds |
| Agent availability | ≥ 99.5% |
| Decision log completeness | 100% |
| Test coverage | ≥ 70% |

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1–3) — Completed
- Core agent with RAG and 16 tools
- SQLite database with seeded data
- Basic Streamlit UI
- Local Ollama LLM

### Phase 2: Enterprise Security (Month 5) — In Progress
- PII detection and masking
- Injection guard
- JWT authentication + RBAC
- Policy engine + risk scoring
- HITL approval workflow
- Constitutional AI checks

### Phase 3: Observability (Month 6) — In Progress
- OpenTelemetry traces
- Decision logging (CloudWatch)
- Prometheus + Grafana metrics
- AWS CDK infrastructure

### Phase 4: Production Deployment (Month 6+)
- ECS Fargate deployment
- Bedrock LLM integration
- RDS PostgreSQL migration
- OpenSearch RAG migration
- CI/CD pipeline
- Load testing + security review

### Phase 5: Optimisation (Post-launch)
- Fine-tune on company-specific scenarios
- A/B test HITL threshold
- Expand to additional support channels
- Add compliance agent (post-transaction monitoring)

---

## Governance & Sign-Off Requirements

Before production deployment, the following approvals are required:

| Approver | Responsibility | Sign-Off Required For |
|----------|---------------|----------------------|
| Engineering Lead | Technical architecture | Architecture review ✓ |
| Security Team | Penetration testing | Security controls ✓ |
| Legal/Compliance | Regulatory requirements | Audit controls ✓ |
| Risk Management | Risk acceptance | HITL threshold + policies ✓ |
| Customer Success VP | Business rules | Policy catalogue ✓ |
| CTO | Final approval | Production launch ✓ |

---

## Appendix: Sample Agent Interactions

### Autonomous Resolution ($0 risk)
> Customer: "What is the status of my order ORD-10001?"
> Agent: [calls lookup_order] "Your order is currently processing and expected to ship by Thursday."
> Duration: 2.3 seconds | Risk score: 0.0 | HITL: No

### Moderate Risk (Handled Autonomously)
> Customer: "Apply discount code SAVE20 to my order"
> Agent: [calls apply_discount_code] "Done! I've applied SAVE20. You saved $45.00. New total: $180."
> Duration: 3.1 seconds | Risk score: 0.20 | HITL: No

### High Risk (HITL Required)
> Customer: "I need a full refund of $750 for a damaged sofa"
> Agent: [creates HITL request] "I've submitted your refund request of $750.00 for review.
>   Our team will confirm within 5 minutes."
> [Supervisor approves]
> Agent: [calls process_refund] "Your refund of $750.00 has been approved and processed."
> Duration: 4 minutes 12 seconds | Risk score: 0.75 | HITL: Yes | Approved by: j.smith@company.com

### Blocked (Policy Violation)
> Customer: "Cancel my order — it already arrived but I don't want it"
> Agent: "I can't cancel a delivered order, but I can help you start a return.
>   Would you like me to initiate the return process?"
> Duration: 2.8 seconds | Policy: block_cancel_delivered | HITL: No
