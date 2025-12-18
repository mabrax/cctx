"""Debt auditor for Living Context systems.

Audits technical debt tracking for staleness and resolution status:
- Age threshold: Flag debt items older than 30 days with no updates
- Resolution check: Check if debt might be resolved (code changed)
- Priority accuracy: High-priority debt should have recent activity
- Empty debt files: Systems with no tracked debt (may be oversight)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from cctx.validators.base import BaseValidator, ValidationIssue, ValidatorResult
from cctx.validators.git_helper import has_changes_since
from cctx.validators.markdown_parser import MarkdownParser
from cctx.validators.path_filter import find_ctx_directories


class DebtAuditor(BaseValidator):
    """Audits technical debt tracking for staleness and resolution.

    Checks:
    1. Age threshold - Flag debt items older than 30 days
    2. Resolution check - Debt may be resolved if referenced files changed
    3. Priority accuracy - High-priority debt should have recent attention
    4. Empty debt files - Systems with no tracked debt
    """

    # Default threshold for debt aging (days)
    DEFAULT_AGE_THRESHOLD_DAYS = 30

    def __init__(
        self,
        project_root: Path,
        db_path: Path,
        age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS,
    ) -> None:
        """Initialize debt auditor.

        Args:
            project_root: Root directory of the project.
            db_path: Path to the Living Context knowledge database.
            age_threshold_days: Days after which debt is considered stale.
        """
        super().__init__(project_root, db_path)
        self.age_threshold_days = age_threshold_days

    def validate(self) -> ValidatorResult:
        """Run debt audit checks.

        Returns:
            ValidatorResult containing the audit outcome and any issues found.
        """
        issues: list[ValidationIssue] = []
        systems_checked = 0
        debt_items_reviewed = 0

        # Find all debt.md files
        debt_files = self._find_debt_files()

        for debt_file in debt_files:
            systems_checked += 1

            try:
                content = debt_file.read_text(encoding="utf-8")
            except Exception:
                continue

            system_path = debt_file.parent.parent  # .ctx/debt.md -> system dir
            rel_system = str(system_path.relative_to(self.project_root))

            # Parse debt items from table
            debt_items = self._parse_debt_items(content)

            if not debt_items:
                # Check if this might be an oversight
                issues.append(
                    ValidationIssue(
                        system=rel_system,
                        check="empty_debt",
                        severity="info",
                        message="No debt items tracked - verify this is intentional",
                        file="debt.md",
                    )
                )
                continue

            # Audit each debt item
            for item in debt_items:
                debt_items_reviewed += 1
                issues.extend(self._audit_debt_item(item, system_path, rel_system))

        # Determine overall status
        has_errors = any(issue.severity == "error" for issue in issues)
        status: Literal["pass", "fail"] = "fail" if has_errors else "pass"

        return ValidatorResult(
            name="debt-auditor",
            status=status,
            issues=issues,
            systems_checked=systems_checked,
        )

    def _find_debt_files(self) -> list[Path]:
        """Find all debt.md files in .ctx directories.

        Returns:
            List of paths to debt.md files.
        """
        debt_files: list[Path] = []

        for ctx_dir in find_ctx_directories(self.project_root):
            debt_file = ctx_dir / "debt.md"
            if debt_file.exists():
                debt_files.append(debt_file)

        return sorted(debt_files)

    def _parse_debt_items(self, content: str) -> list[dict[str, str]]:
        """Parse debt items from debt.md content.

        Expects a table with columns like:
        | ID | Description | Priority | Created | Files |

        Args:
            content: Content of debt.md file.

        Returns:
            List of debt item dictionaries.
        """
        # Try to find a table
        table = MarkdownParser.extract_table_by_header(content, "Debt")
        if table is None:
            # Try without header (first table in document)
            tables = MarkdownParser.extract_tables(content)
            if tables:
                table = tables[0]

        if table is None:
            return []

        return table.rows

    def _audit_debt_item(
        self,
        item: dict[str, str],
        system_path: Path,
        rel_system: str,
    ) -> list[ValidationIssue]:
        """Audit a single debt item.

        Args:
            item: Debt item dictionary from table.
            system_path: Path to the system directory.
            rel_system: Relative system path string.

        Returns:
            List of validation issues for this item.
        """
        issues: list[ValidationIssue] = []

        # Extract fields (flexible column names)
        debt_id = item.get("ID") or item.get("id") or item.get("Id") or "unknown"
        priority = (
            item.get("Priority")
            or item.get("priority")
            or item.get("Severity")
            or item.get("severity")
            or ""
        ).lower()
        created_str = (
            item.get("Created") or item.get("created") or item.get("Date") or item.get("date") or ""
        )
        files_str = (
            item.get("Files") or item.get("files") or item.get("File") or item.get("file") or ""
        )

        # Parse created date
        created_date = self._parse_date(created_str)
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=self.age_threshold_days)

        # Check age threshold
        if created_date:
            # Ensure timezone awareness for comparison
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=timezone.utc)
            age = now - created_date
            if age > threshold:
                if priority == "high":
                    issues.append(
                        ValidationIssue(
                            system=rel_system,
                            check="age_threshold",
                            severity="warning",
                            message=f"High-priority debt {debt_id} aging without resolution ({age.days} days)",
                            file="debt.md",
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            system=rel_system,
                            check="age_threshold",
                            severity="info",
                            message=f"Debt item {debt_id} older than {self.age_threshold_days} days ({age.days} days), consider review",
                            file="debt.md",
                        )
                    )

        # Check if referenced files have changed (possible resolution)
        if files_str and created_date:
            referenced_files = self._extract_file_refs(files_str)
            for ref_file in referenced_files:
                full_path = system_path / ref_file
                if full_path.exists() and has_changes_since(full_path, created_date):
                    issues.append(
                        ValidationIssue(
                            system=rel_system,
                            check="possibly_resolved",
                            severity="info",
                            message=f"Debt {debt_id} references {ref_file} which had commits since debt created",
                            file="debt.md",
                        )
                    )

        return issues

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse a date string to datetime.

        Handles formats:
        - YYYY-MM-DD
        - YYYY/MM/DD
        - DD/MM/YYYY
        - ISO 8601

        Args:
            date_str: Date string to parse.

        Returns:
            datetime object, or None if parsing fails.
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try ISO format first
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        # Try YYYY-MM-DD
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        # Try YYYY/MM/DD
        try:
            return datetime.strptime(date_str, "%Y/%m/%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        # Try DD/MM/YYYY
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        return None

    def _extract_file_refs(self, files_str: str) -> list[str]:
        """Extract file references from a string.

        Handles formats:
        - `file.ts`
        - file.ts, other.ts
        - file.ts; other.ts

        Args:
            files_str: String containing file references.

        Returns:
            List of file paths.
        """
        # Remove backticks
        files_str = files_str.replace("`", "")

        # Split by comma, semicolon, or space
        parts = re.split(r"[,;\s]+", files_str)

        # Filter to valid-looking file paths
        files = [p.strip() for p in parts if p.strip() and "." in p]

        return files
