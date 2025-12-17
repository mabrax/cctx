"""Tests for the fixer framework."""

from __future__ import annotations

from pathlib import Path

import pytest

from cctx.fixers import (
    AdrFixer,
    BaseFixer,
    FixerRegistry,
    FixResult,
    GraphFixer,
    MissingCtxDirFixer,
    MissingTemplateFileFixer,
    SnapshotFixer,
    get_global_registry,
)
from cctx.schema import init_database
from cctx.validators.base import FixableIssue

# -----------------------------------------------------------------------------
# FixResult Tests
# -----------------------------------------------------------------------------


class TestFixResult:
    """Tests for FixResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful fix result."""
        result = FixResult(
            success=True,
            message="Fix applied successfully",
            files_modified=["src/systems/auth/.ctx/snapshot.md"],
        )
        assert result.success is True
        assert result.message == "Fix applied successfully"
        assert result.files_modified == ["src/systems/auth/.ctx/snapshot.md"]
        assert result.files_deleted == []

    def test_create_failure_result(self) -> None:
        """Test creating a failed fix result."""
        result = FixResult(
            success=False,
            message="Failed to create file",
        )
        assert result.success is False
        assert result.message == "Failed to create file"
        assert result.files_modified == []
        assert result.files_deleted == []

    def test_result_with_deleted_files(self) -> None:
        """Test fix result with deleted files."""
        result = FixResult(
            success=True,
            message="Cleaned up stale files",
            files_deleted=["old_file.md"],
        )
        assert result.files_deleted == ["old_file.md"]


# -----------------------------------------------------------------------------
# BaseFixer Tests
# -----------------------------------------------------------------------------


class TestBaseFixer:
    """Tests for BaseFixer abstract class."""

    def test_abstract_method_enforcement(self, tmp_path: Path) -> None:
        """Test that BaseFixer cannot be instantiated directly."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Attempting to instantiate BaseFixer should fail at runtime
        # since fix() is abstract
        with pytest.raises(TypeError, match="abstract"):
            BaseFixer(tmp_path, db_path)  # type: ignore[abstract]

    def test_resolve_path(self, tmp_path: Path) -> None:
        """Test _resolve_path method."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create a concrete fixer for testing
        fixer = SnapshotFixer(tmp_path, db_path)
        resolved = fixer._resolve_path("src/systems/auth")
        assert resolved == tmp_path / "src" / "systems" / "auth"

    def test_can_fix(self, tmp_path: Path) -> None:
        """Test can_fix method."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        fixer = SnapshotFixer(tmp_path, db_path)

        # Should match when fix_id matches
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
        )
        assert fixer.can_fix(issue) is True

        # Should not match when fix_id differs
        issue_other = FixableIssue(
            system="src/systems/auth",
            check="ctx_dir_exists",
            severity="error",
            message=".ctx directory is missing",
            fix_id="missing_ctx_dir",
            fix_description="Create .ctx directory",
        )
        assert fixer.can_fix(issue_other) is False


# -----------------------------------------------------------------------------
# SnapshotFixer Tests
# -----------------------------------------------------------------------------


class TestSnapshotFixer:
    """Tests for SnapshotFixer."""

    def test_fix_id(self) -> None:
        """Test that SnapshotFixer has correct fix_id."""
        assert SnapshotFixer.fix_id == "missing_snapshot"

    def test_create_missing_snapshot(self, tmp_path: Path) -> None:
        """Test creating a missing snapshot.md file."""
        # Setup project structure
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
        )

        # Apply fix
        fixer = SnapshotFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "snapshot.md" in result.message
        assert len(result.files_modified) == 1
        assert (ctx_path / "snapshot.md").exists()

    def test_idempotent_when_exists(self, tmp_path: Path) -> None:
        """Test that fixer is idempotent when file already exists."""
        # Setup project structure with existing snapshot
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)
        snapshot_path = ctx_path / "snapshot.md"
        original_content = "# Existing Snapshot\n"
        snapshot_path.write_text(original_content)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
        )

        # Apply fix
        fixer = SnapshotFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "already exists" in result.message
        assert result.files_modified == []
        # Original content should be preserved
        assert snapshot_path.read_text() == original_content

    def test_fail_when_ctx_dir_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails gracefully when .ctx dir is missing."""
        # Setup project structure WITHOUT .ctx directory
        system_path = tmp_path / "src" / "systems" / "auth"
        system_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
        )

        # Apply fix
        fixer = SnapshotFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert ".ctx directory does not exist" in result.message

    def test_uses_system_name_from_params(self, tmp_path: Path) -> None:
        """Test that fixer uses system_name from fix_params."""
        # Setup project structure
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue with custom system name
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
            fix_params={"system_name": "Authentication Module"},
        )

        # Apply fix
        fixer = SnapshotFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        content = (ctx_path / "snapshot.md").read_text()
        assert "Authentication Module" in content


