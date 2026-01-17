"""Filesystem MCP Server."""

import logging
from pathlib import Path
from typing import Optional

from core.mcp.server import MCPServer

logger = logging.getLogger(__name__)


class FilesystemServer(MCPServer):
    """MCP Server for file system access."""

    def __init__(self, root_path: Optional[str] = None):
        """
        Initialize filesystem server.

        Args:
            root_path: Root directory for file operations (security boundary)
        """
        super().__init__("filesystem")
        self.root_path = Path(root_path or ".")

        # Register tools
        self.register_tool(
            name="read_file",
            description="Read contents of a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file relative to root",
                    },
                },
                "required": ["path"],
            },
            handler=self.read_file,
        )

        self.register_tool(
            name="write_file",
            description="Write contents to a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"},
                    "mode": {
                        "type": "string",
                        "enum": ["w", "a"],
                        "description": "Write mode (w=overwrite, a=append)",
                    },
                },
                "required": ["path", "content"],
            },
            handler=self.write_file,
        )

        self.register_tool(
            name="list_directory",
            description="List files in a directory",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path",
                    },
                },
                "required": ["path"],
            },
            handler=self.list_directory,
        )

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve path safely within root.

        Args:
            path: Path to resolve

        Returns:
            Absolute path
        """
        target = (self.root_path / path).resolve()

        # Security: ensure path is within root
        try:
            target.relative_to(self.root_path.resolve())
        except ValueError:
            raise ValueError(f"Path outside root: {path}")

        return target

    def read_file(self, path: str) -> str:
        """Read file contents."""
        try:
            full_path = self._resolve_path(path)
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not full_path.is_file():
                raise IsADirectoryError(f"Not a file: {path}")

            return full_path.read_text(encoding="utf-8")

        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            raise

    def write_file(self, path: str, content: str, mode: str = "w") -> str:
        """Write to file."""
        try:
            full_path = self._resolve_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "w":
                full_path.write_text(content, encoding="utf-8")
            elif mode == "a":
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                raise ValueError(f"Invalid mode: {mode}")

            logger.info(f"Wrote to file: {path}")
            return f"Successfully wrote to {path}"

        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            raise

    def list_directory(self, path: str) -> list[dict]:
        """List directory contents."""
        try:
            full_path = self._resolve_path(path)
            if not full_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            if not full_path.is_dir():
                raise NotADirectoryError(f"Not a directory: {path}")

            items = []
            for item in sorted(full_path.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })

            return items

        except Exception as e:
            logger.error(f"Failed to list directory: {e}")
            raise
