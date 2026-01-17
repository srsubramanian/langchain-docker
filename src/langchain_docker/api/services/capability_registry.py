"""Unified Capability Registry for Agent Builder.

Replaces the dual skill_registry.py + tool_registry.py with a single
unified model. Capabilities can be simple tools or skill bundles that
load context and provide multiple tools.

Architecture:
- Capability: Base unit that users select in Agent Builder
- type="tool": Simple tool with factory function
- type="skill_bundle": Complex capability that loads context and provides tools
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from langchain_community.utilities import SQLDatabase

from langchain_docker.api.services.demo_database import ensure_demo_database
from langchain_docker.core.config import (
    get_database_url,
    get_jira_api_version,
    get_jira_bearer_token,
    get_jira_url,
    is_jira_configured,
    is_sql_read_only,
)
from langchain_docker.core.demo_data import MOCK_STOCK_PRICES, WEATHER_DATA

logger = logging.getLogger(__name__)

# Skills directory path (for markdown content files)
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


@dataclass
class ToolParameter:
    """Parameter definition for a configurable tool."""

    name: str
    type: str  # "string", "number", "boolean"
    description: str
    default: Any = None
    required: bool = False


@dataclass
class Capability:
    """Unified capability that can be a tool or skill bundle.

    For type="tool": Simple tool created via tool_factory
    For type="skill_bundle": Loads context via load_core and provides multiple tools
    """

    id: str
    name: str
    description: str
    category: str
    type: Literal["tool", "skill_bundle"]

    # For skill_bundles: tools that become available after loading
    tools_provided: list[str] = field(default_factory=list)

    # For skill_bundles: markdown content path
    content_path: Optional[Path] = None

    # Factory to create tool instances (for type="tool")
    tool_factory: Optional[Callable[..., Callable]] = None

    # Tool parameters (for configurable tools)
    parameters: list[ToolParameter] = field(default_factory=list)

    # For skill_bundles: core content loader
    load_core: Optional[Callable[[], str]] = None

    # For skill_bundles: detail loader
    load_details: Optional[Callable[[str], str]] = None

    # Additional methods for skill_bundles (e.g., execute_query for SQL)
    methods: dict[str, Callable] = field(default_factory=dict)


class CapabilityRegistry:
    """Single registry for all agent capabilities.

    Provides a unified view of tools and skills for the Agent Builder.
    Users select capabilities from a single list - the system handles
    whether it needs skill loading or direct tool execution internally.
    """

    def __init__(self):
        """Initialize capability registry with built-in capabilities."""
        self._capabilities: dict[str, Capability] = {}
        self._sql_db: Optional[SQLDatabase] = None
        self._jira_session = None
        self._register_builtin_capabilities()

    def _register_builtin_capabilities(self) -> None:
        """Register all built-in capabilities."""
        # Math tools - bundled as single capability
        self._register_math_capability()

        # Weather capability
        self._register_weather_capability()

        # Research capability
        self._register_research_capability()

        # Finance capability
        self._register_finance_capability()

        # SQL Database skill bundle
        self._register_sql_capability()

        # Jira skill bundle
        self._register_jira_capability()

        # XLSX skill bundle
        self._register_xlsx_capability()

    # =========================================================================
    # Math Capability
    # =========================================================================

    def _register_math_capability(self) -> None:
        """Register math operations as a capability bundle."""

        def create_add():
            def add(a: float, b: float) -> float:
                """Add two numbers together."""
                return a + b
            return add

        def create_subtract():
            def subtract(a: float, b: float) -> float:
                """Subtract b from a."""
                return a - b
            return subtract

        def create_multiply():
            def multiply(a: float, b: float) -> float:
                """Multiply two numbers together."""
                return a * b
            return multiply

        def create_divide():
            def divide(a: float, b: float) -> float:
                """Divide a by b. Returns infinity if b is zero."""
                if b == 0:
                    return float("inf")
                return a / b
            return divide

        self.register(
            Capability(
                id="math_operations",
                name="Math Operations",
                description="Perform arithmetic calculations (add, subtract, multiply, divide)",
                category="math",
                type="tool",
                tools_provided=["add", "subtract", "multiply", "divide"],
                methods={
                    "add": create_add,
                    "subtract": create_subtract,
                    "multiply": create_multiply,
                    "divide": create_divide,
                },
            )
        )

    # =========================================================================
    # Weather Capability
    # =========================================================================

    def _register_weather_capability(self) -> None:
        """Register weather lookup capability."""

        def create_weather_tool(default_city: str = "San Francisco"):
            def get_current_weather(location: str | None = None) -> str:
                """Get the current weather for a location."""
                loc = location or default_city
                location_lower = loc.lower()
                for city, weather in WEATHER_DATA.items():
                    if city in location_lower:
                        return f"Weather in {loc}: {weather}"
                return f"Weather in {loc}: Sunny, 70°F (21°C), clear skies (default)"
            return get_current_weather

        self.register(
            Capability(
                id="weather_lookup",
                name="Weather Lookup",
                description="Get current weather for a location",
                category="weather",
                type="tool",
                tools_provided=["get_weather"],
                tool_factory=create_weather_tool,
                parameters=[
                    ToolParameter(
                        name="default_city",
                        type="string",
                        description="Default city when none specified",
                        default="San Francisco",
                        required=False,
                    )
                ],
            )
        )

    # =========================================================================
    # Research Capability
    # =========================================================================

    def _register_research_capability(self) -> None:
        """Register web search capability."""

        def create_search_tool():
            def search_web(query: str) -> str:
                """Search the web for information (demo - returns mock data)."""
                return (
                    f"Search results for '{query}': This is a demo search result. "
                    "In production, integrate with a real search API like Tavily, SerpAPI, or DuckDuckGo."
                )
            return search_web

        self.register(
            Capability(
                id="web_search",
                name="Web Search",
                description="Search the web for information",
                category="research",
                type="tool",
                tools_provided=["search_web"],
                tool_factory=create_search_tool,
            )
        )

    # =========================================================================
    # Finance Capability
    # =========================================================================

    def _register_finance_capability(self) -> None:
        """Register stock price capability."""

        def create_stock_tool():
            def get_stock_price(symbol: str) -> str:
                """Get the current stock price for a symbol (demo - returns mock data)."""
                symbol_upper = symbol.upper()
                if symbol_upper in MOCK_STOCK_PRICES:
                    return f"{symbol_upper}: ${MOCK_STOCK_PRICES[symbol_upper]:.2f}"
                return f"{symbol_upper}: $100.00 (demo price)"
            return get_stock_price

        self.register(
            Capability(
                id="stock_prices",
                name="Stock Prices",
                description="Get current stock prices for symbols",
                category="finance",
                type="tool",
                tools_provided=["get_stock_price"],
                tool_factory=create_stock_tool,
            )
        )

    # =========================================================================
    # SQL Database Capability (Skill Bundle)
    # =========================================================================

    def _get_sql_db(self) -> SQLDatabase:
        """Get or create SQLDatabase instance."""
        if self._sql_db is None:
            db_url = get_database_url()
            if db_url.startswith("sqlite:///"):
                ensure_demo_database(db_url)
            self._sql_db = SQLDatabase.from_uri(db_url)
        return self._sql_db

    def _register_sql_capability(self) -> None:
        """Register SQL database as a skill bundle capability."""
        skill_dir = SKILLS_DIR / "sql"

        def read_md_file(filename: str) -> str:
            """Read content from a markdown file."""
            file_path = skill_dir / filename
            try:
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    # Strip YAML frontmatter if present
                    if content.startswith("---"):
                        lines = content.split("\n")
                        for i, line in enumerate(lines[1:], 1):
                            if line.strip() == "---":
                                content = "\n".join(lines[i + 1:]).strip()
                                break
                    return content
                else:
                    return f"Error: File {filename} not found"
            except Exception as e:
                return f"Error reading {filename}: {str(e)}"

        def load_core() -> str:
            """Level 2: Load database schema and SQL guidelines."""
            db = self._get_sql_db()
            tables = db.get_usable_table_names()
            schema = db.get_table_info()
            dialect = db.dialect
            read_only = is_sql_read_only()

            read_only_note = ""
            if read_only:
                read_only_note = """
