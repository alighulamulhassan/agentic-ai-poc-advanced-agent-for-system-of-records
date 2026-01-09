"""
Chat API endpoints.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = False
    conversation_id: str = "default"


class ChatResponse(BaseModel):
    message: Message
    tool_calls: Optional[List[dict]] = None
    sources: Optional[List[str]] = None


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    """
    Process a chat completion request.
    """
    from app.core.agent import get_agent
    
    try:
        agent = get_agent(request.conversation_id)
        
        # Get the last user message
        user_message = request.messages[-1].content if request.messages else ""
        
        if request.stream:
            async def generate():
                async for token in agent.stream_response(user_message):
                    yield f"data: {json.dumps({'content': token})}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )
        else:
            response = await agent.process_message(user_message)
            
            return ChatResponse(
                message=Message(role="assistant", content=response["content"]),
                tool_calls=response.get("tool_calls"),
                sources=response.get("sources")
            )
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/with-rag")
async def chat_with_rag(request: ChatRequest):
    """
    Chat with RAG-enhanced responses from documents.
    """
    from app.core.agent import get_agent
    
    try:
        agent = get_agent(request.conversation_id)
        agent.use_rag = True
        
        user_message = request.messages[-1].content if request.messages else ""
        response = await agent.process_message(user_message)
        
        return ChatResponse(
            message=Message(role="assistant", content=response["content"]),
            tool_calls=response.get("tool_calls"),
            sources=response.get("sources")
        )
    
    except Exception as e:
        logger.error(f"RAG chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{conversation_id}")
async def clear_history(conversation_id: str):
    """Clear conversation history."""
    from app.core.agent import clear_agent
    clear_agent(conversation_id)
    return {"message": f"History cleared for conversation {conversation_id}"}