# -----------------------------------------------------------------------------
# GraphFixer Tests
# -----------------------------------------------------------------------------


class TestGraphFixer:
    """Tests for GraphFixer."""

    def test_fix_id(self) -> None:
        """Test that GraphFixer has correct fix_id."""
        assert GraphFixer.fix_id == "stale_graph"

    def test_regenerate_graph(self, tmp_path: Path) -> None:
        """Test regenerating graph.json."""
        # Setup project structure
        ctx_path = tmp_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = ctx_path / "knowledge.db"
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="",  # Graph is project-wide, not system-specific
            check="graph_freshness",
            severity="warning",
            message="graph.json is stale",
            fix_id="stale_graph",
            fix_description="Regenerate graph.json from database",
        )

        # Apply fix
        fixer = GraphFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "graph.json" in result.message
        assert (ctx_path / "graph.json").exists()

    def test_idempotent_regeneration(self, tmp_path: Path) -> None:
        """Test that graph regeneration is safe to run multiple times."""
        # Setup project structure
        ctx_path = tmp_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = ctx_path / "knowledge.db"
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="",
            check="graph_freshness",
            severity="warning",
            message="graph.json is stale",
            fix_id="stale_graph",
            fix_description="Regenerate graph.json from database",
        )

        # Apply fix twice
        fixer = GraphFixer(tmp_path, db_path)
        result1 = fixer.fix(issue)
        result2 = fixer.fix(issue)

        # Both should succeed
        assert result1.success is True
        assert result2.success is True

    def test_fail_when_db_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails gracefully when database is missing."""
        # Setup project structure without database
        ctx_path = tmp_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = ctx_path / "knowledge.db"
        # Note: NOT creating the database

        # Create issue
        issue = FixableIssue(
            system="",
            check="graph_freshness",
            severity="warning",
            message="graph.json is stale",
            fix_id="stale_graph",
            fix_description="Regenerate graph.json from database",
        )

        # Apply fix
        fixer = GraphFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_fail_when_ctx_dir_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails gracefully when .ctx dir is missing."""
        # Create .ctx dir with database but then remove the .ctx dir
        # to test the case where ctx exists but graph.json location doesn't
        # Actually, since db check comes first, let's test with db in another location
        ctx_dir = tmp_path / ".ctx"
        # Create db path at a different location to bypass db check
        other_dir = tmp_path / "other"
        other_dir.mkdir(parents=True, exist_ok=True)
        db_path = other_dir / "knowledge.db"
        init_database(db_path)
        # Note: NOT creating the .ctx directory

        # Create issue
        issue = FixableIssue(
            system="",
            check="graph_freshness",
            severity="warning",
            message="graph.json is stale",
            fix_id="stale_graph",
            fix_description="Regenerate graph.json from database",
        )

        # Apply fix
        fixer = GraphFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert ".ctx directory does not exist" in result.message


# -----------------------------------------------------------------------------
# MissingCtxDirFixer Tests
# -----------------------------------------------------------------------------