### Read-Only Mode
This database is in READ-ONLY mode. Only SELECT queries are allowed.
INSERT, UPDATE, DELETE, and other write operations will be rejected.
"""
            static_content = read_md_file("SKILL.md")

            return f"""## SQL Skill Activated

### Database Information
- Dialect: {dialect}
- Available Tables: {', '.join(tables)}

### Database Schema
{schema}
{read_only_note}
{static_content}
"""

        def load_details(resource: str) -> str:
            """Level 3: Load sample rows or query examples."""
            if resource == "samples":
                db = self._get_sql_db()
                tables = db.get_usable_table_names()
                samples = ["## Sample Data\n"]
                for table in tables[:5]:
                    try:
                        result = db.run(f"SELECT * FROM {table} LIMIT 3")
                        samples.append(f"### {table}\n```\n{result}\n```")
                    except Exception as e:
                        samples.append(f"### {table}\nError fetching samples: {e}")
                return "\n\n".join(samples)

            resource_map = {"examples": "examples.md", "patterns": "patterns.md"}
            if resource in resource_map:
                return read_md_file(resource_map[resource])
            else:
                available = "'samples', " + ", ".join(f"'{r}'" for r in resource_map.keys())
                return f"Unknown resource: {resource}. Available: {available}"

        def execute_query(query: str) -> str:
            """Execute a SQL query with read-only enforcement."""
            db = self._get_sql_db()
            read_only = is_sql_read_only()

            if read_only:
                query_upper = query.strip().upper()
                write_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
                for keyword in write_keywords:
                    if query_upper.startswith(keyword):
                        return f"Error: {keyword} operations are not allowed in read-only mode."

            try:
                return db.run(query)
            except Exception as e:
                return f"Query error: {str(e)}"

        def list_tables() -> str:
            """List all available tables."""
            db = self._get_sql_db()
            tables = db.get_usable_table_names()
            return ", ".join(tables)

        # Tool factories for SQL
        def create_load_sql_skill():
            def load_sql_skill() -> str:
                """Load the SQL skill with database schema and guidelines.

                Call this tool before writing SQL queries to get the database schema,
                available tables, and SQL guidelines.
                """
                return load_core()
            return load_sql_skill

        def create_sql_query():
            def sql_query(query: str) -> str:
                """Execute a SQL query against the database.

                In read-only mode, only SELECT queries are allowed.
                Use load_sql_skill first to get the database schema.

                Args:
                    query: The SQL query to execute
                """
                return execute_query(query)
            return sql_query

        def create_sql_list_tables():
            def sql_list_tables() -> str:
                """List all available tables in the database."""
                return list_tables()
            return sql_list_tables

        def create_sql_get_samples():
            def sql_get_samples() -> str:
                """Get sample rows from database tables."""
                return load_details("samples")
            return sql_get_samples

        self.register(
            Capability(
                id="write_sql",
                name="SQL Database",
                description="Query and analyze database with SQL (progressive disclosure)",
                category="database",
                type="skill_bundle",
                tools_provided=["load_sql_skill", "sql_query", "sql_list_tables", "sql_get_samples"],
                content_path=skill_dir,
                load_core=load_core,
                load_details=load_details,
                methods={
                    "load_sql_skill": create_load_sql_skill,
                    "sql_query": create_sql_query,
                    "sql_list_tables": create_sql_list_tables,
                    "sql_get_samples": create_sql_get_samples,
                    "execute_query": lambda: execute_query,
                    "list_tables": lambda: list_tables,
                },
            )
        )

    # =========================================================================
    # Jira Capability (Skill Bundle)
    # =========================================================================

    def _get_jira_session(self):
        """Get or create requests session with Bearer token authentication."""
        url = get_jira_url()
        bearer_token = get_jira_bearer_token()

        if not url or not bearer_token:
            return None

        if self._jira_session is None:
            import requests
            self._jira_session = requests.Session()
            self._jira_session.headers.update({
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })

        return self._jira_session

    def _jira_api_get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Jira API."""
        session = self._get_jira_session()
        if not session:
            return {"error": "Jira not configured. Set JIRA_URL and JIRA_BEARER_TOKEN."}

        url = f"{get_jira_url().rstrip('/')}{endpoint}"
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Jira API error: {str(e)}"}

    def _register_jira_capability(self) -> None:
        """Register Jira as a skill bundle capability."""
        skill_dir = SKILLS_DIR / "jira"

        def read_md_file(filename: str) -> str:
            """Read content from a markdown file."""
            file_path = skill_dir / filename
            try:
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        lines = content.split("\n")
                        for i, line in enumerate(lines[1:], 1):
                            if line.strip() == "---":
                                content = "\n".join(lines[i + 1:]).strip()
                                break
                    return content
                else:
                    return f"Error: File {filename} not found"
            except Exception as e:
                return f"Error reading {filename}: {str(e)}"

        def load_core() -> str:
            """Level 2: Load Jira skill instructions."""
            config_status = ""
            if not is_jira_configured():
                config_status = """
### Configuration Status
**Warning**: Jira is not fully configured. Set JIRA_URL and JIRA_BEARER_TOKEN.
"""
            else:
                config_status = f"""
### Configuration Status
- Connected to: {get_jira_url()}
- API Version: {get_jira_api_version()}
"""
            static_content = read_md_file("SKILL.md")
            return f"""## Jira Skill Activated
{config_status}
{static_content}
"""

        def load_details(resource: str) -> str:
            """Level 3: Load JQL reference."""
            resource_map = {"jql_reference": "jql_reference.md", "jql": "jql_reference.md"}
            if resource in resource_map:
                return read_md_file(resource_map[resource])
            return f"Unknown resource: {resource}"

        def search_issues(jql: str, max_results: int = 50) -> str:
            """Search for issues using JQL."""
            params = {
                "jql": jql,
                "fields": "key,summary,status,assignee,priority,issuetype",
                "maxResults": max_results,
            }
            result = self._jira_api_get(f"/rest/api/{get_jira_api_version()}/search", params)
            if "error" in result:
                return result["error"]

            issues = result.get("issues", [])
            total = result.get("total", 0)

            if not issues:
                return f"No issues found for query: {jql}"

            output = [f"Found {total} issues (showing {len(issues)}):"]
            for issue in issues:
                key = issue.get("key", "")
                fields_data = issue.get("fields", {})
                summary = fields_data.get("summary", "No summary")
                status = fields_data.get("status", {}).get("name", "Unknown")
                assignee = fields_data.get("assignee", {})
                assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
                priority = fields_data.get("priority", {})
                priority_name = priority.get("name", "None") if priority else "None"
                issue_type = fields_data.get("issuetype", {}).get("name", "Unknown")

                output.append(f"\n**{key}** [{issue_type}] - {summary}")
                output.append(f"  Status: {status} | Priority: {priority_name} | Assignee: {assignee_name}")

            return "\n".join(output)

        def get_issue(issue_key: str) -> str:
            """Get detailed information about a specific issue."""
            result = self._jira_api_get(f"/rest/api/{get_jira_api_version()}/issue/{issue_key}")
            if "error" in result:
                return result["error"]

            key = result.get("key", issue_key)
            fields_data = result.get("fields", {})
            summary = fields_data.get("summary", "No summary")
            description = fields_data.get("description", "No description")
            status = fields_data.get("status", {}).get("name", "Unknown")
            priority = fields_data.get("priority", {})
            priority_name = priority.get("name", "None") if priority else "None"
            issue_type = fields_data.get("issuetype", {}).get("name", "Unknown")
            assignee = fields_data.get("assignee", {})
            assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
            reporter = fields_data.get("reporter", {})
            reporter_name = reporter.get("displayName", "Unknown") if reporter else "Unknown"

            return f"""# {key}: {summary}

**Type:** {issue_type}
**Status:** {status}
**Priority:** {priority_name}
**Assignee:** {assignee_name}
**Reporter:** {reporter_name}

## Description
{description}
"""

        def list_projects() -> str:
            """List all accessible projects."""
            result = self._jira_api_get(f"/rest/api/{get_jira_api_version()}/project")
            if isinstance(result, dict) and "error" in result:
                return result["error"]

            if not result:
                return "No projects found or accessible."

            output = ["**Available Projects:**\n"]
            for project in result:
                key = project.get("key", "")
                name = project.get("name", "")
                output.append(f"- **{key}**: {name}")

            return "\n".join(output)

        def get_sprints(board_id: int, state: str = "active") -> str:
            """Get sprints for a board."""
            params = {"state": state}
            result = self._jira_api_get(f"/rest/agile/1.0/board/{board_id}/sprint", params)
            if "error" in result:
                return result["error"]

            sprints = result.get("values", [])
            if not sprints:
                return f"No {state} sprints found for board {board_id}."

            output = [f"**{state.title()} Sprints for Board {board_id}:**\n"]
            for sprint in sprints:
                sprint_id = sprint.get("id", "")
                name = sprint.get("name", "")
                state_name = sprint.get("state", "")
                start_date = sprint.get("startDate", "N/A")
                end_date = sprint.get("endDate", "N/A")
                output.append(f"- **{name}** (ID: {sprint_id})")
                output.append(f"  State: {state_name} | Start: {start_date} | End: {end_date}")

            return "\n".join(output)

        def get_changelog(issue_key: str) -> str:
            """Get the change history for an issue."""
            params = {"expand": "changelog"}
            result = self._jira_api_get(f"/rest/api/{get_jira_api_version()}/issue/{issue_key}", params)
            if "error" in result:
                return result["error"]

            changelog = result.get("changelog", {})
            histories = changelog.get("histories", [])

            if not histories:
                return f"No change history found for {issue_key}."

            output = [f"**Change History for {issue_key}:**\n"]
            for history in histories[:20]:
                author = history.get("author", {}).get("displayName", "Unknown")
                created = history.get("created", "Unknown")
                items = history.get("items", [])

                output.append(f"\n**{created}** by {author}:")
                for item in items:
                    field_name = item.get("field", "")
                    from_str = item.get("fromString", "None")
                    to_str = item.get("toString", "None")
                    output.append(f"  - {field_name}: '{from_str}' → '{to_str}'")

            return "\n".join(output)

        # Tool factories for Jira
        def create_load_jira_skill():
            def load_jira_skill() -> str:
                """Load Jira skill with context and guidelines."""
                return load_core()
            return load_jira_skill

        def create_jira_search(max_results: int = 50):
            def jira_search(jql: str) -> str:
                """Search for Jira issues using JQL."""
                return search_issues(jql, max_results)
            return jira_search

        def create_jira_get_issue():
            def jira_get_issue(issue_key: str) -> str:
                """Get detailed information about a Jira issue."""
                return get_issue(issue_key)
            return jira_get_issue

        def create_jira_list_projects():
            def jira_list_projects() -> str:
                """List all accessible Jira projects."""
                return list_projects()
            return jira_list_projects

        def create_jira_get_sprints():
            def jira_get_sprints(board_id: int, state: str = "active") -> str:
                """Get sprints for a Jira board."""
                return get_sprints(board_id, state)
            return jira_get_sprints

        def create_jira_get_changelog():
            def jira_get_changelog(issue_key: str) -> str:
                """Get the change history for a Jira issue."""
                return get_changelog(issue_key)
            return jira_get_changelog

        def create_jira_jql_reference():
            def jira_jql_reference() -> str:
                """Load JQL reference documentation."""
                return load_details("jql_reference")
            return jira_jql_reference

        self.register(
            Capability(
                id="jira",
                name="Jira Integration",
                description="Query Jira issues, sprints, projects (read-only)",
                category="project_management",
                type="skill_bundle",
                tools_provided=[
                    "load_jira_skill", "jira_search", "jira_get_issue",
                    "jira_list_projects", "jira_get_sprints", "jira_get_changelog",
                    "jira_jql_reference"
                ],
                content_path=skill_dir,
                load_core=load_core,
                load_details=load_details,
                parameters=[
                    ToolParameter(
                        name="max_results",
                        type="number",
                        description="Maximum search results",
                        default=50,
                        required=False,
                    )
                ],
                methods={
                    "load_jira_skill": create_load_jira_skill,
                    "jira_search": create_jira_search,
                    "jira_get_issue": create_jira_get_issue,
                    "jira_list_projects": create_jira_list_projects,
                    "jira_get_sprints": create_jira_get_sprints,
                    "jira_get_changelog": create_jira_get_changelog,
                    "jira_jql_reference": create_jira_jql_reference,
                },
            )
        )

    # =========================================================================
    # XLSX Capability (Skill Bundle)
    # =========================================================================

    def _register_xlsx_capability(self) -> None:
        """Register XLSX spreadsheet as a skill bundle capability."""
        skill_dir = SKILLS_DIR / "xlsx"

        def read_md_file(filename: str) -> str:
            """Read content from a markdown file."""
            file_path = skill_dir / filename
            try:
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        lines = content.split("\n")
                        for i, line in enumerate(lines[1:], 1):
                            if line.strip() == "---":
                                content = "\n".join(lines[i + 1:]).strip()
                                break
                    return content
                else:
                    return f"Error: File {filename} not found"
            except Exception as e:
                return f"Error reading {filename}: {str(e)}"

        def load_core() -> str:
            """Level 2: Load XLSX skill instructions."""
            content = read_md_file("SKILL.md")
            return f"## XLSX Skill Activated\n\n{content}"

        def load_details(resource: str) -> str:
            """Level 3: Load detailed resources."""
            resource_map = {
                "recalc": "recalc.md",
                "examples": "examples.md",
                "formatting": "formatting.md",
            }
            if resource in resource_map:
                return read_md_file(resource_map[resource])
            else:
                available = ", ".join(f"'{r}'" for r in resource_map.keys())
                return f"Unknown resource: {resource}. Available: {available}"

        # Tool factories for XLSX
        def create_load_xlsx_skill():
            def load_xlsx_skill() -> str:
                """Load XLSX skill with spreadsheet instructions and guidelines."""
                return load_core()
            return load_xlsx_skill

        def create_xlsx_get_examples():
            def xlsx_get_examples() -> str:
                """Get XLSX code examples."""
                return load_details("examples")
            return xlsx_get_examples

        def create_xlsx_get_formatting():
            def xlsx_get_formatting() -> str:
                """Get XLSX formatting guide."""
                return load_details("formatting")
            return xlsx_get_formatting

        self.register(
            Capability(
                id="xlsx",
                name="Spreadsheet Expert",
                description="Create and edit XLSX spreadsheets with formulas, formatting, and charts",
                category="data",
                type="skill_bundle",
                tools_provided=["load_xlsx_skill", "xlsx_get_examples", "xlsx_get_formatting"],
                content_path=skill_dir,
                load_core=load_core,
                load_details=load_details,
                methods={
                    "load_xlsx_skill": create_load_xlsx_skill,
                    "xlsx_get_examples": create_xlsx_get_examples,
                    "xlsx_get_formatting": create_xlsx_get_formatting,
                },
            )
        )

    # =========================================================================
    # Registry Methods
    # =========================================================================

    def register(self, capability: Capability) -> None:
        """Register a capability.

        Args:
            capability: Capability to register
        """
        self._capabilities[capability.id] = capability
        logger.info(f"Registered capability: {capability.id} ({capability.name})")

    def get(self, capability_id: str) -> Optional[Capability]:
        """Get a capability by ID.

        Args:
            capability_id: Capability identifier

        Returns:
            Capability if found, None otherwise
        """
        return self._capabilities.get(capability_id)

    def list_all(self) -> list[Capability]:
        """List all available capabilities.

        Returns:
            List of all capabilities
        """
        return list(self._capabilities.values())

    def list_by_category(self, category: str) -> list[Capability]:
        """List capabilities in a specific category.

        Args:
            category: Category name

        Returns:
            List of capabilities in the category
        """
        return [c for c in self._capabilities.values() if c.category == category]

    def get_categories(self) -> list[str]:
        """Get all unique capability categories.

        Returns:
            List of category names
        """
        return list(sorted(set(c.category for c in self._capabilities.values())))

    def get_tools_for_capability(
        self, capability_id: str, config: Optional[dict[str, Any]] = None
    ) -> list[Callable]:
        """Get all tool functions for a capability.

        Args:
            capability_id: Capability identifier
            config: Optional configuration parameters

        Returns:
            List of callable tool functions

        Raises:
            ValueError: If capability not found
        """
        capability = self.get(capability_id)
        if not capability:
            raise ValueError(f"Unknown capability: {capability_id}")

        tools = []

        if capability.type == "tool":
            # Simple tool capability
            if capability.tool_factory:
                if capability.parameters and config:
                    valid_params = {p.name for p in capability.parameters}
                    filtered_config = {k: v for k, v in config.items() if k in valid_params}
                    tools.append(capability.tool_factory(**filtered_config))
                else:
                    tools.append(capability.tool_factory())
            # Also check methods for multi-tool capabilities like math
            for tool_name, factory in capability.methods.items():
                tools.append(factory())

        elif capability.type == "skill_bundle":
            # Skill bundle - create all provided tools
            for tool_name in capability.tools_provided:
                if tool_name in capability.methods:
                    factory = capability.methods[tool_name]
                    # Handle parameterized factories
                    if capability.parameters and config:
                        valid_params = {p.name for p in capability.parameters}
                        filtered_config = {k: v for k, v in config.items() if k in valid_params}
                        tools.append(factory(**filtered_config))
                    else:
                        tools.append(factory())

        return tools

    def create_tool_instance(
        self, tool_id: str, config: Optional[dict[str, Any]] = None
    ) -> Callable:
        """Create a specific tool instance by tool ID.

        This method finds which capability provides the tool and creates it.

        Args:
            tool_id: Tool identifier
            config: Optional configuration parameters

        Returns:
            Callable tool function

        Raises:
            ValueError: If tool not found
        """
        # Search through capabilities for the tool
        for capability in self._capabilities.values():
            if tool_id in capability.tools_provided or tool_id in capability.methods:
                if tool_id in capability.methods:
                    factory = capability.methods[tool_id]
                    if capability.parameters and config:
                        valid_params = {p.name for p in capability.parameters}
                        filtered_config = {k: v for k, v in config.items() if k in valid_params}
                        return factory(**filtered_config)
                    return factory()

        raise ValueError(f"Unknown tool: {tool_id}")

    def to_dict_list(self) -> list[dict]:
        """Convert all capabilities to dictionary format for API response.

        Returns:
            List of capabilities as dictionaries
        """
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "category": c.category,
                "type": c.type,
                "tools_provided": c.tools_provided,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "default": p.default,
                        "required": p.required,
                    }
                    for p in c.parameters
                ],
            }
            for c in self._capabilities.values()
        ]
