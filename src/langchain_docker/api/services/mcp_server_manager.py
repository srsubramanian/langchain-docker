"""MCP Server Manager for subprocess lifecycle management."""

import asyncio
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

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


@dataclass
class MCPConnection:
    """Active connection to an MCP server."""

    server_id: str
    process: asyncio.subprocess.Process
    request_id: int = 0
    pending_requests: dict[int, asyncio.Future] = field(default_factory=dict)
    reader_task: asyncio.Task | None = None


class MCPServerManager:
    """Manages MCP server subprocess lifecycle and JSON-RPC communication."""

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
        self._connections: dict[str, MCPConnection] = {}  # For stdio servers
        self._http_active: set[str] = set()  # For HTTP servers
        self._lock = asyncio.Lock()
        self._load_config()

    def _load_config(self) -> None:
        """Load server configurations from JSON file."""
        # Load builtin servers
        try:
            with open(self._config_path) as f:
                data = json.load(f)

            for server_id, config in data.get("servers", {}).items():
                self._servers[server_id] = MCPServerConfig(
                    id=server_id,
                    name=config.get("name", server_id),
                    description=config.get("description", ""),
                    command=config["command"],
                    args=config.get("args", []),
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
        self._save_custom_config()
        logger.info(f"Deleted custom MCP server: {server_id}")

    def get_server_status(self, server_id: str) -> str:
        """Get the status of a specific server.

        Args:
            server_id: The server identifier.

        Returns:
            Status string: "running", "stopped", or "error".
        """
        if server_id not in self._servers:
            return "error"

        config = self._servers[server_id]

        # HTTP servers use _http_active set
        if config.transport == "http":
            return "running" if server_id in self._http_active else "stopped"

        # Stdio servers use _connections dict
        if server_id in self._connections:
            conn = self._connections[server_id]
            if conn.process.returncode is None:
                return "running"
            return "error"
        return "stopped"

    async def _send_http_request(
        self,
        url: str,
        method: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        """Send a JSON-RPC request over HTTP.

        Args:
            url: Server base URL.
            method: The RPC method name.
            params: Optional parameters for the method.
            timeout: Request timeout in seconds.

        Returns:
            The result from the server response.

        Raises:
            RuntimeError: If request fails or server returns error.
        """
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=request,
                    timeout=timeout,
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    error = result["error"]
                    raise RuntimeError(
                        f"MCP error: {error.get('message', 'Unknown error')} "
                        f"(code: {error.get('code', 'N/A')})"
                    )

                return result.get("result", {})
            except httpx.HTTPError as e:
                raise RuntimeError(f"HTTP request failed: {e}")

    async def start_server(self, server_id: str) -> MCPConnection | None:
        """Start an MCP server subprocess or connect to HTTP server.

        Args:
            server_id: The server identifier to start.

        Returns:
            MCPConnection for stdio servers, None for HTTP servers.

        Raises:
            ValueError: If server_id is not configured.
            RuntimeError: If server fails to start.
        """
        if server_id not in self._servers:
            raise ValueError(f"Unknown MCP server: {server_id}")

        config = self._servers[server_id]

        # Handle HTTP-based servers
        if config.transport == "http":
            async with self._lock:
                if server_id in self._http_active:
                    logger.info(f"HTTP server '{server_id}' already connected")
                    return None

                logger.info(f"Connecting to HTTP MCP server '{server_id}' at {config.url}")

                try:
                    # Test connection with initialize handshake
                    await self._send_http_request(
                        config.url,
                        "initialize",
                        {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "langchain-docker",
                                "version": "0.1.0"
                            }
                        },
                        config.timeout_seconds,
                    )

                    # Mark as active
                    self._http_active.add(server_id)
                    logger.info(f"HTTP MCP server '{server_id}' connected successfully")
                    return None

                except Exception as e:
                    logger.error(f"Failed to connect to HTTP MCP server '{server_id}': {e}")
                    raise RuntimeError(f"Failed to connect to MCP server at {config.url}: {e}")

        # Handle stdio-based servers (existing logic)
        async with self._lock:
            # Return existing connection if running
            if server_id in self._connections:
                conn = self._connections[server_id]
                if conn.process.returncode is None:
                    return conn
                # Clean up dead connection
                del self._connections[server_id]

            # Prepare environment
            env = os.environ.copy()
            env.update(config.env)

            # Resolve command path (important for Windows where PATH lookup differs)
            command = config.command
            resolved_command = shutil.which(command)

            if resolved_command:
                command = resolved_command
                logger.debug(f"Resolved command '{config.command}' to '{command}'")
            else:
                logger.warning(f"Could not resolve command '{command}' in PATH")

            # Build command
            cmd = [command] + config.args

            logger.info(f"Starting MCP server '{server_id}': {' '.join(cmd)}")

            try:
                # On Windows, we need shell=True for commands like npx/node
                # that are actually .cmd/.bat wrapper scripts
                if sys.platform == "win32":
                    # Use shell on Windows to properly handle PATH and .cmd wrappers
                    shell_cmd = " ".join(cmd)
                    logger.debug(f"Using shell execution on Windows: {shell_cmd}")
                    process = await asyncio.create_subprocess_shell(
                        shell_cmd,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                else:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
            except Exception as e:
                logger.error(f"Failed to start MCP server '{server_id}': {e}")
                raise RuntimeError(f"Failed to start MCP server: {e}")

            conn = MCPConnection(
                server_id=server_id,
                process=process,
            )

            # Start background reader task
            conn.reader_task = asyncio.create_task(
                self._read_responses(conn)
            )

            self._connections[server_id] = conn

            # Send initialize request
            try:
                await self._initialize_server(conn, config.timeout_seconds)
            except Exception as e:
                logger.error(f"Failed to initialize MCP server '{server_id}': {e}")
                await self.stop_server(server_id)
                raise RuntimeError(f"Failed to initialize MCP server: {e}")

            logger.info(f"MCP server '{server_id}' started successfully")
            return conn

    async def _initialize_server(self, conn: MCPConnection, timeout: int) -> dict:
        """Send initialize request to MCP server.

        Args:
            conn: The server connection.
            timeout: Timeout in seconds.

        Returns:
            Initialize response from server.
        """
        response = await self.send_request(
            conn.server_id,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "langchain-docker",
                    "version": "0.1.0"
                }
            },
            timeout=timeout
        )

        # Send initialized notification
        await self._send_notification(conn, "notifications/initialized", {})

        return response

    async def stop_server(self, server_id: str) -> None:
        """Stop an MCP server subprocess or disconnect from HTTP server.

        Args:
            server_id: The server identifier to stop.
        """
        # Check if this is an HTTP server
        if server_id in self._servers and self._servers[server_id].transport == "http":
            async with self._lock:
                if server_id in self._http_active:
                    self._http_active.discard(server_id)
                    logger.info(f"HTTP MCP server '{server_id}' disconnected")
            return

        # Handle stdio-based servers
        async with self._lock:
            if server_id not in self._connections:
                return

            conn = self._connections[server_id]

            # Cancel reader task
            if conn.reader_task:
                conn.reader_task.cancel()
                try:
                    await conn.reader_task
                except asyncio.CancelledError:
                    pass

            # Cancel pending requests
            for future in conn.pending_requests.values():
                if not future.done():
                    future.cancel()

            # Terminate process
            if conn.process.returncode is None:
                conn.process.terminate()
                try:
                    await asyncio.wait_for(conn.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    conn.process.kill()
                    await conn.process.wait()

            del self._connections[server_id]
            logger.info(f"MCP server '{server_id}' stopped")

    async def stop_all_servers(self) -> None:
        """Stop all running MCP servers (stdio and HTTP)."""
        # Stop stdio servers
        server_ids = list(self._connections.keys())
        for server_id in server_ids:
            await self.stop_server(server_id)

        # Disconnect HTTP servers
        http_server_ids = list(self._http_active)
        for server_id in http_server_ids:
            await self.stop_server(server_id)

    async def send_request(
        self,
        server_id: str,
        method: str,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        """Send a JSON-RPC request to an MCP server.

        Args:
            server_id: The server identifier.
            method: The RPC method name.
            params: Optional parameters for the method.
            timeout: Optional timeout in seconds.

        Returns:
            The result from the server response.

        Raises:
            ValueError: If server is not running.
            TimeoutError: If request times out.
            RuntimeError: If server returns an error.
        """
        if server_id not in self._servers:
            raise ValueError(f"Unknown MCP server: {server_id}")

        config = self._servers[server_id]

        if timeout is None:
            timeout = config.timeout_seconds

        # Handle HTTP-based servers
        if config.transport == "http":
            if server_id not in self._http_active:
                raise ValueError(f"HTTP MCP server '{server_id}' is not connected")

            return await self._send_http_request(
                config.url,
                method,
                params,
                timeout,
            )

        # Handle stdio-based servers
        if server_id not in self._connections:
            raise ValueError(f"MCP server '{server_id}' is not running")

        conn = self._connections[server_id]

        # Generate request ID
        conn.request_id += 1
        request_id = conn.request_id

        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        conn.pending_requests[request_id] = future

        # Send request
        request_line = json.dumps(request) + "\n"
        logger.debug(f"Sending to '{server_id}': {request_line.strip()}")

        try:
            conn.process.stdin.write(request_line.encode())
            await conn.process.stdin.drain()
        except Exception as e:
            del conn.pending_requests[request_id]
            raise RuntimeError(f"Failed to send request: {e}")

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            del conn.pending_requests[request_id]
            raise TimeoutError(f"Request to '{server_id}' timed out")

        # Check for error
        if "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"MCP error: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'N/A')})"
            )

        return response.get("result", {})

    async def _send_notification(
        self,
        conn: MCPConnection,
        method: str,
        params: dict | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            conn: The server connection.
            method: The notification method name.
            params: Optional parameters.
        """
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        notification_line = json.dumps(notification) + "\n"
        logger.debug(f"Sending notification: {notification_line.strip()}")

        conn.process.stdin.write(notification_line.encode())
        await conn.process.stdin.drain()

    async def _read_responses(self, conn: MCPConnection) -> None:
        """Background task to read responses from MCP server.

        Args:
            conn: The server connection.
        """
        try:
            while True:
                line = await conn.process.stdout.readline()
                if not line:
                    break

                try:
                    response = json.loads(line.decode())
                    logger.debug(f"Received from '{conn.server_id}': {response}")

                    # Handle response with ID
                    if "id" in response:
                        request_id = response["id"]
                        if request_id in conn.pending_requests:
                            future = conn.pending_requests.pop(request_id)
                            if not future.done():
                                future.set_result(response)
                    # Handle notification (no ID)
                    else:
                        logger.debug(
                            f"Received notification from '{conn.server_id}': "
                            f"{response.get('method', 'unknown')}"
                        )

                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Invalid JSON from '{conn.server_id}': {e}"
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading from '{conn.server_id}': {e}")

        # Mark all pending requests as failed
        for future in conn.pending_requests.values():
            if not future.done():
                future.set_exception(
                    RuntimeError(f"MCP server '{conn.server_id}' disconnected")
                )
