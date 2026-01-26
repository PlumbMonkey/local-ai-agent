"""Unit tests for retry strategies module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.retry_strategies import (
    RetryStrategy,
    StrategyResult,
    StrategyRegistry,
    FileNotFoundStrategy,
    PermissionDeniedStrategy,
    TimeoutRetryStrategy,
    ConnectionErrorStrategy,
    RateLimitStrategy,
    ValidationErrorStrategy,
    SyntaxErrorStrategy,
    get_retry_strategy,
    get_recovery_plan,
    retry_with_strategy,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FileNotFoundStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileNotFoundStrategy:
    """Tests for FileNotFoundStrategy."""

    @pytest.fixture
    def strategy(self):
        return FileNotFoundStrategy()

    def test_matches_not_found(self, strategy):
        """Should match 'not found' errors."""
        assert strategy.matches("File not found: config.yaml", "FileNotFoundError")

    def test_matches_no_such_file(self, strategy):
        """Should match 'no such file' errors."""
        assert strategy.matches("No such file or directory", "OSError")

    def test_matches_enoent(self, strategy):
        """Should match ENOENT errors."""
        assert strategy.matches("[Errno 2] ENOENT", "OSError")

    def test_no_match_other_error(self, strategy):
        """Should not match other errors."""
        assert not strategy.matches("Permission denied", "PermissionError")

    def test_apply_adds_prefix(self, strategy):
        """Should add ./ prefix on first attempt."""
        result = strategy.apply(
            "Not found",
            {"path": "config.yaml"},
            attempt=1
        )
        assert result.should_retry is True
        assert result.modified_args["path"] == "./config.yaml"

    def test_apply_exhausted(self, strategy):
        """Should stop after exhausting variations."""
        result = strategy.apply(
            "Not found",
            {"path": "config.yaml"},
            attempt=100
        )
        assert result.should_retry is False

    def test_apply_no_path(self, strategy):
        """Should not retry if no path argument."""
        result = strategy.apply(
            "Not found",
            {"something_else": "value"},
            attempt=1
        )
        assert result.should_retry is False


# ═══════════════════════════════════════════════════════════════════════════════
# PermissionDeniedStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPermissionDeniedStrategy:
    """Tests for PermissionDeniedStrategy."""

    @pytest.fixture
    def strategy(self):
        return PermissionDeniedStrategy()

    def test_matches_permission_denied(self, strategy):
        """Should match permission denied errors."""
        assert strategy.matches("Permission denied: /root/file", "PermissionError")

    def test_matches_access_denied(self, strategy):
        """Should match access denied errors."""
        assert strategy.matches("Access denied to resource", "OSError")

    def test_no_retry(self, strategy):
        """Should not retry permission errors."""
        result = strategy.apply(
            "Permission denied",
            {"path": "/root/file"},
            attempt=1
        )
        assert result.should_retry is False


# ═══════════════════════════════════════════════════════════════════════════════
# TimeoutRetryStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTimeoutRetryStrategy:
    """Tests for TimeoutRetryStrategy."""

    @pytest.fixture
    def strategy(self):
        return TimeoutRetryStrategy()

    def test_matches_timeout(self, strategy):
        """Should match timeout errors."""
        assert strategy.matches("Connection timed out", "TimeoutError")

    def test_matches_deadline(self, strategy):
        """Should match deadline exceeded."""
        assert strategy.matches("Deadline exceeded", "asyncio.TimeoutError")

    def test_apply_exponential_backoff(self, strategy):
        """Should use exponential backoff."""
        result1 = strategy.apply("Timeout", {}, attempt=1)
        result2 = strategy.apply("Timeout", {}, attempt=2)
        result3 = strategy.apply("Timeout", {}, attempt=3)

        assert result1.wait_seconds == 2
        assert result2.wait_seconds == 4
        assert result3.wait_seconds == 8

    def test_apply_max_wait(self, strategy):
        """Should cap wait time."""
        result = strategy.apply("Timeout", {}, attempt=10)
        assert result.wait_seconds <= 60

    def test_apply_increases_timeout(self, strategy):
        """Should increase timeout argument."""
        result = strategy.apply("Timeout", {"timeout": 30}, attempt=1)
        assert result.modified_args["timeout"] == 45


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectionErrorStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionErrorStrategy:
    """Tests for ConnectionErrorStrategy."""

    @pytest.fixture
    def strategy(self):
        return ConnectionErrorStrategy()

    def test_matches_refused(self, strategy):
        """Should match connection refused."""
        assert strategy.matches("Connection refused", "ConnectionRefusedError")

    def test_matches_reset(self, strategy):
        """Should match connection reset."""
        assert strategy.matches("Connection reset by peer", "ConnectionResetError")

    def test_apply_backoff(self, strategy):
        """Should use linear backoff."""
        result1 = strategy.apply("Connection refused", {}, attempt=1)
        result2 = strategy.apply("Connection refused", {}, attempt=2)

        assert result1.wait_seconds == 5
        assert result2.wait_seconds == 10


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimitStrategy:
    """Tests for RateLimitStrategy."""

    @pytest.fixture
    def strategy(self):
        return RateLimitStrategy()

    def test_matches_rate_limit(self, strategy):
        """Should match rate limit errors."""
        assert strategy.matches("Rate limit exceeded", "RateLimitError")

    def test_matches_429(self, strategy):
        """Should match 429 status."""
        assert strategy.matches("HTTP 429 Too Many Requests", "HTTPError")

    def test_matches_throttled(self, strategy):
        """Should match throttled errors."""
        assert strategy.matches("Request throttled", "APIError")

    def test_apply_extracts_retry_after(self, strategy):
        """Should extract retry-after from message."""
        result = strategy.apply(
            "Rate limit exceeded. Retry-After: 45",
            {},
            attempt=1
        )
        assert result.wait_seconds == 45

    def test_apply_default_wait(self, strategy):
        """Should use default wait if no retry-after."""
        result = strategy.apply(
            "Too many requests",
            {},
            attempt=1
        )
        assert result.wait_seconds == 30


# ═══════════════════════════════════════════════════════════════════════════════
# ValidationErrorStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidationErrorStrategy:
    """Tests for ValidationErrorStrategy."""

    @pytest.fixture
    def strategy(self):
        return ValidationErrorStrategy()

    def test_matches_invalid_argument(self, strategy):
        """Should match invalid argument errors."""
        assert strategy.matches("Invalid argument: 'path'", "ValueError")

    def test_matches_validation_error(self, strategy):
        """Should match validation errors."""
        assert strategy.matches("Validation error on field 'name'", "ValidationError")

    def test_apply_int_conversion(self, strategy):
        """Should convert string to int."""
        result = strategy.apply(
            "'count' must be an integer",
            {"count": "42"},
            attempt=1
        )
        assert result.should_retry is True
        assert result.modified_args["count"] == 42

    def test_apply_string_conversion(self, strategy):
        """Should convert to string."""
        result = strategy.apply(
            "'path' must be a string",
            {"path": 123},
            attempt=1
        )
        assert result.should_retry is True
        assert result.modified_args["path"] == "123"

    def test_apply_bool_conversion(self, strategy):
        """Should convert to boolean."""
        result = strategy.apply(
            "'enabled' must be a boolean",
            {"enabled": "true"},
            attempt=1
        )
        assert result.should_retry is True
        assert result.modified_args["enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# SyntaxErrorStrategy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyntaxErrorStrategy:
    """Tests for SyntaxErrorStrategy."""

    @pytest.fixture
    def strategy(self):
        return SyntaxErrorStrategy()

    def test_matches_syntax_error(self, strategy):
        """Should match syntax errors."""
        assert strategy.matches("SyntaxError: invalid syntax", "SyntaxError")

    def test_no_retry(self, strategy):
        """Should not retry syntax errors (needs LLM)."""
        result = strategy.apply(
            "SyntaxError: invalid syntax",
            {"code": "def foo("},
            attempt=1
        )
        assert result.should_retry is False


# ═══════════════════════════════════════════════════════════════════════════════
# StrategyRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStrategyRegistry:
    """Tests for StrategyRegistry."""

    @pytest.fixture
    def registry(self):
        return StrategyRegistry()

    def test_find_strategy_timeout(self, registry):
        """Should find timeout strategy."""
        strategy = registry.find_strategy("Connection timed out", "TimeoutError")
        assert isinstance(strategy, TimeoutRetryStrategy)

    def test_find_strategy_file_not_found(self, registry):
        """Should find file not found strategy."""
        strategy = registry.find_strategy("No such file", "FileNotFoundError")
        assert isinstance(strategy, FileNotFoundStrategy)

    def test_find_strategy_none(self, registry):
        """Should return None for unknown errors."""
        strategy = registry.find_strategy("Something random", "UnknownError")
        assert strategy is None

    def test_register_custom(self, registry):
        """Should allow custom strategy registration."""
        class CustomStrategy(RetryStrategy):
            name = "custom"
            description = "Custom"

            def matches(self, error_message, error_type):
                return "custom" in error_message.lower()

            def apply(self, error_message, original_args, attempt):
                return StrategyResult(
                    should_retry=True,
                    modified_args=original_args,
                    reason="Custom strategy",
                )

        registry.register(CustomStrategy())
        strategy = registry.find_strategy("Custom error occurred", "CustomError")
        assert strategy is not None
        assert strategy.name == "custom"

    def test_get_recovery_plan_with_strategy(self, registry):
        """Should return strategy-based plan."""
        plan = registry.get_recovery_plan(
            "Connection timed out",
            "TimeoutError",
            {"url": "http://example.com"},
            attempt=1
        )
        assert plan.should_retry is True
        assert plan.strategy_name == "timeout"

    def test_get_recovery_plan_generic(self, registry):
        """Should return generic plan for unknown errors."""
        plan = registry.get_recovery_plan(
            "Unknown error XYZ",
            "UnknownError",
            {},
            attempt=1
        )
        assert plan.should_retry is True
        assert "generic" in plan.reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Function Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_retry_strategy(self):
        """Should find strategy via convenience function."""
        strategy = get_retry_strategy("Rate limit exceeded", "RateLimitError")
        assert isinstance(strategy, RateLimitStrategy)

    def test_get_recovery_plan(self):
        """Should get plan via convenience function."""
        plan = get_recovery_plan(
            "Connection refused",
            "ConnectionRefusedError",
            {"host": "localhost"},
            attempt=1
        )
        assert plan.should_retry is True

    @pytest.mark.asyncio
    async def test_retry_with_strategy_success(self):
        """Should succeed after retries."""
        call_count = 0

        async def flaky_func(arg):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary network error")
            return "success"

        result = await retry_with_strategy(
            flaky_func,
            {"arg": "value"},
            max_attempts=3
        )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_strategy_failure(self):
        """Should raise after max attempts."""
        async def always_fails(arg):
            raise Exception("Permanent error")

        with pytest.raises(Exception, match="Permanent error"):
            await retry_with_strategy(
                always_fails,
                {"arg": "value"},
                max_attempts=3
            )
