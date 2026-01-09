"""
RAG retriever - the interface for document search.
This is what the agent tools call.
"""
from typing import Dict, Any, List
from app.rag.vectorstore import search_with_scores, get_collection_stats


def search(query: str, k: int = 4) -> Dict[str, Any]:
    """
    Search documents and return formatted results for the agent.
    This is the main entry point for the search_documents tool.
    """
    try:
        # Get collection stats first
        stats = get_collection_stats()
        
        if stats["count"] == 0:
            return {
                "results": [],
                "message": "No documents have been indexed yet. Please upload some documents first.",
                "query": query
            }
        
        # Search for similar documents
        results = search_with_scores(query, k=k)
        
        if not results:
            return {
                "results": [],
                "message": f"No relevant documents found for: '{query}'",
                "query": query
            }
        
        # Format results
        formatted_results = []
        for doc, score in results:
            # Convert distance to similarity score (lower distance = higher similarity)
            similarity = max(0, 1 - score)  # Normalize to 0-1
            
            formatted_results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "relevance_score": round(similarity, 3)
            })
        
        return {
            "results": formatted_results,
            "query": query,
            "total_documents": stats["count"],
            "results_count": len(formatted_results)
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to search documents. The knowledge base may not be initialized.",
            "query": query
        }


def get_context_for_query(query: str, k: int = 4) -> str:
    """
    Get formatted context string for RAG.
    Used for injecting into prompts.
    """
    results = search(query, k=k)
    
    if not results.get("results"):
        return ""
    
    context_parts = []
    for i, result in enumerate(results["results"], 1):
        source = result["source"]
        content = result["content"]
        context_parts.append(f"[Source {i}: {source}]\n{content}")
    
    return "\n\n---\n\n".join(context_parts)


def format_sources(results: List[Dict]) -> str:
    """Format sources for citation in responses."""
    if not results:
        return ""
    
    sources = set(r.get("source", "unknown") for r in results)
    return "Sources: " + ", ".join(sources)



