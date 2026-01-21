#!/usr/bin/env python3
"""Schema Discovery Tool for GraphRAG.

Analyzes documents to discover new entity types and relationships
that should be added to your schema.

Usage:
    # Analyze a document with LLM
    python scripts/schema_discovery.py --file /path/to/document.pdf
    python scripts/schema_discovery.py --text "Your text here"

    # Analyze extraction insights log (from actual extractions)
    python scripts/schema_discovery.py --insights
    python scripts/schema_discovery.py --insights --min-occurrences 3
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def get_current_schema() -> tuple[list[str], list[str]]:
    """Get current schema from environment."""
    from langchain_docker.core.config import get_graph_rag_entities, get_graph_rag_relations
    return get_graph_rag_entities(), get_graph_rag_relations()


def discover_schema(text: str, current_entities: list[str], current_relations: list[str]) -> dict:
    """Use LLM to discover new entities and relationships in text."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = f"""Analyze the following text from the PAYMENT PROCESSING industry.

CURRENT SCHEMA (already configured):
- Entity types: {', '.join(current_entities)}
- Relationship types: {', '.join(current_relations)}

TEXT TO ANALYZE:
{text[:8000]}  # Limit to avoid token limits

TASK: Identify entities and relationships in this text that are NOT in the current schema but SHOULD be added.

Focus on payment processing domain concepts like:
- Payment methods, networks, processors
- Compliance standards, regulations
- Transaction types, statuses, flows
- Fees, rates, pricing models
- Fraud types, risk categories
- Technical integrations, APIs

Return JSON format:
{{
    "new_entities": [
        {{"type": "EntityType", "examples": ["example1", "example2"], "reason": "why it's important"}}
    ],
    "new_relations": [
        {{"type": "relation_name", "example": "Entity1 -> relation -> Entity2", "reason": "why it's important"}}
    ],
    "found_entities": [
        {{"text": "extracted text", "suggested_type": "EntityType", "current_type": "existing type or null"}}
    ]
}}

