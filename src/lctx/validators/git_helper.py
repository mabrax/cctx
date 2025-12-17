"""Git utilities for accessing file metadata from version control.

Provides functions to query git history for file modification times
and recent changes, with fallback to filesystem metadata.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def get_file_mtime_git(path: Path) -> datetime | None:
    """Get file modification time from git history.

    Queries git log to find the most recent commit timestamp for a file.
    Falls back to filesystem modification time if the file is not tracked by git.

    Args:
        path: Path to the file to check.

    Returns:
        datetime of the most recent commit, or None if file is not tracked by git
        or git command fails.
    """
    try:
        # Get the most recent commit timestamp in ISO format
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ai", "--", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not result.stdout.strip():
            # File not in git or git command failed
            return None

        # Parse ISO 8601 format: "2025-01-15 10:30:45 +0000"
        timestamp_str = result.stdout.strip()
        # Use fromisoformat with the timestamp (replacing space with T)
        dt = datetime.fromisoformat(timestamp_str.replace(" ", "T", 1))
        return dt
    except (subprocess.SubprocessError, ValueError, OSError):
        # git not available, file not tracked, or parsing error
        return None


def get_file_mtime_fs(path: Path) -> datetime:
    """Get file modification time from filesystem.

    Reads the modification time directly from the file's metadata.

    Args:
        path: Path to the file to check.

    Returns:
        datetime of the file's last modification.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If file metadata cannot be read.
    """
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime)


def has_changes_since(path: Path, since_date: datetime) -> bool:
    """Check if file has commits since a given date.

    Queries git log to find commits for a file after the specified date.

    Args:
        path: Path to the file to check.
        since_date: Cutoff datetime. Returns True if any commits exist after this date.

    Returns:
        True if file has commits since the given date, False otherwise.
        Returns False if file is not tracked by git or git command fails.
    """
    try:
        # Format date for git since parameter (ISO 8601 format)
        since_str = since_date.isoformat()

        # Check if there are any commits since the date
        result = subprocess.run(
            ["git", "log", f"--since={since_str}", "--oneline", "--", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # git command failed or file not in git
            return False

        # If there's any output, there are commits since the date
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        # git not available or other error
        return False
