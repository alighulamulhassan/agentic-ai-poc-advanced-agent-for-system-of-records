"""
Document chunking strategies for RAG.
"""
from typing import List, Dict, Any
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)
from langchain.schema import Document
from app.config import settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Get the default text splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )


def load_document(file_path: str) -> List[Document]:
    """
    Load a document from file path.
    Supports PDF, DOCX, TXT, and MD files.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    loaders = {
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".doc": Docx2txtLoader,
        ".txt": TextLoader,
        ".md": TextLoader,  # Use TextLoader for markdown (simpler, no extra deps)
    }
    
    if suffix not in loaders:
        raise ValueError(f"Unsupported file type: {suffix}")
    
    loader_class = loaders[suffix]
    loader = loader_class(str(path))
    
    return loader.load()


def chunk_document(file_path: str) -> List[Document]:
    """
    Load and chunk a document for indexing.
    Returns list of Document objects with metadata.
    """
    # Load the document
    documents = load_document(file_path)
    
    # Split into chunks
    splitter = get_text_splitter()
    chunks = splitter.split_documents(documents)
    
    # Add source metadata
    file_name = Path(file_path).name
    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = file_name
        chunk.metadata["chunk_index"] = i
    
    return chunks


def chunk_text(text: str, source: str = "unknown") -> List[Document]:
    """
    Chunk raw text into documents.
    """
    splitter = get_text_splitter()
    chunks = splitter.create_documents(
        texts=[text],
        metadatas=[{"source": source}]
    )
    
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
    
    return chunks


def process_documents_directory(directory: str = None) -> List[Document]:
    """
    Process all documents in a directory.
    """
    if directory is None:
        directory = settings.documents_dir
    
    path = Path(directory)
    all_chunks = []
    
    supported_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}
    
    for file_path in path.iterdir():
        if file_path.suffix.lower() in supported_extensions:
            try:
                chunks = chunk_document(str(file_path))
                all_chunks.extend(chunks)
                print(f"✅ Processed: {file_path.name} ({len(chunks)} chunks)")
            except Exception as e:
                print(f"❌ Failed to process {file_path.name}: {e}")
    
    return all_chunks

