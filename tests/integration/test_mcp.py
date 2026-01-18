"""Integration tests for MCP Server hardening."""

import asyncio
import json
import pytest
from pathlib import Path
from typing import Any

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_root(tmp_path):
    """Create a temporary root directory for filesystem tests."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, MCP!")
    return tmp_path


@pytest.fixture
def mcp_server():
    """Create a basic MCP server for testing."""
    from core.mcp.server import MCPServer

    server = MCPServer(
        name="test-server",
        version="1.0.0",
        instructions="Test server for unit tests",
    )

    # Register a simple tool
    def echo(message: str) -> str:
        return f"Echo: {message}"

    server.register_tool(
        name="echo",
        description="Echo a message back",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        handler=echo,
    )

    # Register an async tool
    async def async_echo(message: str, delay: float = 0) -> str:
        await asyncio.sleep(delay)
        return f"Async Echo: {message}"

    server.register_tool(
        name="async_echo",
        description="Echo a message asynchronously",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "delay": {"type": "number"},
            },
            "required": ["message"],
        },
        handler=async_echo,
    )

    return server


@pytest.fixture
def filesystem_server(temp_root):
    """Create a filesystem server for testing."""
    from domains.base.filesystem.server import FilesystemServer

    return FilesystemServer(root_path=str(temp_root))


@pytest.fixture
def terminal_server():
    """Create a terminal server for testing."""
    from domains.base.terminal.server import TerminalServer

    return TerminalServer(enable_dangerous=False)


@pytest.fixture
def registry(filesystem_server, terminal_server):
    """Create a registry with domain servers."""
    from core.mcp.registry import MCPServerRegistry

    registry = MCPServerRegistry(name="test-registry", version="1.0.0")
    registry.register_server(filesystem_server, prefix="fs")
    registry.register_server(terminal_server, prefix="terminal")
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# Protocol Type Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProtocolTypes:
    """Test MCP protocol types."""

    def test_json_rpc_request(self):
        """Test JSON-RPC request serialization."""
        from core.mcp.protocol import JSONRPCRequest

        request = JSONRPCRequest(
            id=1,
            method="tools/list",
            params={"cursor": None},
        )

        data = request.model_dump(exclude_none=True)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["method"] == "tools/list"

    def test_json_rpc_response(self):
        """Test JSON-RPC response serialization."""
        from core.mcp.protocol import JSONRPCResponse, JSONRPCError

        # Success response
        response = JSONRPCResponse(id=1, result={"tools": []})
        data = response.model_dump(exclude_none=True)
        assert data["result"] == {"tools": []}
        assert "error" not in data

        # Error response
        error_response = JSONRPCResponse(
            id=1,
            error=JSONRPCError(code=-32601, message="Method not found"),
        )
        data = error_response.model_dump(exclude_none=True)
        assert data["error"]["code"] == -32601

    def test_tool_definition(self):
        """Test tool definition with aliases."""
        from core.mcp.types import Tool

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )

        # Check alias works
        data = tool.model_dump(by_alias=True)
        assert "inputSchema" in data

    def test_tool_result_content(self):
        """Test tool result with content format."""
        from core.mcp.types import ToolResult, ToolContent

        result = ToolResult(
            content=[
                ToolContent(type="text", text="Hello"),
                ToolContent(type="text", text="World"),
            ],
            is_error=False,
        )

        assert len(result.content) == 2
        assert result.content[0].text == "Hello"

    def test_initialize_result(self):
        """Test initialization result structure."""
        from core.mcp.protocol import (
            InitializeResult,
            ServerCapabilities,
            ServerInfo,
            MCP_VERSION,
        )

        result = InitializeResult(
            protocolVersion=MCP_VERSION,
            capabilities=ServerCapabilities(
                tools={"listChanged": True},
            ),
            serverInfo=ServerInfo(name="test", version="1.0"),
        )

        data = result.model_dump(exclude_none=True)
        assert data["protocolVersion"] == MCP_VERSION
        assert data["serverInfo"]["name"] == "test"


# ═══════════════════════════════════════════════════════════════════════════════
# Server Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServer:
    """Test MCP server functionality."""

    def test_tool_registration(self, mcp_server):
        """Test tool registration."""
        tools = mcp_server.list_tools()
        assert len(tools) == 2
        assert any(t.name == "echo" for t in tools)
        assert any(t.name == "async_echo" for t in tools)

    @pytest.mark.asyncio
    async def test_sync_tool_call(self, mcp_server):
        """Test synchronous tool call."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="echo", arguments={"message": "test"})
        result = await mcp_server.call_tool(tool_call)

        assert not result.is_error
        assert result.content[0].text == "Echo: test"

    @pytest.mark.asyncio
    async def test_async_tool_call(self, mcp_server):
        """Test asynchronous tool call."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="async_echo",
            arguments={"message": "async test", "delay": 0.01},
        )
        result = await mcp_server.call_tool(tool_call)

        assert not result.is_error
        assert result.content[0].text == "Async Echo: async test"

    @pytest.mark.asyncio
    async def test_tool_not_found(self, mcp_server):
        """Test calling non-existent tool."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="nonexistent", arguments={})
        result = await mcp_server.call_tool(tool_call)

        assert result.is_error
        assert "not found" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_json_rpc_initialize(self, mcp_server):
        """Test JSON-RPC initialize request."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }

        response = await mcp_server.handle_message(message)
        data = json.loads(response)

        assert data["id"] == 1
        assert "result" in data
        assert data["result"]["serverInfo"]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_json_rpc_tools_list(self, mcp_server):
        """Test JSON-RPC tools/list request."""
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = await mcp_server.handle_message(message)
        data = json.loads(response)

        assert data["id"] == 2
        assert len(data["result"]["tools"]) == 2

    @pytest.mark.asyncio
    async def test_json_rpc_tools_call(self, mcp_server):
        """Test JSON-RPC tools/call request."""
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "JSON-RPC test"},
            },
        }

        response = await mcp_server.handle_message(message)
        data = json.loads(response)

        assert data["id"] == 3
        assert data["result"]["content"][0]["text"] == "Echo: JSON-RPC test"

    @pytest.mark.asyncio
    async def test_json_rpc_notification(self, mcp_server):
        """Test JSON-RPC notification (no response)."""
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }

        response = await mcp_server.handle_message(message)
        assert response is None

    @pytest.mark.asyncio
    async def test_json_rpc_method_not_found(self, mcp_server):
        """Test JSON-RPC method not found error."""
        message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "unknown/method",
            "params": {},
        }

        response = await mcp_server.handle_message(message)
        data = json.loads(response)

        assert data["id"] == 4
        assert data["error"]["code"] == -32601

    def test_resource_registration(self, mcp_server):
        """Test resource registration."""
        mcp_server.register_resource(
            uri="file:///test.txt",
            name="Test File",
            description="A test file",
            mime_type="text/plain",
            handler=lambda: "Test content",
        )

        resources = mcp_server.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == "file:///test.txt"

    def test_prompt_registration(self, mcp_server):
        """Test prompt registration."""
        mcp_server.register_prompt(
            name="greeting",
            description="Generate a greeting",
            arguments=[{"name": "name", "required": True}],
        )

        prompts = mcp_server.list_prompts()
        assert len(prompts) == 1
        assert prompts[0].name == "greeting"


# ═══════════════════════════════════════════════════════════════════════════════
# Registry Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPRegistry:
    """Test MCP server registry."""

    def test_server_registration(self, registry):
        """Test server registration."""
        servers = registry.list_servers()
        assert "fs" in servers
        assert "terminal" in servers

    def test_aggregated_tools(self, registry):
        """Test aggregated tool listing."""
        tools = registry.list_tools()
        tool_names = [t.name for t in tools]

        assert any("fs.read_file" in name for name in tool_names)
        assert any("terminal.run_command" in name for name in tool_names)

    @pytest.mark.asyncio
    async def test_prefixed_tool_call(self, registry, temp_root):
        """Test calling tool with prefix."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="fs.read_file",
            arguments={"path": "test.txt"},
        )
        result = await registry.call_tool(tool_call)

        assert not result.is_error
        assert "Hello, MCP!" in result.content[0].text

    @pytest.mark.asyncio
    async def test_unprefixed_tool_call(self, registry, temp_root):
        """Test calling tool without prefix."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt"},
        )
        result = await registry.call_tool(tool_call)

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_registry_handle_message(self, registry):
        """Test registry JSON-RPC handling."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        response = await registry.handle_message(message)
        data = json.loads(response)

        assert len(data["result"]["tools"]) > 0

    def test_registry_stats(self, registry):
        """Test registry statistics."""
        stats = registry.stats()
        assert stats["servers"] == 2
        assert stats["tools"] > 0

    def test_server_unregistration(self, registry):
        """Test server unregistration."""
        registry.unregister_server("terminal")
        assert "terminal" not in registry.list_servers()

        # Tools should be removed too
        tools = registry.list_tools()
        assert not any("terminal" in t.name for t in tools)


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Server Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilesystemServer:
    """Test filesystem domain server."""

    @pytest.mark.asyncio
    async def test_read_file(self, filesystem_server, temp_root):
        """Test file reading."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(tool_name="read_file", arguments={"path": "test.txt"})
        result = await filesystem_server.call_tool(tool_call)

        assert not result.is_error
        assert "Hello, MCP!" in result.content[0].text

    @pytest.mark.asyncio
    async def test_write_file(self, filesystem_server, temp_root):
        """Test file writing."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="write_file",
            arguments={"path": "new.txt", "content": "New content"},
        )
        result = await filesystem_server.call_tool(tool_call)

        assert not result.is_error
        assert (temp_root / "new.txt").read_text() == "New content"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, filesystem_server, temp_root):
        """Test path traversal attack is blocked."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "../../../etc/passwd"},
        )
        result = await filesystem_server.call_tool(tool_call)

        assert result.is_error
        assert "outside root" in result.content[0].text.lower() or "error" in result.content[0].text.lower()


class TestTerminalServer:
    """Test terminal domain server."""

    @pytest.mark.asyncio
    async def test_whitelisted_command(self, terminal_server):
        """Test whitelisted command execution."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="run_command",
            arguments={"command": "python --version"},
        )
        result = await terminal_server.call_tool(tool_call)

        assert not result.is_error
        # Parse the JSON output
        output = json.loads(result.content[0].text)
        assert output["success"]

    @pytest.mark.asyncio
    async def test_non_whitelisted_blocked(self, terminal_server):
        """Test non-whitelisted command is blocked."""
        from core.mcp.types import ToolCall

        tool_call = ToolCall(
            tool_name="run_command",
            arguments={"command": "rm -rf /"},
        )
        result = await terminal_server.call_tool(tool_call)

        # Either error or blocked in output
        output_text = result.content[0].text
        assert result.is_error or "not whitelisted" in output_text.lower() or "error" in output_text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Transport Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSSETransport:
    """Test SSE transport."""

    @pytest.mark.asyncio
    async def test_client_creation(self):
        """Test SSE client creation."""
        from core.mcp.transport import SSETransport

        sse = SSETransport()
        queue = sse.create_client("test-client")

        assert "test-client" in sse._clients
        sse.remove_client("test-client")
        assert "test-client" not in sse._clients

    @pytest.mark.asyncio
    async def test_send_to_client(self):
        """Test sending events to client."""
        from core.mcp.transport import SSETransport

        sse = SSETransport()
        queue = sse.create_client("test-client")

        await sse.send("test-client", "progress", {"value": 50})

        message = await queue.get()
        assert message["event"] == "progress"
        assert '"value": 50' in message["data"]


