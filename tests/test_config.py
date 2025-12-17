"""Tests for lctx configuration management."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from lctx.config import (
    LctxConfig,
    find_config_file,
    load_config,
    validate_paths_exist,
)


class TestLctxConfig:
    """Tests for the LctxConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = LctxConfig()
        assert config.ctx_dir == ".ctx"
        assert config.systems_dir == "src/systems"
        assert config.db_name == "knowledge.db"
        assert config.graph_name == "graph.json"

    def test_custom_values(self) -> None:
        """Test that custom values can be set."""
        config = LctxConfig(
            ctx_dir=".context",
            systems_dir="lib/modules",
            db_name="context.db",
            graph_name="deps.json",
        )
        assert config.ctx_dir == ".context"
        assert config.systems_dir == "lib/modules"
        assert config.db_name == "context.db"
        assert config.graph_name == "deps.json"

    def test_validation_empty_ctx_dir(self) -> None:
        """Test that empty ctx_dir raises ValueError."""
        with pytest.raises(ValueError, match="ctx_dir must be a non-empty string"):
            LctxConfig(ctx_dir="")

    def test_validation_empty_systems_dir(self) -> None:
        """Test that empty systems_dir raises ValueError."""
        with pytest.raises(ValueError, match="systems_dir must be a non-empty string"):
            LctxConfig(systems_dir="")

    def test_validation_empty_db_name(self) -> None:
        """Test that empty db_name raises ValueError."""
        with pytest.raises(ValueError, match="db_name must be a non-empty string"):
            LctxConfig(db_name="")

    def test_validation_db_name_extension(self) -> None:
        """Test that db_name must end with .db."""
        with pytest.raises(ValueError, match="db_name must end with .db"):
            LctxConfig(db_name="knowledge.sqlite")

    def test_validation_empty_graph_name(self) -> None:
        """Test that empty graph_name raises ValueError."""
        with pytest.raises(ValueError, match="graph_name must be a non-empty string"):
            LctxConfig(graph_name="")

    def test_validation_graph_name_extension(self) -> None:
        """Test that graph_name must end with .json."""
        with pytest.raises(ValueError, match="graph_name must end with .json"):
            LctxConfig(graph_name="graph.yaml")

    def test_get_ctx_path(self, tmp_path: Path) -> None:
        """Test get_ctx_path returns correct path."""
        config = LctxConfig(ctx_dir=".ctx")
        assert config.get_ctx_path(tmp_path) == tmp_path / ".ctx"

    def test_get_ctx_path_default(self) -> None:
        """Test get_ctx_path uses cwd when no base_path provided."""
        config = LctxConfig(ctx_dir=".ctx")
        expected = Path.cwd() / ".ctx"
        assert config.get_ctx_path() == expected

    def test_get_db_path(self, tmp_path: Path) -> None:
        """Test get_db_path returns correct path."""
        config = LctxConfig(ctx_dir=".ctx", db_name="knowledge.db")
        assert config.get_db_path(tmp_path) == tmp_path / ".ctx" / "knowledge.db"

    def test_get_graph_path(self, tmp_path: Path) -> None:
        """Test get_graph_path returns correct path."""
        config = LctxConfig(ctx_dir=".ctx", graph_name="graph.json")
        assert config.get_graph_path(tmp_path) == tmp_path / ".ctx" / "graph.json"

    def test_get_systems_path(self, tmp_path: Path) -> None:
        """Test get_systems_path returns correct path."""
        config = LctxConfig(systems_dir="src/systems")
        assert config.get_systems_path(tmp_path) == tmp_path / "src" / "systems"


