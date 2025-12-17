"""Fixer framework for automatically resolving Living Context issues.

Provides fixers that can automatically fix validation issues detected
by the validation framework.
"""

from __future__ import annotations

from cctx.fixers.adr_fixer import AdrFixer
from cctx.fixers.base import BaseFixer, FixResult
from cctx.fixers.graph_fixer import GraphFixer
from cctx.fixers.registry import (
    FixerRegistry,
    get_global_registry,
)
from cctx.fixers.scaffolding_fixer import (
    MissingCtxDirFixer,
    MissingTemplateFileFixer,
)
from cctx.fixers.snapshot_fixer import SnapshotFixer

__all__ = [
    # Base types
    "BaseFixer",
    "FixResult",
    # Registry
    "FixerRegistry",
    "get_global_registry",
    # Fixers
    "AdrFixer",
    "GraphFixer",
    "MissingCtxDirFixer",
    "MissingTemplateFileFixer",
    "SnapshotFixer",
]
