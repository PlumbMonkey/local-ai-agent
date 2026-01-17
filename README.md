# Local AI Agent

**Privacy-first, self-hosted AI agent** that enhances VS Code with personalized context from your chat history, while seamlessly integrating with GitHub Copilot's ecosystem through Model Context Protocol (MCP).

## 🎯 Key Features

- **Zero Cloud Dependency**: All inference runs locally via Ollama
- **Personalized Memory**: RAG pipeline learns from your entire chat/coding history  
- **MCP-Native**: First-class integration with GitHub Copilot's context protocol
- **Agentic Actions**: Execute multi-step tasks across IDE, terminal, browser, and local files
- **Modular Architecture**: Free core + premium domains for specialized workflows

## 🚀 Quick Start

### Requirements
- **OS**: Windows, macOS, or Linux
- **Python**: 3.11+
- **RAM**: 16GB minimum (32GB recommended)
- **GPU**: Optional but recommended (NVIDIA RTX 3060+ with CUDA)

### Installation

```bash
# Clone the repository
git clone https://github.com/PlumbMonkey/local-ai-agent.git
cd local-ai-agent

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Or (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Setup Ollama

1. Download [Ollama](https://ollama.ai) for your OS
2. Install and start the service
3. Pull models:
```bash
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

4. Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

## 📦 Project Structure

```
local-ai-agent/
├── core/                    # Base implementation (MIT Licensed)
│   ├── mcp/                # Model Context Protocol
│   ├── llm/                # Ollama integration
│   ├── memory/             # RAG pipeline
│   └── config/             # Configuration
├── domains/                # Modular features
│   ├── base/               # Free: File, Terminal, Chat
│   ├── coding/             # Free+Premium: Code assistance
│   ├── study/              # Free+Premium: Learning tools
│   ├── daw/                # Premium: Music production
│   └── blender/            # Premium: 3D graphics
├── interfaces/             # User interfaces
│   ├── vscode/             # VS Code extension
│   └── cli/                # Command-line interface
├── agents/                 # Agentic workflows
├── scripts/                # Setup and utilities
└── docs/                   # Documentation
```

## 🏗️ Architecture

```
VS Code IDE
    ↓
Model Context Protocol (MCP)
    ├── Filesystem Server
    ├── Terminal Server
    ├── Memory Server
    └── Browser Server
    ↓
Ollama (Local LLM)
    ├── qwen2.5-coder:7b
    ├── deepseek-r1:8b
    └── nomic-embed-text
    ↓
Memory & Context Layer
    ├── ChromaDB (Vector Store)
    └── LlamaIndex (RAG Engine)
```

## 📚 Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design details
- [SETUP.md](docs/SETUP.md) - Detailed installation guide
- [DOMAINS.md](docs/DOMAINS.md) - Domain-specific features
- [MCP_PROTOCOL.md](docs/MCP_PROTOCOL.md) - MCP server development
- [PRD.md](PRD.md) - Full product requirements

## 🎮 Usage

### Command Line

```bash
# Start the agent
python -m interfaces.cli.main chat

# Index your chat history
python scripts/export_chat_history.py --input chatgpt_export.json

# Run benchmarks
python scripts/benchmark.py
```

### VS Code Integration

1. Open VS Code settings
2. Configure the Continue extension:
   ```json
   {
     "continue.modelProvider": "ollama",
     "continue.modelName": "qwen2.5-coder:7b",
     "continue.ollamaEndpoint": "http://localhost:11434",
     "continue.enableMCP": true
   }
   ```
3. Ask: "Read main.py and explain it"

## 🔐 Security & Privacy

- ✅ All data stays on your machine
- ✅ No external API calls (verified by network audit)
- ✅ Encrypted at-rest storage (SQLCipher)
- ✅ User confirmation for destructive actions

## 📊 Roadmap

### Phase 1 (Week 1-2): Foundation
- [x] Repository setup
- [ ] Ollama integration
- [ ] MCP filesystem server
- [ ] VS Code extension configuration

### Phase 2 (Week 3-4): Memory Layer
- [ ] Chat history parser
- [ ] ChromaDB + embeddings
- [ ] RAG query engine
- [ ] MCP memory server

### Phase 3 (Week 5-6): Agentic Actions
- [ ] LangGraph orchestrator
- [ ] Multi-step workflows
- [ ] Browser automation
- [ ] Confirmation system

### Phase 4 (Week 7-8): Polish
- [ ] Documentation
- [ ] Performance tuning
- [ ] Configuration UI
- [ ] Release v1.0

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

- **Core** (`/core`): MIT License
- **Premium Domains**: Commercial License (see LICENSE-COMMERCIAL)
- **Enterprise**: Commercial License

## 📧 Contact

- Author: PlumbMonkey
- GitHub: [@PlumbMonkey](https://github.com/PlumbMonkey)
- Issues: [GitHub Issues](https://github.com/PlumbMonkey/local-ai-agent/issues)

---

**Status**: 🚧 Early Alpha (Phase 1 in progress)  
**Last Updated**: January 17, 2026
