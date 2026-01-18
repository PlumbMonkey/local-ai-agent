"""Type definitions for Model Context Protocol."""

from typing import Any, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Types
# ═══════════════════════════════════════════════════════════════════════════════


class Tool(BaseModel):
    """Tool definition in MCP."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: dict[str, Any] = Field(
        ..., alias="inputSchema", description="JSON Schema for tool input"
    )


class ToolCall(BaseModel):
    """Tool invocation."""

    model_config = ConfigDict(populate_by_name=True)

    tool_name: str = Field(..., alias="name", description="Name of tool to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )
    call_id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_meta",
        description="Call ID for tracking",
    )


class ToolResult(BaseModel):
    """Result of tool execution."""

    model_config = ConfigDict(populate_by_name=True)

    call_id: Optional[str] = Field(default=None, description="Call ID this result is for")
    content: list["ToolContent"] = Field(
        default_factory=list, description="Result content items"
    )
    is_error: bool = Field(default=False, alias="isError", description="Whether result is an error")

    # Legacy fields for backward compatibility
    output: Optional[Any] = Field(default=None, exclude=True, description="Legacy output field")
    error: Optional[str] = Field(default=None, exclude=True, description="Legacy error field")


class ToolContent(BaseModel):
    """Content item in tool result."""

    type: Literal["text", "image", "resource"] = "text"
    text: Optional[str] = None
    data: Optional[str] = None  # Base64 for images
    mimeType: Optional[str] = None
    resource: Optional[dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Progress & Cancellation
# ═══════════════════════════════════════════════════════════════════════════════


class ProgressToken(BaseModel):
    """Token for tracking long-running operations."""

    token: Union[str, int]


class ProgressNotification(BaseModel):
    """Progress update for long-running operations."""

    progressToken: Union[str, int]
    progress: float = Field(..., ge=0.0, le=1.0)
    total: Optional[float] = None
    message: Optional[str] = None


class CancelledNotification(BaseModel):
    """Notification that an operation was cancelled."""

    requestId: Union[str, int]
    reason: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Pagination
# ═══════════════════════════════════════════════════════════════════════════════


class PaginatedRequest(BaseModel):
    """Request with pagination support."""

    cursor: Optional[str] = None


class PaginatedResult(BaseModel):
    """Result with pagination support."""

    nextCursor: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Roots (Client capabilities)
# ═══════════════════════════════════════════════════════════════════════════════


class Root(BaseModel):
    """A root directory exposed by the client."""

    uri: str = Field(..., description="File URI of the root")
    name: Optional[str] = Field(default=None, description="Display name for the root")


class ListRootsResult(BaseModel):
    """Response to roots/list request."""

    roots: list[Root] = Field(default_factory=list)


# Update forward references
ToolResult.model_rebuild()
