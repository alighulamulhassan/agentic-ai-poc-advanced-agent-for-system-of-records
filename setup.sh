#!/bin/bash

# Voice Agent POC - Project Setup Script
# This script creates the initial project structure and installs dependencies

set -e

echo "🚀 Setting up Voice Agent POC..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create directory structure
echo -e "${BLUE}📁 Creating project structure...${NC}"

mkdir -p backend/app/{api/routes,core,rag,voice,tools/definitions,guardrails,db}
mkdir -p frontend
mkdir -p data/{documents,db}
mkdir -p docs
mkdir -p scripts

# Create backend files
echo -e "${BLUE}🐍 Setting up Python backend...${NC}"

# Create requirements.txt
cat > backend/requirements.txt << 'EOF'
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
websockets>=12.0
pydantic-settings>=2.1.0

# LLM & AI
openai>=1.12.0
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-community>=0.0.20

# RAG
chromadb>=0.4.22
pypdf>=4.0.0
python-docx>=1.1.0
unstructured>=0.12.0

# Voice (optional - for local Whisper)
# openai-whisper>=20231117
# sounddevice>=0.4.6

# Database
sqlalchemy>=2.0.25

# Utilities
python-dotenv>=1.0.0
httpx>=0.26.0

# Development
pytest>=8.0.0
black>=24.1.0
ruff>=0.1.14
EOF

# Create main FastAPI app
cat > backend/app/main.py << 'EOF'
"""
Voice Agent POC - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import chat, documents, voice
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    print("🚀 Starting Voice Agent POC...")
    # Startup: Initialize services here
    yield
    # Shutdown: Cleanup here
    print("👋 Shutting down...")


app = FastAPI(
    title="Voice Agent POC",
    description="A Sierra AI-inspired conversational AI system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
EOF

# Create config
cat > backend/app/config.py << 'EOF'
"""
Application configuration using pydantic-settings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    openai_api_key: str = ""
    
    # LLM Settings
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    
    # Voice Settings
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "nova"
    
    # RAG Settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_k: int = 4
    
    # Database
    database_url: str = "sqlite:///./data/db/app.db"
    
    # Vector Store
    chroma_persist_dir: str = "./data/chroma"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
EOF

# Create chat router
cat > backend/app/api/routes/chat.py << 'EOF'
"""
Chat API endpoints.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json

router = APIRouter()


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = True


class ChatResponse(BaseModel):
    message: Message
    sources: Optional[List[dict]] = None


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    """
    Process a chat completion request.
    Supports streaming responses.
    """
    from app.core.agent import Agent
    
    agent = Agent()
    
    if request.stream:
        async def generate():
            async for chunk in agent.stream_response(request.messages):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    else:
        response = await agent.get_response(request.messages)
        return ChatResponse(
            message=Message(role="assistant", content=response["content"]),
            sources=response.get("sources")
        )


@router.post("/with-rag")
async def chat_with_rag(request: ChatRequest):
    """
    Chat with RAG-enhanced responses from documents.
    """
    from app.core.agent import Agent
    
    agent = Agent(use_rag=True)
    response = await agent.get_response(request.messages)
    
    return ChatResponse(
        message=Message(role="assistant", content=response["content"]),
        sources=response.get("sources")
    )
EOF

# Create documents router
cat > backend/app/api/routes/documents.py << 'EOF'
"""
Document management API endpoints.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import os

router = APIRouter()


class Document(BaseModel):
    id: str
    name: str
    size: int
    chunks: int


