"""Markdown parsing utility for Living Context documentation.

Provides tools for extracting structured data from markdown files including
tables, sections, and code blocks. Uses only regex (no external markdown libraries).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MarkdownTable:
    """A parsed markdown table.

    Attributes:
        headers: List of column header strings.
        rows: List of dictionaries mapping header names to cell values.
    """

    headers: list[str]
    rows: list[dict[str, str]]


@dataclass
class MarkdownSection:
    """A parsed markdown section.

    Attributes:
        heading: The heading text (without the # prefix).
        level: The heading level (1 for #, 2 for ##, etc.).
        content: The content under this heading until the next same/higher level heading.
    """

    heading: str
    level: int
    content: str


class MarkdownParser:
    """Parse markdown files for context documentation.

    This parser extracts structured data from markdown files used in the
    Living Context system, including tables, sections, and code blocks.
    All methods are static and stateless.
    """

    # Regex patterns
    _TABLE_ROW_PATTERN = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    _SEPARATOR_PATTERN = re.compile(r"^:?-+:?$")
    _HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _CODE_BLOCK_PATTERN = re.compile(
        r"^```(\w*)\n(.*?)^```",
        re.MULTILINE | re.DOTALL,
    )

    @staticmethod
    def extract_tables(content: str) -> list[MarkdownTable]:
        """Extract all markdown tables from content.

        Handles:
        - Standard | col1 | col2 | format
        - Header separator row (|---|---|)
        - Cell alignment markers (:---, :---:, ---:)

        Args:
            content: Markdown content to parse.

        Returns:
            List of MarkdownTable objects found in the content.
        """
        tables: list[MarkdownTable] = []
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Look for potential table start (line with pipes)
            if line.startswith("|") and line.endswith("|"):
                # Try to parse a table starting here
                table = MarkdownParser._try_parse_table(lines, i)
                if table is not None:
                    tables.append(table)
                    # Skip past the table we just parsed
                    # Count header + separator + data rows
                    i += 2 + len(table.rows)
                    continue

            i += 1

        return tables

    @staticmethod
    def _try_parse_table(lines: list[str], start_index: int) -> MarkdownTable | None:
        """Try to parse a table starting at the given index.

        Args:
            lines: All lines in the document.
            start_index: Index of the potential header row.

        Returns:
            MarkdownTable if successful, None otherwise.
        """
        if start_index + 1 >= len(lines):
            return None

        header_line = lines[start_index].strip()
        separator_line = lines[start_index + 1].strip()

        # Validate header line
        if not (header_line.startswith("|") and header_line.endswith("|")):
            return None

        # Validate separator line
        if not (separator_line.startswith("|") and separator_line.endswith("|")):
            return None

        # Parse header cells
        headers = MarkdownParser._parse_table_row(header_line)
        if not headers:
            return None

        # Validate separator row
        separator_cells = MarkdownParser._parse_table_row(separator_line)
        if not separator_cells:
            return None

        # Check that separator cells contain only dashes and alignment markers
        for cell in separator_cells:
            if not MarkdownParser._SEPARATOR_PATTERN.match(cell):
                return None

        # Check that separator has same number of columns as header
        if len(separator_cells) != len(headers):
            return None

        # Parse data rows
        rows: list[dict[str, str]] = []
        i = start_index + 2

        while i < len(lines):
            line = lines[i].strip()

            # Empty line or non-table line ends the table
            if not line or not (line.startswith("|") and line.endswith("|")):
                break

            cells = MarkdownParser._parse_table_row(line)

            # Row must have same number of columns as header (or we pad/truncate)
            if cells:
                row_dict: dict[str, str] = {}
                for j, header in enumerate(headers):
                    if j < len(cells):
                        row_dict[header] = cells[j]
                    else:
                        row_dict[header] = ""
                rows.append(row_dict)

            i += 1

        return MarkdownTable(headers=headers, rows=rows)

    @staticmethod
    def _parse_table_row(line: str) -> list[str]:
        """Parse a single table row into cells.

        Args:
            line: A line like "| cell1 | cell2 |"

        Returns:
            List of cell contents, trimmed of whitespace.
        """
        # Remove leading and trailing pipes
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]

        # Use regex split to handle escaped pipes
        # This regex looks for a pipe that is NOT preceded by a backslash
        cells: list[str] = []
        current_cell: list[str] = []
        i = 0
        while i < len(line):
            char = line[i]
            if char == "\\":
                # Check next char
                if i + 1 < len(line):
                    next_char = line[i + 1]
                    if next_char == "|":
                        current_cell.append("|")  # Unescape pipe
                        i += 2
                        continue
                    else:
                        current_cell.append("\\")
                        i += 1
                        continue
                else:
                    current_cell.append("\\")
                    i += 1
                    continue
            elif char == "|":
                cells.append("".join(current_cell).strip())
                current_cell = []
                i += 1
            else:
                current_cell.append(char)
                i += 1

        # Add the last cell
        cells.append("".join(current_cell).strip())

        return cells

    @staticmethod
    def extract_table_by_header(content: str, header_contains: str) -> MarkdownTable | None:
        """Find table that follows a heading containing given text.

        Searches for a heading that contains the specified text (case-insensitive),
        then returns the first table found after that heading.

        Args:
            content: Markdown content to search.
            header_contains: Text to search for in headings.

        Returns:
            The first MarkdownTable found after the matching heading, or None.
        """
        # Find all headings and their positions
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        headings = list(heading_pattern.finditer(content))

        # Find the heading containing the search text
        target_heading = None
        target_pos = -1

        for match in headings:
            heading_text = match.group(2).strip()
            if header_contains.lower() in heading_text.lower():
                target_heading = match
                target_pos = match.end()
                break

        if target_heading is None:
            return None

        # Find the next heading (if any) to bound our search
        next_heading_pos = len(content)
        for match in headings:
            if match.start() > target_pos:
                next_heading_pos = match.start()
                break

        # Extract content between this heading and next
        section_content = content[target_pos:next_heading_pos]

        # Find first table in this section
        tables = MarkdownParser.extract_tables(section_content)
        if tables:
            return tables[0]

        return None

    @staticmethod
    def extract_section(content: str, heading: str, level: int = 2) -> str | None:
        """Extract content under a specific heading.

        Returns content from after the heading until next heading of same or
        higher level (lower number), or end of file.

        Args:
            content: Markdown content to search.
            heading: Exact heading text to find (without # prefix).
            level: The heading level to search for (default 2 for ##).

        Returns:
            Content under the heading, or None if heading not found.
        """
        # Build pattern for the specific heading
        hashes = "#" * level
        # Escape special regex characters in heading
        escaped_heading = re.escape(heading)
        pattern = re.compile(
            rf"^{hashes}\s+{escaped_heading}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )

        match = pattern.search(content)
        if match is None:
            return None

        start_pos = match.end()

        # Find next heading of same or higher level
        # Higher level = fewer hashes (e.g., level 1 is higher than level 2)
        next_heading_pattern = re.compile(
            rf"^#{{{1},{level}}}\s+",
            re.MULTILINE,
        )

        next_match = next_heading_pattern.search(content, start_pos)
        end_pos = next_match.start() if next_match else len(content)

        # Extract and clean up the content
        section_content = content[start_pos:end_pos].strip()
        return section_content

    @staticmethod
    def extract_all_sections(content: str) -> list[MarkdownSection]:
        """Extract all sections with their headings and content.

        Parses all headings in the document and extracts the content
        under each heading until the next heading of the same or higher level.

        Args:
            content: Markdown content to parse.

        Returns:
            List of MarkdownSection objects representing all sections.
        """
        sections: list[MarkdownSection] = []
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

        # Find all headings
        headings = list(heading_pattern.finditer(content))

        for i, match in enumerate(headings):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            start_pos = match.end()

            # Find where this section ends
            # It ends at the next heading of same or higher level (fewer #)
            end_pos = len(content)

            for j in range(i + 1, len(headings)):
                next_level = len(headings[j].group(1))
                if next_level <= level:
                    end_pos = headings[j].start()
                    break

            # Extract content
            section_content = content[start_pos:end_pos].strip()

            sections.append(
                MarkdownSection(
                    heading=heading_text,
                    level=level,
                    content=section_content,
                )
            )

        return sections

    @staticmethod
    def extract_code_blocks(content: str, language: str | None = None) -> list[str]:
        """Extract fenced code blocks, optionally filtering by language.

        Extracts content from triple-backtick fenced code blocks. Can filter
        to only return blocks with a specific language tag.

        Args:
            content: Markdown content to parse.
            language: Optional language to filter by (e.g., "python", "sql").
                     If None, returns all code blocks.

        Returns:
            List of code block contents (without the fence markers).
        """
        code_blocks: list[str] = []

        # Use regex to find all code blocks
        for match in MarkdownParser._CODE_BLOCK_PATTERN.finditer(content):
            block_language = match.group(1).strip().lower()
            block_content = match.group(2)

            # Filter by language if specified
            if language is None or language.lower() == block_language:
                code_blocks.append(block_content)

        return code_blocks
