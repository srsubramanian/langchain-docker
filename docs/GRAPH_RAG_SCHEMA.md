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

When documents are uploaded with GraphRAG enabled, the system automatically logs schema insights to `logs/schema_insights.jsonl`. This captures entity and relationship types discovered during extraction.

**How it works:**
1. Document is uploaded → GraphRAG extracts entities/relationships
2. Extracted types are compared against configured schema
3. New types (not in schema) are logged with occurrence counts
4. Analyze logs to identify types to add to schema

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

| Convention | Example | Avoid |
|------------|---------|-------|
| PascalCase for entities | `PaymentNetwork` | `payment_network`, `PAYMENT_NETWORK` |
| snake_case for relations | `settles_with` | `SettlesWith`, `SETTLES_WITH` |
| Singular nouns for entities | `Transaction` | `Transactions` |
| Active verbs for relations | `processes` | `processed_by` |

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

---

## References

- [LlamaIndex PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)
- [SchemaLLMPathExtractor](https://docs.llamaindex.ai/en/stable/api_reference/extractors/path/)
- [Neo4j Graph Data Modeling](https://neo4j.com/developer/data-modeling/)
