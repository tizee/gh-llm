"""CLI commands for gh-llm."""

import sys
import json
import asyncio
import subprocess
from contextlib import contextmanager
from collections.abc import Iterator

import typer

from gh_llm import config
from gh_llm.github import (
    GitHubError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
    AuthenticationError,
)

app = typer.Typer(help='gh-llm: Local-first GitHub repository browsing tool for LLMs')


def _err(msg: str) -> None:
    """Print error message to stderr."""
    print(f'Error: {msg}', file=sys.stderr)


def require_token() -> None:
    """Ensure a token is configured, or exit with an error."""
    if not config.has_token():
        _err("No token configured. Run 'gh-llm setup' first.")
        raise typer.Exit(1)


@contextmanager
def handle_github_errors(resource_desc: str) -> Iterator[None]:
    """Catch GitHub API errors and print user-friendly messages."""
    try:
        yield
    except NotFoundError:
        _err(f'{resource_desc} not found')
        raise typer.Exit(1)
    except RateLimitError as e:
        _err(str(e))
        print("Run 'gh-llm setup' to configure a token.", file=sys.stderr)
        raise typer.Exit(1)
    except AuthenticationError as e:
        _err(str(e))
        print("Run 'gh-llm setup' to reconfigure your token.", file=sys.stderr)
        raise typer.Exit(1)
    except GitHubError as e:
        _err(str(e))
        raise typer.Exit(1)


