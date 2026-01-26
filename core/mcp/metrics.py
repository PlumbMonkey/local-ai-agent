"""Metrics and telemetry for MCP servers."""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """A single metric measurement."""

    name: str
    type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


class Histogram:
    """Histogram for tracking distributions."""

    # Default buckets (in seconds for timing)
    DEFAULT_BUCKETS = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def __init__(self, buckets: Optional[List[float]] = None):
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[float, int] = {b: 0 for b in self.buckets}
        self._counts[float("inf")] = 0
        self._sum: float = 0.0
        self._count: int = 0

    def observe(self, value: float) -> None:
        """Record an observation."""
        self._sum += value
        self._count += 1

        for bucket in self.buckets:
            if value <= bucket:
                self._counts[bucket] += 1

        self._counts[float("inf")] += 1

    def get_percentile(self, percentile: float) -> float:
        """Get approximate percentile value."""
        if self._count == 0:
            return 0.0

        target = percentile / 100.0 * self._count
        cumulative = 0

        for bucket in self.buckets:
            cumulative = self._counts[bucket]
            if cumulative >= target:
                return bucket

        return self.buckets[-1] if self.buckets else 0.0

    @property
    def mean(self) -> float:
        """Get mean value."""
        return self._sum / self._count if self._count > 0 else 0.0

    @property
    def count(self) -> int:
        """Get total count."""
        return self._count

    @property
    def sum(self) -> float:
        """Get sum of all values."""
        return self._sum


class MetricsCollector:
    """
    Collects and aggregates MCP server metrics.

    Tracks:
    - Request counts and rates
    - Tool call latencies
    - Error rates
    - Active connections
    """

    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, Histogram] = defaultdict(Histogram)
        self._start_time = time.time()
        self._lock = asyncio.Lock()

    def increment(self, name: str, value: int = 1, labels: Optional[Dict] = None) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        self._histograms[key].observe(value)

    def _make_key(self, name: str, labels: Optional[Dict] = None) -> str:
        """Create a unique key for metric + labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    async def record_request(
        self,
        method: str,
        duration: float,
        success: bool,
        client_id: Optional[str] = None,
    ) -> None:
        """Record a request metric."""
        async with self._lock:
            # Count
            self.increment("mcp_requests_total", labels={"method": method})

            if success:
                self.increment("mcp_requests_success", labels={"method": method})
            else:
                self.increment("mcp_requests_error", labels={"method": method})

            # Duration
            self.observe("mcp_request_duration_seconds", duration, labels={"method": method})

    async def record_tool_call(
        self,
        tool_name: str,
        duration: float,
        success: bool,
    ) -> None:
        """Record a tool call metric."""
        async with self._lock:
            self.increment("mcp_tool_calls_total", labels={"tool": tool_name})

            if success:
                self.increment("mcp_tool_calls_success", labels={"tool": tool_name})
            else:
                self.increment("mcp_tool_calls_error", labels={"tool": tool_name})

            self.observe("mcp_tool_duration_seconds", duration, labels={"tool": tool_name})

    def get_counter(self, name: str, labels: Optional[Dict] = None) -> int:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, labels: Optional[Dict] = None) -> float:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0.0)

    def get_histogram(self, name: str, labels: Optional[Dict] = None) -> Optional[Histogram]:
        """Get histogram."""
        key = self._make_key(name, labels)
        return self._histograms.get(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        uptime = time.time() - self._start_time

        # Calculate request rate
        total_requests = sum(
            v for k, v in self._counters.items() if k.startswith("mcp_requests_total")
        )
        request_rate = total_requests / uptime if uptime > 0 else 0

        # Calculate error rate
        total_errors = sum(
            v for k, v in self._counters.items() if k.startswith("mcp_requests_error")
        )
        error_rate = total_errors / total_requests if total_requests > 0 else 0

        # Get latency stats
        latency_hist = self._histograms.get("mcp_request_duration_seconds")
        latency_stats = {}
        if latency_hist:
            latency_stats = {
                "mean": latency_hist.mean,
                "p50": latency_hist.get_percentile(50),
                "p95": latency_hist.get_percentile(95),
                "p99": latency_hist.get_percentile(99),
            }

        return {
            "uptime_seconds": uptime,
            "total_requests": total_requests,
            "request_rate_per_second": request_rate,
            "error_rate": error_rate,
            "latency": latency_stats,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.time()


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(
        self,
        collector: MetricsCollector,
        method: str,
        client_id: Optional[str] = None,
    ):
        self.collector = collector
        self.method = method
        self.client_id = client_id
        self.start_time: float = 0
        self.success = True

    async def __aenter__(self) -> "RequestTimer":
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = time.time() - self.start_time
        success = exc_type is None and self.success
        await self.collector.record_request(
            self.method, duration, success, self.client_id
        )

    def mark_failed(self) -> None:
        """Mark the request as failed."""
        self.success = False


class ToolTimer:
    """Context manager for timing tool calls."""

    def __init__(self, collector: MetricsCollector, tool_name: str):
        self.collector = collector
        self.tool_name = tool_name
        self.start_time: float = 0
        self.success = True

    async def __aenter__(self) -> "ToolTimer":
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = time.time() - self.start_time
        success = exc_type is None and self.success
        await self.collector.record_tool_call(self.tool_name, duration, success)

    def mark_failed(self) -> None:
        """Mark the tool call as failed."""
        self.success = False


# Default metrics collector
default_metrics = MetricsCollector()
