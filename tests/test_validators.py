"""Tests for the validation framework."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cctx.database import ContextDB
from cctx.schema import init_database
from cctx.validators import (
    AdrValidator,
    AggregatedResult,
    DebtAuditor,
    FreshnessChecker,
    SnapshotValidator,
    ValidationRunner,
)
from cctx.validators.base import ValidationIssue, ValidatorResult

# -----------------------------------------------------------------------------
# Base Validator Tests
# -----------------------------------------------------------------------------


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_create_issue(self) -> None:
        """Test creating a validation issue."""
        issue = ValidationIssue(
            system="src/systems/audio",
            check="file_existence",
            severity="error",
            message="File not found",
            file="snapshot.md",
            line=10,
        )
        assert issue.system == "src/systems/audio"
        assert issue.check == "file_existence"
        assert issue.severity == "error"
        assert issue.message == "File not found"
        assert issue.file == "snapshot.md"
        assert issue.line == 10

    def test_issue_defaults(self) -> None:
        """Test ValidationIssue default values."""
        issue = ValidationIssue(
            system="test",
            check="test_check",
            severity="warning",
            message="Test message",
        )
        assert issue.file is None
        assert issue.line is None


class TestValidatorResult:
    """Tests for ValidatorResult dataclass."""

    def test_create_pass_result(self) -> None:
        """Test creating a passing result."""
        result = ValidatorResult(
            name="test-validator",
            status="pass",
            issues=[],
            systems_checked=5,
        )
        assert result.name == "test-validator"
        assert result.status == "pass"
        assert result.issues == []
        assert result.systems_checked == 5

    def test_create_fail_result(self) -> None:
        """Test creating a failing result."""
        issues = [
            ValidationIssue(
                system="test",
                check="test_check",
                severity="error",
                message="Test error",
            )
        ]
        result = ValidatorResult(
            name="test-validator",
            status="fail",
            issues=issues,
            systems_checked=1,
        )
        assert result.status == "fail"
        assert len(result.issues) == 1


# -----------------------------------------------------------------------------
# Snapshot Validator Tests
# -----------------------------------------------------------------------------


class TestSnapshotValidator:
    """Tests for SnapshotValidator."""

    def test_no_ctx_directories(self, tmp_path: Path) -> None:
        """Test validation with no .ctx directories."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.name == "snapshot-validator"
        assert result.status == "pass"
        assert result.systems_checked == 0

    def test_missing_snapshot(self, tmp_path: Path) -> None:
        """Test validation with missing snapshot.md."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.status == "fail"
        assert len(result.issues) == 1
        assert result.issues[0].check == "snapshot_exists"
        assert result.issues[0].severity == "error"

    def test_valid_snapshot(self, tmp_path: Path) -> None:
        """Test validation with valid snapshot.md."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md
        snapshot_content = """# Audio System

## Purpose
Handle audio playback.

## Files
| File | Description |
|------|-------------|
| index.ts | Main entry |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)
        (system_path / "index.ts").write_text("export const audio = {};")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.status == "pass"
        assert result.systems_checked == 1

    def test_missing_file(self, tmp_path: Path) -> None:
        """Test validation detects missing files."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md referencing non-existent file
        snapshot_content = """# Audio System

## Files
| File | Description |
|------|-------------|
| missing.ts | Does not exist |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.status == "fail"
        assert any(i.check == "file_existence" for i in result.issues)

    def test_external_dependency_skipped(self, tmp_path: Path) -> None:
        """Test that external npm dependencies don't produce warnings."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md with external dependencies
        snapshot_content = """# Audio System

## Purpose
Handle audio playback.

## Files
| File | Description |
|------|-------------|
| index.ts | Main entry |

## Dependencies
| System | Purpose |
|--------|---------|
| howler (external) | Audio library |
| tslog (external) | Logging |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)
        (system_path / "index.ts").write_text("export const audio = {};")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        # Should not have any dependency_exists warnings for external deps
        dep_issues = [i for i in result.issues if i.check == "dependency_exists"]
        assert len(dep_issues) == 0

    def test_file_path_dependency_skipped(self, tmp_path: Path) -> None:
        """Test that file path dependencies don't produce warnings."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md with file path dependents
        snapshot_content = """# Audio System

## Purpose
Handle audio playback.

## Files
| File | Description |
|------|-------------|
| index.ts | Main entry |

## Dependents
| System | Purpose |
|--------|---------|
| src/game/Game.ts | Main game file |
| src/scenes/MainScene.tsx | Main scene |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)
        (system_path / "index.ts").write_text("export const audio = {};")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        # Should not have any dependent_exists warnings for file paths
        dep_issues = [i for i in result.issues if i.check == "dependent_exists"]
        assert len(dep_issues) == 0

    def test_descriptive_text_dependency_skipped(self, tmp_path: Path) -> None:
        """Test that descriptive text dependencies don't produce warnings."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md with descriptive text dependents
        snapshot_content = """# Audio System

## Purpose
Handle audio playback.

## Files
| File | Description |
|------|-------------|
| index.ts | Main entry |

## Dependents
| System | Purpose |
|--------|---------|
| Scene classes | All scene implementations |
| UI components | Various UI elements |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)
        (system_path / "index.ts").write_text("export const audio = {};")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        # Should not have any dependent_exists warnings for descriptive text
        dep_issues = [i for i in result.issues if i.check == "dependent_exists"]
        assert len(dep_issues) == 0

    def test_real_missing_system_still_warns(self, tmp_path: Path) -> None:
        """Test that actual missing systems still produce warnings."""
        # Setup
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create snapshot.md with a real missing system dependency
        snapshot_content = """# Audio System

