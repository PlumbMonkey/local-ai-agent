"""Tests for MCP Phase 3 hardening modules."""

import asyncio
import json
import pytest
import time
from typing import Any

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidator:
    """Test schema validation."""

    def test_valid_required_fields(self):
        """Test validation passes with all required fields."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }

        result = validator.validate(schema, {"name": "Alice", "age": 30})
        assert result.valid
        assert len(result.errors) == 0

    def test_missing_required_field(self):
        """Test validation fails on missing required field."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

        result = validator.validate(schema, {})
        assert not result.valid
        assert "name" in result.errors[0]

    def test_wrong_type(self):
        """Test validation fails on wrong type."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
        }

        result = validator.validate(schema, {"age": "not a number"})
        assert not result.valid
        assert "type" in result.errors[0].lower()

    def test_string_constraints(self):
        """Test string length constraints."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 2, "maxLength": 10}
            },
        }

        # Too short
        result = validator.validate(schema, {"name": "a"})
        assert not result.valid

        # Too long
        result = validator.validate(schema, {"name": "a" * 20})
        assert not result.valid

        # Just right
        result = validator.validate(schema, {"name": "Alice"})
        assert result.valid

    def test_number_constraints(self):
        """Test number min/max constraints."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 0, "maximum": 100}},
        }

        result = validator.validate(schema, {"count": -1})
        assert not result.valid

        result = validator.validate(schema, {"count": 101})
        assert not result.valid

        result = validator.validate(schema, {"count": 50})
        assert result.valid

    def test_enum_validation(self):
        """Test enum constraint."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "inactive"]}},
        }

        result = validator.validate(schema, {"status": "unknown"})
        assert not result.valid

        result = validator.validate(schema, {"status": "active"})
        assert result.valid

    def test_array_validation(self):
        """Test array constraints."""
        from core.mcp.validation import SchemaValidator

        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 3,
                }
            },
        }

        result = validator.validate(schema, {"items": []})
        assert not result.valid

        result = validator.validate(schema, {"items": ["a", "b", "c", "d"]})
        assert not result.valid

        result = validator.validate(schema, {"items": ["a", "b"]})
        assert result.valid


class TestRequestValidator:
    """Test JSON-RPC request validation."""

    def test_valid_request(self):
        """Test valid request passes."""
        from core.mcp.validation import RequestValidator

        validator = RequestValidator()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        result = validator.validate_request(request)
        assert result.valid

    def test_missing_jsonrpc_version(self):
        """Test missing jsonrpc version fails."""
        from core.mcp.validation import RequestValidator

        validator = RequestValidator()
        request = {"id": 1, "method": "tools/list"}

        result = validator.validate_request(request)
        assert not result.valid

    def test_missing_method(self):
        """Test missing method fails."""
        from core.mcp.validation import RequestValidator

        validator = RequestValidator()
        request = {"jsonrpc": "2.0", "id": 1}

        result = validator.validate_request(request)
        assert not result.valid


