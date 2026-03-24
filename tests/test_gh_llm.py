"""Tests for gh-llm."""

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gh_llm import config
from gh_llm.github import GitHubEntry
from gh_llm.commands import app, parse_repo, parse_repo_and_path


def test_config_dir():
    """Test that config directory is created properly."""
    config_dir = config.get_config_dir()
    assert config_dir.name == 'gh-llm'


def test_token_path():
    """Test token path resolution."""
    token_path = config.get_token_path()
    assert token_path.name == 'token'
    assert token_path.parent.name == 'gh-llm'


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


class TestParseRepoAndPath:
    """parse_repo_and_path splits 'owner/repo/path...' into (owner, repo, path)."""

    def test_owner_repo_only(self):
        assert parse_repo_and_path('octocat/Hello-World') == ('octocat', 'Hello-World', '')

    def test_owner_repo_with_file(self):
        assert parse_repo_and_path('octocat/Hello-World/README.md') == (
            'octocat',
            'Hello-World',
            'README.md',
        )

    def test_owner_repo_with_nested_path(self):
        assert parse_repo_and_path('facebook/react/src/hooks/useState.js') == (
            'facebook',
            'react',
            'src/hooks/useState.js',
        )

    def test_full_url_with_path(self):
        assert parse_repo_and_path('https://github.com/octocat/Hello-World/src/main.py') == (
            'octocat',
            'Hello-World',
            'src/main.py',
        )

    def test_full_url_repo_only(self):
        assert parse_repo_and_path('https://github.com/octocat/Hello-World') == (
            'octocat',
            'Hello-World',
            '',
        )

    def test_trailing_slash_stripped(self):
        assert parse_repo_and_path('octocat/Hello-World/src/') == ('octocat', 'Hello-World', 'src')

    def test_invalid_single_segment(self):
        with pytest.raises(ValueError, match='owner/repo'):
            parse_repo_and_path('just-a-name')

    def test_empty_string(self):
        with pytest.raises(ValueError, match='owner/repo'):
            parse_repo_and_path('')


# -- CLI command behavior tests --

runner = CliRunner()


def _make_entries() -> list[GitHubEntry]:
    return [
        GitHubEntry(name='README.md', path='README.md', type='file', sha='abc', size=1234),
        GitHubEntry(name='src', path='src', type='dir', sha='def', size=None),
        GitHubEntry(name='setup.py', path='setup.py', type='file', sha='ghi', size=567),
    ]


class TestLsOutput:
    """ls outputs plain text lines, not rich tables."""

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_plain_text_output(self, mock_run: Any, _get: Any, _has: Any):
        mock_run.return_value = _make_entries()
        result = runner.invoke(app, ['ls', 'octocat/Hello-World'])
        assert result.exit_code == 0
        lines = result.output.strip().split('\n')
        # dirs first, then files, each line is plain text
        assert 'dir' in lines[0]
        assert 'src' in lines[0]
        assert 'file' in lines[1]

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_no_rich_table_markup(self, mock_run: Any, _get: Any, _has: Any):
        """Output must not contain box-drawing or ANSI escape sequences."""
        mock_run.return_value = _make_entries()
        result = runner.invoke(app, ['ls', 'octocat/Hello-World'])
        assert result.exit_code == 0
        # Rich tables contain box-drawing characters like ─ │ ┌ etc.
        for char in ['─', '│', '┌', '┐', '└', '┘', '├', '┤']:
            assert char not in result.output, f'Found table char {char!r} in output'

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_json_output_unchanged(self, mock_run: Any, _get: Any, _has: Any):
        mock_run.return_value = _make_entries()
        result = runner.invoke(app, ['ls', 'octocat/Hello-World', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]['name'] in ('README.md', 'src', 'setup.py')


class TestLsUnifiedPath:
    """ls accepts owner/repo/path as a single argument."""

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_ls_with_path_in_repo_arg(self, mock_run: Any, _get: Any, _has: Any):
        mock_run.return_value = _make_entries()
        result = runner.invoke(app, ['ls', 'octocat/Hello-World/src'])
        assert result.exit_code == 0


class TestCatUnifiedPath:
    """cat accepts owner/repo/path as a single argument."""

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_cat_single_arg_path(self, mock_run: Any, _get: Any, _has: Any):
        mock_run.return_value = 'print("hello")\n'
        result = runner.invoke(app, ['cat', 'octocat/Hello-World/main.py'])
        assert result.exit_code == 0
        assert 'print("hello")' in result.output

    @patch('gh_llm.commands.config.has_token', return_value=True)
    @patch('gh_llm.commands.config.get_token', return_value='fake-token')
    @patch('gh_llm.commands.asyncio.run')
    def test_cat_still_works_with_two_args(self, mock_run: Any, _get: Any, _has: Any):
        mock_run.return_value = 'content\n'
        result = runner.invoke(app, ['cat', 'octocat/Hello-World', 'README.md'])
        assert result.exit_code == 0
        assert 'content' in result.output


class TestErrorOutputPlain:
    """Errors go to stderr as plain text, no rich markup."""

    def test_invalid_repo_plain_error(self):
        result = runner.invoke(app, ['ls', 'bad-input'])
        assert result.exit_code == 1
        # Should contain "Error" but no rich markup
        full = result.output + (result.stderr if hasattr(result, 'stderr') else '')
        assert '[red]' not in full
        assert '[/red]' not in full
