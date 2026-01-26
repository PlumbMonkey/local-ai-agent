"""Unit tests for agent executor module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.executor import (
    ToolExecutor,
    BatchExecutor,
    ExecutionResult,
    ExecutionError,
    ErrorCategory,
    ErrorClassifier,
    RetryStrategy,
    TimeoutRetryStrategy,
    FileNotFoundRetryStrategy,
    RateLimitRetryStrategy,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ErrorClassifier Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorClassifier:
    """Tests for ErrorClassifier."""

    def test_classify_transient_timeout(self):
        """Should classify timeout errors as transient."""
        error = Exception("Connection timeout after 30s")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_transient_network(self):
        """Should classify network errors as transient."""
        error = Exception("Network connection failed")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_recoverable_validation(self):
        """Should classify validation errors as recoverable."""
        error = Exception("Invalid argument: 'path' must be a string")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.RECOVERABLE

    def test_classify_fatal_permission(self):
        """Should classify permission errors as fatal."""
        error = Exception("Permission denied: /root/secret")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.FATAL

    def test_classify_fatal_not_found(self):
        """Should classify not found errors as fatal."""
        error = Exception("File does not exist: config.yaml")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.FATAL

    def test_classify_unknown(self):
        """Should classify unknown errors as unknown."""
        error = Exception("Something weird happened")
        result = ErrorClassifier.classify(error)
        assert result == ErrorCategory.UNKNOWN


class TestRetryStrategies:
    """Tests for retry strategies."""

    def test_timeout_strategy_should_retry(self):
        """TimeoutRetryStrategy should_retry checks message for 'timeout'."""
        # The strategy checks for 'timeout' in the message
        error = ExecutionError(
            tool="test",
            arguments={},
            error_type="TimeoutError",
            message="timeout",  # Message must contain 'timeout'
            category=ErrorCategory.TRANSIENT,
            attempt=1,
        )
        assert TimeoutRetryStrategy.should_retry(error) is True

    def test_timeout_strategy_increases_timeout(self):
        """TimeoutRetryStrategy should increase timeout arg."""
        error = ExecutionError(
            tool="test",
            arguments={},
            error_type="TimeoutError",
            message="Timeout",
            category=ErrorCategory.TRANSIENT,
            attempt=1,
        )
        original = {"timeout": 30}
        modified = TimeoutRetryStrategy.modify_arguments(error, original)
        assert modified["timeout"] == 60

    def test_file_not_found_strategy_matches(self):
        """FileNotFoundRetryStrategy should match not found errors."""
        error = ExecutionError(
            tool="test",
            arguments={},
            error_type="FileNotFoundError",
            message="No such file or directory",
            category=ErrorCategory.FATAL,
            attempt=1,
        )
        assert FileNotFoundRetryStrategy.should_retry(error) is True

    def test_file_not_found_strategy_modifies_path(self):
        """FileNotFoundRetryStrategy should add ./ prefix."""
        error = ExecutionError(
            tool="test",
            arguments={},
            error_type="FileNotFoundError",
            message="Not found",
            category=ErrorCategory.FATAL,
            attempt=1,
        )
        original = {"path": "config.yaml"}
        modified = FileNotFoundRetryStrategy.modify_arguments(error, original)
        assert modified["path"] == "./config.yaml"

    @pytest.mark.asyncio
    async def test_rate_limit_strategy_wait_time(self):
        """RateLimitRetryStrategy should return exponential backoff."""
        error = ExecutionError(
            tool="test",
            arguments={},
            error_type="RateLimitError",
            message="Too many requests",
            category=ErrorCategory.TRANSIENT,
            attempt=1,
        )
        wait = await RateLimitRetryStrategy.wait_before_retry(error)
        assert wait == 2  # 2^1

        error.attempt = 3
        wait = await RateLimitRetryStrategy.wait_before_retry(error)
        assert wait == 8  # 2^3


# ═══════════════════════════════════════════════════════════════════════════════
# ToolExecutor Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.fixture
    def executor(self):
        """Create executor without registry (simulation mode)."""
        return ToolExecutor(max_retries=3, default_timeout=5.0)

    @pytest.mark.asyncio
    async def test_execute_success_simulation(self, executor):
        """Should return simulated result without registry."""
        result = await executor.execute("test.tool", {"arg": "value"})
        assert result.success is True
        assert result.result["simulated"] is True
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_execute_with_registry_success(self):
        """Should call registry for real execution."""
        mock_registry = MagicMock()
        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.content = [MagicMock(text="Success")]
        mock_registry.call_tool = AsyncMock(return_value=mock_result)

        executor = ToolExecutor(mcp_registry=mock_registry)
        result = await executor.execute("test.tool", {"arg": "value"})

        assert result.success is True
        assert result.result == "Success"
        mock_registry.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_registry_error(self):
        """Should handle registry errors."""
        mock_registry = MagicMock()
        mock_result = MagicMock()
        mock_result.is_error = True
        mock_result.content = [MagicMock(text="Tool failed")]
        mock_registry.call_tool = AsyncMock(return_value=mock_result)

        executor = ToolExecutor(mcp_registry=mock_registry, max_retries=1)
        result = await executor.execute("test.tool", {})

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Should handle timeout errors."""
        mock_registry = MagicMock()

        async def slow_call(*args):
            await asyncio.sleep(10)

        mock_registry.call_tool = slow_call

        executor = ToolExecutor(
            mcp_registry=mock_registry,
            max_retries=1,
            default_timeout=0.1
        )
        result = await executor.execute("slow.tool", {})

        assert result.success is False
        assert result.error.error_type == "TimeoutError"

    @pytest.mark.asyncio
    async def test_execute_retry_on_transient(self):
        """Should retry transient errors."""
        mock_registry = MagicMock()
        call_count = 0

        async def failing_then_success(tool_call):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary network error")
            mock_result = MagicMock()
            mock_result.is_error = False
            mock_result.content = [MagicMock(text="Success after retry")]
            return mock_result

        mock_registry.call_tool = failing_then_success

        executor = ToolExecutor(mcp_registry=mock_registry, max_retries=3)
        result = await executor.execute("test.tool", {})

        assert result.success is True
        assert result.attempts == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_no_retry_on_fatal(self):
        """Should not retry fatal errors."""
        mock_registry = MagicMock()
        call_count = 0

        async def fatal_error(tool_call):
            nonlocal call_count
            call_count += 1
            raise Exception("Permission denied")

        mock_registry.call_tool = fatal_error

        executor = ToolExecutor(mcp_registry=mock_registry, max_retries=3)
        result = await executor.execute("test.tool", {})

        assert result.success is False
        assert call_count == 1  # No retries

    def test_get_attempt_history(self, executor):
        """Should track attempt history."""
        # Initial state
        assert executor.get_attempt_history() == []


