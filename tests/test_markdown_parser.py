"""Tests for markdown parser utility."""

from __future__ import annotations

from cctx.validators.markdown_parser import MarkdownParser


class TestExtractTables:
    """Tests for MarkdownParser.extract_tables method."""

    def test_simple_table(self) -> None:
        """Test extraction of a simple two-column table."""
        content = """
| Column 1 | Column 2 |
|----------|----------|
| value1   | value2   |
| value3   | value4   |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].headers == ["Column 1", "Column 2"]
        assert len(tables[0].rows) == 2
        assert tables[0].rows[0] == {"Column 1": "value1", "Column 2": "value2"}
        assert tables[0].rows[1] == {"Column 1": "value3", "Column 2": "value4"}

    def test_table_with_alignment_markers(self) -> None:
        """Test table with left, center, and right alignment markers."""
        content = """
| Left | Center | Right |
|:-----|:------:|------:|
| a    | b      | c     |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].headers == ["Left", "Center", "Right"]
        assert tables[0].rows[0] == {"Left": "a", "Center": "b", "Right": "c"}

    def test_empty_cells(self) -> None:
        """Test table with empty cells."""
        content = """
| Name | Value |
|------|-------|
| foo  |       |
|      | bar   |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].rows[0] == {"Name": "foo", "Value": ""}
        assert tables[0].rows[1] == {"Name": "", "Value": "bar"}

    def test_multiple_tables(self) -> None:
        """Test extraction of multiple tables from content."""
        content = """
## First Section

| A | B |
|---|---|
| 1 | 2 |

## Second Section

| C | D | E |
|---|---|---|
| x | y | z |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 2
        assert tables[0].headers == ["A", "B"]
        assert tables[1].headers == ["C", "D", "E"]

    def test_table_with_special_content(self) -> None:
        """Test table with backticks, links, and special characters."""
        content = """
| Export | Type | Description |
|--------|------|-------------|
| `example` | function | What it does |
| `[link](url)` | method | A [link](http://example.com) |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].rows[0]["Export"] == "`example`"
        assert tables[0].rows[0]["Type"] == "function"

    def test_no_tables(self) -> None:
        """Test content with no tables returns empty list."""
        content = """
# Heading

Some text without tables.

- List item 1
- List item 2
"""
        tables = MarkdownParser.extract_tables(content)
        assert tables == []

    def test_invalid_table_no_separator(self) -> None:
        """Test that lines without proper separator are not treated as table."""
        content = """
| Header 1 | Header 2 |
| value1   | value2   |
"""
        tables = MarkdownParser.extract_tables(content)
        # Should not parse as table since second row is not a valid separator
        assert tables == []

    def test_table_with_extra_whitespace(self) -> None:
        """Test table cells with extra whitespace are trimmed."""
        content = """
|   Name   |   Value   |
|----------|-----------|
|   foo    |   bar     |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].headers == ["Name", "Value"]
        assert tables[0].rows[0] == {"Name": "foo", "Value": "bar"}

    def test_table_ends_at_non_table_line(self) -> None:
        """Test that table parsing stops at non-table content."""
        content = """
| A | B |
|---|---|
| 1 | 2 |

Some text after table.

More text.
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert len(tables[0].rows) == 1

    def test_single_column_table(self) -> None:
        """Test single column table."""
        content = """
| Item |
|------|
| one  |
| two  |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].headers == ["Item"]
        assert tables[0].rows[0] == {"Item": "one"}
        assert tables[0].rows[1] == {"Item": "two"}

    def test_table_header_only(self) -> None:
        """Test table with header and separator but no data rows."""
        content = """
| Header |
|--------|
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        assert tables[0].headers == ["Header"]
        assert tables[0].rows == []


class TestExtractTableByHeader:
    """Tests for MarkdownParser.extract_table_by_header method."""

    def test_find_table_after_heading(self) -> None:
        """Test finding table after a specific heading."""
        content = """
## Public API

| Export | Type | Description |
|--------|------|-------------|
| `func` | function | Does something |

## Dependencies