def parse_repo_and_path(input_str: str) -> tuple[str, str, str]:
    """Parse a combined 'owner/repo/path...' string into (owner, repo, path).

    Accepts:
        - 'owner/repo'
        - 'owner/repo/path/to/file'
        - 'https://github.com/owner/repo/path/to/file'

    Returns:
        Tuple of (owner, repo_name, path) where path may be empty.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    # Strip full GitHub URL prefix
    for prefix in ('https://github.com/', 'http://github.com/'):
        if input_str.startswith(prefix):
            input_str = input_str[len(prefix) :]
            break

    # Remove trailing slash
    input_str = input_str.strip('/')

    parts = input_str.split('/')
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("Repository must be in format 'owner/repo' or 'owner/repo/path'")

    owner = parts[0]
    repo_name = parts[1]
    path = '/'.join(parts[2:])
    return owner, repo_name, path


def parse_repo(repo: str) -> tuple[str, str]:
    """Parse a repo string into (owner, repo_name).

    Accepts:
        - 'owner/repo'
        - 'https://github.com/owner/repo'
        - 'http://github.com/owner/repo'

    Raises:
        ValueError: If the string cannot be parsed as owner/repo.
    """
    # Strip full GitHub URL prefix
    for prefix in ('https://github.com/', 'http://github.com/'):
        if repo.startswith(prefix):
            repo = repo[len(prefix) :]
            break

    # Remove trailing slash
    repo = repo.strip('/')

    parts = repo.split('/')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Repository must be in format 'owner/repo' or a full GitHub URL")
    return parts[0], parts[1]


def get_client() -> GitHubClient:
    """Get a GitHub client with the configured token."""
    token = config.get_token()
    return GitHubClient(token)


@app.command()
def setup(
    token: str | None = typer.Option(
        None,
        '--token',
        '-t',
        help="GitHub token. If not provided, attempts to use 'gh auth token'.",
    ),
    force: bool = typer.Option(
        False,
        '--force',
        '-f',
        help='Overwrite existing token without prompting.',
    ),
) -> None:
    """Configure the GitHub token for authentication.

    This command saves your GitHub token locally so that subsequent commands
    can authenticate with the GitHub API.

    For public repositories, a token is optional but recommended for higher
    rate limits (60 requests/hour unauthenticated vs 5,000 authenticated).

    For private repositories, a token with 'Contents: Read-only' permission
    is required.

    You can create a fine-grained personal access token at:
    https://github.com/settings/tokens
    """
    # Check if token already exists
    if config.has_token() and not force:
        _err('Token already configured. Use --force to overwrite.')
        raise typer.Exit(1)

    # Try to get token from gh CLI if not provided
    if not token:
        try:
            result = subprocess.run(
                ['gh', 'auth', 'token'],
                capture_output=True,
                text=True,
                check=True,
            )
            token = result.stdout.strip()
            print("Retrieved token from 'gh auth token'", file=sys.stderr)
        except FileNotFoundError:
            _err('gh CLI not found. Please provide a token manually with --token.')
            raise typer.Exit(1)
        except subprocess.CalledProcessError:
            _err(
                "Failed to get token from 'gh auth token'. "
                'Please provide a token manually with --token.'
            )
            raise typer.Exit(1)

    if not token:
        _err('No token provided.')
        raise typer.Exit(1)

    # Validate token format (basic check)
    if len(token) < 10:
        _err('Token appears to be invalid (too short).')
        raise typer.Exit(1)

    # Save the token
    config.save_token(token)
    print('Token saved successfully.')
    print(f'Stored in: {config.get_token_path()}')


@app.command('ls')
@app.command('tree')
def list_directory(
    repo: str = typer.Argument(
        ..., help="Repository with optional path: 'owner/repo[/path]' or full GitHub URL"
    ),
    path: str = typer.Argument('', help='Path within the repository (optional)'),
    ref: str = typer.Option(
        None,
        '--ref',
        '-r',
        help='Git reference (branch, tag, or commit SHA)',
    ),
    json_output: bool = typer.Option(
        False,
        '--json',
        help='Output as JSON for machine consumption',
    ),
) -> None:
    """List directory contents of a GitHub repository.

    Examples:
        gh-llm ls octocat/Hello-World
        gh-llm ls octocat/Hello-World/src
        gh-llm ls octocat/Hello-World src
        gh-llm ls octocat/Hello-World --ref main
    """
    try:
        owner, repo_name, parsed_path = parse_repo_and_path(repo)
    except ValueError:
        _err("Repository must be in format 'owner/repo' or 'owner/repo/path'")
        raise typer.Exit(1)

    # Explicit path arg takes precedence; otherwise use path embedded in repo arg
    effective_path = path if path else parsed_path

    require_token()
    client = get_client()

    with handle_github_errors(f"Path '{effective_path}' in {owner}/{repo_name}"):
        entries = asyncio.run(client.get_repo_contents(owner, repo_name, effective_path, ref))

    if json_output:
        output = [
            {
                'name': e.name,
                'path': e.path,
                'type': e.type,
                'size': e.size,
            }
            for e in entries
        ]
        print(json.dumps(output, indent=2))
        return

    # Sort: directories first, then files
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.type != 'dir', e.name.lower()),
    )

    for entry in sorted_entries:
        entry_type = 'dir' if entry.type == 'dir' else 'file'
        size_str = '' if entry.size is None else f'\t{_format_size(entry.size)}'
        print(f'{entry_type}\t{entry.name}{size_str}')


@app.command('cat')
def cat_file(
    repo: str = typer.Argument(
        ..., help="Repository with optional path: 'owner/repo[/path]' or full GitHub URL"
    ),
    path: str = typer.Argument('', help='Path to the file (can be included in repo arg)'),
    ref: str = typer.Option(
        None,
        '--ref',
        '-r',
        help='Git reference (branch, tag, or commit SHA)',
    ),
) -> None:
    """Display raw contents of a file from a GitHub repository.

    Examples:
        gh-llm cat octocat/Hello-World/README.md
        gh-llm cat octocat/Hello-World README.md
        gh-llm cat octocat/Hello-World/src/main.py --ref main
    """
    try:
        owner, repo_name, parsed_path = parse_repo_and_path(repo)
    except ValueError:
        _err("Repository must be in format 'owner/repo' or 'owner/repo/path'")
        raise typer.Exit(1)

    # Explicit path arg takes precedence; otherwise use path embedded in repo arg
    effective_path = path if path else parsed_path

    if not effective_path:
        _err('File path is required. Use: gh-llm cat owner/repo/path')
        raise typer.Exit(1)

    require_token()
    client = get_client()

    with handle_github_errors(f"File '{effective_path}' in {owner}/{repo_name}"):
        content = asyncio.run(client.get_file_content(owner, repo_name, effective_path, ref))

    print(content, end='')


@app.command()
def status() -> None:
    """Check the current configuration status."""
    if config.has_token():
        print('Token: Configured')
        print(f'Location: {config.get_token_path()}')
    else:
        print('Token: Not configured')
        print("Run 'gh-llm setup' to configure.")


def _format_size(size: int) -> str:
    """Format file size in human-readable format."""
    if size < 1024:
        return f'{size}B'
    fsize = float(size)
    for unit in ['KB', 'MB', 'GB', 'TB']:
        fsize /= 1024
        if fsize < 1024:
            return f'{fsize:.1f}{unit}'
    return f'{fsize:.1f}TB'
