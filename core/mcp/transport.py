"""MCP Transport implementations: HTTP, WebSocket, and Stdio."""

import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def start(self) -> None:
        """Start the transport."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""
        pass

    @abstractmethod
    async def send(self, message: str) -> None:
        """Send a message."""
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[str]:
        """Receive messages."""
        pass


class StdioTransport(MCPTransport):
    """
    Stdio transport for subprocess/CLI integration.

    This is the transport VS Code and other clients typically use
    to communicate with MCP servers via stdin/stdout.
    """

    def __init__(
        self,
        message_handler: Callable[[str], Any],
        read_stream: Any = None,
        write_stream: Any = None,
    ):
        """
        Initialize stdio transport.

        Args:
            message_handler: Async function to handle incoming messages
            read_stream: Input stream (defaults to sys.stdin)
            write_stream: Output stream (defaults to sys.stdout)
        """
        self._handler = message_handler
        self._read_stream = read_stream or sys.stdin
        self._write_stream = write_stream or sys.stdout
        self._running = False
        self._read_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start reading from stdin."""
        self._running = True
        self._read_task = asyncio.create_task(self._read_loop())
        logger.info("Stdio transport started")

    async def stop(self) -> None:
        """Stop the transport."""
        self._running = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        logger.info("Stdio transport stopped")

    async def send(self, message: str) -> None:
        """Send message to stdout."""
        # MCP uses newline-delimited JSON
        output = message.strip() + "\n"
        self._write_stream.write(output)
        self._write_stream.flush()

    async def receive(self) -> AsyncIterator[str]:
        """Receive messages from stdin."""
        while self._running:
            try:
                # Use asyncio to read from stdin without blocking
                loop = asyncio.get_event_loop()
                line = await loop.run_in_executor(None, self._read_stream.readline)
                if line:
                    yield line.strip()
                else:
                    # EOF received
                    break
            except Exception as e:
                logger.error(f"Error reading from stdin: {e}")
                break

    async def _read_loop(self) -> None:
        """Main read loop."""
        async for message in self.receive():
            if message:
                try:
                    response = await self._handler(message)
                    if response:
                        await self.send(response)
                except Exception as e:
                    logger.exception(f"Error handling message: {e}")


class WebSocketTransport(MCPTransport):
    """WebSocket transport for bidirectional communication."""

    def __init__(
        self,
        message_handler: Callable[[str], Any],
        host: str = "localhost",
        port: int = 8765,
    ):
        """
        Initialize WebSocket transport.

        Args:
            message_handler: Async function to handle incoming messages
            host: Host to bind to
            port: Port to bind to
        """
        self._handler = message_handler
        self._host = host
        self._port = port
        self._server = None
        self._connections: set = set()

    async def start(self) -> None:
        """Start WebSocket server."""
        try:
            import websockets
        except ImportError:
            raise ImportError("websockets package required. Install with: pip install websockets")

        self._server = await websockets.serve(
            self._handle_connection,
            self._host,
            self._port,
        )
        logger.info(f"WebSocket transport started on ws://{self._host}:{self._port}")

    async def stop(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for ws in self._connections:
            await ws.close()
        self._connections.clear()
        logger.info("WebSocket transport stopped")

    async def send(self, message: str) -> None:
        """Broadcast message to all connected clients."""
        if self._connections:
            import websockets
            await asyncio.gather(
                *[ws.send(message) for ws in self._connections],
                return_exceptions=True,
            )

    async def send_to(self, websocket, message: str) -> None:
        """Send message to specific client."""
        try:
            await websocket.send(message)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")

    async def receive(self) -> AsyncIterator[str]:
        """Not used for server mode."""
        yield ""

    async def _handle_connection(self, websocket, path: str = "") -> None:
        """Handle a WebSocket connection."""
        self._connections.add(websocket)
        client_id = id(websocket)
        logger.info(f"Client connected: {client_id}")

        try:
            async for message in websocket:
                try:
                    response = await self._handler(message)
                    if response:
                        await self.send_to(websocket, response)
                except Exception as e:
                    logger.exception(f"Error handling message: {e}")
                    error_response = json.dumps({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    })
                    await self.send_to(websocket, error_response)
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self._connections.discard(websocket)
            logger.info(f"Client disconnected: {client_id}")


class SSETransport:
    """
    Server-Sent Events transport for HTTP streaming.

    This provides one-way server-to-client streaming,
    useful for progress updates and log messages.
    """

    def __init__(self):
        """Initialize SSE transport."""
        self._clients: dict[str, asyncio.Queue] = {}

    def create_client(self, client_id: str) -> asyncio.Queue:
        """Create a new SSE client queue."""
        queue = asyncio.Queue()
        self._clients[client_id] = queue
        logger.debug(f"SSE client created: {client_id}")
        return queue

    def remove_client(self, client_id: str) -> None:
        """Remove an SSE client."""
        self._clients.pop(client_id, None)
        logger.debug(f"SSE client removed: {client_id}")

    async def send(self, client_id: str, event: str, data: Any) -> None:
        """Send event to specific client."""
        if client_id in self._clients:
            message = {
                "event": event,
                "data": data if isinstance(data, str) else json.dumps(data),
            }
            await self._clients[client_id].put(message)

    async def broadcast(self, event: str, data: Any) -> None:
        """Broadcast event to all clients."""
        for client_id in self._clients:
            await self.send(client_id, event, data)

    async def event_generator(self, client_id: str) -> AsyncIterator[str]:
        """Generate SSE events for a client."""
        queue = self._clients.get(client_id)
        if not queue:
            return

        try:
            while True:
                message = await queue.get()
                yield f"event: {message['event']}\ndata: {message['data']}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.remove_client(client_id)
