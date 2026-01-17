"""Contributing guidelines."""

# Contributing to Local AI Agent

## Code of Conduct

Be respectful, inclusive, and constructive.

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the development setup in [SETUP.md](docs/SETUP.md)

## Code Standards

### Python Style
- Use black for formatting: `black .`
- Use ruff for linting: `ruff check .`
- Use mypy for type checking: `mypy core/`
- Target Python 3.11+

### Commit Messages
- Use clear, descriptive messages
- Reference issues when relevant: `Fixes #123`
- Example: `feat(mcp): add browser-use server`

### Documentation
- Add docstrings to all functions
- Update README.md for user-facing changes
- Update ARCHITECTURE.md for design changes

## Pull Request Process

1. Update tests for your changes
2. Ensure all tests pass: `pytest`
3. Run linters: `black . && ruff check .`
4. Update relevant docs
5. Submit PR with description

## Issue Labels

- `good first issue`: Good for newcomers
- `help wanted`: Need contributions
- `bug`: Something broken
- `enhancement`: New feature
- `docs`: Documentation

## Questions?

Open a discussion or issue on GitHub!

---

Thank you for contributing! 🙏
