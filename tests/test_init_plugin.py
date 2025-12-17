"""Tests for cctx init command plugin installation functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from cctx.cli import app

runner = CliRunner()


class TestInitPluginInstallation:
    """Tests for the init command's plugin installation."""

    def test_init_installs_plugin(self, tmp_path: Path) -> None:
        """Test init command installs plugin to .claude/plugins/living-context/."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create minimal plugin structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test Command")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Test Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert "Success:" in result.stdout or "Installed plugin" in result.stdout

        # Verify files were copied to project scope location
        dest_dir = tmp_path / ".claude" / "plugins" / "living-context"
        assert dest_dir.exists()
        assert (dest_dir / ".claude-plugin" / "plugin.json").exists()
        assert (dest_dir / "commands" / "context" / "test.md").exists()
        assert (dest_dir / "skills" / "living-context" / "SKILL.md").exists()
        assert (dest_dir / "hooks" / "pre-write-ctx-check.sh").exists()

    def test_init_creates_both_ctx_and_plugin(self, tmp_path: Path) -> None:
        """Test init creates both .ctx/ and plugin in one command."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create minimal plugin structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0

        # Verify .ctx/ was created
        assert (tmp_path / ".ctx").exists()
        assert (tmp_path / ".ctx" / "knowledge.db").exists()
        assert (tmp_path / ".ctx" / "graph.json").exists()

        # Verify plugin was installed
        plugin_dir = tmp_path / ".claude" / "plugins" / "living-context"
        assert plugin_dir.exists()
        assert (plugin_dir / ".claude-plugin" / "plugin.json").exists()

    def test_init_skips_existing_plugin(self, tmp_path: Path) -> None:
        """Test init skips plugin installation if already installed."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create minimal plugin structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            # First init
            runner.invoke(app, ["init", str(tmp_path)])
            # Second init
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert "Plugin already installed" in result.stdout

    def test_init_force_reinstalls_plugin(self, tmp_path: Path) -> None:
        """Test init --force reinstalls plugin."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create minimal plugin structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"version": "1.0"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            # First init
            runner.invoke(app, ["init", str(tmp_path)])

            # Verify initial content
            plugin_json = tmp_path / ".claude" / "plugins" / "living-context" / ".claude-plugin" / "plugin.json"
            assert "1.0" in plugin_json.read_text()

            # Update source
            (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"version": "2.0"}')

            # Force reinit
            result = runner.invoke(app, ["init", str(tmp_path), "--force"])

        assert result.exit_code == 0
        assert "Overwriting" in result.output
        # Verify updated content
        assert "2.0" in plugin_json.read_text()

    def test_init_json_output_includes_plugin_status(self, tmp_path: Path) -> None:
        """Test init --json includes plugin installation status."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create minimal plugin structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["ctx"]["status"] == "created"
        assert data["plugin"]["status"] == "installed"
        assert "path" in data["plugin"]

    def test_init_fails_gracefully_if_plugin_source_not_found(self, tmp_path: Path) -> None:
        """Test init fails gracefully when plugin source not found."""
        with mock.patch("cctx.cli._get_plugin_source_path", return_value=None):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code != 0
        assert "Plugin files not found" in result.output

    def test_init_preserves_nested_plugin_directories(self, tmp_path: Path) -> None:
        """Test that nested directory structure in plugin is preserved."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()

        # Create nested structure
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')

        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "cmd1.md").write_text("# Cmd1")
        (test_plugin_src / "commands" / "context" / "cmd2.md").write_text("# Cmd2")

        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")

        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0

        dest_dir = tmp_path / ".claude" / "plugins" / "living-context"
        assert (dest_dir / "commands" / "context" / "cmd1.md").exists()
        assert (dest_dir / "commands" / "context" / "cmd2.md").exists()


class TestInitStatusChecking:
    """Tests for the init command's status checking functionality."""

    def test_init_detects_partial_ctx(self, tmp_path: Path) -> None:
        """Test init warns about partial .ctx/ installation."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        # Create partial .ctx/ (missing knowledge.db)
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "graph.json").write_text("[]")
        (ctx_dir / "templates").mkdir()

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert "incomplete" in result.output.lower() or "partial" in result.output.lower()
        assert "doctor --fix" in result.output

    def test_init_detects_partial_plugin(self, tmp_path: Path) -> None:
        """Test init warns about partial plugin installation."""
        test_plugin_src = tmp_path / "plugin_source"
        test_plugin_src.mkdir()
        (test_plugin_src / ".claude-plugin").mkdir()
        (test_plugin_src / ".claude-plugin" / "plugin.json").write_text('{"name": "test"}')
        (test_plugin_src / "commands").mkdir()
        (test_plugin_src / "commands" / "context").mkdir()
        (test_plugin_src / "commands" / "context" / "test.md").write_text("# Test")
        (test_plugin_src / "skills").mkdir()
        (test_plugin_src / "skills" / "living-context").mkdir()
        (test_plugin_src / "skills" / "living-context" / "SKILL.md").write_text("# Skill")
        (test_plugin_src / "hooks").mkdir()
        (test_plugin_src / "hooks" / "pre-write-ctx-check.sh").write_text("#!/bin/bash")

        # First, do a full init
        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            runner.invoke(app, ["init", str(tmp_path)])

        # Now corrupt the plugin by removing a required file
        plugin_dir = tmp_path / ".claude" / "plugins" / "living-context"
        (plugin_dir / "hooks" / "pre-write-ctx-check.sh").unlink()

        with mock.patch("cctx.cli._get_plugin_source_path", return_value=test_plugin_src):
            result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert "incomplete" in result.output.lower() or "partial" in result.output.lower()
        assert "doctor --fix" in result.output
