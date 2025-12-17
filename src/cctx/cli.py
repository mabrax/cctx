"""Living Context CLI Tool - Main entry point."""

from __future__ import annotations

import importlib.resources
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.table import Table

from cctx import __version__
from cctx.cli_utils import (
    EXIT_USER_ERROR,
    ProjectRootNotFoundError,
    check_ctx_status,
    check_plugin_status,
    ctx_dir_option,
    find_project_root,
    wire_config,
)
from cctx.fixers.base import FixResult
from cctx.fixers.registry import get_global_registry
from cctx.scaffolder import ScaffoldError, scaffold_project_ctx, scaffold_system_ctx
from cctx.schema import init_database
from cctx.validators.base import FixableIssue

if TYPE_CHECKING:
    from cctx.database import ContextDB

app = typer.Typer(
    name="cctx",
    help="Living Context CLI Tool - Co-located documentation that stays synchronized with code.",
    add_completion=False,
)

# Rich consoles for output
console = Console()
err_console = Console(stderr=True)


# -----------------------------------------------------------------------------
# Output Helpers
# -----------------------------------------------------------------------------


def _output_success(message: str, quiet: bool = False) -> None:
    """Print a success message."""
    if not quiet:
        console.print(f"[green]Success:[/green] {message}")


def _output_error(message: str) -> None:
    """Print an error message."""
    err_console.print(f"[red]Error:[/red] {message}")


def _output_warning(message: str, quiet: bool = False) -> None:
    """Print a warning message."""
    if not quiet:
        err_console.print(f"[yellow]Warning:[/yellow] {message}")


def _output_info(message: str, quiet: bool = False) -> None:
    """Print an info message."""
    if not quiet:
        console.print(message)


def _exit_error(message: str, exit_code: int = EXIT_USER_ERROR) -> None:
    """Print error and exit."""
    _output_error(message)
    raise typer.Exit(code=exit_code)


# -----------------------------------------------------------------------------
# Version and Main Callbacks
# -----------------------------------------------------------------------------


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"cctx version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Living Context CLI Tool - Co-located documentation that stays synchronized with code."""
    pass


# -----------------------------------------------------------------------------
# Init Command
# -----------------------------------------------------------------------------


