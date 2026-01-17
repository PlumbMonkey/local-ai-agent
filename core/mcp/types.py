"""Type definitions for Model Context Protocol."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class Tool(BaseModel):
    """Tool definition in MCP."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: dict[str, Any] = Field(
        ..., description="JSON Schema for tool input"
    )


class ToolCall(BaseModel):
    """Tool invocation."""

    tool_name: str = Field(..., description="Name of tool to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )
    call_id: Optional[str] = Field(default=None, description="Call ID for tracking")


class ToolResult(BaseModel):
    """Result of tool execution."""

    call_id: Optional[str] = Field(default=None, description="Call ID this result is for")
    output: Any = Field(..., description="Tool output")
    error: Optional[str] = Field(default=None, description="Error message if any")
    is_error: bool = Field(default=False, description="Whether result is an error")
