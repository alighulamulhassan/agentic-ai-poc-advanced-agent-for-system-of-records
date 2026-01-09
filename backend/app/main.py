"""
Voice Agent POC - Main FastAPI Application
Option A: Lightweight / Learning-Focused Stack

Stack:
- LLM: Ollama (local) with Llama 3.2 / Mistral
- STT: OpenAI Whisper (local)
- TTS: pyttsx3 / gTTS
- RAG: LangChain + ChromaDB
- DB: SQLite
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import chat, documents, voice
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    logger.info("🚀 Starting Voice Agent POC...")
    logger.info(f"   LLM: Ollama @ {settings.ollama_base_url} ({settings.llm_model})")
    logger.info(f"   Embeddings: {settings.embedding_model}")
    logger.info(f"   Whisper: {settings.whisper_model}")
    
    # Initialize database
    from app.db.database import init_db
    init_db()
    logger.info("   ✅ Database initialized")
    
    # Seed database if empty
    try:
        from app.db.seed import seed_database
        seed_database()
    except Exception as e:
        logger.warning(f"   ⚠️ Seed skipped: {e}")
    
    # Pre-load Whisper model in background (non-blocking)
    import threading
    def preload_whisper():
        try:
            from app.voice.stt import get_whisper_model
            get_whisper_model()
            logger.info("   ✅ Whisper model loaded")
        except Exception as e:
            logger.warning(f"   ⚠️ Whisper preload failed: {e}")
    
    threading.Thread(target=preload_whisper, daemon=True).start()
    
    yield
    
    logger.info("👋 Shutting down Voice Agent POC...")


app = FastAPI(
    title="Voice Agent POC",
    description="""
    A Sierra AI-inspired conversational AI system.
    
    ## Features
    - 💬 **Chat**: Natural language conversations
    - 🎤 **Voice**: Speech-to-text and text-to-speech
    - 📚 **RAG**: Document-grounded responses
    - 🔧 **Tools**: Database operations via natural language
    
    ## Stack (Option A: Lightweight)
    - LLM: Ollama + Llama 3.2
    - STT: Whisper (local)
    - TTS: pyttsx3
    - RAG: LangChain + ChromaDB
    - DB: SQLite
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
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
    return {
        "status": "healthy",
        "version": "0.1.0",
        "stack": "Option A: Lightweight",
        "llm": settings.llm_model,
        "ollama_url": settings.ollama_base_url
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Voice Agent POC",
        "description": "Sierra AI-inspired conversational AI",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
