"""
Human-in-the-Loop (HITL) — pause high-risk agent actions for human approval.

When the risk scorer or policy engine flags an action as requiring approval,
execution is PAUSED and an approval request is created. A human supervisor
must APPROVE or DENY within the timeout window.

Transport options (select via HITL_TRANSPORT env var):
  - "memory"   — in-process dict (development, testing)
  - "webhook"  — HTTP POST to a Slack/Teams/PagerDuty webhook
  - "sns"      — AWS SNS topic (production)
  - "ses"      — AWS SES email (production)

Session for audience:
  - Knowledge fuel: HITL patterns in agentic AI, supervisor-agent loops
  - Lab: implement the SNSTransport class to send real approval requests
        to an AWS SNS topic that triggers a Lambda approval workflow
"""
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HITL_TIMEOUT_SECONDS = int(os.getenv("HITL_TIMEOUT_SECONDS", "300"))  # 5 min default
HITL_TRANSPORT = os.getenv("HITL_TRANSPORT", "memory")
HITL_WEBHOOK_URL = os.getenv("HITL_WEBHOOK_URL", "")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"   # used when HITL is bypassed in dev


@dataclass
class ApprovalRequest:
    approval_id: str
    tool_name: str
    args: Dict[str, Any]
    reason: str
    risk_score: float
    requested_by: str                  # conversation_id or user sub
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    denial_reason: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > HITL_TIMEOUT_SECONDS and self.status == ApprovalStatus.PENDING

    def to_dict(self) -> Dict:
        return {
            "approval_id": self.approval_id,
            "tool_name": self.tool_name,
            "args": self.args,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "denial_reason": self.denial_reason,
        }


# ---------------------------------------------------------------------------
# Transport interface
# ---------------------------------------------------------------------------
class HITLTransport:
    """Base class for HITL notification transports."""

    async def send_approval_request(self, request: ApprovalRequest) -> None:
        raise NotImplementedError

    async def send_resolution(self, request: ApprovalRequest) -> None:
        raise NotImplementedError


class MemoryTransport(HITLTransport):
    """In-process transport for development. Logs to console."""

    async def send_approval_request(self, request: ApprovalRequest) -> None:
        logger.warning(
            f"\n{'='*60}\n"
            f"⚠️  HITL APPROVAL REQUIRED\n"
            f"  ID:      {request.approval_id}\n"
            f"  Tool:    {request.tool_name}\n"
            f"  Args:    {request.args}\n"
            f"  Risk:    {request.risk_score:.2f}\n"
            f"  Reason:  {request.reason}\n"
            f"  Approve: POST /api/hitl/approve/{request.approval_id}\n"
            f"  Deny:    POST /api/hitl/deny/{request.approval_id}\n"
            f"{'='*60}"
        )

    async def send_resolution(self, request: ApprovalRequest) -> None:
        logger.info(
            f"HITL resolved | id={request.approval_id} | "
            f"status={request.status.value} | by={request.resolved_by}"
        )


class WebhookTransport(HITLTransport):
    """HTTP webhook transport (Slack, Teams, PagerDuty)."""

    async def send_approval_request(self, request: ApprovalRequest) -> None:
        if not HITL_WEBHOOK_URL:
            logger.warning("HITL_WEBHOOK_URL not configured — falling back to log")
            return

        try:
            import httpx
            payload = {
                "text": (
                    f"🚨 *HITL Approval Required*\n"
                    f"*Tool:* `{request.tool_name}`\n"
                    f"*Args:* `{request.args}`\n"
                    f"*Risk:* `{request.risk_score:.2f}`\n"
                    f"*Reason:* {request.reason}\n"
                    f"*Approval ID:* `{request.approval_id}`"
                )
            }
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(HITL_WEBHOOK_URL, json=payload)
        except Exception as exc:
            logger.error(f"Webhook notification failed: {exc}")

    async def send_resolution(self, request: ApprovalRequest) -> None:
        pass  # optionally notify on resolution


