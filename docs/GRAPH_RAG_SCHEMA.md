# GraphRAG Schema Evolution Guide

This guide explains how to configure and evolve the entity/relationship schema for GraphRAG in a domain-specific context.

## Overview

GraphRAG uses **SchemaLLMPathExtractor** from LlamaIndex to extract entities and relationships from documents. The schema defines:

- **Entities**: Types of things to extract (Person, Organization, Transaction, etc.)
- **Relations**: Types of relationships between entities (processes, owns, complies_with, etc.)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT TEXT                                       │
│  "Visa processes card-not-present transactions through 3DS auth."       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SchemaLLMPathExtractor                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Schema Guidance:                                                │   │
│  │  • possible_entities: PaymentNetwork, Transaction, Technology    │   │
│  │  • possible_relations: processes, authenticates, uses            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                     │                                   │
│                    LLM analyzes text with schema context                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      EXTRACTED TRIPLES                                   │
│   (Visa) ──[PROCESSES]──▶ (card-not-present transactions)               │
│   PaymentNetwork              Transaction                                │
│                                                                          │
│   (card-not-present transactions) ──[AUTHENTICATES_VIA]──▶ (3DS)        │
│   Transaction                                              Technology    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Configuration

Schema is configured via environment variables in `.env`:

```bash
# Entity types (comma-separated)
GRAPH_RAG_ENTITIES=Person,Organization,Merchant,PaymentNetwork,Transaction,...

# Relationship types (comma-separated)
GRAPH_RAG_RELATIONS=processes,owns,complies_with,integrates_with,...
```

### Entity Types and Neo4j Labels

Entity types configured in `.env` are automatically converted to **UPPER_SNAKE_CASE** and become Neo4j node labels. This conversion preserves acronyms:

| Input (`.env`) | Neo4j Label | Example Node |
|----------------|-------------|--------------|
| `PaymentNetwork` | `PAYMENT_NETWORK` | `(Visa:PAYMENT_NETWORK)` |
| `API` | `API` | `(Stripe:API)` |
| `BIN` | `BIN` | `(411111:BIN)` |
| `PaymentFacilitator` | `PAYMENT_FACILITATOR` | `(Square:PAYMENT_FACILITATOR)` |

**Why UPPERCASE?** LlamaIndex's SchemaLLMPathExtractor uses entity types as Neo4j labels. UPPERCASE naming:
- Clearly distinguishes entity types from properties
- Follows Neo4j labeling conventions
- Improves LLM extraction accuracy

You can write entity types in `.env` using any case (PascalCase, camelCase, snake_case) - they'll be normalized automatically.

### Schema Mode: `strict` vs Non-Strict

In `graph_rag_service.py`, the extractor is configured with `strict=False`:

```python
extractor = SchemaLLMPathExtractor(
    llm=Settings.llm,
    possible_entities=get_graph_rag_entities(),
    possible_relations=get_graph_rag_relations(),
    strict=False,  # Allow entities outside schema
)
```

| Mode | Behavior |
|------|----------|
| `strict=False` (default) | LLM can discover new entity/relation types not in schema |
| `strict=True` | Only extracts entities/relations matching the schema exactly |

**Recommendation**: Use `strict=False` initially to discover what entities exist in your documents, then refine your schema based on findings.

---

## Domain-Specific Schema: Payment Processing

### Entities (31 types)

| Category | Entity Types | Description |
|----------|--------------|-------------|
| **Participants** | Person, Organization, Merchant, Acquirer, Issuer, PaymentNetwork, PaymentFacilitator | Parties involved in payment processing |
| **Transactions** | Transaction, PaymentMethod, Settlement, Chargeback, PaymentFlow | Transaction types and flows |
| **Infrastructure** | Gateway, Processor, API, Technology, AuthenticationProtocol | Technical components |
| **Compliance** | Regulation, Standard, ComplianceRequirement, RiskCategory | Regulatory and compliance items |
| **Financial** | Fee, Currency, Country, MCC | Financial and geographic elements |
| **Codes** | DeclineCode, ReasonCode, BIN, CardScheme | Industry codes and identifiers |
| **Risk** | FraudType, RiskCategory | Risk and fraud categories |

