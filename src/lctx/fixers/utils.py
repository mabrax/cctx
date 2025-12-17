"""Utility functions for fixers."""

from __future__ import annotations

from pathlib import Path


def derive_system_name(system_path: Path) -> str:
    """Derive a human-readable system name from the path.

    Converts directory names like "audio-manager" to "Audio Manager".

    Args:
        system_path: Path to the system directory.

    Returns:
        Human-readable system name.
    """
    dir_name = system_path.name
    name = dir_name.replace("-", " ").replace("_", " ")
    return name.title()
