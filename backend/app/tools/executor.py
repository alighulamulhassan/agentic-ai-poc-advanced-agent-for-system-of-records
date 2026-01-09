"""
Tool execution engine with safety checks and logging.
"""
import json
import logging
from typing import Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Execute a tool by name with the given arguments.
    Includes validation, logging, and error handling.
    """
    from app.tools.registry import ALL_TOOLS
    
    # Find the tool
    tool_map = {t.name: t for t in ALL_TOOLS}
    
    if tool_name not in tool_map:
        logger.error(f"Unknown tool requested: {tool_name}")
        return {"error": f"Unknown tool: {tool_name}"}
    
    tool = tool_map[tool_name]
    
    # Log the tool call
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
    
    try:
        # Execute the tool
        start_time = datetime.now()
        result = tool.invoke(arguments)
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Tool {tool_name} completed in {duration:.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {str(e)}")
        return {
            "error": str(e),
            "tool": tool_name,
            "message": "The operation could not be completed. Please try again or contact support."
        }


def validate_tool_args(tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate tool arguments before execution.
    Returns (is_valid, error_message)
    """
    # Add custom validation rules here
    if tool_name == "process_refund":
        if arguments.get("amount", 0) <= 0:
            return False, "Refund amount must be positive"
        if not arguments.get("reason"):
            return False, "Refund reason is required"
    
    if tool_name == "update_order_status":
        valid_statuses = ["processing", "shipped", "delivered", "cancelled", "on_hold"]
        if arguments.get("new_status") not in valid_statuses:
            return False, f"Invalid status. Must be one of: {valid_statuses}"
    
    return True, ""
