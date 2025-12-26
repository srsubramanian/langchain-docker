"""Skill registry service implementing progressive disclosure pattern.

Based on LangChain's skills architecture for on-demand context loading.
Reference: https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_community.utilities import SQLDatabase

from langchain_docker.api.services.demo_database import ensure_demo_database
from langchain_docker.core.config import get_database_url, is_sql_read_only

logger = logging.getLogger(__name__)


class Skill(ABC):
    """Base class for skills with progressive disclosure levels.

    Progressive disclosure architecture:
    - Level 1 (Metadata): Skill id, name, description - always visible in agent prompt
    - Level 2 (Core): Main skill content - loaded on-demand via load_core()
    - Level 3 (Details): Specific resources - loaded as needed via load_details()
    """

    id: str
    name: str
    description: str
    category: str

    @abstractmethod
    def load_core(self) -> str:
        """Level 2: Load core content on-demand.

        Returns:
            Core skill content including context, guidelines, and capabilities
        """
        pass

    @abstractmethod
    def load_details(self, resource: str) -> str:
        """Level 3: Load specific detailed resources.

        Args:
            resource: Resource identifier (e.g., "samples", "examples")

        Returns:
            Detailed resource content
        """
        pass


class SQLSkill(Skill):
    """SQL skill with database schema progressive disclosure.

    Provides database querying capabilities with on-demand schema loading.
    This keeps the base agent context lightweight while allowing full
    database introspection when needed.
    """

    def __init__(self, db_url: Optional[str] = None, read_only: Optional[bool] = None):
        """Initialize SQL skill.

        Args:
            db_url: Database URL (defaults to DATABASE_URL env var)
            read_only: Whether to enforce read-only mode (defaults to SQL_READ_ONLY env var)
        """
        self.id = "write_sql"
        self.name = "SQL Query Expert"
        self.description = "Write and execute SQL queries against the database"
        self.category = "database"
        self.db_url = db_url or get_database_url()
        self.read_only = read_only if read_only is not None else is_sql_read_only()
        self._db: Optional[SQLDatabase] = None

    def _get_db(self) -> SQLDatabase:
        """Get or create SQLDatabase instance.

        Returns:
            SQLDatabase wrapper for the configured database
        """
        if self._db is None:
            # Ensure demo database exists for SQLite
            if self.db_url.startswith("sqlite:///"):
                ensure_demo_database(self.db_url)
            self._db = SQLDatabase.from_uri(self.db_url)
        return self._db

    def load_core(self) -> str:
        """Level 2: Load database schema and SQL guidelines.

        Returns:
            Complete skill context including tables, schema, and guidelines
        """
        db = self._get_db()
        tables = db.get_usable_table_names()
        schema = db.get_table_info()
        dialect = db.dialect

        read_only_note = ""
        if self.read_only:
            read_only_note = """
### Read-Only Mode
This database is in READ-ONLY mode. Only SELECT queries are allowed.
INSERT, UPDATE, DELETE, and other write operations will be rejected.
"""

        return f"""## SQL Skill Activated

### Database Information
- Dialect: {dialect}
- Available Tables: {', '.join(tables)}

### Database Schema
{schema}
{read_only_note}
### Guidelines
- Always use explicit column names (avoid SELECT *)
- Use appropriate JOINs for related tables
- Use LIMIT to prevent large result sets
- Format queries for readability
- Explain query results clearly to users

### Query Patterns
- Count records: SELECT COUNT(*) FROM table_name
- Filter data: SELECT ... WHERE condition
- Join tables: SELECT ... FROM t1 JOIN t2 ON t1.id = t2.foreign_id
- Aggregate: SELECT column, SUM(value) FROM ... GROUP BY column
- Sort: SELECT ... ORDER BY column DESC LIMIT n
"""

    def load_details(self, resource: str) -> str:
        """Level 3: Load sample rows or query examples.

        Args:
            resource: "samples" for sample rows, "examples" for query examples

        Returns:
            Detailed resource content
        """
        db = self._get_db()

        if resource == "samples":
            tables = db.get_usable_table_names()
            samples = []
            for table in tables[:5]:  # Limit to first 5 tables
                try:
                    result = db.run(f"SELECT * FROM {table} LIMIT 3")
                    samples.append(f"### {table}\n{result}")
                except Exception as e:
                    samples.append(f"### {table}\nError fetching samples: {e}")
            return "\n\n".join(samples)

        elif resource == "examples":
            return """### Example Queries

