"""GitHub API client for gh-llm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from dataclasses import dataclass

if TYPE_CHECKING:
    import httpx


GITHUB_API_BASE = 'https://api.github.com'
GITHUB_API_HEADERS = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'gh-llm',
    'X-GitHub-Api-Version': '2022-11-28',
}


@dataclass
class RepoRef:
    """Represents a GitHub repository reference."""

    owner: str
    name: str


@dataclass
class GitHubEntry:
    """Represents a file or directory entry in a repository."""

    name: str
    path: str
    type: str  # "file" or "dir"
    sha: str
    size: int | None = None
    download_url: str | None = None


class GitHubError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(GitHubError):
    """Raised when GitHub API rate limit is exceeded."""


class NotFoundError(GitHubError):
    """Raised when a repository or resource is not found."""


class AuthenticationError(GitHubError):
    """Raised when authentication fails."""


class GitHubClient:
    """Client for interacting with the GitHub API."""

    def __init__(self, token: str | None = None):
        """Initialize the GitHub client.

        Args:
            token: Optional GitHub token for authenticated requests.
        """
        self.token = token

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = dict(GITHUB_API_HEADERS)
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    async def get_repo_contents(
        self,
        owner: str,
        repo: str,
        path: str = '',
        ref: str | None = None,
    ) -> list[GitHubEntry]:
        """Get contents of a repository path.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: Path within the repository.
            ref: Git reference (branch, tag, or commit SHA).

        Returns:
            List of entries (files and directories).

        Raises:
            NotFoundError: If the path does not exist.
            RateLimitError: If the API rate limit is exceeded.
            AuthenticationError: If authentication fails.
            GitHubError: For other API errors.
        """
        import httpx

        url = f'{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}'
        params = {'ref': ref} if ref else None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._build_headers(),
                params=params,
            )
            self._handle_response_errors(response)

            data: Any = response.json()
            if isinstance(data, dict):
                # Single file - return as a list with one entry
                return [self._entry_from_dict(cast(dict[str, Any], data))]
            return [self._entry_from_dict(cast(dict[str, Any], item)) for item in data]

    async def get_repo_root(self, owner: str, repo: str) -> list[GitHubEntry]:
        """Get contents of the repository root.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            List of entries at the repository root.
        """
        return await self.get_repo_contents(owner, repo, '')

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        """Get raw content of a file.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: Path to the file.
            ref: Git reference (branch, tag, or commit SHA).

        Returns:
            Raw file content as string.
        """
        import base64

        import httpx

        url = f'{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}'
        params = {'ref': ref} if ref else None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._build_headers(),
                params=params,
            )
            self._handle_response_errors(response)

            data: Any = response.json()
            if data.get('content'):
                encoding = data.get('encoding', 'base64')
                if encoding == 'base64':
                    return base64.b64decode(data['content']).decode('utf-8')
                raise GitHubError(f'Unsupported content encoding: {encoding}')

            # For very large files, GitHub returns a download URL instead
            if data.get('download_url'):
                download_response = await client.get(data['download_url'])
                return download_response.text

            raise GitHubError('File content not available')

    def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle API response errors.

        Raises:
            NotFoundError: If the resource is not found.
            RateLimitError: If rate limited.
            AuthenticationError: If authentication fails.
            GitHubError: For other errors.
        """
        if response.status_code == 200:
            return

        if response.status_code == 404:
            raise NotFoundError('Resource not found', 404)

        # 403 with exhausted rate limit is a specific error;
        # other 403s (repo disabled, DMCA, IP block) fall through to generic error.
        if response.status_code == 403 and response.headers.get('x-ratelimit-remaining') == '0':
            raise RateLimitError(
                'GitHub API rate limit exceeded. '
                "Configure a token with 'gh-llm setup' for higher limits.",
                403,
            )

        if response.status_code == 401:
            raise AuthenticationError(
                "Authentication required. Run 'gh-llm setup' to configure your token.",
                401,
            )

        try:
            error_data: Any = response.json()
            message = error_data.get('message', 'Unknown error')
        except Exception:
            message = response.text or 'Unknown error'

        raise GitHubError(f'GitHub API error: {message}', response.status_code)

    def _entry_from_dict(self, data: dict[str, Any]) -> GitHubEntry:
        """Create a GitHubEntry from API response data."""
        return GitHubEntry(
            name=data['name'],
            path=data['path'],
            type='dir' if data['type'] == 'dir' else 'file',
            sha=data['sha'],
            size=data.get('size'),
            download_url=data.get('download_url'),
        )
