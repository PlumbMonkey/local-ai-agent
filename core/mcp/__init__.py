"""Model Context Protocol (MCP) implementation.

This module provides a complete MCP implementation including:
- Server: Base server with tool/resource/prompt registration
- HardenedMCPServer: Production-ready server with validation, rate limiting, security
- Client: Connect to external MCP servers via HTTP/WebSocket/stdio
- Transport: HTTP, WebSocket, and stdio transports
- Registry: Manage multiple domain servers
- Protocol: JSON-RPC types and MCP constants
- Validation: Schema and request validation
- Rate Limiting: Token bucket rate limiter
- Security: Authentication and authorization middleware
- Metrics: Request and tool call metrics
"""

from core.mcp.client import MCPClient
from core.mcp.hardened import HardenedMCPServer
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

# Phase 3: Hardening modules
from core.mcp.validation import (
    SchemaValidator,
    RequestValidator,
    ValidationResult,
    schema_validator,
    request_validator,
)
from core.mcp.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    default_rate_limiter,
)
from core.mcp.security import (
    AuthContext,
    AuthProvider,
    NoAuthProvider,
    TokenAuthProvider,
    HMACAuthProvider,
    SecurityMiddleware,
    Permission,
    Role,
    ROLE_READONLY,
    ROLE_USER,
    ROLE_ADMIN,
    default_security,
)
from core.mcp.metrics import (
    MetricsCollector,
    RequestTimer,
    ToolTimer,
    Histogram,
    default_metrics,
)

__all__ = [
    # Core classes
    "MCPServer",
    "HardenedMCPServer",
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
    # Phase 3: Validation
    "SchemaValidator",
    "RequestValidator",
    "ValidationResult",
    "schema_validator",
    "request_validator",
    # Phase 3: Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "default_rate_limiter",
    # Phase 3: Security
    "AuthContext",
    "AuthProvider",
    "NoAuthProvider",
    "TokenAuthProvider",
    "HMACAuthProvider",
    "SecurityMiddleware",
    "Permission",
    "Role",
    "ROLE_READONLY",
    "ROLE_USER",
    "ROLE_ADMIN",
    "default_security",
    # Phase 3: Metrics
    "MetricsCollector",
    "RequestTimer",
    "ToolTimer",
    "Histogram",
    "default_metrics",
]
