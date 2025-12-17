"""Validation framework for Living Context systems.

Provides validators for checking documentation completeness, consistency,
and correctness across Living Context systems.
"""

from __future__ import annotations

from lctx.validators.adr_validator import AdrValidator
from lctx.validators.base import (
    BaseValidator,
    FixableIssue,
    Severity,
    ValidationIssue,
    ValidatorResult,
)
from lctx.validators.debt_auditor import DebtAuditor
from lctx.validators.freshness_checker import FreshnessChecker
from lctx.validators.runner import AggregatedResult, ValidationRunner
from lctx.validators.snapshot_validator import SnapshotValidator

__all__ = [
    # Base types
    "BaseValidator",
    "FixableIssue",
    "Severity",
    "ValidationIssue",
    "ValidatorResult",
    # Validators
    "AdrValidator",
    "DebtAuditor",
    "FreshnessChecker",
    "SnapshotValidator",
    # Runner
    "AggregatedResult",
    "ValidationRunner",
]
