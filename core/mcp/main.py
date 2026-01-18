#!/usr/bin/env python
"""
MCP Server Runner

Start the Local AI Agent MCP server with all domain servers registered.

Usage:
    # HTTP mode (default)
    python -m core.mcp.main --http --port 8080

    # WebSocket mode
    python -m core.mcp.main --websocket --port 8765

    # Stdio mode (for VS Code integration)
    python -m core.mcp.main --stdio

    # Combined HTTP + WebSocket
    python -m core.mcp.main --http --websocket
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.mcp.http_server import MCPHttpServer
from core.mcp.registry import MCPServerRegistry
from core.mcp.transport import StdioTransport, WebSocketTransport

# Import domain servers
from domains.base.filesystem.server import FilesystemServer
from domains.base.terminal.server import TerminalServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_registry(root_path: str = ".") -> MCPServerRegistry:
    """Create and configure the MCP server registry."""
    registry = MCPServerRegistry(
        name="local-ai-agent",
        version="0.1.0",
    )

    # Register filesystem server
    fs_server = FilesystemServer(root_path=root_path)
    registry.register_server(fs_server, prefix="fs")

    # Register terminal server
    terminal_server = TerminalServer(enable_dangerous=False)
    registry.register_server(terminal_server, prefix="terminal")

    logger.info(f"Registry created with {registry.stats()}")
    return registry


async def run_stdio(registry: MCPServerRegistry) -> None:
    """Run server in stdio mode."""
    logger.info("Starting MCP server in stdio mode...")

    transport = StdioTransport(
        message_handler=registry.handle_message,
    )
    await transport.start()


async def run_websocket(registry: MCPServerRegistry, host: str, port: int) -> None:
    """Run server in WebSocket mode."""
    logger.info(f"Starting MCP WebSocket server on ws://{host}:{port}")

    transport = WebSocketTransport(
        message_handler=registry.handle_message,
        host=host,
        port=port,
    )
    await transport.start()

    # Keep running
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        await transport.stop()


async def run_http(registry: MCPServerRegistry, host: str, port: int) -> None:
    """Run server in HTTP mode."""
    # Create a unified MCP server from registry
    from core.mcp.server import MCPServer

    # Create composite server
    server = MCPServer(
        name=registry.name,
        version=registry.version,
        instructions=f"Local AI Agent with {registry.stats()['tools']} tools",
    )

    # Copy tools from all registered servers
    for server_name, mcp_server in registry._servers.items():
        for tool_name, handler in mcp_server.tools.items():
            full_name = f"{server_name}.{tool_name}"
            tool_def = mcp_server.tool_definitions[tool_name]
            server.register_tool(
                name=full_name,
                description=f"[{server_name}] {tool_def.description}",
                input_schema=tool_def.input_schema,
                handler=handler,
            )

    http_server = MCPHttpServer(server, host=host, port=port)
    await http_server.start()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local AI Agent MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run in stdio mode (for VS Code integration)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run HTTP server with REST API",
    )
    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Run WebSocket server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8080,
        help="HTTP server port (default: 8080)",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--root-path",
        type=str,
        default=".",
        help="Root path for filesystem operations",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create registry
    registry = create_registry(root_path=args.root_path)

    # Default to HTTP if no mode specified
    if not any([args.stdio, args.http, args.websocket]):
        args.http = True

    async def run_servers():
        tasks = []

        if args.stdio:
            tasks.append(run_stdio(registry))

        if args.http:
            tasks.append(run_http(registry, args.host, args.http_port))

        if args.websocket:
            tasks.append(run_websocket(registry, args.host, args.ws_port))

        await asyncio.gather(*tasks)

    try:
        asyncio.run(run_servers())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")


if __name__ == "__main__":
    main()
