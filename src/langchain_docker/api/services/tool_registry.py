"""Tool registry service for exposing tools as discoverable templates."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolParameter:
    """Parameter definition for a configurable tool."""

    name: str
    type: str  # "string", "number", "boolean"
    description: str
    default: Any = None
    required: bool = False


@dataclass
class ToolTemplate:
    """Tool template with metadata and configuration options."""

    id: str
    name: str
    description: str
    category: str  # "math", "weather", "research", "finance"
    parameters: list[ToolParameter] = field(default_factory=list)
    factory: Callable[..., Callable] = None


class ToolRegistry:
    """Registry of available tool templates.

    Provides a discoverable catalog of tools that can be used to build
    custom agents. Each tool template includes metadata, documentation,
    and optionally configurable parameters.
    """

    def __init__(self):
        """Initialize tool registry and register built-in tools."""
        self._tools: dict[str, ToolTemplate] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register all built-in tools as templates."""
        # Math tools - simple, no parameters
        self.register(
            ToolTemplate(
                id="add",
                name="Add Numbers",
                description="Add two numbers together",
                category="math",
                parameters=[],
                factory=lambda: self._create_add_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="subtract",
                name="Subtract Numbers",
                description="Subtract the second number from the first",
                category="math",
                parameters=[],
                factory=lambda: self._create_subtract_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="multiply",
                name="Multiply Numbers",
                description="Multiply two numbers together",
                category="math",
                parameters=[],
                factory=lambda: self._create_multiply_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="divide",
                name="Divide Numbers",
                description="Divide the first number by the second",
                category="math",
                parameters=[],
                factory=lambda: self._create_divide_tool(),
            )
        )

        # Weather tool - with configurable default city
        self.register(
            ToolTemplate(
                id="get_weather",
                name="Get Weather",
                description="Get current weather for a location",
                category="weather",
                parameters=[
                    ToolParameter(
                        name="default_city",
                        type="string",
                        description="Default city when none specified",
                        default="San Francisco",
                        required=False,
                    )
                ],
                factory=self._create_weather_tool,
            )
        )

        # Research tool
        self.register(
            ToolTemplate(
                id="search_web",
                name="Web Search",
                description="Search the web for information",
                category="research",
                parameters=[],
                factory=lambda: self._create_search_tool(),
            )
        )

        # Finance tool
        self.register(
            ToolTemplate(
                id="get_stock_price",
                name="Stock Price",
                description="Get current stock price for a symbol",
                category="finance",
                parameters=[],
                factory=lambda: self._create_stock_tool(),
            )
        )

        # Database/SQL tools - progressive disclosure pattern
        self.register(
            ToolTemplate(
                id="load_sql_skill",
                name="Load SQL Skill",
                description="Load SQL skill with database schema (progressive disclosure)",
                category="database",
                parameters=[],
                factory=lambda: self._create_load_sql_skill_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_query",
                name="SQL Query",
                description="Execute a read-only SQL query against the database",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_query_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_list_tables",
                name="List Tables",
                description="List all available tables in the database",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_list_tables_tool(),
            )
        )

        self.register(
            ToolTemplate(
                id="sql_get_samples",
                name="Get Sample Rows",
                description="Get sample rows from database tables",
                category="database",
                parameters=[],
                factory=lambda: self._create_sql_get_samples_tool(),
            )
        )

    # Tool factory methods
    def _create_add_tool(self) -> Callable:
        """Create add tool."""

        def add(a: float, b: float) -> float:
            """Add two numbers together."""
            return a + b

        return add

    def _create_subtract_tool(self) -> Callable:
        """Create subtract tool."""

        def subtract(a: float, b: float) -> float:
            """Subtract b from a."""
            return a - b

        return subtract

    def _create_multiply_tool(self) -> Callable:
        """Create multiply tool."""

        def multiply(a: float, b: float) -> float:
            """Multiply two numbers together."""
            return a * b

        return multiply

    def _create_divide_tool(self) -> Callable:
        """Create divide tool."""

        def divide(a: float, b: float) -> float:
            """Divide a by b. Returns error if b is zero."""
            if b == 0:
                return float("inf")
            return a / b

        return divide

    def _create_weather_tool(self, default_city: str = "San Francisco") -> Callable:
        """Create weather tool with configurable default city."""
        weather_data = {
            "san francisco": "Sunny, 68°F (20°C), light breeze",
            "new york": "Cloudy, 55°F (13°C), chance of rain",
            "london": "Rainy, 50°F (10°C), overcast",
            "tokyo": "Clear, 72°F (22°C), humid",
            "paris": "Partly cloudy, 62°F (17°C), pleasant",
        }

        def get_current_weather(location: str = None) -> str:
            """Get the current weather for a location."""
            loc = location or default_city
            location_lower = loc.lower()
            for city, weather in weather_data.items():
                if city in location_lower:
                    return f"Weather in {loc}: {weather}"
            return f"Weather in {loc}: Sunny, 70°F (21°C), clear skies (default)"

        return get_current_weather

    def _create_search_tool(self) -> Callable:
        """Create web search tool."""

        def search_web(query: str) -> str:
            """Search the web for information (demo - returns mock data)."""
            return (
                f"Search results for '{query}': This is a demo search result. "
                "In production, integrate with a real search API like Tavily, SerpAPI, or DuckDuckGo."
            )

        return search_web

    def _create_stock_tool(self) -> Callable:
        """Create stock price tool."""
        mock_prices = {
            "AAPL": 178.50,
            "GOOGL": 141.25,
            "MSFT": 378.90,
            "AMZN": 178.25,
            "META": 505.75,
        }

        def get_stock_price(symbol: str) -> str:
            """Get the current stock price for a symbol (demo - returns mock data)."""
            symbol_upper = symbol.upper()
            if symbol_upper in mock_prices:
                return f"{symbol_upper}: ${mock_prices[symbol_upper]:.2f}"
            return f"{symbol_upper}: $100.00 (demo price)"

        return get_stock_price

    # SQL tool factory methods
    def _get_sql_skill(self):
        """Get or create SQLSkill instance (lazy loading)."""
        if not hasattr(self, "_sql_skill"):
            from langchain_docker.api.services.skill_registry import SQLSkill
            self._sql_skill = SQLSkill()
        return self._sql_skill

    def _create_load_sql_skill_tool(self) -> Callable:
        """Create load SQL skill tool for progressive disclosure."""
        sql_skill = self._get_sql_skill()

        def load_sql_skill() -> str:
            """Load the SQL skill with database schema and guidelines.

            Call this tool before writing SQL queries to get the database schema,
            available tables, and SQL guidelines. This enables you to write
            accurate queries against the database.

            Returns:
                Database schema, available tables, and SQL guidelines
            """
            return sql_skill.load_core()

        return load_sql_skill

    def _create_sql_query_tool(self) -> Callable:
        """Create SQL query execution tool."""
        sql_skill = self._get_sql_skill()

        def sql_query(query: str) -> str:
            """Execute a SQL query against the database.

            In read-only mode, only SELECT queries are allowed.
            Use load_sql_skill first to get the database schema.

            Args:
                query: The SQL query to execute (SELECT only in read-only mode)

            Returns:
                Query results or error message
            """
            return sql_skill.execute_query(query)

        return sql_query

    def _create_sql_list_tables_tool(self) -> Callable:
        """Create SQL list tables tool."""
        sql_skill = self._get_sql_skill()

        def sql_list_tables() -> str:
            """List all available tables in the database.

            Returns:
                Comma-separated list of table names
            """
            return sql_skill.list_tables()

        return sql_list_tables

    def _create_sql_get_samples_tool(self) -> Callable:
        """Create SQL get samples tool."""
        sql_skill = self._get_sql_skill()

        def sql_get_samples() -> str:
            """Get sample rows from database tables.

            Returns sample data from each table to help understand
            the data structure and content.

            Returns:
                Sample rows from each table
            """
            return sql_skill.load_details("samples")

        return sql_get_samples

    # Registry methods
    def register(self, template: ToolTemplate) -> None:
        """Register a tool template.

        Args:
            template: Tool template to register
        """
        self._tools[template.id] = template

    def list_tools(self) -> list[ToolTemplate]:
        """List all available tool templates.

        Returns:
            List of all tool templates
        """
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> Optional[ToolTemplate]:
        """Get a tool template by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            Tool template if found, None otherwise
        """
        return self._tools.get(tool_id)

    def list_by_category(self, category: str) -> list[ToolTemplate]:
        """List tools in a specific category.

        Args:
            category: Category name

        Returns:
            List of tools in the category
        """
        return [t for t in self._tools.values() if t.category == category]

    def get_categories(self) -> list[str]:
        """Get all unique tool categories.

        Returns:
            List of category names
        """
        return list(sorted(set(t.category for t in self._tools.values())))

    def create_tool_instance(
        self, tool_id: str, config: Optional[dict] = None
    ) -> Callable:
        """Create a tool instance with the given configuration.

        Args:
            tool_id: Tool template ID
            config: Optional configuration parameters

        Returns:
            Callable tool function

        Raises:
            ValueError: If tool not found
        """
        template = self.get_tool(tool_id)
        if not template:
            raise ValueError(f"Unknown tool: {tool_id}")

        if template.parameters and config:
            # Filter config to only include valid parameters
            valid_params = {p.name for p in template.parameters}
            filtered_config = {k: v for k, v in config.items() if k in valid_params}
            return template.factory(**filtered_config)

        return template.factory()

    def to_dict_list(self) -> list[dict]:
        """Convert all templates to dictionary format for API response.

        Returns:
            List of tool templates as dictionaries
        """
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "default": p.default,
                        "required": p.required,
                    }
                    for p in t.parameters
                ],
            }
            for t in self._tools.values()
        ]