# ═══════════════════════════════════════════════════════════════════════════════
# BatchExecutor Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchExecutor:
    """Tests for BatchExecutor."""

    @pytest.fixture
    def batch_executor(self):
        """Create batch executor with mock tool executor."""
        mock_executor = MagicMock(spec=ToolExecutor)
        mock_executor.execute = AsyncMock(
            return_value=ExecutionResult(
                tool="test",
                arguments={},
                success=True,
                result="OK",
            )
        )
        return BatchExecutor(mock_executor)

    @pytest.mark.asyncio
    async def test_execute_plan_success(self, batch_executor):
        """Should execute plan steps in order."""
        steps = [
            {"tool": "step1", "arguments": {"a": 1}},
            {"tool": "step2", "arguments": {"b": 2}},
            {"tool": "step3", "arguments": {"c": 3}},
        ]

        results = await batch_executor.execute_plan(steps)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_plan_stop_on_error(self, batch_executor):
        """Should stop on error by default."""
        batch_executor.executor.execute = AsyncMock(
            side_effect=[
                ExecutionResult(tool="s1", arguments={}, success=True),
                ExecutionResult(
                    tool="s2",
                    arguments={},
                    success=False,
                    error=ExecutionError(
                        tool="s2",
                        arguments={},
                        error_type="Error",
                        message="Failed",
                        category=ErrorCategory.FATAL,
                        attempt=1,
                    ),
                ),
                ExecutionResult(tool="s3", arguments={}, success=True),
            ]
        )

        steps = [
            {"tool": "step1", "arguments": {}},
            {"tool": "step2", "arguments": {}},
            {"tool": "step3", "arguments": {}},
        ]

        results = await batch_executor.execute_plan(steps, stop_on_error=True)

        assert len(results) == 2  # Stopped at step 2

    @pytest.mark.asyncio
    async def test_execute_plan_continue_on_error(self, batch_executor):
        """Should continue on error when configured."""
        batch_executor.executor.execute = AsyncMock(
            side_effect=[
                ExecutionResult(tool="s1", arguments={}, success=True),
                ExecutionResult(
                    tool="s2",
                    arguments={},
                    success=False,
                    error=ExecutionError(
                        tool="s2",
                        arguments={},
                        error_type="Error",
                        message="Failed",
                        category=ErrorCategory.FATAL,
                        attempt=1,
                    ),
                ),
                ExecutionResult(tool="s3", arguments={}, success=True),
            ]
        )

        steps = [
            {"tool": "step1", "arguments": {}},
            {"tool": "step2", "arguments": {}},
            {"tool": "step3", "arguments": {}},
        ]

        results = await batch_executor.execute_plan(steps, stop_on_error=False)

        assert len(results) == 3  # Continued past error

    @pytest.mark.asyncio
    async def test_execute_parallel(self, batch_executor):
        """Should execute tools in parallel."""
        tools_and_args = [
            ("tool1", {"a": 1}),
            ("tool2", {"b": 2}),
            ("tool3", {"c": 3}),
        ]

        results = await batch_executor.execute_parallel(tools_and_args)

        assert len(results) == 3
        assert batch_executor.executor.execute.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionResult Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_success_result(self):
        """Should create success result."""
        result = ExecutionResult(
            tool="test.tool",
            arguments={"key": "value"},
            success=True,
            result="output",
            duration_ms=150.5,
        )
        assert result.success is True
        assert result.error is None
        assert result.result == "output"

    def test_failure_result(self):
        """Should create failure result."""
        error = ExecutionError(
            tool="test.tool",
            arguments={},
            error_type="ValueError",
            message="Invalid input",
            category=ErrorCategory.RECOVERABLE,
            attempt=3,
        )
        result = ExecutionResult(
            tool="test.tool",
            arguments={},
            success=False,
            error=error,
            attempts=3,
        )
        assert result.success is False
        assert result.error is not None
        assert result.attempts == 3