class TestFindConfigFile:
    """Tests for find_config_file function."""

    def test_find_in_current_dir(self, tmp_path: Path) -> None:
        """Test finding config file in current directory."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text("[config]\n")

        result = find_config_file(".lctxrc", tmp_path)
        assert result == config_file

    def test_find_in_parent_dir(self, tmp_path: Path) -> None:
        """Test finding config file in parent directory."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text("[config]\n")

        child_dir = tmp_path / "subdir"
        child_dir.mkdir()

        result = find_config_file(".lctxrc", child_dir)
        assert result == config_file

    def test_find_in_grandparent_dir(self, tmp_path: Path) -> None:
        """Test finding config file in grandparent directory."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text("[config]\n")

        nested_dir = tmp_path / "a" / "b" / "c"
        nested_dir.mkdir(parents=True)

        result = find_config_file(".lctxrc", nested_dir)
        assert result == config_file

    def test_not_found(self, tmp_path: Path) -> None:
        """Test returning None when config file not found."""
        result = find_config_file(".lctxrc", tmp_path)
        assert result is None

    def test_find_pyproject_toml(self, tmp_path: Path) -> None:
        """Test finding pyproject.toml file."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text("[tool.lctx]\n")

        result = find_config_file("pyproject.toml", tmp_path)
        assert result == config_file

    def test_prefers_closest_file(self, tmp_path: Path) -> None:
        """Test that closest file is preferred over parent."""
        parent_config = tmp_path / ".lctxrc"
        parent_config.write_text('ctx_dir = ".parent-ctx"\n')

        child_dir = tmp_path / "subdir"
        child_dir.mkdir()
        child_config = child_dir / ".lctxrc"
        child_config.write_text('ctx_dir = ".child-ctx"\n')

        result = find_config_file(".lctxrc", child_dir)
        assert result == child_config


class TestLoadFromLctxrc:
    """Tests for loading configuration from .lctxrc file."""

    def test_load_valid_lctxrc(self, tmp_path: Path) -> None:
        """Test loading valid .lctxrc file."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text(
            'ctx_dir = ".context"\n'
            'systems_dir = "lib/systems"\n'
            'db_name = "data.db"\n'
            'graph_name = "deps.json"\n'
        )

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".context"
        assert config.systems_dir == "lib/systems"
        assert config.db_name == "data.db"
        assert config.graph_name == "deps.json"

    def test_load_partial_lctxrc(self, tmp_path: Path) -> None:
        """Test loading .lctxrc with only some values."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text('ctx_dir = ".myctx"\n')

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".myctx"
        # Defaults should be used for other values
        assert config.systems_dir == "src/systems"
        assert config.db_name == "knowledge.db"
        assert config.graph_name == "graph.json"

    def test_ignore_unknown_fields(self, tmp_path: Path) -> None:
        """Test that unknown fields in .lctxrc are ignored."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text(
            'ctx_dir = ".context"\n'
            'unknown_field = "value"\n'
            'another_unknown = 42\n'
        )

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".context"
        # Should not raise and should use defaults for missing fields


class TestLoadFromPyproject:
    """Tests for loading configuration from pyproject.toml."""

    def test_load_from_tool_lctx_section(self, tmp_path: Path) -> None:
        """Test loading from [tool.lctx] section in pyproject.toml."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            "[project]\n"
            'name = "myproject"\n'
            "\n"
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
            'systems_dir = "pyproject/systems"\n'
        )

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".pyproject-ctx"
        assert config.systems_dir == "pyproject/systems"

    def test_empty_tool_lctx_section(self, tmp_path: Path) -> None:
        """Test handling empty [tool.lctx] section."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            "[project]\n"
            'name = "myproject"\n'
            "\n"
            "[tool.lctx]\n"
        )

        config = load_config(start_dir=tmp_path)
        # Should use defaults
        assert config.ctx_dir == ".ctx"

    def test_no_tool_lctx_section(self, tmp_path: Path) -> None:
        """Test handling pyproject.toml without [tool.lctx] section."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            "[project]\n"
            'name = "myproject"\n'
        )

        config = load_config(start_dir=tmp_path)
        # Should use defaults
        assert config.ctx_dir == ".ctx"


