"""Setup and installation guide."""

# Local AI Agent - Setup Guide

## Quick Start (5 minutes)

### 1. Prerequisites

- **Python 3.11+**: [Download](https://www.python.org/downloads/)
- **Ollama**: [Download](https://ollama.ai)
- **VS Code** (optional): [Download](https://code.visualstudio.com)

### 2. Clone Repository

```bash
git clone https://github.com/PlumbMonkey/local-ai-agent.git
cd local-ai-agent
```

### 3. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 5. Setup Ollama

```bash
# Install Ollama (if not already installed)
# https://ollama.ai

# Start Ollama service
ollama serve

# In another terminal, pull models
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

### 6. Test Installation

```bash
# Start the CLI
python -m interfaces.cli.main

# You should see:
# ✅ Ollama connected
# 📦 Available models: qwen2.5-coder:7b, nomic-embed-text
```

## Detailed Setup

### Python Environment

#### Windows
```powershell
# Create venv
python -m venv venv

# Activate
venv\Scripts\Activate.ps1

# Or with cmd.exe
venv\Scripts\activate.bat
```

#### macOS/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Ollama

1. **Download**: Visit [ollama.ai](https://ollama.ai)
2. **Install**: Follow platform-specific instructions
3. **Verify**:
   ```bash
   ollama --version
   ollama serve &  # Start service in background
   ```

### Model Selection

#### Recommended Setup

| Task | Model | Size | Speed |
|------|-------|------|-------|
| Code Completion | qwen2.5-coder:7b | 4.5GB | Fast |
| Embeddings | nomic-embed-text | 500MB | Fast |
| Complex Reasoning | deepseek-r1:8b | 5GB | Medium |

```bash
# Pull recommended models
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
ollama pull deepseek-r1:8b  # Optional, for reasoning tasks
```

#### Large Projects (If you have GPU)

```bash
# Better models if you have NVIDIA RTX 3060+ (12GB VRAM)
ollama pull qwen2.5-coder:14b  # Larger model, better quality
ollama pull mistral  # Alternative reasoning model
```

### VS Code Setup

1. **Install Continue Extension**:
   - Open VS Code
   - Search "Continue" in Extensions
   - Install [Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue)

2. **Configure** (`.vscode/settings.json`):
   ```json
   {
     "continue.modelProvider": "ollama",
     "continue.modelName": "qwen2.5-coder:7b",
     "continue.ollamaEndpoint": "http://localhost:11434"
   }
   ```

3. **Test**: Open any file, press `Ctrl+Shift+P` → "Continue: Chat"

### CLI Usage

```bash
# Start interactive chat
python -m interfaces.cli.main

# Example prompts:
# > Write a Python function to sort a list
# > Explain this code
# > exit
```

### Verify Everything Works

```bash
# Check Ollama health
curl http://localhost:11434/api/tags

# Run tests
pytest tests/unit/

# Try CLI
python -m interfaces.cli.main
```

## Troubleshooting

### Ollama Connection Fails

```bash
# Check if Ollama is running
# macOS: Check menu bar for Ollama icon
# Windows: Check System Tray or run:
ollama serve

# If still fails, check endpoint
curl -v http://localhost:11434/api/tags
```

### Out of Memory

- **RAM**: Close other apps, or reduce model size
- **VRAM**: Use smaller models (7B instead of 14B)

```bash
# Check available VRAM
nvidia-smi  # For NVIDIA
```

### Model Download Fails

```bash
# Try pulling directly
ollama pull qwen2.5-coder:7b

# If still fails, check disk space
# Models are large: 4.5GB + 4.5GB + 500MB = ~10GB
```

### Import Errors

```bash
# Reinstall in editable mode
pip install -e ".[dev]"

# Or install missing packages
pip install chromadb llama-index langraph
```

## Development Setup

### Install Dev Tools

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/unit/
pytest tests/unit/ -v  # Verbose
pytest tests/unit/ --cov  # With coverage
```

### Code Quality

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy core/
```

### Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

## Configuration

### Environment Variables

Create `.env`:
```bash
OLLAMA_ENDPOINT=http://localhost:11434
MODEL_PRIMARY=qwen2.5-coder:7b
MODEL_REASONING=deepseek-r1:8b
MODEL_EMBEDDING=nomic-embed-text
DEBUG=false
```

### Settings File

Edit `core/config/settings.py` for defaults.

## Next Steps

- [Architecture Guide](ARCHITECTURE.md)
- [MCP Server Development](MCP_PROTOCOL.md)
- [Domain Integration](DOMAINS.md)
- [Example Workflows](../examples/workflows/)

## Support

- **Issues**: [GitHub Issues](https://github.com/PlumbMonkey/local-ai-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/PlumbMonkey/local-ai-agent/discussions)

---

**Stuck?** Try the [troubleshooting section](#troubleshooting) or open an issue!