1. **List all customers from a city**
```sql
SELECT name, email FROM customers WHERE city = 'New York'
```

2. **Get top customers by order total**
```sql
SELECT c.name, SUM(o.total) as total_spent
FROM customers c
JOIN orders o ON c.id = o.customer_id
GROUP BY c.id
ORDER BY total_spent DESC
LIMIT 5
```

3. **Find products in a category**
```sql
SELECT name, price FROM products
WHERE category = 'Electronics'
ORDER BY price DESC
```

4. **Recent orders with customer info**
```sql
SELECT c.name, p.name as product, o.quantity, o.total, o.order_date
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN products p ON o.product_id = p.id
ORDER BY o.order_date DESC
LIMIT 10
```
"""

        else:
            return f"Unknown resource: {resource}. Available: 'samples', 'examples'"

    def execute_query(self, query: str) -> str:
        """Execute a SQL query with read-only enforcement.

        Args:
            query: SQL query string

        Returns:
            Query results or error message
        """
        db = self._get_db()

        # Enforce read-only mode
        if self.read_only:
            query_upper = query.strip().upper()
            write_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
            for keyword in write_keywords:
                if query_upper.startswith(keyword):
                    return f"Error: {keyword} operations are not allowed in read-only mode. Only SELECT queries are permitted."

        try:
            result = db.run(query)
            return result
        except Exception as e:
            return f"Query error: {str(e)}"

    def list_tables(self) -> str:
        """List all available tables.

        Returns:
            Comma-separated list of table names
        """
        db = self._get_db()
        tables = db.get_usable_table_names()
        return ", ".join(tables)

    def get_table_schema(self, table_name: str) -> str:
        """Get schema for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Table schema information
        """
        db = self._get_db()
        try:
            return db.get_table_info([table_name])
        except Exception as e:
            return f"Error getting schema for {table_name}: {str(e)}"


class SkillRegistry:
    """Registry of available skills for progressive disclosure.

    Manages skill metadata (Level 1) and provides access to
    on-demand skill loading (Levels 2 and 3).
    """

    def __init__(self):
        """Initialize skill registry with built-in skills."""
        self._skills: dict[str, Skill] = {}
        self._register_builtin_skills()

    def _register_builtin_skills(self) -> None:
        """Register all built-in skills."""
        # SQL skill
        sql_skill = SQLSkill()
        self.register(sql_skill)

    def register(self, skill: Skill) -> None:
        """Register a skill.

        Args:
            skill: Skill instance to register
        """
        self._skills[skill.id] = skill
        logger.info(f"Registered skill: {skill.id} ({skill.name})")

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill if found, None otherwise
        """
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills (Level 1 metadata).

        Returns:
            List of skill metadata dictionaries
        """
        return [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
            }
            for skill in self._skills.values()
        ]

    def get_skill_summary(self) -> str:
        """Get a summary of available skills for agent prompts.

        Returns:
            Formatted string listing available skills
        """
        lines = ["Available skills (use load_sql_skill to activate):"]
        for skill in self._skills.values():
            lines.append(f"- {skill.id}: {skill.description}")
        return "\n".join(lines)

    def load_skill(self, skill_id: str) -> str:
        """Load a skill's core content (Level 2).

        Args:
            skill_id: Skill identifier

        Returns:
            Skill core content or error message
        """
        skill = self.get_skill(skill_id)
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Unknown skill: {skill_id}. Available skills: {available}"

        return skill.load_core()

    def load_skill_details(self, skill_id: str, resource: str) -> str:
        """Load a skill's detailed resources (Level 3).

        Args:
            skill_id: Skill identifier
            resource: Resource identifier

        Returns:
            Detailed resource content or error message
        """
        skill = self.get_skill(skill_id)
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Unknown skill: {skill_id}. Available skills: {available}"

        return skill.load_details(resource)
