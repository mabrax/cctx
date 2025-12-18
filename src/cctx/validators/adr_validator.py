"""ADR validator for Living Context systems.

Validates ADR (Architecture Decision Record) consistency:
- No orphan ADRs: Every ADR file has entry in decisions.md and database
- No broken references: Every entry in decisions.md has corresponding file
- Database sync: ADRs in knowledge.db match filesystem
- Superseded chains: If ADR is superseded, the superseding ADR exists
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from cctx.adr_crud import get_adr, list_adrs
from cctx.database import ContextDB
from cctx.validators.base import (
    BaseValidator,
    FixableIssue,
    ValidationIssue,
    ValidatorResult,
)
from cctx.validators.path_filter import find_ctx_directories


class AdrValidator(BaseValidator):
    """Validates ADR consistency across the Living Context system.

    Checks:
    1. No orphan ADRs - Every ADR file is indexed
    2. No broken references - Index entries have corresponding files
    3. Database sync - ADRs in DB match filesystem
    4. Superseded chains - Superseding ADRs exist
    """

    def validate(self) -> ValidatorResult:
        """Run ADR validation checks.

        Returns:
            ValidatorResult containing the validation outcome and any issues found.
        """
        issues: list[ValidationIssue] = []
        adrs_checked = 0

        # Find all ADR directories
        adr_dirs = self._find_adr_directories()

        # Collect all ADR files
        all_adr_files: dict[str, Path] = {}  # ADR ID -> file path
        for adr_dir in adr_dirs:
            for adr_file in adr_dir.glob("ADR-*.md"):
                adr_id = self._extract_adr_id(adr_file.name)
                if adr_id:
                    all_adr_files[adr_id] = adr_file
                    adrs_checked += 1

        # Check each ADR file
        for adr_id, adr_file in all_adr_files.items():
            # Check if ADR is in database
            issues.extend(self._check_db_registration(adr_id, adr_file))

            # Check superseded chains
            issues.extend(self._check_superseded_chain(adr_id, adr_file, all_adr_files))

        # Check for orphan DB entries (in DB but file missing)
        issues.extend(self._check_orphan_db_entries(all_adr_files))

        # Check decisions.md indexes
        issues.extend(self._check_decisions_indexes(all_adr_files))

        # Determine overall status
        has_errors = any(issue.severity == "error" for issue in issues)
        status: Literal["pass", "fail"] = "fail" if has_errors else "pass"

        return ValidatorResult(
            name="adr-validator",
            status=status,
            issues=issues,
            systems_checked=adrs_checked,
        )

    def _find_adr_directories(self) -> list[Path]:
        """Find all adr/ directories in .ctx directories.

        Returns:
            List of paths to ADR directories.
        """
        adr_dirs: list[Path] = []

        # Find adr directories in all valid .ctx directories
        for ctx_dir in find_ctx_directories(self.project_root):
            adr_dir = ctx_dir / "adr"
            if adr_dir.exists() and adr_dir.is_dir():
                adr_dirs.append(adr_dir)

        return sorted(set(adr_dirs))

    def _extract_adr_id(self, filename: str) -> str | None:
        """Extract ADR ID from filename.

        Args:
            filename: Filename like "ADR-001-some-title.md".

        Returns:
            ADR ID like "ADR-001", or None if not matched.
        """
        match = re.match(r"(ADR-\d+)", filename)
        return match.group(1) if match else None

    def _check_db_registration(self, adr_id: str, adr_file: Path) -> list[ValidationIssue]:
        """Check if an ADR is registered in the database.

        Args:
            adr_id: The ADR identifier.
            adr_file: Path to the ADR file.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        if not self.db_path.exists():
            return issues  # No DB to check against

        try:
            with ContextDB(self.db_path, auto_init=False) as db:
                adr = get_adr(db, adr_id)
                if adr is None:
                    rel_path = str(adr_file.relative_to(self.project_root))
                    system_path = str(adr_file.parent.parent.relative_to(self.project_root))
                    issues.append(
                        FixableIssue(
                            system=system_path,
                            check="db_registration",
                            severity="warning",
                            message=f"ADR {adr_id} exists as file but not registered in database",
                            file=rel_path,
                            fix_id="unregistered_adr",
                            fix_params={
                                "adr_id": adr_id,
                                "file_path": rel_path,
                                "system": system_path,
                            },
                            fix_description=f"Register {adr_id} in database by parsing the ADR file",
                        )
                    )
        except Exception:
            pass  # DB access error, skip check

        return issues

    def _check_superseded_chain(
        self, adr_id: str, adr_file: Path, all_adr_files: dict[str, Path]
    ) -> list[ValidationIssue]:
        """Check that superseded ADRs have valid chains.

        Args:
            adr_id: The ADR identifier.
            adr_file: Path to the ADR file.
            all_adr_files: Map of all known ADR IDs to file paths.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        try:
            content = adr_file.read_text(encoding="utf-8")
        except Exception:
            return issues

        # Check for "superseded" status and "Superseded by" reference
        status_match = re.search(r"\*\*Status\*\*:\s*(\w+)", content, re.IGNORECASE)
        if status_match and status_match.group(1).lower() == "superseded":
            # Look for "Superseded by ADR-XXX" reference
            superseded_by_match = re.search(r"[Ss]uperseded\s+by\s+(ADR-\d+)", content)
            if superseded_by_match:
                superseding_id = superseded_by_match.group(1)
                if superseding_id not in all_adr_files:
                    rel_path = str(adr_file.relative_to(self.project_root))
                    issues.append(
                        ValidationIssue(
                            system=str(adr_file.parent.parent.relative_to(self.project_root)),
                            check="superseded_chain",
                            severity="warning",
                            message=f"ADR {adr_id} is superseded by {superseding_id} which does not exist",
                            file=rel_path,
                        )
                    )
            else:
                rel_path = str(adr_file.relative_to(self.project_root))
                issues.append(
                    ValidationIssue(
                        system=str(adr_file.parent.parent.relative_to(self.project_root)),
                        check="superseded_chain",
                        severity="warning",
                        message=f"ADR {adr_id} is marked as superseded but does not link to superseding ADR",
                        file=rel_path,
                    )
                )

        return issues

    def _check_orphan_db_entries(self, all_adr_files: dict[str, Path]) -> list[ValidationIssue]:
        """Check for ADRs in database that don't have corresponding files.

        Args:
            all_adr_files: Map of all known ADR IDs to file paths.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        if not self.db_path.exists():
            return issues

        try:
            with ContextDB(self.db_path, auto_init=False) as db:
                db_adrs = list_adrs(db)
                for adr in db_adrs:
                    adr_id = adr.get("id")
                    if adr_id and adr_id not in all_adr_files:
                        file_path = adr.get("file_path", "unknown")
                        issues.append(
                            ValidationIssue(
                                system=".ctx",
                                check="orphan_db_entry",
                                severity="error",
                                message=f"ADR {adr_id} exists in database but file not found at {file_path}",
                                file=file_path,
                            )
                        )
        except Exception:
            pass  # DB access error, skip check

        return issues

    def _check_decisions_indexes(self, all_adr_files: dict[str, Path]) -> list[ValidationIssue]:
        """Check that decisions.md indexes are in sync with ADR files.

        Args:
            all_adr_files: Map of all known ADR IDs to file paths.

        Returns:
            List of validation issues.
        """
        issues: list[ValidationIssue] = []

        # Find all decisions.md files
        for ctx_dir in find_ctx_directories(self.project_root):
            decisions_file = ctx_dir / "decisions.md"
            if not decisions_file.exists():
                continue

            try:
                content = decisions_file.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_ctx = str(ctx_dir.relative_to(self.project_root))
            adr_dir = ctx_dir / "adr"

            # Extract ADR references from decisions.md
            indexed_adrs = set(re.findall(r"(ADR-\d+)", content))

            # Check for ADRs in decisions.md that don't exist as files
            for indexed_id in indexed_adrs:
                if indexed_id not in all_adr_files:
                    # Check if it should be in this context's adr/ directory
                    adr_dir / f"{indexed_id}*.md"
                    local_matches = (
                        list(adr_dir.glob(f"{indexed_id}*.md")) if adr_dir.exists() else []
                    )
                    if not local_matches:
                        issues.append(
                            ValidationIssue(
                                system=rel_ctx,
                                check="broken_reference",
                                severity="error",
                                message=f"decisions.md references {indexed_id} but file not found",
                                file="decisions.md",
                            )
                        )

            # Check for ADR files in this context's adr/ directory not indexed
            if adr_dir.exists():
                for adr_file in adr_dir.glob("ADR-*.md"):
                    adr_id = self._extract_adr_id(adr_file.name)
                    if adr_id and adr_id not in indexed_adrs:
                        issues.append(
                            ValidationIssue(
                                system=rel_ctx,
                                check="orphan_file",
                                severity="warning",
                                message=f"ADR file {adr_id} exists but not indexed in decisions.md",
                                file=str(adr_file.relative_to(self.project_root)),
                            )
                        )

        return issues