class DocumentListResponse(BaseModel):
    documents: List[Document]


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and index a document for RAG.
    """
    # Save file
    file_path = f"./data/documents/{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # TODO: Process and index document
    # from app.rag.chunker import chunk_document
    # from app.rag.vectorstore import add_to_vectorstore
    
    return {
        "message": f"Document '{file.filename}' uploaded successfully",
        "file_path": file_path
    }


@router.get("/", response_model=DocumentListResponse)
async def list_documents():
    """
    List all indexed documents.
    """
    documents_dir = "./data/documents"
    documents = []
    
    if os.path.exists(documents_dir):
        for filename in os.listdir(documents_dir):
            file_path = os.path.join(documents_dir, filename)
            if os.path.isfile(file_path):
                documents.append(Document(
                    id=filename,
                    name=filename,
                    size=os.path.getsize(file_path),
                    chunks=0  # TODO: Get actual chunk count
                ))
    
    return DocumentListResponse(documents=documents)


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and remove from vector store.
    """
    file_path = f"./data/documents/{document_id}"
    
    if os.path.exists(file_path):
        os.remove(file_path)
        # TODO: Remove from vector store
        return {"message": f"Document '{document_id}' deleted"}
    
    raise HTTPException(status_code=404, detail="Document not found")
EOF

# Create voice router
cat > backend/app/api/routes/voice.py << 'EOF'
"""
Voice processing API endpoints.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

router = APIRouter()


class TranscriptionResponse(BaseModel):
    text: str
    language: str = "en"


class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio to text using Whisper.
    """
    from app.voice.stt import transcribe
    
    audio_bytes = await audio.read()
    result = await transcribe(audio_bytes)
    
    return TranscriptionResponse(
        text=result["text"],
        language=result.get("language", "en")
    )


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    Convert text to speech.
    """
    from app.voice.tts import synthesize
    
    audio_bytes = await synthesize(request.text, request.voice)
    
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=speech.mp3"}
    )
EOF

# Create placeholder for routes __init__
cat > backend/app/api/routes/__init__.py << 'EOF'
"""API Routes package."""
EOF

cat > backend/app/api/__init__.py << 'EOF'
"""API package."""
EOF

# Create agent core
cat > backend/app/core/agent.py << 'EOF'
"""
Agent orchestrator - the brain of the voice agent.
"""
from typing import List, AsyncGenerator, Optional
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful, knowledgeable customer support agent. You are empathetic, 
professional, and always aim to resolve customer issues efficiently.

Key behaviors:
- Be concise but thorough
- Ask clarifying questions when needed
- Confirm before taking any actions
- Always be polite and patient

You have access to the following tools:
- Search documents for product information and policies
- Look up orders and customer information
- Process refunds and returns
- Update order status

Always cite your sources when providing information from documents.
"""


