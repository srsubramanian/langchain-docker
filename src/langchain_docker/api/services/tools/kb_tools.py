"""Knowledge Base tool provider for RAG operations."""

import logging
from typing import TYPE_CHECKING, Callable, Optional

from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)
from langchain_docker.core.tracing import get_tracer

if TYPE_CHECKING:
    from langchain_docker.api.services.skill_registry import (
        KnowledgeBaseSkill,
        SkillRegistry,
    )

logger = logging.getLogger(__name__)


class KBToolProvider(ToolProvider):
    """Tool provider for Knowledge Base / RAG operations.

    Provides tools for:
    - Loading KB skill (progressive disclosure)
    - Searching the knowledge base
    - Listing documents
    - Listing collections
    - Getting KB statistics
    """

    def get_skill_id(self) -> str:
        """Return the Knowledge Base skill ID."""
        return "knowledge_base"

    def get_templates(self) -> list[ToolTemplate]:
        """Return all Knowledge Base tool templates."""
        return [
            ToolTemplate(
                id="load_kb_skill",
                name="Load Knowledge Base Skill",
                description="Load Knowledge Base skill with status and instructions (progressive disclosure)",
                category="knowledge",
                parameters=[],
                factory=self._create_load_kb_skill_tool,
            ),
            ToolTemplate(
                id="kb_search",
                name="Knowledge Base Search",
                description="Search the knowledge base for relevant documents using semantic search",
                category="knowledge",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query to find relevant documents",
                        required=True,
                    ),
                    ToolParameter(
                        name="top_k",
                        type="int",
                        description="Number of results to return (default 5)",
                        default=5,
                        required=False,
                    ),
                    ToolParameter(
                        name="collection",
                        type="string",
                        description="Optional collection filter",
                        required=False,
                    ),
                ],
                factory=self._create_kb_search_tool,
            ),
            ToolTemplate(
                id="kb_list_documents",
                name="List KB Documents",
                description="List documents in the knowledge base",
                category="knowledge",
                parameters=[
                    ToolParameter(
                        name="collection",
                        type="string",
                        description="Optional collection filter",
                        required=False,
                    ),
                ],
                factory=self._create_kb_list_documents_tool,
            ),
            ToolTemplate(
                id="kb_list_collections",
                name="List KB Collections",
                description="List all collections in the knowledge base",
                category="knowledge",
                parameters=[],
                factory=self._create_kb_list_collections_tool,
            ),
            ToolTemplate(
                id="kb_get_stats",
                name="Get KB Statistics",
                description="Get knowledge base statistics including document and chunk counts",
                category="knowledge",
                parameters=[],
                factory=self._create_kb_get_stats_tool,
            ),
        ]

    def _create_load_kb_skill_tool(self) -> Callable[[], str]:
        """Create load KB skill tool for progressive disclosure."""
        kb_skill = self.get_skill()

        def load_kb_skill() -> str:
            """Load the Knowledge Base skill with status and instructions.

            Call this tool before searching the knowledge base to understand
            its current status, available documents, and usage guidelines.

            Returns:
                Knowledge base status, capabilities, and search guidelines
            """
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span("skill.load_core") as span:
                    span.set_attribute("skill.id", "knowledge_base")
                    span.set_attribute("skill.name", kb_skill.name)
                    span.set_attribute("skill.category", kb_skill.category)
                    content = kb_skill.load_core()
                    span.set_attribute("content_length", len(content))
                    return content
            return kb_skill.load_core()

        return load_kb_skill

    def _create_kb_search_tool(self) -> Callable[[str, int, Optional[str]], str]:
        """Create KB search tool."""
        kb_skill = self.get_skill()

        def kb_search(
            query: str,
            top_k: int = 5,
            collection: Optional[str] = None,
        ) -> str:
            """Search the knowledge base for relevant documents.

            Uses semantic search to find documents matching the query.
            Results are ranked by relevance score.

            Args:
                query: The search query to find relevant documents
                top_k: Number of results to return (default 5)
                collection: Optional collection to filter results

            Returns:
                Formatted search results with content snippets and sources
            """
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span("kb.search") as span:
                    span.set_attribute("query", query)
                    span.set_attribute("top_k", top_k)
                    if collection:
                        span.set_attribute("collection", collection)
                    result = kb_skill.search(query, top_k, collection)
                    span.set_attribute("result_length", len(result))
                    return result
            return kb_skill.search(query, top_k, collection)

        return kb_search

    def _create_kb_list_documents_tool(self) -> Callable[[Optional[str]], str]:
        """Create KB list documents tool."""
        kb_skill = self.get_skill()

        def kb_list_documents(collection: Optional[str] = None) -> str:
            """List documents in the knowledge base.

            Args:
                collection: Optional collection to filter documents

            Returns:
                Formatted list of documents with metadata
            """
            return kb_skill.list_documents(collection)

        return kb_list_documents

    def _create_kb_list_collections_tool(self) -> Callable[[], str]:
        """Create KB list collections tool."""
        kb_skill = self.get_skill()

        def kb_list_collections() -> str:
            """List all collections in the knowledge base.

            Returns:
                Formatted list of collections with document counts
            """
            return kb_skill.list_collections()

        return kb_list_collections

    def _create_kb_get_stats_tool(self) -> Callable[[], str]:
        """Create KB get stats tool."""
        kb_skill = self.get_skill()

        def kb_get_stats() -> str:
            """Get knowledge base statistics.

            Returns:
                Statistics including document count, chunk count,
                collection count, and index size
            """
            return kb_skill.get_stats()

        return kb_get_stats
