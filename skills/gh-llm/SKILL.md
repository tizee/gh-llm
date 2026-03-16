---
name: gh-llm
description: >
  Browse GitHub repository contents from the command line using gh-llm.
  Use this skill whenever you need to list files in a GitHub repo, read file
  contents from GitHub, explore a repository's directory structure, or check
  gh-llm configuration status. Triggers on requests like "show me the files in
  this GitHub repo", "read README from owner/repo", "list the contents of
  https://github.com/owner/repo", "what's in this repo", "cat this file from
  GitHub", or any task involving browsing GitHub repository trees and files
  without cloning. Also use when the user mentions "gh-llm" directly.
---

# gh-llm

A local-first CLI tool for browsing GitHub repository contents without cloning. Fetches directory listings and file contents via the GitHub API.

## Prerequisites

Before using any command (except `setup` and `status`), verify a token is configured:

```bash
gh-llm status
```

If no token is configured, set one up. The easiest path is to let it pull from the `gh` CLI:

```bash
gh-llm setup
```

Or provide a token directly:

```bash
gh-llm setup --token ghp_xxxxx
```

If a token already exists and you need to replace it:

```bash
gh-llm setup --token ghp_xxxxx --force
```

## Repository Argument

All browsing commands accept the repo in two formats:

| Format | Example |
|--------|---------|
| `owner/repo` | `octocat/Hello-World` |
| Full GitHub URL | `https://github.com/octocat/Hello-World` |

Both are equivalent. Use whichever is more convenient -- if the user provides a full URL, pass it directly.

## Commands

### List directory contents

```bash
# List repo root
gh-llm ls owner/repo

# List a subdirectory
gh-llm ls owner/repo src/components

# Specific branch/tag/commit
gh-llm ls owner/repo --ref v2.0.0

# JSON output (for piping or machine consumption)
gh-llm ls owner/repo --json
```

`tree` is an alias for `ls` -- they behave identically.

Output is a table with Type (dir/file), Name, and Size columns. Directories are listed first, then files, both sorted alphabetically.

Use `--json` when you need to process the output programmatically. It outputs a JSON array of objects with `name`, `path`, `type`, and `size` fields, bypassing Rich formatting.

### Read file contents

```bash
# Read a file
gh-llm cat owner/repo README.md

# Read from a specific ref
gh-llm cat owner/repo src/main.py --ref main
```

Outputs raw file content to stdout with no formatting. Safe to pipe or redirect.

### Check status

```bash
gh-llm status
```

Shows whether a token is configured and where it's stored.

## Workflow Pattern

A typical exploration session looks like:

```bash
# 1. Check what's in the repo
gh-llm ls owner/repo

# 2. Drill into a directory
gh-llm ls owner/repo src

# 3. Read a file of interest
gh-llm cat owner/repo src/main.py
```

## Error Handling

| Error | Meaning | Action |
|-------|---------|--------|
| "No token configured" | No token saved | Run `gh-llm setup` |
| "not found" | Path or repo doesn't exist | Check the repo name and path |
| "rate limit exceeded" | API rate limit hit | Run `gh-llm setup` to add a token (5000 req/hr vs 60) |
| "Authentication required" | Token is invalid or expired | Run `gh-llm setup --force` with a new token |

## Tips

- For large repos, use `--json` and pipe through `jq` to filter results
- The `cat` command handles large files that exceed GitHub's API content limit by following the download URL automatically
- Color output is automatically disabled when piped to another command (Rich auto-detects non-TTY)
