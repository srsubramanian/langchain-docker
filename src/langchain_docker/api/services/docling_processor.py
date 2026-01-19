"""Docling-based PDF processor using LangChain integration."""

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DoclingChunk:
    """A chunk extracted by Docling with rich metadata."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    content_type: str = "text"


class DoclingProcessor:
    """Processor for PDF documents using langchain-docling.

    Provides structure-aware PDF extraction that preserves:
    - Document hierarchy (headings, sections)
    - Tables as markdown
    - Rich metadata per chunk (page, bounding box, origin)

    Uses DoclingLoader with HybridChunker for tokenizer-aligned chunking
    that respects document structure boundaries.
    """

    def __init__(
        self,
        tokenizer: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_tokens: int = 512,
        enable_ocr: bool = False,
        enable_table_extraction: bool = True,
    ):
        """Initialize the Docling processor.

        Args:
            tokenizer: Tokenizer name for HybridChunker (should match embedding model)
            max_tokens: Maximum tokens per chunk
            enable_ocr: Enable OCR for scanned documents (requires tesseract)
            enable_table_extraction: Enable table structure extraction
        """
        self._tokenizer = tokenizer
        self._max_tokens = max_tokens
        self._enable_ocr = enable_ocr
        self._enable_table_extraction = enable_table_extraction

        # Lazy initialization
        self._chunker = None
        self._converter = None

        logger.info(
            f"DoclingProcessor configured: tokenizer={tokenizer}, "
            f"max_tokens={max_tokens}, ocr={enable_ocr}, tables={enable_table_extraction}"
        )

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Docling components."""
        if self._chunker is not None:
            return

        from docling.chunking import HybridChunker
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
        from docling.datamodel.base_models import InputFormat

        # Configure PDF pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self._enable_ocr
        pipeline_options.do_table_structure = self._enable_table_extraction

        if self._enable_table_extraction:
            pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

        # Create document converter
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Create hybrid chunker
        self._chunker = HybridChunker(
            tokenizer=self._tokenizer,
            max_tokens=self._max_tokens,
        )

        logger.info("DoclingProcessor initialized successfully")

    def process_pdf(self, pdf_path: str | Path) -> list[DoclingChunk]:
        """Process a PDF file and return structure-aware chunks.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of DoclingChunk objects with rich metadata

        Raises:
            ValueError: If processing fails
        """
        self._ensure_initialized()

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise ValueError(f"PDF file not found: {pdf_path}")

        try:
            from langchain_docling import DoclingLoader
            from langchain_docling.loader import ExportType

            logger.info(f"Processing PDF with DoclingLoader: {pdf_path.name}")

            # Use DoclingLoader with DOC_CHUNKS export type
            loader = DoclingLoader(
                file_path=str(pdf_path),
                export_type=ExportType.DOC_CHUNKS,
                converter=self._converter,
                chunker=self._chunker,
            )

            # Load documents
            docs = loader.load()

            # Convert LangChain Documents to DoclingChunks
            chunks = []
            for doc in docs:
                # Extract metadata from dl_meta if available
                dl_meta = doc.metadata.get("dl_meta", {})

                # Extract headings
                headings = []
                if isinstance(dl_meta, dict):
                    headings = dl_meta.get("headings", [])

                # Extract page number from doc_items
                page = None
                element_type = "text"
                if isinstance(dl_meta, dict) and "doc_items" in dl_meta:
                    doc_items = dl_meta.get("doc_items", [])
                    if doc_items:
                        first_item = doc_items[0]
                        # Get element type from label
                        if "label" in first_item:
                            element_type = str(first_item["label"])
                        # Get page from prov
                        if "prov" in first_item and first_item["prov"]:
                            first_prov = first_item["prov"][0]
                            if "page_no" in first_prov:
                                page = first_prov["page_no"]

                # Build heading context string
                heading_context = " > ".join(headings) if headings else None

                # Extract bounding box if available
                bbox = None
                if isinstance(dl_meta, dict) and "doc_items" in dl_meta:
                    doc_items = dl_meta.get("doc_items", [])
                    if doc_items and "prov" in doc_items[0] and doc_items[0]["prov"]:
                        first_prov = doc_items[0]["prov"][0]
                        if "bbox" in first_prov:
                            bbox = first_prov["bbox"]

                chunk_metadata = {
                    "headings": headings,
                    "page": page,
                    "element_type": element_type,
                    "heading_context": heading_context,
                    "source": doc.metadata.get("source"),
                    "bbox": bbox,  # Bounding box for advanced grounding
                }

                chunks.append(DoclingChunk(
                    content=doc.page_content,
                    metadata=chunk_metadata,
                    content_type=element_type,
                ))

            logger.info(f"DoclingLoader extracted {len(chunks)} chunks from {pdf_path.name}")
            return chunks

        except Exception as e:
            logger.error(f"Docling processing failed for {pdf_path}: {e}")
            raise ValueError(f"Failed to process PDF with Docling: {e}")

    def get_full_text(self, pdf_path: str | Path) -> str:
        """Extract full text from PDF using Docling.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Full text content of the PDF as markdown
        """
        self._ensure_initialized()

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise ValueError(f"PDF file not found: {pdf_path}")

        try:
            from langchain_docling import DoclingLoader
            from langchain_docling.loader import ExportType

            # Use MARKDOWN export for full text
            loader = DoclingLoader(
                file_path=str(pdf_path),
                export_type=ExportType.MARKDOWN,
                converter=self._converter,
            )

            docs = loader.load()

            # Combine all document contents
            return "\n\n".join(doc.page_content for doc in docs)

        except Exception as e:
            logger.error(f"Docling text extraction failed for {pdf_path}: {e}")
            raise ValueError(f"Failed to extract text with Docling: {e}")
