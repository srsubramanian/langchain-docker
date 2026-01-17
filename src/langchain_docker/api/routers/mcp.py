"""MCP server management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import (
    get_mcp_server_manager,
    get_mcp_tool_service,
)
from langchain_docker.api.schemas.mcp import (
    MCPServerCreateRequest,
    MCPServerCreateResponse,
    MCPServerDeleteResponse,
    MCPServerInfo,
    MCPServersResponse,
    MCPServerStartResponse,
    MCPServerStopResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolInfo,
    MCPToolsResponse,
)
from langchain_docker.api.services.mcp_server_manager import MCPServerManager
from langchain_docker.api.services.mcp_tool_service import MCPToolService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP Servers"])


def _to_mcp_tool_info(tools: list[dict]) -> list[MCPToolInfo]:
    """Convert raw MCP tool dicts to MCPToolInfo schema objects."""
    return [
        MCPToolInfo(
            name=t.get("name", "unknown"),
            description=t.get("description", ""),
            input_schema=t.get("inputSchema", {}),
        )
        for t in tools
    ]


@router.get("/servers", response_model=MCPServersResponse)
async def list_servers(
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
) -> MCPServersResponse:
    """List all configured MCP servers with their status.

    Returns:
        List of MCP servers with id, name, description, enabled, status, is_custom, and url.
    """
    servers_data = server_manager.list_servers()
    servers = [
        MCPServerInfo(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            enabled=s["enabled"],
            status=s["status"],
            is_custom=s.get("is_custom", False),
            url=s.get("url"),
            tools=None,
        )
        for s in servers_data
    ]
    return MCPServersResponse(servers=servers)


@router.post("/servers", response_model=MCPServerCreateResponse)
async def create_server(
    request: MCPServerCreateRequest,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
) -> MCPServerCreateResponse:
    """Add a custom HTTP MCP server.

    Args:
        request: Server creation request with URL and optional name/description.

    Returns:
        Created server info with generated ID.

    Raises:
        HTTPException: If server already exists or URL is invalid.
    """
    from urllib.parse import urlparse

    # Parse URL to generate server ID
    parsed = urlparse(request.url)
    if not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL: missing hostname"
        )

    # Generate ID from URL (e.g., "localhost-3001")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    server_id = f"{parsed.hostname}-{port}".replace(".", "-")

    # Check for duplicates
    existing_servers = server_manager.list_servers()
    if any(s["id"] == server_id for s in existing_servers):
        raise HTTPException(
            status_code=400,
            detail=f"Server '{server_id}' already exists"
        )

    # Generate name if not provided
    name = request.name or f"Custom: {parsed.hostname}:{port}"

    try:
        server_manager.add_custom_server(
            server_id=server_id,
            name=name,
            url=request.url,
            description=request.description,
            timeout_seconds=request.timeout_seconds,
        )

        logger.info(f"Created custom MCP server: {server_id} ({request.url})")

        return MCPServerCreateResponse(
            id=server_id,
            name=name,
            url=request.url,
            message="Server added successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/servers/{server_id}", response_model=MCPServerDeleteResponse)
async def delete_server(
    server_id: str,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> MCPServerDeleteResponse:
    """Delete a custom MCP server.

    Args:
        server_id: The server identifier to delete.

    Returns:
        Deletion confirmation.

    Raises:
        HTTPException: If server not found or is a builtin server.
    """
    try:
        # Stop server if running
        status = server_manager.get_server_status(server_id)
        if status == "running":
            await server_manager.stop_server(server_id)
            tool_service.clear_cache(server_id)

        # Delete the server
        server_manager.delete_custom_server(server_id)

        logger.info(f"Deleted custom MCP server: {server_id}")

        return MCPServerDeleteResponse(
            id=server_id,
            deleted=True,
        )

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_id}' not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post(
    "/servers/{server_id}/start",
    response_model=MCPServerStartResponse
)
async def start_server(
    server_id: str,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> MCPServerStartResponse:
    """Start an MCP server and discover its tools.

    Args:
        server_id: The server identifier to start.

    Returns:
        Server status and discovered tools.

    Raises:
        HTTPException: If server_id is not found or server fails to start.
    """
    try:
        await server_manager.start_server(server_id)

        # Discover tools
        mcp_tools = await tool_service.discover_tools(server_id)
        tools = _to_mcp_tool_info(mcp_tools)

        return MCPServerStartResponse(
            id=server_id,
            status="running",
            message=f"Server started with {len(tools)} tools",
            tools=tools,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        return MCPServerStartResponse(
            id=server_id,
            status="error",
            message=str(e),
            tools=None,
        )


@router.post(
    "/servers/{server_id}/stop",
    response_model=MCPServerStopResponse
)
async def stop_server(
    server_id: str,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> MCPServerStopResponse:
    """Stop a running MCP server.

    Args:
        server_id: The server identifier to stop.

    Returns:
        Server status after stopping.
    """
    await server_manager.stop_server(server_id)
    tool_service.clear_cache(server_id)

    return MCPServerStopResponse(
        id=server_id,
        status="stopped",
        message="Server stopped successfully",
    )


@router.get(
    "/servers/{server_id}/tools",
    response_model=MCPToolsResponse
)
async def list_server_tools(
    server_id: str,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> MCPToolsResponse:
    """List tools available from an MCP server.

    Starts the server if not already running.

    Args:
        server_id: The server identifier.

    Returns:
        List of tools with name, description, and input schema.

    Raises:
        HTTPException: If server_id is not found.
    """
    # Check if server exists
    status = server_manager.get_server_status(server_id)
    if status == "error":
        raise HTTPException(
            status_code=404,
            detail=f"Unknown MCP server: {server_id}"
        )

    try:
        mcp_tools = await tool_service.discover_tools(server_id)
        tools = _to_mcp_tool_info(mcp_tools)

        return MCPToolsResponse(
            server_id=server_id,
            tools=tools,
        )

    except Exception as e:
        logger.error(f"Failed to list tools from '{server_id}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to discover tools: {e}"
        )


@router.post(
    "/servers/{server_id}/tools/call",
    response_model=MCPToolCallResponse
)
async def call_tool(
    server_id: str,
    request: MCPToolCallRequest,
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> MCPToolCallResponse:
    """Call a tool on an MCP server.

    Starts the server if not already running.

    Args:
        server_id: The server identifier.
        request: Tool call request with tool_name and arguments.

    Returns:
        Tool execution result.

    Raises:
        HTTPException: If server_id is not found or tool call fails.
    """
    # Check if server exists
    status = server_manager.get_server_status(server_id)
    if status == "error":
        raise HTTPException(
            status_code=404,
            detail=f"Unknown MCP server: {server_id}"
        )

    try:
        result = await tool_service.call_tool(
            server_id,
            request.tool_name,
            request.arguments,
        )

        return MCPToolCallResponse(
            server_id=server_id,
            tool_name=request.tool_name,
            result=result,
            success=True,
            error=None,
        )

    except Exception as e:
        logger.error(
            f"Tool call failed: {server_id}/{request.tool_name}: {e}"
        )
        return MCPToolCallResponse(
            server_id=server_id,
            tool_name=request.tool_name,
            result=None,
            success=False,
            error=str(e),
        )
