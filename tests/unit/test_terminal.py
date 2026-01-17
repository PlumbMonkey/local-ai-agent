"""Tests for TerminalServer."""

import pytest
from domains.base.terminal.server import TerminalServer


class TestTerminalServer:
    """Test TerminalServer functionality."""

    @pytest.fixture
    def server(self):
        """Create test server."""
        return TerminalServer(enable_dangerous=False)

    def test_safe_command(self, server):
        """Test execution of safe command."""
        result = server.run_command("python --version")
        assert result["success"] is True
        assert result["exit_code"] == 0

    def test_unsafe_command_blocked(self, server):
        """Test that unsafe commands are blocked."""
        result = server.run_command("rm -rf /")
        assert result["success"] is False
        assert "not whitelisted" in result["stderr"]

    def test_dangerous_mode(self):
        """Test dangerous mode allows any command."""
        server = TerminalServer(enable_dangerous=True)
        result = server.run_command("echo test")
        assert result["success"] is True

    def test_command_timeout(self, server):
        """Test command timeout handling."""
        result = server.run_command("sleep 100")
        assert result["success"] is False
        assert result["exit_code"] == 124  # Timeout exit code
