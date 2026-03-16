"""Configuration management for gh-llm."""

from pathlib import Path

import platformdirs


def get_config_dir() -> Path:
    """Get the configuration directory for gh-llm."""
    return Path(platformdirs.user_config_dir('gh-llm'))


def get_token_path() -> Path:
    """Get the path to the stored token file."""
    return get_config_dir() / 'token'


def get_token() -> str | None:
    """Load the stored GitHub token.

    Returns:
        The stored token, or None if not configured.
    """
    token_path = get_token_path()
    if not token_path.exists():
        return None
    token = token_path.read_text().strip()
    return token or None


def save_token(token: str) -> None:
    """Save the GitHub token to the config directory.

    Args:
        token: The GitHub token to save.

    Raises:
        OSError: If the config directory or token file cannot be written.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    token_path = get_token_path()
    token_path.write_text(token.strip())
    # Set permissions to be readable only by the owner
    token_path.chmod(0o600)


def clear_token() -> None:
    """Remove the stored GitHub token."""
    token_path = get_token_path()
    if token_path.exists():
        token_path.unlink()


def has_token() -> bool:
    """Check if a valid token is configured."""
    return bool(get_token())
