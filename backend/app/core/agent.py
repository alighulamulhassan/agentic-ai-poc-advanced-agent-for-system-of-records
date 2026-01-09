"""
Agent orchestrator - the brain of the voice agent.
Uses Ollama for local LLM inference by default.
"""
from typing import List, AsyncGenerator, Optional, Dict, Any
from app.config import settings
from app.core.llm import get_llm
from app.tools.registry import get_tools, get_tool_schemas
from app.tools.executor import execute_tool

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful, knowledgeable customer support agent for an e-commerce company. 
You are empathetic, professional, and always aim to resolve customer issues efficiently.

You have FULL AUTHORITY to perform transactions on the system of record (database).

## Your Capabilities:

### 📋 READ Operations:
- **lookup_order**: Check order status, tracking, items, and shipping info
- **get_customer_info**: Look up customer details, loyalty points, and tier
- **find_customer_by_email**: Find customer by email address
- **get_customer_order_history**: Get complete order history
- **search_products**: Find products in catalog
- **search_documents**: Search knowledge base, policies, and FAQs

### 💳 WRITE/TRANSACTION Operations (MODIFY DATABASE):
- **cancel_order**: Cancel an order (auto-refunds if not shipped)
- **process_refund**: Issue partial or full refunds
- **update_order_status**: Change order status (processing, shipped, on_hold, etc.)
- **update_shipping_address**: Change delivery address (before shipment)
- **apply_discount_code**: Apply coupon codes (WELCOME10, SAVE20, VIP25, FREESHIP, HOLIDAY30)
- **add_loyalty_points**: Award bonus points to customers
- **update_customer_profile**: Update customer name, email, phone, or address
- **expedite_order_shipping**: Upgrade to express shipping (free, as goodwill)

## Transaction Guidelines:
1. **Confirm before destructive actions**: Cancellations and refunds should be confirmed
2. **Use tools liberally**: Don't just explain - actually perform the action!
3. **Report results**: After a transaction, tell the customer exactly what happened
4. **Be proactive**: Offer expedited shipping or loyalty points for service issues

## Key Behaviors:
- Be concise but thorough in your responses
- Actually CALL the tools to perform actions - don't just describe what you would do
- When a customer asks you to do something, DO IT (call the appropriate tool)
- If a tool call fails, explain why and offer alternatives
- Cite sources when providing information from documents

## Example Interactions:
- "Cancel my order ORD-10003" → Call cancel_order tool, then report the result
- "Apply code SAVE20 to my order" → Call apply_discount_code tool, report savings
- "I want a refund" → Ask for order ID, then call process_refund
- "Speed up my delivery" → Call expedite_order_shipping

Remember: You have real power to help customers. Use your tools to actually solve their problems!"""


class Agent:
    """Main agent class that orchestrates the conversation."""
    
    def __init__(self, use_rag: bool = True):
        self.use_rag = use_rag
        self.llm = get_llm()
        self.tools = get_tool_schemas()
        self.conversation_history: List[Dict] = []
    
    async def process_message(self, user_message: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Process a user message and return the agent's response.
        Handles tool calling and RAG automatically.
        """
        # Build messages list
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        # Get initial response (may include tool calls)
        response = await self.llm.chat(messages, tools=self.tools if self.tools else None)
        
        # Handle tool calls if present
        if response.get("tool_calls"):
            tool_results = await self._execute_tools(response["tool_calls"])
            
            # Add assistant's tool call message
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response["tool_calls"]
            })
            
            # Add tool results
            for result in tool_results:
                messages.append(result)
            
            # Get final response after tool execution
            final_response = await self.llm.chat(messages)
            content = final_response["content"]
            
            # Update history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": content})
            
            return {
                "content": content,
                "tool_calls": response["tool_calls"],
                "tool_results": tool_results
            }
        
        content = response["content"]
        
        # Update history
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": content})
        
        return {"content": content}
    
    async def stream_response(self, user_message: str) -> AsyncGenerator[str, None]:
        """Stream response tokens for real-time display."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        full_response = ""
        async for token in self.llm.stream(messages):
            full_response += token
            yield token
        
        # Update history after streaming completes
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": full_response})
    
    async def _execute_tools(self, tool_calls: list) -> list:
        """Execute tool calls and return results."""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", f"call_{tool_name}")
            
            # Execute the tool
            result = await execute_tool(tool_name, tool_args)
            
            results.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": str(result)
            })
        
        return results
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict]:
        """Get conversation history."""
        return self.conversation_history


# Agent instance cache
_agents: Dict[str, Agent] = {}


def get_agent(conversation_id: str = "default") -> Agent:
    """Get or create an agent for a conversation."""
    if conversation_id not in _agents:
        _agents[conversation_id] = Agent()
    return _agents[conversation_id]


def clear_agent(conversation_id: str = "default"):
    """Clear an agent's state."""
    if conversation_id in _agents:
        del _agents[conversation_id]
