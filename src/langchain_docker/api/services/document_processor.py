"""Document processor for parsing and chunking documents."""

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.api.services.opensearch_store import DocumentChunk
from langchain_docker.core.config import (
    get_rag_chunk_overlap,
    get_rag_chunk_size,
    get_docling_max_tokens,
    is_docling_ocr_enabled,
    get_docling_tokenizer,
    is_docling_table_extraction_enabled,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """A processed document with its chunks."""

    id: str
    filename: str
    content_type: str
    original_content: str
    chunks: list[DocumentChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class DocumentProcessor:
    """Processor for parsing and chunking documents.

    Supports PDF (via Docling), Markdown, and plain text files. Splits documents
    into chunks and generates embeddings for vector search.

    For PDFs, uses Docling for structure-aware extraction that preserves:
    - Document hierarchy (headings, sections)
    - Tables as markdown
    - Page numbers and rich metadata
    """

    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "text/markdown": "markdown",
        "text/plain": "text",
        "text/x-markdown": "markdown",
        ".pdf": "pdf",
        ".md": "markdown",
        ".txt": "text",
    }

    def __init__(
        self,
        embedding_service: EmbeddingService,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        """Initialize the document processor.

        Args:
            embedding_service: Service for generating embeddings
            chunk_size: Size of text chunks (defaults to env)
            chunk_overlap: Overlap between chunks (defaults to env)
        """
        self._embedding_service = embedding_service
        self._chunk_size = chunk_size or get_rag_chunk_size()
        self._chunk_overlap = chunk_overlap or get_rag_chunk_overlap()

        # Text splitter for markdown/text files
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        # Initialize Docling processor for PDFs
        self._docling_processor = self._init_docling()

        logger.info(
            f"DocumentProcessor initialized: chunk_size={self._chunk_size}, "
            f"chunk_overlap={self._chunk_overlap}, docling=True"
        )

    def _init_docling(self):
        """Initialize Docling for PDF processing.

        Returns:
            DoclingProcessor instance

        Raises:
            ImportError: If Docling is not installed
        """
        from langchain_docker.api.services.docling_processor import DoclingProcessor

        processor = DoclingProcessor(
            tokenizer=get_docling_tokenizer(),
            max_tokens=get_docling_max_tokens(),
            enable_ocr=is_docling_ocr_enabled(),
            enable_table_extraction=is_docling_table_extraction_enabled(),
        )
        logger.info("Docling initialized for PDF processing")
        return processor

    def detect_content_type(self, filename: str, content_type: str | None = None) -> str:
        """Detect the content type from filename or MIME type.

        Args:
            filename: Original filename
            content_type: MIME type if provided

        Returns:
            Normalized content type (pdf, markdown, text)

        Raises:
            ValueError: If content type is not supported
        """
        # Try MIME type first
        if content_type and content_type in self.SUPPORTED_TYPES:
            return self.SUPPORTED_TYPES[content_type]

        # Fall back to extension
        for ext, doc_type in self.SUPPORTED_TYPES.items():
            if ext.startswith(".") and filename.lower().endswith(ext):
                return doc_type

        raise ValueError(
            f"Unsupported file type for '{filename}'. "
            f"Supported: PDF, Markdown (.md), Text (.txt)"
        )

    def _process_pdf(
        self,
        content: bytes,
        doc_id: str,
        doc_metadata: dict[str, Any],
    ) -> tuple[list[DocumentChunk], str]:
        """Process PDF using Docling with structure-aware chunking.

        Args:
            content: PDF file content as bytes
            doc_id: Document ID
            doc_metadata: Base document metadata

        Returns:
            Tuple of (list of DocumentChunk objects, full text content)

        Raises:
            ValueError: If PDF processing fails
        """
        # Save to temp file for Docling (it needs file path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Process with Docling
            docling_chunks = self._docling_processor.process_pdf(tmp_path)

            # Generate embeddings for all chunks
            chunk_texts = [c.content for c in docling_chunks]
            logger.info(f"Generating embeddings for {len(chunk_texts)} Docling chunks")
            embeddings = self._embedding_service.embed_documents(chunk_texts)

            # Create DocumentChunk objects with rich metadata
            chunks = []
            for i, (docling_chunk, embedding) in enumerate(zip(docling_chunks, embeddings)):
                # Merge base metadata with Docling metadata
                chunk_metadata = {
                    **doc_metadata,
                    **docling_chunk.metadata,
                    "processor": "docling",
                }

                chunk = DocumentChunk(
                    id=f"{doc_id}_chunk_{i}",
                    document_id=doc_id,
                    content=docling_chunk.content,
                    embedding=embedding,
                    metadata=chunk_metadata,
                    chunk_index=i,
                )
                chunks.append(chunk)

            # Get full text for original_content
            full_text = self._docling_processor.get_full_text(tmp_path)

            return chunks, full_text

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _process_text(
        self,
        content: str,
        doc_id: str,
        doc_metadata: dict[str, Any],
    ) -> list[DocumentChunk]:
        """Process text/markdown content with standard chunking.

        Args:
            content: Text content
            doc_id: Document ID
            doc_metadata: Base document metadata

        Returns:
            List of DocumentChunk objects
        """
        # Split into chunks
        text_chunks = self._splitter.split_text(content)

        # Add processor info to metadata
        chunk_metadata = {**doc_metadata, "processor": "text"}

        # Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(text_chunks)} chunks")
        embeddings = self._embedding_service.embed_documents(text_chunks)

        # Create DocumentChunk objects
        chunks = []
        for i, (text, embedding) in enumerate(zip(text_chunks, embeddings)):
            chunk = DocumentChunk(
                id=f"{doc_id}_chunk_{i}",
                document_id=doc_id,
                content=text,
                embedding=embedding,
                metadata=chunk_metadata,
                chunk_index=i,
            )
            chunks.append(chunk)

        return chunks

    def process(
        self,
        content: bytes | str,
        filename: str,
        content_type: str | None = None,
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProcessedDocument:
        """Process a document into chunks with embeddings.

        For PDFs, uses Docling for structure-aware processing.
        For text/markdown, uses RecursiveCharacterTextSplitter.

        Args:
            content: Document content (bytes or string)
            filename: Original filename
            content_type: MIME type (optional, detected from filename)
            collection: Optional collection name
            metadata: Additional metadata

        Returns:
            ProcessedDocument with chunks and embeddings

        Raises:
            ValueError: If document type is not supported or processing fails
        """
        # Detect content type
        doc_type = self.detect_content_type(filename, content_type)

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Build base metadata
        doc_metadata = {
            "filename": filename,
            "content_type": doc_type,
            "collection": collection or "",
            "created_at": datetime.utcnow().isoformat(),
            "original_size": len(content) if isinstance(content, bytes) else len(content.encode()),
            **(metadata or {}),
        }

        if doc_type == "pdf":
            # Ensure content is bytes
            if isinstance(content, str):
                content = content.encode("utf-8")

            logger.info(f"Processing PDF with Docling: {filename}")
            chunks, text_content = self._process_pdf(content, doc_id, doc_metadata)

            return ProcessedDocument(
                id=doc_id,
                filename=filename,
                content_type=doc_type,
                original_content=text_content,
                chunks=chunks,
                metadata={**doc_metadata, "processor": "docling"},
            )
        else:
            # Text or markdown
            if isinstance(content, bytes):
                text_content = content.decode("utf-8")
            else:
                text_content = content

            logger.info(f"Processing text file: {filename}")
            chunks = self._process_text(text_content, doc_id, doc_metadata)

            return ProcessedDocument(
                id=doc_id,
                filename=filename,
                content_type=doc_type,
                original_content=text_content,
                chunks=chunks,
                metadata={**doc_metadata, "processor": "text"},
            )

    def process_text(
        self,
        text: str,
        title: str = "Untitled",
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProcessedDocument:
        """Process plain text content directly.

        Args:
            text: Plain text content
            title: Document title
            collection: Optional collection name
            metadata: Additional metadata

        Returns:
            ProcessedDocument with chunks and embeddings
        """
        return self.process(
            content=text,
            filename=f"{title}.txt",
            content_type="text/plain",
            collection=collection,
            metadata=metadata,
        )
