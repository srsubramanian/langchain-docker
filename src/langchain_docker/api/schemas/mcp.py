"""Pydantic schemas for MCP server management."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str = Field(..., description="Tool name")
    description: str = Field("", description="Tool description")
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool input"
    )


class MCPServerInfo(BaseModel):
    """Information about an MCP server."""

    id: str = Field(..., description="Server identifier")
    name: str = Field(..., description="Human-readable server name")
    description: str = Field("", description="Server description")
    enabled: bool = Field(True, description="Whether server is enabled in config")
    status: Literal["running", "stopped", "error"] = Field(
        ...,
        description="Current server status"
    )
    is_custom: bool = Field(False, description="Whether this is a custom HTTP server")
    url: str | None = Field(None, description="Server URL for custom HTTP servers")
    tools: list[MCPToolInfo] | None = Field(
        None,
        description="Available tools (only when running)"
    )


class MCPServersResponse(BaseModel):
    """Response for listing MCP servers."""

    servers: list[MCPServerInfo] = Field(
        ...,
        description="List of configured MCP servers"
    )


class MCPServerStartRequest(BaseModel):
    """Request to start an MCP server."""

    pass  # No body needed, server_id comes from path


class MCPServerStartResponse(BaseModel):
    """Response after starting an MCP server."""

    id: str = Field(..., description="Server identifier")
    status: Literal["running", "stopped", "error"] = Field(
        ...,
        description="Server status after start attempt"
    )
    message: str = Field("", description="Status message")
    tools: list[MCPToolInfo] | None = Field(
        None,
        description="Discovered tools after start"
    )


class MCPServerStopResponse(BaseModel):
    """Response after stopping an MCP server."""

    id: str = Field(..., description="Server identifier")
    status: Literal["stopped"] = Field(
        "stopped",
        description="Server status after stop"
    )
    message: str = Field("", description="Status message")


class MCPToolsResponse(BaseModel):
    """Response for listing tools from an MCP server."""

    server_id: str = Field(..., description="Server identifier")
    tools: list[MCPToolInfo] = Field(
        ...,
        description="Available tools from the server"
    )


class MCPToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool"
    )


class MCPToolCallResponse(BaseModel):
    """Response from calling an MCP tool."""

    server_id: str = Field(..., description="Server identifier")
    tool_name: str = Field(..., description="Tool that was called")
    result: Any = Field(..., description="Tool execution result")
    success: bool = Field(True, description="Whether the call succeeded")
    error: str | None = Field(None, description="Error message if failed")


class MCPServerCreateRequest(BaseModel):
    """Request to add a custom HTTP MCP server."""

    url: str = Field(..., description="Server URL (e.g., http://localhost:3001)")
    name: str | None = Field(None, description="Display name (defaults to URL)")
    description: str = Field("", description="Optional description")
    timeout_seconds: int = Field(30, ge=5, le=300, description="Request timeout")


class MCPServerCreateResponse(BaseModel):
    """Response after creating a custom MCP server."""

    id: str = Field(..., description="Generated server identifier")
    name: str = Field(..., description="Server display name")
    url: str = Field(..., description="Server URL")
    message: str = Field("", description="Status message")


class MCPServerDeleteResponse(BaseModel):
    """Response after deleting a custom MCP server."""

    id: str = Field(..., description="Deleted server identifier")
    deleted: bool = Field(True, description="Whether deletion was successful")
