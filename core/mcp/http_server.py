"""HTTP Server for MCP with REST API and SSE support."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional
from uuid import uuid4

from core.mcp.server import MCPServer
from core.mcp.transport import SSETransport

logger = logging.getLogger(__name__)


class MCPHttpServer:
    """
    HTTP server wrapper for MCP servers.

    Provides:
    - REST API for JSON-RPC requests
    - Server-Sent Events for streaming responses
    - Health checks and server info endpoints
    """

    def __init__(
        self,
        mcp_server: MCPServer,
        host: str = "localhost",
        port: int = 8080,
    ):
        """
        Initialize HTTP server.

        Args:
            mcp_server: The MCP server to expose
            host: Host to bind to
            port: Port to bind to
        """
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.sse_transport = SSETransport()
        self._app = None

    def create_app(self):
        """Create FastAPI application."""
        try:
            from fastapi import FastAPI, Request, Response, HTTPException
            from fastapi.responses import StreamingResponse, JSONResponse
            from fastapi.middleware.cors import CORSMiddleware
        except ImportError:
            raise ImportError(
                "FastAPI required. Install with: pip install fastapi uvicorn"
            )

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan handler."""
            logger.info(f"Starting MCP HTTP server: {self.mcp_server.name}")
            yield
            logger.info("Shutting down MCP HTTP server")

        app = FastAPI(
            title=f"MCP Server: {self.mcp_server.name}",
            version=self.mcp_server.version,
            description="Model Context Protocol HTTP Server",
            lifespan=lifespan,
        )

        # CORS middleware for browser access
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ═══════════════════════════════════════════════════════════════════════
        # Health & Info Endpoints
        # ═══════════════════════════════════════════════════════════════════════

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "server": self.mcp_server.name}

        @app.get("/info")
        async def server_info():
            """Get server information."""
            return {
                "name": self.mcp_server.name,
                "version": self.mcp_server.version,
                "tools": len(self.mcp_server.tools),
                "resources": len(self.mcp_server.resources),
                "prompts": len(self.mcp_server.prompts),
            }

        # ═══════════════════════════════════════════════════════════════════════
        # JSON-RPC Endpoint
        # ═══════════════════════════════════════════════════════════════════════

        @app.post("/rpc")
        async def json_rpc(request: Request):
            """
            Handle JSON-RPC requests.

            This is the main MCP protocol endpoint.
            """
            try:
                body = await request.json()
                response = await self.mcp_server.handle_message(body)

                if response is None:
                    # Notification - no response needed
                    return Response(status_code=204)

                return JSONResponse(content=__import__("json").loads(response))
            except Exception as e:
                logger.exception("JSON-RPC error")
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    },
                )

        # ═══════════════════════════════════════════════════════════════════════
        # REST API Endpoints (Convenience wrappers)
        # ═══════════════════════════════════════════════════════════════════════

        @app.get("/tools")
        async def list_tools():
            """List available tools."""
            return {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in self.mcp_server.list_tools()
                ]
            }

        @app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, request: Request):
            """Call a specific tool."""
            from core.mcp.types import ToolCall

            try:
                body = await request.json()
            except:
                body = {}

            tool_call = ToolCall(tool_name=tool_name, arguments=body)
            result = await self.mcp_server.call_tool(tool_call)

            if result.is_error:
                raise HTTPException(status_code=400, detail=result.content[0].text if result.content else "Error")

            return result.model_dump(exclude_none=True, by_alias=True)

        @app.get("/resources")
        async def list_resources():
            """List available resources."""
            return {
                "resources": [
                    {
                        "uri": r.uri,
                        "name": r.name,
                        "description": r.description,
                        "mimeType": r.mimeType,
                    }
                    for r in self.mcp_server.list_resources()
                ]
            }

        @app.get("/resources/{uri:path}")
        async def read_resource(uri: str):
            """Read a specific resource."""
            try:
                contents = await self.mcp_server.read_resource(uri)
                return contents.model_dump(exclude_none=True)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.get("/prompts")
        async def list_prompts():
            """List available prompts."""
            return {
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "arguments": [a.model_dump() for a in (p.arguments or [])],
                    }
                    for p in self.mcp_server.list_prompts()
                ]
            }

        @app.post("/prompts/{prompt_name}")
        async def get_prompt(prompt_name: str, request: Request):
            """Get a specific prompt."""
            try:
                body = await request.json()
            except:
                body = {}

            try:
                messages = await self.mcp_server.get_prompt(prompt_name, body)
                return {"messages": [m.model_dump(exclude_none=True) for m in messages]}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        # ═══════════════════════════════════════════════════════════════════════
        # Server-Sent Events Endpoint
        # ═══════════════════════════════════════════════════════════════════════

        @app.get("/events")
        async def event_stream(request: Request):
            """
            SSE endpoint for server-to-client streaming.

            Clients can subscribe to receive:
            - Progress updates
            - Log messages
            - Resource change notifications
            """
            client_id = str(uuid4())
            self.sse_transport.create_client(client_id)

            async def generate():
                try:
                    async for event in self.sse_transport.event_generator(client_id):
                        yield event
                except asyncio.CancelledError:
                    pass
                finally:
                    self.sse_transport.remove_client(client_id)

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        self._app = app
        return app

    async def start(self) -> None:
        """Start the HTTP server."""
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn required. Install with: pip install uvicorn")

        if not self._app:
            self.create_app()

        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run(self) -> None:
        """Run the server (blocking)."""
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn required. Install with: pip install uvicorn")

        if not self._app:
            self.create_app()

        uvicorn.run(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )

    async def send_progress(self, client_id: str, progress: float, message: str = "") -> None:
        """Send progress update to SSE client."""
        await self.sse_transport.send(
            client_id,
            "progress",
            {"progress": progress, "message": message},
        )

    async def broadcast_log(self, level: str, message: str) -> None:
        """Broadcast log message to all SSE clients."""
        await self.sse_transport.broadcast(
            "log",
            {"level": level, "message": message},
        )
