"""
Document management API endpoints.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import os
import logging
from pathlib import Path

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class Document(BaseModel):
    id: str
    name: str
    size: int
    chunks: int = 0


class DocumentListResponse(BaseModel):
    documents: List[Document]
    total_chunks: int = 0


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and index a document for RAG.
    """
    # Ensure documents directory exists
    docs_dir = Path(settings.documents_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = docs_dir / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    logger.info(f"Uploaded document: {file.filename}")
    
    # Process and index document
    try:
        from app.rag.chunker import chunk_document
        from app.rag.vectorstore import add_documents
        
        chunks = chunk_document(str(file_path))
        num_chunks = add_documents(chunks)
        
        logger.info(f"Indexed {num_chunks} chunks from {file.filename}")
        
        return {
            "message": f"Document '{file.filename}' uploaded and indexed",
            "file_path": str(file_path),
            "chunks": num_chunks
        }
    except Exception as e:
        logger.error(f"Failed to index document: {e}")
        return {
            "message": f"Document '{file.filename}' uploaded (indexing failed: {e})",
            "file_path": str(file_path),
            "chunks": 0
        }


@router.post("/index")
async def index_all_documents():
    """
    Index all documents in the documents directory.
    """
    from app.rag.chunker import process_documents_directory
    from app.rag.vectorstore import add_documents, get_collection_stats
    
    try:
        # Process all documents
        all_chunks = process_documents_directory()
        
        if all_chunks:
            num_added = add_documents(all_chunks)
            stats = get_collection_stats()
            
            return {
                "message": f"Indexed {num_added} chunks from documents",
                "total_documents": stats["count"]
            }
        else:
            return {
                "message": "No documents found to index",
                "total_documents": 0
            }
    
    except Exception as e:
        logger.error(f"Failed to index documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=DocumentListResponse)
async def list_documents():
    """
    List all documents and their indexing status.
    """
    docs_dir = Path(settings.documents_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    documents = []
    supported_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}
    
    for file_path in docs_dir.iterdir():
        if file_path.suffix.lower() in supported_extensions:
            documents.append(Document(
                id=file_path.name,
                name=file_path.name,
                size=file_path.stat().st_size,
                chunks=0  # TODO: Get actual chunk count per doc
            ))
    
    # Get total indexed chunks
    try:
        from app.rag.vectorstore import get_collection_stats
        stats = get_collection_stats()
        total_chunks = stats["count"]
    except:
        total_chunks = 0
    
    return DocumentListResponse(
        documents=documents,
        total_chunks=total_chunks
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and remove from vector store.
    """
    file_path = Path(settings.documents_dir) / document_id
    
    if file_path.exists():
        file_path.unlink()
        # TODO: Remove from vector store by source metadata
        logger.info(f"Deleted document: {document_id}")
        return {"message": f"Document '{document_id}' deleted"}
    
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/stats")
async def get_stats():
    """Get document indexing statistics."""
    try:
        from app.rag.vectorstore import get_collection_stats
        return get_collection_stats()
    except Exception as e:
        return {"error": str(e), "count": 0}
