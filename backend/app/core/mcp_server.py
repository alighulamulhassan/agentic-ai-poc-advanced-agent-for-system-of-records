"""
Model Context Protocol (MCP) Server — expose agent tools as MCP endpoints.

MCP (Anthropic, 2024) standardises how LLMs discover and invoke external
tools and resources. By implementing MCP, our agent's tools become
discoverable by ANY MCP-compatible LLM client (Claude Desktop, Cursor, etc.)

MCP server exposes three primitives:
  - Tools: functions the LLM can call (our 16 tools)
  - Resources: data sources the LLM can read (orders, customers, docs)
  - Prompts: reusable prompt templates (system prompts, few-shot examples)

This module provides:
  1. Tool manifest endpoint: GET /mcp/tools → list of tool schemas
  2. Tool invoke endpoint: POST /mcp/tools/{name} → tool result
  3. Resource read endpoint: GET /mcp/resources/{uri} → resource content

In production, register this server with Claude Desktop or your MCP host
so the tools appear natively in the LLM's context.

Session for audience:
  - Knowledge fuel: MCP spec, tool use patterns, resource URIs
  - Lab: add a new MCP resource "mcp://orders/{order_id}" that returns
        structured order data in MCP resource format

Reference: https://modelcontextprotocol.io/specification
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools.registry import ALL_TOOLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])


# ---------------------------------------------------------------------------
# MCP data models (aligned with MCP spec v0.1)
# ---------------------------------------------------------------------------
class MCPToolParameter(BaseModel):
    name: str
    description: str
    type: str
    required: bool = True


class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPResource(BaseModel):
    uri: str
    name: str
    description: str
    mimeType: str = "application/json"


class MCPPrompt(BaseModel):
    name: str
    description: str
    arguments: List[Dict[str, str]] = []


class MCPToolCallRequest(BaseModel):
    arguments: Dict[str, Any] = {}
    conversation_id: str = "default"


class MCPToolCallResponse(BaseModel):
    content: List[Dict[str, Any]]
    isError: bool = False


# ---------------------------------------------------------------------------
# Tool schema conversion (LangChain → MCP format)
# ---------------------------------------------------------------------------
def _langchain_to_mcp_tool(lc_tool) -> MCPTool:
    """Convert a LangChain @tool to MCP tool schema."""
    schema = lc_tool.args_schema.schema() if lc_tool.args_schema else {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    input_schema = {
        "type": "object",
        "properties": {
            k: {
                "type": v.get("type", "string"),
                "description": v.get("description", v.get("title", k)),
            }
            for k, v in properties.items()
        },
        "required": required,
    }

    # Clean up description (take first paragraph only)
    description = lc_tool.description.split("\n")[0].strip()

    return MCPTool(
        name=lc_tool.name,
        description=description,
        inputSchema=input_schema,
    )


# ---------------------------------------------------------------------------
# MCP Tool endpoints
# ---------------------------------------------------------------------------
@router.get("/tools", response_model=List[MCPTool])
async def list_tools():
    """
    MCP tools/list endpoint.
    Returns all available tools in MCP schema format.

    MCP clients call this at startup to discover available capabilities.
    """
    return [_langchain_to_mcp_tool(t) for t in ALL_TOOLS]


@router.post("/tools/{tool_name}", response_model=MCPToolCallResponse)
async def invoke_tool(tool_name: str, request: MCPToolCallRequest):
    """
    MCP tools/call endpoint.
    Invokes a tool by name with the provided arguments.

    This endpoint runs the full security + guardrails pipeline:
      input validation → injection check → risk score → policy → execute
    """
    from app.tools.executor import execute_tool
    from app.security.output_validator import validate_tool_args
    from app.security.injection_guard import check_injection

    # Validate tool exists
    tool_names = {t.name for t in ALL_TOOLS}
    if tool_name not in tool_names:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Security: validate args
    validation = validate_tool_args(tool_name, request.arguments)
    if not validation.is_valid:
        return MCPToolCallResponse(
            content=[{"type": "text", "text": f"Validation failed: {'; '.join(validation.errors)}"}],
            isError=True,
        )

    # Execute tool
    try:
        result = await execute_tool(tool_name, validation.sanitized_args or request.arguments)
        return MCPToolCallResponse(
            content=[{"type": "text", "text": str(result)}],
            isError=False,
        )
    except Exception as exc:
        logger.error(f"MCP tool invocation failed: {tool_name} — {exc}")
        return MCPToolCallResponse(
            content=[{"type": "text", "text": f"Tool execution error: {exc}"}],
            isError=True,
        )


# ---------------------------------------------------------------------------
# MCP Resource endpoints
# ---------------------------------------------------------------------------
_RESOURCES: List[MCPResource] = [
    MCPResource(
        uri="mcp://orders/{order_id}",
        name="Order Record",
        description="Retrieve a specific order by ID from the system of record",
    ),
    MCPResource(
        uri="mcp://customers/{customer_id}",
        name="Customer Record",
        description="Retrieve customer profile and loyalty information",
    ),
    MCPResource(
        uri="mcp://docs/{query}",
        name="Knowledge Base",
        description="Search product FAQs, return policies, and shipping information",
    ),
]


@router.get("/resources", response_model=List[MCPResource])
async def list_resources():
    """MCP resources/list endpoint."""
    return _RESOURCES


@router.get("/resources/orders/{order_id}")
async def read_order_resource(order_id: str):
    """
    MCP resource: mcp://orders/{order_id}
    Returns structured order data for the LLM context.

    TODO (Lab):
    Add more resource types:
      - mcp://customers/{customer_id}/orders — order history
      - mcp://products/{product_id} — product details
      - mcp://policies/{policy_name} — policy documents

    Each resource should return data in a format that's
    immediately usable as LLM context without further processing.
    """
    from app.db.operations import get_order
    result = get_order(order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "uri": f"mcp://orders/{order_id}",
        "mimeType": "application/json",
        "content": result,
    }


@router.get("/resources/customers/{customer_id}")
async def read_customer_resource(customer_id: str):
    """MCP resource: mcp://customers/{customer_id}"""
    from app.db.operations import get_customer
    result = get_customer(customer_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "uri": f"mcp://customers/{customer_id}",
        "mimeType": "application/json",
        "content": result,
    }


