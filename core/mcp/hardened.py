"""Hardened MCP Server with validation, rate limiting, security, and metrics."""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional, Union

from core.mcp.metrics import MetricsCollector, RequestTimer, ToolTimer, default_metrics
from core.mcp.protocol import (
    ErrorCode,
    JSONRPCError,
    JSONRPCResponse,
)
from core.mcp.rate_limit import RateLimiter, RateLimitConfig, default_rate_limiter
from core.mcp.security import (
    AuthContext,
    Permission,
    SecurityMiddleware,
    default_security,
)
from core.mcp.server import MCPServer
from core.mcp.types import ToolCall, ToolContent, ToolResult
from core.mcp.validation import SchemaValidator, request_validator, schema_validator

logger = logging.getLogger(__name__)


class HardenedMCPServer(MCPServer):
    """
    MCP Server with production hardening features.

    Extends MCPServer with:
    - Input validation (schema validation for tool calls)
    - Rate limiting (per-client and per-tool)
    - Security middleware (authentication/authorization)
    - Metrics collection (latency, error rates, etc.)
    - Request timeouts
    """

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        instructions: Optional[str] = None,
        # Hardening options
        rate_limiter: Optional[RateLimiter] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        security: Optional[SecurityMiddleware] = None,
        metrics: Optional[MetricsCollector] = None,
        validate_inputs: bool = True,
        request_timeout: float = 30.0,
    ):
        """
        Initialize hardened MCP server.

        Args:
            name: Server name
            version: Server version
            instructions: Instructions for the LLM
            rate_limiter: Rate limiter instance (uses default if None)
            rate_limit_config: Rate limit configuration (creates new limiter if provided)
            security: Security middleware (uses default if None)
            metrics: Metrics collector (uses default if None)
            validate_inputs: Whether to validate tool inputs against schemas
            request_timeout: Default timeout for requests in seconds
        """
        super().__init__(name, version, instructions)

        # Initialize hardening components
        if rate_limit_config:
            self.rate_limiter = RateLimiter(rate_limit_config)
        else:
            self.rate_limiter = rate_limiter or default_rate_limiter

        self.security = security or default_security
        self.metrics = metrics or default_metrics
        self.validate_inputs = validate_inputs
        self.request_timeout = request_timeout

        # Schema validator
        self._schema_validator = schema_validator

    async def handle_message(
        self,
        message: Union[str, dict],
        client_id: str = "anonymous",
        auth_credentials: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Handle incoming JSON-RPC message with hardening.

        Args:
            message: Raw JSON string or parsed dict
            client_id: Client identifier for rate limiting
            auth_credentials: Authentication credentials

        Returns:
            JSON-RPC response string, or None for notifications
        """
        start_time = time.time()

        try:
            # Parse message
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            method = data.get("method", "unknown")

            # Check rate limit
            allowed, retry_after = await self.rate_limiter.check_limit(client_id)
            if not allowed:
                self.metrics.increment(
                    "mcp_rate_limit_exceeded", labels={"client": client_id}
                )
                return self._rate_limit_response(data.get("id"), retry_after)

            # Authenticate
            auth_context = await self.security.authenticate(
                auth_credentials or {"client_id": client_id}
            )

            # Authorize based on method
            if not self._check_authorization(auth_context, method, data.get("params")):
                return self._unauthorized_response(data.get("id"))

            # Consume rate limit token
            await self.rate_limiter.consume(client_id)

            # Process with timeout
            try:
                response = await asyncio.wait_for(
                    super().handle_message(data),
                    timeout=self.request_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout: {method}")
                self.metrics.increment("mcp_request_timeout", labels={"method": method})
                return self._timeout_response(data.get("id"))

            # Record metrics
            duration = time.time() - start_time
            await self.metrics.record_request(
                method, duration, success=True, client_id=client_id
            )

            return response

        except json.JSONDecodeError as e:
            duration = time.time() - start_time
            await self.metrics.record_request(
                "parse_error", duration, success=False, client_id=client_id
            )
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
            duration = time.time() - start_time
            await self.metrics.record_request(
                "internal_error", duration, success=False, client_id=client_id
            )
            error_response = JSONRPCResponse(
                id=data.get("id") if isinstance(data, dict) else None,
                error=JSONRPCError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e),
                ),
            )
            return error_response.model_dump_json(exclude_none=True)

    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call with validation and metrics.

        Args:
            tool_call: Tool invocation details

        Returns:
            Tool execution result
        """
        tool_name = tool_call.tool_name

        # Validate input schema if enabled
        if self.validate_inputs and tool_name in self.tool_definitions:
            tool = self.tool_definitions[tool_name]
            validation = self._schema_validator.validate(
                tool.input_schema, tool_call.arguments
            )

            if not validation.valid:
                logger.warning(
                    f"Tool input validation failed for {tool_name}: {validation.errors}"
                )
                return ToolResult(
                    call_id=tool_call.call_id,
                    content=[
                        ToolContent(
                            type="text",
                            text=f"Validation error: {'; '.join(validation.errors)}",
                        )
                    ],
                    is_error=True,
                )

        # Execute with metrics
        async with ToolTimer(self.metrics, tool_name) as timer:
            try:
                result = await super().call_tool(tool_call)
                if result.is_error:
                    timer.mark_failed()
                return result
            except Exception as e:
                timer.mark_failed()
                raise

    def _check_authorization(
        self,
        auth_context: AuthContext,
        method: str,
        params: Optional[dict],
    ) -> bool:
        """Check if request is authorized."""
        # Map method to permission
        method_permissions = {
            "tools/list": Permission.TOOLS_LIST,
            "tools/call": Permission.TOOLS_CALL,
            "resources/list": Permission.RESOURCES_LIST,
            "resources/read": Permission.RESOURCES_READ,
            "prompts/list": Permission.PROMPTS_LIST,
            "prompts/get": Permission.PROMPTS_GET,
        }

        permission = method_permissions.get(method)
        if not permission:
            # Allow lifecycle methods (initialize, shutdown, notifications)
            return True

        # For tool calls, also check specific tool authorization
        resource = None
        if method == "tools/call" and params:
            resource = params.get("name")

        return self.security.authorize(auth_context, permission, resource)

    def _rate_limit_response(self, request_id: Any, retry_after: Optional[float]) -> str:
        """Create rate limit exceeded response."""
        response = JSONRPCResponse(
            id=request_id,
            error=JSONRPCError(
                code=-32029,  # Custom rate limit error code
                message="Rate limit exceeded",
                data={"retryAfter": retry_after} if retry_after else None,
            ),
        )
        return response.model_dump_json(exclude_none=True)

    def _unauthorized_response(self, request_id: Any) -> str:
        """Create unauthorized response."""
        response = JSONRPCResponse(
            id=request_id,
            error=JSONRPCError(
                code=ErrorCode.PERMISSION_DENIED,
                message="Unauthorized",
            ),
        )
        return response.model_dump_json(exclude_none=True)

    def _timeout_response(self, request_id: Any) -> str:
        """Create timeout response."""
        response = JSONRPCResponse(
            id=request_id,
            error=JSONRPCError(
                code=ErrorCode.TIMEOUT,
                message=f"Request timeout ({self.request_timeout}s)",
            ),
        )
        return response.model_dump_json(exclude_none=True)

    def get_health(self) -> dict:
        """Get server health status including metrics."""
        metrics_stats = self.metrics.get_stats()

        return {
            "status": "healthy",
            "server": self.name,
            "version": self.version,
            "tools_count": len(self.tools),
            "resources_count": len(self.resources),
            "prompts_count": len(self.prompts),
            "metrics": {
                "uptime_seconds": metrics_stats.get("uptime_seconds", 0),
                "total_requests": metrics_stats.get("total_requests", 0),
                "error_rate": metrics_stats.get("error_rate", 0),
                "latency": metrics_stats.get("latency", {}),
            },
        }
