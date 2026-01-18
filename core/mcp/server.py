"""Base MCP Server implementation with full protocol support."""

import asyncio
import json
import logging
from typing import Any, Callable, Optional, Union
from uuid import uuid4

from core.mcp.protocol import (
    ClientCapabilities,
    ClientInfo,
    ErrorCode,
    InitializeResult,
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    LogLevel,
    LogMessage,
    MCP_VERSION,
    MCPMethod,
    Prompt,
    PromptMessage,
    Resource,
    ResourceContents,
    ServerCapabilities,
    ServerInfo,
)
from core.mcp.types import (
    PaginatedResult,
    ProgressNotification,
    Tool,
    ToolCall,
    ToolContent,
    ToolResult,
)

logger = logging.getLogger(__name__)


class MCPServer:
    """Base Model Context Protocol Server with full spec compliance."""

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        instructions: Optional[str] = None,
    ):
        """
        Initialize MCP server.

        Args:
            name: Server name
            version: Server version
            instructions: Optional instructions for the LLM on how to use this server
        """
        self.name = name
        self.version = version
        self.instructions = instructions

        # Tool registry
        self.tools: dict[str, Callable] = {}
        self.tool_definitions: dict[str, Tool] = {}

        # Resource registry
        self.resources: dict[str, Resource] = {}
        self.resource_handlers: dict[str, Callable] = {}

        # Prompt registry
        self.prompts: dict[str, Prompt] = {}
        self.prompt_handlers: dict[str, Callable] = {}

        # Session state
        self._initialized = False
        self._client_info: Optional[ClientInfo] = None
        self._client_capabilities: Optional[ClientCapabilities] = None

        # Method handlers
        self._method_handlers: dict[str, Callable] = {
            MCPMethod.INITIALIZE: self._handle_initialize,
            MCPMethod.SHUTDOWN: self._handle_shutdown,
            MCPMethod.TOOLS_LIST: self._handle_tools_list,
            MCPMethod.TOOLS_CALL: self._handle_tools_call,
            MCPMethod.RESOURCES_LIST: self._handle_resources_list,
            MCPMethod.RESOURCES_READ: self._handle_resources_read,
            MCPMethod.PROMPTS_LIST: self._handle_prompts_list,
            MCPMethod.PROMPTS_GET: self._handle_prompts_get,
            MCPMethod.LOGGING_SET_LEVEL: self._handle_logging_set_level,
        }

        # Logging
        self._log_level = LogLevel.INFO

    # ═══════════════════════════════════════════════════════════════════════════
    # Tool Registration
    # ═══════════════════════════════════════════════════════════════════════════

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
        logger.debug(f"Registered tool: {name}")

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
                    content=[ToolContent(type="text", text=f"Tool not found: {tool_call.tool_name}")],
                    is_error=True,
                )

            handler = self.tools[tool_call.tool_name]

            # Support both sync and async handlers
            if asyncio.iscoroutinefunction(handler):
                output = await handler(**tool_call.arguments)
            else:
                output = handler(**tool_call.arguments)

            # Normalize output to content list
            content = self._normalize_output(output)

            return ToolResult(
                call_id=tool_call.call_id,
                content=content,
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                content=[ToolContent(type="text", text=str(e))],
                is_error=True,
            )

    def _normalize_output(self, output: Any) -> list[ToolContent]:
        """Convert various output types to MCP content format."""
        if isinstance(output, list) and all(isinstance(x, ToolContent) for x in output):
            return output
        if isinstance(output, ToolContent):
            return [output]
        if isinstance(output, str):
            return [ToolContent(type="text", text=output)]
        if isinstance(output, dict):
            return [ToolContent(type="text", text=json.dumps(output, indent=2))]
        return [ToolContent(type="text", text=str(output))]

    # ═══════════════════════════════════════════════════════════════════════════
    # Resource Registration
    # ═══════════════════════════════════════════════════════════════════════════

    def register_resource(
        self,
        uri: str,
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        handler: Optional[Callable] = None,
    ) -> None:
        """
        Register a resource with this server.

        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            mime_type: MIME type of resource content
            handler: Callable to retrieve resource content
        """
        resource = Resource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mime_type,
        )
        self.resources[uri] = resource
        if handler:
            self.resource_handlers[uri] = handler
        logger.debug(f"Registered resource: {uri}")

    def list_resources(self) -> list[Resource]:
        """Get list of available resources."""
        return list(self.resources.values())

    async def read_resource(self, uri: str) -> ResourceContents:
        """Read resource contents."""
        if uri not in self.resources:
            raise ValueError(f"Resource not found: {uri}")

        resource = self.resources[uri]
        handler = self.resource_handlers.get(uri)

        if handler:
            if asyncio.iscoroutinefunction(handler):
                content = await handler()
            else:
                content = handler()
        else:
            content = ""

        return ResourceContents(
            uri=uri,
            mimeType=resource.mimeType,
            text=content if isinstance(content, str) else None,
            blob=content if not isinstance(content, str) else None,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Prompt Registration
    # ═══════════════════════════════════════════════════════════════════════════

    def register_prompt(
        self,
        name: str,
        description: Optional[str] = None,
        arguments: Optional[list[dict]] = None,
        handler: Optional[Callable] = None,
    ) -> None:
        """
        Register a prompt template with this server.

        Args:
            name: Prompt name
            description: Prompt description
            arguments: List of argument definitions
            handler: Callable to generate prompt messages
        """
        from core.mcp.protocol import PromptArgument

        prompt = Prompt(
            name=name,
            description=description,
            arguments=[PromptArgument(**arg) for arg in (arguments or [])],
        )
        self.prompts[name] = prompt
        if handler:
            self.prompt_handlers[name] = handler
        logger.debug(f"Registered prompt: {name}")

    def list_prompts(self) -> list[Prompt]:
        """Get list of available prompts."""
        return list(self.prompts.values())

    async def get_prompt(self, name: str, arguments: Optional[dict] = None) -> list[PromptMessage]:
        """Get prompt messages."""
        if name not in self.prompts:
            raise ValueError(f"Prompt not found: {name}")

        handler = self.prompt_handlers.get(name)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(**(arguments or {}))
            return handler(**(arguments or {}))
        return []

    # ═══════════════════════════════════════════════════════════════════════════
    # JSON-RPC Message Handling
    # ═══════════════════════════════════════════════════════════════════════════

    async def handle_message(self, message: Union[str, dict]) -> Optional[str]:
        """
        Handle incoming JSON-RPC message.

        Args:
            message: Raw JSON string or parsed dict

        Returns:
            JSON-RPC response string, or None for notifications
        """
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            # Check if it's a notification (no id)
            if "id" not in data or data.get("id") is None:
                notification = JSONRPCNotification(**data)
                await self._handle_notification(notification)
                return None

            # Parse as request
            request = JSONRPCRequest(**data)
            response = await self._handle_request(request)
            return response.model_dump_json(exclude_none=True)

        except json.JSONDecodeError as e:
            error_response = JSONRPCResponse(
                id=None,
                error=JSONRPCError(
                    code=ErrorCode.PARSE_ERROR,
                    message=f"Parse error: {e}",
                ),
            )
            return error_response.model_dump_json(exclude_none=True)
        except Exception as e:
            logger.exception("Error handling message")
            error_response = JSONRPCResponse(
                id=data.get("id") if isinstance(data, dict) else None,
                error=JSONRPCError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e),
                ),
            )
            return error_response.model_dump_json(exclude_none=True)

    async def _handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle a JSON-RPC request."""
        method = request.method

        if method not in self._method_handlers:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=ErrorCode.METHOD_NOT_FOUND,
                    message=f"Method not found: {method}",
                ),
            )

        try:
            handler = self._method_handlers[method]
            result = await handler(request.params or {})
            return JSONRPCResponse(id=request.id, result=result)
        except Exception as e:
            logger.exception(f"Error in method {method}")
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e),
                ),
            )

    async def _handle_notification(self, notification: JSONRPCNotification) -> None:
        """Handle a JSON-RPC notification."""
        method = notification.method

        if method == MCPMethod.INITIALIZED:
            self._initialized = True
            logger.info(f"Client initialized: {self._client_info}")
        elif method == MCPMethod.NOTIFICATION_CANCELLED:
            logger.debug(f"Request cancelled: {notification.params}")
        else:
            logger.debug(f"Unhandled notification: {method}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Protocol Method Handlers
    # ═══════════════════════════════════════════════════════════════════════════

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        self._client_info = ClientInfo(**params.get("clientInfo", {}))
        self._client_capabilities = ClientCapabilities(**params.get("capabilities", {}))

        result = InitializeResult(
            protocolVersion=MCP_VERSION,
            capabilities=ServerCapabilities(
                tools={"listChanged": True} if self.tools else None,
                resources={"subscribe": True, "listChanged": True} if self.resources else None,
                prompts={"listChanged": True} if self.prompts else None,
            ),
            serverInfo=ServerInfo(name=self.name, version=self.version),
            instructions=self.instructions,
        )
        return result.model_dump(exclude_none=True, by_alias=True)

    async def _handle_shutdown(self, params: dict) -> dict:
        """Handle shutdown request."""
        self._initialized = False
        return {}

    async def _handle_tools_list(self, params: dict) -> dict:
        """Handle tools/list request."""
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self.list_tools()
        ]
        return {"tools": tools}

    async def _handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request."""
        tool_call = ToolCall(
            tool_name=params.get("name", ""),
            arguments=params.get("arguments", {}),
        )
        result = await self.call_tool(tool_call)
        return result.model_dump(exclude_none=True, by_alias=True)

    async def _handle_resources_list(self, params: dict) -> dict:
        """Handle resources/list request."""
        resources = [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mimeType,
            }
            for r in self.list_resources()
        ]
        return {"resources": resources}

    async def _handle_resources_read(self, params: dict) -> dict:
        """Handle resources/read request."""
        uri = params.get("uri", "")
        contents = await self.read_resource(uri)
        return {"contents": [contents.model_dump(exclude_none=True)]}

    async def _handle_prompts_list(self, params: dict) -> dict:
        """Handle prompts/list request."""
        prompts = [
            {
                "name": p.name,
                "description": p.description,
                "arguments": [a.model_dump() for a in (p.arguments or [])],
            }
            for p in self.list_prompts()
        ]
        return {"prompts": prompts}

    async def _handle_prompts_get(self, params: dict) -> dict:
        """Handle prompts/get request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        messages = await self.get_prompt(name, arguments)
        return {"messages": [m.model_dump(exclude_none=True) for m in messages]}

    async def _handle_logging_set_level(self, params: dict) -> dict:
        """Handle logging/setLevel request."""
        level = params.get("level", "info")
        self._log_level = LogLevel(level)
        return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # Notifications (Server -> Client)
    # ═══════════════════════════════════════════════════════════════════════════

    def create_progress_notification(
        self,
        token: Union[str, int],
        progress: float,
        message: Optional[str] = None,
    ) -> str:
        """Create a progress notification message."""
        notification = JSONRPCNotification(
            method=MCPMethod.NOTIFICATION_PROGRESS,
            params={
                "progressToken": token,
                "progress": progress,
                "message": message,
            },
        )
        return notification.model_dump_json(exclude_none=True)

    def create_log_notification(
        self,
        level: LogLevel,
        data: Any,
        logger_name: Optional[str] = None,
    ) -> str:
        """Create a log notification message."""
        notification = JSONRPCNotification(
            method="notifications/message",
            params=LogMessage(
                level=level,
                logger=logger_name,
                data=data,
            ).model_dump(),
        )
        return notification.model_dump_json(exclude_none=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # Serialization
    # ═══════════════════════════════════════════════════════════════════════════

    def to_json(self) -> str:
        """Serialize server to JSON for protocol."""
        return json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in self.list_tools()
                ],
                "resources": [
                    {
                        "uri": r.uri,
                        "name": r.name,
                        "description": r.description,
                        "mimeType": r.mimeType,
                    }
                    for r in self.list_resources()
                ],
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                    }
                    for p in self.list_prompts()
                ],
            }
        )
