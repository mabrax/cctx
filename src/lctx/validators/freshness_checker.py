"""Freshness checker for Living Context documentation.

Checks if documentation is stale relative to source code changes:
- Snapshot staleness: snapshot.md older than source files it documents
- Decision staleness: decisions.md not updated when new ADRs added
- Constraint drift: constraints.md unchanged after significant refactors
- Graph sync: graph.json older than system changes
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from lctx.validators.base import (
    BaseValidator,
    FixableIssue,
    ValidationIssue,
    ValidatorResult,
)
from lctx.validators.git_helper import get_file_mtime_fs, get_file_mtime_git
from lctx.validators.path_filter import find_ctx_directories


class FreshnessChecker(BaseValidator):
    """Checks if Living Context documentation is stale.

    Staleness thresholds:
    - snapshot.md: 7 days (core system overview should track changes)
    - decisions.md: 1 day (index should update when ADRs change)
    - constraints.md: 14 days (constraints change less frequently)
    - graph.json: 7 days (should reflect current architecture)
    """

    # Staleness thresholds in days
    SNAPSHOT_THRESHOLD_DAYS = 7
    DECISIONS_THRESHOLD_DAYS = 1
    CONSTRAINTS_THRESHOLD_DAYS = 14
    GRAPH_THRESHOLD_DAYS = 7

    # Severe staleness threshold (error level)
    SEVERE_STALENESS_DAYS = 30

    def validate(self) -> ValidatorResult:
        """Run freshness checks.

        Returns:
            ValidatorResult containing the validation outcome and any issues found.
        """
        issues: list[ValidationIssue] = []
        systems_checked = 0

        # Check global graph.json freshness
        issues.extend(self._check_graph_freshness())

        # Find all systems with .ctx directories
        systems = self._find_systems_with_ctx()

        for system_path in systems:
            systems_checked += 1
            rel_system = str(system_path.relative_to(self.project_root))

            # Get latest source file modification in system (excluding .ctx)
            latest_source_mtime = self._get_latest_source_mtime(system_path)

            if latest_source_mtime is None:
                continue  # No source files to compare against

            # Check snapshot.md freshness
            issues.extend(
                self._check_doc_freshness(
                    system_path / ".ctx" / "snapshot.md",
                    latest_source_mtime,
                    self.SNAPSHOT_THRESHOLD_DAYS,
                    rel_system,
                    "snapshot.md",
                )
            )

            # Check constraints.md freshness
            issues.extend(
                self._check_doc_freshness(
                    system_path / ".ctx" / "constraints.md",
                    latest_source_mtime,
                    self.CONSTRAINTS_THRESHOLD_DAYS,
                    rel_system,
                    "constraints.md",
                )
            )

            # Check decisions.md vs ADR freshness
            issues.extend(
                self._check_decisions_freshness(system_path, rel_system)
            )

        # Determine overall status
        has_errors = any(issue.severity == "error" for issue in issues)
        status: Literal["pass", "fail"] = "fail" if has_errors else "pass"

        return ValidatorResult(
            name="freshness-checker",
            status=status,
            issues=issues,
            systems_checked=systems_checked,
        )

    def _find_systems_with_ctx(self) -> list[Path]:
        """Find all directories containing .ctx subdirectories.

        Returns:
            List of paths to system directories with .ctx.
        """
        systems: list[Path] = []

        for ctx_dir in find_ctx_directories(self.project_root):
            # Exclude root .ctx directory
            if ctx_dir.parent != self.project_root:
                systems.append(ctx_dir.parent)

        return sorted(systems)

    def _get_file_mtime(self, path: Path) -> datetime | None:
        """Get file modification time, preferring git over filesystem.

        Args:
            path: Path to the file.

        Returns:
            datetime of last modification, or None if file doesn't exist.
        """
        if not path.exists():
            return None

        # Try git first
        git_mtime = get_file_mtime_git(path)
        if git_mtime is not None:
            return git_mtime

        # Fall back to filesystem
        try:
            return get_file_mtime_fs(path)
        except (FileNotFoundError, OSError):
            return None

    def _get_latest_source_mtime(self, system_path: Path) -> datetime | None:
        """Get the latest modification time of source files in a system.

        Excludes .ctx directory and common non-source patterns.

        Args:
            system_path: Path to the system directory.

        Returns:
            datetime of the most recently modified source file.
        """
        latest_mtime: datetime | None = None

        # Common source file extensions
        source_extensions = {
            ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go",
            ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
            ".cs", ".rb", ".php", ".vue", ".svelte",
            ".json", ".yaml", ".yml", ".mjs", ".cjs", ".sh", ".sql",
        }

        for file_path in system_path.rglob("*"):
            # Skip .ctx directory
            if ".ctx" in file_path.parts:
                continue

            # Skip non-files
            if not file_path.is_file():
                continue

            # Check if it's a source file
            if file_path.suffix not in source_extensions:
                continue

            mtime = self._get_file_mtime(file_path)
            if mtime is not None and (latest_mtime is None or mtime > latest_mtime):
                latest_mtime = mtime

        return latest_mtime

    def _check_doc_freshness(
        self,
        doc_path: Path,
        source_mtime: datetime,
        threshold_days: int,
        rel_system: str,
        doc_name: str,
    ) -> list[ValidationIssue]:
        """Check if a documentation file is stale relative to source.

        Args:
            doc_path: Path to the documentation file.
            source_mtime: Modification time of the most recent source file.
            threshold_days: Days after which the doc is considered stale.
            rel_system: Relative system path for issue reporting.
            doc_name: Name of the document for messages.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        if not doc_path.exists():
            return issues

        doc_mtime = self._get_file_mtime(doc_path)
        if doc_mtime is None:
            return issues

        # Ensure both times are timezone-aware for comparison
        if source_mtime.tzinfo is None:
            source_mtime = source_mtime.replace(tzinfo=timezone.utc)
        if doc_mtime.tzinfo is None:
            doc_mtime = doc_mtime.replace(tzinfo=timezone.utc)

        # Calculate staleness
        staleness = source_mtime - doc_mtime
        threshold = timedelta(days=threshold_days)
        severe_threshold = timedelta(days=self.SEVERE_STALENESS_DAYS)

        if staleness > threshold:
            # Determine severity and create issue
            if staleness > severe_threshold:
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="staleness",
                        severity="error",
                        message=f"{doc_name} is severely stale ({staleness.days} days behind source)",
                        file=doc_name,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="staleness",
                        severity="warning",
                        message=f"{doc_name} is {staleness.days} days older than source files",
                        file=doc_name,
                    )
                )

        return issues

    def _check_decisions_freshness(
        self, system_path: Path, rel_system: str
    ) -> list[ValidationIssue]:
        """Check if decisions.md is in sync with ADR files.

        Args:
            system_path: Path to the system directory.
            rel_system: Relative system path for issue reporting.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        ctx_path = system_path / ".ctx"
        decisions_path = ctx_path / "decisions.md"
        adr_dir = ctx_path / "adr"

        if not decisions_path.exists():
            return issues

        decisions_mtime = self._get_file_mtime(decisions_path)
        if decisions_mtime is None:
            return issues

        # Check if any ADR files are newer than decisions.md
        if adr_dir.exists():
            for adr_file in adr_dir.glob("*.md"):
                adr_mtime = self._get_file_mtime(adr_file)
                if adr_mtime is None:
                    continue

                # Ensure timezone awareness
                if adr_mtime.tzinfo is None:
                    adr_mtime = adr_mtime.replace(tzinfo=timezone.utc)
                if decisions_mtime.tzinfo is None:
                    decisions_mtime = decisions_mtime.replace(tzinfo=timezone.utc)

                staleness = adr_mtime - decisions_mtime
                if staleness > timedelta(days=self.DECISIONS_THRESHOLD_DAYS):
                    issues.append(
                        ValidationIssue(
                            system=rel_system,
                            check="decisions_sync",
                            severity="warning",
                            message=f"decisions.md is {staleness.days} days older than {adr_file.name}",
                            file="decisions.md",
                        )
                    )
                    break  # One warning is enough

        return issues

    def _check_graph_freshness(self) -> list[ValidationIssue]:
        """Check if global graph.json is stale.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        graph_path = self.project_root / ".ctx" / "graph.json"
        if not graph_path.exists():
            return issues

        graph_mtime = self._get_file_mtime(graph_path)
        if graph_mtime is None:
            return issues

        # Find the newest system modification
        latest_system_mtime: datetime | None = None
        for ctx_dir in find_ctx_directories(self.project_root):
            # Exclude root .ctx directory
            if ctx_dir.parent != self.project_root:
                system_path = ctx_dir.parent
                source_mtime = self._get_latest_source_mtime(system_path)
                if source_mtime is not None and (latest_system_mtime is None or source_mtime > latest_system_mtime):
                    latest_system_mtime = source_mtime

        if latest_system_mtime is None:
            return issues

        # Ensure timezone awareness
        if latest_system_mtime.tzinfo is None:
            latest_system_mtime = latest_system_mtime.replace(tzinfo=timezone.utc)
        if graph_mtime.tzinfo is None:
            graph_mtime = graph_mtime.replace(tzinfo=timezone.utc)

        staleness = latest_system_mtime - graph_mtime
        threshold = timedelta(days=self.GRAPH_THRESHOLD_DAYS)

        if staleness > threshold:
            issues.append(
                FixableIssue(
                    system=".ctx",
                    check="graph_staleness",
                    severity="warning",
                    message=f"graph.json is {staleness.days} days older than system changes",
                    file="graph.json",
                    fix_id="stale_graph",
                    fix_params={},
                    fix_description="Regenerate graph.json from the knowledge database",
                )
            )

        return issues
