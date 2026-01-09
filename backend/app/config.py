"""
Application configuration using pydantic-settings.
Configured for Option A: Lightweight / Learning-Focused stack.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ===== LLM Settings (Ollama - Local) =====
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"  # or "mistral" for faster responses
    
    # ===== Embedding Settings (Local) =====
    # Using sentence-transformers for local embeddings
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast, good quality
    # Alternative: "BAAI/bge-small-en-v1.5" for better quality
    
    # ===== Voice Settings (Local) =====
    # Whisper model size: tiny, base, small, medium, large
    whisper_model: str = "base"  # Good balance of speed/quality
    
    # TTS settings (Piper)
    tts_model: str = "en_US-lessac-medium"  # Good quality English voice
    tts_rate: int = 22050  # Sample rate
    
    # ===== RAG Settings =====
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_k: int = 4
    
    # ===== Database =====
    database_url: str = "sqlite+aiosqlite:///./data/db/app.db"
    
    # ===== Vector Store =====
    chroma_persist_dir: str = "../data/chroma"
    chroma_collection_name: str = "documents"
    
    # ===== Paths =====
    documents_dir: str = "../data/documents"
    audio_dir: str = "../data/audio"
    
    # ===== Optional: OpenAI Fallback =====
    # Set these if you want to switch to cloud APIs
    openai_api_key: str = ""
    use_openai: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def base_path(self) -> Path:
        return Path(__file__).parent.parent.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