| System | Why |
|--------|-----|
| `other` | Reason |
"""
        table = MarkdownParser.extract_table_by_header(content, "Public API")

        assert table is not None
        assert table.headers == ["Export", "Type", "Description"]

    def test_find_table_case_insensitive(self) -> None:
        """Test heading search is case-insensitive."""
        content = """
## PUBLIC API

| A | B |
|---|---|
| 1 | 2 |
"""
        table = MarkdownParser.extract_table_by_header(content, "public api")

        assert table is not None
        assert table.headers == ["A", "B"]

    def test_find_table_partial_match(self) -> None:
        """Test heading search matches partial text."""
        content = """
## Active Debt

| ID | Description |
|----|-------------|
| D1 | Some debt   |
"""
        table = MarkdownParser.extract_table_by_header(content, "Debt")

        assert table is not None
        assert table.headers == ["ID", "Description"]

    def test_no_matching_heading(self) -> None:
        """Test returns None when heading not found."""
        content = """
## Other Section

| A | B |
|---|---|
| 1 | 2 |
"""
        table = MarkdownParser.extract_table_by_header(content, "NonExistent")

        assert table is None

    def test_heading_without_table(self) -> None:
        """Test returns None when heading exists but has no table."""
        content = """
## Empty Section

Just some text, no table here.

## Another Section

| A | B |
|---|---|
| 1 | 2 |
"""
        table = MarkdownParser.extract_table_by_header(content, "Empty Section")

        assert table is None


class TestExtractSection:
    """Tests for MarkdownParser.extract_section method."""

    def test_extract_level2_section(self) -> None:
        """Test extracting a level 2 section."""
        content = """
## Purpose

This is the purpose section content.
It spans multiple lines.

## Next Section

Different content here.
"""
        section = MarkdownParser.extract_section(content, "Purpose", level=2)

        assert section is not None
        assert "purpose section content" in section
        assert "multiple lines" in section
        assert "Different content" not in section

    def test_extract_level1_section(self) -> None:
        """Test extracting a level 1 section."""
        content = """
# Main Title

Main content here.

## Subsection

Subsection content.
"""
        section = MarkdownParser.extract_section(content, "Main Title", level=1)

        assert section is not None
        assert "Main content" in section
        # Level 1 section should stop at another level 1, but include level 2 subsections
        # Actually, by our logic, it should stop at any same-or-higher level
        # Level 2 is "lower" than level 1 (more #s = lower importance)
        # So level 1 section continues until another level 1

    def test_section_ends_at_same_level(self) -> None:
        """Test section ends at next heading of same level."""
        content = """
## First

First content.

## Second

Second content.

## Third

Third content.
"""
        section = MarkdownParser.extract_section(content, "Second", level=2)

        assert section is not None
        assert "Second content" in section
        assert "First content" not in section
        assert "Third content" not in section

    def test_section_ends_at_higher_level(self) -> None:
        """Test section ends at higher level heading."""
        content = """
# Chapter 1

## Section A

Section A content.

# Chapter 2

More content.
"""
        section = MarkdownParser.extract_section(content, "Section A", level=2)

        assert section is not None
        assert "Section A content" in section
        assert "Chapter 2" not in section

    def test_section_includes_lower_level_headings(self) -> None:
        """Test section includes subsections (lower level headings)."""
        content = """
## Main Section

Content here.

### Subsection

Subsection content.

#### Deep Section

Deep content.

## Next Main
"""
        section = MarkdownParser.extract_section(content, "Main Section", level=2)

        assert section is not None
        assert "Content here" in section
        assert "Subsection content" in section
        assert "Deep content" in section
        assert "Next Main" not in section

    def test_section_not_found(self) -> None:
        """Test returns None for non-existent section."""
        content = """
## Existing

Content.
"""
        section = MarkdownParser.extract_section(content, "NonExistent", level=2)

        assert section is None

    def test_section_at_end_of_file(self) -> None:
        """Test section at end of file includes all remaining content."""
        content = """
## First

First content.

## Last

