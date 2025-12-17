"""Tests for system directory scaffolding."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from cctx.config import CctxConfig
from cctx.scaffolder import (
    SYSTEM_TEMPLATES,
    ScaffoldError,
    scaffold_project_ctx,
    scaffold_system_ctx,
)


class TestScaffoldSystemCtx:
    """Tests for scaffold_system_ctx function."""

    def test_creates_ctx_directory(self, tmp_path: Path) -> None:
        """Test that .ctx/ directory is created."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        result = scaffold_system_ctx("Auth System", system_path, config)

        assert result == system_path / ".ctx"
        assert result.exists()
        assert result.is_dir()

    def test_creates_all_template_files(self, tmp_path: Path) -> None:
        """Test that all template files are created."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        scaffold_system_ctx("Auth System", system_path, config)
        ctx_path = system_path / ".ctx"

        # Check all template files exist
        assert (ctx_path / "snapshot.md").exists()
        assert (ctx_path / "constraints.md").exists()
        assert (ctx_path / "decisions.md").exists()
        assert (ctx_path / "debt.md").exists()

    def test_creates_adr_subdirectory(self, tmp_path: Path) -> None:
        """Test that adr/ subdirectory is created."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        scaffold_system_ctx("Auth System", system_path, config)

        adr_dir = system_path / ".ctx" / "adr"
        assert adr_dir.exists()
        assert adr_dir.is_dir()

    def test_adr_directory_is_empty(self, tmp_path: Path) -> None:
        """Test that adr/ directory is created empty."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        scaffold_system_ctx("Auth System", system_path, config)

        adr_dir = system_path / ".ctx" / "adr"
        assert list(adr_dir.iterdir()) == []

    def test_renders_system_name_in_snapshot(self, tmp_path: Path) -> None:
        """Test that system name is rendered in snapshot.md."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        scaffold_system_ctx("Auth System", system_path, config)

        snapshot_content = (system_path / ".ctx" / "snapshot.md").read_text()
        assert "# Auth System" in snapshot_content
        assert "{System Name}" not in snapshot_content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        config = CctxConfig()
        # Deeply nested path that doesn't exist
        system_path = tmp_path / "src" / "systems" / "deep" / "nested" / "auth"

        result = scaffold_system_ctx("Auth System", system_path, config)

        assert result.exists()
        assert system_path.exists()

    def test_raises_error_if_ctx_exists(self, tmp_path: Path) -> None:
        """Test that error is raised if .ctx/ already exists."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        # Create .ctx/ manually first
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True)

        with pytest.raises(ScaffoldError, match="already exists"):
            scaffold_system_ctx("Auth System", system_path, config)

    def test_does_not_overwrite_existing_ctx(self, tmp_path: Path) -> None:
        """Test that existing .ctx/ is not overwritten."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        # Create .ctx/ with a marker file
        ctx_path = system_path / ".ctx"
        ctx_path.mkdir(parents=True)
        marker_file = ctx_path / "marker.txt"
        marker_file.write_text("original content")

        with contextlib.suppress(ScaffoldError):
            scaffold_system_ctx("Auth System", system_path, config)

        # Marker file should still exist
        assert marker_file.exists()
        assert marker_file.read_text() == "original content"

    def test_uses_custom_ctx_dir_name(self, tmp_path: Path) -> None:
        """Test that custom ctx_dir name from config is used."""
        config = CctxConfig(ctx_dir=".context")
        system_path = tmp_path / "systems" / "auth"

        result = scaffold_system_ctx("Auth System", system_path, config)

        assert result == system_path / ".context"
        assert result.exists()

    def test_handles_special_characters_in_system_name(self, tmp_path: Path) -> None:
        """Test that special characters in system name are handled."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        # System name with special characters
        scaffold_system_ctx("Auth & Authorization System", system_path, config)

        snapshot_content = (system_path / ".ctx" / "snapshot.md").read_text()
        assert "# Auth & Authorization System" in snapshot_content

    def test_files_are_utf8_encoded(self, tmp_path: Path) -> None:
        """Test that created files are UTF-8 encoded."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        scaffold_system_ctx("Authentication System", system_path, config)

        # Should be readable as UTF-8 without errors
        for template in SYSTEM_TEMPLATES:
            file_path = system_path / ".ctx" / f"{template}.md"
            content = file_path.read_text(encoding="utf-8")
            assert content  # Non-empty

    def test_returns_created_ctx_path(self, tmp_path: Path) -> None:
        """Test that function returns the created .ctx/ path."""
        config = CctxConfig()
        system_path = tmp_path / "systems" / "auth"

        result = scaffold_system_ctx("Auth System", system_path, config)

        assert isinstance(result, Path)
        assert result == system_path / ".ctx"


