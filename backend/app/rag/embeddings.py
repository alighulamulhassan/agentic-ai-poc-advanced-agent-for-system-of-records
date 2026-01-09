"""
Embedding service using sentence-transformers (local).
No API calls needed - runs entirely on your machine.
"""
from typing import List
from sentence_transformers import SentenceTransformer
from app.config import settings

# Global model instance (loaded once)
_model: SentenceTransformer = None


def get_embedding_model() -> SentenceTransformer:
    """Get or load the embedding model."""
    global _model
    if _model is None:
        print(f"📦 Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        print(f"✅ Embedding model loaded")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.
    Uses local sentence-transformers model.
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Generate embedding for a single query."""
    model = get_embedding_model()
    embedding = model.encode(query, convert_to_numpy=True)
    return embedding.tolist()


class LocalEmbeddings:
    """
    LangChain-compatible embedding class using local models.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None
    
    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()



