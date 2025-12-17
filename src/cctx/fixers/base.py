"""Base classes for Living Context fixers.

Provides core abstractions for implementing fixers that can automatically
resolve validation issues detected by validators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from cctx.validators.base import FixableIssue


@dataclass
class FixResult:
    """Result of a fixer execution.

    Attributes:
        success: Whether the fix was applied successfully.
        message: Human-readable description of what happened.
        files_modified: List of file paths that were created or modified.
        files_deleted: List of file paths that were deleted.
    """

    success: bool
    message: str
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)


class BaseFixer(ABC):
    """Abstract base class for all fixers.

    Fixers implement the fix framework's plugin architecture,
    providing automated solutions for validation issues.

    Attributes:
        project_root: Root directory of the project being fixed.
        db_path: Path to the Living Context knowledge database.
    """

    # The fix_id this fixer handles (must be set by subclasses)
    fix_id: str = ""

    def __init__(self, project_root: Path, db_path: Path) -> None:
        """Initialize fixer.

        Args:
            project_root: Root directory of the project.
            db_path: Path to the Living Context knowledge database.
        """
        self.project_root = project_root
        self.db_path = db_path

    @abstractmethod
    def fix(self, issue: FixableIssue) -> FixResult:
        """Apply a fix for the given issue.

        Must be implemented by subclasses to perform specific fix logic.
        Fixers should be idempotent - safe to run multiple times.

        Args:
            issue: The fixable issue to resolve.

        Returns:
            FixResult containing the outcome and affected files.
        """

    def can_fix(self, issue: FixableIssue) -> bool:
        """Check if this fixer can handle the given issue.

        Default implementation checks if issue.fix_id matches this fixer's fix_id.

        Args:
            issue: The issue to check.

        Returns:
            True if this fixer can handle the issue.
        """
        return issue.fix_id == self.fix_id

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path to an absolute path.

        Args:
            relative_path: Path relative to project root.

        Returns:
            Absolute path.
        """
        return self.project_root / relative_path
