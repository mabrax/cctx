"""Configuration management for lctx CLI tool.

Handles configuration loading from multiple sources with precedence:
CLI args > environment variables > .lctxrc > pyproject.toml > defaults
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

# tomllib is only available in Python 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class LctxConfig:
    """Configuration for the lctx CLI tool.

    Attributes:
        ctx_dir: Name of the context directory (default: ".ctx")
        systems_dir: Path to systems directory (default: "src/systems")
        db_name: Name of the SQLite database file (default: "knowledge.db")
        graph_name: Name of the dependency graph file (default: "graph.json")
    """

    ctx_dir: str = ".ctx"
    systems_dir: str = "src/systems"
    db_name: str = "knowledge.db"
    graph_name: str = "graph.json"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid.
        """
        # Validate ctx_dir
        if not self.ctx_dir or not isinstance(self.ctx_dir, str):
            raise ValueError("ctx_dir must be a non-empty string")

        # Validate systems_dir
        if not self.systems_dir or not isinstance(self.systems_dir, str):
            raise ValueError("systems_dir must be a non-empty string")

        # Validate db_name
        if not self.db_name or not isinstance(self.db_name, str):
            raise ValueError("db_name must be a non-empty string")
        if not self.db_name.endswith(".db"):
            raise ValueError("db_name must end with .db")

        # Validate graph_name
        if not self.graph_name or not isinstance(self.graph_name, str):
            raise ValueError("graph_name must be a non-empty string")
        if not self.graph_name.endswith(".json"):
            raise ValueError("graph_name must end with .json")

    def get_ctx_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the context directory.

        Args:
            base_path: Base path to resolve from. Defaults to current directory.

        Returns:
            Path to the context directory.
        """
        base = base_path or Path.cwd()
        return base / self.ctx_dir

    def get_db_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the knowledge database.

        Args:
            base_path: Base path to resolve from. Defaults to current directory.

        Returns:
            Path to the database file.
        """
        return self.get_ctx_path(base_path) / self.db_name

    def get_graph_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the dependency graph file.

        Args:
            base_path: Base path to resolve from. Defaults to current directory.

        Returns:
            Path to the graph file.
        """
        return self.get_ctx_path(base_path) / self.graph_name

    def get_systems_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the systems directory.

        Args:
            base_path: Base path to resolve from. Defaults to current directory.

        Returns:
            Path to the systems directory.
        """
        base = base_path or Path.cwd()
        return base / self.systems_dir


def _get_config_field_names() -> set[str]:
    """Get the set of valid configuration field names.

    Returns:
        Set of field names from LctxConfig.
    """
    return {f.name for f in fields(LctxConfig)}


def find_config_file(filename: str = ".lctxrc", start_dir: Path | None = None) -> Path | None:
    """Find a configuration file by traversing up the directory tree.

    Searches for the specified file starting from start_dir (or current directory)
    and traversing up to the filesystem root.

    Args:
        filename: Name of the config file to find.
        start_dir: Directory to start searching from. Defaults to current directory.

    Returns:
        Path to the config file if found, None otherwise.
    """
    current = start_dir or Path.cwd()
    current = current.resolve()

    while True:
        config_path = current / filename
        if config_path.is_file():
            return config_path

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent


