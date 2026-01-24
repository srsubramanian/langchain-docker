"""MCP Server Manager for configuration management.

Note: With langchain-mcp-adapters, subprocess lifecycle is managed automatically.
This manager now focuses on server configuration and status tracking.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Path for custom server configurations
CUSTOM_SERVERS_PATH = Path.home() / ".langchain-docker" / "custom_mcp_servers.json"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    id: str
    name: str
    description: str
    # For stdio-based (subprocess) servers
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # For HTTP-based servers
    url: str | None = None
    enabled: bool = True
    timeout_seconds: int = 30
    is_custom: bool = False
    transport: Literal["stdio", "http"] = "stdio"


class MCPServerManager:
    """Manages MCP server configurations.

    With the migration to langchain-mcp-adapters, this manager now focuses on:
    - Loading server configurations from JSON files
    - Managing custom server configurations
    - Providing server status information

    Subprocess lifecycle is handled automatically by langchain-mcp-adapters.
    """

    def __init__(self, config_path: str | None = None):
        """Initialize the MCP server manager.

        Args:
            config_path: Path to mcp_servers.json config file.
                        Defaults to the file in the api directory.
        """
        if config_path is None:
            config_path = str(
                Path(__file__).parent.parent / "mcp_servers.json"
            )
        self._config_path = config_path
        self._servers: dict[str, MCPServerConfig] = {}
        self._active_servers: set[str] = set()  # Track which servers have been used
        self._load_config()

    def _load_config(self) -> None:
        """Load server configurations from JSON file."""
        # Load builtin servers
        try:
            with open(self._config_path) as f:
                data = json.load(f)

            for server_id, config in data.get("servers", {}).items():
                args = config.get("args", [])
                logger.info(f"Loading MCP server '{server_id}': command={config['command']}, args={args}")
                self._servers[server_id] = MCPServerConfig(
                    id=server_id,
                    name=config.get("name", server_id),
                    description=config.get("description", ""),
                    command=config["command"],
                    args=args,
                    env=config.get("env", {}),
                    enabled=config.get("enabled", True),
                    timeout_seconds=config.get("timeout_seconds", 30),
                    is_custom=False,
                    transport="stdio",
                )
            logger.info(f"Loaded {len(self._servers)} builtin MCP server configurations")
        except FileNotFoundError:
            logger.warning(f"MCP config file not found: {self._config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP config: {e}")

        # Load custom servers
        self._load_custom_config()

    def _load_custom_config(self) -> None:
        """Load custom servers from user config file."""
        if not CUSTOM_SERVERS_PATH.exists():
            return

        try:
            with open(CUSTOM_SERVERS_PATH) as f:
                data = json.load(f)

            for server_id, config in data.get("servers", {}).items():
                self._servers[server_id] = MCPServerConfig(
                    id=server_id,
                    name=config.get("name", server_id),
                    description=config.get("description", ""),
                    url=config.get("url"),
                    timeout_seconds=config.get("timeout_seconds", 30),
                    is_custom=True,
                    transport="http",
                )
            logger.info(f"Loaded {sum(1 for s in self._servers.values() if s.is_custom)} custom MCP servers")
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in custom MCP config: {e}")

    def _save_custom_config(self) -> None:
        """Save custom servers to user config file."""
        CUSTOM_SERVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        custom_servers = {
            server_id: {
                "name": config.name,
                "description": config.description,
                "url": config.url,
                "timeout_seconds": config.timeout_seconds,
            }
            for server_id, config in self._servers.items()
            if config.is_custom
        }
        with open(CUSTOM_SERVERS_PATH, "w") as f:
            json.dump({"servers": custom_servers}, f, indent=2)
        logger.info(f"Saved {len(custom_servers)} custom MCP servers")

    def list_servers(self) -> list[dict[str, Any]]:
        """List all configured servers with their status.

        Returns:
            List of server info dicts with id, name, description, enabled, status, is_custom, url.
        """
        result = []
        for server_id, config in self._servers.items():
            status = self.get_server_status(server_id)
            result.append({
                "id": server_id,
                "name": config.name,
                "description": config.description,
                "enabled": config.enabled,
                "status": status,
                "is_custom": config.is_custom,
                "url": config.url,
            })
        return result

    def get_server_config(self, server_id: str) -> MCPServerConfig | None:
        """Get the configuration for a server.

        Args:
            server_id: The server identifier.

        Returns:
            MCPServerConfig or None if not found.
        """
        return self._servers.get(server_id)

    def add_custom_server(
        self,
        server_id: str,
        name: str,
        url: str,
        description: str = "",
        timeout_seconds: int = 30,
    ) -> None:
        """Add a custom HTTP-based MCP server.

        Args:
            server_id: Unique server identifier.
            name: Human-readable server name.
            url: Server URL (e.g., http://localhost:3001).
            description: Optional server description.
            timeout_seconds: Request timeout in seconds.

        Raises:
            ValueError: If server_id already exists.
        """
        if server_id in self._servers:
            raise ValueError(f"Server '{server_id}' already exists")

        self._servers[server_id] = MCPServerConfig(
            id=server_id,
            name=name,
            description=description,
            url=url,
            timeout_seconds=timeout_seconds,
            is_custom=True,
            transport="http",
        )
        self._save_custom_config()
        logger.info(f"Added custom MCP server: {server_id} ({url})")

    def delete_custom_server(self, server_id: str) -> None:
        """Delete a custom MCP server.

        Args:
            server_id: Server identifier to delete.

        Raises:
            KeyError: If server_id is not found.
            ValueError: If server is not a custom server.
        """
        if server_id not in self._servers:
            raise KeyError(f"Server '{server_id}' not found")

        if not self._servers[server_id].is_custom:
            raise ValueError("Cannot delete builtin server")

        del self._servers[server_id]
        self._active_servers.discard(server_id)
        self._save_custom_config()
        logger.info(f"Deleted custom MCP server: {server_id}")

    def get_server_status(self, server_id: str) -> str:
        """Get the status of a specific server.

        With langchain-mcp-adapters, servers are managed automatically.
        This returns:
        - "available" if configured and enabled
        - "disabled" if configured but not enabled
        - "unknown" if not configured

        Args:
            server_id: The server identifier.

        Returns:
            Status string: "available", "disabled", or "unknown".
        """
        if server_id not in self._servers:
            return "unknown"

        config = self._servers[server_id]
        if not config.enabled:
            return "disabled"

        # With langchain-mcp-adapters, we can't easily track running status
        # since it manages lifecycle automatically per invocation
        return "available"

    def mark_server_active(self, server_id: str) -> None:
        """Mark a server as having been used (for tracking purposes).

        Args:
            server_id: The server identifier.
        """
        if server_id in self._servers:
            self._active_servers.add(server_id)

    def is_server_active(self, server_id: str) -> bool:
        """Check if a server has been used in this session.

        Args:
            server_id: The server identifier.

        Returns:
            True if server has been used.
        """
        return server_id in self._active_servers

    async def start_server(self, server_id: str) -> None:
        """Mark a server as started.

        With langchain-mcp-adapters, actual subprocess management is automatic.
        This method exists for API compatibility and tracking.

        Args:
            server_id: The server identifier to start.

        Raises:
            ValueError: If server_id is not configured.
        """
        if server_id not in self._servers:
            raise ValueError(f"Unknown MCP server: {server_id}")

        config = self._servers[server_id]
        if not config.enabled:
            raise ValueError(f"MCP server '{server_id}' is disabled")

        self._active_servers.add(server_id)
        logger.info(f"MCP server '{server_id}' marked as active")

    async def stop_server(self, server_id: str) -> None:
        """Mark a server as stopped.

        With langchain-mcp-adapters, actual subprocess management is automatic.
        This method exists for API compatibility and tracking.

        Args:
            server_id: The server identifier to stop.
        """
        self._active_servers.discard(server_id)
        logger.info(f"MCP server '{server_id}' marked as inactive")

    async def stop_all_servers(self) -> None:
        """Mark all servers as stopped."""
        self._active_servers.clear()
        logger.info("All MCP servers marked as inactive")
