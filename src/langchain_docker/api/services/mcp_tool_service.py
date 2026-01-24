"""MCP Tool Service using langchain-mcp-adapters for tool discovery and execution."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import (
    MCPToolCallRequest,
    MCPToolCallResult,
    ToolCallInterceptor,
)
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
from mcp.types import CallToolResult, ImageContent, TextContent

from langchain_docker.api.services.mcp_server_manager import MCPServerManager

logger = logging.getLogger(__name__)


class ImageFilterInterceptor(ToolCallInterceptor):
    """Interceptor that filters out image content from MCP tool results.

    OpenAI's API does not support images in tool result messages.
    This interceptor converts ImageContent to a text description,
    preserving any text content and providing information about images.
    """

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
    ) -> MCPToolCallResult:
        """Filter image content from tool results.

        Args:
            request: The tool call request.
            handler: The next handler in the chain.

        Returns:
            Tool result with images converted to text descriptions.
        """
        result = await handler(request)

        # Only process CallToolResult (MCP format), not ToolMessage or Command
        if not isinstance(result, CallToolResult):
            return result

        # Filter content to remove images and replace with descriptions
        filtered_content = []
        image_count = 0

        for content in result.content:
            if isinstance(content, ImageContent):
                image_count += 1
                # Add a text description instead of the image
                filtered_content.append(
                    TextContent(
                        type="text",
                        text=f"[Image {image_count}: {content.mimeType or 'image'} "
                        f"({len(content.data) // 1024}KB base64 data)]"
                    )
                )
            else:
                filtered_content.append(content)

        # If we filtered any images, add a summary
        if image_count > 0:
            filtered_content.append(
                TextContent(
                    type="text",
                    text=f"\n(Note: {image_count} image(s) captured but omitted from "
                    "response as images are not supported in tool results for this model)"
                )
            )
            logger.info(
                f"Filtered {image_count} image(s) from tool '{request.name}' result"
            )

        # Return modified result with filtered content
        return CallToolResult(
            content=filtered_content,
            isError=result.isError,
            structuredContent=result.structuredContent if hasattr(result, 'structuredContent') else None,
        )


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
            logger.debug(f"MCP server '{server_id}' not found in server manager")
            return None

        config = self._server_manager._servers[server_id]
        logger.info(f"MCP server '{server_id}' raw config: command={config.command}, args={config.args}, env={config.env}")

        if config.transport == "http":
            # HTTP/SSE transport
            # Note: timeout is passed via session_kwargs if needed
            client_config = {
                "transport": "sse",
                "url": config.url,
            }
            logger.info(f"MCP server '{server_id}' using HTTP/SSE transport: {client_config}")
            return client_config
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
            logger.info(f"MCP server '{server_id}' using stdio transport: command='{config.command}', args={config.args}")
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
                client = MultiServerMCPClient(
                    {server_id: client_config},
                    # tool_interceptors=[ImageFilterInterceptor()],  # Disabled for testing
                )
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

    @asynccontextmanager
    async def get_tools_with_session(
        self,
        server_ids: list[str]
    ) -> AsyncIterator[list[BaseTool]]:
        """Get LangChain tools with persistent MCP sessions.

        This context manager keeps MCP sessions alive during agent execution,
        which is required for stateful servers like chrome-devtools that need
        to maintain browser state across multiple tool calls.

        Usage:
            async with mcp_tool_service.get_tools_with_session(["chrome-devtools"]) as tools:
                # Run agent with tools - sessions stay alive
                agent = create_react_agent(model, tools)
                async for event in agent.astream_events(...):
                    ...
            # Sessions are closed when exiting the context

        Args:
            server_ids: List of server identifiers to get tools from.

        Yields:
            List of LangChain BaseTool instances bound to persistent sessions.
        """
        all_tools: list[BaseTool] = []
        active_sessions: list[tuple[str, ClientSession, Any]] = []  # (server_id, session, context_manager)
        clients: list[MultiServerMCPClient] = []

        try:
            for server_id in server_ids:
                try:
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

                    logger.info(f"Creating persistent session for MCP server '{server_id}'")
                    logger.info(f"MCP client config for '{server_id}': {client_config}")

                    # Create client for this server
                    client = MultiServerMCPClient({server_id: client_config})
                    clients.append(client)
                    logger.info(f"MultiServerMCPClient created for '{server_id}', starting session...")

                    # Create persistent session - this keeps the subprocess alive
                    session_ctx = client.session(server_id)
                    session: ClientSession = await session_ctx.__aenter__()
                    active_sessions.append((server_id, session, session_ctx))

                    # Load tools from the persistent session
                    tools = await load_mcp_tools(session)
                    all_tools.extend(tools)

                    logger.info(
                        f"Loaded {len(tools)} tools from MCP server '{server_id}' "
                        f"with persistent session: {[t.name for t in tools]}"
                    )

                except Exception as e:
                    logger.error(f"Failed to create session for MCP server '{server_id}': {e}")

            logger.info(f"Total tools loaded with persistent sessions: {len(all_tools)}")
            yield all_tools

        finally:
            # Clean up all sessions when context exits
            for server_id, session, session_ctx in active_sessions:
                try:
                    logger.info(f"Closing persistent session for MCP server '{server_id}'")
                    await session_ctx.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Error closing session for '{server_id}': {e}")

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
