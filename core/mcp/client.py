"""MCP Client for connecting to external MCP servers."""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Optional, Union
from uuid import uuid4

from core.mcp.protocol import (
    ClientCapabilities,
    ClientInfo,
    InitializeResult,
    JSONRPCRequest,
    JSONRPCResponse,
    MCP_VERSION,
    MCPMethod,
    Prompt,
    Resource,
    ResourceContents,
)
from core.mcp.types import Tool, ToolCall, ToolResult, ToolContent

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for connecting to MCP servers.

    Supports multiple transport modes:
    - HTTP: REST API calls
    - WebSocket: Bidirectional streaming
    - Stdio: Subprocess communication (used by VS Code)
    """

    def __init__(
        self,
        name: str = "local-ai-agent",
        version: str = "0.1.0",
    ):
        """
        Initialize MCP client.

        Args:
            name: Client name
            version: Client version
        """
        self.name = name
        self.version = version
        self._request_id = 0
        self._initialized = False
        self._server_info: Optional[InitializeResult] = None

        # Transport state
        self._transport_type: Optional[str] = None
        self._http_base_url: Optional[str] = None
        self._ws_connection = None
        self._subprocess: Optional[subprocess.Popen] = None
        self._pending_requests: dict[Union[str, int], asyncio.Future] = {}

    def _next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    # ═══════════════════════════════════════════════════════════════════════════
    # HTTP Transport
    # ═══════════════════════════════════════════════════════════════════════════

    async def connect_http(self, base_url: str) -> InitializeResult:
        """
        Connect to an MCP server via HTTP.

        Args:
            base_url: Server base URL (e.g., "http://localhost:8080")

        Returns:
            Server initialization result
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required. Install with: pip install httpx")

        self._transport_type = "http"
        self._http_base_url = base_url.rstrip("/")

        # Initialize connection
        result = await self._http_request(
            MCPMethod.INITIALIZE,
            {
                "protocolVersion": MCP_VERSION,
                "capabilities": ClientCapabilities().model_dump(),
                "clientInfo": {"name": self.name, "version": self.version},
            },
        )

        self._server_info = InitializeResult(**result)
        self._initialized = True

        # Send initialized notification
        await self._http_notify(MCPMethod.INITIALIZED, {})

        logger.info(f"Connected to {self._server_info.serverInfo.name} via HTTP")
        return self._server_info

    async def _http_request(self, method: str, params: dict) -> dict:
        """Make HTTP JSON-RPC request."""
        import httpx

        request = JSONRPCRequest(
            id=self._next_id(),
            method=method,
            params=params,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._http_base_url}/rpc",
                json=request.model_dump(exclude_none=True),
                timeout=30.0,
            )
            response.raise_for_status()

            if response.status_code == 204:
                return {}

            data = response.json()
            if "error" in data and data["error"]:
                raise Exception(f"RPC Error: {data['error']}")
            return data.get("result", {})

    async def _http_notify(self, method: str, params: dict) -> None:
        """Send HTTP notification (no response expected)."""
        import httpx

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._http_base_url}/rpc",
                json=notification,
                timeout=10.0,
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # WebSocket Transport
    # ═══════════════════════════════════════════════════════════════════════════

    async def connect_websocket(self, url: str) -> InitializeResult:
        """
        Connect to an MCP server via WebSocket.

        Args:
            url: WebSocket URL (e.g., "ws://localhost:8765")

        Returns:
            Server initialization result
        """
        try:
            import websockets
        except ImportError:
            raise ImportError("websockets required. Install with: pip install websockets")

        self._transport_type = "websocket"
        self._ws_connection = await websockets.connect(url)

        # Start message handler
        asyncio.create_task(self._ws_message_handler())

        # Initialize connection
        result = await self._ws_request(
            MCPMethod.INITIALIZE,
            {
                "protocolVersion": MCP_VERSION,
                "capabilities": ClientCapabilities().model_dump(),
                "clientInfo": {"name": self.name, "version": self.version},
            },
        )

        self._server_info = InitializeResult(**result)
        self._initialized = True

        # Send initialized notification
        await self._ws_notify(MCPMethod.INITIALIZED, {})

        logger.info(f"Connected to {self._server_info.serverInfo.name} via WebSocket")
        return self._server_info

    async def _ws_request(self, method: str, params: dict) -> dict:
        """Make WebSocket JSON-RPC request."""
        request_id = self._next_id()
        request = JSONRPCRequest(
            id=request_id,
            method=method,
            params=params,
        )

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        await self._ws_connection.send(request.model_dump_json(exclude_none=True))

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        finally:
            self._pending_requests.pop(request_id, None)

    async def _ws_notify(self, method: str, params: dict) -> None:
        """Send WebSocket notification."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._ws_connection.send(json.dumps(notification))

    async def _ws_message_handler(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in self._ws_connection:
                data = json.loads(message)
                request_id = data.get("id")

                if request_id and request_id in self._pending_requests:
                    future = self._pending_requests[request_id]
                    if "error" in data and data["error"]:
                        future.set_exception(Exception(f"RPC Error: {data['error']}"))
                    else:
                        future.set_result(data.get("result", {}))
                else:
                    # Handle notification
                    logger.debug(f"Received notification: {data.get('method')}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(e)

    # ═══════════════════════════════════════════════════════════════════════════
    # Stdio Transport
    # ═══════════════════════════════════════════════════════════════════════════

    async def connect_stdio(self, command: list[str]) -> InitializeResult:
        """
        Connect to an MCP server via subprocess stdio.

        Args:
            command: Command to start the server (e.g., ["python", "-m", "mcp_server"])

        Returns:
            Server initialization result
        """
        self._transport_type = "stdio"
        self._subprocess = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Start message handler
        asyncio.create_task(self._stdio_message_handler())

        # Initialize connection
        result = await self._stdio_request(
            MCPMethod.INITIALIZE,
            {
                "protocolVersion": MCP_VERSION,
                "capabilities": ClientCapabilities().model_dump(),
                "clientInfo": {"name": self.name, "version": self.version},
            },
        )

        self._server_info = InitializeResult(**result)
        self._initialized = True

        # Send initialized notification
        await self._stdio_notify(MCPMethod.INITIALIZED, {})

        logger.info(f"Connected to {self._server_info.serverInfo.name} via stdio")
        return self._server_info

    async def _stdio_request(self, method: str, params: dict) -> dict:
        """Make stdio JSON-RPC request."""
        request_id = self._next_id()
        request = JSONRPCRequest(
            id=request_id,
            method=method,
            params=params,
        )

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        message = request.model_dump_json(exclude_none=True) + "\n"
        self._subprocess.stdin.write(message)
        self._subprocess.stdin.flush()

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        finally:
            self._pending_requests.pop(request_id, None)

    async def _stdio_notify(self, method: str, params: dict) -> None:
        """Send stdio notification."""
        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }) + "\n"
        self._subprocess.stdin.write(notification)
        self._subprocess.stdin.flush()

    async def _stdio_message_handler(self) -> None:
        """Handle incoming stdio messages."""
        loop = asyncio.get_event_loop()
        try:
            while self._subprocess and self._subprocess.poll() is None:
                line = await loop.run_in_executor(
                    None, self._subprocess.stdout.readline
                )
                if not line:
                    break

                data = json.loads(line.strip())
                request_id = data.get("id")

                if request_id and request_id in self._pending_requests:
                    future = self._pending_requests[request_id]
                    if "error" in data and data["error"]:
                        future.set_exception(Exception(f"RPC Error: {data['error']}"))
                    else:
                        future.set_result(data.get("result", {}))
                else:
                    logger.debug(f"Received notification: {data.get('method')}")
        except Exception as e:
            logger.error(f"Stdio error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # MCP API Methods
    # ═══════════════════════════════════════════════════════════════════════════

    async def _request(self, method: str, params: dict) -> dict:
        """Route request to appropriate transport."""
        if self._transport_type == "http":
            return await self._http_request(method, params)
        elif self._transport_type == "websocket":
            return await self._ws_request(method, params)
        elif self._transport_type == "stdio":
            return await self._stdio_request(method, params)
        else:
            raise RuntimeError("Not connected to any server")

    async def list_tools(self) -> list[Tool]:
        """Get list of available tools."""
        result = await self._request(MCPMethod.TOOLS_LIST, {})
        return [Tool(**t) for t in result.get("tools", [])]

    async def call_tool(self, name: str, arguments: Optional[dict] = None) -> ToolResult:
        """
        Call a tool on the server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        result = await self._request(
            MCPMethod.TOOLS_CALL,
            {"name": name, "arguments": arguments or {}},
        )
        return ToolResult(
            content=[ToolContent(**c) for c in result.get("content", [])],
            is_error=result.get("isError", False),
        )

    async def list_resources(self) -> list[Resource]:
        """Get list of available resources."""
        result = await self._request(MCPMethod.RESOURCES_LIST, {})
        return [Resource(**r) for r in result.get("resources", [])]

    async def read_resource(self, uri: str) -> ResourceContents:
        """Read resource contents."""
        result = await self._request(MCPMethod.RESOURCES_READ, {"uri": uri})
        contents = result.get("contents", [{}])[0]
        return ResourceContents(**contents)

    async def list_prompts(self) -> list[Prompt]:
        """Get list of available prompts."""
        result = await self._request(MCPMethod.PROMPTS_LIST, {})
        return [Prompt(**p) for p in result.get("prompts", [])]

    async def get_prompt(self, name: str, arguments: Optional[dict] = None) -> list:
        """Get prompt messages."""
        result = await self._request(
            MCPMethod.PROMPTS_GET,
            {"name": name, "arguments": arguments or {}},
        )
        return result.get("messages", [])

    # ═══════════════════════════════════════════════════════════════════════════
    # Connection Management
    # ═══════════════════════════════════════════════════════════════════════════

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if not self._initialized:
            return

        try:
            await self._request(MCPMethod.SHUTDOWN, {})
        except Exception as e:
            logger.warning(f"Shutdown error: {e}")

        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

        if self._subprocess:
            self._subprocess.terminate()
            self._subprocess.wait()
            self._subprocess = None

        self._initialized = False
        self._transport_type = None
        logger.info("Disconnected from MCP server")

    @property
    def server_info(self) -> Optional[InitializeResult]:
        """Get server information."""
        return self._server_info

    @property
    def is_connected(self) -> bool:
        """Check if connected to a server."""
        return self._initialized
