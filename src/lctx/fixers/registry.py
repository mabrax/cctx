"""Fixer registry for mapping fix_ids to fixer classes.

The registry provides a central lookup mechanism for finding the appropriate
fixer for a given fix_id. Fixers register themselves by their fix_id.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lctx.fixers.base import BaseFixer, FixResult
from lctx.validators.base import FixableIssue

if TYPE_CHECKING:
    pass


class FixerRegistry:
    """Registry that maps fix_ids to fixer classes.

    Provides a centralized way to look up and instantiate fixers
    based on the fix_id of a FixableIssue.

    Example:
        >>> registry = FixerRegistry()
        >>> registry.register(SnapshotFixer)
        >>> fixer = registry.get_fixer("missing_snapshot", project_root, db_path)
        >>> if fixer:
        ...     result = fixer.fix(issue)
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._fixers: dict[str, type[BaseFixer]] = {}

    def register(self, fixer_class: type[BaseFixer]) -> None:
        """Register a fixer class by its fix_id.

        Args:
            fixer_class: A BaseFixer subclass to register.

        Raises:
            ValueError: If the fixer has no fix_id or if a fixer with
                the same fix_id is already registered.
        """
        fix_id = fixer_class.fix_id
        if not fix_id:
            raise ValueError(
                f"Fixer class {fixer_class.__name__} has no fix_id defined"
            )
        if fix_id in self._fixers:
            raise ValueError(
                f"Fixer for fix_id '{fix_id}' already registered: "
                f"{self._fixers[fix_id].__name__}"
            )
        self._fixers[fix_id] = fixer_class

    def get_fixer(
        self, fix_id: str, project_root: Path, db_path: Path
    ) -> BaseFixer | None:
        """Get an instantiated fixer for the given fix_id.

        Args:
            fix_id: The fix identifier to look up.
            project_root: Root directory of the project.
            db_path: Path to the knowledge database.

        Returns:
            An instantiated fixer if one is registered for the fix_id,
            None otherwise.
        """
        fixer_class = self._fixers.get(fix_id)
        if fixer_class is None:
            return None
        return fixer_class(project_root, db_path)

    def has_fixer(self, fix_id: str) -> bool:
        """Check if a fixer is registered for the given fix_id.

        Args:
            fix_id: The fix identifier to check.

        Returns:
            True if a fixer is registered for this fix_id.
        """
        return fix_id in self._fixers

    def list_fix_ids(self) -> list[str]:
        """List all registered fix_ids.

        Returns:
            Sorted list of registered fix_ids.
        """
        return sorted(self._fixers.keys())

    def apply_fix(
        self, issue: FixableIssue, project_root: Path, db_path: Path
    ) -> FixResult:
        """Apply a fix for the given issue using the appropriate fixer.

        Convenience method that looks up the fixer and applies the fix.

        Args:
            issue: The fixable issue to resolve.
            project_root: Root directory of the project.
            db_path: Path to the knowledge database.

        Returns:
            FixResult from the fixer, or a failure result if no fixer
            is registered for the issue's fix_id.
        """
        fixer = self.get_fixer(issue.fix_id, project_root, db_path)
        if fixer is None:
            return FixResult(
                success=False,
                message=f"No fixer registered for fix_id: {issue.fix_id}",
            )
        return fixer.fix(issue)


# Global registry instance - populated by __init__.py
_global_registry: FixerRegistry | None = None


def get_global_registry() -> FixerRegistry:
    """Get the global fixer registry.

    Returns a singleton registry instance that is populated with all
    built-in fixers.

    Returns:
        The global FixerRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = _create_default_registry()
    return _global_registry


def _create_default_registry() -> FixerRegistry:
    """Create and populate the default registry with built-in fixers.

    Returns:
        A FixerRegistry populated with all built-in fixers.
    """
    # Import here to avoid circular imports
    from lctx.fixers.adr_fixer import AdrFixer
    from lctx.fixers.graph_fixer import GraphFixer
    from lctx.fixers.scaffolding_fixer import (
        MissingCtxDirFixer,
        MissingTemplateFileFixer,
    )
    from lctx.fixers.snapshot_fixer import SnapshotFixer

    registry = FixerRegistry()
    registry.register(SnapshotFixer)
    registry.register(GraphFixer)
    registry.register(MissingCtxDirFixer)
    registry.register(MissingTemplateFileFixer)
    registry.register(AdrFixer)
    return registry
