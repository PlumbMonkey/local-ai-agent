"""Retry strategies for autonomous agent error recovery.

This module provides reusable patterns for recovering from common errors:
- File path corrections
- Network/timeout retries
- Permission escalation
- Syntax error fixes
- API rate limit handling
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Base Strategy
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StrategyResult:
    """Result of applying a retry strategy."""

    should_retry: bool
    modified_args: Dict[str, Any]
    wait_seconds: float = 0.0
    reason: str = ""
    strategy_name: str = ""


class RetryStrategy(ABC):
    """Base class for retry strategies."""

    name: str = "base"
    description: str = "Base retry strategy"

    @abstractmethod
    def matches(self, error_message: str, error_type: str) -> bool:
        """Check if this strategy applies to the error."""
        pass

    @abstractmethod
    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        """Apply the strategy to modify arguments for retry."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# File Path Strategies
# ═══════════════════════════════════════════════════════════════════════════════


class FileNotFoundStrategy(RetryStrategy):
    """Handle file not found errors by trying path variations."""

    name = "file_not_found"
    description = "Try alternative file paths when file not found"

    PATH_VARIATIONS = [
        lambda p: f"./{p}",  # Add ./
        lambda p: p.lstrip("./"),  # Remove ./
        lambda p: p.replace("\\", "/"),  # Unix paths
        lambda p: p.replace("/", "\\"),  # Windows paths
        lambda p: p.lower(),  # Lowercase
        lambda p: f"src/{p}",  # Common source dir
        lambda p: f"lib/{p}",  # Common lib dir
    ]

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = [
            "no such file",
            "not found",
            "does not exist",
            "cannot find",
            "enoent",
        ]
        return any(p in error_message.lower() for p in patterns)

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        # Find path argument
        path_keys = ["path", "file", "file_path", "filepath", "source"]
        path = None
        path_key = None

        for key in path_keys:
            if key in original_args:
                path = original_args[key]
                path_key = key
                break

        if not path or not path_key:
            return StrategyResult(
                should_retry=False,
                modified_args=original_args,
                reason="No path argument found",
            )

        # Apply variation based on attempt number
        if attempt <= len(self.PATH_VARIATIONS):
            variation = self.PATH_VARIATIONS[attempt - 1]
            new_path = variation(path)
            modified = original_args.copy()
            modified[path_key] = new_path

            return StrategyResult(
                should_retry=True,
                modified_args=modified,
                reason=f"Trying path variation: {new_path}",
                strategy_name=self.name,
            )

        return StrategyResult(
            should_retry=False,
            modified_args=original_args,
            reason="Exhausted path variations",
        )