class TestLoadFromEnv:
    """Tests for loading configuration from environment variables."""

    @pytest.fixture
    def _clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean up environment variables after test."""
        env_vars = ["LCTX_CTX_DIR", "LCTX_SYSTEMS_DIR", "LCTX_DB_NAME", "LCTX_GRAPH_NAME"]
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

    def test_load_ctx_dir_from_env(self, tmp_path: Path, _clean_env: None) -> None:
        """Test loading ctx_dir from LCTX_CTX_DIR environment variable."""
        os.environ["LCTX_CTX_DIR"] = ".env-ctx"

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".env-ctx"

    def test_load_systems_dir_from_env(self, tmp_path: Path, _clean_env: None) -> None:
        """Test loading systems_dir from LCTX_SYSTEMS_DIR environment variable."""
        os.environ["LCTX_SYSTEMS_DIR"] = "env/systems"

        config = load_config(start_dir=tmp_path)
        assert config.systems_dir == "env/systems"

    def test_load_db_name_from_env(self, tmp_path: Path, _clean_env: None) -> None:
        """Test loading db_name from LCTX_DB_NAME environment variable."""
        os.environ["LCTX_DB_NAME"] = "env.db"

        config = load_config(start_dir=tmp_path)
        assert config.db_name == "env.db"

    def test_load_graph_name_from_env(self, tmp_path: Path, _clean_env: None) -> None:
        """Test loading graph_name from LCTX_GRAPH_NAME environment variable."""
        os.environ["LCTX_GRAPH_NAME"] = "env-graph.json"

        config = load_config(start_dir=tmp_path)
        assert config.graph_name == "env-graph.json"

    def test_load_all_from_env(self, tmp_path: Path, _clean_env: None) -> None:
        """Test loading all config values from environment variables."""
        os.environ["LCTX_CTX_DIR"] = ".env-ctx"
        os.environ["LCTX_SYSTEMS_DIR"] = "env/systems"
        os.environ["LCTX_DB_NAME"] = "env.db"
        os.environ["LCTX_GRAPH_NAME"] = "env-graph.json"

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".env-ctx"
        assert config.systems_dir == "env/systems"
        assert config.db_name == "env.db"
        assert config.graph_name == "env-graph.json"


class TestConfigPrecedence:
    """Tests for configuration precedence."""

    @pytest.fixture
    def _clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean up environment variables after test."""
        env_vars = ["LCTX_CTX_DIR", "LCTX_SYSTEMS_DIR", "LCTX_DB_NAME", "LCTX_GRAPH_NAME"]
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

    def test_cli_overrides_all(self, tmp_path: Path, _clean_env: None) -> None:
        """Test that CLI arguments override all other sources."""
        # Set up pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
        )

        # Set up .lctxrc
        lctxrc = tmp_path / ".lctxrc"
        lctxrc.write_text('ctx_dir = ".lctxrc-ctx"\n')

        # Set up environment
        os.environ["LCTX_CTX_DIR"] = ".env-ctx"

        # CLI override should win
        config = load_config(cli_overrides={"ctx_dir": ".cli-ctx"}, start_dir=tmp_path)
        assert config.ctx_dir == ".cli-ctx"

    def test_env_overrides_files(self, tmp_path: Path, _clean_env: None) -> None:
        """Test that environment variables override file configs."""
        # Set up pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
        )

        # Set up .lctxrc
        lctxrc = tmp_path / ".lctxrc"
        lctxrc.write_text('ctx_dir = ".lctxrc-ctx"\n')

        # Environment should override files
        os.environ["LCTX_CTX_DIR"] = ".env-ctx"

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".env-ctx"

    def test_lctxrc_overrides_pyproject(self, tmp_path: Path, _clean_env: None) -> None:
        """Test that .lctxrc overrides pyproject.toml."""
        # Set up pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
        )

        # Set up .lctxrc
        lctxrc = tmp_path / ".lctxrc"
        lctxrc.write_text('ctx_dir = ".lctxrc-ctx"\n')

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".lctxrc-ctx"

    def test_pyproject_overrides_defaults(self, tmp_path: Path, _clean_env: None) -> None:
        """Test that pyproject.toml overrides defaults."""
        # Set up pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
        )

        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".pyproject-ctx"

    def test_defaults_used_when_nothing_set(self, tmp_path: Path, _clean_env: None) -> None:
        """Test that defaults are used when no config is set."""
        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".ctx"
        assert config.systems_dir == "src/systems"
        assert config.db_name == "knowledge.db"
        assert config.graph_name == "graph.json"

    def test_partial_override_chain(self, tmp_path: Path, _clean_env: None) -> None:
        """Test partial overrides from different sources."""
        # pyproject.toml sets ctx_dir
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.lctx]\n"
            'ctx_dir = ".pyproject-ctx"\n'
        )

        # .lctxrc sets systems_dir
        lctxrc = tmp_path / ".lctxrc"
        lctxrc.write_text('systems_dir = "lctxrc/systems"\n')

        # Environment sets db_name
        os.environ["LCTX_DB_NAME"] = "env.db"

        # CLI sets graph_name
        config = load_config(cli_overrides={"graph_name": "cli.json"}, start_dir=tmp_path)

        # Each should come from its respective source
        assert config.ctx_dir == ".pyproject-ctx"
        assert config.systems_dir == "lctxrc/systems"
        assert config.db_name == "env.db"
        assert config.graph_name == "cli.json"


