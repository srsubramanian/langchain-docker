"""MCP Server Manager for subprocess lifecycle management."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    id: str
    name: str
    description: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout_seconds: int = 30


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
        self._connections: dict[str, MCPConnection] = {}
        self._lock = asyncio.Lock()
        self._load_config()

    def _load_config(self) -> None:
        """Load server configurations from JSON file."""
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
                )
            logger.info(f"Loaded {len(self._servers)} MCP server configurations")
        except FileNotFoundError:
            logger.warning(f"MCP config file not found: {self._config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP config: {e}")

    def list_servers(self) -> list[dict[str, Any]]:
        """List all configured servers with their status.

        Returns:
            List of server info dicts with id, name, description, enabled, status.
        """
        result = []
        for server_id, config in self._servers.items():
            status = "running" if server_id in self._connections else "stopped"
            result.append({
                "id": server_id,
                "name": config.name,
                "description": config.description,
                "enabled": config.enabled,
                "status": status,
            })
        return result

    def get_server_status(self, server_id: str) -> str:
        """Get the status of a specific server.

        Args:
            server_id: The server identifier.

        Returns:
            Status string: "running", "stopped", or "error".
        """
        if server_id not in self._servers:
            return "error"
        if server_id in self._connections:
            conn = self._connections[server_id]
            if conn.process.returncode is None:
                return "running"
            return "error"
        return "stopped"

    async def start_server(self, server_id: str) -> MCPConnection:
        """Start an MCP server subprocess.

        Args:
            server_id: The server identifier to start.

        Returns:
            MCPConnection for the started server.

        Raises:
            ValueError: If server_id is not configured.
            RuntimeError: If server fails to start.
        """
        if server_id not in self._servers:
            raise ValueError(f"Unknown MCP server: {server_id}")

        async with self._lock:
            # Return existing connection if running
            if server_id in self._connections:
                conn = self._connections[server_id]
                if conn.process.returncode is None:
                    return conn
                # Clean up dead connection
                del self._connections[server_id]

            config = self._servers[server_id]

            # Prepare environment
            env = os.environ.copy()
            env.update(config.env)

            # Build command
            cmd = [config.command] + config.args

            logger.info(f"Starting MCP server '{server_id}': {' '.join(cmd)}")

            try:
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
        """Stop an MCP server subprocess.

        Args:
            server_id: The server identifier to stop.
        """
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
        """Stop all running MCP servers."""
        server_ids = list(self._connections.keys())
        for server_id in server_ids:
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
        if server_id not in self._connections:
            raise ValueError(f"MCP server '{server_id}' is not running")

        conn = self._connections[server_id]
        config = self._servers[server_id]

        if timeout is None:
            timeout = config.timeout_seconds

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
