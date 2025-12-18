"""Path filtering utilities for Living Context validators.

Provides functions to find .ctx directories while filtering out paths that
should not be scanned (virtual environments, test fixtures, etc.).
"""

from __future__ import annotations

from pathlib import Path

# Directories to exclude when scanning for .ctx directories
IGNORED_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "site-packages",
    }
)

# Path segments that indicate test fixtures (should be excluded)
FIXTURE_INDICATORS = frozenset(
    {
        "fixtures",
        "fixture",
        "test_data",
        "testdata",
    }
)


def _should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped during scanning.

    Args:
        path: Path to check.

    Returns:
        True if the path should be skipped.
    """
    parts = set(path.parts)

    # Skip if any part is in ignored directories
    if parts & IGNORED_DIRS:
        return True

    # Skip if path contains fixture indicators
    return bool(parts & FIXTURE_INDICATORS)


def find_ctx_directories(project_root: Path) -> list[Path]:
    """Find all .ctx directories in the project, excluding ignored paths.

    Filters out:
    - .venv/, venv/, node_modules/, __pycache__/, .git/
    - dist/, build/, .tox/, .nox/, .mypy_cache/, .pytest_cache/
    - Any path containing /fixtures/, /fixture/, /test_data/, /testdata/

    Args:
        project_root: Root directory of the project to scan.

    Returns:
        Sorted list of .ctx directory paths.
    """
    ctx_dirs: list[Path] = []

    for ctx_dir in project_root.rglob(".ctx"):
        if not ctx_dir.is_dir():
            continue

        # Get the relative path from project root for checking
        try:
            rel_path = ctx_dir.relative_to(project_root)
        except ValueError:
            continue

        if _should_skip_path(rel_path):
            continue

        ctx_dirs.append(ctx_dir)

    return sorted(ctx_dirs)
