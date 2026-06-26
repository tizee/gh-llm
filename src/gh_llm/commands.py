"""CLI commands for gh-llm."""

import sys
import json
import asyncio
import subprocess
from typing import NoReturn
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

app = typer.Typer(
    help='gh-llm: Local-first GitHub repository browsing tool for LLMs',
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)

# Exit codes for distinct failure modes
EXIT_NOT_FOUND = 2
EXIT_RATE_LIMIT = 3
EXIT_AUTH = 4
EXIT_NETWORK = 5


@app.callback(invoke_without_command=True, no_args_is_help=True)
def _version_callback(  # pyright: ignore[reportUnusedFunction]
    version: bool = typer.Option(
        False,
        '--version',
        '-V',
        help='Show version and exit.',
    ),
) -> None:
    if version:
        from gh_llm import __version__

        print(f'gh-llm {__version__}')
        raise typer.Exit()


def _err(msg: str, exit_code: int = 1) -> NoReturn:
    """Print error message to stderr and exit."""
    _print_error(msg, exit_code=exit_code)


def require_token() -> None:
    """Ensure a token is configured, or exit with an error."""
    if not config.has_token():
        _err("No token configured. Run 'gh-llm setup' first.", EXIT_AUTH)


def _print_error(msg: str, json_output: bool = False, error_code: str = '', exit_code: int = 1) -> NoReturn:
    """Print error message and exit. Uses JSON format when json_output is True."""
    if json_output:
        error_obj: dict[str, str] = {'error': error_code, 'message': msg}
        print(json.dumps(error_obj), file=sys.stderr)
    else:
        print(f'Error: {msg}', file=sys.stderr)
    raise typer.Exit(exit_code)


@contextmanager
def handle_github_errors(resource_desc: str, json_output: bool = False) -> Iterator[None]:
    """Catch GitHub API errors and print user-friendly messages."""
    try:
        yield
    except NotFoundError:
        _print_error(f'{resource_desc} not found', json_output, 'not_found', EXIT_NOT_FOUND)
    except RateLimitError as e:
        _print_error(str(e), json_output, 'rate_limit', EXIT_RATE_LIMIT)
        if not json_output:
            print("Run 'gh-llm setup' to configure a token.", file=sys.stderr)
    except AuthenticationError as e:
        _print_error(str(e), json_output, 'auth', EXIT_AUTH)
        if not json_output:
            print("Run 'gh-llm setup' to reconfigure your token.", file=sys.stderr)
    except GitHubError as e:
        _print_error(str(e), json_output, 'github_error', 1)


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
        except subprocess.CalledProcessError:
            _err(
                "Failed to get token from 'gh auth token'. "
                'Please provide a token manually with --token.'
            )

    if not token:
        _err('No token provided.')

    # Validate token format (basic check)
    if len(token) < 10:
        _err('Token appears to be invalid (too short).')

    # Save the token
    config.save_token(token)
    print('Token saved successfully.', file=sys.stderr)
    print(f'Stored in: {config.get_token_path()}', file=sys.stderr)


@app.command('ls', no_args_is_help=True)
@app.command('tree', no_args_is_help=True)
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
        _print_error(
            "Repository must be in format 'owner/repo' or 'owner/repo/path'",
            json_output,
            'invalid_input',
        )

    # Explicit path arg takes precedence; otherwise use path embedded in repo arg
    effective_path = path if path else parsed_path

    require_token()
    client = get_client()

    with handle_github_errors(f"Path '{effective_path}' in {owner}/{repo_name}", json_output):
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

    # Sort: directories first, then by name
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.type != 'dir', e.name.lower()),
    )

    # Build rows and compute size column width
    rows: list[tuple[str, bool, str]] = []  # (size_str, is_dir, display_name)
    for entry in sorted_entries:
        is_dir = entry.type == 'dir'
        display_name = f'{entry.name}/' if is_dir else entry.name
        size_str = '-' if is_dir else _format_size(entry.size) if entry.size is not None else '-'
        rows.append((size_str, is_dir, display_name))

    max_size_w = max((len(r[0]) for r in rows), default=0)

    for size_str, _is_dir, display_name in rows:
        print(f'{size_str:>{max_size_w}}  {display_name}')


@app.command('cat', no_args_is_help=True)
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
    lines: int = typer.Option(
        0,
        '--lines',
        '-n',
        help='Output only the first N lines (0 = all)',
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

    # Explicit path arg takes precedence; otherwise use path embedded in repo arg
    effective_path = path if path else parsed_path

    if not effective_path:
        _err('File path is required. Use: gh-llm cat owner/repo/path')

    require_token()
    client = get_client()

    with handle_github_errors(f"File '{effective_path}' in {owner}/{repo_name}"):
        content = asyncio.run(client.get_file_content(owner, repo_name, effective_path, ref))

    if lines > 0:
        content_lines = content.splitlines()
        content = '\n'.join(content_lines[:lines])
        if len(content_lines) > lines:
            content += '\n'

    print(content, end='')


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        '--json',
        help='Output as JSON for machine consumption',
    ),
) -> None:
    """Check the current configuration status."""
    if json_output:
        if config.has_token():
            token = config.get_token()
            masked = token[:4] + '****' if token and len(token) > 4 else 'none'
            output = {
                'configured': True,
                'token_masked': masked,
                'config_dir': str(config.get_config_dir()),
            }
        else:
            output = {
                'configured': False,
                'token_masked': None,
                'config_dir': str(config.get_config_dir()),
            }
        print(json.dumps(output, indent=2))
        return

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
