"""Tests for cctx.validators.git_helper module."""

from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cctx.validators.git_helper import (
    get_file_mtime_fs,
    get_file_mtime_git,
    has_changes_since,
)


class TestGetFileMtimeFs:
    """Tests for get_file_mtime_fs function."""

    def test_get_existing_file_mtime(self) -> None:
        """Test getting mtime of an existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            mtime = get_file_mtime_fs(temp_path)
            assert isinstance(mtime, datetime)
            # Verify it's recent (within last minute)
            now = datetime.now()
            assert (now - mtime).total_seconds() < 60
        finally:
            temp_path.unlink()

    def test_nonexistent_file_raises(self) -> None:
        """Test that nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_file_mtime_fs(Path("/nonexistent/path/file.txt"))

    def test_mtime_is_datetime(self) -> None:
        """Test that returned mtime is a datetime object."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            mtime = get_file_mtime_fs(temp_path)
            assert isinstance(mtime, datetime)
        finally:
            temp_path.unlink()


class TestGetFileMtimeGit:
    """Tests for get_file_mtime_git function."""

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_git_mtime_success(self, mock_run: MagicMock) -> None:
        """Test successfully getting file mtime from git."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2025-01-15 10:30:45 +0000\n",
        )
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_git_mtime_not_in_git(self, mock_run: MagicMock) -> None:
        """Test when file is not tracked by git."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
        )
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is None

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_git_mtime_git_error(self, mock_run: MagicMock) -> None:
        """Test when git command returns error."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
        )
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is None

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_git_mtime_subprocess_error(self, mock_run: MagicMock) -> None:
        """Test when subprocess raises an error."""
        mock_run.side_effect = subprocess.SubprocessError("git not found")
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is None

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_git_mtime_parse_error(self, mock_run: MagicMock) -> None:
        """Test when timestamp parsing fails."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid timestamp\n",
        )
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is None

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_git_command_called_with_correct_args(self, mock_run: MagicMock) -> None:
        """Test that git log command is called with correct arguments."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2025-01-15 10:30:45 +0000\n",
        )
        test_path = Path("src/systems/audio/file.md")
        get_file_mtime_git(test_path)

        # Verify subprocess.run was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "log", "-1", "--format=%ai", "--", str(test_path)]

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_git_mtime_with_timezone(self, mock_run: MagicMock) -> None:
        """Test parsing git timestamp with different timezone."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2025-01-15 14:30:45 +0100\n",
        )
        result = get_file_mtime_git(Path("test/file.txt"))
        assert result is not None
        assert isinstance(result, datetime)


class TestHasChangesSince:
    """Tests for has_changes_since function."""

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_has_changes_since_true(self, mock_run: MagicMock) -> None:
        """Test when file has changes since date."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc1234 Fix: something\n",
        )
        since_date = datetime(2025, 1, 1, 0, 0, 0)
        result = has_changes_since(Path("test/file.txt"), since_date)
        assert result is True

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_has_changes_since_false(self, mock_run: MagicMock) -> None:
        """Test when file has no changes since date."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
        )
        since_date = datetime(2025, 1, 1, 0, 0, 0)
        result = has_changes_since(Path("test/file.txt"), since_date)
        assert result is False

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_has_changes_since_git_error(self, mock_run: MagicMock) -> None:
        """Test when git command returns error."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
        )
        since_date = datetime(2025, 1, 1, 0, 0, 0)
        result = has_changes_since(Path("test/file.txt"), since_date)
        assert result is False

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_has_changes_since_subprocess_error(self, mock_run: MagicMock) -> None:
        """Test when subprocess raises an error."""
        mock_run.side_effect = subprocess.SubprocessError("git not found")
        since_date = datetime(2025, 1, 1, 0, 0, 0)
        result = has_changes_since(Path("test/file.txt"), since_date)
        assert result is False

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_has_changes_since_multiple_commits(self, mock_run: MagicMock) -> None:
        """Test with multiple commits."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc1234 First commit\ndef5678 Second commit\nghi9012 Third commit\n",
        )
        since_date = datetime(2025, 1, 1, 0, 0, 0)
        result = has_changes_since(Path("test/file.txt"), since_date)
        assert result is True

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_git_command_called_with_correct_args(self, mock_run: MagicMock) -> None:
        """Test that git log command is called with correct arguments."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
        )
        test_path = Path("src/systems/audio/file.md")
        since_date = datetime(2025, 1, 15, 10, 30, 45)
        has_changes_since(test_path, since_date)

        # Verify subprocess.run was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # The command should be git log with --since parameter
        assert call_args[0][0][0] == "git"
        assert call_args[0][0][1] == "log"
        assert any("--since" in str(arg) for arg in call_args[0][0])


class TestIntegration:
    """Integration tests with real files (not mocked)."""

    def test_get_file_mtime_fs_with_real_file(self) -> None:
        """Test filesystem mtime with a real temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)

        try:
            mtime = get_file_mtime_fs(temp_path)
            assert isinstance(mtime, datetime)
            # Verify it's a sensible datetime
            now = datetime.now()
            assert mtime <= now
        finally:
            temp_path.unlink()

    @patch("cctx.validators.git_helper.subprocess.run")
    def test_get_file_mtime_git_fallback_to_fs_not_needed(self, mock_run: MagicMock) -> None:
        """Test that get_file_mtime_git returns None when file not in git."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )
            result = get_file_mtime_git(temp_path)
            # Should return None because git output is empty
            assert result is None
        finally:
            temp_path.unlink()