# ---------------------------------------------------------------------------
# MCP Prompt endpoints
# ---------------------------------------------------------------------------
_PROMPTS: List[MCPPrompt] = [
    MCPPrompt(
        name="customer_support",
        description="System prompt for the customer support agent",
        arguments=[],
    ),
    MCPPrompt(
        name="refund_handling",
        description="Few-shot examples for refund scenarios",
        arguments=[{"name": "order_id", "description": "The order being refunded"}],
    ),
]


@router.get("/prompts", response_model=List[MCPPrompt])
async def list_prompts():
    """MCP prompts/list endpoint."""
    return _PROMPTS


@router.get("/prompts/{prompt_name}")
async def get_prompt(prompt_name: str, order_id: Optional[str] = None):
    """MCP prompts/get endpoint — returns a rendered prompt."""
    if prompt_name == "customer_support":
        from app.core.agent import SYSTEM_PROMPT
        return {
            "description": "Customer support agent system prompt",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        }
    if prompt_name == "refund_handling":
        return {
            "description": "Few-shot refund handling examples",
            "messages": [
                {"role": "user", "content": f"I need a refund for order {order_id or 'ORD-XXXXX'}"},
                {"role": "assistant", "content": "I'll look up that order and process your refund right away."},
            ],
        }
    raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found")


# ---------------------------------------------------------------------------
# MCP Server info
# ---------------------------------------------------------------------------
@router.get("/")
async def mcp_info():
    """MCP server capabilities advertisement."""
    return {
        "name": "Enterprise Agent MCP Server",
        "version": "1.0.0",
        "protocolVersion": "0.1",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
            "prompts": {"listChanged": False},
        },
        "tools_count": len(ALL_TOOLS),
        "resources_count": len(_RESOURCES),
        "prompts_count": len(_PROMPTS),
    }
