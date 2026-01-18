"""MCP Protocol constants and message types per JSON-RPC 2.0 spec."""

from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

# Protocol version
MCP_VERSION = "2024-11-05"

# ═══════════════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 Base Types
# ═══════════════════════════════════════════════════════════════════════════════


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional["JSONRPCError"] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error."""

    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCNotification(BaseModel):
    """JSON-RPC 2.0 Notification (no id, no response expected)."""

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Optional[dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Standard Error Codes
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorCode(int, Enum):
    """Standard JSON-RPC and MCP error codes."""

    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    TOOL_NOT_FOUND = -32001
    RESOURCE_NOT_FOUND = -32002
    PERMISSION_DENIED = -32003
    TIMEOUT = -32004


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Capability Types
# ═══════════════════════════════════════════════════════════════════════════════


class ServerCapabilities(BaseModel):
    """Server capability advertisement."""

    tools: Optional[dict[str, Any]] = Field(default_factory=lambda: {"listChanged": True})
    resources: Optional[dict[str, Any]] = Field(
        default_factory=lambda: {"subscribe": True, "listChanged": True}
    )
    prompts: Optional[dict[str, Any]] = Field(default_factory=lambda: {"listChanged": True})
    logging: Optional[dict[str, Any]] = None
    experimental: Optional[dict[str, Any]] = None


class ClientCapabilities(BaseModel):
    """Client capability advertisement."""

    roots: Optional[dict[str, Any]] = Field(default_factory=lambda: {"listChanged": True})
    sampling: Optional[dict[str, Any]] = None
    experimental: Optional[dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Initialization
# ═══════════════════════════════════════════════════════════════════════════════


class ClientInfo(BaseModel):
    """Client identification."""

    name: str
    version: str


class ServerInfo(BaseModel):
    """Server identification."""

    name: str
    version: str


class InitializeRequest(BaseModel):
    """Client -> Server initialization request."""

    protocolVersion: str = MCP_VERSION
    capabilities: ClientCapabilities = Field(default_factory=ClientCapabilities)
    clientInfo: ClientInfo


class InitializeResult(BaseModel):
    """Server -> Client initialization response."""

    protocolVersion: str = MCP_VERSION
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    serverInfo: ServerInfo
    instructions: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Resource Types
# ═══════════════════════════════════════════════════════════════════════════════


class Resource(BaseModel):
    """A resource exposed by the server."""

    uri: str = Field(..., description="Unique resource identifier")
    name: str = Field(..., description="Human-readable name")
    description: Optional[str] = None
    mimeType: Optional[str] = None


class ResourceTemplate(BaseModel):
    """A parameterized resource template."""

    uriTemplate: str = Field(..., description="URI template with placeholders")
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None


class ResourceContents(BaseModel):
    """Contents of a resource."""

    uri: str
    mimeType: Optional[str] = None
    text: Optional[str] = None
    blob: Optional[str] = None  # Base64 encoded


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Prompt Types
# ═══════════════════════════════════════════════════════════════════════════════


class PromptArgument(BaseModel):
    """Argument for a prompt template."""

    name: str
    description: Optional[str] = None
    required: bool = False


class Prompt(BaseModel):
    """A prompt template exposed by the server."""

    name: str
    description: Optional[str] = None
    arguments: Optional[list[PromptArgument]] = None


class PromptMessage(BaseModel):
    """A message in a prompt response."""

    role: Literal["user", "assistant"]
    content: "TextContent | ImageContent | EmbeddedResource"


class TextContent(BaseModel):
    """Text content in a message."""

    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    """Image content in a message."""

    type: Literal["image"] = "image"
    data: str  # Base64 encoded
    mimeType: str


class EmbeddedResource(BaseModel):
    """Embedded resource in a message."""

    type: Literal["resource"] = "resource"
    resource: ResourceContents


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Method Names
# ═══════════════════════════════════════════════════════════════════════════════


class MCPMethod(str, Enum):
    """Standard MCP method names."""

    # Lifecycle
    INITIALIZE = "initialize"
    INITIALIZED = "notifications/initialized"
    SHUTDOWN = "shutdown"

    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"

    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"

    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    # Logging
    LOGGING_SET_LEVEL = "logging/setLevel"

    # Notifications
    NOTIFICATION_CANCELLED = "notifications/cancelled"
    NOTIFICATION_PROGRESS = "notifications/progress"
    NOTIFICATION_RESOURCES_UPDATED = "notifications/resources/updated"
    NOTIFICATION_RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"
    NOTIFICATION_TOOLS_LIST_CHANGED = "notifications/tools/list_changed"
    NOTIFICATION_PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed"


# ═══════════════════════════════════════════════════════════════════════════════
# Logging Types
# ═══════════════════════════════════════════════════════════════════════════════


class LogLevel(str, Enum):
    """MCP log levels."""

    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


class LogMessage(BaseModel):
    """Log message notification."""

    level: LogLevel
    logger: Optional[str] = None
    data: Any


# Update forward references
PromptMessage.model_rebuild()
JSONRPCResponse.model_rebuild()