# ═══════════════════════════════════════════════════════════════════════════════
# Rate Limiting Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimiter:
    """Test rate limiting."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        """Test requests within limit are allowed."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(
            requests_per_second=10,
            burst_capacity=5,
            enabled=True,
        )
        limiter = RateLimiter(config)

        # First few requests should be allowed
        for _ in range(3):
            allowed, _ = await limiter.check_limit("client1")
            assert allowed
            await limiter.consume("client1")

    @pytest.mark.asyncio
    async def test_blocks_when_exceeded(self):
        """Test requests are blocked when limit exceeded."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(
            requests_per_second=1,
            burst_capacity=2,
            cooldown_seconds=0.5,
            enabled=True,
        )
        limiter = RateLimiter(config)

        # Use up burst capacity
        for _ in range(2):
            await limiter.check_limit("client1")
            await limiter.consume("client1")

        # Next request should be blocked
        allowed, retry_after = await limiter.check_limit("client1")
        assert not allowed
        assert retry_after is not None

    @pytest.mark.asyncio
    async def test_disabled_limiter(self):
        """Test disabled limiter allows all."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(config)

        for _ in range(100):
            allowed, _ = await limiter.check_limit("client1")
            assert allowed

    @pytest.mark.asyncio
    async def test_per_client_limits(self):
        """Test limits are per-client."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(burst_capacity=2, enabled=True)
        limiter = RateLimiter(config)

        # Client 1 uses capacity
        for _ in range(2):
            await limiter.consume("client1")

        # Client 2 should still have capacity
        allowed, _ = await limiter.check_limit("client2")
        assert allowed

    @pytest.mark.asyncio
    async def test_acquire_waits(self):
        """Test acquire waits for capacity."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(
            requests_per_second=10,
            burst_capacity=1,
            cooldown_seconds=0.1,
            enabled=True,
        )
        limiter = RateLimiter(config)

        # Use capacity
        await limiter.acquire("client1")

        # Next acquire should wait but succeed
        start = time.time()
        acquired = await limiter.acquire("client1", timeout=1.0)
        duration = time.time() - start

        assert acquired
        assert duration >= 0.05  # Some wait occurred

    def test_get_stats(self):
        """Test getting rate limit stats."""
        from core.mcp.rate_limit import RateLimiter, RateLimitConfig

        config = RateLimitConfig(burst_capacity=10)
        limiter = RateLimiter(config)

        stats = limiter.get_stats("unknown_client")
        assert stats["tokens"] == 10
        assert stats["request_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Security Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthContext:
    """Test authentication context."""

    def test_has_permission(self):
        """Test permission checking."""
        from core.mcp.security import AuthContext, Permission, ROLE_USER

        context = AuthContext(
            client_id="test",
            authenticated=True,
            role=ROLE_USER,
        )

        assert context.has_permission(Permission.TOOLS_LIST)
        assert context.has_permission(Permission.TOOLS_CALL)
        assert not context.has_permission(Permission.ADMIN_CONFIG)

    def test_unauthenticated_no_permissions(self):
        """Test unauthenticated has no permissions."""
        from core.mcp.security import AuthContext, Permission

        context = AuthContext(client_id="test", authenticated=False)

        assert not context.has_permission(Permission.TOOLS_LIST)

    def test_can_call_tool_with_whitelist(self):
        """Test tool whitelist enforcement."""
        from core.mcp.security import AuthContext, Permission, Role

        role = Role(
            name="limited",
            permissions={Permission.TOOLS_CALL},
            tool_whitelist={"allowed_tool"},
        )
        context = AuthContext(client_id="test", authenticated=True, role=role)

        assert context.can_call_tool("allowed_tool")
        assert not context.can_call_tool("other_tool")

    def test_can_call_tool_with_blacklist(self):
        """Test tool blacklist enforcement."""
        from core.mcp.security import AuthContext, Permission, Role

        role = Role(
            name="limited",
            permissions={Permission.TOOLS_CALL},
            tool_blacklist={"dangerous_tool"},
        )
        context = AuthContext(client_id="test", authenticated=True, role=role)

        assert context.can_call_tool("safe_tool")
        assert not context.can_call_tool("dangerous_tool")


class TestTokenAuthProvider:
    """Test token authentication."""

    @pytest.mark.asyncio
    async def test_valid_token(self):
        """Test authentication with valid token."""
        from core.mcp.security import TokenAuthProvider, ROLE_USER

        provider = TokenAuthProvider()
        token = provider.generate_token(ROLE_USER)

        context = await provider.authenticate({"token": token})
        assert context is not None
        assert context.authenticated
        assert context.role.name == "user"

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test authentication with invalid token."""
        from core.mcp.security import TokenAuthProvider

        provider = TokenAuthProvider()

        context = await provider.authenticate({"token": "invalid"})
        assert context is None

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        """Test token revocation."""
        from core.mcp.security import TokenAuthProvider, ROLE_USER

        provider = TokenAuthProvider()
        token = provider.generate_token(ROLE_USER)

        # Token works before revocation
        context = await provider.authenticate({"token": token})
        assert context is not None

        # Revoke and verify
        provider.revoke_token(token)
        context = await provider.authenticate({"token": token})
        assert context is None


class TestSecurityMiddleware:
    """Test security middleware."""

    @pytest.mark.asyncio
    async def test_no_auth_provider(self):
        """Test NoAuthProvider grants access."""
        from core.mcp.security import SecurityMiddleware, NoAuthProvider, Permission

        middleware = SecurityMiddleware(NoAuthProvider())

        context = await middleware.authenticate({"client_id": "test"})
        assert context.authenticated
        assert middleware.authorize(context, Permission.TOOLS_CALL)

    @pytest.mark.asyncio
    async def test_authorization_denied(self):
        """Test authorization denial."""
        from core.mcp.security import (
            SecurityMiddleware,
            NoAuthProvider,
            ROLE_READONLY,
            Permission,
        )

        middleware = SecurityMiddleware(NoAuthProvider(default_role=ROLE_READONLY))

        context = await middleware.authenticate({"client_id": "test"})

        # Read-only can list but not call
        assert middleware.authorize(context, Permission.TOOLS_LIST)
        assert not middleware.authorize(context, Permission.TOOLS_CALL)


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetricsCollector:
    """Test metrics collection."""

    def test_counter_increment(self):
        """Test counter increment."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()
        metrics.increment("test_counter")
        metrics.increment("test_counter")

        assert metrics.get_counter("test_counter") == 2

    def test_counter_with_labels(self):
        """Test counter with labels."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()
        metrics.increment("requests", labels={"method": "tools/list"})
        metrics.increment("requests", labels={"method": "tools/call"})

        assert metrics.get_counter("requests", labels={"method": "tools/list"}) == 1
        assert metrics.get_counter("requests", labels={"method": "tools/call"}) == 1

    def test_gauge_set(self):
        """Test gauge setting."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()
        metrics.set_gauge("active_connections", 5)
        metrics.set_gauge("active_connections", 3)

        assert metrics.get_gauge("active_connections") == 3

    def test_histogram_observe(self):
        """Test histogram observations."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()

        for duration in [0.01, 0.05, 0.1, 0.5, 1.0]:
            metrics.observe("latency", duration)

        hist = metrics.get_histogram("latency")
        assert hist is not None
        assert hist.count == 5
        assert 0.3 < hist.mean < 0.4  # Average of the values

    @pytest.mark.asyncio
    async def test_record_request(self):
        """Test request recording."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()
        await metrics.record_request("tools/list", 0.1, success=True)
        await metrics.record_request("tools/list", 0.2, success=True)
        await metrics.record_request("tools/call", 0.5, success=False)

        assert metrics.get_counter("mcp_requests_total", {"method": "tools/list"}) == 2
        assert metrics.get_counter("mcp_requests_error", {"method": "tools/call"}) == 1

    def test_get_stats(self):
        """Test stats summary."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()

        stats = metrics.get_stats()
        assert "uptime_seconds" in stats
        assert "total_requests" in stats
        assert "error_rate" in stats

    def test_reset(self):
        """Test metrics reset."""
        from core.mcp.metrics import MetricsCollector

        metrics = MetricsCollector()
        metrics.increment("test")
        metrics.reset()

        assert metrics.get_counter("test") == 0


class TestHistogram:
    """Test histogram implementation."""

    def test_percentiles(self):
        """Test percentile calculation."""
        from core.mcp.metrics import Histogram

        hist = Histogram()

        # Add values that should distribute across buckets
        for v in [0.001, 0.01, 0.05, 0.1, 0.5, 1.0]:
            hist.observe(v)

        p50 = hist.get_percentile(50)
        p99 = hist.get_percentile(99)

        assert p50 < p99

    def test_mean_calculation(self):
        """Test mean calculation."""
        from core.mcp.metrics import Histogram

        hist = Histogram()
        hist.observe(1.0)
        hist.observe(2.0)
        hist.observe(3.0)

        assert hist.mean == 2.0
        assert hist.count == 3
        assert hist.sum == 6.0


# ═══════════════════════════════════════════════════════════════════════════════
# Hardened Server Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHardenedServer:
    """Test hardened MCP server."""

    @pytest.fixture
    def hardened_server(self):
        """Create a hardened server for testing."""
        from core.mcp.hardened import HardenedMCPServer
        from core.mcp.rate_limit import RateLimitConfig

        server = HardenedMCPServer(
            name="test-hardened",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(burst_capacity=10, enabled=True),
            validate_inputs=True,
            request_timeout=5.0,
        )

        # Register a test tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        server.register_tool(
            name="greet",
            description="Greet someone",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string", "minLength": 1}},
                "required": ["name"],
            },
            handler=greet,
        )

        return server

    @pytest.mark.asyncio
    async def test_valid_tool_call(self, hardened_server):
        """Test valid tool call succeeds."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="greet", arguments={"name": "World"})
        result = await hardened_server.call_tool(tool_call)

        assert not result.is_error
        assert "Hello, World!" in result.content[0].text

    @pytest.mark.asyncio
    async def test_invalid_tool_input(self, hardened_server):
        """Test invalid tool input is rejected."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="greet", arguments={"name": ""})
        result = await hardened_server.call_tool(tool_call)

        assert result.is_error
        assert "validation" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_missing_required_field(self, hardened_server):
        """Test missing required field is rejected."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="greet", arguments={})
        result = await hardened_server.call_tool(tool_call)

        assert result.is_error
        assert "required" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_health_endpoint(self, hardened_server):
        """Test health endpoint."""
        health = hardened_server.get_health()

        assert health["status"] == "healthy"
        assert health["server"] == "test-hardened"
        assert "metrics" in health

    @pytest.mark.asyncio
    async def test_rate_limit_response(self, hardened_server):
        """Test rate limit generates proper response."""
        from core.mcp.rate_limit import RateLimitConfig

        # Create server with very low limit
        from core.mcp.hardened import HardenedMCPServer

        server = HardenedMCPServer(
            name="rate-limited",
            rate_limit_config=RateLimitConfig(burst_capacity=1, enabled=True),
        )

        # First request OK
        await server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            client_id="test",
        )

        # Second should hit rate limit
        response = await server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            client_id="test",
        )

        data = json.loads(response)
        assert data["error"]["code"] == -32029
        assert "rate limit" in data["error"]["message"].lower()
