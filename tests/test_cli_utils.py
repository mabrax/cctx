"""Tests for cctx CLI utility functions."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from cctx.cli_utils import (
    EXIT_SUCCESS,
    EXIT_SYSTEM_ERROR,
    EXIT_USER_ERROR,
    ProjectRootNotFoundError,
    ctx_dir_option,
    db_name_option,
    ensure_path_exists,
    error,
    find_project_root,
    format_error_details,
    get_config_from_context,
    graph_name_option,
    info,
    resolve_path,
    success,
    systems_dir_option,
    warning,
    wire_config,
)
from cctx.config import CctxConfig

# Default CliRunner - note that stderr is mixed into stdout by default
runner = CliRunner()


class TestErrorFormatting:
    """Tests for error formatting helpers (T3.8)."""

    def test_error_exits_with_user_error_code_by_default(self) -> None:
        """Test that error() exits with EXIT_USER_ERROR by default."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            error("Test error message")

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_USER_ERROR
        assert "Error:" in result.output
        assert "Test error message" in result.output

    def test_error_exits_with_custom_exit_code(self) -> None:
        """Test that error() can use a custom exit code."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            error("System error", exit_code=EXIT_SYSTEM_ERROR)

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_SYSTEM_ERROR

    def test_warning_does_not_exit(self) -> None:
        """Test that warning() does not exit the program."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            warning("This is a warning")
            typer.echo("Continued execution")

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_SUCCESS
        assert "Warning:" in result.output
        assert "Continued execution" in result.output

    def test_success_does_not_exit(self) -> None:
        """Test that success() does not exit the program."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            success("Operation completed")
            typer.echo("Continued execution")

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_SUCCESS
        assert "Success:" in result.output
        assert "Continued execution" in result.output

    def test_info_does_not_exit(self) -> None:
        """Test that info() does not exit the program."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            info("Some information")
            typer.echo("Continued execution")

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_SUCCESS
        assert "Some information" in result.output
        assert "Continued execution" in result.output

    def test_format_error_details_empty_list(self) -> None:
        """Test format_error_details with empty list."""
        result = format_error_details([])
        assert result == ""

    def test_format_error_details_single_error(self) -> None:
        """Test format_error_details with single error."""
        result = format_error_details(["First error"])
        assert result == "  - First error"

    def test_format_error_details_multiple_errors(self) -> None:
        """Test format_error_details with multiple errors."""
        result = format_error_details(["Error one", "Error two", "Error three"])
        assert "  - Error one" in result
        assert "  - Error two" in result
        assert "  - Error three" in result
        # Check it's properly newline-separated
        lines = result.split("\n")
        assert len(lines) == 3

    def test_exit_code_constants(self) -> None:
        """Test that exit code constants have correct values."""
        assert EXIT_SUCCESS == 0
        assert EXIT_USER_ERROR == 1
        assert EXIT_SYSTEM_ERROR == 2


