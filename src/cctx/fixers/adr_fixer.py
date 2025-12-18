"""Fixer for unregistered ADR files.

Registers ADR files that exist on disk but are not in the knowledge database.
Parses the ADR markdown file to extract metadata and creates the database entry.
"""

from __future__ import annotations

import re

from cctx.adr_crud import create_adr, get_adr
from cctx.database import ContextDB
from cctx.fixers.base import BaseFixer, FixResult
from cctx.validators.base import FixableIssue


class AdrFixer(BaseFixer):
    """Fixer for unregistered ADR files.

    Registers ADR files found on disk into the knowledge.db database.
    Parses the ADR markdown to extract title, status, date, context,
    decision, and consequences.

    Fix parameters expected in FixableIssue.fix_params:
        - adr_id: The ADR identifier (e.g., "ADR-003").
        - file_path: Relative path to the ADR file.
        - system: The system this ADR belongs to (relative path to .ctx directory).
    """

    fix_id = "unregistered_adr"

    def fix(self, issue: FixableIssue) -> FixResult:
        """Register an unregistered ADR file in the database.

        Args:
            issue: The fixable issue containing the ADR details.

        Returns:
            FixResult indicating success or failure.
        """
        # Extract fix parameters
        adr_id = issue.fix_params.get("adr_id")
        file_path = issue.fix_params.get("file_path")

        if not adr_id:
            return FixResult(
                success=False,
                message="adr_id is required in fix_params",
            )

        if not file_path:
            return FixResult(
                success=False,
                message="file_path is required in fix_params",
            )

        # Check if database exists
        if not self.db_path.exists():
            return FixResult(
                success=False,
                message=f"Database not found at {self.db_path}",
            )

        # Resolve the file path
        adr_file = self._resolve_path(file_path)
        if not adr_file.exists():
            return FixResult(
                success=False,
                message=f"ADR file not found at {adr_file}",
            )

        # Check if ADR is already registered (idempotency)
        try:
            with ContextDB(self.db_path, auto_init=False) as db:
                existing = get_adr(db, adr_id)
                if existing is not None:
                    return FixResult(
                        success=True,
                        message=f"ADR {adr_id} is already registered in database",
                        files_modified=[],
                    )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Failed to check existing ADR: {e}",
            )

        # Parse the ADR file
        try:
            content = adr_file.read_text(encoding="utf-8")
            parsed = self._parse_adr_content(content, adr_id)
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Failed to parse ADR file: {e}",
            )

        # Register in database
        # Title and status always have defaults from _parse_adr_content
        title = parsed["title"] or adr_id
        status = parsed["status"] or "proposed"
        try:
            with ContextDB(self.db_path, auto_init=False) as db, db.transaction():
                create_adr(
                    db,
                    id=adr_id,
                    title=title,
                    status=status,
                    file_path=file_path,
                    context=parsed.get("context"),
                    decision=parsed.get("decision"),
                    consequences=parsed.get("consequences"),
                )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Failed to register ADR in database: {e}",
            )

        return FixResult(
            success=True,
            message=f"Registered ADR {adr_id} in database",
            files_modified=[],  # Database modified, not files
        )

    def _parse_adr_content(self, content: str, adr_id: str) -> dict[str, str | None]:
        """Parse ADR markdown content to extract metadata.

        Handles standard ADR format with:
        - Title in first heading (# ADR-XXX: Title)
        - Status in **Status**: value format
        - Context, Decision, Consequences in ## sections

        Args:
            content: The raw markdown content.
            adr_id: The ADR identifier for fallback title.

        Returns:
            Dictionary with title, status, context, decision, consequences.
        """
        result: dict[str, str | None] = {
            "title": adr_id,  # Default to adr_id if title not found
            "status": "proposed",  # Default status
            "context": None,
            "decision": None,
            "consequences": None,
        }

        # Extract title from first heading
        # Pattern: # ADR-XXX: Title or just # Title
        title_match = re.search(r"^#\s+(?:ADR-\d+:\s*)?(.+)$", content, re.MULTILINE)
        if title_match:
            result["title"] = title_match.group(1).strip()

        # Extract status
        # Pattern: **Status**: value or - **Status**: value
        status_match = re.search(r"\*\*Status\*\*:\s*(\w+)", content, re.IGNORECASE)
        if status_match:
            result["status"] = status_match.group(1).lower()

        # Extract sections (Context, Decision, Consequences)
        sections = self._extract_sections(content)
        result["context"] = sections.get("context")
        result["decision"] = sections.get("decision")
        result["consequences"] = sections.get("consequences")

        return result

    def _extract_sections(self, content: str) -> dict[str, str | None]:
        """Extract content from ## sections.

        Args:
            content: The raw markdown content.

        Returns:
            Dictionary mapping section names to their content.
        """
        sections: dict[str, str | None] = {}

        # Split content by ## headings
        # Pattern finds ## Heading and captures until next ## or end
        section_pattern = re.compile(r"##\s+([^\n]+)\n(.*?)(?=\n##\s+|\Z)", re.DOTALL)

        for match in section_pattern.finditer(content):
            heading = match.group(1).strip().lower()
            body = match.group(2).strip()

            # Map common heading names to our keys
            if "context" in heading:
                sections["context"] = body if body else None
            elif "decision" in heading and "record" not in heading:
                # "Decision" but not "Architecture Decision Record"
                sections["decision"] = body if body else None
            elif "consequence" in heading:
                sections["consequences"] = body if body else None

        return sections