class TestMissingCtxDirFixer:
    """Tests for MissingCtxDirFixer."""

    def test_fix_id(self) -> None:
        """Test that MissingCtxDirFixer has correct fix_id."""
        assert MissingCtxDirFixer.fix_id == "missing_ctx_dir"

    def test_create_ctx_directory(self, tmp_path: Path) -> None:
        """Test creating a missing .ctx directory."""
        # Setup project structure
        system_path = tmp_path / "src" / "systems" / "auth"
        system_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create templates directory for scaffolder
        templates_path = tmp_path / ".ctx" / "templates"
        templates_path.mkdir(parents=True, exist_ok=True)
        (templates_path / "snapshot.template.md").write_text("# {system_name}\n")
        (templates_path / "constraints.template.md").write_text("# Constraints\n")
        (templates_path / "decisions.template.md").write_text("# Decisions\n")
        (templates_path / "debt.template.md").write_text("# Technical Debt\n")

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="ctx_dir_exists",
            severity="error",
            message=".ctx directory is missing",
            fix_id="missing_ctx_dir",
            fix_description="Create .ctx directory with template files",
        )

        # Apply fix
        fixer = MissingCtxDirFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert ".ctx" in result.message
        assert (system_path / ".ctx").exists()
        assert (system_path / ".ctx" / "snapshot.md").exists()
        assert (system_path / ".ctx" / "constraints.md").exists()
        assert (system_path / ".ctx" / "decisions.md").exists()
        assert (system_path / ".ctx" / "debt.md").exists()
        assert (system_path / ".ctx" / "adr").is_dir()

    def test_idempotent_when_exists(self, tmp_path: Path) -> None:
        """Test that fixer is idempotent when .ctx already exists."""
        # Setup project structure with existing .ctx
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="ctx_dir_exists",
            severity="error",
            message=".ctx directory is missing",
            fix_id="missing_ctx_dir",
            fix_description="Create .ctx directory with template files",
        )

        # Apply fix
        fixer = MissingCtxDirFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "already exists" in result.message
        assert result.files_modified == []


# -----------------------------------------------------------------------------
# MissingTemplateFileFixer Tests
# -----------------------------------------------------------------------------


class TestMissingTemplateFileFixer:
    """Tests for MissingTemplateFileFixer."""

    def test_fix_id(self) -> None:
        """Test that MissingTemplateFileFixer has correct fix_id."""
        assert MissingTemplateFileFixer.fix_id == "missing_template_file"

    def test_valid_templates(self) -> None:
        """Test that valid templates are defined correctly."""
        assert {
            "constraints",
            "decisions",
            "debt",
        } == MissingTemplateFileFixer.VALID_TEMPLATES

    def test_create_missing_template_file(self, tmp_path: Path) -> None:
        """Test creating a missing template file."""
        # Setup project structure with .ctx but missing file
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create templates directory
        templates_path = tmp_path / ".ctx" / "templates"
        templates_path.mkdir(parents=True, exist_ok=True)
        (templates_path / "constraints.template.md").write_text(
            "# {system_name} Constraints\n"
        )

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="template_file_exists",
            severity="error",
            message="constraints.md is missing",
            fix_id="missing_template_file",
            fix_description="Create constraints.md from template",
            fix_params={"template_name": "constraints"},
        )

        # Apply fix
        fixer = MissingTemplateFileFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "constraints.md" in result.message
        assert (ctx_path / "constraints.md").exists()

    def test_idempotent_when_exists(self, tmp_path: Path) -> None:
        """Test that fixer is idempotent when file already exists."""
        # Setup project structure with existing file
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)
        constraints_path = ctx_path / "constraints.md"
        original_content = "# Existing Constraints\n"
        constraints_path.write_text(original_content)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="template_file_exists",
            severity="error",
            message="constraints.md is missing",
            fix_id="missing_template_file",
            fix_description="Create constraints.md from template",
            fix_params={"template_name": "constraints"},
        )

        # Apply fix
        fixer = MissingTemplateFileFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "already exists" in result.message
        assert result.files_modified == []
        # Original content should be preserved
        assert constraints_path.read_text() == original_content

    def test_fail_when_template_name_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails when template_name is not provided."""
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue WITHOUT template_name
        issue = FixableIssue(
            system="src/systems/auth",
            check="template_file_exists",
            severity="error",
            message="file is missing",
            fix_id="missing_template_file",
            fix_description="Create file from template",
            fix_params={},  # No template_name!
        )

        # Apply fix
        fixer = MissingTemplateFileFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "template_name is required" in result.message

    def test_fail_when_invalid_template_name(self, tmp_path: Path) -> None:
        """Test that fixer fails for invalid template names."""
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue with invalid template_name
        issue = FixableIssue(
            system="src/systems/auth",
            check="template_file_exists",
            severity="error",
            message="invalid.md is missing",
            fix_id="missing_template_file",
            fix_description="Create invalid.md from template",
            fix_params={"template_name": "invalid_template"},
        )

        # Apply fix
        fixer = MissingTemplateFileFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "Invalid template_name" in result.message

    def test_fail_when_ctx_dir_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails gracefully when .ctx dir is missing."""
        # System exists but no .ctx directory
        system_path = tmp_path / "src" / "systems" / "auth"
        system_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="template_file_exists",
            severity="error",
            message="constraints.md is missing",
            fix_id="missing_template_file",
            fix_description="Create constraints.md from template",
            fix_params={"template_name": "constraints"},
        )

        # Apply fix
        fixer = MissingTemplateFileFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert ".ctx directory does not exist" in result.message