class TestPathResolution:
    """Tests for path resolution helpers (T3.7)."""

    def test_find_project_root_in_current_dir(self, tmp_path: Path) -> None:
        """Test finding project root when .ctx is in current directory."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()

        result = find_project_root(start_dir=tmp_path)
        assert result == tmp_path

    def test_find_project_root_in_parent_dir(self, tmp_path: Path) -> None:
        """Test finding project root when .ctx is in parent directory."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()

        child_dir = tmp_path / "src" / "module"
        child_dir.mkdir(parents=True)

        result = find_project_root(start_dir=child_dir)
        assert result == tmp_path

    def test_find_project_root_in_grandparent_dir(self, tmp_path: Path) -> None:
        """Test finding project root when .ctx is in grandparent directory."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()

        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)

        result = find_project_root(start_dir=deep_dir)
        assert result == tmp_path

    def test_find_project_root_not_found(self, tmp_path: Path) -> None:
        """Test ProjectRootNotFoundError when no .ctx directory found."""
        with pytest.raises(ProjectRootNotFoundError) as exc_info:
            find_project_root(start_dir=tmp_path)

        assert ".ctx" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value)

    def test_find_project_root_custom_marker(self, tmp_path: Path) -> None:
        """Test finding project root with custom marker."""
        custom_marker = tmp_path / ".custom-marker"
        custom_marker.mkdir()

        result = find_project_root(start_dir=tmp_path, marker=".custom-marker")
        assert result == tmp_path

    def test_find_project_root_defaults_to_cwd(self, tmp_path: Path) -> None:
        """Test find_project_root uses cwd when no start_dir provided."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()

        # Change to tmp_path and call without start_dir
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = find_project_root()
            assert result == tmp_path
        finally:
            os.chdir(original_cwd)

    def test_find_project_root_ignores_file_with_marker_name(self, tmp_path: Path) -> None:
        """Test that a file named .ctx is not treated as project root marker."""
        # Create a file (not directory) named .ctx
        ctx_file = tmp_path / ".ctx"
        ctx_file.write_text("not a directory")

        with pytest.raises(ProjectRootNotFoundError):
            find_project_root(start_dir=tmp_path)

    def test_find_project_root_handles_symlink(self, tmp_path: Path) -> None:
        """Test finding project root through symlinks."""
        # Create project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        ctx_dir = project_dir / ".ctx"
        ctx_dir.mkdir()

        # Create symlink to project
        link_dir = tmp_path / "link"
        link_dir.symlink_to(project_dir)

        result = find_project_root(start_dir=link_dir)
        # Should resolve to the actual project directory
        assert result.resolve() == project_dir.resolve()

    def test_resolve_path_absolute(self, tmp_path: Path) -> None:
        """Test resolve_path with absolute path."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = resolve_path(str(test_file))
        assert result == test_file.resolve()

    def test_resolve_path_relative(self, tmp_path: Path) -> None:
        """Test resolve_path with relative path."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir()
        test_file.touch()

        result = resolve_path("subdir/test.txt", base_path=tmp_path)
        assert result == test_file.resolve()

    def test_resolve_path_with_path_object(self, tmp_path: Path) -> None:
        """Test resolve_path with Path object input."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = resolve_path(Path("test.txt"), base_path=tmp_path)
        assert result == test_file.resolve()

    def test_resolve_path_defaults_to_cwd(self, tmp_path: Path) -> None:
        """Test resolve_path uses cwd when no base_path provided."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = resolve_path("test.txt")
            assert result == test_file.resolve()
        finally:
            os.chdir(original_cwd)

    def test_ensure_path_exists_success(self, tmp_path: Path) -> None:
        """Test ensure_path_exists with existing path."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = ensure_path_exists(test_file, "test file")
        assert result == test_file

    def test_ensure_path_exists_not_found(self, tmp_path: Path) -> None:
        """Test ensure_path_exists with non-existent path."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            ensure_path_exists(tmp_path / "nonexistent", "test path")

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_USER_ERROR
        assert "does not exist" in result.output

    def test_ensure_path_exists_must_be_dir(self, tmp_path: Path) -> None:
        """Test ensure_path_exists when path must be directory."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            ensure_path_exists(test_file, "test dir", must_be_dir=True)

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_USER_ERROR
        assert "not a directory" in result.output

    def test_ensure_path_exists_must_be_file(self, tmp_path: Path) -> None:
        """Test ensure_path_exists when path must be file."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            ensure_path_exists(test_dir, "test file", must_be_file=True)

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_USER_ERROR
        assert "not a file" in result.output

    def test_ensure_path_exists_dir_success(self, tmp_path: Path) -> None:
        """Test ensure_path_exists with valid directory."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = ensure_path_exists(test_dir, "test directory", must_be_dir=True)
        assert result == test_dir

    def test_ensure_path_exists_file_success(self, tmp_path: Path) -> None:
        """Test ensure_path_exists with valid file."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = ensure_path_exists(test_file, "test file", must_be_file=True)
        assert result == test_file


