"""Terminal MCP Server."""

import logging
import subprocess
from typing import Optional

from core.mcp.server import MCPServer

logger = logging.getLogger(__name__)


class TerminalServer(MCPServer):
    """MCP Server for shell command execution."""

    def __init__(self, enable_dangerous: bool = False):
        """
        Initialize terminal server.

        Args:
            enable_dangerous: Allow execution of potentially dangerous commands
        """
        super().__init__("terminal")
        self.enable_dangerous = enable_dangerous
        self._whitelist = {
            "ls", "dir", "pwd", "cd", "cat", "grep", "python",
            "pip", "git", "npm", "node", "pytest", "make",
        }

        self.register_tool(
            name="run_command",
            description="Execute a shell command",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory",
                    },
                },
                "required": ["command"],
            },
            handler=self.run_command,
        )

    def _is_safe(self, command: str) -> bool:
        """Check if command is safe to execute."""
        if self.enable_dangerous:
            return True

        # Check first word of command
        first_word = command.split()[0].split("/")[-1]
        return first_word in self._whitelist

    def run_command(self, command: str, cwd: Optional[str] = None) -> dict:
        """
        Execute a shell command.

        Args:
            command: Command to execute
            cwd: Working directory

        Returns:
            Command output and exit code
        """
        try:
            if not self._is_safe(command):
                raise PermissionError(
                    f"Command not whitelisted: {command.split()[0]}"
                )

            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout: {command}")
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Command timed out",
                "success": False,
            }
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }
