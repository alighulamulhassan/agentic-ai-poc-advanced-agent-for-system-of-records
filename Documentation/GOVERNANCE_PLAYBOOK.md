# Agent Governance Playbook

## Purpose

This playbook defines the operating procedures, policies, and controls for
deploying and running AI agents that perform transactions on systems of record.

It is intended for:
- **Engineering teams** building and deploying agents
- **Risk/Compliance teams** evaluating agent deployments
- **Operations teams** running agents in production
- **Auditors** reviewing agent activity

---

## 1. Agent Authority Levels

Every agent instance is assigned an authority level that determines what
it can do autonomously vs. what requires human approval.

| Level | Description | Auto-Execute | Requires Approval | Cannot Do |
|-------|-------------|-------------|------------------|-----------|
| **L0 — Read Only** | Information retrieval | All lookup tools | — | Any write operation |
| **L1 — Low Risk** | Minor modifications | Discount codes, loyalty points ≤1k, address changes | — | Cancellations, refunds |
| **L2 — Standard** | Full customer support | All L1 + cancellations, refunds ≤$500 | Refunds $500–$1,000 | Refunds >$1,000 |
| **L3 — Extended** | Supervised escalation | All L2 + refunds up to $1,000 | Refunds >$1,000 | Bulk operations |

The production agent operates at **L2** by default.

---

## 2. Policy Catalogue

The following policies are enforced by the Policy Engine before every tool call.

### Hard Blocks (cannot be overridden)
| Policy | Trigger | Action |
|--------|---------|--------|
| `block_excessive_refund` | Refund > $1,000 | BLOCK |
| `block_cancel_delivered` | Cancel a delivered order | BLOCK |
| `block_status_regression` | Move terminal order to processing | BLOCK |
| `block_address_after_shipped` | Change address after shipment | BLOCK |
| `block_loyalty_grant_flood` | >3 loyalty grants per session | BLOCK |

### Approval Required
| Policy | Trigger | Approver |
|--------|---------|---------|
| `approve_large_refund` | Refund $500–$1,000 | On-call supervisor |

### Warnings (logged, not blocked)
| Policy | Trigger |
|--------|---------|
| `warn_excessive_loyalty_points` | >10,000 points in one grant |

---

## 3. Risk Scoring Framework

Every tool call receives a risk score from 0.0 to 1.0 before execution.

### Base Scores
| Category | Tools | Base Score |
|----------|-------|-----------|
| Read-only | lookup, search | 0.0–0.05 |
| Low-impact writes | address, expedite, discount | 0.15–0.30 |
| Financial | cancel, refund, loyalty | 0.40–0.60 |

### Score Adjustments
| Condition | Adjustment |
|-----------|-----------|
| Refund > $100 | +0.10 |
| Refund > $500 | +0.20 |
| Refund > $1,000 | +0.30 |
| Same tool called 2+ times | +0.10 |
| Same tool called 4+ times | +0.25 |
| `readonly` role attempting write | +0.20 |

### HITL Threshold
- **Default**: 0.70 (any score ≥ 0.70 pauses for human approval)
- **Development**: 0.90 (less interruption during testing)
- **High-stakes deployment**: 0.50

---

## 4. Human-in-the-Loop (HITL) Procedures

### When HITL is Triggered
1. Agent scores a tool call at ≥ 0.70
2. Policy engine marks action as `REQUIRE_APPROVAL`
3. Execution **pauses** — the action is NOT taken
4. Approval request created with full context
5. On-call supervisor notified (Slack/email/SMS)
6. Supervisor reviews and approves/denies within 5 minutes
7. Agent resumes or gracefully informs customer of delay

### Escalation Chain
```
Agent HITL Request
    └─► On-call Supervisor (5 min window)
            └─► If no response: Senior Supervisor (additional 5 min)
                    └─► If no response: Auto-DENY + customer callback
```

### Supervisor Responsibilities
- Review the full context (user message, tool call, order details)
- Approve only if the action aligns with company policy
- Document denial reason for every denied request
- Escalate unusual patterns (repeated requests, unusual amounts)

### HITL SLAs
| Priority | Response Time |
|----------|--------------|
| P1 (refund > $800) | 2 minutes |
| P2 (refund $500–$800) | 5 minutes |
| P3 (other) | 15 minutes |
| Default timeout | 5 minutes → auto-deny |