@app.command()
def init(
    path: str | None = typer.Argument(
        None,
        help="Path to initialize in. Defaults to current directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reinitialization, overwriting existing files.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Initialize Living Context and install Claude Code plugin.

    Creates the Living Context directory structure (.ctx/) and installs
    the Claude Code plugin (.claude/plugins/living-context/).

    The .ctx/ directory includes:
    - knowledge.db (SQLite database for ADRs, systems, dependencies)
    - graph.json (dependency graph)
    - templates/ (documentation templates)

    The plugin provides:
    - Slash commands for context management
    - A Living Context skill for Claude Code
    - Pre-write hooks for context validation

    Use --force to reinitialize existing installations.
    """
    target_path = Path(path).resolve() if path else Path.cwd()
    config = wire_config(ctx_dir=ctx_dir, start_dir=target_path)

    result: dict[str, Any] = {
        "success": False,
        "path": str(target_path),
        "ctx": {"status": None, "action": None},
        "plugin": {"status": None, "action": None},
        "warnings": [],
    }

    # 1. Handle .ctx/
    ctx_status, ctx_missing = check_ctx_status(target_path)
    should_create_ctx = ctx_status == "missing" or force

    if should_create_ctx:
        if ctx_status != "missing":
            result["warnings"].append("Overwriting existing .ctx/")
            if not json_output:
                _output_warning("Overwriting existing .ctx/", quiet)
            # Remove existing .ctx/ to allow clean reinit
            ctx_path = config.get_ctx_path(target_path)
            if ctx_path.exists():
                shutil.rmtree(ctx_path)

        try:
            ctx_path = scaffold_project_ctx(target_path, config)
            db_path = config.get_db_path(target_path)
            init_database(db_path)
            result["ctx"]["status"] = "created"
            result["ctx"]["action"] = "created"
            result["ctx"]["path"] = str(ctx_path)
            if not json_output:
                _output_success(f"Created .ctx/ at: {ctx_path}", quiet)
        except ScaffoldError as e:
            result["ctx"]["status"] = "error"
            result["ctx"]["error"] = str(e)
            if json_output:
                console.print_json(json.dumps(result))
            _exit_error(f"Failed to create .ctx/: {e}")

    elif ctx_status == "partial":
        result["ctx"]["status"] = "partial"
        result["ctx"]["action"] = "skipped"
        result["ctx"]["missing"] = ctx_missing
        msg = f".ctx/ exists but is incomplete (missing: {', '.join(ctx_missing)}). Run: cctx doctor --fix"
        result["warnings"].append(msg)
        if not json_output:
            _output_warning(msg, quiet)

    else:  # complete
        result["ctx"]["status"] = "exists"
        result["ctx"]["action"] = "skipped"
        if not json_output:
            _output_info("[green]✓[/green] .ctx/ already initialized", quiet)

    # 2. Handle plugin
    plugin_status, plugin_missing = check_plugin_status(target_path)
    plugin_dest = target_path / ".claude" / "plugins" / "living-context"
    should_install_plugin = plugin_status == "missing" or force

    if should_install_plugin:
        if plugin_status != "missing":
            result["warnings"].append("Overwriting existing plugin files")
            if not json_output:
                _output_warning("Overwriting existing plugin files", quiet)

        # Find plugin source files
        plugin_src = _get_plugin_source_path()
        if plugin_src is None:
            result["plugin"]["status"] = "error"
            result["plugin"]["error"] = "Plugin files not found. Ensure cctx is properly installed."
            if json_output:
                console.print_json(json.dumps(result))
            _exit_error("Plugin files not found. Ensure cctx is properly installed.")
            return  # unreachable, but helps mypy

        try:
            plugin_dest.mkdir(parents=True, exist_ok=True)
            copied_files = _copy_plugin_files(plugin_src, plugin_dest)
            result["plugin"]["status"] = "installed"
            result["plugin"]["action"] = "installed"
            result["plugin"]["path"] = str(plugin_dest)
            result["plugin"]["files_copied"] = len(copied_files)
            if not json_output:
                _output_success(f"Installed plugin at: {plugin_dest}", quiet)
        except (PermissionError, OSError) as e:
            result["plugin"]["status"] = "error"
            result["plugin"]["error"] = str(e)
            if json_output:
                console.print_json(json.dumps(result))
            _exit_error(f"Failed to install plugin: {e}")

    elif plugin_status == "partial":
        result["plugin"]["status"] = "partial"
        result["plugin"]["action"] = "skipped"
        result["plugin"]["missing"] = plugin_missing
        msg = f"Plugin exists but is incomplete (missing: {', '.join(plugin_missing)}). Run: cctx doctor --fix"
        result["warnings"].append(msg)
        if not json_output:
            _output_warning(msg, quiet)

    else:  # complete
        result["plugin"]["status"] = "exists"
        result["plugin"]["action"] = "skipped"
        if not json_output:
            _output_info("[green]✓[/green] Plugin already installed", quiet)

    # 3. Final result
    result["success"] = True

    if json_output:
        console.print_json(json.dumps(result))


# -----------------------------------------------------------------------------
# Health Command
# -----------------------------------------------------------------------------


@app.command()
def health(
    deep: bool = typer.Option(
        False,
        "--deep",
        "-d",
        help="Include constraint checking in health validation.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Run health checks on Living Context documentation.

    Validates that all context files are present, properly formatted,
    and synchronized with the codebase.

    Runs the following validators:
    - Snapshot validator: Checks file existence and dependencies
    - ADR validator: Validates ADR consistency and indexing
    - Debt auditor: Audits technical debt tracking
    - Freshness checker: Detects stale documentation
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        ctx_path = config.get_ctx_path(project_root)
        db_path = config.get_db_path(project_root)

        result: dict[str, Any] = {
            "healthy": True,
            "ctx_path": str(ctx_path),
            "deep": deep,
            "checks": [],
            "warnings": [],
            "errors": [],
            "validators": [],
        }

        # Basic existence checks
        if ctx_path.exists():
            result["checks"].append({"name": "ctx_exists", "passed": True})
        else:
            result["healthy"] = False
            result["checks"].append({"name": "ctx_exists", "passed": False})
            result["errors"].append(f"Context directory not found: {ctx_path}")

        if db_path.exists():
            result["checks"].append({"name": "db_exists", "passed": True})
        else:
            result["healthy"] = False
            result["checks"].append({"name": "db_exists", "passed": False})
            result["errors"].append(f"Database not found: {db_path}")

        graph_path = config.get_graph_path(project_root)
        if graph_path.exists():
            result["checks"].append({"name": "graph_exists", "passed": True})
        else:
            result["warnings"].append(f"Graph file not found: {graph_path}")
            result["checks"].append({"name": "graph_exists", "passed": True, "warning": True})

        # Run validators if basic checks pass
        if ctx_path.exists() and db_path.exists():
            from cctx.validators import ValidationRunner

            runner = ValidationRunner(project_root, db_path)
            validation_result = runner.run_all(deep=deep)

            # Add validator results
            for vr in validation_result.results:
                validator_info = {
                    "name": vr.name,
                    "status": vr.status,
                    "systems_checked": vr.systems_checked,
                    "issues_count": len(vr.issues),
                }
                result["validators"].append(validator_info)
                result["checks"].append({
                    "name": vr.name,
                    "passed": vr.status == "pass",
                })

            # Collect issues
            for issue in validation_result.all_issues:
                issue_dict: dict[str, str | int] = {
                    "system": issue.system,
                    "check": issue.check,
                    "severity": issue.severity,
                    "message": issue.message,
                }
                if issue.file:
                    issue_dict["file"] = issue.file
                if issue.line:
                    issue_dict["line"] = issue.line

                if issue.severity == "error":
                    result["errors"].append(issue.message)
                elif issue.severity == "warning":
                    result["warnings"].append(issue.message)

            # Update healthy status
            if validation_result.status == "fail":
                result["healthy"] = False

            result["summary"] = {
                "validators_run": validation_result.validators_run,
                "total_issues": validation_result.total_issues,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "infos": validation_result.infos,
            }

        if json_output:
            console.print_json(json.dumps(result))
        else:
            if result["healthy"]:
                _output_success(f"Context is healthy: {ctx_path}", quiet)
            else:
                _output_error(f"Context has issues: {ctx_path}")

            if not quiet:
                for check in result["checks"]:
                    status = "[green]PASS[/green]" if check["passed"] else "[red]FAIL[/red]"
                    if check.get("warning"):
                        status = "[yellow]WARN[/yellow]"
                    console.print(f"  {status} {check['name']}")

                if "summary" in result:
                    console.print("")
                    console.print(f"  Validators: {result['summary']['validators_run']}")
                    console.print(f"  Issues: {result['summary']['total_issues']} ({result['summary']['errors']} errors, {result['summary']['warnings']} warnings)")

                for warning in result["warnings"][:10]:  # Limit displayed warnings
                    _output_warning(warning)

                for error in result["errors"][:10]:  # Limit displayed errors
                    _output_error(error)

        if not result["healthy"]:
            raise typer.Exit(code=EXIT_USER_ERROR)

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"healthy": False, "error": str(e)}))
        _exit_error(str(e))


# -----------------------------------------------------------------------------
# Status Command
# -----------------------------------------------------------------------------


@app.command()
def status(
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Show Living Context status summary.

    Displays an overview of:
    - Number of documented systems
    - ADR count and status breakdown
    - Technical debt items
    - Last sync timestamp
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        ctx_path = config.get_ctx_path(project_root)
        db_path = config.get_db_path(project_root)

        result: dict[str, Any] = {
            "ctx_path": str(ctx_path),
            "systems": {"count": 0},
            "adrs": {"count": 0, "by_status": {}},
            "dependencies": {"count": 0},
        }

        if db_path.exists():
            from cctx.adr_crud import list_adrs
            from cctx.crud import list_systems
            from cctx.database import ContextDB

            with ContextDB(db_path, auto_init=False) as db:
                # Count systems
                systems = list_systems(db)
                result["systems"]["count"] = len(systems)

                # Count ADRs by status
                adrs = list_adrs(db)
                result["adrs"]["count"] = len(adrs)
                status_counts: dict[str, int] = {}
                for adr in adrs:
                    s = adr.get("status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1
                result["adrs"]["by_status"] = status_counts

                # Count dependencies
                dep_count = db.fetchone("SELECT COUNT(*) as cnt FROM system_dependencies")
                result["dependencies"]["count"] = dep_count["cnt"] if dep_count else 0

        if json_output:
            console.print_json(json.dumps(result))
        else:
            _output_info("[bold]Living Context Status[/bold]", quiet)
            _output_info(f"  Context: {ctx_path}", quiet)
            _output_info("", quiet)
            _output_info(f"  Systems: {result['systems']['count']}", quiet)
            _output_info(f"  ADRs: {result['adrs']['count']}", quiet)
            if result["adrs"]["by_status"]:
                for s, c in result["adrs"]["by_status"].items():
                    _output_info(f"    - {s}: {c}", quiet)
            _output_info(f"  Dependencies: {result['dependencies']['count']}", quiet)

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        _exit_error(str(e))


# -----------------------------------------------------------------------------
# Sync Command
# -----------------------------------------------------------------------------


@app.command()
def sync(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Preview changes without applying them.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Sync documentation with codebase changes.

    Analyzes the codebase for changes that require documentation updates.
    Uses the freshness checker to identify stale documentation.

    In dry-run mode, shows what would need updating without making changes.
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        ctx_path = config.get_ctx_path(project_root)
        db_path = config.get_db_path(project_root)

        result: dict[str, Any] = {
            "ctx_path": str(ctx_path),
            "dry_run": dry_run,
            "stale_files": [],
            "needs_update": False,
        }

        if not ctx_path.exists() or not db_path.exists():
            result["error"] = "Context not initialized. Run 'cctx init' first."
            if json_output:
                console.print_json(json.dumps(result))
            else:
                _exit_error("Context not initialized. Run 'cctx init' first.")
            return

        # Run freshness checker to find stale docs
        from cctx.validators import ValidationRunner

        runner = ValidationRunner(project_root, db_path)
        validation_result = runner.run_single("freshness")

        if validation_result:
            for issue in validation_result.issues:
                stale_info = {
                    "system": issue.system,
                    "file": issue.file,
                    "message": issue.message,
                    "severity": issue.severity,
                }
                result["stale_files"].append(stale_info)

            result["needs_update"] = len(validation_result.issues) > 0

        if json_output:
            console.print_json(json.dumps(result))
        else:
            if dry_run:
                _output_warning("Dry run mode - showing what needs updating", quiet)

            _output_info(f"Checking context at: {ctx_path}", quiet)

            if not result["stale_files"]:
                _output_success("All documentation is up to date!", quiet)
            else:
                _output_warning(f"Found {len(result['stale_files'])} stale documentation files:", quiet)
                if not quiet:
                    for stale in result["stale_files"]:
                        severity_color = {
                            "error": "red",
                            "warning": "yellow",
                            "info": "blue",
                        }.get(stale["severity"], "white")
                        console.print(f"  [{severity_color}]{stale['severity']}[/{severity_color}] {stale['system']}/{stale['file']}")
                        console.print(f"    {stale['message']}")

                if not dry_run:
                    _output_info("", quiet)
                    _output_info("To update stale documentation:", quiet)
                    _output_info("  1. Review each file listed above", quiet)
                    _output_info("  2. Update with current system state", quiet)
                    _output_info("  3. Run 'cctx health' to verify", quiet)

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        _exit_error(str(e))


# -----------------------------------------------------------------------------
# Validate Command
# -----------------------------------------------------------------------------


@app.command()
def validate(
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Run pre-commit validation checks.

    Performs validation suitable for pre-commit hooks:
    - Checks context file integrity
    - Validates ADR format and indexing
    - Ensures required fields are present
    - Verifies system registrations

    Exits with code 2 if validation fails (errors found).
    Warnings do not cause validation failure.
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        ctx_path = config.get_ctx_path(project_root)
        db_path = config.get_db_path(project_root)

        result: dict[str, Any] = {
            "valid": True,
            "ctx_path": str(ctx_path),
            "checks": [],
            "errors": [],
            "warnings": [],
        }

        # Basic validation
        if not ctx_path.exists():
            result["valid"] = False
            result["errors"].append(f"Context directory not found: {ctx_path}")
            result["checks"].append({"name": "ctx_exists", "passed": False})
        else:
            result["checks"].append({"name": "ctx_exists", "passed": True})

        if not db_path.exists():
            result["valid"] = False
            result["errors"].append(f"Database not found: {db_path}")
            result["checks"].append({"name": "db_exists", "passed": False})
        else:
            result["checks"].append({"name": "db_exists", "passed": True})

        # Run validators if basic checks pass
        if ctx_path.exists() and db_path.exists():
            from cctx.validators import ValidationRunner

            runner = ValidationRunner(project_root, db_path)
            # Only run snapshot and adr validators for pre-commit (fast checks)
            validation_result = runner.run_validators(["snapshot", "adr"])

            # Add validator results
            for vr in validation_result.results:
                result["checks"].append({
                    "name": vr.name,
                    "passed": vr.status == "pass",
                })

            # Collect issues (only errors cause validation failure)
            for issue in validation_result.all_issues:
                if issue.severity == "error":
                    result["errors"].append(issue.message)
                    result["valid"] = False
                elif issue.severity == "warning":
                    result["warnings"].append(issue.message)

            result["summary"] = {
                "validators_run": validation_result.validators_run,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
            }

        if json_output:
            console.print_json(json.dumps(result))
        else:
            if result["valid"]:
                _output_success("Validation passed", quiet)
            else:
                _output_error("Validation failed")

            if not quiet:
                for check in result["checks"]:
                    status = "[green]PASS[/green]" if check["passed"] else "[red]FAIL[/red]"
                    console.print(f"  {status} {check['name']}")

                for error in result["errors"]:
                    _output_error(error)

                for warning in result["warnings"][:5]:  # Limit warnings shown
                    _output_warning(warning)

        if not result["valid"]:
            raise typer.Exit(code=2)  # Validation failure exit code

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"valid": False, "error": str(e)}))
        _exit_error(str(e))


# -----------------------------------------------------------------------------
# Doctor Command
# -----------------------------------------------------------------------------


@app.command()
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Apply fixes automatically.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be fixed (no changes).",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output.",
    ),
) -> None:
    """Find and fix common Living Context issues.

    Runs all validators and identifies issues that can be automatically fixed.
    By default, lists fixable issues with descriptions of what each fix would do.

    With --fix, applies all available fixes automatically.
    With --dry-run, shows what would be fixed without making changes.

    Exit codes:
      0 - All issues fixed or no issues found
      1 - Issues remain unfixed
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        ctx_path = config.get_ctx_path(project_root)
        db_path = config.get_db_path(project_root)

        result: dict[str, Any] = {
            "success": True,
            "ctx_path": str(ctx_path),
            "mode": "dry_run" if dry_run else ("fix" if fix else "check"),
            "total_issues": 0,
            "fixable_issues": 0,
            "fixes_applied": 0,
            "fixes_failed": 0,
            "issues": [],
            "fixes": [],
        }

        # Check basic requirements
        if not ctx_path.exists() or not db_path.exists():
            result["success"] = False
            result["error"] = "Context not initialized. Run 'cctx init' first."
            if json_output:
                console.print_json(json.dumps(result))
            else:
                _output_error("Context not initialized. Run 'cctx init' first.")
            raise typer.Exit(code=EXIT_USER_ERROR)

        # Run all validators
        from cctx.validators import ValidationRunner

        runner = ValidationRunner(project_root, db_path)
        validation_result = runner.run_all(deep=True)

        result["total_issues"] = validation_result.total_issues

        # Separate fixable from non-fixable issues
        fixable_issues: list[FixableIssue] = []
        non_fixable_issues: list[Any] = []

        for issue in validation_result.all_issues:
            issue_dict: dict[str, Any] = {
                "system": issue.system,
                "check": issue.check,
                "severity": issue.severity,
                "message": issue.message,
            }
            if issue.file:
                issue_dict["file"] = issue.file
            if issue.line:
                issue_dict["line"] = issue.line

            if isinstance(issue, FixableIssue) and issue.fix_id:
                fixable_issues.append(issue)
                issue_dict["fixable"] = True
                issue_dict["fix_id"] = issue.fix_id
                issue_dict["fix_description"] = issue.fix_description
            else:
                non_fixable_issues.append(issue)
                issue_dict["fixable"] = False

            result["issues"].append(issue_dict)

        result["fixable_issues"] = len(fixable_issues)

        # Get the fixer registry
        registry = get_global_registry()

        # Process fixes if requested
        if fix or dry_run:
            for issue in fixable_issues:
                fix_info: dict[str, Any] = {
                    "fix_id": issue.fix_id,
                    "system": issue.system,
                    "description": issue.fix_description,
                }

                if dry_run:
                    # Just record what would be done
                    fix_info["status"] = "would_apply"
                    fix_info["message"] = f"Would fix: {issue.fix_description}"
                    result["fixes"].append(fix_info)
                else:
                    # Actually apply the fix
                    fix_result: FixResult = registry.apply_fix(
                        issue, project_root, db_path
                    )

                    fix_info["status"] = "applied" if fix_result.success else "failed"
                    fix_info["message"] = fix_result.message
                    if fix_result.files_modified:
                        fix_info["files_modified"] = fix_result.files_modified
                    if fix_result.files_deleted:
                        fix_info["files_deleted"] = fix_result.files_deleted

                    if fix_result.success:
                        result["fixes_applied"] += 1
                    else:
                        result["fixes_failed"] += 1

                    result["fixes"].append(fix_info)

        # Determine overall success
        if fix:
            # In fix mode, success if all fixable issues were fixed
            result["success"] = result["fixes_failed"] == 0
        elif dry_run:
            # In dry-run mode, success is just informational
            result["success"] = True
        else:
            # In check mode, success if no issues found (fixable or not)
            result["success"] = len(fixable_issues) == 0 and len(non_fixable_issues) == 0

        # Output results
        if json_output:
            console.print_json(json.dumps(result))
        else:
            _doctor_print_results(
                result,
                fixable_issues,
                non_fixable_issues,
                fix=fix,
                dry_run=dry_run,
                verbose=verbose,
            )

        if not result["success"]:
            raise typer.Exit(code=EXIT_USER_ERROR)

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"success": False, "error": str(e)}))
        _exit_error(str(e))


