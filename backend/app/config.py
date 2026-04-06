"""
Application configuration using pydantic-settings.
All values can be overridden via environment variables or .env file.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""

    # ===== LLM Settings =====
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"

    # ===== Embeddings =====
    embedding_model: str = "all-MiniLM-L6-v2"

    # ===== Voice =====
    whisper_model: str = "base"
    tts_model: str = "en_US-lessac-medium"
    tts_rate: int = 22050

    # ===== RAG =====
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

    # ===== OpenAI fallback =====
    openai_api_key: str = ""
    use_openai: bool = False

    # ===== AWS / Bedrock (production) =====
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    use_bedrock: bool = False

    # ===== Security =====
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_expiry_minutes: int = 60
    api_keys: str = "dev-key-12345"          # comma-separated
    environment: str = "development"

    # ===== Guardrails =====
    hitl_enabled: bool = True
    hitl_threshold: float = 0.7              # risk score above which HITL triggers
    hitl_timeout_seconds: int = 300
    hitl_transport: str = "memory"           # memory | webhook | sns
    hitl_webhook_url: str = ""
    hitl_sns_topic_arn: str = ""
    reflection_enabled: bool = True
    policy_strict_mode: bool = True

    # ===== Observability =====
    otlp_endpoint: str = ""                  # e.g. http://localhost:4317
    service_name: str = "agent-poc"
    metrics_backend: str = "memory"          # memory | prometheus | cloudwatch
    cloudwatch_namespace: str = "AgentPOC"
    xray_enabled: bool = False

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