Last content here.
This continues to the end.
"""
        section = MarkdownParser.extract_section(content, "Last", level=2)

        assert section is not None
        assert "Last content" in section
        assert "continues to the end" in section

    def test_section_case_insensitive(self) -> None:
        """Test heading matching is case-insensitive."""
        content = """
## Public API

API documentation.
"""
        section = MarkdownParser.extract_section(content, "public api", level=2)

        assert section is not None
        assert "API documentation" in section

    def test_section_level3(self) -> None:
        """Test extracting level 3 sections."""
        content = """
### Option 1

First option.

### Option 2

Second option.
"""
        section = MarkdownParser.extract_section(content, "Option 1", level=3)

        assert section is not None
        assert "First option" in section
        assert "Second option" not in section


class TestExtractAllSections:
    """Tests for MarkdownParser.extract_all_sections method."""

    def test_extract_all_sections(self) -> None:
        """Test extracting all sections from document."""
        content = """
# Title

Intro text.

## Section A

Section A content.

## Section B

Section B content.
"""
        sections = MarkdownParser.extract_all_sections(content)

        assert len(sections) == 3
        assert sections[0].heading == "Title"
        assert sections[0].level == 1
        assert sections[1].heading == "Section A"
        assert sections[1].level == 2
        assert sections[2].heading == "Section B"
        assert sections[2].level == 2

    def test_nested_sections(self) -> None:
        """Test nested sections with different levels."""
        content = """
# Chapter 1

Chapter intro.

## Section 1.1

Section content.

### Subsection 1.1.1

Subsection content.

## Section 1.2

Another section.
"""
        sections = MarkdownParser.extract_all_sections(content)

        assert len(sections) == 4
        assert sections[0].level == 1
        assert sections[1].level == 2
        assert sections[2].level == 3
        assert sections[3].level == 2

        # Check content boundaries
        assert "Subsection content" in sections[2].content
        assert "Another section" not in sections[2].content

    def test_empty_content(self) -> None:
        """Test empty content returns empty list."""
        sections = MarkdownParser.extract_all_sections("")
        assert sections == []

    def test_no_headings(self) -> None:
        """Test content with no headings returns empty list."""
        content = """
Just some text.
No headings here.
"""
        sections = MarkdownParser.extract_all_sections(content)
        assert sections == []

    def test_section_content_trimmed(self) -> None:
        """Test section content is trimmed of leading/trailing whitespace."""
        content = """
## Section

Content here.

"""
        sections = MarkdownParser.extract_all_sections(content)

        assert len(sections) == 1
        assert sections[0].content == "Content here."


class TestExtractCodeBlocks:
    """Tests for MarkdownParser.extract_code_blocks method."""

    def test_simple_code_block(self) -> None:
        """Test extracting a simple code block."""
        content = """
Some text.

```
code here
```

More text.
"""
        blocks = MarkdownParser.extract_code_blocks(content)

        assert len(blocks) == 1
        assert "code here" in blocks[0]

    def test_code_block_with_language(self) -> None:
        """Test code block with language identifier."""
        content = """
```python
def hello():
    print("Hello")
```
"""
        blocks = MarkdownParser.extract_code_blocks(content)

        assert len(blocks) == 1
        assert "def hello():" in blocks[0]

    def test_filter_by_language(self) -> None:
        """Test filtering code blocks by language."""
        content = """
```python
python code
```

```javascript
javascript code
```

```python
more python
```
"""
        python_blocks = MarkdownParser.extract_code_blocks(content, language="python")
        js_blocks = MarkdownParser.extract_code_blocks(content, language="javascript")
        all_blocks = MarkdownParser.extract_code_blocks(content)

        assert len(python_blocks) == 2
        assert len(js_blocks) == 1
        assert len(all_blocks) == 3

    def test_code_block_language_case_insensitive(self) -> None:
        """Test language filtering is case-insensitive."""
        content = """
```Python
code
```

```PYTHON
more code
```
"""
        blocks = MarkdownParser.extract_code_blocks(content, language="python")

        assert len(blocks) == 2

    def test_multiline_code_block(self) -> None:
        """Test multiline code block preserves formatting."""
        content = """