### Relations (32 types)

| Category | Relationships | Example |
|----------|---------------|---------|
| **Processing** | processes, authorizes, captures, settles_with, routes_to | Gateway → processes → Transaction |
| **Business** | issues, acquires, partners_with, owns, operates_in, aggregates | Acquirer → acquires → Merchant |
| **Technical** | integrates_with, connects_to, supports, uses, requires, authenticates | Gateway → integrates_with → API |
| **Compliance** | complies_with, regulates, certifies, validates | Processor → complies_with → PCI-DSS |
| **Financial** | charges, refunds, disputes, mitigates | Transaction → charges → Fee |
| **Lifecycle** | initiates, terminates, fails_with, triggers, identifies, categorizes | Transaction → fails_with → DeclineCode |

---

## Schema Evolution Strategies

### Strategy 1: Automatic Insights Logging (Recommended)

When documents are uploaded with GraphRAG enabled, the system automatically logs schema insights. This captures entity and relationship types discovered during extraction.

**Storage:**
- **Redis (primary)**: Durable storage across container restarts when `REDIS_URL` is configured
- **In-memory (fallback)**: When Redis is not available

**Redis Keys:**
| Key | Type | Description |
|-----|------|-------------|
| `schema_insights:logs` | List | Recent extraction insight records (max 1000) |
| `schema_insights:entity_counts` | Hash | Aggregated counts of discovered entity types |
| `schema_insights:relation_counts` | Hash | Aggregated counts of discovered relation types |
| `schema_insights:doc_count` | String | Total documents analyzed |

**How it works:**
1. Document is uploaded → GraphRAG extracts entities/relationships
2. Extracted types are compared against configured schema (case-insensitive)
3. New types (not in schema) are logged with occurrence counts to Redis
4. Analyze insights via API or CLI to identify types to add to schema

**View insights via API:**
```bash
curl http://localhost:8000/api/v1/kb/graph/schema-insights | jq
```

**Response:**
```json
{
  "analyzed_documents": 15,
  "configured_entities": ["Person", "Organization", "Merchant", ...],
  "configured_relations": ["processes", "owns", "complies_with", ...],
  "suggested_entities": [
    {"type": "PaymentFacilitator", "occurrences": 8},
    {"type": "DeclineCode", "occurrences": 5}
  ],
  "suggested_relations": [
    {"type": "aggregates", "occurrences": 6}
  ],
  "env_update": {
    "GRAPH_RAG_ENTITIES": "Person,Organization,...,PaymentFacilitator,DeclineCode",
    "GRAPH_RAG_RELATIONS": "processes,owns,...,aggregates"
  }
}
```

**Analyze via CLI:**
```bash
# Analyze extraction insights (from actual document processing)
.venv/bin/python scripts/schema_discovery.py --insights

# Require at least 3 occurrences to suggest
.venv/bin/python scripts/schema_discovery.py --insights --min-occurrences 3
```

### Strategy 2: LLM-Based Document Analysis

Use the discovery tool to analyze documents with an LLM before ingestion:

```bash
# Analyze a PDF document
.venv/bin/python scripts/schema_discovery.py --file /path/to/payment-spec.pdf

# Analyze specific text
.venv/bin/python scripts/schema_discovery.py --text "PCI DSS Level 1 requires annual audits..."

# Save suggestions for team review
.venv/bin/python scripts/schema_discovery.py --file doc.pdf --output suggestions.json
```

**Sample Output:**
```
📊 SCHEMA DISCOVERY RESULTS
============================================================

🆕 SUGGESTED NEW ENTITY TYPES:

   • PaymentFacilitator
     Examples: Stripe, Square
     Reason: Payment facilitators aggregate merchants under master accounts

   • DeclineCode
     Examples: 05, 51, 14
     Reason: Important for identifying transaction failure reasons

🔗 SUGGESTED NEW RELATIONSHIP TYPES:

   • aggregates
     Example: PaymentFacilitator -> aggregates -> Merchant
     Reason: Describes how PayFacs manage multiple merchants

📝 TO UPDATE YOUR SCHEMA:
============================================================
GRAPH_RAG_ENTITIES=...,PaymentFacilitator,DeclineCode
GRAPH_RAG_RELATIONS=...,aggregates
```

