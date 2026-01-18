"""Model Context Protocol (MCP) implementation.

This module provides a complete MCP implementation including:
- Server: Base server with tool/resource/prompt registration
- Client: Connect to external MCP servers via HTTP/WebSocket/stdio
- Transport: HTTP, WebSocket, and stdio transports
- Registry: Manage multiple domain servers
- Protocol: JSON-RPC types and MCP constants
"""

from core.mcp.client import MCPClient
from core.mcp.http_server import MCPHttpServer
from core.mcp.protocol import (
    MCP_VERSION,
    ClientCapabilities,
    ClientInfo,
    ErrorCode,
    InitializeRequest,
    InitializeResult,
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    LogLevel,
    MCPMethod,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    ResourceContents,
    ResourceTemplate,
    ServerCapabilities,
    ServerInfo,
    TextContent,
)
from core.mcp.registry import MCPServerRegistry
from core.mcp.server import MCPServer
from core.mcp.transport import MCPTransport, SSETransport, StdioTransport, WebSocketTransport
from core.mcp.types import (
    CancelledNotification,
    PaginatedRequest,
    PaginatedResult,
    ProgressNotification,
    ProgressToken,
    Root,
    Tool,
    ToolCall,
    ToolContent,
    ToolResult,
)

__all__ = [
    # Core classes
    "MCPServer",
    "MCPClient",
    "MCPHttpServer",
    "MCPServerRegistry",
    # Transports
    "MCPTransport",
    "StdioTransport",
    "WebSocketTransport",
    "SSETransport",
    # Protocol types
    "MCP_VERSION",
    "MCPMethod",
    "ErrorCode",
    "LogLevel",
    # JSON-RPC
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCNotification",
    # Initialization
    "InitializeRequest",
    "InitializeResult",
    "ClientInfo",
    "ServerInfo",
    "ClientCapabilities",
    "ServerCapabilities",
    # Tools
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolContent",
    # Resources
    "Resource",
    "ResourceTemplate",
    "ResourceContents",
    # Prompts
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "TextContent",
    # Progress & pagination
    "ProgressToken",
    "ProgressNotification",
    "CancelledNotification",
    "PaginatedRequest",
    "PaginatedResult",
    "Root",
]
