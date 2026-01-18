"""MCP Server Registry for managing multiple domain servers."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from core.mcp.protocol import (
    InitializeResult,
    JSONRPCRequest,
    JSONRPCResponse,
    MCP_VERSION,
    ServerCapabilities,
    ServerInfo,
)
from core.mcp.server import MCPServer
from core.mcp.types import Tool, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class MCPServerRegistry:
    """
    Registry for managing multiple MCP servers.

    Provides a unified interface to route requests to the appropriate
    domain server based on tool/resource prefixes or explicit routing.
    """

    def __init__(
        self,
        name: str = "local-ai-agent",
        version: str = "0.1.0",
    ):
        """
        Initialize server registry.

        Args:
            name: Registry name
            version: Registry version
        """
        self.name = name
        self.version = version
        self._servers: Dict[str, MCPServer] = {}
        self._tool_routes: Dict[str, str] = {}  # tool_name -> server_name
        self._resource_routes: Dict[str, str] = {}  # uri_prefix -> server_name
        self._prompt_routes: Dict[str, str] = {}  # prompt_name -> server_name

    def register_server(
        self,
        server: MCPServer,
        prefix: Optional[str] = None,
    ) -> None:
        """
        Register an MCP server.

        Args:
            server: MCP server instance
            prefix: Optional prefix for routing (defaults to server name)
        """
        server_name = prefix or server.name
        self._servers[server_name] = server

        # Register tool routes
        for tool_name in server.tools:
            full_name = f"{server_name}.{tool_name}" if prefix else tool_name
            self._tool_routes[full_name] = server_name
            self._tool_routes[tool_name] = server_name  # Also register without prefix

        # Register resource routes
        for uri in server.resources:
            self._resource_routes[uri] = server_name

        # Register prompt routes
        for prompt_name in server.prompts:
            self._prompt_routes[prompt_name] = server_name

        logger.info(f"Registered server: {server_name} with {len(server.tools)} tools")

    def unregister_server(self, name: str) -> None:
        """
        Unregister an MCP server.

        Args:
            name: Server name
        """
        if name not in self._servers:
            return

        server = self._servers.pop(name)

        # Remove tool routes
        self._tool_routes = {
            k: v for k, v in self._tool_routes.items() if v != name
        }

        # Remove resource routes
        self._resource_routes = {
            k: v for k, v in self._resource_routes.items() if v != name
        }

        # Remove prompt routes
        self._prompt_routes = {
            k: v for k, v in self._prompt_routes.items() if v != name
        }

        logger.info(f"Unregistered server: {name}")

    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get a server by name."""
        return self._servers.get(name)

    def list_servers(self) -> List[str]:
        """List all registered server names."""
        return list(self._servers.keys())

    # ═══════════════════════════════════════════════════════════════════════════
    # Aggregated Tool Interface
    # ═══════════════════════════════════════════════════════════════════════════

    def list_tools(self, include_prefix: bool = True) -> List[Tool]:
        """
        Get all tools from all servers.

        Args:
            include_prefix: Whether to prefix tool names with server name

        Returns:
            Combined list of all tools
        """
        tools = []
        for server_name, server in self._servers.items():
            for tool in server.list_tools():
                if include_prefix:
                    # Create new tool with prefixed name
                    prefixed_tool = Tool(
                        name=f"{server_name}.{tool.name}",
                        description=f"[{server_name}] {tool.description}",
                        input_schema=tool.input_schema,
                    )
                    tools.append(prefixed_tool)
                else:
                    tools.append(tool)
        return tools

    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Route tool call to appropriate server.

        Supports both prefixed (server.tool) and unprefixed tool names.
        """
        tool_name = tool_call.tool_name

        # Check for prefixed name (server.tool)
        if "." in tool_name:
            parts = tool_name.split(".", 1)
            server_name = parts[0]
            actual_tool = parts[1]

            if server_name in self._servers:
                server = self._servers[server_name]
                # Create new tool call with unprefixed name
                local_call = ToolCall(
                    tool_name=actual_tool,
                    arguments=tool_call.arguments,
                    call_id=tool_call.call_id,
                )
                return await server.call_tool(local_call)

        # Try direct routing
        if tool_name in self._tool_routes:
            server_name = self._tool_routes[tool_name]
            server = self._servers[server_name]
            return await server.call_tool(tool_call)

        # Tool not found
        from core.mcp.types import ToolContent
        return ToolResult(
            call_id=tool_call.call_id,
            content=[ToolContent(type="text", text=f"Tool not found: {tool_name}")],
            is_error=True,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Aggregated Resource Interface
    # ═══════════════════════════════════════════════════════════════════════════

    def list_resources(self) -> List:
        """Get all resources from all servers."""
        resources = []
        for server in self._servers.values():
            resources.extend(server.list_resources())
        return resources

    async def read_resource(self, uri: str):
        """Route resource read to appropriate server."""
        # Find server by URI prefix match
        for prefix, server_name in self._resource_routes.items():
            if uri == prefix or uri.startswith(prefix):
                server = self._servers[server_name]
                return await server.read_resource(uri)

        raise ValueError(f"Resource not found: {uri}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Aggregated Prompt Interface
    # ═══════════════════════════════════════════════════════════════════════════

    def list_prompts(self) -> List:
        """Get all prompts from all servers."""
        prompts = []
        for server in self._servers.values():
            prompts.extend(server.list_prompts())
        return prompts

    async def get_prompt(self, name: str, arguments: Optional[dict] = None) -> List:
        """Route prompt request to appropriate server."""
        if name in self._prompt_routes:
            server_name = self._prompt_routes[name]
            server = self._servers[server_name]
            return await server.get_prompt(name, arguments)

        raise ValueError(f"Prompt not found: {name}")

    # ═══════════════════════════════════════════════════════════════════════════
    # JSON-RPC Interface
    # ═══════════════════════════════════════════════════════════════════════════

    async def handle_message(self, message: Union[str, dict]) -> Optional[str]:
        """
        Handle incoming JSON-RPC message.

        Routes to appropriate server or handles registry-level requests.
        """
        import json

        if isinstance(message, str):
            data = json.loads(message)
        else:
            data = message

        method = data.get("method", "")
        params = data.get("params", {})

        # Handle registry-level methods
        if method == "initialize":
            result = self._handle_initialize(params)
            return json.dumps({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": result,
            })

        if method == "tools/list":
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self.list_tools()
            ]
            return json.dumps({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"tools": tools},
            })

        if method == "tools/call":
            tool_call = ToolCall(
                tool_name=params.get("name", ""),
                arguments=params.get("arguments", {}),
            )
            result = await self.call_tool(tool_call)
            return json.dumps({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": result.model_dump(exclude_none=True, by_alias=True),
            })

        if method == "resources/list":
            resources = [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in self.list_resources()
            ]
            return json.dumps({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"resources": resources},
            })

        if method == "prompts/list":
            prompts = [
                {
                    "name": p.name,
                    "description": p.description,
                }
                for p in self.list_prompts()
            ]
            return json.dumps({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"prompts": prompts},
            })

        # Method not found
        return json.dumps({
            "jsonrpc": "2.0",
            "id": data.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        # Aggregate capabilities from all servers
        has_tools = any(s.tools for s in self._servers.values())
        has_resources = any(s.resources for s in self._servers.values())
        has_prompts = any(s.prompts for s in self._servers.values())

        return {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": True} if has_tools else None,
                "resources": {"subscribe": True, "listChanged": True} if has_resources else None,
                "prompts": {"listChanged": True} if has_prompts else None,
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
            "instructions": f"Registry with {len(self._servers)} servers: {', '.join(self._servers.keys())}",
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def to_json(self) -> str:
        """Serialize registry to JSON."""
        import json
        return json.dumps({
            "name": self.name,
            "version": self.version,
            "servers": [
                {
                    "name": name,
                    "tools": len(server.tools),
                    "resources": len(server.resources),
                    "prompts": len(server.prompts),
                }
                for name, server in self._servers.items()
            ],
        })

    def stats(self) -> dict:
        """Get registry statistics."""
        return {
            "servers": len(self._servers),
            "tools": sum(len(s.tools) for s in self._servers.values()),
            "resources": sum(len(s.resources) for s in self._servers.values()),
            "prompts": sum(len(s.prompts) for s in self._servers.values()),
        }