# -----------------------------------------------------------------------------
# AdrFixer Tests
# -----------------------------------------------------------------------------


class TestAdrFixer:
    """Tests for AdrFixer."""

    def test_fix_id(self) -> None:
        """Test that AdrFixer has correct fix_id."""
        assert AdrFixer.fix_id == "unregistered_adr"

    def test_register_unregistered_adr(self, tmp_path: Path) -> None:
        """Test registering an ADR that exists as file but not in DB."""
        # Setup project structure with ADR file
        system_path = tmp_path / "src" / "systems" / "auth"
        adr_dir = system_path / ".ctx" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Create ADR file with standard format
        adr_file = adr_dir / "ADR-001.md"
        adr_content = """# ADR-001: Use JWT for authentication

- **Status**: accepted
- **Date**: 2025-01-15

## Context

We need a stateless authentication mechanism for our API.

## Decision

Use JWT (JSON Web Tokens) for API authentication.

## Consequences

### Positive
- Stateless authentication
- Easy to scale

### Negative
- Token revocation is complex
"""
        adr_file.write_text(adr_content)

        # Setup database
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR ADR-001 exists as file but not registered in database",
            file="src/systems/auth/.ctx/adr/ADR-001.md",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-001",
                "file_path": "src/systems/auth/.ctx/adr/ADR-001.md",
                "system": "src/systems/auth/.ctx",
            },
            fix_description="Register ADR-001 in database by parsing the ADR file",
        )

        # Apply fix
        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "ADR-001" in result.message
        assert "Registered" in result.message

        # Verify ADR is in database
        from cctx.adr_crud import get_adr
        from cctx.database import ContextDB

        with ContextDB(db_path, auto_init=False) as db:
            adr = get_adr(db, "ADR-001")
            assert adr is not None
            assert adr["title"] == "Use JWT for authentication"
            assert adr["status"] == "accepted"
            assert "stateless authentication" in adr["context"].lower()
            assert "JWT" in adr["decision"]
            assert adr["consequences"] is not None

    def test_idempotent_when_already_registered(self, tmp_path: Path) -> None:
        """Test that fixer is idempotent when ADR is already registered."""
        # Setup project structure with ADR file
        system_path = tmp_path / "src" / "systems" / "auth"
        adr_dir = system_path / ".ctx" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        adr_file = adr_dir / "ADR-001.md"
        adr_file.write_text("# ADR-001: Test\n\n- **Status**: accepted\n")

        # Setup database and pre-register the ADR
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        from cctx.adr_crud import create_adr
        from cctx.database import ContextDB

        with ContextDB(db_path, auto_init=False) as db, db.transaction():
            create_adr(
                db,
                id="ADR-001",
                title="Pre-existing ADR",
                status="accepted",
                file_path="src/systems/auth/.ctx/adr/ADR-001.md",
            )

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR ADR-001 exists as file but not registered in database",
            file="src/systems/auth/.ctx/adr/ADR-001.md",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-001",
                "file_path": "src/systems/auth/.ctx/adr/ADR-001.md",
                "system": "src/systems/auth/.ctx",
            },
            fix_description="Register ADR-001 in database by parsing the ADR file",
        )

        # Apply fix
        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True
        assert "already registered" in result.message
        assert result.files_modified == []

    def test_fail_when_adr_id_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails when adr_id is not provided."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists as file but not registered",
            fix_id="unregistered_adr",
            fix_params={
                "file_path": "src/systems/auth/.ctx/adr/ADR-001.md",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "adr_id is required" in result.message

    def test_fail_when_file_path_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails when file_path is not provided."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists as file but not registered",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-001",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "file_path is required" in result.message

    def test_fail_when_adr_file_not_found(self, tmp_path: Path) -> None:
        """Test that fixer fails when ADR file doesn't exist."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists as file but not registered",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-001",
                "file_path": "src/systems/auth/.ctx/adr/ADR-001.md",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "not found" in result.message

    def test_fail_when_db_missing(self, tmp_path: Path) -> None:
        """Test that fixer fails when database doesn't exist."""
        # Create ADR file but no database
        adr_dir = tmp_path / "src" / "systems" / "auth" / ".ctx" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        (adr_dir / "ADR-001.md").write_text("# ADR-001: Test\n")

        db_path = tmp_path / ".ctx" / "knowledge.db"  # Not created

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists as file but not registered",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-001",
                "file_path": "src/systems/auth/.ctx/adr/ADR-001.md",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_parse_adr_with_minimal_content(self, tmp_path: Path) -> None:
        """Test parsing ADR with minimal content uses defaults."""
        # Setup ADR with minimal content
        adr_dir = tmp_path / "src" / "systems" / "auth" / ".ctx" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        adr_file = adr_dir / "ADR-002.md"
        adr_file.write_text("# ADR-002: Minimal ADR\n\nSome content.\n")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists as file but not registered",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-002",
                "file_path": "src/systems/auth/.ctx/adr/ADR-002.md",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True

        # Verify defaults were used
        from cctx.adr_crud import get_adr
        from cctx.database import ContextDB

        with ContextDB(db_path, auto_init=False) as db:
            adr = get_adr(db, "ADR-002")
            assert adr is not None
            assert adr["title"] == "Minimal ADR"
            assert adr["status"] == "proposed"  # Default status
            assert adr["context"] is None
            assert adr["decision"] is None

    def test_parse_adr_with_different_status_formats(self, tmp_path: Path) -> None:
        """Test parsing ADR with various status formats."""
        adr_dir = tmp_path / "src" / "systems" / "auth" / ".ctx" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Test with uppercase status
        adr_file = adr_dir / "ADR-003.md"
        adr_file.write_text("# ADR-003: Test\n\n- **Status**: DEPRECATED\n")

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        issue = FixableIssue(
            system="src/systems/auth/.ctx",
            check="db_registration",
            severity="warning",
            message="ADR exists",
            fix_id="unregistered_adr",
            fix_params={
                "adr_id": "ADR-003",
                "file_path": "src/systems/auth/.ctx/adr/ADR-003.md",
            },
        )

        fixer = AdrFixer(tmp_path, db_path)
        result = fixer.fix(issue)

        assert result.success is True

        from cctx.adr_crud import get_adr
        from cctx.database import ContextDB

        with ContextDB(db_path, auto_init=False) as db:
            adr = get_adr(db, "ADR-003")
            assert adr["status"] == "deprecated"  # Normalized to lowercase


# -----------------------------------------------------------------------------
# FixerRegistry Tests
# -----------------------------------------------------------------------------


class TestFixerRegistry:
    """Tests for FixerRegistry."""

    def test_register_fixer(self) -> None:
        """Test registering a fixer."""
        registry = FixerRegistry()
        registry.register(SnapshotFixer)

        assert registry.has_fixer("missing_snapshot") is True
        assert "missing_snapshot" in registry.list_fix_ids()

    def test_register_fixer_without_fix_id(self) -> None:
        """Test that registering a fixer without fix_id raises error."""

        # Create a fixer class without fix_id
        class BadFixer(BaseFixer):
            fix_id = ""

            def fix(self, issue: FixableIssue) -> FixResult:
                return FixResult(success=True, message="")

        registry = FixerRegistry()
        with pytest.raises(ValueError, match="no fix_id defined"):
            registry.register(BadFixer)

    def test_register_duplicate_fixer(self) -> None:
        """Test that registering duplicate fix_id raises error."""
        registry = FixerRegistry()
        registry.register(SnapshotFixer)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(SnapshotFixer)

    def test_get_fixer(self, tmp_path: Path) -> None:
        """Test getting a fixer instance."""
        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        registry = FixerRegistry()
        registry.register(SnapshotFixer)

        fixer = registry.get_fixer("missing_snapshot", tmp_path, db_path)
        assert fixer is not None
        assert isinstance(fixer, SnapshotFixer)
        assert fixer.project_root == tmp_path
        assert fixer.db_path == db_path

    def test_get_fixer_unknown_id(self, tmp_path: Path) -> None:
        """Test that getting unknown fix_id returns None."""
        db_path = tmp_path / ".ctx" / "knowledge.db"

        registry = FixerRegistry()
        fixer = registry.get_fixer("unknown_fix_id", tmp_path, db_path)
        assert fixer is None

    def test_has_fixer(self) -> None:
        """Test has_fixer method."""
        registry = FixerRegistry()
        assert registry.has_fixer("missing_snapshot") is False

        registry.register(SnapshotFixer)
        assert registry.has_fixer("missing_snapshot") is True
        assert registry.has_fixer("unknown") is False

    def test_list_fix_ids(self) -> None:
        """Test list_fix_ids returns sorted list."""
        registry = FixerRegistry()
        registry.register(SnapshotFixer)
        registry.register(GraphFixer)
        registry.register(MissingCtxDirFixer)

        fix_ids = registry.list_fix_ids()
        assert fix_ids == sorted(fix_ids)  # Verify sorted
        assert "missing_snapshot" in fix_ids
        assert "stale_graph" in fix_ids
        assert "missing_ctx_dir" in fix_ids

    def test_apply_fix(self, tmp_path: Path) -> None:
        """Test apply_fix convenience method."""
        # Setup project structure
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / ".ctx" / "knowledge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path)

        # Create issue
        issue = FixableIssue(
            system="src/systems/auth",
            check="snapshot_exists",
            severity="error",
            message="snapshot.md is missing",
            fix_id="missing_snapshot",
            fix_description="Create snapshot.md from template",
        )

        # Apply fix through registry
        registry = FixerRegistry()
        registry.register(SnapshotFixer)
        result = registry.apply_fix(issue, tmp_path, db_path)

        assert result.success is True
        assert (ctx_path / "snapshot.md").exists()

    def test_apply_fix_unknown_id(self, tmp_path: Path) -> None:
        """Test apply_fix returns failure for unknown fix_id."""
        db_path = tmp_path / ".ctx" / "knowledge.db"

        # Create issue with unknown fix_id
        issue = FixableIssue(
            system="src/systems/auth",
            check="some_check",
            severity="error",
            message="Some issue",
            fix_id="unknown_fix_id",
            fix_description="Unknown fix",
        )

        registry = FixerRegistry()
        result = registry.apply_fix(issue, tmp_path, db_path)

        assert result.success is False
        assert "No fixer registered" in result.message


# -----------------------------------------------------------------------------
# Global Registry Tests
# -----------------------------------------------------------------------------


class TestGlobalRegistry:
    """Tests for get_global_registry function."""

    def test_returns_populated_registry(self) -> None:
        """Test that global registry is populated with built-in fixers."""
        registry = get_global_registry()

        # Should have all built-in fixers
        assert registry.has_fixer("missing_snapshot") is True
        assert registry.has_fixer("stale_graph") is True
        assert registry.has_fixer("missing_ctx_dir") is True
        assert registry.has_fixer("missing_template_file") is True
        assert registry.has_fixer("unregistered_adr") is True

    def test_returns_singleton(self) -> None:
        """Test that get_global_registry returns the same instance."""
        registry1 = get_global_registry()
        registry2 = get_global_registry()
        assert registry1 is registry2
