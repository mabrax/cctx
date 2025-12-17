"""Tests for lctx CLI commands."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lctx.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test --version flag shows version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "lctx version" in result.stdout


def test_help() -> None:
    """Test --help flag shows help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Living Context CLI Tool" in result.stdout


# -----------------------------------------------------------------------------
# Init Command Tests
# -----------------------------------------------------------------------------


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_ctx_directory(self, tmp_path: Path) -> None:
        """Test init command creates .ctx/ directory."""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "Success:" in result.stdout
        assert (tmp_path / ".ctx").exists()
        assert (tmp_path / ".ctx" / "knowledge.db").exists()
        assert (tmp_path / ".ctx" / "graph.json").exists()
        assert (tmp_path / ".ctx" / "templates").exists()

    def test_init_creates_database(self, tmp_path: Path) -> None:
        """Test init command initializes the database."""
        runner.invoke(app, ["init", str(tmp_path)])
        db_path = tmp_path / ".ctx" / "knowledge.db"
        assert db_path.exists()
        # Verify database has tables
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "systems" in tables
        assert "adrs" in tables

    def test_init_skips_if_already_exists(self, tmp_path: Path) -> None:
        """Test init command skips if .ctx/ already exists."""
        # First init
        runner.invoke(app, ["init", str(tmp_path)])
        # Second init should succeed but skip
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already initialized" in result.output

    def test_init_force_reinitializes(self, tmp_path: Path) -> None:
        """Test init --force reinitializes existing .ctx/."""
        # First init
        runner.invoke(app, ["init", str(tmp_path)])
        # Modify something to verify it gets overwritten
        (tmp_path / ".ctx" / "test_marker.txt").write_text("marker")
        # Force reinit
        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert result.exit_code == 0
        assert "Overwriting" in result.output
        assert "Created .ctx/" in result.output
        # Marker should be gone after reinit
        assert not (tmp_path / ".ctx" / "test_marker.txt").exists()

    def test_init_with_custom_ctx_dir(self, tmp_path: Path) -> None:
        """Test init command with custom --ctx-dir."""
        result = runner.invoke(
            app, ["init", str(tmp_path), "--ctx-dir", ".custom-ctx"]
        )
        assert result.exit_code == 0
        assert (tmp_path / ".custom-ctx").exists()
        assert (tmp_path / ".custom-ctx" / "knowledge.db").exists()

    def test_init_json_output(self, tmp_path: Path) -> None:
        """Test init command with --json flag."""
        result = runner.invoke(app, ["init", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["ctx"]["status"] == "created"
        assert data["plugin"]["status"] == "installed"

    def test_init_quiet_mode(self, tmp_path: Path) -> None:
        """Test init command with --quiet flag."""
        result = runner.invoke(app, ["init", str(tmp_path), "--quiet"])
        assert result.exit_code == 0
        # Quiet mode should have minimal output
        assert len(result.stdout.strip()) < 100


# -----------------------------------------------------------------------------
# Health Command Tests
# -----------------------------------------------------------------------------


class TestHealthCommand:
    """Tests for the health command."""

    def test_health_without_ctx_fails(self, tmp_path: Path) -> None:
        """Test health command fails when no .ctx directory exists."""
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1
            assert "Could not find project root" in result.output
        finally:
            os.chdir(original_cwd)

    def test_health_with_initialized_ctx(self, tmp_path: Path) -> None:
        """Test health command succeeds with initialized .ctx/."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 0
            assert "Success:" in result.stdout or "healthy" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    def test_health_deep_mode(self, tmp_path: Path) -> None:
        """Test health command with --deep flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health", "--deep"])
            assert result.exit_code == 0
            # Deep mode should mention Phase 4
            assert "Phase 4" in result.stdout or "deep" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    def test_health_json_output(self, tmp_path: Path) -> None:
        """Test health command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "healthy" in data
            assert "checks" in data
        finally:
            os.chdir(original_cwd)

    def test_health_with_custom_ctx_dir(self, tmp_path: Path) -> None:
        """Test health command with custom context directory."""
        # Initialize with custom directory
        runner.invoke(app, ["init", str(tmp_path), "--ctx-dir", ".my-ctx"])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Should fail without specifying the custom dir (can't find root)
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1

            # Should succeed when specifying the custom dir
            result = runner.invoke(app, ["health", "--ctx-dir", ".my-ctx"])
            assert result.exit_code == 0
            assert "healthy" in result.stdout.lower() or "Success" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_health_fails_without_db(self, tmp_path: Path) -> None:
        """Test health command fails when database is missing."""
        # Create .ctx/ without database
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# Status Command Tests
# -----------------------------------------------------------------------------


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_without_ctx_fails(self, tmp_path: Path) -> None:
        """Test status command fails when no .ctx directory exists."""
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "Could not find project root" in result.output
        finally:
            os.chdir(original_cwd)

    def test_status_with_initialized_ctx(self, tmp_path: Path) -> None:
        """Test status command succeeds with initialized .ctx/."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "Systems:" in result.stdout
            assert "ADRs:" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_status_json_output(self, tmp_path: Path) -> None:
        """Test status command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "systems" in data
            assert "adrs" in data
            assert "dependencies" in data
        finally:
            os.chdir(original_cwd)

    def test_status_quiet_mode(self, tmp_path: Path) -> None:
        """Test status command with --quiet flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["status", "--quiet"])
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# Sync Command Tests
# -----------------------------------------------------------------------------


class TestSyncCommand:
    """Tests for the sync command."""

    def test_sync_without_ctx_fails(self, tmp_path: Path) -> None:
        """Test sync command fails when no .ctx directory exists."""
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["sync"])
            assert result.exit_code == 1
            assert "Could not find project root" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_with_initialized_ctx(self, tmp_path: Path) -> None:
        """Test sync command succeeds with initialized .ctx/."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["sync"])
            assert result.exit_code == 0
            # Sync should check for stale docs
            assert "Checking context at" in result.stdout or "up to date" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_sync_dry_run(self, tmp_path: Path) -> None:
        """Test sync command with --dry-run flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["sync", "--dry-run"])
            assert result.exit_code == 0
            # Dry run warning goes to stderr which is part of result.output
            assert "dry run" in result.output.lower()
        finally:
            os.chdir(original_cwd)

    def test_sync_json_output(self, tmp_path: Path) -> None:
        """Test sync command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["sync", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "dry_run" in data
            assert "stale_files" in data
            assert "needs_update" in data
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# Validate Command Tests
# -----------------------------------------------------------------------------


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_without_ctx_fails(self, tmp_path: Path) -> None:
        """Test validate command fails when no .ctx directory exists."""
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["validate"])
            assert result.exit_code == 1
            assert "Could not find project root" in result.output
        finally:
            os.chdir(original_cwd)

    def test_validate_with_initialized_ctx(self, tmp_path: Path) -> None:
        """Test validate command succeeds with initialized .ctx/."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["validate"])
            assert result.exit_code == 0
            assert "Success:" in result.stdout or "passed" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    def test_validate_fails_without_db(self, tmp_path: Path) -> None:
        """Test validate command fails with exit code 2 when database missing."""
        # Create .ctx/ without database
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["validate"])
            assert result.exit_code == 2  # Validation failure exit code
        finally:
            os.chdir(original_cwd)

    def test_validate_json_output(self, tmp_path: Path) -> None:
        """Test validate command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["validate", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "valid" in data
            assert "checks" in data
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# Add-System Command Tests
# -----------------------------------------------------------------------------


class TestAddSystemCommand:
    """Tests for the add-system command."""

    def test_add_system_creates_ctx(self, tmp_path: Path) -> None:
        """Test add-system command creates .ctx/ for system."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["add-system", "src/systems/auth"])
            assert result.exit_code == 0
            assert "Success:" in result.stdout
            system_ctx = tmp_path / "src" / "systems" / "auth" / ".ctx"
            assert system_ctx.exists()
            assert (system_ctx / "snapshot.md").exists()
            assert (system_ctx / "constraints.md").exists()
            assert (system_ctx / "decisions.md").exists()
            assert (system_ctx / "debt.md").exists()
            assert (system_ctx / "adr").is_dir()
        finally:
            os.chdir(original_cwd)

    def test_add_system_with_custom_name(self, tmp_path: Path) -> None:
        """Test add-system command with custom --name."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(
                app,
                ["add-system", "src/systems/auth", "--name", "Authentication Module"],
            )
            assert result.exit_code == 0
            assert "Authentication Module" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_add_system_fails_if_exists(self, tmp_path: Path) -> None:
        """Test add-system command fails if .ctx/ already exists."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(app, ["add-system", "src/systems/auth"])
            # Second attempt should fail
            result = runner.invoke(app, ["add-system", "src/systems/auth"])
            assert result.exit_code == 1
            assert "already exists" in result.output
        finally:
            os.chdir(original_cwd)

    def test_add_system_json_output(self, tmp_path: Path) -> None:
        """Test add-system command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(
                app, ["add-system", "src/systems/auth", "--json"]
            )
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["success"] is True
            assert "ctx_path" in data
        finally:
            os.chdir(original_cwd)


    def test_add_system_outside_root_fails(self, tmp_path: Path) -> None:
        """Test add-system fails gracefully when path is outside project root."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Try to add a system outside the project root
            outside_path = tmp_path.parent / "outside_system"
            result = runner.invoke(app, ["add-system", str(outside_path)])
            assert result.exit_code == 1
            # Check output (mix of stdout/stderr)
            if "must be inside project root" not in result.output:
                print(f"Output was: {result.output!r}")
            assert "must be inside project root" in result.output
        finally:
            os.chdir(original_cwd)


    def test_add_system_no_redundant_suffix(self, tmp_path: Path) -> None:
        """Test add-system avoids 'System System' suffix."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Create a directory ending in "system"
            (tmp_path / "src" / "inventory-system").mkdir(parents=True)

            result = runner.invoke(app, ["add-system", "src/inventory-system"])
            assert result.exit_code == 0

            # Check the generated name in knowledge.db
            from lctx.database import ContextDB
            db_path = tmp_path / ".ctx" / "knowledge.db"
            with ContextDB(db_path, auto_init=False) as db:
                rows = db.fetchall("SELECT path, name FROM systems")
                found = False
                for row in rows:
                    if row["path"] == "src/inventory-system":
                        assert row["name"] == "Inventory System"
                        found = True
                        break

                if not found:
                    pytest.fail("System 'src/inventory-system' not found in database")
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# ADR Command Tests
# -----------------------------------------------------------------------------


class TestAdrCommand:
    """Tests for the adr command."""

    def test_adr_creates_file(self, tmp_path: Path) -> None:
        """Test adr command creates ADR file."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(
                app, ["adr", "Use PostgreSQL for persistence"]
            )
            assert result.exit_code == 0
            assert "Success:" in result.stdout
            assert "ADR-001" in result.stdout
            # Check file was created
            adr_dir = tmp_path / ".ctx" / "adr"
            adr_files = list(adr_dir.glob("ADR-001-*.md"))
            assert len(adr_files) == 1
        finally:
            os.chdir(original_cwd)

    def test_adr_increments_number(self, tmp_path: Path) -> None:
        """Test adr command increments ADR number."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(app, ["adr", "First decision"])
            result = runner.invoke(app, ["adr", "Second decision"])
            assert result.exit_code == 0
            assert "ADR-002" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_adr_in_system(self, tmp_path: Path) -> None:
        """Test adr command with --system flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(app, ["add-system", "src/systems/auth"])
            result = runner.invoke(
                app,
                ["adr", "Use JWT tokens", "--system", "src/systems/auth"],
            )
            assert result.exit_code == 0
            # Check file was created in system's adr directory
            system_adr_dir = tmp_path / "src" / "systems" / "auth" / ".ctx" / "adr"
            adr_files = list(system_adr_dir.glob("ADR-001-*.md"))
            assert len(adr_files) == 1
        finally:
            os.chdir(original_cwd)

    def test_adr_file_content(self, tmp_path: Path) -> None:
        """Test adr command creates file with correct content."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(app, ["adr", "Use PostgreSQL"])
            adr_dir = tmp_path / ".ctx" / "adr"
            adr_file = list(adr_dir.glob("ADR-001-*.md"))[0]
            content = adr_file.read_text()
            assert "ADR-001: Use PostgreSQL" in content
            assert "Status**: proposed" in content
            # Should have replaced YYYY-MM-DD with actual date
            assert "YYYY-MM-DD" not in content
        finally:
            os.chdir(original_cwd)

    def test_adr_json_output(self, tmp_path: Path) -> None:
        """Test adr command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(
                app, ["adr", "Use PostgreSQL", "--json"]
            )
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["success"] is True
            assert data["adr_id"] == "ADR-001"
            assert "adr_path" in data
        finally:
            os.chdir(original_cwd)

    def test_adr_status_replacement(self, tmp_path: Path) -> None:
        """Test adr command correctly replaces the status placeholder."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(app, ["adr", "Test Decision"])
            adr_dir = tmp_path / ".ctx" / "adr"
            adr_file = list(adr_dir.glob("ADR-001-*.md"))[0]
            content = adr_file.read_text()
            # Should have replaced the list with just "proposed"
            assert "**Status**: proposed" in content
            assert "proposed | accepted" not in content
        finally:
            os.chdir(original_cwd)

    def test_adr_outside_root_fails(self, tmp_path: Path) -> None:
        """Test adr command fails gracefully when system path is outside root."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Create a system directory outside root manually (since add-system would fail)
            outside_system = tmp_path.parent / "outside_system"
            outside_system.mkdir(exist_ok=True)

            # Try to create ADR in that system
            # Note: We need to pass the path as it would be resolved
            result = runner.invoke(
                app, ["adr", "Bad Path", "--system", str(outside_system)]
            )
            # This fails because system path resolution happens before the check we added
            # But let's see if our error handling catches it
            assert result.exit_code == 1
            if "must be inside project root" not in result.output:
                print(f"Output was: {result.output!r}")
            assert "must be inside project root" in result.output
        finally:
            os.chdir(original_cwd)

    def test_adr_status_replacement_robustness(self, tmp_path: Path) -> None:
        """Test adr command replaces status even with modified template."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)

            # Modify the template to have different status options
            template_path = tmp_path / ".ctx" / "templates" / "adr.template.md"
            if template_path.exists():
                content = template_path.read_text()
                # Change the status line to something unexpected
                content = content.replace(
                    "**Status**: proposed | accepted | deprecated | superseded",
                    "**Status**: draft | final"
                )
                template_path.write_text(content)

            runner.invoke(app, ["adr", "Robust Decision"])
            adr_dir = tmp_path / ".ctx" / "adr"
            adr_file = list(adr_dir.glob("ADR-001-*.md"))[0]
            content = adr_file.read_text()

            assert "**Status**: proposed" in content
            assert "draft | final" not in content
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# List Command Tests
# -----------------------------------------------------------------------------


class TestListCommand:
    """Tests for the list command."""

    def test_list_systems_empty(self, tmp_path: Path) -> None:
        """Test list systems when none registered."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "systems"])
            assert result.exit_code == 0
            assert "No systems registered" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_systems_with_data(self, tmp_path: Path) -> None:
        """Test list systems with registered systems."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Add a system to database
            from lctx.crud import create_system
            from lctx.database import ContextDB

            db_path = tmp_path / ".ctx" / "knowledge.db"
            with ContextDB(db_path, auto_init=False) as db, db.transaction():
                create_system(db, "src/auth", "Auth System", "Authentication")

            result = runner.invoke(app, ["list", "systems"])
            assert result.exit_code == 0
            assert "src/auth" in result.stdout
            assert "Auth System" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_adrs_empty(self, tmp_path: Path) -> None:
        """Test list adrs when none registered."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "adrs"])
            assert result.exit_code == 0
            assert "No ADRs registered" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_adrs_with_data(self, tmp_path: Path) -> None:
        """Test list adrs with registered ADRs."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Add an ADR to database
            from lctx.adr_crud import create_adr
            from lctx.database import ContextDB

            db_path = tmp_path / ".ctx" / "knowledge.db"
            with ContextDB(db_path, auto_init=False) as db, db.transaction():
                create_adr(
                    db,
                    "ADR-001",
                    "Use PostgreSQL",
                    "accepted",
                    ".ctx/adr/ADR-001.md",
                )

            result = runner.invoke(app, ["list", "adrs"])
            assert result.exit_code == 0
            assert "ADR-001" in result.stdout
            assert "Use PostgreSQL" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_debt_placeholder(self, tmp_path: Path) -> None:
        """Test list debt shows placeholder message."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "debt"])
            assert result.exit_code == 0
            # Debt tracking is placeholder
            assert "not yet implemented" in result.stdout.lower() or "debt.md" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    def test_list_invalid_entity(self, tmp_path: Path) -> None:
        """Test list command with invalid entity type."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "invalid"])
            assert result.exit_code == 1
            assert "Invalid entity type" in result.output
        finally:
            os.chdir(original_cwd)

    def test_list_json_output(self, tmp_path: Path) -> None:
        """Test list command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "systems", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "systems" in data
        finally:
            os.chdir(original_cwd)

    def test_list_quiet_mode(self, tmp_path: Path) -> None:
        """Test list command with --quiet flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Add a system
            from lctx.crud import create_system
            from lctx.database import ContextDB

            db_path = tmp_path / ".ctx" / "knowledge.db"
            with ContextDB(db_path, auto_init=False) as db, db.transaction():
                create_system(db, "src/auth", "Auth System")

            result = runner.invoke(app, ["list", "systems", "--quiet"])
            assert result.exit_code == 0
            # Quiet mode should just show paths
            assert "src/auth" in result.stdout
            # Should not have table formatting
            assert "Registered Systems" not in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_without_db_fails(self, tmp_path: Path) -> None:
        """Test list command fails when database is missing."""
        # Create .ctx/ without database
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["list", "systems"])
            assert result.exit_code == 1
            assert "Database not found" in result.output
        finally:
            os.chdir(original_cwd)


# -----------------------------------------------------------------------------
# Doctor Command Tests
# -----------------------------------------------------------------------------


class TestDoctorCommand:
    """Tests for the doctor command."""

    def test_doctor_without_ctx_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command fails when no .ctx directory exists."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "Could not find project root" in result.output

    def test_doctor_with_initialized_ctx(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command succeeds with initialized .ctx/."""
        runner.invoke(app, ["init", str(tmp_path)])
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        # Doctor should succeed with no issues on fresh init
        assert result.exit_code == 0

    def test_doctor_lists_fixable_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command lists fixable issues."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)
        # Don't create snapshot.md - this creates a fixable issue

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        # Should have exit code 1 due to unfixed issues
        assert result.exit_code == 1
        # Should mention the issue or that fixes are available
        assert "issue" in result.output.lower() or "fix" in result.output.lower()

    def test_doctor_dry_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command with --dry-run flag."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--dry-run"])
        # Dry run should succeed
        assert result.exit_code == 0
        # Should mention what would be done
        assert "would" in result.output.lower() or "dry" in result.output.lower()
        # snapshot.md should NOT have been created
        assert not (ctx_path / "snapshot.md").exists()

    def test_doctor_fix_applies_fixes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command with --fix flag applies fixes."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--fix"])
        # Fix mode should succeed when fixes are applied
        assert result.exit_code == 0
        # snapshot.md should have been created
        assert (ctx_path / "snapshot.md").exists()

    def test_doctor_json_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command with --json flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "success" in data
        assert "total_issues" in data
        assert "fixable_issues" in data
        assert "issues" in data
        assert "fixes" in data

    def test_doctor_json_with_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command JSON output includes issue details."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--json"])
        # Should have exit code 1 due to unfixed issues
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["total_issues"] > 0
        assert data["fixable_issues"] > 0
        # Issues should have fix_id
        fixable = [i for i in data["issues"] if i.get("fixable")]
        assert len(fixable) > 0
        assert "fix_id" in fixable[0]

    def test_doctor_json_with_dry_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command JSON output with --dry-run."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--dry-run", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["mode"] == "dry_run"
        # Should show what would be done
        if data["fixable_issues"] > 0:
            assert len(data["fixes"]) > 0
            assert data["fixes"][0]["status"] == "would_apply"

    def test_doctor_json_with_fix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command JSON output with --fix."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--fix", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["mode"] == "fix"
        assert data["fixes_applied"] > 0
        # Should show applied fixes
        if len(data["fixes"]) > 0:
            assert data["fixes"][0]["status"] == "applied"

    def test_doctor_verbose_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command with --verbose flag."""
        runner.invoke(app, ["init", str(tmp_path)])
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor", "--verbose"])
        assert result.exit_code == 0
        # Verbose should have more detailed output
        # (Just verify it runs without error)

    def test_doctor_exit_code_zero_when_no_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command exits with 0 when no issues found."""
        runner.invoke(app, ["init", str(tmp_path)])
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        # Clean project should have no issues
        assert result.exit_code == 0

    def test_doctor_exit_code_one_when_issues_remain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command exits with 1 when issues remain unfixed."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        # Should have exit code 1 due to unfixed issues
        assert result.exit_code == 1

    def test_doctor_with_custom_ctx_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command with custom context directory."""
        # Initialize with custom directory
        runner.invoke(app, ["init", str(tmp_path), "--ctx-dir", ".my-ctx"])
        monkeypatch.chdir(tmp_path)

        # Should fail without specifying the custom dir (can't find root)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1

        # Should succeed when specifying the custom dir
        result = runner.invoke(app, ["doctor", "--ctx-dir", ".my-ctx"])
        assert result.exit_code == 0

    def test_doctor_fix_is_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that running doctor --fix multiple times is safe."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system directory with missing snapshot
        system_path = tmp_path / "src" / "systems" / "audio"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(tmp_path)
        # First fix
        result1 = runner.invoke(app, ["doctor", "--fix"])
        assert result1.exit_code == 0

        # Second fix should also succeed (idempotent)
        result2 = runner.invoke(app, ["doctor", "--fix"])
        assert result2.exit_code == 0

    def test_doctor_fails_without_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command fails when database is missing."""
        # Create .ctx/ without database
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "not initialized" in result.output.lower() or "init" in result.output.lower()

    def test_doctor_with_non_fixable_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test doctor command behavior when non-fixable issues exist."""
        runner.invoke(app, ["init", str(tmp_path)])

        # Create a system with a snapshot that references a missing file
        # This creates a non-fixable ValidationIssue (not FixableIssue)
        system_path = tmp_path / "src" / "systems" / "auth"
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True, exist_ok=True)
        
        snapshot_content = """# Auth System

## Files

| File | Description |
|------|-------------|
| src/systems/auth/missing_file.py | A file that does not exist |
"""
        (ctx_path / "snapshot.md").write_text(snapshot_content)

        monkeypatch.chdir(tmp_path)
        # Use --verbose to ensure non-fixable issues are listed
        result = runner.invoke(app, ["doctor", "--verbose"])
        
        # Should have exit code 1 due to issues remaining
        assert result.exit_code == 1
        # Should report the issue
        assert "missing_file.py" in result.output
        # Should NOT say it is fixable (checking implicitly by absence of "Fix:" prefix for this issue)
        # But broadly checking if it mentions non-fixable or manual attention
        assert "manual attention" in result.output or "Non-fixable" in result.output

