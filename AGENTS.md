# AGENTS.md

Project-specific instructions for AI agents.

## Project Overview

- **Name**: gh-llm
- **Type**: CLI tool (Python)
- **Package**: gh_llm

## Commands

```bash
# Run CLI
uv run gh-llm --help

# Install as CLI tool
uv pip install -e .

# Run tests
make test

# Lint
make lint

# Format
make fmt

# Type check
make typecheck
```

## Code Style

- Use single quotes in Python code (enforced by ruff)
- Google-style docstrings
- Strict type checking enabled
- Run `make lint && make typecheck` before committing

## Key Files

- `src/gh_llm/commands.py` - CLI command definitions
- `src/gh_llm/github.py` - GitHub API client
- `src/gh_llm/config.py` - Token storage configuration

## Dependencies

- typer - CLI framework
- httpx - Async HTTP client
- rich - Terminal output formatting
- platformdirs - Cross-platform config directory