## Purpose
Handle audio playback.

## Files
| File | Description |
|------|-------------|
| index.ts | Main entry |

## Dependencies
| System | Purpose |
|--------|---------|
| src/systems/missing-system | Does not exist |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)
        (system_path / "index.ts").write_text("export const audio = {};")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = SnapshotValidator(tmp_path, db_path)
        result = validator.validate()

        # Should have a warning for the missing system
        dep_issues = [i for i in result.issues if i.check == "dependency_exists"]
        assert len(dep_issues) == 1
        assert "src/systems/missing-system" in dep_issues[0].message


# -----------------------------------------------------------------------------
# ADR Validator Tests
# -----------------------------------------------------------------------------


class TestAdrValidator:
    """Tests for AdrValidator."""

    def test_no_adr_directories(self, tmp_path: Path) -> None:
        """Test validation with no ADR directories."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        validator = AdrValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.name == "adr-validator"
        assert result.status == "pass"

    def test_valid_adr(self, tmp_path: Path) -> None:
        """Test validation with valid ADR."""
        # Setup
        ctx_path = tmp_path / ".ctx"
        adr_dir = ctx_path / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        adr_content = """# ADR-001: Use PostgreSQL

- **Status**: accepted
- **Date**: 2025-01-01

## Context
We need a database.

## Decision
Use PostgreSQL.
"""
        (adr_dir / "ADR-001-use-postgresql.md").write_text(adr_content)

        # Create decisions.md
        decisions_content = """# Decisions

## ADR-001: Use PostgreSQL
Status: accepted
"""
        (ctx_path / "decisions.md").write_text(decisions_content)

        db_path = ctx_path / "knowledge.db"
        init_database(db_path)

        # Register ADR in database
        from cctx.adr_crud import create_adr

        with ContextDB(db_path, auto_init=False) as db:
            create_adr(
                db, "ADR-001", "Use PostgreSQL", "accepted", ".ctx/adr/ADR-001-use-postgresql.md"
            )

        validator = AdrValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.status == "pass"

    def test_orphan_db_entry(self, tmp_path: Path) -> None:
        """Test validation detects orphan database entries."""
        ctx_path = tmp_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = ctx_path / "knowledge.db"
        init_database(db_path)

        # Create ADR in DB but not on filesystem (needs transaction to persist)
        from cctx.adr_crud import create_adr

        with ContextDB(db_path, auto_init=False) as db, db.transaction():
            create_adr(db, "ADR-999", "Missing ADR", "proposed", ".ctx/adr/ADR-999.md")

        validator = AdrValidator(tmp_path, db_path)
        result = validator.validate()

        assert result.status == "fail"
        assert any(i.check == "orphan_db_entry" for i in result.issues)

    def test_superseded_chain(self, tmp_path: Path) -> None:
        """Test validation checks superseded chains."""
        ctx_path = tmp_path / ".ctx"
        adr_dir = ctx_path / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Create ADR that references non-existent superseding ADR
        adr_content = """# ADR-001: Old Decision

- **Status**: superseded
- **Date**: 2025-01-01

Superseded by ADR-999

## Context
Old context.
"""
        (adr_dir / "ADR-001-old-decision.md").write_text(adr_content)

        db_path = ctx_path / "knowledge.db"
        init_database(db_path)

        validator = AdrValidator(tmp_path, db_path)
        result = validator.validate()

        assert any(i.check == "superseded_chain" for i in result.issues)


# -----------------------------------------------------------------------------
# Debt Auditor Tests
# -----------------------------------------------------------------------------


class TestDebtAuditor:
    """Tests for DebtAuditor."""

    def test_no_debt_files(self, tmp_path: Path) -> None:
        """Test auditor with no debt.md files."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        auditor = DebtAuditor(tmp_path, db_path)
        result = auditor.validate()

        assert result.name == "debt-auditor"
        assert result.status == "pass"
        assert result.systems_checked == 0

    def test_empty_debt_file(self, tmp_path: Path) -> None:
        """Test auditor reports empty debt files."""
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create empty debt.md
        (ctx_path / "debt.md").write_text("# Technical Debt\n\nNo debt tracked.\n")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        auditor = DebtAuditor(tmp_path, db_path)
        result = auditor.validate()

        assert any(i.check == "empty_debt" for i in result.issues)
        assert any(i.severity == "info" for i in result.issues)

    def test_old_debt_item(self, tmp_path: Path) -> None:
        """Test auditor flags old debt items."""
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create debt.md with old item
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d")
        debt_content = f"""# Technical Debt

| ID | Description | Priority | Created |
|----|-------------|----------|---------|
| DEBT-001 | Old debt | high | {old_date} |
"""
        (ctx_path / "debt.md").write_text(debt_content)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        auditor = DebtAuditor(tmp_path, db_path)
        result = auditor.validate()

        assert any(i.check == "age_threshold" for i in result.issues)
        assert any("high-priority" in i.message.lower() for i in result.issues)


