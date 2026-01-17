"""Changelog tracking version history."""

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and scaffolding
- Core Ollama integration with health checks and model management
- Base MCP protocol implementation (server, types, client stubs)
- Filesystem MCP server with security boundaries
- Terminal MCP server with command whitelist
- Vector store wrapper for ChromaDB
- Configuration management with Pydantic settings
- CLI interface for interactive chat
- VS Code extension scaffolding
- Development test suite (unit tests for core components)
- Comprehensive documentation (Architecture, Setup guides)

### In Progress (Phase 1)
- [ ] VS Code extension development
- [ ] MCP protocol refinement
- [ ] Memory server integration
- [ ] Browser automation server

## [0.1.0] - 2026-01-17

### Initial Release
- Project initialization
- Core architecture implementation
- Basic Ollama integration
- MCP server framework

---

For detailed PRD, see [PRD.md](PRD.md)
