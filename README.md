# gh-llm

Local-first GitHub repository browsing tool for LLMs. Inspired by [github-llm](https://github.com/rien7/github-llm).

## Why Local-First?

Unlike the Cloudflare Worker version (`github-llm`), this tool runs locally on your machine. No deployment needed—just install and use.

**Advantages:**
- No Cloudflare account required
- Token stored locally, never leaves your machine
- Works offline after initial setup
- Zero infrastructure cost

## Installation

### From source

```bash
git clone https://github.com/rien7/gh-llm
cd gh-llm
uv sync
```

### As a CLI tool

```bash
# Using uv tool (recommended - no need to activate virtualenv)
make install-tool

# Or using pip
uv pip install -e .
```

## Quick Start

### 1. Configure your token

```bash
# Auto-detect from gh CLI (if installed)
gh-llm setup

# Or provide manually
gh-llm setup --token ghp_xxxxxxxxxxxxxxxxxxxx
```

The token is stored in `~/.config/gh-llm/token`.

### 2. Browse repositories

```bash
# List repository contents
gh-llm ls octocat/Hello-World
gh-llm ls octocat/Hello-World --ref main

# List with JSON output (great for LLMs)
gh-llm ls octocat/Hello-World --json

# View file contents
gh-llm cat octocat/Hello-World README.md
gh-llm cat octocat/Hello-World src/main.py --ref develop

# Check configuration
gh-llm status
```

## Commands

| Command | Description |
|---------|-------------|
| `setup` | Configure GitHub token |
| `ls` / `tree` | List directory contents |
| `cat` | Display file contents |
| `status` | Show configuration status |

## Rate Limits

- **Unauthenticated**: 60 requests/hour per IP
- **Authenticated**: 5,000 requests/hour

For public repositories, authentication is optional but recommended for higher rate limits.

## Development

```bash
# Install dependencies
uv sync

# Run tests
make test

# Lint & format
make lint
make fmt

# Type check
make typecheck
```

## License

MIT
