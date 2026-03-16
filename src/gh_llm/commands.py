"""CLI commands for gh-llm."""

import json
import asyncio
import subprocess
from contextlib import contextmanager
from collections.abc import Iterator

import typer
import rich.table
import rich.console

from gh_llm import config
from gh_llm.github import (
    GitHubError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
    AuthenticationError,
)

app = typer.Typer(help='gh-llm: Local-first GitHub repository browsing tool for LLMs')
console = rich.console.Console()


def require_token() -> None:
    """Ensure a token is configured, or exit with an error."""
    if not config.has_token():
        console.print("[red]Error: No token configured.[/red] Run 'gh-llm setup' first.")
        raise typer.Exit(1)


@contextmanager
def handle_github_errors(resource_desc: str) -> Iterator[None]:
    """Catch GitHub API errors and print user-friendly messages."""
    try:
        yield
    except NotFoundError:
        console.print(f'[red]Error: {resource_desc} not found[/red]')
        raise typer.Exit(1)
    except RateLimitError as e:
        console.print(f'[red]Error: {e}[/red]')
        console.print("[yellow]Run 'gh-llm setup' to configure a token.[/yellow]")
        raise typer.Exit(1)
    except AuthenticationError as e:
        console.print(f'[red]Error: {e}[/red]')
        console.print("[yellow]Run 'gh-llm setup' to reconfigure your token.[/yellow]")
        raise typer.Exit(1)
    except GitHubError as e:
        console.print(f'[red]Error: {e}[/red]')
        raise typer.Exit(1)


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
            repo = repo[len(prefix):]
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
        console.print('[yellow]Token already configured.[/yellow] Use --force to overwrite.')
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
            console.print("[dim]Retrieved token from 'gh auth token'[/dim]")
        except FileNotFoundError:
            console.print(
                '[yellow]gh CLI not found.[/yellow] Please provide a token manually with --token.'
            )
            raise typer.Exit(1)
        except subprocess.CalledProcessError:
            console.print(
                "[red]Failed to get token from 'gh auth token'.[/red] "
                'Please provide a token manually with --token.'
            )
            raise typer.Exit(1)

    if not token:
        console.print('[red]No token provided.[/red]')
        raise typer.Exit(1)

    # Validate token format (basic check)
    if len(token) < 10:
        console.print('[red]Token appears to be invalid (too short).[/red]')
        raise typer.Exit(1)

    # Save the token
    config.save_token(token)
    console.print('[green]Token saved successfully![/green]')
    console.print(f'[dim]Stored in: {config.get_token_path()}[/dim]')


@app.command('ls')
@app.command('tree')
def list_directory(
    repo: str = typer.Argument(..., help="Repository as 'owner/repo' or full GitHub URL"),
    path: str = typer.Argument('', help='Path within the repository'),
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
        gh-llm ls octocat/Hello-World --ref main
        gh-llm ls octocat/Hello-World src
    """
    try:
        owner, repo_name = parse_repo(repo)
    except ValueError:
        console.print(
            "[red]Error: Repository must be in format 'owner/repo'"
            " or a full GitHub URL[/red]"
        )
        raise typer.Exit(1)

    require_token()
    client = get_client()

    with handle_github_errors(f"Path '{path}' in {repo}"):
        entries = asyncio.run(client.get_repo_contents(owner, repo_name, path, ref))

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

    # Display as table
    table = rich.table.Table(
        show_header=True,
        header_style='bold',
    )
    table.add_column('Type', style='cyan', width=4)
    table.add_column('Name')
    table.add_column('Size', justify='right')

    for entry in sorted_entries:
        entry_type = 'dir' if entry.type == 'dir' else 'file'
        size_str = '-' if entry.size is None else _format_size(entry.size)
        table.add_row(entry_type, entry.name, size_str)

    console.print(table)


@app.command('cat')
def cat_file(
    repo: str = typer.Argument(..., help="Repository as 'owner/repo' or full GitHub URL"),
    path: str = typer.Argument(..., help='Path to the file'),
    ref: str = typer.Option(
        None,
        '--ref',
        '-r',
        help='Git reference (branch, tag, or commit SHA)',
    ),
) -> None:
    """Display raw contents of a file from a GitHub repository.

    Examples:
        gh-llm cat octocat/Hello-World README.md
        gh-llm cat octocat/Hello-World src/main.py --ref main
    """
    try:
        owner, repo_name = parse_repo(repo)
    except ValueError:
        console.print(
            "[red]Error: Repository must be in format 'owner/repo'"
            " or a full GitHub URL[/red]"
        )
        raise typer.Exit(1)

    require_token()
    client = get_client()

    with handle_github_errors(f"File '{path}' in {repo}"):
        content = asyncio.run(client.get_file_content(owner, repo_name, path, ref))

    print(content, end='')


@app.command()
def status() -> None:
    """Check the current configuration status."""
    if config.has_token():
        console.print('[green]Token: Configured[/green]')
        console.print(f'[dim]Location: {config.get_token_path()}[/dim]')
    else:
        console.print('[yellow]Token: Not configured[/yellow]')
        console.print("[dim]Run 'gh-llm setup' to configure.[/dim]")


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