### Strategy 3: Periodic Review Process

Establish a regular schema review cadence:

```
┌─────────────────────────────────────────────────────────────────┐
│                 MONTHLY SCHEMA REVIEW PROCESS                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Week 1: Discovery                                               │
│  ├── Run: curl .../kb/graph/schema-insights                     │
│  ├── Review suggested_entities and suggested_relations          │
│  └── Check logs/schema_insights.jsonl for patterns              │
│                                                                  │
│  Week 2: Analysis                                                │
│  ├── Categorize suggested entities by domain area               │
│  ├── Evaluate relationship completeness                         │
│  └── Identify gaps in coverage                                  │
│                                                                  │
│  Week 3: Implementation                                          │
│  ├── Add high-value entities/relations to .env                  │
│  ├── Use env_update from API response                           │
│  └── Restart services to apply changes                          │
│                                                                  │
│  Week 4: Validation                                              │
│  ├── Re-index sample documents with new schema                  │
│  ├── Verify extraction quality                                  │
│  └── Document changes in schema changelog                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Strategy 4: Query-Based Feedback Loop

Track user queries to identify missing schema elements:

```python
# Example: Track what users are asking about
user_queries = [
    "What is the relationship between BIN and issuing bank?",
    "How does 3DS authentication work with SCA?",
    "Which merchants have high chargeback rates?",
]

# Analysis:
# - "BIN" mentioned → Ensure BIN entity exists
# - "issuing bank" → Ensure Issuer entity and identifies relation
# - "3DS", "SCA" → Ensure AuthenticationProtocol, authenticates relation
# - "chargeback rates" → Ensure metrics/rates can be captured
```

### Strategy 5: Industry Standard Alignment

Align your schema with industry standards and specifications:

| Standard | Entities to Include | Relations to Include |
|----------|--------------------|--------------------|
| **ISO 8583** | MessageType, DataElement, Bitmap | contains, maps_to |
| **PCI DSS** | Scope, Requirement, Control | complies_with, implements |
| **EMV** | Chip, Terminal, Cryptogram | generates, validates |
| **3DS 2.0** | ACS, DS, Challenge | authenticates, redirects_to |
| **NACHA/ACH** | ODFIBank, RDFIBank, BatchFile | originates, receives |

---

## Best Practices

### 1. Start Broad, Then Refine

```bash
# Initial schema (broad)
GRAPH_RAG_ENTITIES=Person,Organization,Transaction,Technology,Regulation

# After analysis (refined for payments)
GRAPH_RAG_ENTITIES=Person,Organization,Merchant,Acquirer,Issuer,PaymentNetwork,...
```

### 2. Use Consistent Naming Conventions

**In `.env` file** (input):
| Convention | Example | Notes |
|------------|---------|-------|
| PascalCase for entities | `PaymentNetwork` | Automatically converted to `PAYMENT_NETWORK` |
| snake_case for relations | `settles_with` | Automatically converted to `SETTLES_WITH` |
| Singular nouns for entities | `Transaction` | Not `Transactions` |
| Active verbs for relations | `processes` | Not `processed_by` |

**Automatic Conversion:**
```
Input (.env)              →  Neo4j Label
─────────────────────────────────────────
PaymentNetwork            →  PAYMENT_NETWORK
API                       →  API (acronyms preserved)
BIN                       →  BIN
cardNetwork               →  CARD_NETWORK
already_snake_case        →  ALREADY_SNAKE_CASE
```

The conversion function handles:
- PascalCase → UPPER_SNAKE_CASE (`PaymentNetwork` → `PAYMENT_NETWORK`)
- Acronym preservation (`API` → `API`, not `A_P_I`)
- Mixed case (`APIKey` → `API_KEY`)

### 3. Balance Granularity

```
Too Broad:                    Too Granular:                 Just Right:
─────────────────────────────────────────────────────────────────────────
Entity                        VisaCreditCard                PaymentMethod
                              MastercardDebitCard           CardScheme
                              AmexChargeCard                CardType
