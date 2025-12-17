"""Template management for Living Context system documentation."""

from __future__ import annotations

import importlib.resources
from string import Template

# Template filenames in the templates package
TEMPLATE_FILES = [
    "snapshot.template.md",
    "constraints.template.md",
    "decisions.template.md",
    "debt.template.md",
    "adr.template.md",
]

TEMPLATE_NAMES = [
    "snapshot",
    "constraints",
    "decisions",
    "debt",
    "adr",
]


def _get_template_path(name: str) -> str:
    """Get the filename for a template by name.

    Args:
        name: Template name (without .template.md extension)

    Returns:
        The full template filename

    Raises:
        ValueError: If template name is invalid
    """
    if name not in TEMPLATE_NAMES:
        raise ValueError(f"Unknown template: {name}")
    return f"{name}.template.md"


def get_template(name: str) -> str:
    """Load a template file from package resources.

    Args:
        name: Template name (e.g., 'snapshot', 'adr')

    Returns:
        The template content as a string

    Raises:
        ValueError: If template name is invalid
        FileNotFoundError: If template file cannot be loaded
    """
    template_file = _get_template_path(name)

    try:
        # Load the template file from the package resources
        if hasattr(importlib.resources, "files"):
            # Python 3.9+
            templates_module = importlib.resources.files("lctx").joinpath("templates")
            template_path = templates_module.joinpath(template_file)
            content = template_path.read_text(encoding="utf-8")
        else:
            # Fallback for older Python versions
            import pkgutil

            raw_content = pkgutil.get_data("lctx.templates", template_file)
            if raw_content is None:
                raise FileNotFoundError(f"Cannot load template: {template_file}")
            content = raw_content.decode("utf-8")

        return content
    except (FileNotFoundError, AttributeError, TypeError) as e:
        raise FileNotFoundError(f"Cannot load template '{name}': {e}") from e


def list_templates() -> list[str]:
    """List all available templates.

    Returns:
        List of template names (without extensions)
    """
    return TEMPLATE_NAMES.copy()


def render_template(name: str, **variables: str) -> str:
    """Render a template with variable substitution.

    Uses string.Template for simple $var substitution.
    Also supports {Variable Name} style placeholders for compatibility
    with the existing template format.

    Args:
        name: Template name (e.g., 'snapshot', 'adr')
        **variables: Variables to substitute in the template
            (both {Variable} and $var syntax supported)

    Returns:
        The rendered template with variables substituted

    Raises:
        ValueError: If template name is invalid
        FileNotFoundError: If template file cannot be loaded
    """
    content = get_template(name)

    # Build a dict that maps placeholder names to values for {Variable Name} style
    format_vars: dict[str, str] = {}
    for key, value in variables.items():
        # Convert keys like system_name to both "system_name" and "System Name"
        format_vars[key] = value
        # Also add title-cased version for {System Name} style
        title_key = " ".join(word.capitalize() for word in key.split("_"))
        format_vars[title_key] = value

    # Use a custom formatter that ignores missing keys
    class SafeFormatter(dict[str, str]):
        """A dict subclass that returns the key itself for missing keys."""

        def __missing__(self, key: str) -> str:
            """Return the key itself when it's not found."""
            return "{" + key + "}"

    safe_format_vars: dict[str, str] = SafeFormatter(format_vars)
    content = content.format_map(safe_format_vars)

    # Then, handle $var style substitution using string.Template
    template_vars: dict[str, str] = {}
    for key, value in variables.items():
        template_vars[key] = value

    template = Template(content)
    content = template.safe_substitute(template_vars)

    return content