class TestValidatePathsExist:
    """Tests for validate_paths_exist function."""

    def test_all_paths_exist(self, tmp_path: Path) -> None:
        """Test validation passes when all paths exist."""
        # Create all required directories and files
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "knowledge.db").touch()
        (ctx_dir / "graph.json").touch()

        systems_dir = tmp_path / "src" / "systems"
        systems_dir.mkdir(parents=True)

        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert errors == []

    def test_missing_ctx_dir(self, tmp_path: Path) -> None:
        """Test validation reports missing context directory."""
        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert any("Context directory does not exist" in e for e in errors)

    def test_missing_systems_dir(self, tmp_path: Path) -> None:
        """Test validation reports missing systems directory."""
        # Create ctx_dir but not systems_dir
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "knowledge.db").touch()
        (ctx_dir / "graph.json").touch()

        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert any("Systems directory does not exist" in e for e in errors)

    def test_missing_db_file(self, tmp_path: Path) -> None:
        """Test validation reports missing database file."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "graph.json").touch()

        systems_dir = tmp_path / "src" / "systems"
        systems_dir.mkdir(parents=True)

        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert any("Database file does not exist" in e for e in errors)

    def test_missing_graph_file(self, tmp_path: Path) -> None:
        """Test validation reports missing graph file."""
        ctx_dir = tmp_path / ".ctx"
        ctx_dir.mkdir()
        (ctx_dir / "knowledge.db").touch()

        systems_dir = tmp_path / "src" / "systems"
        systems_dir.mkdir(parents=True)

        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert any("Graph file does not exist" in e for e in errors)

    def test_reports_all_missing(self, tmp_path: Path) -> None:
        """Test validation reports all missing paths."""
        config = LctxConfig()
        errors = validate_paths_exist(config, tmp_path)
        assert len(errors) == 4


class TestCliOverrides:
    """Tests for CLI override handling."""

    def test_none_values_ignored(self, tmp_path: Path) -> None:
        """Test that None values in CLI overrides are ignored."""
        config = load_config(
            cli_overrides={
                "ctx_dir": ".cli-ctx",
                "systems_dir": None,
                "db_name": None,
                "graph_name": None,
            },
            start_dir=tmp_path,
        )
        assert config.ctx_dir == ".cli-ctx"
        assert config.systems_dir == "src/systems"  # Default
        assert config.db_name == "knowledge.db"  # Default
        assert config.graph_name == "graph.json"  # Default

    def test_unknown_cli_fields_ignored(self, tmp_path: Path) -> None:
        """Test that unknown fields in CLI overrides are ignored."""
        config = load_config(
            cli_overrides={
                "ctx_dir": ".cli-ctx",
                "unknown_field": "value",
            },
            start_dir=tmp_path,
        )
        assert config.ctx_dir == ".cli-ctx"
        # Should not raise


class TestInvalidTomlFiles:
    """Tests for handling invalid TOML files."""

    def test_invalid_lctxrc_toml(self, tmp_path: Path) -> None:
        """Test handling invalid TOML in .lctxrc."""
        config_file = tmp_path / ".lctxrc"
        config_file.write_text("this is not valid toml [[[")

        # Should not raise, just use defaults
        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".ctx"

    def test_invalid_pyproject_toml(self, tmp_path: Path) -> None:
        """Test handling invalid TOML in pyproject.toml."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text("this is not valid toml [[[")

        # Should not raise, just use defaults
        config = load_config(start_dir=tmp_path)
        assert config.ctx_dir == ".ctx"
