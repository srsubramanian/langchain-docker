"""MCP server management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import (
    get_mcp_server_manager,
    get_mcp_tool_service,
)
from langchain_docker.api.schemas.mcp import (
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


@router.get("/servers", response_model=MCPServersResponse)
async def list_servers(
    server_manager: MCPServerManager = Depends(get_mcp_server_manager),
) -> MCPServersResponse:
    """List all configured MCP servers with their status.

    Returns:
        List of MCP servers with id, name, description, enabled, and status.
    """
    servers_data = server_manager.list_servers()
    servers = [
        MCPServerInfo(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            enabled=s["enabled"],
            status=s["status"],
            tools=None,
        )
        for s in servers_data
    ]
    return MCPServersResponse(servers=servers)


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
        tools = [
            MCPToolInfo(
                name=t.get("name", "unknown"),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in mcp_tools
        ]

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
        tools = [
            MCPToolInfo(
                name=t.get("name", "unknown"),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in mcp_tools
        ]

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