def _doctor_print_results(
    result: dict[str, Any],
    fixable_issues: list[FixableIssue],
    non_fixable_issues: list[Any],
    *,
    fix: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Print doctor command results to console.

    Args:
        result: The result dictionary with fix information.
        fixable_issues: List of issues that can be fixed.
        non_fixable_issues: List of issues that cannot be fixed automatically.
        fix: Whether fixes were applied.
        dry_run: Whether this is a dry run.
        verbose: Whether to show detailed output.
    """
    total = result["total_issues"]
    fixable = result["fixable_issues"]

    # Header
    if total == 0:
        _output_success("No issues found. Context is healthy!")
        return

    mode_str = ""
    if dry_run:
        mode_str = " [dim](dry run)[/dim]"
    elif fix:
        mode_str = " [dim](fix mode)[/dim]"

    console.print(f"\n[bold]Living Context Doctor{mode_str}[/bold]")
    console.print(f"Found {total} issue(s), {fixable} fixable\n")

    # Show fixable issues
    if fixable_issues:
        console.print("[bold cyan]Fixable Issues:[/bold cyan]")

        for issue in fixable_issues:
            severity_color = {
                "error": "red",
                "warning": "yellow",
                "info": "blue",
            }.get(issue.severity, "white")

            console.print(
                f"  [{severity_color}]{issue.severity}[/{severity_color}] "
                f"[dim]{issue.system}[/dim]: {issue.message}"
            )
            console.print(f"    [green]Fix:[/green] {issue.fix_description}")
            if verbose:
                console.print(f"    [dim]fix_id: {issue.fix_id}[/dim]")

        console.print()

    # Show non-fixable issues if verbose
    if non_fixable_issues and verbose:
        console.print("[bold yellow]Non-fixable Issues:[/bold yellow]")

        for issue in non_fixable_issues:
            severity_color = {
                "error": "red",
                "warning": "yellow",
                "info": "blue",
            }.get(issue.severity, "white")

            console.print(
                f"  [{severity_color}]{issue.severity}[/{severity_color}] "
                f"[dim]{issue.system}[/dim]: {issue.message}"
            )

        console.print()

    # Show fix results if applicable
    if fix or dry_run:
        fixes = result.get("fixes", [])
        if fixes:
            if dry_run:
                console.print("[bold]Would apply the following fixes:[/bold]")
            else:
                console.print("[bold]Fix Results:[/bold]")

            for fix_info in fixes:
                status = fix_info.get("status", "unknown")
                if status == "would_apply":
                    console.print(
                        f"  [cyan]WOULD FIX[/cyan] {fix_info['description']}"
                    )
                elif status == "applied":
                    console.print(
                        f"  [green]FIXED[/green] {fix_info['description']}"
                    )
                    if verbose and fix_info.get("files_modified"):
                        for f in fix_info["files_modified"]:
                            console.print(f"    [dim]Modified: {f}[/dim]")
                elif status == "failed":
                    console.print(
                        f"  [red]FAILED[/red] {fix_info['description']}"
                    )
                    console.print(f"    [dim]{fix_info.get('message', '')}[/dim]")

            console.print()

    # Summary
    if fix:
        applied = result["fixes_applied"]
        failed = result["fixes_failed"]
        if failed == 0 and applied > 0:
            _output_success(f"Applied {applied} fix(es) successfully")
        elif failed > 0:
            _output_error(f"Applied {applied} fix(es), {failed} failed")
        elif applied == 0 and fixable > 0:
            _output_warning("No fixes were applied")
    elif dry_run:
        if fixable > 0:
            _output_info(
                f"Run [bold]cctx doctor --fix[/bold] to apply {fixable} fix(es)"
            )
    else:
        # Check mode
        if fixable > 0:
            _output_warning(
                f"Found {fixable} fixable issue(s). "
                f"Run [bold]cctx doctor --fix[/bold] to apply fixes"
            )
        if len(non_fixable_issues) > 0:
            _output_info(
                f"{len(non_fixable_issues)} issue(s) require manual attention"
            )


# -----------------------------------------------------------------------------
# Add-System Command
# -----------------------------------------------------------------------------


@app.command("add-system")
def add_system(
    path: str = typer.Argument(
        ...,
        help="Path to the system directory (e.g., src/systems/auth).",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Human-readable system name. Defaults to directory name.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Create .ctx/ directory structure for a system/module.

    Scaffolds the system context with:
    - snapshot.md: System overview and public API
    - constraints.md: System invariants and boundaries
    - decisions.md: Index of ADRs for this system
    - debt.md: Technical debt tracking
    - adr/: Directory for Architecture Decision Records
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)

        # Resolve system path relative to project root
        system_path = (project_root / path).resolve()

        # Derive name from path if not provided
        if name is None:
            # Convert path like "src/systems/auth" to "Auth System"
            dir_name = system_path.name
            name_parts = dir_name.replace("-", " ").replace("_", " ").split()
            # Capitalize each word
            name_parts = [p.capitalize() for p in name_parts]

            # Avoid "System System" if directory ends in "system"
            if name_parts and name_parts[-1].lower() == "system":
                name = " ".join(name_parts)
            else:
                name = " ".join(name_parts) + " System"

        result: dict[str, Any] = {
            "success": False,
            "system_path": str(system_path),
            "system_name": name,
        }

        try:
            ctx_path = scaffold_system_ctx(name, system_path, config)

            # Register system in database
            db_path = config.get_db_path(project_root)
            if db_path.exists():
                from cctx.crud import create_system
                from cctx.database import ContextDB

                with ContextDB(db_path, auto_init=False) as db, db.transaction():
                    try:
                        rel_path = system_path.relative_to(project_root).as_posix()
                    except ValueError:
                        _exit_error(f"System path {system_path} must be inside project root {project_root}")
                    create_system(db, rel_path, name)

            result["success"] = True
            result["ctx_path"] = str(ctx_path)

            if json_output:
                console.print_json(json.dumps(result))
            else:
                _output_success(f"Created system context at: {ctx_path}", quiet)
                if not quiet:
                    _output_info(f"  System: {name}")
                    _output_info(f"  Path: {system_path}")

        except ScaffoldError as e:
            result["error"] = str(e)
            if json_output:
                console.print_json(json.dumps(result))
            _exit_error(str(e))

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"success": False, "error": str(e)}))
        _exit_error(str(e))


# -----------------------------------------------------------------------------
# ADR Command
# -----------------------------------------------------------------------------


def _get_next_adr_number(adr_dir: Path) -> int:
    """Get the next available ADR number."""
    if not adr_dir.exists():
        return 1

    max_num = 0
    pattern = re.compile(r"ADR-(\d+)")
    for f in adr_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            match = pattern.search(f.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return max_num + 1


@app.command()
def adr(
    title: str = typer.Argument(
        ...,
        help="Title of the ADR (e.g., 'Use PostgreSQL for persistence').",
    ),
    system: str | None = typer.Option(
        None,
        "--system",
        "-s",
        help="System path to create ADR in. Creates in global .ctx/adr/ if not specified.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """Create a new Architecture Decision Record from template.

    Creates an ADR file with the next available number in sequence.
    If --system is specified, creates in that system's .ctx/adr/ directory.
    Otherwise, creates in the global .ctx/adr/ directory.
    """
    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)

        # Determine target ADR directory
        if system:
            system_path = project_root / system
            adr_dir = system_path / config.ctx_dir / "adr"
        else:
            # Global ADR directory
            ctx_path = config.get_ctx_path(project_root)
            adr_dir = ctx_path / "adr"

        result: dict[str, Any] = {
            "success": False,
            "title": title,
            "adr_dir": str(adr_dir),
        }

        # Ensure ADR directory exists
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Get next ADR number
        adr_num = _get_next_adr_number(adr_dir)
        adr_id = f"ADR-{adr_num:03d}"

        # Get current date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Load and render template
        from cctx.template_manager import get_template

        template_content = get_template("adr")

        # Replace placeholders
        content = template_content.replace("ADR-NNN", adr_id)
        content = content.replace("{Decision Title}", title)
        content = content.replace("YYYY-MM-DD", today)
        # Robustly replace status options with "proposed"
        # Matches "- **Status**: <anything>" and replaces with "- **Status**: proposed"
        # Handles optional bullet point and whitespace
        content = re.sub(
            r"(?m)^(\s*(?:[-*]\s+)?\*\*Status\*\*:\s*).+$",
            r"\1proposed",
            content,
        )

        # Write ADR file
        adr_filename = f"{adr_id}-{title.lower().replace(' ', '-')[:50]}.md"
        adr_path = adr_dir / adr_filename
        adr_path.write_text(content, encoding="utf-8")

        # Register ADR in database
        db_path = config.get_db_path(project_root)
        if db_path.exists():
            from cctx.adr_crud import create_adr
            from cctx.database import ContextDB

            with ContextDB(db_path, auto_init=False) as db, db.transaction():
                try:
                    rel_adr_path = adr_path.relative_to(project_root).as_posix()
                except ValueError:
                    _exit_error(f"ADR path {adr_path} must be inside project root {project_root}")
                create_adr(db, adr_id, title, "proposed", rel_adr_path)

        result["success"] = True
        result["adr_id"] = adr_id
        result["adr_path"] = str(adr_path)
        result["date"] = today

        if json_output:
            console.print_json(json.dumps(result))
        else:
            _output_success(f"Created {adr_id}: {title}", quiet)
            if not quiet:
                _output_info(f"  Path: {adr_path}")
                _output_info(f"  Date: {today}")
                _output_info("")
                _output_info("Next steps:")
                _output_info("  1. Edit the ADR file to fill in context, options, and decision")
                _output_info("  2. Update status to 'accepted' when approved")

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"success": False, "error": str(e)}))
        _exit_error(str(e))
    except FileNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"success": False, "error": str(e)}))
        _exit_error(f"Template not found: {e}")


# -----------------------------------------------------------------------------
# List Command
# -----------------------------------------------------------------------------


@app.command("list")
def list_entities(
    entity: str = typer.Argument(
        "systems",
        help="Entity type to list: systems, adrs, or debt.",
    ),
    ctx_dir: str | None = ctx_dir_option(),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output for CI.",
    ),
) -> None:
    """List registered entities (systems, ADRs, or debt items).

    Usage:
      cctx list systems   - List all registered systems
      cctx list adrs      - List all Architecture Decision Records
      cctx list debt      - List technical debt items (placeholder)
    """
    entity = entity.lower()
    valid_entities = ["systems", "adrs", "debt"]

    if entity not in valid_entities:
        _exit_error(f"Invalid entity type: {entity}. Must be one of: {', '.join(valid_entities)}")

    try:
        project_root = find_project_root(marker=ctx_dir or ".ctx")
        config = wire_config(ctx_dir=ctx_dir, start_dir=project_root)
        db_path = config.get_db_path(project_root)

        if not db_path.exists():
            _exit_error(f"Database not found: {db_path}. Run 'cctx init' first.")

        from cctx.database import ContextDB

        with ContextDB(db_path, auto_init=False) as db:
            if entity == "systems":
                _list_systems(db, json_output, quiet)
            elif entity == "adrs":
                _list_adrs(db, json_output, quiet)
            elif entity == "debt":
                _list_debt(db, json_output, quiet)

    except ProjectRootNotFoundError as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        _exit_error(str(e))


def _list_systems(db: ContextDB, json_output: bool, quiet: bool) -> None:
    """List all systems."""
    from cctx.crud import list_systems

    systems = list_systems(db)

    if json_output:
        console.print_json(json.dumps({"systems": systems}))
        return

    if not systems:
        _output_info("No systems registered.", quiet)
        return

    if quiet:
        for s in systems:
            console.print(s["path"])
        return

    table = Table(title="Registered Systems")
    table.add_column("Path", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")

    for s in systems:
        table.add_row(
            s["path"],
            s["name"],
            s.get("description") or "-",
        )

    console.print(table)


def _list_adrs(db: ContextDB, json_output: bool, quiet: bool) -> None:
    """List all ADRs."""
    from cctx.adr_crud import list_adrs

    adrs = list_adrs(db)

    if json_output:
        console.print_json(json.dumps({"adrs": adrs}))
        return

    if not adrs:
        _output_info("No ADRs registered.", quiet)
        return

    if quiet:
        for a in adrs:
            console.print(f"{a['id']}: {a['title']}")
        return

    table = Table(title="Architecture Decision Records")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Status")
    table.add_column("File")

    for a in adrs:
        status = a.get("status", "unknown")
        status_style = {
            "proposed": "yellow",
            "accepted": "green",
            "deprecated": "red",
            "superseded": "dim",
        }.get(status, "white")

        table.add_row(
            a["id"],
            a["title"],
            f"[{status_style}]{status}[/{status_style}]",
            a.get("file_path") or "-",
        )

    console.print(table)


def _list_debt(db: ContextDB, json_output: bool, quiet: bool) -> None:  # noqa: ARG001
    """List technical debt items (placeholder)."""
    # Note: db is unused for now but will be used when debt tracking is fully implemented
    result: dict[str, Any] = {
        "debt": [],
        "message": "Debt tracking not yet fully implemented. Check system .ctx/debt.md files.",
    }

    if json_output:
        console.print_json(json.dumps(result))
        return

    _output_warning("Debt tracking from database not yet implemented.", quiet)
    _output_info("Check individual system .ctx/debt.md files for debt items.", quiet)


# -----------------------------------------------------------------------------
# Plugin Helper Functions
# -----------------------------------------------------------------------------


def _get_plugin_source_path() -> Path | None:
    """Get the path to plugin files from the package.

    First tries importlib.resources for installed package,
    then falls back to development paths.

    Returns:
        Path to plugin directory or None if not found.
    """
    # Try importlib.resources for installed package
    try:
        if hasattr(importlib.resources, "files"):
            pkg_files = importlib.resources.files("cctx")
            plugin_path = pkg_files.joinpath("plugin")
            # Check if it exists and has content
            if hasattr(plugin_path, "is_dir") and plugin_path.is_dir():
                return Path(str(plugin_path))
    except (TypeError, AttributeError, FileNotFoundError):
        pass

    # Fallback: Check for development layout (cctx/plugin relative to package)
    try:
        pkg_files = importlib.resources.files("cctx")
        pkg_path = Path(str(pkg_files))
        # Development: cctx/src/cctx -> cctx/plugin
        dev_plugin_path = pkg_path.parent.parent / "plugin"
        if dev_plugin_path.is_dir():
            return dev_plugin_path
    except (TypeError, AttributeError, FileNotFoundError):
        pass

    return None


def _copy_plugin_files(src_dir: Path, dest_dir: Path) -> list[str]:
    """Copy plugin files from source to destination, preserving structure.

    Args:
        src_dir: Source plugin directory
        dest_dir: Destination directory (.claude/plugins/living-context/)

    Returns:
        List of relative paths of copied files.
    """
    copied_files: list[str] = []

    # Files and directories to copy
    items_to_copy = [
        (".claude-plugin", True),  # (path, is_directory)
        ("commands", True),
        ("skills", True),
        ("hooks", True),
    ]

    for item_name, is_dir in items_to_copy:
        src_path = src_dir / item_name
        if not src_path.exists():
            continue

        dest_path = dest_dir / item_name

        if is_dir:
            # Copy entire directory tree
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)

            # Collect all copied files
            for file_path in dest_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(dest_dir)
                    copied_files.append(str(rel_path))
        else:
            # Copy single file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            copied_files.append(item_name)

    return sorted(copied_files)


# -----------------------------------------------------------------------------
# Eval Command
# -----------------------------------------------------------------------------


@app.command("eval")
def eval_plugin(
    command: str | None = typer.Option(
        None,
        "--command",
        help="Filter tests by command name.",
    ),
    case: str | None = typer.Option(
        None,
        "--case",
        help="Run specific test case by name.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output.",
    ),
) -> None:
    """Run Living Context plugin evaluation tests.

    Executes test cases against the cctx CLI and validates results.

    Loads test cases from the plugin/eval/test-cases/ directory,
    using fixtures from plugin/eval/fixtures/ for isolated testing.
    """
    # Find the eval runner script
    plugin_src = _get_plugin_source_path()
    if plugin_src is None:
        _output_error("Plugin files not found. Ensure cctx is properly installed.")
        raise typer.Exit(code=EXIT_USER_ERROR)

    runner_script = plugin_src / "eval" / "runner.py"
    if not runner_script.exists():
        _output_error(f"Evaluation runner not found: {runner_script}")
        raise typer.Exit(code=EXIT_USER_ERROR)

    # Build command arguments
    cmd_args = [str(runner_script)]

    if command:
        cmd_args.extend(["--command", command])

    if case:
        cmd_args.extend(["--case", case])

    if json_output:
        cmd_args.append("--json")

    if verbose:
        cmd_args.append("--verbose")

    # Execute the runner script
    try:
        result = subprocess.run(
            [sys.executable] + cmd_args,
            cwd=plugin_src.parent,  # cctx/ directory
            capture_output=False,  # Let output flow to console
            text=True,
        )
        # Return the exit code from the runner
        raise typer.Exit(code=result.returncode)
    except FileNotFoundError:
        _output_error("Python interpreter not found")
        raise typer.Exit(code=EXIT_USER_ERROR) from None
    except OSError as e:
        _output_error(f"Failed to run evaluation: {e}")
        raise typer.Exit(code=EXIT_USER_ERROR) from None


if __name__ == "__main__":
    app()
