"""Architecture and design documentation."""

# Local AI Agent - Architecture

## System Overview

The Local AI Agent is built on a modular, layered architecture designed for privacy, extensibility, and performance.

```
┌─────────────────────────────────────────┐
│         User Interfaces                 │
│   ├─ VS Code Extension (TypeScript)    │
│   ├─ CLI (Python)                      │
│   └─ Web UI (FastAPI + Web)           │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Model Context Protocol (MCP)           │
│   ├─ Filesystem Server                 │
│   ├─ Terminal Server                   │
│   ├─ Memory Server (RAG)               │
│   ├─ Browser Server                    │
│   └─ GitHub Server                     │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Core Layer (MIT Licensed)              │
│   ├─ Config Management                 │
│   ├─ Ollama LLM Integration           │
│   ├─ Memory/RAG Pipeline               │
│   └─ MCP Protocol Handler              │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Domains (Free & Premium)              │
│   ├─ base/ (File, Terminal, Chat)     │
│   ├─ coding/ (Code Tools)             │
│   ├─ study/ (Learning Tools)          │
│   ├─ daw/ (Music Production)          │
│   └─ blender/ (3D Graphics)           │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Agent Layer                            │
│   ├─ Orchestrator (LangGraph)          │
│   ├─ Planner (Multi-step)             │
│   └─ Executor (Tool Runner)           │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Local Services (No Cloud)              │
│   ├─ Ollama (qwen, deepseek, embeddings)
│   ├─ ChromaDB (Vector Storage)         │
│   └─ File System                       │
└─────────────────────────────────────────┘
```

## Core Components

### 1. Configuration (`core/config/`)
- **settings.py**: Pydantic-based settings with environment variable loading
- Manages Ollama endpoint, models, storage paths
- Thread-safe global settings instance

### 2. LLM Integration (`core/llm/`)
- **ollama.py**: HTTP client for Ollama API
  - Health checks
  - Model listing
  - Text generation (streaming & batch)
  - Embeddings

### 3. MCP Protocol (`core/mcp/`)
- **server.py**: Base MCP server with tool registration
- **types.py**: Protocol data structures (Tool, ToolCall, ToolResult)
- **client.py**: Client for communicating with MCP servers

### 4. Memory Layer (`core/memory/`)
- **vector_store.py**: ChromaDB wrapper
  - Document storage and retrieval
  - Metadata tracking
  - Query interface

## Domain Architecture

Each domain is self-contained with:
- `__init__.py`: Public API
- `server.py`: MCP server implementation
- `tools.py`: Domain-specific utilities
- Optional: `config.yaml`, `models.json`

### Base Domains (Free)
- **filesystem**: Read/write local files
- **terminal**: Execute shell commands
- **chat**: Basic conversation interface

### Premium Domains
- **coding**: Code analysis, refactoring, review
- **study**: Note indexing, quiz generation
- **daw**: Music production assistance
- **blender**: 3D graphics helpers

## MCP Server Design Pattern

Each server implements the Model Context Protocol:

```python
from core.mcp.server import MCPServer

class MyServer(MCPServer):
    def __init__(self):
        super().__init__("my_server")
        
        self.register_tool(
            name="my_tool",
            description="What it does",
            input_schema={...},
            handler=self.my_tool_impl
        )
```

## Agent Orchestration

**LangGraph-based workflows** coordinate multi-step tasks:

1. **Planner**: Breaks task into steps
2. **Executor**: Runs each step using MCP servers
3. **Recovery**: Retries on failure
4. **Confirmation**: Prompts user for destructive actions

Example: "Fix this bug"
```
Research Code → Understand Issue → Generate Fix → Test → Commit
```

## Data Flow for Chat

```
User Input
    ↓
CLI/VS Code Extension
    ↓
Local Agent (Ollama qwen2.5-coder)
    ↓
Query Memory (ChromaDB) for context
    ↓
Call MCP Servers as needed (file read, terminal exec, etc)
    ↓
Generate Response
    ↓
Update Chat History
    ↓
Return to User
```

## Security Boundaries

1. **Filesystem Server**: Root path restriction
2. **Terminal Server**: Command whitelist + timeout
3. **Memory Server**: Local storage only
4. **No Network**: Zero external API calls by default

## Performance Considerations

- **Model Loading**: ~5s (cold start)
- **Inference**: <2s for completions, <10s for reasoning
- **RAG Query**: <500ms for top-k retrieval
- **Memory**: 16GB minimum (includes model + OS)

## Extensibility

### Adding a New Domain

1. Create `domains/mydomain/`
2. Implement MCP server in `server.py`
3. Register in configuration
4. Add to CLI/VS Code interfaces

### Custom MCP Server

Any Python script can expose MCP protocol:
```python
from core.mcp.server import MCPServer

server = MCPServer("custom")
server.register_tool(...)
```

## Future Architecture Improvements

1. **Multi-model routing**: Route tasks to best model
2. **Local caching**: Cache inference results
3. **Parallel execution**: Run independent tasks concurrently
4. **Telemetry**: Local-only usage tracking
5. **Team sync**: Encrypted shared memory (enterprise)