```sql
SELECT *
FROM users
WHERE active = 1;
```
"""
        blocks = MarkdownParser.extract_code_blocks(content, language="sql")

        assert len(blocks) == 1
        assert "SELECT *" in blocks[0]
        assert "FROM users" in blocks[0]
        assert "WHERE active" in blocks[0]

    def test_no_code_blocks(self) -> None:
        """Test content with no code blocks returns empty list."""
        content = """
Just text.
No code blocks.
"""
        blocks = MarkdownParser.extract_code_blocks(content)
        assert blocks == []

    def test_empty_code_block(self) -> None:
        """Test empty code block."""
        content = """
```

```
"""
        blocks = MarkdownParser.extract_code_blocks(content)

        assert len(blocks) == 1
        assert blocks[0].strip() == ""

    def test_code_block_with_backticks_in_content(self) -> None:
        """Test code block containing backticks in content."""
        content = '''
```markdown
Use `inline code` like this.
```
'''
        blocks = MarkdownParser.extract_code_blocks(content, language="markdown")

        assert len(blocks) == 1
        assert "`inline code`" in blocks[0]

    def test_nonexistent_language_filter(self) -> None:
        """Test filtering by non-existent language returns empty list."""
        content = """
```python
code
```
"""
        blocks = MarkdownParser.extract_code_blocks(content, language="rust")
        assert blocks == []


class TestRealWorldTemplates:
    """Tests using real-world template formats from Living Context."""

    def test_snapshot_template_public_api_table(self) -> None:
        """Test parsing Public API table from snapshot template."""
        content = """
# Audio System

> Audio playback and management.

## Purpose

Handles audio playback.

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `example` | function | What it does |
| `AudioConfig` | interface | Configuration options |

## Dependencies

| System | Why |
|--------|-----|
| `other-system` | Reason for dependency |
"""
        # Test extract_tables
        tables = MarkdownParser.extract_tables(content)
        assert len(tables) == 2

        # Test extract_table_by_header
        api_table = MarkdownParser.extract_table_by_header(content, "Public API")
        assert api_table is not None
        assert api_table.headers == ["Export", "Type", "Description"]
        assert len(api_table.rows) == 2
        assert api_table.rows[0]["Export"] == "`example`"

    def test_debt_template(self) -> None:
        """Test parsing debt template format."""
        content = """
# Technical Debt

Tracked shortcuts and known issues.

## Active Debt

| ID | Description | Created | Priority | Impact |
|----|-------------|---------|----------|--------|
| DEBT-001 | Missing tests | 2024-01-15 | high | Quality |
| DEBT-002 | Hardcoded value | 2024-01-16 | low | Maintainability |

## Resolved Debt

| ID | Description | Resolved | Resolution |
|----|-------------|----------|------------|
| DEBT-000 | Example | 2024-01-10 | Fixed it |
"""
        active_table = MarkdownParser.extract_table_by_header(content, "Active Debt")
        resolved_table = MarkdownParser.extract_table_by_header(content, "Resolved Debt")

        assert active_table is not None
        assert len(active_table.rows) == 2
        assert active_table.rows[0]["ID"] == "DEBT-001"
        assert active_table.rows[0]["Priority"] == "high"

        assert resolved_table is not None
        assert len(resolved_table.rows) == 1
        assert resolved_table.rows[0]["Resolution"] == "Fixed it"

    def test_adr_template(self) -> None:
        """Test parsing ADR template format."""
        content = """
# ADR-001: Use SQLite for Storage

- **Status**: accepted
- **Date**: 2024-01-15

## Context

Need a database solution.

## Options Considered

### Option 1: SQLite

Lightweight database.

**Pros:**
- Simple
- No server needed

**Cons:**
- Limited concurrency

### Option 2: PostgreSQL

Full-featured database.

**Pros:**
- Powerful

**Cons:**
- Complex setup

## Decision

We chose SQLite.

## Consequences

### Positive
- Easy setup