class TestScaffoldProjectCtx:
    """Tests for scaffold_project_ctx function."""

    def test_creates_ctx_directory(self, tmp_path: Path) -> None:
        """Test that .ctx/ directory is created."""
        config = CctxConfig()

        result = scaffold_project_ctx(tmp_path, config)

        assert result == tmp_path / ".ctx"
        assert result.exists()
        assert result.is_dir()

    def test_creates_graph_json(self, tmp_path: Path) -> None:
        """Test that graph.json is created."""
        config = CctxConfig()

        scaffold_project_ctx(tmp_path, config)

        graph_file = tmp_path / ".ctx" / "graph.json"
        assert graph_file.exists()
        assert graph_file.read_text() == "[]"

    def test_creates_templates_directory(self, tmp_path: Path) -> None:
        """Test that templates/ directory is created."""
        config = CctxConfig()

        scaffold_project_ctx(tmp_path, config)

        templates_dir = tmp_path / ".ctx" / "templates"
        assert templates_dir.exists()
        assert templates_dir.is_dir()

    def test_templates_directory_contains_all_templates(self, tmp_path: Path) -> None:
        """Test that templates/ contains all template files."""
        config = CctxConfig()

        scaffold_project_ctx(tmp_path, config)

        templates_dir = tmp_path / ".ctx" / "templates"
        assert (templates_dir / "snapshot.template.md").exists()
        assert (templates_dir / "constraints.template.md").exists()
        assert (templates_dir / "decisions.template.md").exists()
        assert (templates_dir / "debt.template.md").exists()
        assert (templates_dir / "adr.template.md").exists()

    def test_creates_readme(self, tmp_path: Path) -> None:
        """Test that README.md is created."""
        config = CctxConfig()

        scaffold_project_ctx(tmp_path, config)

        readme_file = tmp_path / ".ctx" / "README.md"
        assert readme_file.exists()
        assert "Living Context" in readme_file.read_text()

    def test_raises_error_if_ctx_exists(self, tmp_path: Path) -> None:
        """Test that error is raised if .ctx/ already exists."""
        config = CctxConfig()

        # Create .ctx/ manually first
        ctx_path = tmp_path / ".ctx"
        ctx_path.mkdir()

        with pytest.raises(ScaffoldError, match="already exists"):
            scaffold_project_ctx(tmp_path, config)

    def test_uses_custom_ctx_dir_name(self, tmp_path: Path) -> None:
        """Test that custom ctx_dir name from config is used."""
        config = CctxConfig(ctx_dir=".context")

        result = scaffold_project_ctx(tmp_path, config)

        assert result == tmp_path / ".context"
        assert result.exists()

    def test_uses_custom_graph_name(self, tmp_path: Path) -> None:
        """Test that custom graph_name from config is used."""
        config = CctxConfig(graph_name="dependencies.json")

        scaffold_project_ctx(tmp_path, config)

        graph_file = tmp_path / ".ctx" / "dependencies.json"
        assert graph_file.exists()

    def test_returns_created_ctx_path(self, tmp_path: Path) -> None:
        """Test that function returns the created .ctx/ path."""
        config = CctxConfig()

        result = scaffold_project_ctx(tmp_path, config)

        assert isinstance(result, Path)
        assert result == tmp_path / ".ctx"


class TestScaffoldError:
    """Tests for ScaffoldError exception."""

    def test_scaffold_error_is_exception(self) -> None:
        """Test that ScaffoldError is an Exception."""
        error = ScaffoldError("test error")
        assert isinstance(error, Exception)

    def test_scaffold_error_message(self) -> None:
        """Test that ScaffoldError preserves message."""
        error = ScaffoldError("test error message")
        assert str(error) == "test error message"


class TestSystemTemplatesConstant:
    """Tests for SYSTEM_TEMPLATES constant."""

    def test_contains_expected_templates(self) -> None:
        """Test that SYSTEM_TEMPLATES contains all expected templates."""
        assert "snapshot" in SYSTEM_TEMPLATES
        assert "constraints" in SYSTEM_TEMPLATES
        assert "decisions" in SYSTEM_TEMPLATES
        assert "debt" in SYSTEM_TEMPLATES

    def test_does_not_contain_adr(self) -> None:
        """Test that SYSTEM_TEMPLATES does not include adr (per-decision template)."""
        assert "adr" not in SYSTEM_TEMPLATES

    def test_has_exactly_four_templates(self) -> None:
        """Test that SYSTEM_TEMPLATES has exactly 4 templates."""
        assert len(SYSTEM_TEMPLATES) == 4
