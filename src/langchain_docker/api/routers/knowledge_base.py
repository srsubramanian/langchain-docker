"""Knowledge Base API router for RAG functionality."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from langchain_docker.api.dependencies import get_knowledge_base_service
from langchain_docker.api.schemas.knowledge_base import (
    CollectionListResponse,
    CollectionResponse,
    DeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    FileUploadResponse,
    KBStatsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from langchain_docker.api.services.knowledge_base_service import KnowledgeBaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


def _check_available(kb_service: KnowledgeBaseService) -> None:
    """Check if knowledge base is available.

    Raises:
        HTTPException: If knowledge base is not available
    """
    if not kb_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Knowledge base is not available. Check OpenSearch connection.",
        )


@router.get("/stats", response_model=KBStatsResponse)
async def get_stats(
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KBStatsResponse:
    """Get knowledge base statistics.

    Returns document count, chunk count, collection count, and availability status.
    """
    stats = kb_service.get_stats()
    return KBStatsResponse(
        total_documents=stats.total_documents,
        total_chunks=stats.total_chunks,
        total_collections=stats.total_collections,
        index_size=stats.index_size,
        last_updated=stats.last_updated,
        available=stats.available,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    collection: str | None = None,
    limit: int = 100,
    offset: int = 0,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentListResponse:
    """List all documents in the knowledge base.

    Args:
        collection: Optional collection filter
        limit: Maximum documents to return
        offset: Pagination offset
    """
    _check_available(kb_service)

    documents = kb_service.list_documents(
        collection=collection,
        limit=limit,
        offset=offset,
    )

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                content_type=doc.content_type,
                chunk_count=doc.chunk_count,
                size=doc.size,
                collection=doc.collection,
                created_at=doc.created_at,
                metadata=doc.metadata,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentResponse:
    """Get document information by ID."""
    _check_available(kb_service)

    document = kb_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        chunk_count=document.chunk_count,
        size=document.size,
        collection=document.collection,
        created_at=document.created_at,
        metadata=document.metadata,
    )


@router.post("/documents", response_model=FileUploadResponse)
async def upload_document(
    request: DocumentUploadRequest,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> FileUploadResponse:
    """Upload text content as a document.

    Use this endpoint to upload plain text or markdown content directly.
    For file uploads, use the /documents/upload endpoint.
    """
    _check_available(kb_service)

    try:
        document = kb_service.upload_document(
            content=request.content,
            filename=request.filename,
            collection=request.collection,
            metadata=request.metadata,
        )

        return FileUploadResponse(
            document=DocumentResponse(
                id=document.id,
                filename=document.filename,
                content_type=document.content_type,
                chunk_count=document.chunk_count,
                size=document.size,
                collection=document.collection,
                created_at=document.created_at,
                metadata=document.metadata,
            ),
            message=f"Document '{document.filename}' uploaded successfully with {document.chunk_count} chunks",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    collection: str | None = Form(None),
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> FileUploadResponse:
    """Upload a file to the knowledge base.

    Supports PDF, Markdown (.md), and Text (.txt) files.
    """
    _check_available(kb_service)

    # Read file content
    content = await file.read()
    filename = file.filename or "unknown"

    try:
        document = kb_service.upload_document(
            content=content,
            filename=filename,
            content_type=file.content_type,
            collection=collection,
        )

        return FileUploadResponse(
            document=DocumentResponse(
                id=document.id,
                filename=document.filename,
                content_type=document.content_type,
                chunk_count=document.chunk_count,
                size=document.size,
                collection=document.collection,
                created_at=document.created_at,
                metadata=document.metadata,
            ),
            message=f"File '{document.filename}' uploaded successfully with {document.chunk_count} chunks",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DeleteResponse:
    """Delete a document from the knowledge base."""
    _check_available(kb_service)

    success = kb_service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return DeleteResponse(
        success=True,
        message=f"Document '{document_id}' deleted successfully",
    )


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> SearchResponse:
    """Search the knowledge base using semantic search.

    Returns the most relevant document chunks for the query.
    """
    _check_available(kb_service)

    results = kb_service.search(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        collection=request.collection,
    )

    return SearchResponse(
        query=request.query,
        results=[
            SearchResultItem(
                document_id=r.document_id,
                chunk_id=r.chunk_id,
                content=r.content,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ],
        total=len(results),
    )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> CollectionListResponse:
    """List all collections in the knowledge base."""
    _check_available(kb_service)

    collections = kb_service.list_collections()

    return CollectionListResponse(
        collections=[
            CollectionResponse(
                id=col.id,
                name=col.name,
                document_count=col.document_count,
                color=col.color,
            )
            for col in collections
        ],
        total=len(collections),
    )


@router.get("/context")
async def get_context(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    collection: str | None = None,
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> dict[str, Any]:
    """Get formatted context for RAG.

    Returns context ready to be injected into an LLM prompt.
    This is the main endpoint for RAG integration with chat.
    """
    _check_available(kb_service)

    context = kb_service.get_context_for_query(
        query=query,
        top_k=top_k,
        min_score=min_score,
        collection=collection,
    )

    return {
        "query": query,
        "context": context,
        "has_context": bool(context),
    }
