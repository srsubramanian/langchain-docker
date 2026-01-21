"""MCP Tool Service for tool discovery and LangChain integration."""

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from langchain_docker.api.services.mcp_server_manager import MCPServerManager

logger = logging.getLogger(__name__)


def json_schema_to_pydantic(
    schema: dict[str, Any],
    model_name: str = "ToolInput"
) -> type[BaseModel]:
    """Convert JSON Schema to a Pydantic model.

    Args:
        schema: JSON Schema dict with properties and required fields.
        model_name: Name for the generated model.

    Returns:
        Dynamically created Pydantic model class.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions = {}

    for name, prop in properties.items():
        # Determine Python type from JSON Schema type
        json_type = prop.get("type", "string")
        if json_type == "string":
            python_type = str
        elif json_type == "integer":
            python_type = int
        elif json_type == "number":
            python_type = float
        elif json_type == "boolean":
            python_type = bool
        elif json_type == "array":
            python_type = list
        elif json_type == "object":
            python_type = dict
        else:
            python_type = Any

        # Build Field with description
        description = prop.get("description", "")

        # Check if field has an explicit default value in the schema
        has_explicit_default = "default" in prop

        # Treat field as required if:
        # 1. It's in the required array, OR
        # 2. It has no explicit default value (many MCP servers don't mark required properly)
        is_required = name in required or not has_explicit_default

        if is_required:
            field_definitions[name] = (python_type, Field(description=description))
            logger.debug(f"Field '{name}' treated as required (in_required={name in required}, has_default={has_explicit_default})")
        else:
            # Optional field with schema default or None
            default_value = prop.get("default")
            field_definitions[name] = (
                python_type | None,
                Field(default=default_value, description=description)
            )
            logger.debug(f"Field '{name}' treated as optional with default={default_value}")

    return create_model(model_name, **field_definitions)


class MCPToolService:
    """Service for discovering and invoking MCP tools."""

    def __init__(self, server_manager: MCPServerManager):
        """Initialize the MCP tool service.

        Args:
            server_manager: The MCPServerManager instance.
        """
        self._server_manager = server_manager
        self._tool_cache: dict[str, list[dict]] = {}

    async def discover_tools(self, server_id: str) -> list[dict[str, Any]]:
        """Discover available tools from an MCP server.

        Args:
            server_id: The server identifier.

        Returns:
            List of tool definitions with name, description, inputSchema.
        """
        # Check cache first
        if server_id in self._tool_cache:
            return self._tool_cache[server_id]

        # Start server if needed
        status = self._server_manager.get_server_status(server_id)
        if status != "running":
            await self._server_manager.start_server(server_id)

        # Call tools/list RPC method
        try:
            result = await self._server_manager.send_request(
                server_id,
                "tools/list",
                {}
            )
            tools = result.get("tools", [])
            self._tool_cache[server_id] = tools
            logger.info(
                f"Discovered {len(tools)} tools from MCP server '{server_id}'"
            )
            # Log tool schemas for debugging
            for tool in tools:
                tool_name = tool.get("name", "unknown")
                input_schema = tool.get("inputSchema", {})
                required_fields = input_schema.get("required", [])
                properties = input_schema.get("properties", {})
                logger.info(
                    f"Tool '{tool_name}': required={required_fields}, properties={properties}"
                )
            return tools
        except Exception as e:
            logger.error(f"Failed to discover tools from '{server_id}': {e}")
            return []

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """Call a tool on an MCP server.

        Args:
            server_id: The server identifier.
            tool_name: The name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool execution result.
        """
        # Ensure server is running
        status = self._server_manager.get_server_status(server_id)
        if status != "running":
            await self._server_manager.start_server(server_id)

        # Filter out None values from arguments to avoid sending undefined
        # MCP servers may reject arguments with null/undefined values
        filtered_arguments = {
            k: v for k, v in arguments.items() if v is not None
        }

        logger.info(
            f"MCP call_tool '{tool_name}': raw_args={arguments}, filtered_args={filtered_arguments}"
        )

        # Call tools/call RPC method
        result = await self._server_manager.send_request(
            server_id,
            "tools/call",
            {
                "name": tool_name,
                "arguments": filtered_arguments
            }
        )

        # Extract content from result
        content = result.get("content", [])
        if not content:
            return result

        # Handle different content types
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                text_parts.append(f"[Image: {item.get('mimeType', 'unknown')}]")
            elif item.get("type") == "resource":
                text_parts.append(f"[Resource: {item.get('uri', 'unknown')}]")

        return "\n".join(text_parts) if text_parts else result

    async def get_langchain_tools(
        self,
        server_ids: list[str]
    ) -> list[StructuredTool]:
        """Get LangChain StructuredTools for the specified MCP servers.

        Args:
            server_ids: List of server identifiers to get tools from.

        Returns:
            List of LangChain StructuredTool instances.
        """
        tools = []

        for server_id in server_ids:
            try:
                mcp_tools = await self.discover_tools(server_id)

                for mcp_tool in mcp_tools:
                    tool = self._create_langchain_tool(server_id, mcp_tool)
                    if tool:
                        tools.append(tool)

            except Exception as e:
                logger.error(
                    f"Failed to get tools from server '{server_id}': {e}"
                )

        return tools

    def _create_langchain_tool(
        self,
        server_id: str,
        mcp_tool: dict[str, Any]
    ) -> StructuredTool | None:
        """Create a LangChain StructuredTool from an MCP tool definition.

        Args:
            server_id: The server identifier.
            mcp_tool: MCP tool definition dict.

        Returns:
            StructuredTool instance or None if creation fails.
        """
        try:
            name = mcp_tool.get("name", "unknown")
            description = mcp_tool.get("description", "No description")
            input_schema = mcp_tool.get("inputSchema", {})

            # Create unique tool name with server prefix
            tool_name = f"{server_id}_{name}"

            # Create Pydantic model for arguments
            args_schema = json_schema_to_pydantic(
                input_schema,
                model_name=f"{tool_name.title().replace('_', '')}Input"
            )

            # Log the generated schema for debugging - show which fields are required
            if hasattr(args_schema, 'model_fields'):
                field_info = {}
                for field_name, field in args_schema.model_fields.items():
                    is_required = field.is_required()
                    field_info[field_name] = "required" if is_required else "optional"
                logger.info(
                    f"Created LangChain tool '{tool_name}' with fields: {field_info}"
                )
            else:
                logger.info(f"Created LangChain tool '{tool_name}' (no model_fields)")

            # Create tool execution wrapper that captures server context
            tool_service = self

            # Get required fields from the schema for validation
            required_fields = [
                f for f, info in args_schema.model_fields.items()
                if info.is_required()
            ] if hasattr(args_schema, 'model_fields') else []

            async def async_tool_executor(**kwargs) -> str:
                """Async executor for MCP tool calls."""
                logger.info(f"MCP tool '{name}' invoked with kwargs: {kwargs}")

                # Check for missing required fields
                missing = [f for f in required_fields if f not in kwargs or kwargs[f] is None]
                if missing:
                    error_msg = f"Missing required arguments for tool '{name}': {missing}. Please provide: {', '.join(missing)}"
                    logger.error(error_msg)
                    return error_msg

                result = await tool_service.call_tool(server_id, name, kwargs)
                return str(result)

            def sync_tool_executor(**kwargs) -> str:
                """Sync executor that runs async call in thread pool."""
                import asyncio
                import concurrent.futures

                logger.info(f"MCP tool '{name}' (sync) invoked with kwargs: {kwargs}")

                # Check for missing required fields
                missing = [f for f in required_fields if f not in kwargs or kwargs[f] is None]
                if missing:
                    error_msg = f"Missing required arguments for tool '{name}': {missing}. Please provide: {', '.join(missing)}"
                    logger.error(error_msg)
                    return error_msg

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        tool_service.call_tool(server_id, name, kwargs)
                    )
                    return str(future.result())

            # Build enhanced description that includes required args hint
            enhanced_description = f"[{server_id}] {description}"
            if required_fields:
                enhanced_description += f" (Required args: {', '.join(required_fields)})"

            return StructuredTool.from_function(
                func=sync_tool_executor,
                coroutine=async_tool_executor,
                name=tool_name,
                description=enhanced_description,
                args_schema=args_schema,
            )

        except Exception as e:
            logger.error(
                f"Failed to create LangChain tool for '{mcp_tool.get('name')}': {e}"
            )
            return None

    def clear_cache(self, server_id: str | None = None) -> None:
        """Clear the tool cache.

        Args:
            server_id: Optional server to clear. If None, clears all.
        """
        if server_id:
            self._tool_cache.pop(server_id, None)
        else:
            self._tool_cache.clear()
