"""
Agent-to-Agent (A2A) Protocol — standardised inter-agent communication.

Implements a lightweight A2A message passing protocol inspired by Google's
A2A specification and AutoGen's message schema.

This enables:
  - Loose coupling between agents (no direct function calls)
  - Async agent communication (agents don't block waiting for each other)
  - Audit trail of all inter-agent messages
  - Easy addition of new agents without modifying existing ones

Message flow:
  Supervisor → [A2AMessage] → MessageBus → [A2AMessage] → Specialist
  Specialist → [A2AMessage] → MessageBus → [A2AMessage] → Supervisor

In production, replace the in-memory MessageBus with SQS (async) or
Step Functions (orchestrated workflows).

Session for audience:
  - Knowledge fuel: A2A spec, AutoGen message schema, actor model
  - Lab: implement SQSMessageBus that routes messages via AWS SQS queues
        so each specialist agent can run as an independent Lambda function

Reference: https://google.github.io/A2A/
"""
import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------
class MessageType(str, Enum):
    REQUEST = "request"          # from supervisor to specialist
    RESPONSE = "response"        # from specialist back to supervisor
    BROADCAST = "broadcast"      # to all registered agents
    ERROR = "error"              # error in processing
    HEARTBEAT = "heartbeat"      # agent liveness check


# ---------------------------------------------------------------------------
# A2A Message
# ---------------------------------------------------------------------------
@dataclass
class A2AMessage:
    """
    Standardised inter-agent message envelope.

    Inspired by the A2A protocol spec and LangChain's agent message schema.
    All agent-to-agent communication should use this envelope.
    """
    message_id: str
    type: MessageType
    sender: str                          # agent name / ID
    recipient: str                       # agent name / ID or "*" for broadcast
    conversation_id: str
    payload: Dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    correlation_id: Optional[str] = None  # links response to a request
    priority: int = 5                    # 1 (highest) to 10 (lowest)
    ttl_seconds: int = 300               # message expiry

    @classmethod
    def request(
        cls,
        sender: str,
        recipient: str,
        conversation_id: str,
        payload: Dict[str, Any],
    ) -> "A2AMessage":
        return cls(
            message_id=str(uuid.uuid4()),
            type=MessageType.REQUEST,
            sender=sender,
            recipient=recipient,
            conversation_id=conversation_id,
            payload=payload,
        )

    @classmethod
    def response(cls, original: "A2AMessage", payload: Dict[str, Any], sender: str) -> "A2AMessage":
        return cls(
            message_id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            sender=sender,
            recipient=original.sender,
            conversation_id=original.conversation_id,
            payload=payload,
            correlation_id=original.message_id,
        )

    @classmethod
    def error(cls, original: "A2AMessage", error: str, sender: str) -> "A2AMessage":
        return cls(
            message_id=str(uuid.uuid4()),
            type=MessageType.ERROR,
            sender=sender,
            recipient=original.sender,
            conversation_id=original.conversation_id,
            payload={"error": error},
            correlation_id=original.message_id,
        )

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


# ---------------------------------------------------------------------------
# Agent capability advertisement
# ---------------------------------------------------------------------------
@dataclass
class AgentCapability:
    """Describes what an agent can do — used for routing."""
    agent_id: str
    name: str
    description: str
    supported_intents: List[str]           # e.g. ["lookup_order", "cancel_order"]
    tool_access: str                       # "readonly" | "readwrite" | "admin"
    max_concurrent: int = 5


# ---------------------------------------------------------------------------
# Message Bus (in-memory for dev, SQS for prod)
# ---------------------------------------------------------------------------
HandlerFn = Callable[[A2AMessage], Coroutine[Any, Any, Optional[A2AMessage]]]


class MessageBus:
    """
    In-process async message bus for agent communication.

    In production, replace with SQSMessageBus (see TODO below).
    The interface stays the same — agents don't need to change.

    TODO (Lab — Month 6):
    Implement SQSMessageBus:
      1. publish() → sqs.send_message(QueueUrl=..., MessageBody=json.dumps(msg))
      2. subscribe() → register Lambda trigger on the SQS queue
      3. Each specialist agent runs as a separate Lambda handler
      4. Use SQS FIFO for ordered processing per conversation_id
      5. Dead letter queue for failed messages with retry logic
    """

    def __init__(self):
        self._handlers: Dict[str, HandlerFn] = {}     # agent_id → handler
        self._capabilities: Dict[str, AgentCapability] = {}
        self._message_log: List[A2AMessage] = []
        self._pending: Dict[str, asyncio.Future] = {}  # message_id → Future

    def register(self, capability: AgentCapability, handler: HandlerFn) -> None:
        """Register an agent with its capability advertisement and handler function."""
        self._capabilities[capability.agent_id] = capability
        self._handlers[capability.agent_id] = handler
        logger.info(f"A2A: Agent registered | id={capability.agent_id} | tools={capability.tool_access}")

    async def publish(self, message: A2AMessage) -> Optional[A2AMessage]:
        """
        Publish a message and optionally wait for a response.

        For REQUEST messages, returns the correlated RESPONSE.
        For other types, returns None immediately.
        """
        self._message_log.append(message)
        logger.debug(
            f"A2A publish | {message.type.value} | "
            f"{message.sender} → {message.recipient} | "
            f"conversation={message.conversation_id}"
        )

        if message.type == MessageType.REQUEST:
            return await self._route_request(message)
        elif message.type == MessageType.BROADCAST:
            return await self._broadcast(message)

        return None

    async def _route_request(self, message: A2AMessage) -> Optional[A2AMessage]:
        """Route a request to the target agent and await its response."""
        handler = self._handlers.get(message.recipient)
        if not handler:
            logger.error(f"A2A: No handler for recipient '{message.recipient}'")
            return A2AMessage.error(message, f"Unknown agent: {message.recipient}", "bus")

        try:
            response = await asyncio.wait_for(handler(message), timeout=30.0)
            if response:
                self._message_log.append(response)
            return response
        except asyncio.TimeoutError:
            logger.error(f"A2A: Handler timeout for '{message.recipient}'")
            return A2AMessage.error(message, "Agent response timeout", "bus")
        except Exception as exc:
            logger.error(f"A2A: Handler error for '{message.recipient}': {exc}")
            return A2AMessage.error(message, str(exc), "bus")

    async def _broadcast(self, message: A2AMessage) -> None:
        """Send to all registered agents."""
        tasks = []
        for agent_id, handler in self._handlers.items():
            if agent_id != message.sender:
                tasks.append(handler(message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_agents(self) -> List[AgentCapability]:
        return list(self._capabilities.values())

    def get_message_log(self, conversation_id: str = None) -> List[Dict]:
        msgs = self._message_log
        if conversation_id:
            msgs = [m for m in msgs if m.conversation_id == conversation_id]
        return [m.to_dict() for m in msgs]


# ---------------------------------------------------------------------------
# Global bus singleton
# ---------------------------------------------------------------------------
_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
