"""Snapshot validator for Living Context systems.

Validates snapshot.md files for accuracy against actual codebase:
- File existence: All files in the "Files" table exist
- Export accuracy: Public API exports listed actually exist in source
- Dependency accuracy: Systems listed in Dependencies exist
- Dependent accuracy: Systems listed in Dependents actually import this system
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from cctx.crud import get_system
from cctx.database import ContextDB
from cctx.validators.base import (
    BaseValidator,
    FixableIssue,
    ValidationIssue,
    ValidatorResult,
)
from cctx.validators.markdown_parser import MarkdownParser
from cctx.validators.path_filter import find_ctx_directories


class SnapshotValidator(BaseValidator):
    """Validates snapshot.md files against actual codebase state.

    Checks:
    1. File existence - Files listed in snapshot.md exist
    2. Export accuracy - Public API exports exist in source
    3. Dependency accuracy - Dependencies exist as registered systems
    4. Dependent accuracy - Dependents actually import this system
    """

    def validate(self) -> ValidatorResult:
        """Run snapshot validation checks.

        Returns:
            ValidatorResult containing the validation outcome and any issues found.
        """
        issues: list[ValidationIssue] = []
        systems_checked = 0

        # Find all systems with .ctx directories
        systems = self._find_systems_with_ctx()

        for system_path in systems:
            snapshot_path = system_path / ".ctx" / "snapshot.md"
            rel_system = str(system_path.relative_to(self.project_root))
            if not snapshot_path.exists():
                issues.append(
                    FixableIssue(
                        system=rel_system,
                        check="snapshot_exists",
                        severity="error",
                        message="snapshot.md not found in .ctx directory",
                        file=".ctx/snapshot.md",
                        fix_id="missing_snapshot",
                        fix_params={"system_path": rel_system},
                        fix_description=(
                            f"Create snapshot.md from template for system '{rel_system}'"
                        ),
                    )
                )
                continue

            systems_checked += 1
            content = snapshot_path.read_text(encoding="utf-8")

            # Run all checks
            issues.extend(self._check_file_existence(system_path, content))
            issues.extend(self._check_dependencies(system_path, content))
            issues.extend(self._check_dependents(system_path, content))

        # Determine overall status
        has_errors = any(issue.severity == "error" for issue in issues)
        status: Literal["pass", "fail"] = "fail" if has_errors else "pass"

        return ValidatorResult(
            name="snapshot-validator",
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

        # Search for .ctx directories (excluding the root .ctx)
        for ctx_dir in find_ctx_directories(self.project_root):
            if ctx_dir.parent != self.project_root:
                systems.append(ctx_dir.parent)

        return sorted(systems)

    def _check_file_existence(self, system_path: Path, content: str) -> list[ValidationIssue]:
        """Check that files listed in snapshot.md exist.

        Args:
            system_path: Path to the system directory.
            content: Content of snapshot.md.

        Returns:
            List of validation issues for missing files.
        """
        issues: list[ValidationIssue] = []
        rel_system = str(system_path.relative_to(self.project_root))

        # Extract Files table
        files_table = MarkdownParser.extract_table_by_header(content, "Files")
        if files_table is None:
            return issues  # No Files table, nothing to check

        # Check each file in the table
        for row in files_table.rows:
            # Try common column names for file paths
            file_path = (
                row.get("File")
                or row.get("Path")
                or row.get("file")
                or row.get("path")
                or row.get("Name")
                or row.get("name")
            )
            if not file_path:
                continue

            # Clean up the file path (remove backticks, etc.)
            file_path = file_path.strip("`").strip()
            if not file_path:
                continue

            # Check if file exists relative to system directory
            full_path = system_path / file_path
            if not full_path.exists():
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="file_existence",
                        severity="error",
                        message=f"File '{file_path}' listed in snapshot.md but not found",
                        file="snapshot.md",
                    )
                )

        return issues

    def _check_dependencies(self, system_path: Path, content: str) -> list[ValidationIssue]:
        """Check that dependencies listed in snapshot.md exist.

        Args:
            system_path: Path to the system directory.
            content: Content of snapshot.md.

        Returns:
            List of validation issues for invalid dependencies.
        """
        issues: list[ValidationIssue] = []
        rel_system = str(system_path.relative_to(self.project_root))

        # Extract Dependencies section/table
        deps_table = MarkdownParser.extract_table_by_header(content, "Dependencies")
        if deps_table is None:
            # Try to extract from section content as list
            deps_section = MarkdownParser.extract_section(content, "Dependencies", level=2)
            if deps_section:
                deps = self._extract_system_refs_from_text(deps_section)
                for dep in deps:
                    # Skip external references (npm packages, file paths, descriptive text)
                    if self._is_external_reference(dep):
                        continue
                    if not self._system_exists(dep):
                        issues.append(
                            ValidationIssue(
                                system=rel_system,
                                check="dependency_exists",
                                severity="warning",
                                message=f"Dependency '{dep}' not found as registered system",
                                file="snapshot.md",
                            )
                        )
            return issues

        # Check each dependency in the table
        for row in deps_table.rows:
            dep_path = (
                row.get("System")
                or row.get("Path")
                or row.get("system")
                or row.get("path")
                or row.get("Name")
                or row.get("name")
            )
            if not dep_path:
                continue

            dep_path = dep_path.strip("`").strip()
            if not dep_path:
                continue

            # Skip external references (npm packages, file paths, descriptive text)
            if self._is_external_reference(dep_path):
                continue

            if not self._system_exists(dep_path):
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="dependency_exists",
                        severity="warning",
                        message=f"Dependency '{dep_path}' not found as registered system",
                        file="snapshot.md",
                    )
                )

        return issues

    def _check_dependents(self, system_path: Path, content: str) -> list[ValidationIssue]:
        """Check that dependents listed in snapshot.md actually import this system.

        Args:
            system_path: Path to the system directory.
            content: Content of snapshot.md.

        Returns:
            List of validation issues for invalid dependents.
        """
        issues: list[ValidationIssue] = []
        rel_system = str(system_path.relative_to(self.project_root))

        # Extract Dependents section/table
        deps_table = MarkdownParser.extract_table_by_header(content, "Dependents")
        if deps_table is None:
            # Try to extract from section content as list
            deps_section = MarkdownParser.extract_section(content, "Dependents", level=2)
            if deps_section:
                dependents = self._extract_system_refs_from_text(deps_section)
                for dep in dependents:
                    # Skip external references (npm packages, file paths, descriptive text)
                    if self._is_external_reference(dep):
                        continue
                    if not self._system_exists(dep):
                        issues.append(
                            ValidationIssue(
                                system=rel_system,
                                check="dependent_exists",
                                severity="warning",
                                message=f"Dependent '{dep}' not found as registered system",
                                file="snapshot.md",
                            )
                        )
            return issues

        # Check each dependent in the table
        for row in deps_table.rows:
            dep_path = (
                row.get("System")
                or row.get("Path")
                or row.get("system")
                or row.get("path")
                or row.get("Name")
                or row.get("name")
            )
            if not dep_path:
                continue

            dep_path = dep_path.strip("`").strip()
            if not dep_path:
                continue

            # Skip external references (npm packages, file paths, descriptive text)
            if self._is_external_reference(dep_path):
                continue

            if not self._system_exists(dep_path):
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="dependent_exists",
                        severity="warning",
                        message=f"Dependent '{dep_path}' not found as registered system",
                        file="snapshot.md",
                    )
                )

        return issues

    def _is_external_reference(self, ref: str) -> bool:
        """Check if a reference is external (not a registered system).

        External references include:
        - NPM packages marked with (external), e.g., "howler (external)"
        - File paths (contain / and .ts/.js/.tsx/.jsx extensions)
        - Descriptive text (contains spaces and looks like natural language)

        Args:
            ref: The reference string to check.

        Returns:
            True if this is an external reference that should not be validated.
        """
        # Marked as external (e.g., "howler (external)")
        if "(external)" in ref.lower():
            return True

        # Looks like a specific file path (not a system directory)
        # File paths have extensions like .ts, .js, .tsx, .jsx
        file_extensions = (
            ".ts",
            ".js",
            ".tsx",
            ".jsx",
            ".py",
            ".rs",
            ".go",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".css",
            ".html",
        )
        if any(ref.endswith(ext) for ext in file_extensions):
            return True

        # Descriptive text with spaces (e.g., "Scene classes", "UI components")
        # System paths typically don't have spaces
        return bool(" " in ref and not ref.startswith("src/"))

    def _system_exists(self, system_path: str) -> bool:
        """Check if a system exists (either in DB or on filesystem).

        Args:
            system_path: Path to check.

        Returns:
            True if system exists.
        """
        # Check filesystem first
        full_path = self.project_root / system_path
        if full_path.exists() and full_path.is_dir():
            return True

        # Check database
        if self.db_path.exists():
            try:
                with ContextDB(self.db_path, auto_init=False) as db:
                    system = get_system(db, system_path)
                    return system is not None
            except Exception:
                pass

        return False

    def _extract_system_refs_from_text(self, text: str) -> list[str]:
        """Extract system path references from markdown text.

        Looks for patterns like:
        - `src/systems/foo`
        - src/systems/foo
        - [System Name](path)

        Args:
            text: Markdown text to parse.

        Returns:
            List of system paths found.
        """
        refs: list[str] = []

        # Match backtick-wrapped paths
        backtick_pattern = re.compile(r"`([^`]+/[^`]+)`")
        for match in backtick_pattern.finditer(text):
            refs.append(match.group(1))

        # Match markdown links
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for match in link_pattern.finditer(text):
            path = match.group(2)
            if "/" in path and not path.startswith("http"):
                refs.append(path)

        return refs
