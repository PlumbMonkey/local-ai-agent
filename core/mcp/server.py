"""Base MCP Server implementation."""

import json
import logging
from typing import Callable, Optional

from core.mcp.types import Tool, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class MCPServer:
    """Base Model Context Protocol Server."""

    def __init__(self, name: str):
        """
        Initialize MCP server.

        Args:
            name: Server name
        """
        self.name = name
        self.tools: dict[str, Callable] = {}
        self.tool_definitions: dict[str, Tool] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable,
    ) -> None:
        """
        Register a tool with this server.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON Schema for inputs
            handler: Callable that implements the tool
        """
        tool = Tool(
            name=name,
            description=description,
            input_schema=input_schema,
        )
        self.tool_definitions[name] = tool
        self.tools[name] = handler

    def list_tools(self) -> list[Tool]:
        """Get list of available tools."""
        return list(self.tool_definitions.values())

    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool_call: Tool invocation details

        Returns:
            Tool execution result
        """
        try:
            if tool_call.tool_name not in self.tools:
                return ToolResult(
                    call_id=tool_call.call_id,
                    error=f"Tool not found: {tool_call.tool_name}",
                    is_error=True,
                )

            handler = self.tools[tool_call.tool_name]
            output = handler(**tool_call.arguments)

            return ToolResult(
                call_id=tool_call.call_id,
                output=output,
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                error=str(e),
                is_error=True,
            )

    def to_json(self) -> str:
        """Serialize server to JSON for protocol."""
        return json.dumps(
            {
                "name": self.name,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in self.list_tools()
                ],
            }
        )
