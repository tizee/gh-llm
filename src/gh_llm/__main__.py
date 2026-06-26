"""Entry point for gh-llm CLI."""

import sys

from gh_llm.github import (
    GitHubError,
    NotFoundError,
    RateLimitError,
    AuthenticationError,
)
from gh_llm.commands import EXIT_AUTH, EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_RATE_LIMIT, app

if __name__ == '__main__':
    try:
        app()
    except NotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)
    except RateLimitError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(EXIT_RATE_LIMIT)
    except AuthenticationError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(EXIT_AUTH)
    except GitHubError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        msg = str(e) or type(e).__name__
        print(f'Error: {msg}', file=sys.stderr)
        # Try to detect network-level httpx errors
        exit_code = EXIT_NETWORK if 'httpx' in type(e).__module__ else 1
        sys.exit(exit_code)
