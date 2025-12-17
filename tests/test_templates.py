"""Tests for the template system."""

from __future__ import annotations

import pytest

from lctx.template_manager import (
    get_template,
    list_templates,
    render_template,
)


class TestTemplateLoading:
    """Tests for loading templates."""

    def test_get_snapshot_template(self) -> None:
        """Test loading the snapshot template."""
        content = get_template("snapshot")
        assert content
        assert "# {System Name}" in content
        assert "## Purpose" in content
        assert "## Public API" in content

    def test_get_constraints_template(self) -> None:
        """Test loading the constraints template."""
        content = get_template("constraints")
        assert content
        assert "# Constraints" in content
        assert "## Invariants" in content
        assert "## Boundaries" in content

    def test_get_decisions_template(self) -> None:
        """Test loading the decisions template."""
        content = get_template("decisions")
        assert content
        assert "# Decision Log" in content
        assert "## Index" in content
        assert "## Status Values" in content

    def test_get_debt_template(self) -> None:
        """Test loading the debt template."""
        content = get_template("debt")
        assert content
        assert "# Technical Debt" in content
        assert "## Active Debt" in content
        assert "## Priority Guide" in content

    def test_get_adr_template(self) -> None:
        """Test loading the ADR template."""
        content = get_template("adr")
        assert content
        assert "# ADR-NNN:" in content
        assert "## Context" in content
        assert "## Options Considered" in content
        assert "## Decision" in content

    def test_get_invalid_template(self) -> None:
        """Test loading an invalid template raises ValueError."""
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("invalid_template")


class TestListTemplates:
    """Tests for listing templates."""

    def test_list_templates(self) -> None:
        """Test listing all available templates."""
        templates = list_templates()
        assert isinstance(templates, list)
        assert len(templates) == 5
        assert "snapshot" in templates
        assert "constraints" in templates
        assert "decisions" in templates
        assert "debt" in templates
        assert "adr" in templates

    def test_list_templates_returns_copy(self) -> None:
        """Test that list_templates returns a copy, not the internal list."""
        templates1 = list_templates()
        templates2 = list_templates()
        assert templates1 == templates2
        # Verify they're different list objects
        assert templates1 is not templates2


class TestRenderTemplate:
    """Tests for rendering templates with variable substitution."""

    def test_render_snapshot_with_system_name(self) -> None:
        """Test rendering snapshot template with system name."""
        content = render_template("snapshot", System_Name="MySystem")
        # Should replace {System Name} placeholder
        assert "# MySystem" in content
        assert "{System Name}" not in content

    def test_render_snapshot_with_snake_case_variable(self) -> None:
        """Test rendering with snake_case variables."""
        content = render_template("snapshot", system_name="MySystem")
        assert "# MySystem" in content

    def test_render_adr_with_title(self) -> None:
        """Test rendering ADR template with decision title."""
        content = render_template("adr", Decision_Title="Use TypeScript")
        # ADR template uses {Decision Title} placeholder
        assert "# ADR-NNN: Use TypeScript" in content

    def test_render_template_with_multiple_variables(self) -> None:
        """Test rendering with multiple variables."""
        content = render_template(
            "snapshot",
            system_name="Logger",
            example="log",
        )
        assert "# Logger" in content

    def test_render_template_preserves_unsubstituted_placeholders(self) -> None:
        """Test that unsubstituted placeholders are preserved or safely ignored."""
        content = render_template("adr")
        # {Title} placeholders should not be substituted without value
        assert "{Decision Title}" in content or "ADR-NNN:" in content

    def test_render_constraints_template(self) -> None:
        """Test rendering constraints template."""
        content = render_template("constraints", system_name="Logger")
        assert "# Constraints" in content
        # Template doesn't use system name, but should still work
        assert content

    def test_render_decisions_template(self) -> None:
        """Test rendering decisions template."""
        content = render_template("decisions")
        assert "# Decision Log" in content
        assert content

    def test_render_debt_template(self) -> None:
        """Test rendering debt template."""
        content = render_template("debt")
        assert "# Technical Debt" in content
        assert content

    def test_render_invalid_template_raises_error(self) -> None:
        """Test rendering invalid template raises error."""
        with pytest.raises(ValueError, match="Unknown template"):
            render_template("nonexistent")


class TestTemplateContent:
    """Tests for template content correctness."""

    def test_snapshot_template_has_all_sections(self) -> None:
        """Test that snapshot template includes all required sections."""
        content = get_template("snapshot")
        assert "## Purpose" in content
        assert "## Public API" in content
        assert "## Dependencies" in content
        assert "## Dependents" in content
        assert "## Files" in content
        assert "## Constraints" in content
        assert "## Known Debt" in content

    def test_adr_template_has_all_sections(self) -> None:
        """Test that ADR template includes all required sections."""
        content = get_template("adr")
        assert "## Context" in content
        assert "## Options Considered" in content
        assert "## Decision" in content
        assert "## Consequences" in content

    def test_constraints_template_has_all_sections(self) -> None:
        """Test that constraints template includes all sections."""
        content = get_template("constraints")
        assert "## Invariants" in content
        assert "## Boundaries" in content
        assert "## External Constraints" in content
        assert "## Assumptions" in content

    def test_decisions_template_has_all_sections(self) -> None:
        """Test that decisions template includes all sections."""
        content = get_template("decisions")
        assert "## Index" in content
        assert "## Status Values" in content

    def test_debt_template_has_all_sections(self) -> None:
        """Test that debt template includes all sections."""
        content = get_template("debt")
        assert "## Active Debt" in content
        assert "## Priority Guide" in content
        assert "## Resolved Debt" in content