class PermissionDeniedStrategy(RetryStrategy):
    """Handle permission errors."""

    name = "permission_denied"
    description = "Handle permission denied errors"

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = ["permission denied", "access denied", "eacces", "eperm"]
        return any(p in error_message.lower() for p in patterns)

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        # Permission errors usually can't be retried without escalation
        # We can suggest but not auto-retry
        return StrategyResult(
            should_retry=False,
            modified_args=original_args,
            reason="Permission denied - manual intervention required",
            strategy_name=self.name,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Network Strategies
# ═══════════════════════════════════════════════════════════════════════════════


class TimeoutRetryStrategy(RetryStrategy):
    """Handle timeout errors with exponential backoff."""

    name = "timeout"
    description = "Retry timeouts with exponential backoff"

    MAX_WAIT = 60  # Maximum wait in seconds
    BASE_WAIT = 2  # Base wait time

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = ["timeout", "timed out", "deadline exceeded"]
        return any(p in error_message.lower() for p in patterns) or \
               error_type in ["TimeoutError", "asyncio.TimeoutError"]

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        # Exponential backoff
        wait = min(self.BASE_WAIT ** attempt, self.MAX_WAIT)

        # Increase timeout if specified in args
        modified = original_args.copy()
        if "timeout" in modified:
            modified["timeout"] = modified["timeout"] * 1.5

        return StrategyResult(
            should_retry=True,
            modified_args=modified,
            wait_seconds=wait,
            reason=f"Timeout - waiting {wait}s before retry",
            strategy_name=self.name,
        )


class ConnectionErrorStrategy(RetryStrategy):
    """Handle connection errors."""

    name = "connection_error"
    description = "Retry connection errors with backoff"

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = [
            "connection refused",
            "connection reset",
            "network unreachable",
            "name resolution",
            "dns",
        ]
        return any(p in error_message.lower() for p in patterns) or \
               error_type in ["ConnectionError", "ConnectionRefusedError"]

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        wait = min(5 * attempt, 30)

        return StrategyResult(
            should_retry=True,
            modified_args=original_args,
            wait_seconds=wait,
            reason=f"Connection error - waiting {wait}s before retry",
            strategy_name=self.name,
        )


class RateLimitStrategy(RetryStrategy):
    """Handle rate limit errors."""

    name = "rate_limit"
    description = "Handle API rate limits with backoff"

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = [
            "rate limit",
            "too many requests",
            "429",
            "quota exceeded",
            "throttled",
        ]
        return any(p in error_message.lower() for p in patterns)

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        # Try to extract retry-after from message
        retry_after = None
        match = re.search(r"retry.?after[:\s]+(\d+)", error_message.lower())
        if match:
            retry_after = int(match.group(1))

        wait = retry_after or min(30 * attempt, 120)

        return StrategyResult(
            should_retry=True,
            modified_args=original_args,
            wait_seconds=wait,
            reason=f"Rate limited - waiting {wait}s",
            strategy_name=self.name,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Syntax/Validation Strategies
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationErrorStrategy(RetryStrategy):
    """Handle validation/argument errors."""

    name = "validation_error"
    description = "Handle validation errors with argument correction"

    def matches(self, error_message: str, error_type: str) -> bool:
        patterns = [
            "invalid argument",
            "validation error",
            "bad request",
            "missing required",
            "type error",
        ]
        return any(p in error_message.lower() for p in patterns) or \
               error_type in ["ValueError", "TypeError", "ValidationError"]

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        modified = original_args.copy()

        # Try to extract the problematic field
        field_match = re.search(r"['\"]([\w_]+)['\"]", error_message)
        if field_match:
            field = field_match.group(1)

            # Common fixes
            if field in modified:
                value = modified[field]

                # String/int conversions
                if "integer" in error_message.lower() and isinstance(value, str):
                    try:
                        modified[field] = int(value)
                    except ValueError:
                        pass
                elif "string" in error_message.lower() and not isinstance(value, str):
                    modified[field] = str(value)

                # Boolean conversions
                if "boolean" in error_message.lower():
                    if value in ["true", "1", 1]:
                        modified[field] = True
                    elif value in ["false", "0", 0]:
                        modified[field] = False

        # Check if we made changes
        if modified != original_args:
            return StrategyResult(
                should_retry=True,
                modified_args=modified,
                reason=f"Applied type correction",
                strategy_name=self.name,
            )

        return StrategyResult(
            should_retry=False,
            modified_args=original_args,
            reason="Could not determine correction",
        )


class SyntaxErrorStrategy(RetryStrategy):
    """Handle syntax errors in generated code."""

    name = "syntax_error"
    description = "Handle syntax errors in code"

    def matches(self, error_message: str, error_type: str) -> bool:
        return error_type == "SyntaxError" or "syntaxerror" in error_message.lower()

    def apply(
        self,
        error_message: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        # Syntax errors in generated code need LLM intervention
        # This strategy mainly identifies them
        return StrategyResult(
            should_retry=False,  # Needs LLM fix
            modified_args=original_args,
            reason="Syntax error requires code regeneration",
            strategy_name=self.name,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy Registry
# ═══════════════════════════════════════════════════════════════════════════════


class StrategyRegistry:
    """Registry of all retry strategies."""

    def __init__(self):
        self._strategies: List[RetryStrategy] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register default strategies."""
        self._strategies = [
            FileNotFoundStrategy(),
            PermissionDeniedStrategy(),
            TimeoutRetryStrategy(),
            ConnectionErrorStrategy(),
            RateLimitStrategy(),
            ValidationErrorStrategy(),
            SyntaxErrorStrategy(),
        ]

    def register(self, strategy: RetryStrategy):
        """Register a custom strategy."""
        self._strategies.append(strategy)

    def find_strategy(
        self, error_message: str, error_type: str
    ) -> Optional[RetryStrategy]:
        """Find matching strategy for an error."""
        for strategy in self._strategies:
            if strategy.matches(error_message, error_type):
                return strategy
        return None

    def get_recovery_plan(
        self,
        error_message: str,
        error_type: str,
        original_args: Dict[str, Any],
        attempt: int,
    ) -> StrategyResult:
        """Get recovery plan for an error."""
        strategy = self.find_strategy(error_message, error_type)

        if strategy:
            result = strategy.apply(error_message, original_args, attempt)
            return result

        # No matching strategy
        return StrategyResult(
            should_retry=attempt < 3,  # Generic retry for unknown errors
            modified_args=original_args,
            wait_seconds=2 ** attempt,
            reason="No specific strategy, generic retry",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════


# Global registry
_default_registry = StrategyRegistry()


def get_retry_strategy(
    error_message: str,
    error_type: str = "",
) -> Optional[RetryStrategy]:
    """Get a retry strategy for an error."""
    return _default_registry.find_strategy(error_message, error_type)


def get_recovery_plan(
    error_message: str,
    error_type: str,
    original_args: Dict[str, Any],
    attempt: int = 1,
) -> StrategyResult:
    """Get a recovery plan for an error."""
    return _default_registry.get_recovery_plan(
        error_message, error_type, original_args, attempt
    )


async def retry_with_strategy(
    func: Callable,
    args: Dict[str, Any],
    max_attempts: int = 3,
) -> Any:
    """
    Execute a function with automatic retry using strategies.

    Args:
        func: Async function to call
        args: Arguments to pass
        max_attempts: Maximum retry attempts

    Returns:
        Function result or raises last error
    """
    last_error = None
    current_args = args.copy()

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(**current_args)
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            error_message = str(e)

            logger.warning(f"Attempt {attempt} failed: {error_message}")

            plan = get_recovery_plan(
                error_message, error_type, current_args, attempt
            )

            if not plan.should_retry:
                logger.info(f"Strategy says don't retry: {plan.reason}")
                break

            if plan.wait_seconds > 0:
                logger.info(f"Waiting {plan.wait_seconds}s before retry")
                await asyncio.sleep(plan.wait_seconds)

            current_args = plan.modified_args
            logger.info(f"Retrying with strategy: {plan.strategy_name}")

    raise last_error