class Agent:
    """Main agent class that orchestrates the conversation."""
    
    def __init__(self, use_rag: bool = False):
        self.use_rag = use_rag
        self.tools = self._register_tools()
    
    def _register_tools(self) -> list:
        """Register available tools for function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_order",
                    "description": "Look up an order by its ID to get status, items, and shipping info",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order ID to look up"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search product documentation, FAQs, and policies",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "process_refund",
                    "description": "Process a refund for an order. Requires confirmation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order ID to refund"
                            },
                            "amount": {
                                "type": "number",
                                "description": "The refund amount in dollars"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for the refund"
                            }
                        },
                        "required": ["order_id", "amount", "reason"]
                    }
                }
            }
        ]
    
    async def get_response(self, messages: list) -> dict:
        """Get a complete response from the agent."""
        formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        formatted_messages.extend([{"role": m.role, "content": m.content} for m in messages])
        
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=formatted_messages,
            tools=self.tools if self.tools else None,
        )
        
        message = response.choices[0].message
        
        # Handle tool calls if any
        if message.tool_calls:
            # Execute tools and get results
            tool_results = await self._execute_tools(message.tool_calls)
            
            # Add tool results to messages and get final response
            formatted_messages.append(message.model_dump())
            formatted_messages.extend(tool_results)
            
            final_response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=formatted_messages,
            )
            return {"content": final_response.choices[0].message.content}
        
        return {"content": message.content}
    
    async def stream_response(self, messages: list) -> AsyncGenerator[dict, None]:
        """Stream response tokens from the agent."""
        formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        formatted_messages.extend([{"role": m.role, "content": m.content} for m in messages])
        
        stream = await client.chat.completions.create(
            model=settings.llm_model,
            messages=formatted_messages,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {"content": chunk.choices[0].delta.content}
    
    async def _execute_tools(self, tool_calls: list) -> list:
        """Execute tool calls and return results."""
        from app.tools.executor import execute_tool
        
        results = []
        for tool_call in tool_calls:
            result = await execute_tool(
                tool_call.function.name,
                tool_call.function.arguments
            )
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })
        return results
EOF

cat > backend/app/core/__init__.py << 'EOF'
"""Core package."""
EOF

# Create tool executor
cat > backend/app/tools/executor.py << 'EOF'
"""
Tool execution engine with safety checks.
"""
import json
from typing import Any


async def execute_tool(tool_name: str, arguments: str) -> Any:
    """
    Execute a tool by name with the given arguments.
    Includes validation and error handling.
    """
    args = json.loads(arguments)
    
    # Tool registry
    tools = {
        "lookup_order": lookup_order,
        "search_documents": search_documents,
        "process_refund": process_refund,
    }
    
    if tool_name not in tools:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        result = await tools[tool_name](**args)
        return result
    except Exception as e:
        return {"error": str(e)}


async def lookup_order(order_id: str) -> dict:
    """Look up an order from the database."""
    # TODO: Implement actual database lookup
    # For now, return mock data
    return {
        "order_id": order_id,
        "status": "shipped",
        "items": [
            {"name": "Wireless Headphones", "quantity": 1, "price": 79.99}
        ],
        "shipping": {
            "carrier": "FedEx",
            "tracking": "FX123456789",
            "estimated_delivery": "2024-12-23"
        }
    }


async def search_documents(query: str) -> dict:
    """Search documents using RAG."""
    # TODO: Implement actual RAG search
    # from app.rag.retriever import search
    # return await search(query)
    return {
        "results": [
            {
                "content": "Our return policy allows returns within 30 days of purchase...",
                "source": "return_policy.pdf",
                "relevance": 0.92
            }
        ]
    }


async def process_refund(order_id: str, amount: float, reason: str) -> dict:
    """Process a refund for an order."""
    # TODO: Implement actual refund processing
    # This should include confirmation flow in production
    return {
        "success": True,
        "refund_id": f"REF-{order_id}",
        "amount": amount,
        "status": "processing",
        "message": f"Refund of ${amount} initiated for order {order_id}"
    }
EOF

cat > backend/app/tools/__init__.py << 'EOF'
"""Tools package."""
EOF

cat > backend/app/tools/definitions/__init__.py << 'EOF'
"""Tool definitions package."""
EOF

# Create STT module
cat > backend/app/voice/stt.py << 'EOF'
"""
Speech-to-Text using OpenAI Whisper.
"""
from openai import AsyncOpenAI
from app.config import settings
import io

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe(audio_bytes: bytes) -> dict:
    """
    Transcribe audio bytes to text.
    """
    # Create a file-like object from bytes
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"  # Whisper needs a filename
    
    transcript = await client.audio.transcriptions.create(
        model=settings.stt_model,
        file=audio_file,
        response_format="json"
    )
    
    return {
        "text": transcript.text,
        "language": "en"
    }
EOF

# Create TTS module
cat > backend/app/voice/tts.py << 'EOF'
"""
Text-to-Speech using OpenAI TTS.
"""
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def synthesize(text: str, voice: str = None) -> bytes:
    """
    Convert text to speech audio bytes.
    """
    response = await client.audio.speech.create(
        model=settings.tts_model,
        voice=voice or settings.tts_voice,
        input=text,
        response_format="mp3"
    )
    
    return response.content
EOF

cat > backend/app/voice/__init__.py << 'EOF'
"""Voice package."""
EOF

# Create remaining __init__ files
cat > backend/app/rag/__init__.py << 'EOF'
"""RAG package."""
EOF

cat > backend/app/guardrails/__init__.py << 'EOF'
"""Guardrails package."""
EOF

cat > backend/app/db/__init__.py << 'EOF'
"""Database package."""
EOF

cat > backend/app/__init__.py << 'EOF'
"""Voice Agent POC Backend."""
EOF

# Create .env.example
cat > backend/.env.example << 'EOF'
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-api-key-here

# Model Configuration
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
STT_MODEL=whisper-1
TTS_MODEL=tts-1
TTS_VOICE=nova

# RAG Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVAL_K=4

# Database
DATABASE_URL=sqlite:///./data/db/app.db
CHROMA_PERSIST_DIR=./data/chroma
EOF

# Create Makefile
cat > Makefile << 'EOF'
.PHONY: setup backend frontend install dev clean

# Setup everything
setup:
	@echo "🚀 Setting up Voice Agent POC..."
	@bash setup.sh

# Install backend dependencies
install-backend:
	@echo "📦 Installing backend dependencies..."
	cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt

# Install frontend dependencies
install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

# Run backend
backend:
	@echo "🐍 Starting backend..."
	cd backend && . venv/bin/activate && python -m uvicorn app.main:app --reload --port 8000

# Run frontend
frontend:
	@echo "⚛️ Starting frontend..."
	cd frontend && npm run dev

# Run both (requires tmux or run in separate terminals)
dev:
	@echo "🚀 Run 'make backend' and 'make frontend' in separate terminals"

# Clean up
clean:
	rm -rf backend/venv
	rm -rf frontend/node_modules
	rm -rf data/db/*.db
	rm -rf data/chroma
	@echo "🧹 Cleaned up!"

# Run tests
test:
	cd backend && . venv/bin/activate && pytest

# Format code
format:
	cd backend && . venv/bin/activate && black . && ruff check --fix .
EOF

# Create README
cat > README.md << 'EOF'
# 🎙️ Voice Agent POC

A Sierra AI-inspired conversational AI system with voice support, RAG, and system operations.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenAI API key

### Setup

1. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure environment:**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Install dependencies:**
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Frontend (in another terminal)
   cd frontend
   npm install
   ```

4. **Start the servers:**
   ```bash
   # Terminal 1: Backend
   make backend

   # Terminal 2: Frontend
   make frontend
   ```

5. **Open http://localhost:3000**

## 📚 Documentation

- [Project Plan](./PROJECT_PLAN.md) - Full strategic plan and architecture
- [Models & Frameworks](./MODELS_AND_FRAMEWORKS.md) - Technology comparisons

## 🏗️ Project Structure

```
voice-agent-poc/
├── frontend/          # Next.js web app
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── core/      # Agent orchestration
│   │   ├── rag/       # RAG pipeline
│   │   ├── voice/     # STT/TTS
│   │   ├── tools/     # Tool definitions
│   │   └── db/        # Database
│   └── requirements.txt
├── data/
│   ├── documents/     # Documents for RAG
│   └── db/            # SQLite database
└── docs/              # Documentation
```

## 🎯 Features

- [ ] Text chat with streaming responses
- [ ] Voice input (Speech-to-Text)
- [ ] Voice output (Text-to-Speech)
- [ ] RAG on uploaded documents
- [ ] Tool execution (database operations)
- [ ] Guardrails and safety

## 📖 Learning Resources

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for comprehensive learning resources and concepts.
EOF

echo -e "${GREEN}✅ Project structure created successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. cd backend && cp .env.example .env"
echo "  2. Add your OPENAI_API_KEY to backend/.env"
echo "  3. Install dependencies: make install-backend"
echo "  4. Set up frontend: cd frontend && npx create-next-app@latest . --typescript --tailwind"
echo "  5. Start development: make backend (in one terminal) and make frontend (in another)"
echo ""
echo "📚 Read PROJECT_PLAN.md for the full strategic plan!"