class SNSTransport(HITLTransport):
    """
    AWS SNS transport for production HITL.

    TODO (Lab — Month 5 Session 2):
    Implement this class to:
      1. Publish the ApprovalRequest to an SNS topic as a JSON message
      2. SNS triggers a Lambda that sends a Slack DM to on-call supervisor
      3. Supervisor clicks Approve/Deny link → Lambda updates DynamoDB
      4. HITLManager polls DynamoDB for resolution

    Steps:
      a. Create an SNS topic: aws sns create-topic --name agent-hitl-approvals
      b. Set HITL_SNS_TOPIC_ARN and HITL_APPROVAL_TABLE env vars
      c. Implement publish_to_sns() using boto3.client('sns').publish()
      d. Implement poll_dynamodb() in HITLManager.wait_for_approval()

    Why SNS: decouples the agent from the approval UI, supports multiple
    subscribers (email + Slack + PagerDuty) without code changes.
    """

    async def send_approval_request(self, request: ApprovalRequest) -> None:
        topic_arn = os.getenv("HITL_SNS_TOPIC_ARN", "")
        if not topic_arn:
            logger.warning("HITL_SNS_TOPIC_ARN not set — SNS transport inactive")
            return

        try:
            import boto3, json
            sns = boto3.client("sns")
            sns.publish(
                TopicArn=topic_arn,
                Subject=f"Agent HITL Approval Required: {request.tool_name}",
                Message=json.dumps(request.to_dict()),
                MessageAttributes={
                    "tool_name": {"DataType": "String", "StringValue": request.tool_name},
                    "risk_score": {"DataType": "Number", "StringValue": str(request.risk_score)},
                },
            )
            logger.info(f"HITL approval request published to SNS | id={request.approval_id}")
        except Exception as exc:
            logger.error(f"SNS publish failed: {exc}")

    async def send_resolution(self, request: ApprovalRequest) -> None:
        pass


# ---------------------------------------------------------------------------
# HITL Manager
# ---------------------------------------------------------------------------
class HITLManager:
    """
    Manages the full HITL approval lifecycle:
      create → notify → wait → resolve → execute or block

    Usage:
        manager = get_hitl_manager()
        req = await manager.request_approval(
            tool_name="process_refund",
            args={"amount": 750, "order_id": "ORD-1"},
            reason="Refund > $500",
            risk_score=0.75,
            requested_by=conversation_id,
        )
        approved = await manager.wait_for_approval(req.approval_id)
        if approved:
            result = await execute_tool(tool_name, args)
    """

    def __init__(self, transport: Optional[HITLTransport] = None):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._transport = transport or self._build_transport()

    @staticmethod
    def _build_transport() -> HITLTransport:
        t = HITL_TRANSPORT.lower()
        if t == "webhook":
            return WebhookTransport()
        if t == "sns":
            return SNSTransport()
        return MemoryTransport()

    async def request_approval(
        self,
        tool_name: str,
        args: Dict[str, Any],
        reason: str,
        risk_score: float,
        requested_by: str = "agent",
    ) -> ApprovalRequest:
        """Create and broadcast an approval request."""
        req = ApprovalRequest(
            approval_id=f"HITL-{uuid.uuid4().hex[:10].upper()}",
            tool_name=tool_name,
            args=args,
            reason=reason,
            risk_score=risk_score,
            requested_by=requested_by,
        )
        self._requests[req.approval_id] = req
        await self._transport.send_approval_request(req)
        logger.info(f"HITL request created | {req.approval_id}")
        return req

    async def wait_for_approval(
        self,
        approval_id: str,
        poll_interval: float = 2.0,
    ) -> bool:
        """
        Poll for approval resolution until timeout.

        In production with SNS/DynamoDB, replace this polling loop with
        a long-poll against DynamoDB or an event-driven callback.

        Returns:
            True if approved, False if denied or timed out
        """
        deadline = datetime.now(timezone.utc) + timedelta(seconds=HITL_TIMEOUT_SECONDS)

        while datetime.now(timezone.utc) < deadline:
            req = self._requests.get(approval_id)
            if req is None:
                logger.error(f"HITL request not found: {approval_id}")
                return False

            if req.status == ApprovalStatus.APPROVED:
                return True
            if req.status in (ApprovalStatus.DENIED, ApprovalStatus.TIMEOUT):
                return False

            await asyncio.sleep(poll_interval)

        # Timeout
        req = self._requests.get(approval_id)
        if req and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.TIMEOUT
            req.resolved_at = datetime.now(timezone.utc)
            logger.warning(f"HITL approval timed out | {approval_id}")

        return False

    def approve(self, approval_id: str, approved_by: str = "supervisor") -> bool:
        """Mark an approval request as approved."""
        req = self._requests.get(approval_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.APPROVED
        req.resolved_at = datetime.now(timezone.utc)
        req.resolved_by = approved_by
        logger.info(f"HITL approved | {approval_id} | by={approved_by}")
        return True

    def deny(self, approval_id: str, denied_by: str, reason: str = "") -> bool:
        """Mark an approval request as denied."""
        req = self._requests.get(approval_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.DENIED
        req.resolved_at = datetime.now(timezone.utc)
        req.resolved_by = denied_by
        req.denial_reason = reason
        logger.info(f"HITL denied | {approval_id} | by={denied_by} | reason={reason}")
        return True

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(approval_id)

    def list_pending(self) -> list:
        return [
            r.to_dict() for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING and not r.is_expired
        ]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_manager: Optional[HITLManager] = None


def get_hitl_manager() -> HITLManager:
    global _manager
    if _manager is None:
        _manager = HITLManager()
    return _manager