def _load_toml_file(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents.

    Args:
        path: Path to the TOML file.

    Returns:
        Dictionary containing the parsed TOML content.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    with open(path, "rb") as f:
        result: dict[str, Any] = tomllib.load(f)
        return result


def _load_from_lctxrc(start_dir: Path | None = None) -> dict[str, Any]:
    """Load configuration from .lctxrc file.

    Args:
        start_dir: Directory to start searching from.

    Returns:
        Dictionary containing configuration from .lctxrc, or empty dict if not found.
    """
    config_path = find_config_file(".lctxrc", start_dir)
    if config_path is None:
        return {}

    try:
        data = _load_toml_file(config_path)
        # Filter to only valid config fields
        valid_fields = _get_config_field_names()
        return {k: v for k, v in data.items() if k in valid_fields}
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _load_from_pyproject(start_dir: Path | None = None) -> dict[str, Any]:
    """Load configuration from pyproject.toml [tool.lctx] section.

    Args:
        start_dir: Directory to start searching from.

    Returns:
        Dictionary containing configuration from pyproject.toml, or empty dict if not found.
    """
    config_path = find_config_file("pyproject.toml", start_dir)
    if config_path is None:
        return {}

    try:
        data = _load_toml_file(config_path)
        tool_section = data.get("tool", {})
        lctx_section = tool_section.get("lctx", {})

        # Filter to only valid config fields
        valid_fields = _get_config_field_names()
        return {k: v for k, v in lctx_section.items() if k in valid_fields}
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _load_from_env() -> dict[str, Any]:
    """Load configuration from environment variables.

    Environment variables are prefixed with LCTX_ and use uppercase names.
    For example: LCTX_CTX_DIR, LCTX_SYSTEMS_DIR, LCTX_DB_NAME, LCTX_GRAPH_NAME

    Returns:
        Dictionary containing configuration from environment variables.
    """
    env_mapping = {
        "LCTX_CTX_DIR": "ctx_dir",
        "LCTX_SYSTEMS_DIR": "systems_dir",
        "LCTX_DB_NAME": "db_name",
        "LCTX_GRAPH_NAME": "graph_name",
    }

    result: dict[str, Any] = {}
    for env_var, config_key in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            result[config_key] = value

    return result


def _merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple configuration dictionaries.

    Later dictionaries take precedence over earlier ones.

    Args:
        *configs: Configuration dictionaries to merge, in order of increasing precedence.

    Returns:
        Merged configuration dictionary.
    """
    result: dict[str, Any] = {}
    for config in configs:
        for key, value in config.items():
            if value is not None:
                result[key] = value
    return result


def load_config(
    cli_overrides: dict[str, Any] | None = None,
    start_dir: Path | None = None,
) -> LctxConfig:
    """Load configuration with full precedence chain.

    Loads configuration from multiple sources and merges them with the following
    precedence (highest to lowest):
    1. CLI arguments (cli_overrides)
    2. Environment variables (LCTX_*)
    3. .lctxrc file
    4. pyproject.toml [tool.lctx] section
    5. Default values

    Args:
        cli_overrides: Configuration overrides from CLI arguments.
        start_dir: Directory to start searching for config files.

    Returns:
        Fully resolved LctxConfig instance.

    Raises:
        ValueError: If the resulting configuration is invalid.
    """
    # Load from each source (in order of increasing precedence)
    pyproject_config = _load_from_pyproject(start_dir)
    lctxrc_config = _load_from_lctxrc(start_dir)
    env_config = _load_from_env()
    cli_config = cli_overrides or {}

    # Filter CLI overrides to only valid fields
    valid_fields = _get_config_field_names()
    cli_config = {k: v for k, v in cli_config.items() if k in valid_fields and v is not None}

    # Merge all configurations
    merged = _merge_configs(
        pyproject_config,
        lctxrc_config,
        env_config,
        cli_config,
    )

    # Create config instance (defaults are applied by the dataclass)
    return LctxConfig(**merged)


def validate_paths_exist(config: LctxConfig, base_path: Path | None = None) -> list[str]:
    """Validate that configured paths exist.

    This is an optional validation that checks if the configured directories
    and files actually exist on the filesystem.

    Args:
        config: Configuration to validate.
        base_path: Base path to resolve from. Defaults to current directory.

    Returns:
        List of error messages for paths that don't exist. Empty if all valid.
    """
    errors: list[str] = []
    base = base_path or Path.cwd()

    ctx_path = config.get_ctx_path(base)
    if not ctx_path.exists():
        errors.append(f"Context directory does not exist: {ctx_path}")

    systems_path = config.get_systems_path(base)
    if not systems_path.exists():
        errors.append(f"Systems directory does not exist: {systems_path}")

    db_path = config.get_db_path(base)
    if not db_path.exists():
        errors.append(f"Database file does not exist: {db_path}")

    graph_path = config.get_graph_path(base)
    if not graph_path.exists():
        errors.append(f"Graph file does not exist: {graph_path}")

    return errors
