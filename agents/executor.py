"""Smart tool execution engine with retry logic and error recovery.

This module provides intelligent tool execution with:
- Automatic retry with LLM-guided error analysis
- Timeout handling
- Error classification and recovery strategies
- Execution metrics tracking
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Error Types
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorCategory(str, Enum):
    """Categories of errors for retry strategy selection."""

    TRANSIENT = "transient"  # Network, timeout - retry as-is
    RECOVERABLE = "recoverable"  # Bad args - retry with fixes
    FATAL = "fatal"  # Permission, not found - don't retry
    UNKNOWN = "unknown"  # Analyze with LLM


@dataclass
class ExecutionError:
    """Detailed error information from tool execution."""

    tool: str
    arguments: Dict[str, Any]
    error_type: str
    message: str
    category: ErrorCategory
    attempt: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    traceback: Optional[str] = None
    recovery_suggestion: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of tool execution."""

    tool: str
    arguments: Dict[str, Any]
    success: bool
    result: Optional[Any] = None
    error: Optional[ExecutionError] = None
    duration_ms: float = 0.0
    attempts: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════════════════
# Retry Strategies
# ═══════════════════════════════════════════════════════════════════════════════


class RetryStrategy:
    """Base class for retry strategies."""

    @staticmethod
    def should_retry(error: ExecutionError) -> bool:
        """Determine if this error should be retried."""
        return error.category in [ErrorCategory.TRANSIENT, ErrorCategory.RECOVERABLE]

    @staticmethod
    def modify_arguments(
        error: ExecutionError,
        original_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Modify arguments for retry based on error."""
        return original_args  # Default: no modification


class TimeoutRetryStrategy(RetryStrategy):
    """Strategy for handling timeout errors."""

    @staticmethod
    def should_retry(error: ExecutionError) -> bool:
        return "timeout" in error.message.lower()

    @staticmethod
    def modify_arguments(
        error: ExecutionError,
        original_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Increase timeout if specified
        args = original_args.copy()
        if "timeout" in args:
            args["timeout"] = args["timeout"] * 2
        return args


class FileNotFoundRetryStrategy(RetryStrategy):
    """Strategy for handling file not found errors."""

    @staticmethod
    def should_retry(error: ExecutionError) -> bool:
        return any(
            phrase in error.message.lower()
            for phrase in ["not found", "no such file", "does not exist"]
        )

    @staticmethod
    def modify_arguments(
        error: ExecutionError,
        original_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        args = original_args.copy()
        # Try adding ./ prefix or changing path format
        if "path" in args:
            path = args["path"]
            if not path.startswith("./") and not path.startswith("/"):
                args["path"] = f"./{path}"
        return args


class RateLimitRetryStrategy(RetryStrategy):
    """Strategy for handling rate limit errors."""

    @staticmethod
    def should_retry(error: ExecutionError) -> bool:
        return any(
            phrase in error.message.lower()
            for phrase in ["rate limit", "too many requests", "429"]
        )

    @staticmethod
    async def wait_before_retry(error: ExecutionError) -> float:
        """Return wait time in seconds before retry."""
        # Exponential backoff based on attempt number
        base_wait = 2 ** error.attempt
        return min(base_wait, 60)  # Cap at 60 seconds


# ═══════════════════════════════════════════════════════════════════════════════
# Error Classifier
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorClassifier:
    """Classify errors into categories for retry decisions."""

    TRANSIENT_PATTERNS = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "rate limit",
        "too many requests",
    ]

    RECOVERABLE_PATTERNS = [
        "invalid argument",
        "bad request",
        "missing parameter",
        "type error",
        "validation",
    ]

    FATAL_PATTERNS = [
        "permission denied",
        "unauthorized",
        "forbidden",
        "not found",
        "does not exist",
        "authentication",
    ]

    @classmethod
    def classify(cls, error: Exception) -> ErrorCategory:
        """Classify an error into a category."""
        message = str(error).lower()

        for pattern in cls.TRANSIENT_PATTERNS:
            if pattern in message:
                return ErrorCategory.TRANSIENT

        for pattern in cls.RECOVERABLE_PATTERNS:
            if pattern in message:
                return ErrorCategory.RECOVERABLE

        for pattern in cls.FATAL_PATTERNS:
            if pattern in message:
                return ErrorCategory.FATAL

        return ErrorCategory.UNKNOWN

    @classmethod
    def get_strategy(cls, error: ExecutionError) -> Type[RetryStrategy]:
        """Get appropriate retry strategy for error."""
        message = error.message.lower()

        if "timeout" in message:
            return TimeoutRetryStrategy
        elif any(p in message for p in ["not found", "does not exist"]):
            return FileNotFoundRetryStrategy
        elif any(p in message for p in ["rate limit", "429"]):
            return RateLimitRetryStrategy
        else:
            return RetryStrategy


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Executor
# ═══════════════════════════════════════════════════════════════════════════════


class ToolExecutor:
    """
    Smart tool executor with automatic retry and error recovery.

    Example:
        executor = ToolExecutor(registry)
        result = await executor.execute("filesystem.read_file", {"path": "api.py"})
    """

    def __init__(
        self,
        mcp_registry: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        max_retries: int = 3,
        default_timeout: float = 30.0,
    ):
        """
        Initialize tool executor.

        Args:
            mcp_registry: MCP server registry for tool calls
            llm_client: LLM client for error analysis
            max_retries: Maximum retry attempts
            default_timeout: Default timeout for tool calls
        """
        self.registry = mcp_registry
        self.llm = llm_client
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        self._attempt_history: List[ExecutionError] = []

    async def execute(
        self,
        tool: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute a tool with automatic retry.

        Args:
            tool: Tool name (e.g., "filesystem.read_file")
            arguments: Tool arguments
            timeout: Optional timeout override

        Returns:
            ExecutionResult with success/failure info
        """
        timeout = timeout or self.default_timeout
        self._attempt_history = []

        current_args = arguments.copy()

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Executing {tool} (attempt {attempt}/{self.max_retries})")

            start_time = time.time()

            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._call_tool(tool, current_args),
                    timeout=timeout,
                )

                duration_ms = (time.time() - start_time) * 1000

                return ExecutionResult(
                    tool=tool,
                    arguments=current_args,
                    success=True,
                    result=result,
                    duration_ms=duration_ms,
                    attempts=attempt,
                )

            except asyncio.TimeoutError:
                error = ExecutionError(
                    tool=tool,
                    arguments=current_args,
                    error_type="TimeoutError",
                    message=f"Tool execution timed out after {timeout}s",
                    category=ErrorCategory.TRANSIENT,
                    attempt=attempt,
                )
                self._attempt_history.append(error)

            except Exception as e:
                category = ErrorClassifier.classify(e)
                error = ExecutionError(
                    tool=tool,
                    arguments=current_args,
                    error_type=type(e).__name__,
                    message=str(e),
                    category=category,
                    attempt=attempt,
                )
                self._attempt_history.append(error)

                # Check if we should retry
                if category == ErrorCategory.FATAL:
                    logger.warning(f"Fatal error, not retrying: {e}")
                    break

            # Prepare for retry
            if attempt < self.max_retries:
                # Get retry strategy
                strategy = ErrorClassifier.get_strategy(error)

                if not strategy.should_retry(error):
                    logger.warning(f"Strategy says don't retry: {error.message}")
                    break

                # Handle rate limit wait
                if strategy == RateLimitRetryStrategy:
                    wait_time = await RateLimitRetryStrategy.wait_before_retry(error)
                    logger.info(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

                # Try LLM analysis for unknown errors
                if error.category == ErrorCategory.UNKNOWN and self.llm:
                    suggestion = await self._analyze_error_with_llm(error, current_args)
                    if suggestion:
                        current_args = suggestion
                        logger.info(f"LLM suggested modified args: {current_args}")
                else:
                    # Apply strategy modification
                    current_args = strategy.modify_arguments(error, current_args)

        # All retries failed
        duration_ms = (time.time() - start_time) * 1000

        return ExecutionResult(
            tool=tool,
            arguments=arguments,
            success=False,
            error=self._attempt_history[-1] if self._attempt_history else None,
            duration_ms=duration_ms,
            attempts=len(self._attempt_history),
        )

    async def _call_tool(self, tool: str, arguments: Dict[str, Any]) -> Any:
        """Call the actual MCP tool."""
        if self.registry:
            from core.mcp.types import ToolCall

            tool_call = ToolCall(tool_name=tool, arguments=arguments)
            result = await self.registry.call_tool(tool_call)

            if result.is_error:
                raise Exception(result.content[0].text if result.content else "Tool error")

            return result.content[0].text if result.content else None
        else:
            # Simulation mode
            logger.warning(f"No registry, simulating tool call: {tool}")
            return {"simulated": True, "tool": tool, "arguments": arguments}

    async def _analyze_error_with_llm(
        self,
        error: ExecutionError,
        current_args: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to analyze error and suggest fixes."""
        if not self.llm:
            return None

        prompt = f"""You attempted to call tool '{error.tool}' with:
Arguments: {json.dumps(current_args, indent=2)}

It failed with error:
Type: {error.error_type}
Message: {error.message}

This is attempt {error.attempt} of {self.max_retries}.

Analyze the error and suggest modified arguments to fix it.
Respond with JSON only (no explanation):
{{
    "can_fix": true/false,
    "new_arguments": {{...}},
    "reason": "brief explanation"
}}"""

        try:
            if hasattr(self.llm, "generate_async"):
                response = await self.llm.generate_async(prompt)
            elif hasattr(self.llm, "generate"):
                response = self.llm.generate(prompt)
            else:
                return None

            data = json.loads(response)
            if data.get("can_fix"):
                return data.get("new_arguments", current_args)
        except Exception as e:
            logger.warning(f"LLM error analysis failed: {e}")

        return None

    def get_attempt_history(self) -> List[ExecutionError]:
        """Get history of all execution attempts."""
        return self._attempt_history.copy()


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Executor
# ═══════════════════════════════════════════════════════════════════════════════


class BatchExecutor:
    """Execute multiple tools with dependency ordering."""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    async def execute_plan(
        self,
        steps: List[Dict[str, Any]],
        stop_on_error: bool = True,
    ) -> List[ExecutionResult]:
        """
        Execute a plan of steps in order.

        Args:
            steps: List of step dicts with tool, arguments, etc.
            stop_on_error: Whether to stop on first error

        Returns:
            List of ExecutionResults for each step
        """
        results = []

        for i, step in enumerate(steps):
            tool = step.get("tool", "")
            arguments = step.get("arguments", {})

            logger.info(f"Executing plan step {i + 1}/{len(steps)}: {tool}")

            result = await self.executor.execute(tool, arguments)
            results.append(result)

            if not result.success and stop_on_error:
                logger.warning(f"Stopping execution due to error in step {i + 1}")
                break

        return results

    async def execute_parallel(
        self,
        tools_and_args: List[Tuple[str, Dict[str, Any]]],
    ) -> List[ExecutionResult]:
        """
        Execute multiple independent tools in parallel.

        Args:
            tools_and_args: List of (tool_name, arguments) tuples

        Returns:
            List of ExecutionResults
        """
        tasks = [
            self.executor.execute(tool, args)
            for tool, args in tools_and_args
        ]

        return await asyncio.gather(*tasks)
