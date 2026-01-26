"""Rate limiting and throttling for MCP servers."""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Requests per window
    requests_per_minute: int = 60
    requests_per_second: int = 10

    # Burst capacity (token bucket)
    burst_capacity: int = 20

    # Per-tool limits (tool_name -> requests per minute)
    tool_limits: Dict[str, int] = field(default_factory=dict)

    # Cooldown after hitting limit (seconds)
    cooldown_seconds: float = 1.0

    # Enable/disable
    enabled: bool = True


@dataclass
class RateLimitState:
    """Current state of rate limiting for a client."""

    tokens: float = 0.0
    last_update: float = 0.0
    request_count: int = 0
    window_start: float = 0.0
    blocked_until: float = 0.0


class RateLimiter:
    """
    Token bucket rate limiter for MCP requests.

    Features:
    - Per-client rate limiting
    - Per-tool rate limiting
    - Burst handling with token bucket
    - Automatic cooldown
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._clients: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._tool_states: Dict[str, Dict[str, RateLimitState]] = defaultdict(
            lambda: defaultdict(RateLimitState)
        )
        self._lock = asyncio.Lock()

    def _refill_tokens(self, state: RateLimitState, now: float) -> None:
        """Refill tokens based on time elapsed."""
        if state.last_update == 0:
            state.tokens = self.config.burst_capacity
            state.last_update = now
            state.window_start = now
            return

        elapsed = now - state.last_update
        tokens_per_second = self.config.requests_per_second

        # Add tokens based on time elapsed
        state.tokens = min(
            self.config.burst_capacity,
            state.tokens + elapsed * tokens_per_second,
        )
        state.last_update = now

        # Reset window if needed
        if now - state.window_start >= 60:
            state.request_count = 0
            state.window_start = now

    async def check_limit(
        self,
        client_id: str,
        tool_name: Optional[str] = None,
    ) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed.

        Args:
            client_id: Unique client identifier
            tool_name: Optional tool being called

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        if not self.config.enabled:
            return True, None

        async with self._lock:
            now = time.time()
            state = self._clients[client_id]

            # Check if in cooldown
            if state.blocked_until > now:
                retry_after = state.blocked_until - now
                return False, retry_after

            # Refill tokens
            self._refill_tokens(state, now)

            # Check burst limit (token bucket)
            if state.tokens < 1:
                state.blocked_until = now + self.config.cooldown_seconds
                logger.warning(f"Rate limit exceeded for client {client_id} (burst)")
                return False, self.config.cooldown_seconds

            # Check per-minute limit
            if state.request_count >= self.config.requests_per_minute:
                retry_after = 60 - (now - state.window_start)
                logger.warning(f"Rate limit exceeded for client {client_id} (per-minute)")
                return False, max(retry_after, 0.1)

            # Check per-tool limit if applicable
            if tool_name and tool_name in self.config.tool_limits:
                tool_state = self._tool_states[client_id][tool_name]
                self._refill_tokens(tool_state, now)

                tool_limit = self.config.tool_limits[tool_name]
                if tool_state.request_count >= tool_limit:
                    retry_after = 60 - (now - tool_state.window_start)
                    logger.warning(
                        f"Tool rate limit exceeded for {tool_name} by client {client_id}"
                    )
                    return False, max(retry_after, 0.1)

            return True, None

    async def consume(
        self,
        client_id: str,
        tool_name: Optional[str] = None,
    ) -> None:
        """
        Consume a token for a request.

        Call this after check_limit returns True.
        """
        if not self.config.enabled:
            return

        async with self._lock:
            state = self._clients[client_id]
            state.tokens -= 1
            state.request_count += 1

            if tool_name:
                tool_state = self._tool_states[client_id][tool_name]
                tool_state.request_count += 1

    async def acquire(
        self,
        client_id: str,
        tool_name: Optional[str] = None,
        timeout: float = 30.0,
    ) -> bool:
        """
        Acquire permission to make a request, waiting if needed.

        Args:
            client_id: Unique client identifier
            tool_name: Optional tool being called
            timeout: Maximum time to wait

        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()

        while True:
            allowed, retry_after = await self.check_limit(client_id, tool_name)

            if allowed:
                await self.consume(client_id, tool_name)
                return True

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed + (retry_after or 0) > timeout:
                return False

            # Wait and retry
            wait_time = min(retry_after or 0.1, timeout - elapsed)
            await asyncio.sleep(wait_time)

    def get_stats(self, client_id: str) -> Dict:
        """Get rate limit stats for a client."""
        state = self._clients.get(client_id)
        if not state:
            return {"tokens": self.config.burst_capacity, "request_count": 0}

        return {
            "tokens": state.tokens,
            "request_count": state.request_count,
            "blocked_until": state.blocked_until if state.blocked_until > time.time() else None,
        }

    def reset(self, client_id: Optional[str] = None) -> None:
        """Reset rate limit state for a client or all clients."""
        if client_id:
            self._clients.pop(client_id, None)
            self._tool_states.pop(client_id, None)
        else:
            self._clients.clear()
            self._tool_states.clear()


# Default rate limiter instance
default_rate_limiter = RateLimiter()
