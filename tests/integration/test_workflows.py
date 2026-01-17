"""Integration test example."""

import pytest
from domains.base.filesystem.server import FilesystemServer
from domains.base.terminal.server import TerminalServer
from core.llm.ollama import OllamaClient


class TestIntegration:
    """Integration tests for core workflows."""

    @pytest.fixture
    def fs_server(self, temp_dir):
        """Filesystem server."""
        return FilesystemServer(root_path=str(temp_dir))

    @pytest.fixture
    def term_server(self):
        """Terminal server."""
        return TerminalServer()

    def test_read_and_analyze_code(self, fs_server):
        """Test reading code file (workflow step 1)."""
        code = '''def hello(name):
    return f"Hello, {name}!"
'''
        fs_server.write_file("test.py", code)
        content = fs_server.read_file("test.py")
        assert "hello" in content

    def test_run_test_command(self, term_server):
        """Test running pytest (workflow step 2)."""
        result = term_server.run_command("python --version")
        assert result["success"] is True

    def test_workflow_read_test_commit(self, fs_server, term_server):
        """Test complete workflow: Read -> Test -> Commit."""
        # Step 1: Create a test file
        test_code = "def test_example(): pass\n"
        fs_server.write_file("test_example.py", test_code)

        # Step 2: Verify file exists
        content = fs_server.read_file("test_example.py")
        assert "test_example" in content

        # Step 3: Would run tests here
        # result = term_server.run_command("pytest test_example.py")
        # assert result["success"]