### Negative
- Must handle concurrency carefully
"""
        sections = MarkdownParser.extract_all_sections(content)

        # Should find all major sections
        headings = [s.heading for s in sections]
        assert "ADR-001: Use SQLite for Storage" in headings
        assert "Context" in headings
        assert "Options Considered" in headings
        assert "Decision" in headings
        assert "Consequences" in headings

        # Test extracting specific section
        context = MarkdownParser.extract_section(content, "Context", level=2)
        assert context is not None
        assert "Need a database" in context

    def test_decisions_template_index_table(self) -> None:
        """Test parsing decisions index table."""
        content = """
# Decision Log

## Index

| ID | Summary | Status | Date |
|----|---------|--------|------|
| ADR-001 | [Storage](./adr/ADR-001.md) | accepted | 2024-01-15 |
| ADR-002 | [Auth](./adr/ADR-002.md) | proposed | 2024-01-20 |
"""
        index_table = MarkdownParser.extract_table_by_header(content, "Index")

        assert index_table is not None
        assert len(index_table.rows) == 2
        assert index_table.rows[0]["Status"] == "accepted"
        assert "[Storage]" in index_table.rows[0]["Summary"]

    def test_constraints_template(self) -> None:
        """Test parsing constraints template."""
        content = """
# Constraints

Hard rules this system must obey.

## Invariants

Properties that must always be true:

1. **No null values**
   - What: All fields must have defaults
   - Why: Prevents runtime errors

## Boundaries

| Boundary | Limit | Reason |
|----------|-------|--------|
| Max items | 100 | Performance |
| Timeout | 30s | UX |
"""
        # Extract boundaries table
        boundaries = MarkdownParser.extract_table_by_header(content, "Boundaries")
        assert boundaries is not None
        assert len(boundaries.rows) == 2
        assert boundaries.rows[0]["Limit"] == "100"

        # Extract invariants section
        invariants = MarkdownParser.extract_section(content, "Invariants", level=2)
        assert invariants is not None
        assert "No null values" in invariants


class TestEdgeCases:
    """Tests for edge cases and malformed markdown."""

    def test_table_with_mismatched_columns(self) -> None:
        """Test table where data rows have different column counts."""
        content = """
| A | B | C |
|---|---|---|
| 1 | 2 |
| 1 | 2 | 3 | 4 |
"""
        tables = MarkdownParser.extract_tables(content)

        # Should still parse, handling missing/extra columns
        assert len(tables) == 1
        # First row missing C column - should have empty value
        assert tables[0].rows[0].get("C", "") == ""
        # Second row has extra column - should only include A, B, C
        assert tables[0].rows[1]["C"] == "3"

    def test_heading_with_special_characters(self) -> None:
        """Test heading with special regex characters."""
        content = """
## Config (v2.0)

Content here.

## Next
"""
        section = MarkdownParser.extract_section(content, "Config (v2.0)", level=2)

        assert section is not None
        assert "Content here" in section

    def test_deeply_nested_headings(self) -> None:
        """Test all 6 levels of headings."""
        content = """
# L1
## L2
### L3
#### L4
##### L5
###### L6

Content at L6.
"""
        sections = MarkdownParser.extract_all_sections(content)

        assert len(sections) == 6
        assert sections[0].level == 1
        assert sections[5].level == 6
        assert "Content at L6" in sections[5].content

    def test_consecutive_tables(self) -> None:
        """Test two tables separated by blank line."""
        content = """
| A |
|---|
| 1 |

| B |
|---|
| 2 |
"""
        tables = MarkdownParser.extract_tables(content)

        # Should parse as two separate tables
        assert len(tables) == 2
        assert tables[0].headers == ["A"]
        assert tables[0].rows[0]["A"] == "1"
        assert tables[1].headers == ["B"]
        assert tables[1].rows[0]["B"] == "2"

    def test_unicode_content(self) -> None:
        """Test handling of unicode characters."""
        content = """
## Section

| Name | Description |
|------|-------------|
| Test | Contains unicode: <emoji> symbols |
"""
        tables = MarkdownParser.extract_tables(content)

        assert len(tables) == 1
        # Check that unicode is preserved (using a safe unicode character)
        assert "unicode" in tables[0].rows[0]["Description"]
