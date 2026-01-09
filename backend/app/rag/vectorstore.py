"""
Vector store management using ChromaDB.
Stores document embeddings for semantic search.
"""
from typing import List, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain.schema import Document
from langchain_chroma import Chroma

from app.config import settings
from app.rag.embeddings import LocalEmbeddings

# Global vectorstore instance
_vectorstore: Optional[Chroma] = None


def get_vectorstore() -> Chroma:
    """Get or create the vector store."""
    global _vectorstore
    
    if _vectorstore is None:
        # Ensure persist directory exists
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Create embeddings
        embeddings = LocalEmbeddings()
        
        # Create Chroma vectorstore
        _vectorstore = Chroma(
            collection_name=settings.chroma_collection_name,
            embedding_function=embeddings,
            persist_directory=str(persist_dir),
        )
        
        print(f"✅ Vector store initialized at {persist_dir}")
    
    return _vectorstore


def add_documents(documents: List[Document]) -> int:
    """
    Add documents to the vector store.
    Returns the number of documents added.
    """
    if not documents:
        return 0
    
    vectorstore = get_vectorstore()
    vectorstore.add_documents(documents)
    
    return len(documents)


def search_similar(query: str, k: int = None) -> List[Document]:
    """
    Search for similar documents.
    Returns top k most similar documents.
    """
    if k is None:
        k = settings.retrieval_k
    
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(query, k=k)
    
    return results


def search_with_scores(query: str, k: int = None) -> List[tuple]:
    """
    Search with relevance scores.
    Returns list of (Document, score) tuples.
    """
    if k is None:
        k = settings.retrieval_k
    
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=k)
    
    return results


def delete_collection():
    """Delete all documents from the collection."""
    global _vectorstore
    
    vectorstore = get_vectorstore()
    vectorstore.delete_collection()
    _vectorstore = None
    
    print("🗑️ Vector store collection deleted")


def get_collection_stats() -> dict:
    """Get statistics about the vector store."""
    vectorstore = get_vectorstore()
    collection = vectorstore._collection
    
    return {
        "name": settings.chroma_collection_name,
        "count": collection.count(),
        "persist_directory": settings.chroma_persist_dir
    }