---

## 5. Incident Response

### Classification
| Severity | Definition | Example |
|----------|------------|---------|
| **SEV-1** | Unauthorized transaction > $1,000 | Agent processed $5,000 refund without approval |
| **SEV-2** | Policy bypass | Agent cancelled delivered order |
| **SEV-3** | Repeated anomaly | >5 HITL requests in 1 hour from same session |
| **SEV-4** | Quality issue | Customer received incorrect information |

### Response Steps
1. **Detect**: CloudWatch alarm fires or manual report
2. **Contain**: Disable affected agent conversation or temporarily raise HITL threshold to 0.0
3. **Assess**: Query decision logs in CloudWatch Logs Insights
4. **Remediate**: Roll back transaction via audit log compensating action
5. **Report**: Document in incident management system within 24 hours
6. **Review**: Post-mortem within 5 business days

---

## 6. Audit & Compliance

### What is Logged
Every agent turn produces:
- **DB audit_logs**: `action`, `entity_type`, `entity_id`, `old_value`, `new_value`, `performed_by`, `timestamp`
- **CloudWatch /agent/decisions**: Full JSON decision log including: `user_message` (PII-masked), `tool_calls`, `risk_scores`, `policy_actions`, `hitl_approval_id`, `constitutional_score`

### CloudWatch Queries for Auditors

**Find all refunds in a date range:**
```
fields @timestamp, conversation_id, decision_id
| filter tool_calls.0.tool_name = 'process_refund'
| filter @timestamp between 2024-01-01 and 2024-01-31
| sort @timestamp desc
```

**Find HITL approvals:**
```
fields @timestamp, conversation_id, decision_id
| filter tool_calls.0.hitl_approval_id like /HITL-/
| sort @timestamp desc
```

**Find PII detection events:**
```
fields @timestamp, conversation_id, pii_detected
| filter pii_detected = true
| stats count() by bin(1d) as day
```

### Monthly Compliance Review
- [ ] Review all SEV-1 and SEV-2 incidents
- [ ] Verify HITL approval records match DB audit_logs
- [ ] Check that PII masking is functioning (query `pii_detected` rate)
- [ ] Review policy engine trigger rates (should align with business expectations)
- [ ] Verify no refunds > $1,000 were auto-processed (should be zero)
- [ ] Review injection detection events for new attack patterns

---

## 7. Model Governance

### Approved Models
| Environment | Model | Provider | Approval Status |
|------------|-------|----------|----------------|
| Development | llama3.2 | Ollama (local) | ✅ Approved |
| Staging | claude-3-5-sonnet | AWS Bedrock | ✅ Approved |
| Production | claude-3-5-sonnet | AWS Bedrock | ✅ Approved |
| Production (fallback) | llama3.2 | Ollama (on-prem) | ✅ Approved |

### Model Change Process
1. Evaluate on standardised test suite (100+ scenarios)
2. Compare risk scores and HITL trigger rates
3. Security team reviews for new attack surface
4. Shadow mode deployment (new model runs in parallel, not executed)
5. Canary deployment (5% traffic, 48hr monitoring)
6. Full rollout with monitoring for 72 hours

### Prohibited Configurations
- Do not disable PII detection
- Do not set HITL threshold above 0.90 in production
- Do not disable the policy engine
- Do not grant `supervisor` or `admin` roles to automated service accounts

---

## 8. Change Management

### Adding a New Tool
1. Define tool in `registry.py` with clear docstring
2. Add tool-specific validation rules in `output_validator.py`
3. Set appropriate base risk score in `risk_scorer.py`
4. Determine if tool needs policy rules in `policy_engine.py`
5. Add unit tests covering the tool's happy path and error cases
6. Update this playbook with the new tool's authority level
7. Get sign-off from risk team before deploying

### Modifying a Policy
1. Document the business reason for the change
2. Update the policy in `policy_engine.py`
3. Write tests for the new policy logic
4. Get approval from risk team
5. Deploy to staging for 48 hours of monitoring
6. Deploy to production
7. Update this document

### Removing a Policy
- Removing a BLOCK policy requires VP-level approval
- Removing REQUIRE_APPROVAL policies requires director-level approval
- All policy removals must be documented with business justification
