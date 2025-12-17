"""Validation framework for Living Context systems.

Provides validators for checking documentation completeness, consistency,
and correctness across Living Context systems.
"""

from __future__ import annotations

from cctx.validators.adr_validator import AdrValidator
from cctx.validators.base import (
    BaseValidator,
    FixableIssue,
    Severity,
    ValidationIssue,
    ValidatorResult,
)
from cctx.validators.debt_auditor import DebtAuditor
from cctx.validators.freshness_checker import FreshnessChecker
from cctx.validators.runner import AggregatedResult, ValidationRunner
from cctx.validators.snapshot_validator import SnapshotValidator

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
