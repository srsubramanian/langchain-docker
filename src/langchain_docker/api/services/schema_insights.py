"""Schema Insights Logger for GraphRAG.

Captures entity types and relationship types discovered during extraction
to help evolve the schema over time. Persists insights to Redis for
durability across container restarts.

Usage:
    insights = SchemaInsightsLogger()
    insights.log_extraction(
        document_id="doc123",
        entities=[("John Smith", "Person"), ("Acme", "Organization")],
        relationships=[("John Smith", "CEO_OF", "Acme")],
    )

    # Later, analyze with:
    # curl http://localhost:8000/api/v1/kb/graph/schema-insights
    # python scripts/schema_discovery.py --insights
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# Redis key prefixes
REDIS_INSIGHTS_LIST_KEY = "schema_insights:logs"
REDIS_ENTITY_COUNTS_KEY = "schema_insights:entity_counts"
REDIS_RELATION_COUNTS_KEY = "schema_insights:relation_counts"
REDIS_DOC_COUNT_KEY = "schema_insights:doc_count"

# Maximum insights to keep in Redis (rolling window)
MAX_INSIGHTS_STORED = 1000


@dataclass
class ExtractionInsight:
    """Single extraction insight record."""

    timestamp: str
    document_id: str
    filename: str | None

    # Entity insights
    entity_types_in_schema: list[str] = field(default_factory=list)
    entity_types_discovered: list[str] = field(default_factory=list)  # Not in schema
    entity_type_counts: dict[str, int] = field(default_factory=dict)

    # Relationship insights
    relation_types_in_schema: list[str] = field(default_factory=list)
    relation_types_discovered: list[str] = field(default_factory=list)  # Not in schema
    relation_type_counts: dict[str, int] = field(default_factory=dict)

    # Sample extractions (for context)
    sample_entities: list[dict[str, str]] = field(default_factory=list)  # [{name, type}]
    sample_relationships: list[dict[str, str]] = field(default_factory=list)  # [{subject, predicate, object}]


class SchemaInsightsLogger:
    """Logger for schema evolution insights with Redis persistence.

    Captures and persists information about entity and relationship types
    discovered during GraphRAG extraction. This data helps identify
    new types that should be added to the schema.

    Storage:
    - Redis (primary): Durable storage across container restarts
    - In-memory (fallback): When Redis is not available

    Thread-safe for concurrent extraction operations.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        configured_entities: list[str] | None = None,
        configured_relations: list[str] | None = None,
        max_samples: int = 10,
    ):
        """Initialize the insights logger.

        Args:
            redis_url: Redis connection URL (default: from environment)
            configured_entities: List of entity types in current schema
            configured_relations: List of relation types in current schema
            max_samples: Maximum sample entities/relations to store per extraction
        """
        self._max_samples = max_samples
        self._lock = Lock()

        # Redis connection
        self._redis = None
        self._redis_available = False
        self._init_redis(redis_url)

        # In-memory fallback storage
        self._memory_insights: list[dict] = []
        self._memory_entity_counts: dict[str, int] = defaultdict(int)
        self._memory_relation_counts: dict[str, int] = defaultdict(int)

        # Load configured schema
        if configured_entities is None:
            from langchain_docker.core.config import get_graph_rag_entities
            self._configured_entities = set(get_graph_rag_entities())
        else:
            self._configured_entities = set(configured_entities)

        if configured_relations is None:
            from langchain_docker.core.config import get_graph_rag_relations
            self._configured_relations = set(get_graph_rag_relations())
        else:
            self._configured_relations = set(configured_relations)

        # Normalize to lowercase for comparison
        self._configured_entities_lower = {e.lower() for e in self._configured_entities}
        self._configured_relations_lower = {r.lower() for r in self._configured_relations}

        storage_type = "Redis" if self._redis_available else "in-memory"
        logger.info(
            f"SchemaInsightsLogger initialized: storage={storage_type}, "
            f"configured_entities={len(self._configured_entities)}, "
            f"configured_relations={len(self._configured_relations)}"
        )

    def _init_redis(self, redis_url: str | None) -> None:
        """Initialize Redis connection."""
        if redis_url is None:
            from langchain_docker.core.config import get_redis_url
            redis_url = get_redis_url()

        if not redis_url:
            logger.info("SchemaInsightsLogger: No Redis URL configured, using in-memory storage")
            return

        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self._redis.ping()
            self._redis_available = True
            logger.info(f"SchemaInsightsLogger: Connected to Redis at {redis_url}")
        except Exception as e:
            logger.warning(f"SchemaInsightsLogger: Redis connection failed ({e}), using in-memory storage")
            self._redis = None
            self._redis_available = False

    def log_extraction(
        self,
        document_id: str,
        entities: list[tuple[str, str]],  # [(name, type), ...]
        relationships: list[tuple[str, str, str]],  # [(subject, predicate, object), ...]
        filename: str | None = None,
    ) -> ExtractionInsight:
        """Log extraction insights for a document.

        Args:
            document_id: Source document ID
            entities: List of (entity_name, entity_type) tuples
            relationships: List of (subject, predicate, object) tuples
            filename: Optional source filename

        Returns:
            ExtractionInsight record
        """
        # Count entity types
        entity_type_counts: dict[str, int] = defaultdict(int)
        for _, entity_type in entities:
            entity_type_counts[entity_type] += 1

        # Count relationship types
        relation_type_counts: dict[str, int] = defaultdict(int)
        for _, predicate, _ in relationships:
            relation_type_counts[predicate] += 1

        # Categorize entity types (in-schema vs discovered)
        entity_types_in_schema = []
        entity_types_discovered = []
        for entity_type in entity_type_counts.keys():
            if entity_type.lower() in self._configured_entities_lower:
                entity_types_in_schema.append(entity_type)
            else:
                entity_types_discovered.append(entity_type)

        # Categorize relation types
        relation_types_in_schema = []
        relation_types_discovered = []
        for relation_type in relation_type_counts.keys():
            # Normalize: relation types often get uppercased or have underscores
            normalized = relation_type.lower().replace(" ", "_")
            if normalized in self._configured_relations_lower:
                relation_types_in_schema.append(relation_type)
            else:
                relation_types_discovered.append(relation_type)

        # Collect samples
        sample_entities = [
            {"name": name, "type": etype}
            for name, etype in entities[:self._max_samples]
        ]
        sample_relationships = [
            {"subject": subj, "predicate": pred, "object": obj}
            for subj, pred, obj in relationships[:self._max_samples]
        ]

        # Create insight record
        insight = ExtractionInsight(
            timestamp=datetime.utcnow().isoformat(),
            document_id=document_id,
            filename=filename,
            entity_types_in_schema=entity_types_in_schema,
            entity_types_discovered=entity_types_discovered,
            entity_type_counts=dict(entity_type_counts),
            relation_types_in_schema=relation_types_in_schema,
            relation_types_discovered=relation_types_discovered,
            relation_type_counts=dict(relation_type_counts),
            sample_entities=sample_entities,
            sample_relationships=sample_relationships,
        )

        # Persist insight
        self._write_insight(insight)

        # Log discovered types
        if entity_types_discovered:
            logger.info(
                f"Schema insight [{document_id}]: Discovered entity types not in schema: "
                f"{entity_types_discovered}"
            )
        if relation_types_discovered:
            logger.info(
                f"Schema insight [{document_id}]: Discovered relation types not in schema: "
                f"{relation_types_discovered}"
            )

        return insight

    def _write_insight(self, insight: ExtractionInsight) -> None:
        """Write insight to storage (Redis or in-memory)."""
        insight_dict = asdict(insight)

        if self._redis_available:
            self._write_to_redis(insight_dict)
        else:
            self._write_to_memory(insight_dict)

    def _write_to_redis(self, insight_dict: dict) -> None:
        """Write insight to Redis."""
        try:
            pipe = self._redis.pipeline()

            # Store the full insight record
            pipe.lpush(REDIS_INSIGHTS_LIST_KEY, json.dumps(insight_dict))
            # Trim to keep only recent insights
            pipe.ltrim(REDIS_INSIGHTS_LIST_KEY, 0, MAX_INSIGHTS_STORED - 1)

            # Update aggregated counts for discovered types
            for entity_type in insight_dict.get("entity_types_discovered", []):
                count = insight_dict.get("entity_type_counts", {}).get(entity_type, 1)
                pipe.hincrby(REDIS_ENTITY_COUNTS_KEY, entity_type, count)

            for relation_type in insight_dict.get("relation_types_discovered", []):
                count = insight_dict.get("relation_type_counts", {}).get(relation_type, 1)
                pipe.hincrby(REDIS_RELATION_COUNTS_KEY, relation_type, count)

            # Increment document count
            pipe.incr(REDIS_DOC_COUNT_KEY)

            pipe.execute()
            logger.debug(f"Schema insight written to Redis: {insight_dict['document_id']}")

        except Exception as e:
            logger.error(f"Failed to write schema insight to Redis: {e}")
            # Fall back to memory
            self._write_to_memory(insight_dict)

    def _write_to_memory(self, insight_dict: dict) -> None:
        """Write insight to in-memory storage."""
        with self._lock:
            self._memory_insights.append(insight_dict)
            # Keep only recent insights
            if len(self._memory_insights) > MAX_INSIGHTS_STORED:
                self._memory_insights = self._memory_insights[-MAX_INSIGHTS_STORED:]

            # Update counts
            for entity_type in insight_dict.get("entity_types_discovered", []):
                count = insight_dict.get("entity_type_counts", {}).get(entity_type, 1)
                self._memory_entity_counts[entity_type] += count

            for relation_type in insight_dict.get("relation_types_discovered", []):
                count = insight_dict.get("relation_type_counts", {}).get(relation_type, 1)
                self._memory_relation_counts[relation_type] += count

    def get_insights_summary(self) -> dict[str, Any]:
        """Get aggregated summary of all insights.

        Returns:
            Summary dict with discovered types and their frequencies
        """
        if self._redis_available:
            return self._get_summary_from_redis()
        else:
            return self._get_summary_from_memory()

    def _get_summary_from_redis(self) -> dict[str, Any]:
        """Get summary from Redis."""
        try:
            pipe = self._redis.pipeline()
            pipe.get(REDIS_DOC_COUNT_KEY)
            pipe.hgetall(REDIS_ENTITY_COUNTS_KEY)
            pipe.hgetall(REDIS_RELATION_COUNTS_KEY)
            results = pipe.execute()

            total_docs = int(results[0] or 0)
            entity_counts = {k: int(v) for k, v in (results[1] or {}).items()}
            relation_counts = {k: int(v) for k, v in (results[2] or {}).items()}

            return {
                "total_documents": total_docs,
                "discovered_entities": dict(sorted(
                    entity_counts.items(), key=lambda x: -x[1]
                )),
                "discovered_relations": dict(sorted(
                    relation_counts.items(), key=lambda x: -x[1]
                )),
            }

        except Exception as e:
            logger.error(f"Failed to get summary from Redis: {e}")
            return {"total_documents": 0, "discovered_entities": {}, "discovered_relations": {}}

    def _get_summary_from_memory(self) -> dict[str, Any]:
        """Get summary from in-memory storage."""
        with self._lock:
            return {
                "total_documents": len(self._memory_insights),
                "discovered_entities": dict(sorted(
                    self._memory_entity_counts.items(), key=lambda x: -x[1]
                )),
                "discovered_relations": dict(sorted(
                    self._memory_relation_counts.items(), key=lambda x: -x[1]
                )),
            }

    def get_recent_insights(self, limit: int = 50) -> list[dict]:
        """Get recent extraction insights.

        Args:
            limit: Maximum number of insights to return

        Returns:
            List of insight records (most recent first)
        """
        if self._redis_available:
            try:
                raw_insights = self._redis.lrange(REDIS_INSIGHTS_LIST_KEY, 0, limit - 1)
                return [json.loads(r) for r in raw_insights]
            except Exception as e:
                logger.error(f"Failed to get recent insights from Redis: {e}")
                return []
        else:
            with self._lock:
                return list(reversed(self._memory_insights[-limit:]))

    def generate_schema_suggestions(self, min_occurrences: int = 2) -> dict[str, Any]:
        """Generate schema update suggestions based on insights.

        Args:
            min_occurrences: Minimum occurrences to suggest adding to schema

        Returns:
            Suggested schema updates
        """
        summary = self.get_insights_summary()

        suggested_entities = [
            {"type": etype, "occurrences": count}
            for etype, count in summary["discovered_entities"].items()
            if count >= min_occurrences
        ]

        suggested_relations = [
            {"type": rtype, "occurrences": count}
            for rtype, count in summary["discovered_relations"].items()
            if count >= min_occurrences
        ]

        # Generate env update commands
        current_entities = list(self._configured_entities)
        current_relations = list(self._configured_relations)

        new_entities = [s["type"] for s in suggested_entities]
        new_relations = [s["type"] for s in suggested_relations]

        return {
            "analyzed_documents": summary["total_documents"],
            "suggested_entities": suggested_entities,
            "suggested_relations": suggested_relations,
            "env_update": {
                "GRAPH_RAG_ENTITIES": ",".join(current_entities + new_entities),
                "GRAPH_RAG_RELATIONS": ",".join(current_relations + new_relations),
            } if new_entities or new_relations else None,
        }

    def clear_insights(self) -> bool:
        """Clear all stored insights.

        Returns:
            True if successful
        """
        if self._redis_available:
            try:
                self._redis.delete(
                    REDIS_INSIGHTS_LIST_KEY,
                    REDIS_ENTITY_COUNTS_KEY,
                    REDIS_RELATION_COUNTS_KEY,
                    REDIS_DOC_COUNT_KEY,
                )
                logger.info("Schema insights cleared from Redis")
                return True
            except Exception as e:
                logger.error(f"Failed to clear insights from Redis: {e}")
                return False
        else:
            with self._lock:
                self._memory_insights.clear()
                self._memory_entity_counts.clear()
                self._memory_relation_counts.clear()
            logger.info("Schema insights cleared from memory")
            return True


# Singleton instance
_insights_logger: SchemaInsightsLogger | None = None


def get_schema_insights_logger() -> SchemaInsightsLogger:
    """Get singleton schema insights logger."""
    global _insights_logger
    if _insights_logger is None:
        _insights_logger = SchemaInsightsLogger()
    return _insights_logger