class TestProjectRootNotFoundError:
    """Tests for ProjectRootNotFoundError exception."""

    def test_error_contains_start_dir(self, tmp_path: Path) -> None:
        """Test error message contains the start directory."""
        err = ProjectRootNotFoundError(tmp_path)
        assert str(tmp_path) in str(err)

    def test_error_contains_marker(self) -> None:
        """Test error message contains the marker name."""
        err = ProjectRootNotFoundError(Path("/some/path"), marker=".ctx")
        assert ".ctx" in str(err)

    def test_error_with_custom_marker(self) -> None:
        """Test error message with custom marker."""
        err = ProjectRootNotFoundError(Path("/some/path"), marker=".custom")
        assert ".custom" in str(err)

    def test_error_attributes(self, tmp_path: Path) -> None:
        """Test error has correct attributes."""
        err = ProjectRootNotFoundError(tmp_path, marker=".myctx")
        assert err.start_dir == tmp_path
        assert err.marker == ".myctx"


class TestConfigWiring:
    """Tests for config wiring helpers (T3.6)."""

    @pytest.fixture
    def _clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean up environment variables after test."""
        env_vars = ["CCTX_CTX_DIR", "CCTX_SYSTEMS_DIR", "CCTX_DB_NAME", "CCTX_GRAPH_NAME"]
        original_values: dict[str, str | None] = {}

        for var in env_vars:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

        yield

        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_wire_config_no_overrides(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with no overrides uses defaults."""
        config = wire_config(start_dir=tmp_path)
        assert config.ctx_dir == ".ctx"
        assert config.systems_dir == "src/systems"
        assert config.db_name == "knowledge.db"
        assert config.graph_name == "graph.json"

    def test_wire_config_with_ctx_dir(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with ctx_dir override."""
        config = wire_config(ctx_dir=".custom-ctx", start_dir=tmp_path)
        assert config.ctx_dir == ".custom-ctx"

    def test_wire_config_with_db_name(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with db_name override."""
        config = wire_config(db_name="custom.db", start_dir=tmp_path)
        assert config.db_name == "custom.db"

    def test_wire_config_with_systems_dir(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with systems_dir override."""
        config = wire_config(systems_dir="lib/modules", start_dir=tmp_path)
        assert config.systems_dir == "lib/modules"

    def test_wire_config_with_graph_name(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with graph_name override."""
        config = wire_config(graph_name="deps.json", start_dir=tmp_path)
        assert config.graph_name == "deps.json"

    def test_wire_config_with_all_overrides(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config with all overrides."""
        config = wire_config(
            ctx_dir=".custom-ctx",
            db_name="custom.db",
            systems_dir="lib/modules",
            graph_name="deps.json",
            start_dir=tmp_path,
        )
        assert config.ctx_dir == ".custom-ctx"
        assert config.db_name == "custom.db"
        assert config.systems_dir == "lib/modules"
        assert config.graph_name == "deps.json"

    def test_wire_config_none_values_ignored(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config ignores None values."""
        config = wire_config(
            ctx_dir=".custom-ctx",
            db_name=None,
            systems_dir=None,
            graph_name=None,
            start_dir=tmp_path,
        )
        assert config.ctx_dir == ".custom-ctx"
        assert config.db_name == "knowledge.db"  # Default
        assert config.systems_dir == "src/systems"  # Default
        assert config.graph_name == "graph.json"  # Default

    def test_wire_config_invalid_value_exits(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config exits on invalid configuration."""
        app = typer.Typer()

        @app.command()
        def cmd() -> None:
            wire_config(db_name="invalid-no-extension", start_dir=tmp_path)

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_USER_ERROR
        assert "Invalid configuration" in result.output

    def test_wire_config_respects_file_config(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config respects config from .cctxrc."""
        cctxrc = tmp_path / ".cctxrc"
        cctxrc.write_text('ctx_dir = ".from-file"\n')

        config = wire_config(start_dir=tmp_path)
        assert config.ctx_dir == ".from-file"

    def test_wire_config_cli_overrides_file(self, tmp_path: Path, _clean_env: None) -> None:
        """Test wire_config CLI overrides take precedence over file config."""
        cctxrc = tmp_path / ".cctxrc"
        cctxrc.write_text('ctx_dir = ".from-file"\n')

        config = wire_config(ctx_dir=".from-cli", start_dir=tmp_path)
        assert config.ctx_dir == ".from-cli"

    def test_get_config_from_context_success(self) -> None:
        """Test get_config_from_context retrieves config from context."""
        app = typer.Typer()
        expected_config = CctxConfig(ctx_dir=".test-ctx")

        @app.callback()
        def callback(ctx: typer.Context) -> None:
            ctx.obj = expected_config

        @app.command()
        def cmd(ctx: typer.Context) -> None:
            config = get_config_from_context(ctx)
            typer.echo(f"ctx_dir={config.ctx_dir}")

        result = runner.invoke(app, ["cmd"])
        assert result.exit_code == EXIT_SUCCESS
        assert "ctx_dir=.test-ctx" in result.output

    def test_get_config_from_context_missing(self) -> None:
        """Test get_config_from_context fails when config not set."""
        app = typer.Typer()

        @app.callback()
        def callback() -> None:
            # Callback exists but doesn't set ctx.obj
            pass

        @app.command()
        def cmd(ctx: typer.Context) -> None:
            get_config_from_context(ctx)

        result = runner.invoke(app, ["cmd"])
        assert result.exit_code == EXIT_SYSTEM_ERROR
        assert "not initialized" in result.output

    def test_get_config_from_context_wrong_type(self) -> None:
        """Test get_config_from_context fails when context has wrong type."""
        app = typer.Typer()

        @app.callback()
        def callback(ctx: typer.Context) -> None:
            ctx.obj = "not a config object"

        @app.command()
        def cmd(ctx: typer.Context) -> None:
            get_config_from_context(ctx)

        result = runner.invoke(app, ["cmd"])
        assert result.exit_code == EXIT_SYSTEM_ERROR
        assert "not initialized" in result.output


class TestTyperOptionFactoryFunctions:
    """Tests for Typer option factory functions."""

    def test_ctx_dir_option_creates_option(self) -> None:
        """Test ctx_dir_option creates a valid option."""
        opt = ctx_dir_option()
        assert opt.default is None

    def test_db_name_option_creates_option(self) -> None:
        """Test db_name_option creates a valid option."""
        opt = db_name_option()
        assert opt.default is None

    def test_systems_dir_option_creates_option(self) -> None:
        """Test systems_dir_option creates a valid option."""
        opt = systems_dir_option()
        assert opt.default is None

    def test_graph_name_option_creates_option(self) -> None:
        """Test graph_name_option creates a valid option."""
        opt = graph_name_option()
        assert opt.default is None

    def test_factory_creates_unique_instances(self) -> None:
        """Test that factory functions create unique instances each time."""
        opt1 = ctx_dir_option()
        opt2 = ctx_dir_option()
        assert opt1 is not opt2

    def test_options_work_in_command(self) -> None:
        """Test that option factory functions work when used in a command."""
        app = typer.Typer()

        @app.command()
        def cmd(
            ctx_dir: str | None = ctx_dir_option(),
            systems_dir: str | None = systems_dir_option(),
        ) -> None:
            if ctx_dir:
                typer.echo(f"ctx_dir={ctx_dir}")
            if systems_dir:
                typer.echo(f"systems_dir={systems_dir}")

        result = runner.invoke(app, ["--ctx-dir", ".custom", "-s", "lib/sys"])
        assert result.exit_code == EXIT_SUCCESS
        assert "ctx_dir=.custom" in result.output
        assert "systems_dir=lib/sys" in result.output

    def test_options_can_be_reused_in_multiple_commands(self) -> None:
        """Test that option factories can be used for multiple commands."""
        app = typer.Typer()

        @app.command()
        def cmd1(ctx_dir: str | None = ctx_dir_option()) -> None:
            typer.echo(f"cmd1: {ctx_dir}")

        @app.command()
        def cmd2(ctx_dir: str | None = ctx_dir_option()) -> None:
            typer.echo(f"cmd2: {ctx_dir}")

        result1 = runner.invoke(app, ["cmd1", "--ctx-dir", ".one"])
        result2 = runner.invoke(app, ["cmd2", "--ctx-dir", ".two"])

        assert result1.exit_code == EXIT_SUCCESS
        assert "cmd1: .one" in result1.output
        assert result2.exit_code == EXIT_SUCCESS
        assert "cmd2: .two" in result2.output


class TestIntegration:
    """Integration tests combining multiple utilities."""

    @pytest.fixture
    def _clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean up environment variables after test."""
        env_vars = ["CCTX_CTX_DIR", "CCTX_SYSTEMS_DIR", "CCTX_DB_NAME", "CCTX_GRAPH_NAME"]
        original_values: dict[str, str | None] = {}

        for var in env_vars:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

        yield

        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_full_workflow_with_project_root(self, tmp_path: Path, _clean_env: None) -> None:
        """Test full workflow: find project root, wire config, resolve paths."""
        # Set up project structure
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "knowledge.db").touch()

        systems_dir = tmp_path / "src" / "systems"
        systems_dir.mkdir(parents=True)

        # Create nested directory to start from
        work_dir = tmp_path / "src" / "systems" / "auth"
        work_dir.mkdir()

        # Find project root from nested directory
        project_root = find_project_root(start_dir=work_dir)
        assert project_root == tmp_path

        # Wire config
        config = wire_config(start_dir=project_root)
        assert config.ctx_dir == ".ctx"

        # Resolve paths using config
        resolved_ctx = config.get_ctx_path(project_root)
        assert resolved_ctx == ctx_dir

        resolved_db = config.get_db_path(project_root)
        assert resolved_db == ctx_dir / "knowledge.db"

    def test_cli_command_with_utilities(self, tmp_path: Path, _clean_env: None) -> None:
        """Test a CLI command using all utilities together."""
        # Set up project
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()

        app = typer.Typer()

        @app.command()
        def cmd(
            ctx_dir_opt: str | None = ctx_dir_option(),
        ) -> None:
            try:
                project_root = find_project_root(start_dir=tmp_path)
                config = wire_config(ctx_dir=ctx_dir_opt, start_dir=project_root)
                ctx_path = config.get_ctx_path(project_root)
                ensure_path_exists(ctx_path, "context directory", must_be_dir=True)
                success(f"Found context at: {ctx_path}")
            except ProjectRootNotFoundError as e:
                error(str(e))

        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_SUCCESS
        assert "Success:" in result.output
        assert ".ctx" in result.output

    def test_cli_command_with_override(self, tmp_path: Path, _clean_env: None) -> None:
        """Test CLI command with config override."""
        # Set up project with custom context dir
        custom_ctx = tmp_path / ".custom-ctx"
        custom_ctx.mkdir()

        app = typer.Typer()

        @app.command()
        def cmd(
            ctx_dir_opt: str | None = ctx_dir_option(),
        ) -> None:
            try:
                config = wire_config(ctx_dir=ctx_dir_opt, start_dir=tmp_path)
                ctx_path = config.get_ctx_path(tmp_path)
                ensure_path_exists(ctx_path, "context directory", must_be_dir=True)
                success(f"Using context: {config.ctx_dir}")
            except ProjectRootNotFoundError as e:
                error(str(e))

        result = runner.invoke(app, ["--ctx-dir", ".custom-ctx"])
        assert result.exit_code == EXIT_SUCCESS
        assert ".custom-ctx" in result.output