# -----------------------------------------------------------------------------
# Freshness Checker Tests
# -----------------------------------------------------------------------------


class TestFreshnessChecker:
    """Tests for FreshnessChecker."""

    def test_no_systems(self, tmp_path: Path) -> None:
        """Test checker with no systems."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        checker = FreshnessChecker(tmp_path, db_path)
        result = checker.validate()

        assert result.name == "freshness-checker"
        assert result.status == "pass"
        assert result.systems_checked == 0

    def test_fresh_documentation(self, tmp_path: Path) -> None:
        """Test checker passes with fresh documentation."""
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        # Create source file
        (system_path / "index.ts").write_text("export const audio = {};")

        # Create snapshot.md (should be fresh since we just created it)
        (ctx_path / "snapshot.md").write_text("# Audio System\n")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        checker = FreshnessChecker(tmp_path, db_path)
        result = checker.validate()

        # Fresh files should pass
        assert result.systems_checked == 1


# -----------------------------------------------------------------------------
# Validation Runner Tests
# -----------------------------------------------------------------------------


class TestValidationRunner:
    """Tests for ValidationRunner."""

    def test_run_all_validators(self, tmp_path: Path) -> None:
        """Test running all validators."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path)
        result = runner.run_all()

        assert isinstance(result, AggregatedResult)
        assert result.validators_run == 4  # snapshot, adr, debt, freshness

    def test_run_specific_validators(self, tmp_path: Path) -> None:
        """Test running specific validators."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path)
        result = runner.run_validators(["snapshot", "adr"])

        assert result.validators_run == 2

    def test_run_single_validator(self, tmp_path: Path) -> None:
        """Test running a single validator."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path)
        result = runner.run_single("snapshot")

        assert result is not None
        assert result.name == "snapshot-validator"

    def test_run_invalid_validator(self, tmp_path: Path) -> None:
        """Test running an invalid validator returns None."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path)
        result = runner.run_single("nonexistent")

        assert result is None

    def test_aggregated_result_counts(self, tmp_path: Path) -> None:
        """Test aggregated result correctly counts issues."""
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)
        # Missing snapshot.md will cause an error

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path)
        result = runner.run_all()

        # Should have at least one error (missing snapshot)
        assert result.total_issues > 0
        assert result.errors > 0

    def test_parallel_execution(self, tmp_path: Path) -> None:
        """Test parallel execution mode."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path, parallel=True)
        result = runner.run_all()

        # Should complete successfully
        assert result.validators_run == 4

    def test_sequential_execution(self, tmp_path: Path) -> None:
        """Test sequential execution mode."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        runner = ValidationRunner(tmp_path, db_path, parallel=False)
        result = runner.run_all()

        # Should complete successfully
        assert result.validators_run == 4


# -----------------------------------------------------------------------------
# CLI Integration Tests
# -----------------------------------------------------------------------------


class TestHealthCommandWithValidators:
    """Tests for health command with validators."""

    def test_health_runs_validators(self, tmp_path: Path) -> None:
        """Test health command runs validators."""
        import os

        from typer.testing import CliRunner

        from cctx.cli import app

        runner = CliRunner()

        # Initialize context
        runner.invoke(app, ["init", str(tmp_path)])

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health", "--json"])
            assert result.exit_code == 0

            data = json.loads(result.stdout)
            assert "validators" in data
            assert "summary" in data
            assert data["summary"]["validators_run"] == 4
        finally:
            os.chdir(original_cwd)

    def test_validate_runs_subset(self, tmp_path: Path) -> None:
        """Test validate command runs only fast validators."""
        import os

        from typer.testing import CliRunner

        from cctx.cli import app

        runner = CliRunner()

        # Initialize context
        runner.invoke(app, ["init", str(tmp_path)])

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["validate", "--json"])
            assert result.exit_code == 0

            data = json.loads(result.stdout)
            # validate only runs snapshot and adr validators
            assert data["summary"]["validators_run"] == 2
        finally:
            os.chdir(original_cwd)