```

### 4. Document Your Schema

Maintain a schema changelog:

```markdown
## Schema Changelog

### v2.1 (2024-01-20)
- Added: PaymentFacilitator entity (for Stripe, Square, etc.)
- Added: DeclineCode, ReasonCode entities
- Added: aggregates, fails_with relations
- Reason: Better coverage of payment failures and PayFac model

### v2.0 (2024-01-15)
- Initial payment processing schema
- 31 entity types, 32 relation types
```

---

## Applying Schema Changes

After updating the schema in `.env`:

```bash
# 1. Restart the API server
docker-compose restart api

# Or for local development:
pkill -f run_server.py
nohup .venv/bin/python /tmp/run_server.py > /tmp/api-server.log 2>&1 &

# 2. Verify new schema is loaded
curl -s http://localhost:8000/api/v1/kb/graph/stats | jq

# 3. (Optional) Re-index existing documents for new entities
# This will extract entities using the updated schema
curl -X POST http://localhost:8000/api/v1/kb/reindex
```

---

## Troubleshooting

### Entities Not Being Extracted

1. **Check schema is loaded**: Verify via `/api/v1/kb/graph/stats`
2. **Review LLM logs**: Enable debug logging to see extraction prompts
3. **Test with explicit text**: Use schema discovery tool on known text

### Too Many Unknown Entity Types

1. **Enable strict mode** temporarily to see what's being missed
2. **Add common types** that appear frequently
3. **Review extraction results** in Neo4j browser (http://localhost:7474)

### Relationship Quality Issues

1. **Add more specific relations** instead of generic "related_to"
2. **Use active voice** verbs (processes, not processed_by)
3. **Consider directionality** (A → owns → B vs B → owned_by → A)

### Entity Types Showing as Generic `entity` Label

If entities appear in Neo4j with generic labels like `["__Node__", "__Entity__", "entity"]` instead of typed labels like `PAYMENT_NETWORK`:

1. **Check APOC is installed**: The system uses `apoc.create.addLabels()` to set entity type labels
   ```cypher
   SHOW PROCEDURES YIELD name WHERE name CONTAINS 'apoc.create' RETURN name
   ```

2. **Verify extraction is running**: Check for extraction logs:
   ```bash
   tail -f /tmp/api-server.log | grep -i "extraction\|entities"
   ```

3. **Inspect node labels**:
   ```cypher
   MATCH (n:__Entity__)
   RETURN DISTINCT labels(n), count(n)
   ORDER BY count(n) DESC
   ```

4. **Check entity type is being extracted**: Look for typed labels on recent nodes:
   ```cypher
   MATCH (n:__Entity__)
   WHERE n.collection = 'your_collection'
   RETURN [l IN labels(n) WHERE NOT l IN ['__Node__', '__Entity__', 'entity']] as types, n.name
   LIMIT 10
   ```

**Expected result for properly typed entities:**
```
types                    | name
["PAYMENT_NETWORK"]      | "Visa"
["ISSUER"]               | "Chase Bank"
["PAYMENT_PROCESSOR"]    | "First Data"
```

### Schema Insights Not Persisting

If schema insights are lost on restart:

1. **Check Redis connection**: Ensure `REDIS_URL` is set in `.env`
2. **Verify Redis keys exist**:
   ```bash
   docker exec langchain-redis redis-cli KEYS "schema_insights:*"
   ```
3. **Check storage type in logs**: Look for "SchemaInsightsLogger initialized: storage=Redis" on startup

---

## References

- [LlamaIndex PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)
- [SchemaLLMPathExtractor](https://docs.llamaindex.ai/en/stable/api_reference/extractors/path/)
- [Neo4j Graph Data Modeling](https://neo4j.com/developer/data-modeling/)
