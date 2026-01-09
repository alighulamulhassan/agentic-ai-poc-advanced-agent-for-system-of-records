"""
LLM client abstraction - supports both Ollama (local) and OpenAI (cloud).
Default: Ollama for Option A lightweight stack.
"""
from typing import AsyncGenerator, Optional
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from app.config import settings


class LLMClient:
    """Unified LLM client that can use Ollama or OpenAI."""
    
    def __init__(self):
        self.use_openai = settings.use_openai and settings.openai_api_key
        
        if self.use_openai:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.openai_api_key,
                streaming=True
            )
        else:
            self.llm = ChatOllama(
                model=settings.llm_model,
                base_url=settings.ollama_base_url,
                temperature=0.7,
            )
    
    def _convert_messages(self, messages: list) -> list:
        """Convert message dicts to LangChain message objects."""
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            elif role == "tool":
                result.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", "")
                ))
        return result
    
    async def chat(self, messages: list, tools: list = None) -> dict:
        """
        Send a chat completion request.
        Returns: {"content": str, "tool_calls": list or None}
        """
        lc_messages = self._convert_messages(messages)
        
        if tools:
            llm_with_tools = self.llm.bind_tools(tools)
            response = await llm_with_tools.ainvoke(lc_messages)
        else:
            response = await self.llm.ainvoke(lc_messages)
        
        return {
            "content": response.content,
            "tool_calls": getattr(response, "tool_calls", None)
        }
    
    async def stream(self, messages: list) -> AsyncGenerator[str, None]:
        """Stream response tokens."""
        lc_messages = self._convert_messages(messages)
        
        async for chunk in self.llm.astream(lc_messages):
            if chunk.content:
                yield chunk.content


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """Get or create the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client



