"""Fixer for stale or missing graph.json files.

Regenerates the dependency graph from the knowledge database.
"""

from __future__ import annotations

from lctx.database import ContextDB
from lctx.fixers.base import BaseFixer, FixResult
from lctx.graph import generate_graph, save_graph
from lctx.validators.base import FixableIssue


class GraphFixer(BaseFixer):
    """Fixer for stale graph.json files.

    Regenerates graph.json from the knowledge database when it
    is detected as stale or out of sync with system changes.

    Fix parameters expected in FixableIssue.fix_params:
        None required - uses project_root and db_path from initialization.
    """

    fix_id = "stale_graph"

    def fix(self, issue: FixableIssue) -> FixResult:  # noqa: ARG002
        """Regenerate graph.json from the database.

        Args:
            issue: The fixable issue (not used directly, but required
                for the fix interface).

        Returns:
            FixResult indicating success or failure.
        """
        # Determine graph path from project root
        ctx_dir = self.project_root / ".ctx"
        graph_path = ctx_dir / "graph.json"

        # Check if database exists
        if not self.db_path.exists():
            return FixResult(
                success=False,
                message=(
                    f"Knowledge database not found at {self.db_path}. "
                    "Initialize the project first with 'lctx init'."
                ),
            )

        # Check if .ctx directory exists
        if not ctx_dir.exists():
            return FixResult(
                success=False,
                message=(
                    f".ctx directory does not exist at {ctx_dir}. "
                    "Initialize the project first with 'lctx init'."
                ),
            )

        # Generate graph from database
        try:
            with ContextDB(self.db_path, auto_init=False) as db:
                graph_data = generate_graph(db)
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Failed to generate graph from database: {e}",
            )

        # Save the graph
        try:
            save_graph(graph_data, graph_path)
        except OSError as e:
            return FixResult(
                success=False,
                message=f"Failed to write graph.json: {e}",
            )

        rel_path = str(graph_path.relative_to(self.project_root))
        node_count = len(graph_data)
        return FixResult(
            success=True,
            message=f"Regenerated graph.json with {node_count} systems at {rel_path}",
            files_modified=[rel_path],
        )
