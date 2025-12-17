"""Base validator classes and models for Living Context validation framework.

Provides core abstractions for implementing validators that check system
documentation and metadata.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass
class ValidationIssue:
    """A single validation issue found during checking.

    Attributes:
        system: System path that was checked (e.g., "src/systems/audio").
        check: Name of the check that identified the issue (e.g., "file_existence").
        severity: Severity level of the issue ("error", "warning", or "info").
        message: Human-readable description of the issue.
        file: Optional relative path to the file containing the issue.
        line: Optional line number within the file.
    """

    system: str
    check: str
    severity: Severity
    message: str
    file: str | None = None
    line: int | None = None


@dataclass
class FixableIssue(ValidationIssue):
    """A validation issue that can be automatically fixed by the doctor command.

    Extends ValidationIssue with fix-related metadata. When a validator detects
    an issue that has a known automated fix, it should return a FixableIssue
    instead of a plain ValidationIssue.

    Attributes:
        fix_id: Unique identifier for the fix type (e.g., "missing_snapshot",
            "stale_graph"). Used to dispatch to the correct fix handler.
        fix_params: Parameters needed to execute the fix. Contents depend on
            the fix_id (e.g., {"template": "snapshot.template.md"} for
            missing_snapshot).
        fix_description: Human-readable description of what the fix will do.
            Shown to users before applying fixes.
    """

    fix_id: str = ""
    fix_params: dict[str, Any] = field(default_factory=dict)
    fix_description: str = ""


@dataclass
class ValidatorResult:
    """Result of a single validator run.

    Attributes:
        name: Name of the validator (e.g., "snapshot-validator").
        status: Overall status ("pass" or "fail").
        issues: List of validation issues found.
        systems_checked: Number of systems checked by this validator.
    """

    name: str
    status: Literal["pass", "fail"]
    issues: list[ValidationIssue]
    systems_checked: int


class BaseValidator(ABC):
    """Abstract base class for all validators.

    Validators implement the validation framework's plugin architecture,
    checking different aspects of the Living Context system documentation.

    Attributes:
        project_root: Root directory of the project being validated.
        db_path: Path to the Living Context knowledge database.
    """

    def __init__(self, project_root: Path, db_path: Path) -> None:
        """Initialize validator.

        Args:
            project_root: Root directory of the project.
            db_path: Path to the Living Context knowledge database.
        """
        self.project_root = project_root
        self.db_path = db_path

    @abstractmethod
    def validate(self) -> ValidatorResult:
        """Run validation checks.

        Must be implemented by subclasses to perform specific validation logic.

        Returns:
            ValidatorResult containing the validation outcome and any issues found.
        """
