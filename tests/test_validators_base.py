"""Tests for cctx.validators.base module."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from cctx.validators import (
    BaseValidator,
    ValidationIssue,
    ValidatorResult,
)


class ConcreteValidator(BaseValidator):
    """Concrete implementation of BaseValidator for testing."""

    def validate(self) -> ValidatorResult:
        """Return a test result."""
        return ValidatorResult(
            name="test-validator",
            status="pass",
            issues=[],
            systems_checked=0,
        )


@pytest.fixture
def temp_project_root() -> Generator[Path, None, None]:
    """Create a temporary project root directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_project_root: Path) -> Path:
    """Create a temporary database path."""
    return temp_project_root / "knowledge.db"


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Test creating ValidationIssue with all fields."""
        issue = ValidationIssue(
            system="src/systems/audio",
            check="file_existence",
            severity="error",
            message="snapshot.md not found",
            file="src/systems/audio/.ctx/snapshot.md",
            line=42,
        )
        assert issue.system == "src/systems/audio"
        assert issue.check == "file_existence"
        assert issue.severity == "error"
        assert issue.message == "snapshot.md not found"
        assert issue.file == "src/systems/audio/.ctx/snapshot.md"
        assert issue.line == 42

    def test_create_with_required_fields_only(self) -> None:
        """Test creating ValidationIssue with only required fields."""
        issue = ValidationIssue(
            system="src/systems/audio",
            check="file_existence",
            severity="error",
            message="snapshot.md not found",
        )
        assert issue.system == "src/systems/audio"
        assert issue.check == "file_existence"
        assert issue.severity == "error"
        assert issue.message == "snapshot.md not found"
        assert issue.file is None
        assert issue.line is None

    def test_severity_types(self) -> None:
        """Test all valid severity levels."""
        for severity in ["error", "warning", "info"]:
            issue = ValidationIssue(
                system="test",
                check="test",
                severity=severity,  # type: ignore
                message="test",
            )
            assert issue.severity == severity


class TestValidatorResult:
    """Tests for ValidatorResult dataclass."""

    def test_create_pass_result(self) -> None:
        """Test creating a passing validator result."""
        result = ValidatorResult(
            name="snapshot-validator",
            status="pass",
            issues=[],
            systems_checked=5,
        )
        assert result.name == "snapshot-validator"
        assert result.status == "pass"
        assert result.issues == []
        assert result.systems_checked == 5

    def test_create_fail_result_with_issues(self) -> None:
        """Test creating a failing validator result with issues."""
        issues = [
            ValidationIssue(
                system="src/systems/audio",
                check="file_existence",
                severity="error",
                message="snapshot.md not found",
            ),
            ValidationIssue(
                system="src/systems/video",
                check="file_existence",
                severity="warning",
                message="constraints.md missing",
                file="src/systems/video/.ctx",
            ),
        ]
        result = ValidatorResult(
            name="snapshot-validator",
            status="fail",
            issues=issues,
            systems_checked=2,
        )
        assert result.name == "snapshot-validator"
        assert result.status == "fail"
        assert len(result.issues) == 2
        assert result.issues[0].severity == "error"
        assert result.issues[1].severity == "warning"
        assert result.systems_checked == 2

    def test_validator_result_status_types(self) -> None:
        """Test both valid status values."""
        for status in ["pass", "fail"]:
            result = ValidatorResult(
                name="test",
                status=status,  # type: ignore
                issues=[],
                systems_checked=0,
            )
            assert result.status == status


class TestBaseValidator:
    """Tests for BaseValidator abstract base class."""

    def test_init_with_path_objects(self, temp_project_root: Path, temp_db_path: Path) -> None:
        """Test initializing validator with Path objects."""
        validator = ConcreteValidator(temp_project_root, temp_db_path)
        assert validator.project_root == temp_project_root
        assert validator.db_path == temp_db_path

    def test_init_stores_paths(self, temp_project_root: Path, temp_db_path: Path) -> None:
        """Test that paths are stored as Path objects."""
        validator = ConcreteValidator(temp_project_root, temp_db_path)
        assert isinstance(validator.project_root, Path)
        assert isinstance(validator.db_path, Path)

    def test_validate_method_callable(self, temp_project_root: Path, temp_db_path: Path) -> None:
        """Test that validate method can be called."""
        validator = ConcreteValidator(temp_project_root, temp_db_path)
        result = validator.validate()
        assert isinstance(result, ValidatorResult)

    def test_validate_returns_correct_type(
        self, temp_project_root: Path, temp_db_path: Path
    ) -> None:
        """Test that validate returns ValidatorResult."""
        validator = ConcreteValidator(temp_project_root, temp_db_path)
        result = validator.validate()
        assert result.name == "test-validator"
        assert result.status == "pass"
        assert result.issues == []
        assert result.systems_checked == 0

    def test_cannot_instantiate_abstract_base(
        self, temp_project_root: Path, temp_db_path: Path
    ) -> None:
        """Test that BaseValidator cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseValidator(temp_project_root, temp_db_path)  # type: ignore

    def test_multiple_validator_instances(
        self, temp_project_root: Path, temp_db_path: Path
    ) -> None:
        """Test creating multiple validator instances."""
        validator1 = ConcreteValidator(temp_project_root, temp_db_path)
        validator2 = ConcreteValidator(temp_project_root, temp_db_path)
        assert validator1 is not validator2
        assert validator1.project_root == validator2.project_root
        assert validator1.db_path == validator2.db_path
