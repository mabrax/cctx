"""CLI utility functions for lctx.

Provides helper functions for:
- Config wiring: Extracting Typer CLI options and passing to load_config
- Path resolution: Finding project root by looking for .ctx/ directory
- Error formatting: Consistent user-friendly error messages with exit codes
- Status checking: Validate .ctx/ and plugin installation status
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, NoReturn

import typer

from lctx.config import LctxConfig, load_config

# Type aliases for status checking
CtxStatus = Literal["missing", "partial", "complete"]
PluginStatus = Literal["missing", "partial", "complete"]

# Required files for status checking
CTX_REQUIRED_FILES = ["knowledge.db", "graph.json", "templates"]
PLUGIN_REQUIRED_FILES = [
    ".claude-plugin/plugin.json",
    "commands/context",
    "skills/living-context/SKILL.md",
    "hooks/pre-write-ctx-check.sh",
]

# Exit code conventions
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1  # User error (bad input, missing file, etc.)
EXIT_SYSTEM_ERROR = 2  # System error (permissions, I/O, etc.)


class ProjectRootNotFoundError(Exception):
    """Raised when project root cannot be found."""

    def __init__(self, start_dir: Path, marker: str = ".ctx") -> None:
        self.start_dir = start_dir
        self.marker = marker
        super().__init__(
            f"Could not find project root (no '{marker}/' directory found). "
            f"Searched from: {start_dir}"
        )


# -----------------------------------------------------------------------------
# Error Formatting Helpers (T3.8)
# -----------------------------------------------------------------------------


def error(msg: str, *, exit_code: int = EXIT_USER_ERROR) -> NoReturn:
    """Print an error message and exit with the given exit code.

    Args:
        msg: The error message to display.
        exit_code: Exit code to use (default: EXIT_USER_ERROR=1).

    Raises:
        typer.Exit: Always raises to exit the program.
    """
    styled_prefix = typer.style("Error:", fg=typer.colors.RED, bold=True)
    typer.echo(f"{styled_prefix} {msg}", err=True)
    raise typer.Exit(code=exit_code)


def warning(msg: str) -> None:
    """Print a warning message to stderr.

    Args:
        msg: The warning message to display.
    """
    styled_prefix = typer.style("Warning:", fg=typer.colors.YELLOW, bold=True)
    typer.echo(f"{styled_prefix} {msg}", err=True)


def success(msg: str) -> None:
    """Print a success message to stdout.

    Args:
        msg: The success message to display.
    """
    styled_prefix = typer.style("Success:", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"{styled_prefix} {msg}")


def info(msg: str) -> None:
    """Print an info message to stdout.

    Args:
        msg: The info message to display.
    """
    typer.echo(msg)


def format_error_details(errors: list[str]) -> str:
    """Format a list of error messages for display.

    Args:
        errors: List of error messages.

    Returns:
        Formatted string with bullet points.
    """
    if not errors:
        return ""
    return "\n".join(f"  - {e}" for e in errors)


# -----------------------------------------------------------------------------
# Path Resolution Helper (T3.7)
# -----------------------------------------------------------------------------


def find_project_root(
    start_dir: Path | None = None,
    marker: str = ".ctx",
) -> Path:
    """Find the project root by looking for the context directory marker.

    Traverses up the directory tree from start_dir looking for a directory
    containing the marker (default: .ctx/).

    Args:
        start_dir: Directory to start searching from. Defaults to cwd.
        marker: Name of the marker directory to look for (default: ".ctx").

    Returns:
        Path to the project root (directory containing the marker).

    Raises:
        ProjectRootNotFoundError: If no project root is found.
        PermissionError: If a directory cannot be accessed.
    """
    current = (start_dir or Path.cwd()).resolve()
    original_start = current

    while True:
        marker_path = current / marker

        # Check if marker exists
        try:
            if marker_path.is_dir():
                return current
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied when checking for project root at: {current}"
            ) from e

        # Move to parent
        parent = current.parent

        # Check if we've reached the filesystem root
        if parent == current:
            raise ProjectRootNotFoundError(original_start, marker)

        current = parent


def resolve_path(
    path: str | Path,
    base_path: Path | None = None,
) -> Path:
    """Resolve a path relative to a base path.

    Handles:
    - Absolute paths (returned as-is after resolving)
    - Relative paths (resolved relative to base_path or cwd)
    - Symlinks (resolved to their target)

    Args:
        path: The path to resolve.
        base_path: Base path to resolve relative paths from. Defaults to cwd.

    Returns:
        Resolved absolute Path.

    Raises:
        FileNotFoundError: If the path doesn't exist (after resolution).
    """
    p = Path(path)
    base = base_path or Path.cwd()

    resolved = p.resolve() if p.is_absolute() else (base / p).resolve()

    return resolved


def ensure_path_exists(
    path: Path,
    path_type: str = "path",
    must_be_dir: bool = False,
    must_be_file: bool = False,
) -> Path:
    """Ensure a path exists and optionally check its type.

    Args:
        path: The path to check.
        path_type: Human-readable name for the path (for error messages).
        must_be_dir: If True, path must be a directory.
        must_be_file: If True, path must be a file.

    Returns:
        The verified path.

    Raises:
        typer.Exit: If the path doesn't exist or is the wrong type.
    """
    if not path.exists():
        error(f"{path_type} does not exist: {path}")

    if must_be_dir and not path.is_dir():
        error(f"{path_type} is not a directory: {path}")

    if must_be_file and not path.is_file():
        error(f"{path_type} is not a file: {path}")

    return path


# -----------------------------------------------------------------------------
# Config Wiring Helper (T3.6)
# -----------------------------------------------------------------------------


def wire_config(
    ctx_dir: str | None = None,
    db_name: str | None = None,
    systems_dir: str | None = None,
    graph_name: str | None = None,
    start_dir: Path | None = None,
) -> LctxConfig:
    """Wire CLI options to load_config with appropriate overrides.

    This helper extracts common CLI options and passes them to load_config
    as the cli_overrides parameter.

    Args:
        ctx_dir: Override for context directory name.
        db_name: Override for database file name.
        systems_dir: Override for systems directory path.
        graph_name: Override for graph file name.
        start_dir: Directory to start searching for config files.

    Returns:
        Fully resolved LctxConfig instance.

    Raises:
        typer.Exit: If configuration is invalid.
    """
    cli_overrides: dict[str, Any] = {}

    if ctx_dir is not None:
        cli_overrides["ctx_dir"] = ctx_dir
    if db_name is not None:
        cli_overrides["db_name"] = db_name
    if systems_dir is not None:
        cli_overrides["systems_dir"] = systems_dir
    if graph_name is not None:
        cli_overrides["graph_name"] = graph_name

    try:
        return load_config(cli_overrides=cli_overrides, start_dir=start_dir)
    except ValueError as e:
        error(f"Invalid configuration: {e}", exit_code=EXIT_USER_ERROR)


def get_config_from_context(ctx: typer.Context) -> LctxConfig:
    """Get LctxConfig from Typer context if available.

    This helper retrieves the config object that was stored in the
    Typer context by a callback function.

    Args:
        ctx: The Typer context object.

    Returns:
        The LctxConfig instance from context.

    Raises:
        typer.Exit: If no config is found in context.
    """
    config = ctx.obj
    if not isinstance(config, LctxConfig):
        error(
            "Configuration not initialized. This is a bug in the CLI.",
            exit_code=EXIT_SYSTEM_ERROR,
        )
    # At this point, mypy knows config is LctxConfig because error() is NoReturn
    return config


# -----------------------------------------------------------------------------
# Typer Option Factory Functions
# -----------------------------------------------------------------------------
# These factory functions create fresh Typer Option instances for each command.
# This is necessary because Typer consumes Option objects when decorating commands,
# so the same Option instance cannot be reused across multiple commands.


def ctx_dir_option() -> Any:
    """Create a Typer Option for --ctx-dir / -c.

    Returns:
        Typer Option with default None and appropriate help text.
    """
    return typer.Option(
        None,
        "--ctx-dir",
        "-c",
        help="Override context directory name (default: .ctx).",
        envvar="LCTX_CTX_DIR",
    )


def db_name_option() -> Any:
    """Create a Typer Option for --db-name.

    Returns:
        Typer Option with default None and appropriate help text.
    """
    return typer.Option(
        None,
        "--db-name",
        help="Override database file name (default: knowledge.db).",
        envvar="LCTX_DB_NAME",
    )


def systems_dir_option() -> Any:
    """Create a Typer Option for --systems-dir / -s.

    Returns:
        Typer Option with default None and appropriate help text.
    """
    return typer.Option(
        None,
        "--systems-dir",
        "-s",
        help="Override systems directory path (default: src/systems).",
        envvar="LCTX_SYSTEMS_DIR",
    )


def graph_name_option() -> Any:
    """Create a Typer Option for --graph-name.

    Returns:
        Typer Option with default None and appropriate help text.
    """
    return typer.Option(
        None,
        "--graph-name",
        help="Override graph file name (default: graph.json).",
        envvar="LCTX_GRAPH_NAME",
    )


# -----------------------------------------------------------------------------
# Status Checking Functions
# -----------------------------------------------------------------------------


def check_ctx_status(path: Path) -> tuple[CtxStatus, list[str]]:
    """Check .ctx/ directory status.

    Validates whether the .ctx/ directory exists and contains all required files.
    Empty directories are treated as "missing" (safe to create into).

    Args:
        path: Project root path to check for .ctx/ directory.

    Returns:
        Tuple of (status, missing_files) where status is:
        - "missing": .ctx/ doesn't exist or is empty
        - "partial": .ctx/ exists but missing required files
        - "complete": .ctx/ has all required files
    """
    ctx_path = path / ".ctx"

    # Check if directory exists
    if not ctx_path.exists():
        return "missing", CTX_REQUIRED_FILES.copy()

    # Check if directory is empty
    if not any(ctx_path.iterdir()):
        return "missing", CTX_REQUIRED_FILES.copy()

    # Check for required files
    missing: list[str] = []
    for required in CTX_REQUIRED_FILES:
        required_path = ctx_path / required
        if not required_path.exists():
            missing.append(required)

    if missing:
        return "partial", missing

    return "complete", []


def check_plugin_status(path: Path) -> tuple[PluginStatus, list[str]]:
    """Check plugin installation status.

    Validates whether the Claude Code plugin is installed at the expected
    location and contains all required files.

    Args:
        path: Project root path to check for plugin installation.

    Returns:
        Tuple of (status, missing_files) where status is:
        - "missing": plugin not installed
        - "partial": plugin installed but missing files
        - "complete": plugin fully installed
    """
    plugin_path = path / ".claude" / "plugins" / "living-context"

    # Check if plugin directory exists
    if not plugin_path.exists():
        return "missing", PLUGIN_REQUIRED_FILES.copy()

    # Check if directory is empty
    if not any(plugin_path.iterdir()):
        return "missing", PLUGIN_REQUIRED_FILES.copy()

    # Check for required files
    missing: list[str] = []
    for required in PLUGIN_REQUIRED_FILES:
        required_path = plugin_path / required
        if not required_path.exists():
            missing.append(required)

    if missing:
        return "partial", missing

    return "complete", []
