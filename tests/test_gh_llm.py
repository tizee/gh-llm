"""Tests for gh-llm."""

import pytest

from gh_llm import config
from gh_llm.commands import parse_repo


def test_config_dir():
    """Test that config directory is created properly."""
    config_dir = config.get_config_dir()
    assert config_dir.name == "gh-llm"


def test_token_path():
    """Test token path resolution."""
    token_path = config.get_token_path()
    assert token_path.name == "token"
    assert token_path.parent.name == "gh-llm"


class TestParseRepo:
    """Tests for parse_repo: supports owner/repo and full GitHub URLs."""

    def test_owner_slash_repo(self):
        assert parse_repo('rien7/github-llm') == ('rien7', 'github-llm')

    def test_full_https_url(self):
        assert parse_repo('https://github.com/rien7/github-llm') == ('rien7', 'github-llm')

    def test_full_url_trailing_slash(self):
        assert parse_repo('https://github.com/rien7/github-llm/') == ('rien7', 'github-llm')

    def test_http_url(self):
        assert parse_repo('http://github.com/rien7/github-llm') == ('rien7', 'github-llm')

    def test_invalid_bare_name(self):
        with pytest.raises(ValueError, match='owner/repo'):
            parse_repo('just-a-name')

    def test_invalid_url_missing_repo(self):
        with pytest.raises(ValueError, match='owner/repo'):
            parse_repo('https://github.com/rien7')

    def test_empty_string(self):
        with pytest.raises(ValueError, match='owner/repo'):
            parse_repo('')
