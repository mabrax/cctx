"""Fixer for missing or incomplete snapshot.md files.

Creates snapshot.md files from templates when they are missing from
a system's .ctx directory.
"""

from __future__ import annotations

from pathlib import Path

from lctx.fixers.base import BaseFixer, FixResult
from lctx.fixers.utils import derive_system_name
from lctx.template_manager import render_template
from lctx.validators.base import FixableIssue


class SnapshotFixer(BaseFixer):
    """Fixer for missing snapshot.md files.

    Creates a new snapshot.md from the template when one is missing
    from a system's .ctx directory.

    Fix parameters expected in FixableIssue.fix_params:
        - system_name (optional): Human-readable name for the system.
            Defaults to the directory name if not provided.
    """

    fix_id = "missing_snapshot"

    def fix(self, issue: FixableIssue) -> FixResult:
        """Create a missing snapshot.md file from template.

        Args:
            issue: The fixable issue containing the system path.

        Returns:
            FixResult indicating success or failure.
        """
        # Get the system path from the issue
        system_path = self._resolve_path(issue.system)
        ctx_dir = system_path / ".ctx"
        snapshot_path = ctx_dir / "snapshot.md"

        # Check if snapshot already exists (idempotency)
        if snapshot_path.exists():
            return FixResult(
                success=True,
                message=f"snapshot.md already exists at {snapshot_path}",
                files_modified=[],
            )

        # Ensure .ctx directory exists
        if not ctx_dir.exists():
            return FixResult(
                success=False,
                message=(
                    f".ctx directory does not exist at {ctx_dir}. "
                    "Run the missing_ctx_dir fixer first."
                ),
            )

        # Get system name from fix_params or derive from path
        system_name = issue.fix_params.get("system_name")
        if not system_name:
            # Use the directory name as a human-readable name
            system_name = derive_system_name(system_path)

        # Render the snapshot template
        try:
            content = render_template("snapshot", system_name=system_name)
        except (FileNotFoundError, ValueError) as e:
            return FixResult(
                success=False,
                message=f"Failed to render snapshot template: {e}",
            )

        # Write the snapshot file
        try:
            snapshot_path.write_text(content, encoding="utf-8")
        except OSError as e:
            return FixResult(
                success=False,
                message=f"Failed to write snapshot.md: {e}",
            )

        rel_path = str(snapshot_path.relative_to(self.project_root))
        return FixResult(
            success=True,
            message=f"Created snapshot.md from template at {rel_path}",
            files_modified=[rel_path],
        )
