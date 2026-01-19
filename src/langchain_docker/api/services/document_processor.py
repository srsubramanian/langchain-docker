"""Document processor for parsing and chunking documents."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_docker.api.services.embedding_service import EmbeddingService
from langchain_docker.api.services.opensearch_store import DocumentChunk
from langchain_docker.core.config import get_rag_chunk_overlap, get_rag_chunk_size

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

    Supports PDF, Markdown, and plain text files. Splits documents
    into chunks and generates embeddings for vector search.
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

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        logger.info(
            f"DocumentProcessor initialized: chunk_size={self._chunk_size}, "
            f"chunk_overlap={self._chunk_overlap}"
        )

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

    def parse_content(
        self,
        content: bytes | str,
        content_type: str,
    ) -> str:
        """Parse document content to plain text.

        Args:
            content: Raw document content (bytes for PDF, str for text)
            content_type: Normalized content type

        Returns:
            Extracted plain text content
        """
        if content_type == "pdf":
            return self._parse_pdf(content)
        elif content_type in ("markdown", "text"):
            if isinstance(content, bytes):
                return content.decode("utf-8")
            return content
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    def _parse_pdf(self, content: bytes | str) -> str:
        """Parse PDF content to plain text.

        Args:
            content: PDF file content as bytes

        Returns:
            Extracted text from PDF
        """
        try:
            from pypdf import PdfReader

            if isinstance(content, str):
                content = content.encode("utf-8")

            reader = PdfReader(BytesIO(content))
            text_parts = []

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(f"[Page {page_num + 1}]\n{text}")

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise ValueError(f"Failed to parse PDF: {e}")

    def process(
        self,
        content: bytes | str,
        filename: str,
        content_type: str | None = None,
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProcessedDocument:
        """Process a document into chunks with embeddings.

        Args:
            content: Document content (bytes or string)
            filename: Original filename
            content_type: MIME type (optional, detected from filename)
            collection: Optional collection name
            metadata: Additional metadata

        Returns:
            ProcessedDocument with chunks and embeddings
        """
        # Detect content type
        doc_type = self.detect_content_type(filename, content_type)

        # Parse content to text
        text_content = self.parse_content(content, doc_type)

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Split into chunks
        text_chunks = self._splitter.split_text(text_content)

        # Build metadata
        doc_metadata = {
            "filename": filename,
            "content_type": doc_type,
            "collection": collection or "",
            "created_at": datetime.utcnow().isoformat(),
            "original_size": len(content) if isinstance(content, bytes) else len(content.encode()),
            **(metadata or {}),
        }

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
                metadata=doc_metadata,
                chunk_index=i,
            )
            chunks.append(chunk)

        return ProcessedDocument(
            id=doc_id,
            filename=filename,
            content_type=doc_type,
            original_content=text_content,
            chunks=chunks,
            metadata=doc_metadata,
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
