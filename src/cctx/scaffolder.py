"""System directory scaffolding for Living Context.

Creates `.ctx/` directories for new systems with all required template files.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from cctx.config import CctxConfig
from cctx.template_manager import render_template


class ScaffoldError(Exception):
    """Raised when scaffolding operations fail."""


# System-level templates (not including adr which is per-decision)
SYSTEM_TEMPLATES = ["snapshot", "constraints", "decisions", "debt"]


def scaffold_system_ctx(
    system_name: str,
    system_path: Path,
    config: CctxConfig,
) -> Path:
    """Scaffold a new system's .ctx/ directory with all template files.

    Creates the .ctx/ directory structure for a system with:
    - snapshot.md: System overview and public API
    - constraints.md: System invariants and boundaries
    - decisions.md: Index of ADRs for this system
    - debt.md: Technical debt tracking
    - adr/: Empty directory for future Architecture Decision Records

    Args:
        system_name: Human-readable name for the system (e.g., "Auth System").
            This is substituted into templates via the {System Name} placeholder.
        system_path: Path to the system directory (e.g., Path("src/systems/auth")).
            The .ctx/ directory will be created inside this path.
        config: CctxConfig instance for path resolution.

    Returns:
        Path to the created .ctx/ directory.

    Raises:
        ScaffoldError: If the .ctx/ directory already exists, if the operation
            fails, or if the parent system directory cannot be created.

    Example:
        >>> from cctx.scaffolder import scaffold_system_ctx
        >>> from cctx.config import load_config
        >>> from pathlib import Path
        >>> config = load_config()
        >>> system_path = Path("src/systems/auth")
        >>> ctx_path = scaffold_system_ctx("Auth System", system_path, config)
        >>> # Creates src/systems/auth/.ctx/ with all template files
    """
    ctx_dir_name = config.ctx_dir
    target_ctx_path = system_path / ctx_dir_name

    # Check if .ctx/ already exists
    if target_ctx_path.exists():
        raise ScaffoldError(
            f"Context directory already exists: {target_ctx_path}. "
            "Remove it first or use a different system path."
        )

    # Create parent system directory if needed
    try:
        system_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ScaffoldError(f"Cannot create system directory {system_path}: {e}") from e

    # Create in a temp directory first for atomicity, then move
    temp_dir = None
    try:
        # Create temp directory in the same filesystem for atomic move
        temp_dir = Path(tempfile.mkdtemp(dir=system_path, prefix=".ctx_temp_"))

        # Render and write each template file
        for template_name in SYSTEM_TEMPLATES:
            content = render_template(template_name, system_name=system_name)
            output_file = temp_dir / f"{template_name}.md"
            output_file.write_text(content, encoding="utf-8")

        # Create empty adr/ subdirectory
        adr_dir = temp_dir / "adr"
        adr_dir.mkdir()

        # Atomic rename from temp to target
        temp_dir.rename(target_ctx_path)
        temp_dir = None  # Mark as successfully moved

    except OSError as e:
        raise ScaffoldError(f"Failed to scaffold .ctx/ directory: {e}") from e
    finally:
        # Clean up temp directory if something went wrong
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return target_ctx_path


def scaffold_project_ctx(
    project_path: Path,
    config: CctxConfig,
) -> Path:
    """Scaffold a project's global .ctx/ directory.

    Creates the global .ctx/ directory at the project root with:
    - knowledge.db: SQLite database (empty, schema to be initialized separately)
    - graph.json: Empty dependency graph
    - schema.sql: Database schema file (empty placeholder)
    - templates/: Copy of template files for reference
    - README.md: Documentation for the Living Context system

    Note: This creates a minimal structure. The database and graph should be
    initialized by the appropriate initialization commands.

    Args:
        project_path: Path to the project root directory.
        config: CctxConfig instance for path resolution.

    Returns:
        Path to the created .ctx/ directory.

    Raises:
        ScaffoldError: If the .ctx/ directory already exists or if the
            operation fails.

    Example:
        >>> from cctx.scaffolder import scaffold_project_ctx
        >>> from cctx.config import load_config
        >>> from pathlib import Path
        >>> config = load_config()
        >>> ctx_path = scaffold_project_ctx(Path("."), config)
        >>> # Creates .ctx/ with global context files
    """
    ctx_dir_name = config.ctx_dir
    target_ctx_path = project_path / ctx_dir_name

    # Check if .ctx/ already exists
    if target_ctx_path.exists():
        raise ScaffoldError(
            f"Context directory already exists: {target_ctx_path}. "
            "Remove it first or use a different project path."
        )

    # Create project directory if needed
    try:
        project_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ScaffoldError(f"Cannot create project directory {project_path}: {e}") from e

    # Create in a temp directory first for atomicity
    temp_dir = None
    try:
        # Create temp directory in the same filesystem for atomic move
        temp_dir = Path(tempfile.mkdtemp(dir=project_path, prefix=".ctx_temp_"))

        # Create empty graph.json (valid empty JSON array)
        graph_file = temp_dir / config.graph_name
        graph_file.write_text("[]", encoding="utf-8")

        # Create templates/ directory with copies of all templates
        templates_dir = temp_dir / "templates"
        templates_dir.mkdir()

        # Copy all template files to templates/ directory
        all_templates = SYSTEM_TEMPLATES + ["adr"]
        for template_name in all_templates:
            content = render_template(template_name)
            output_file = templates_dir / f"{template_name}.template.md"
            output_file.write_text(content, encoding="utf-8")

        # Create README.md with basic documentation
        readme_content = _get_project_ctx_readme()
        readme_file = temp_dir / "README.md"
        readme_file.write_text(readme_content, encoding="utf-8")

        # Atomic rename from temp to target
        temp_dir.rename(target_ctx_path)
        temp_dir = None  # Mark as successfully moved

    except OSError as e:
        raise ScaffoldError(f"Failed to scaffold project .ctx/ directory: {e}") from e
    finally:
        # Clean up temp directory if something went wrong
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return target_ctx_path


def _get_project_ctx_readme() -> str:
    """Get the content for the project .ctx/ README.md file."""
    return """\
# Living Context

This directory contains project-wide context documentation.

## Structure

| File/Directory | Purpose |
|----------------|---------|
| `knowledge.db` | SQLite database storing ADRs, systems, and dependencies |
| `graph.json` | Generated dependency graph |
| `schema.sql` | Database schema definition |
| `templates/` | Documentation templates for systems and ADRs |
| `README.md` | This file |

## Usage

Use the `cctx` CLI tool to manage this context:

```bash
# Check context health
cctx health

# Sync documentation
cctx sync

# Initialize database
cctx init
```

## System Context

Each system has its own `.ctx/` directory with:
- `snapshot.md` - System overview and public API
- `constraints.md` - Invariants and boundaries
- `decisions.md` - Index of ADRs
- `debt.md` - Technical debt tracking
- `adr/` - Architecture Decision Records
"""
