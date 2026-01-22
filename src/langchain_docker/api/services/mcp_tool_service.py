"""MCP Tool Service using langchain-mcp-adapters for tool discovery and execution."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from langchain_docker.api.services.mcp_server_manager import MCPServerManager

logger = logging.getLogger(__name__)


class MCPToolService:
    """Service for discovering and invoking MCP tools using langchain-mcp-adapters.

    This service uses the official langchain-mcp-adapters library which provides:
    - Built-in subprocess management for stdio servers
    - Built-in HTTP client for remote servers
    - Automatic LangChain tool conversion
    - Client caching for persistent connections
    """

    def __init__(self, server_manager: MCPServerManager):
        """Initialize the MCP tool service.

        Args:
            server_manager: The MCPServerManager instance for config access.
        """
        self._server_manager = server_manager
        self._tool_cache: dict[str, list[BaseTool]] = {}
        self._client_cache: dict[str, MultiServerMCPClient] = {}

    def _get_client_config(self, server_id: str) -> dict[str, Any] | None:
        """Convert MCPServerManager config to MultiServerMCPClient format.

        Args:
            server_id: The server identifier.

        Returns:
            Config dict for MultiServerMCPClient, or None if not found.
        """
        if server_id not in self._server_manager._servers:
            return None

        config = self._server_manager._servers[server_id]

        if config.transport == "http":
            # HTTP/SSE transport
            # Note: timeout is passed via session_kwargs if needed
            return {
                "transport": "sse",
                "url": config.url,
            }
        else:
            # stdio transport (subprocess)
            # See: langchain_mcp_adapters.sessions.StdioConnection
            client_config: dict[str, Any] = {
                "transport": "stdio",
                "command": config.command,
                "args": config.args,
            }
            if config.env:
                client_config["env"] = config.env
            return client_config

    async def get_langchain_tools(
        self,
        server_ids: list[str]
    ) -> list[BaseTool]:
        """Get LangChain tools for the specified MCP servers.

        Uses langchain-mcp-adapters' MultiServerMCPClient for:
        - Automatic subprocess/HTTP management
        - Built-in tool schema conversion
        - Persistent client connections (cached to keep servers running)

        Args:
            server_ids: List of server identifiers to get tools from.

        Returns:
            List of LangChain BaseTool instances.
        """
        all_tools: list[BaseTool] = []

        for server_id in server_ids:
            try:
                # Check cache first
                if server_id in self._tool_cache:
                    all_tools.extend(self._tool_cache[server_id])
                    logger.info(f"Using cached tools for MCP server '{server_id}'")
                    continue

                # Get server config
                client_config = self._get_client_config(server_id)
                if not client_config:
                    logger.warning(f"MCP server '{server_id}' not found in config")
                    continue

                # Check if server is enabled
                if server_id in self._server_manager._servers:
                    if not self._server_manager._servers[server_id].enabled:
                        logger.info(f"MCP server '{server_id}' is disabled, skipping")
                        continue

                logger.info(f"Loading tools from MCP server '{server_id}'")

                # Create client for this server and cache it to keep connection alive
                # This is important for servers like chrome-devtools that need persistent state
                client = MultiServerMCPClient({server_id: client_config})
                self._client_cache[server_id] = client

                # Get tools using the library's built-in method
                # This handles subprocess lifecycle, JSON-RPC, and tool conversion
                tools = await client.get_tools()

                # Cache the tools
                self._tool_cache[server_id] = tools
                all_tools.extend(tools)

                logger.info(
                    f"Loaded {len(tools)} tools from MCP server '{server_id}': "
                    f"{[t.name for t in tools]}"
                )

            except Exception as e:
                logger.error(f"Failed to load tools from MCP server '{server_id}': {e}")

        return all_tools

    async def discover_tools(self, server_id: str) -> list[dict[str, Any]]:
        """Discover available tools from an MCP server.

        This method is kept for backward compatibility with existing code.

        Args:
            server_id: The server identifier.

        Returns:
            List of tool definitions with name, description, inputSchema.
        """
        tools = await self.get_langchain_tools([server_id])

        # Convert to dict format for backward compatibility
        tool_dicts = []
        for tool in tools:
            tool_dict: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description,
            }
            # Extract input schema if available
            if hasattr(tool, "args_schema") and tool.args_schema:
                schema = tool.args_schema
                # Handle both Pydantic models and plain dicts
                if hasattr(schema, "model_json_schema"):
                    tool_dict["inputSchema"] = schema.model_json_schema()
                elif isinstance(schema, dict):
                    tool_dict["inputSchema"] = schema
                else:
                    # Try to convert to dict
                    tool_dict["inputSchema"] = dict(schema) if schema else {}
            tool_dicts.append(tool_dict)

        return tool_dicts

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """Call a tool on an MCP server.

        This method is kept for backward compatibility. The recommended approach
        is to use get_langchain_tools() and invoke tools directly through LangChain.

        Args:
            server_id: The server identifier.
            tool_name: The name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool execution result.
        """
        # Get tools for this server
        tools = await self.get_langchain_tools([server_id])

        # Find the tool by name
        tool = None
        for t in tools:
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found on server '{server_id}'")

        # Invoke the tool
        logger.info(f"Calling MCP tool '{tool_name}' with args: {arguments}")
        result = await tool.ainvoke(arguments)
        return result

    def get_cached_tool_count(self, server_id: str) -> int | None:
        """Get the number of cached tools for a server.

        Args:
            server_id: The server identifier.

        Returns:
            Number of cached tools, or None if not yet loaded.
        """
        cached_tools = self._tool_cache.get(server_id)
        return len(cached_tools) if cached_tools is not None else None

    def clear_cache(self, server_id: str | None = None) -> None:
        """Clear the tool cache.

        Args:
            server_id: Optional server to clear. If None, clears all.
        """
        if server_id:
            self._tool_cache.pop(server_id, None)
            self._client_cache.pop(server_id, None)
        else:
            self._tool_cache.clear()
            self._client_cache.clear()
