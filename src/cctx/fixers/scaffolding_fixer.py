"""Fixers for missing .ctx directories and template files.

Provides fixers for creating missing directory structures and
individual template files.
"""

from __future__ import annotations

from cctx.config import load_config
from cctx.fixers.base import BaseFixer, FixResult
from cctx.fixers.utils import derive_system_name
from cctx.scaffolder import scaffold_system_ctx
from cctx.template_manager import render_template
from cctx.validators.base import FixableIssue


class MissingCtxDirFixer(BaseFixer):
    """Fixer for missing .ctx directories.

    Creates a complete .ctx directory structure for a system,
    including all template files (snapshot.md, constraints.md,
    decisions.md, debt.md) and the adr/ subdirectory.

    Fix parameters expected in FixableIssue.fix_params:
        - system_name (optional): Human-readable name for the system.
            Defaults to the directory name if not provided.
    """

    fix_id = "missing_ctx_dir"

    def fix(self, issue: FixableIssue) -> FixResult:
        """Create a missing .ctx directory with all template files.

        Args:
            issue: The fixable issue containing the system path.

        Returns:
            FixResult indicating success or failure.
        """
        # Get the system path from the issue
        system_path = self._resolve_path(issue.system)
        ctx_dir = system_path / ".ctx"

        # Check if .ctx already exists (idempotency)
        if ctx_dir.exists():
            return FixResult(
                success=True,
                message=f".ctx directory already exists at {ctx_dir}",
                files_modified=[],
            )

        # Ensure system directory exists
        if not system_path.exists():
            try:
                system_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return FixResult(
                    success=False,
                    message=f"Failed to create system directory: {e}",
                )

        # Get system name from fix_params or derive from path
        system_name = issue.fix_params.get("system_name")
        if not system_name:
            system_name = derive_system_name(system_path)

        # Load config for scaffolder
        try:
            config = load_config(start_dir=self.project_root)
        except ValueError as e:
            return FixResult(
                success=False,
                message=f"Failed to load config: {e}",
            )

        # Use scaffolder to create the .ctx directory
        try:
            created_ctx_path = scaffold_system_ctx(
                system_name=system_name,
                system_path=system_path,
                config=config,
            )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Failed to scaffold .ctx directory: {e}",
            )

        # List all created files
        files_modified: list[str] = []
        for file_path in created_ctx_path.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(self.project_root))
                files_modified.append(rel_path)

        rel_ctx = str(created_ctx_path.relative_to(self.project_root))
        return FixResult(
            success=True,
            message=f"Created .ctx directory at {rel_ctx} with {len(files_modified)} files",
            files_modified=sorted(files_modified),
        )


class MissingTemplateFileFixer(BaseFixer):
    """Fixer for missing individual template files.

    Creates individual template files (constraints.md, decisions.md,
    debt.md) when they are missing from an existing .ctx directory.

    Fix parameters expected in FixableIssue.fix_params:
        - template_name (required): Name of the template to create
            (e.g., "constraints", "decisions", "debt").
        - system_name (optional): Human-readable name for the system.
            Defaults to the directory name if not provided.
    """

    fix_id = "missing_template_file"

    # Valid template names that can be created
    VALID_TEMPLATES = {"constraints", "decisions", "debt"}

    def fix(self, issue: FixableIssue) -> FixResult:
        """Create a missing template file.

        Args:
            issue: The fixable issue containing the system path and
                template name in fix_params.

        Returns:
            FixResult indicating success or failure.
        """
        # Get template name from fix_params
        template_name = issue.fix_params.get("template_name")
        if not template_name:
            return FixResult(
                success=False,
                message="template_name is required in fix_params",
            )

        if template_name not in self.VALID_TEMPLATES:
            return FixResult(
                success=False,
                message=(
                    f"Invalid template_name: {template_name}. "
                    f"Valid templates: {', '.join(sorted(self.VALID_TEMPLATES))}"
                ),
            )

        # Get the system path from the issue
        system_path = self._resolve_path(issue.system)
        ctx_dir = system_path / ".ctx"
        template_path = ctx_dir / f"{template_name}.md"

        # Check if file already exists (idempotency)
        if template_path.exists():
            return FixResult(
                success=True,
                message=f"{template_name}.md already exists at {template_path}",
                files_modified=[],
            )

        # Ensure .ctx directory exists
        if not ctx_dir.exists():
            return FixResult(
                success=False,
                message=(
                    f".ctx directory does not exist at {ctx_dir}. "
                    "Run the missing_ctx_dir fixer first."
                ),
            )

        # Get system name from fix_params or derive from path
        system_name = issue.fix_params.get("system_name")
        if not system_name:
            system_name = derive_system_name(system_path)

        # Render the template
        try:
            content = render_template(template_name, system_name=system_name)
        except (FileNotFoundError, ValueError) as e:
            return FixResult(
                success=False,
                message=f"Failed to render {template_name} template: {e}",
            )

        # Write the file
        try:
            template_path.write_text(content, encoding="utf-8")
        except OSError as e:
            return FixResult(
                success=False,
                message=f"Failed to write {template_name}.md: {e}",
            )

        rel_path = str(template_path.relative_to(self.project_root))
        return FixResult(
            success=True,
            message=f"Created {template_name}.md from template at {rel_path}",
            files_modified=[rel_path],
        )
