"""Tests for FilesystemServer."""

import pytest
from pathlib import Path
from domains.base.filesystem.server import FilesystemServer


class TestFilesystemServer:
    """Test FilesystemServer functionality."""

    @pytest.fixture
    def server(self, temp_dir):
        """Create test server."""
        return FilesystemServer(root_path=str(temp_dir))

    def test_read_file(self, server, temp_dir):
        """Test reading a file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        content = server.read_file("test.txt")
        assert content == "Hello, World!"

    def test_read_file_not_found(self, server):
        """Test reading non-existent file."""
        with pytest.raises(FileNotFoundError):
            server.read_file("nonexistent.txt")

    def test_write_file(self, server, temp_dir):
        """Test writing a file."""
        result = server.write_file("output.txt", "Test content")
        assert result == "Successfully wrote to output.txt"
        assert (temp_dir / "output.txt").read_text() == "Test content"

    def test_path_traversal_protection(self, server):
        """Test protection against path traversal."""
        with pytest.raises(ValueError):
            server.read_file("../etc/passwd")

    def test_list_directory(self, server, temp_dir):
        """Test listing directory contents."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        items = server.list_directory(".")
        names = {item["name"] for item in items}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names