Only suggest NEW types not already in the schema. Be specific to payment processing."""

    response = llm.invoke(prompt)

    try:
        # Extract JSON from response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": response.content, "error": "Could not parse JSON"}


def analyze_file(file_path: str) -> str:
    """Extract text from a file."""
    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
            return text
        except ImportError:
            print("PyMuPDF not installed. Install with: pip install pymupdf")
            sys.exit(1)
    else:
        return path.read_text()


def analyze_insights(min_occurrences: int = 2) -> dict:
    """Analyze extraction insights log for schema suggestions.

    Reads the schema_insights.jsonl file generated during document ingestion
    and provides suggestions based on actual extraction data.

    Args:
        min_occurrences: Minimum occurrences to suggest a type

    Returns:
        Analysis results dict
    """
    from langchain_docker.api.services.schema_insights import get_schema_insights_logger

    logger = get_schema_insights_logger()
    return logger.generate_schema_suggestions(min_occurrences=min_occurrences)


def display_insights_analysis(min_occurrences: int = 2, output: str | None = None):
    """Display analysis of extraction insights."""
    print("\n" + "="*60)
    print("📊 SCHEMA INSIGHTS ANALYSIS (from actual extractions)")
    print("="*60)

    results = analyze_insights(min_occurrences)

    print(f"\n📄 Documents analyzed: {results['analyzed_documents']}")

    if not results['analyzed_documents']:
        print("\n⚠️  No extraction insights found.")
        print("   Insights are logged when documents are uploaded with GraphRAG enabled.")
        print("   Upload some documents first, then run this analysis again.")
        return

    if results.get("suggested_entities"):
        print(f"\n🆕 DISCOVERED ENTITY TYPES (≥{min_occurrences} occurrences):")
        for entity in results["suggested_entities"]:
            print(f"   • {entity['type']}: {entity['occurrences']} occurrences")
    else:
        print(f"\n✅ No new entity types found (threshold: {min_occurrences}+ occurrences)")

    if results.get("suggested_relations"):
        print(f"\n🔗 DISCOVERED RELATION TYPES (≥{min_occurrences} occurrences):")
        for rel in results["suggested_relations"]:
            print(f"   • {rel['type']}: {rel['occurrences']} occurrences")
    else:
        print(f"\n✅ No new relation types found (threshold: {min_occurrences}+ occurrences)")

    if results.get("env_update"):
        print("\n" + "="*60)
        print("📝 SUGGESTED .env UPDATES:")
        print("="*60)
        print(f"\nGRAPH_RAG_ENTITIES={results['env_update']['GRAPH_RAG_ENTITIES']}")
        print(f"\nGRAPH_RAG_RELATIONS={results['env_update']['GRAPH_RAG_RELATIONS']}")

    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {output}")


def main():
    parser = argparse.ArgumentParser(description="Discover new schema elements for GraphRAG")
    parser.add_argument("--file", help="Path to document file (PDF, TXT, MD)")
    parser.add_argument("--text", help="Direct text to analyze")
    parser.add_argument("--insights", action="store_true",
                        help="Analyze extraction insights log instead of documents")
    parser.add_argument("--min-occurrences", type=int, default=2,
                        help="Minimum occurrences for insights analysis (default: 2)")
    parser.add_argument("--output", help="Output file for suggestions (JSON)")

    args = parser.parse_args()

    # Insights analysis mode
    if args.insights:
        display_insights_analysis(
            min_occurrences=args.min_occurrences,
            output=args.output
        )
        return

    if not args.file and not args.text:
        parser.print_help()
        print("\nError: Provide --file, --text, or --insights")
        sys.exit(1)

    # Get current schema
    current_entities, current_relations = get_current_schema()
    print(f"\n📋 Current Schema:")
    print(f"   Entities ({len(current_entities)}): {', '.join(current_entities[:10])}...")
    print(f"   Relations ({len(current_relations)}): {', '.join(current_relations[:10])}...")

    # Get text to analyze
    if args.file:
        print(f"\n📄 Analyzing file: {args.file}")
        text = analyze_file(args.file)
    else:
        text = args.text

    print(f"   Text length: {len(text)} characters")

    # Discover new schema elements
    print("\n🔍 Discovering new entities and relationships...")
    results = discover_schema(text, current_entities, current_relations)

    # Display results
    if "error" in results:
        print(f"\n❌ Error: {results['error']}")
        print(f"Raw response: {results.get('raw_response', 'N/A')[:500]}")
        return

    print("\n" + "="*60)
    print("📊 SCHEMA DISCOVERY RESULTS")
    print("="*60)

    if results.get("new_entities"):
        print("\n🆕 SUGGESTED NEW ENTITY TYPES:")
        for entity in results["new_entities"]:
            print(f"\n   • {entity['type']}")
            print(f"     Examples: {', '.join(entity.get('examples', []))}")
            print(f"     Reason: {entity.get('reason', 'N/A')}")
    else:
        print("\n✅ No new entity types suggested")

    if results.get("new_relations"):
        print("\n🔗 SUGGESTED NEW RELATIONSHIP TYPES:")
        for rel in results["new_relations"]:
            print(f"\n   • {rel['type']}")
            print(f"     Example: {rel.get('example', 'N/A')}")
            print(f"     Reason: {rel.get('reason', 'N/A')}")
    else:
        print("\n✅ No new relationship types suggested")

    if results.get("found_entities"):
        print("\n📍 ENTITIES FOUND IN TEXT:")
        for entity in results["found_entities"][:15]:  # Limit display
            current = entity.get('current_type') or '(new)'
            print(f"   • \"{entity['text']}\" → {entity['suggested_type']} {current}")

    # Generate update commands
    if results.get("new_entities") or results.get("new_relations"):
        print("\n" + "="*60)
        print("📝 TO UPDATE YOUR SCHEMA:")
        print("="*60)

        if results.get("new_entities"):
            new_entity_types = [e["type"] for e in results["new_entities"]]
            all_entities = current_entities + new_entity_types
            print(f"\nGRAPH_RAG_ENTITIES={','.join(all_entities)}")

        if results.get("new_relations"):
            new_relation_types = [r["type"] for r in results["new_relations"]]
            all_relations = current_relations + new_relation_types
            print(f"\nGRAPH_RAG_RELATIONS={','.join(all_relations)}")

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()