# ═══════════════════════════════════════════════════════════════════════════════
# Protocol Compliance Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProtocolCompliance:
    """Test MCP protocol compliance."""

    def test_mcp_version(self):
        """Test MCP version constant."""
        from core.mcp.protocol import MCP_VERSION

        assert MCP_VERSION == "2024-11-05"

    def test_error_codes(self):
        """Test error code values."""
        from core.mcp.protocol import ErrorCode

        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.METHOD_NOT_FOUND == -32601
        assert ErrorCode.TOOL_NOT_FOUND == -32001

    def test_mcp_methods(self):
        """Test MCP method names."""
        from core.mcp.protocol import MCPMethod

        assert MCPMethod.INITIALIZE == "initialize"
        assert MCPMethod.TOOLS_LIST == "tools/list"
        assert MCPMethod.TOOLS_CALL == "tools/call"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mcp_server):
        """Test full MCP lifecycle: initialize -> use -> shutdown."""
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        response = await mcp_server.handle_message(init_msg)
        assert json.loads(response)["result"]["protocolVersion"]

        # Send initialized notification
        await mcp_server.handle_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

        # Use tools
        tools_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = await mcp_server.handle_message(tools_msg)
        assert len(json.loads(response)["result"]["tools"]) > 0

        # Shutdown
        shutdown_msg = {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}}
        response = await mcp_server.handle_message(shutdown_msg)
        assert json.loads(response)["id"] == 3
