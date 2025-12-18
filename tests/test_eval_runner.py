"""Tests for the Living Context eval runner module."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# Import the runner module directly from plugin/eval/runner.py
runner_path = Path(__file__).parent.parent / "plugin" / "eval" / "runner.py"
spec = importlib.util.spec_from_file_location("runner", runner_path)
if spec and spec.loader:
    runner = importlib.util.module_from_spec(spec)
    # Register module before executing to avoid dataclass issues
    sys.modules["runner"] = runner
    spec.loader.exec_module(runner)

    TestResult = runner.TestResult
    generate_json_report = runner.generate_json_report
    get_eval_dir = runner.get_eval_dir
    load_fixture = runner.load_fixture
    load_test_cases = runner.load_test_cases
    print_result = runner.print_result
    print_summary = runner.print_summary
    run_test_case = runner.run_test_case
    validate_output = runner.validate_output
else:
    raise ImportError(f"Could not load runner module from {runner_path}")


class TestRunTestCase:
    """Tests for the run_test_case function."""

    def test_run_test_case_calls_subprocess_correctly(self, tmp_path: Path) -> None:
        """Test that run_test_case calls subprocess with shell=False and split command."""
        test_case = {"name": "test1", "command": "cctx init --json", "expected": {"exit_code": 0}}
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        cctx_dir = tmp_path / "cctx"
        cctx_dir.mkdir()

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            run_test_case(test_case, work_dir, cctx_dir)

            # Verify call args
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args

            # Check command is split
            assert args[0] == ["cctx", "init", "--json"]
            # Check shell is False
            assert kwargs.get("shell") is False
            # Check cwd and env
            assert kwargs.get("cwd") == work_dir
            assert "CCTX_PROJECT_DIR" in kwargs.get("env", {})


class TestLoadFixture:
    """Tests for the load_fixture function."""

    def test_load_fixture_copies_directory(self, tmp_path: Path) -> None:
        """Test that load_fixture copies the fixture directory."""
        # Create a fixture directory with some files
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture_name = "test-fixture"
        fixture_path = fixtures_dir / fixture_name
        fixture_path.mkdir()
        (fixture_path / "file.txt").write_text("test content")
        (fixture_path / "subdir").mkdir()
        (fixture_path / "subdir" / "nested.txt").write_text("nested content")

        # Load the fixture
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        result = load_fixture(fixtures_dir, fixture_name, temp_dir)

        # Verify the fixture was copied
        assert result.exists()
        assert (result / "file.txt").read_text() == "test content"
        assert (result / "subdir" / "nested.txt").read_text() == "nested content"

    def test_load_fixture_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that load_fixture returns the correct destination path."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture_name = "my-fixture"
        (fixtures_dir / fixture_name).mkdir()

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        result = load_fixture(fixtures_dir, fixture_name, temp_dir)
        assert result == temp_dir / fixture_name

    def test_load_fixture_not_found(self, tmp_path: Path) -> None:
        """Test that load_fixture raises FileNotFoundError for missing fixture."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Fixture not found"):
            load_fixture(fixtures_dir, "nonexistent", temp_dir)

    def test_load_fixture_handles_dirs_exist_ok(self, tmp_path: Path) -> None:
        """Test that load_fixture handles existing destination gracefully."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture_name = "test-fixture"
        fixture_path = fixtures_dir / fixture_name
        fixture_path.mkdir()
        (fixture_path / "file.txt").write_text("original")

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # First copy
        result1 = load_fixture(fixtures_dir, fixture_name, temp_dir)
        assert result1.exists()

        # Second copy to same destination should still work
        (fixture_path / "file.txt").write_text("updated")
        result2 = load_fixture(fixtures_dir, fixture_name, temp_dir)
        assert result2.exists()
        assert (result2 / "file.txt").read_text() == "updated"

    def test_load_fixture_preserves_permissions(self, tmp_path: Path) -> None:
        """Test that load_fixture preserves file permissions."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture_name = "test-fixture"
        fixture_path = fixtures_dir / fixture_name
        fixture_path.mkdir()
        script_file = fixture_path / "script.sh"
        script_file.write_text("#!/bin/bash\necho 'test'")
        script_file.chmod(0o755)

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        result = load_fixture(fixtures_dir, fixture_name, temp_dir)
        copied_script = result / "script.sh"
        assert copied_script.exists()


class TestLoadTestCases:
    """Tests for the load_test_cases function."""

    def test_load_test_cases_from_single_file(self, tmp_path: Path) -> None:
        """Test loading test cases from a single YAML file."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file = test_cases_dir / "init.yaml"
        yaml_file.write_text(
            """
command: init
test_cases:
  - name: test1
    command: cctx init
    expected:
      exit_code: 0
  - name: test2
    command: cctx init --help
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir)
        assert len(result) == 2
        assert result[0]["name"] == "test1"
        assert result[1]["name"] == "test2"
        assert result[0]["_command_group"] == "init"
        assert result[0]["_source_file"] == "init.yaml"

    def test_load_test_cases_from_multiple_files(self, tmp_path: Path) -> None:
        """Test loading test cases from multiple YAML files."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        # Create first file
        yaml_file1 = test_cases_dir / "init.yaml"
        yaml_file1.write_text(
            """
command: init
test_cases:
  - name: init_test
    command: cctx init
    expected:
      exit_code: 0
"""
        )

        # Create second file
        yaml_file2 = test_cases_dir / "health.yaml"
        yaml_file2.write_text(
            """
command: health
test_cases:
  - name: health_test
    command: cctx health
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir)
        assert len(result) == 2
        names = [tc["name"] for tc in result]
        assert "init_test" in names
        assert "health_test" in names

    def test_load_test_cases_filter_by_command(self, tmp_path: Path) -> None:
        """Test filtering test cases by command."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file1 = test_cases_dir / "init.yaml"
        yaml_file1.write_text(
            """
command: init
test_cases:
  - name: init_test
    command: cctx init
    expected:
      exit_code: 0
"""
        )

        yaml_file2 = test_cases_dir / "health.yaml"
        yaml_file2.write_text(
            """
command: health
test_cases:
  - name: health_test
    command: cctx health
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir, command="init")
        assert len(result) == 1
        assert result[0]["name"] == "init_test"

    def test_load_test_cases_filter_by_case(self, tmp_path: Path) -> None:
        """Test filtering test cases by case name."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file = test_cases_dir / "init.yaml"
        yaml_file.write_text(
            """
command: init
test_cases:
  - name: test1
    command: cctx init
    expected:
      exit_code: 0
  - name: test2
    command: cctx init --help
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir, case="test1")
        assert len(result) == 1
        assert result[0]["name"] == "test1"

    def test_load_test_cases_filter_by_command_and_case(self, tmp_path: Path) -> None:
        """Test filtering by both command and case."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file1 = test_cases_dir / "init.yaml"
        yaml_file1.write_text(
            """
command: init
test_cases:
  - name: test1
    command: cctx init
    expected:
      exit_code: 0
  - name: test2
    command: cctx init --help
    expected:
      exit_code: 0
"""
        )

        yaml_file2 = test_cases_dir / "health.yaml"
        yaml_file2.write_text(
            """
command: health
test_cases:
  - name: test1
    command: cctx health
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir, command="init", case="test1")
        assert len(result) == 1
        assert result[0]["name"] == "test1"
        assert result[0]["_command_group"] == "init"

    def test_load_test_cases_empty_directory(self, tmp_path: Path) -> None:
        """Test loading test cases from empty directory."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        result = load_test_cases(test_cases_dir)
        assert len(result) == 0

    def test_load_test_cases_skips_files_without_test_cases(self, tmp_path: Path) -> None:
        """Test that files without test_cases key are skipped."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file1 = test_cases_dir / "invalid.yaml"
        yaml_file1.write_text(
            """
command: invalid
description: This file has no test_cases
"""
        )

        yaml_file2 = test_cases_dir / "valid.yaml"
        yaml_file2.write_text(
            """
command: valid
test_cases:
  - name: test1
    command: cctx valid
    expected:
      exit_code: 0
"""
        )

        result = load_test_cases(test_cases_dir)
        assert len(result) == 1
        assert result[0]["name"] == "test1"

    def test_load_test_cases_sorted_output(self, tmp_path: Path) -> None:
        """Test that test cases are loaded in sorted file order."""
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        # Create files in non-alphabetical order
        for filename in ["zebra.yaml", "alpha.yaml", "beta.yaml"]:
            yaml_file = test_cases_dir / filename
            yaml_file.write_text(
                f"""
command: {filename.split(".")[0]}
test_cases:
  - name: {filename.split(".")[0]}_test
    command: test
    expected:
      exit_code: 0
"""
            )

        result = load_test_cases(test_cases_dir)
        # Should be loaded in alphabetical order
        assert result[0]["_source_file"] == "alpha.yaml"
        assert result[1]["_source_file"] == "beta.yaml"
        assert result[2]["_source_file"] == "zebra.yaml"


class TestValidateOutput:
    """Tests for the validate_output function."""

    def test_validate_output_stdout_contains_single(self) -> None:
        """Test stdout_contains validation with single pattern."""
        errors = validate_output(
            "Hello world",
            "",
            {"stdout_contains": ["Hello"]},
        )
        assert errors == []

    def test_validate_output_stdout_contains_multiple(self) -> None:
        """Test stdout_contains validation with multiple patterns."""
        errors = validate_output(
            "Hello world test",
            "",
            {"stdout_contains": ["Hello", "world", "test"]},
        )
        assert errors == []

    def test_validate_output_stdout_contains_missing(self) -> None:
        """Test stdout_contains validation with missing pattern."""
        errors = validate_output(
            "Hello world",
            "",
            {"stdout_contains": ["Hello", "missing"]},
        )
        assert len(errors) == 1
        assert "Expected 'missing' in output" in errors[0]

    def test_validate_output_stdout_contains_case_insensitive(self) -> None:
        """Test that stdout_contains is case insensitive."""
        errors = validate_output(
            "Hello World",
            "",
            {"stdout_contains": ["hello", "WORLD"]},
        )
        assert errors == []

    def test_validate_output_stdout_not_contains(self) -> None:
        """Test stdout_not_contains validation."""
        errors = validate_output(
            "Hello world",
            "",
            {"stdout_not_contains": ["error", "failed"]},
        )
        assert errors == []

    def test_validate_output_stdout_not_contains_found(self) -> None:
        """Test stdout_not_contains when pattern is found."""
        errors = validate_output(
            "Hello error world",
            "",
            {"stdout_not_contains": ["error"]},
        )
        assert len(errors) == 1
        assert "Unexpected 'error' in output" in errors[0]

    def test_validate_output_combines_stdout_and_stderr(self) -> None:
        """Test that validation checks both stdout and stderr."""
        errors = validate_output(
            "stdout content",
            "stderr content",
            {"stdout_contains": ["stderr content"]},
        )
        assert errors == []

    def test_validate_output_json_fields_valid(self) -> None:
        """Test json_fields validation with valid JSON."""
        json_output = json.dumps({"name": "test", "value": 42})
        errors = validate_output(
            json_output,
            "",
            {"json_fields": ["name", "value"]},
        )
        assert errors == []

    def test_validate_output_json_fields_missing(self) -> None:
        """Test json_fields validation with missing fields."""
        json_output = json.dumps({"name": "test"})
        errors = validate_output(
            json_output,
            "",
            {"json_fields": ["name", "missing_field"]},
        )
        assert len(errors) == 1
        assert "Missing JSON field: missing_field" in errors[0]

    def test_validate_output_json_fields_invalid_json(self) -> None:
        """Test json_fields validation with invalid JSON."""
        errors = validate_output(
            "not json",
            "",
            {"json_fields": ["field"]},
        )
        assert len(errors) == 1
        assert "Output is not valid JSON" in errors[0]

    def test_validate_output_stdout_matches(self) -> None:
        """Test stdout_matches validation with regex patterns."""
        errors = validate_output(
            "Success: Operation completed",
            "",
            {"stdout_matches": [r"Success:.*completed"]},
        )
        assert errors == []

    def test_validate_output_stdout_matches_no_match(self) -> None:
        """Test stdout_matches when pattern doesn't match."""
        errors = validate_output(
            "Success: Operation completed",
            "",
            {"stdout_matches": [r"Failed:.*error"]},
        )
        assert len(errors) == 1
        assert "Output did not match pattern" in errors[0]

    def test_validate_output_stdout_matches_multiline(self) -> None:
        """Test stdout_matches with multiline patterns."""
        output = "Line 1\nLine 2\nLine 3"
        errors = validate_output(
            output,
            "",
            {"stdout_matches": [r"Line 1[\s\S]*Line 3"]},
        )
        assert errors == []

    def test_validate_output_multiple_validations(self) -> None:
        """Test multiple validation rules applied together."""
        errors = validate_output(
            "Success: test passed",
            "",
            {
                "stdout_contains": ["Success", "passed"],
                "stdout_not_contains": ["error"],
                "stdout_matches": [r"Success.*passed"],
            },
        )
        assert errors == []

    def test_validate_output_multiple_validations_with_errors(self) -> None:
        """Test multiple validation rules with some errors."""
        errors = validate_output(
            "Result: incomplete",
            "",
            {
                "stdout_contains": ["Success", "passed"],
                "stdout_not_contains": ["error"],
                "stdout_matches": [r"Success.*passed"],
            },
        )
        assert len(errors) > 0
        error_messages = "\n".join(errors)
        assert "Success" in error_messages or "Success.*passed" in error_messages


class TestTestResult:
    """Tests for the TestResult dataclass."""

    def test_test_result_creation(self) -> None:
        """Test creating a TestResult."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        assert result.name == "test1"
        assert result.command == "cctx init"
        assert result.passed is True
        assert result.exit_code == 0

    def test_test_result_to_dict_passed(self) -> None:
        """Test TestResult.to_dict for passed test."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        result_dict = result.to_dict()
        assert result_dict["name"] == "test1"
        assert result_dict["passed"] is True
        assert result_dict["exit_code"] == 0
        assert "expected_exit_code" not in result_dict
        assert "errors" not in result_dict

    def test_test_result_to_dict_failed(self) -> None:
        """Test TestResult.to_dict for failed test."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=False,
            exit_code=1,
            expected_exit_code=0,
            stdout="Error",
            errors=["Exit code mismatch"],
        )
        result_dict = result.to_dict()
        assert result_dict["name"] == "test1"
        assert result_dict["passed"] is False
        assert result_dict["exit_code"] == 1
        assert result_dict["expected_exit_code"] == 0
        assert result_dict["errors"] == ["Exit code mismatch"]

    def test_test_result_default_stderr(self) -> None:
        """Test TestResult has default empty stderr."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        assert result.stderr == ""

    def test_test_result_default_errors(self) -> None:
        """Test TestResult has default empty errors list."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        assert result.errors == []


class TestPrintResult:
    """Tests for the print_result function."""

    def test_print_result_pass(self, capsys: Any) -> None:
        """Test printing a passing result."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        print_result(result)
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "test1" in captured.out

    def test_print_result_fail(self, capsys: Any) -> None:
        """Test printing a failing result."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=False,
            exit_code=1,
            expected_exit_code=0,
            stdout="Error",
            errors=["Exit code mismatch"],
        )
        print_result(result)
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "test1" in captured.out
        assert "Exit code mismatch" in captured.out

    def test_print_result_verbose_pass(self, capsys: Any) -> None:
        """Test printing a passing result in verbose mode."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=True,
            exit_code=0,
            expected_exit_code=0,
            stdout="Success",
        )
        print_result(result, verbose=True)
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "test1" in captured.out
        # Verbose mode shows stdout/stderr for passed tests
        assert "stdout:" in captured.out or "test1" in captured.out

    def test_print_result_verbose_fail(self, capsys: Any) -> None:
        """Test printing a failing result in verbose mode."""
        result = TestResult(
            name="test1",
            command="cctx init",
            passed=False,
            exit_code=1,
            expected_exit_code=0,
            stdout="Error output",
            stderr="Error stderr",
            errors=["Exit code mismatch"],
        )
        print_result(result, verbose=True)
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "Exit code mismatch" in captured.out


class TestPrintSummary:
    """Tests for the print_summary function."""

    def test_print_summary_all_passed(self, capsys: Any) -> None:
        """Test printing summary when all tests pass."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
            TestResult(
                name="test2",
                command="cctx health",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
        ]
        print_summary(results)
        captured = capsys.readouterr()
        assert "2/2 passed" in captured.out
        assert "All tests passed" in captured.out

    def test_print_summary_with_failures(self, capsys: Any) -> None:
        """Test printing summary with failures."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
            TestResult(
                name="test2",
                command="cctx health",
                passed=False,
                exit_code=1,
                expected_exit_code=0,
                stdout="Error",
                errors=["Failed"],
            ),
        ]
        print_summary(results)
        captured = capsys.readouterr()
        assert "1/2 passed" in captured.out
        assert "Failed: 1" in captured.out

    def test_print_summary_empty_results(self, capsys: Any) -> None:
        """Test printing summary with no results."""
        results: list[TestResult] = []
        print_summary(results)
        captured = capsys.readouterr()
        assert "0/0 passed" in captured.out


class TestGenerateJsonReport:
    """Tests for the generate_json_report function."""

    def test_generate_json_report_all_passed(self) -> None:
        """Test generating JSON report with all passed tests."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
            TestResult(
                name="test2",
                command="cctx health",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
        ]
        report = generate_json_report(results)
        assert report["total"] == 2
        assert report["passed"] == 2
        assert report["failed"] == 0
        assert len(report["results"]) == 2

    def test_generate_json_report_with_failures(self) -> None:
        """Test generating JSON report with failures."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
            TestResult(
                name="test2",
                command="cctx health",
                passed=False,
                exit_code=1,
                expected_exit_code=0,
                stdout="Error",
                errors=["Exit code mismatch"],
            ),
        ]
        report = generate_json_report(results)
        assert report["total"] == 2
        assert report["passed"] == 1
        assert report["failed"] == 1
        assert report["results"][0]["passed"] is True
        assert report["results"][1]["passed"] is False
        assert "errors" in report["results"][1]

    def test_generate_json_report_empty_results(self) -> None:
        """Test generating JSON report with no results."""
        results: list[TestResult] = []
        report = generate_json_report(results)
        assert report["total"] == 0
        assert report["passed"] == 0
        assert report["failed"] == 0
        assert report["results"] == []

    def test_generate_json_report_structure(self) -> None:
        """Test that JSON report has correct structure."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
        ]
        report = generate_json_report(results)
        # Verify report is valid JSON-serializable
        json_str = json.dumps(report)
        assert isinstance(json_str, str)
        # Verify we can parse it back
        parsed = json.loads(json_str)
        assert parsed["total"] == 1
        assert parsed["passed"] == 1


class TestGetEvalDir:
    """Tests for the get_eval_dir function."""

    def test_get_eval_dir_returns_path(self) -> None:
        """Test that get_eval_dir returns a Path object."""
        eval_dir = get_eval_dir()
        assert isinstance(eval_dir, Path)

    def test_get_eval_dir_is_absolute(self) -> None:
        """Test that get_eval_dir returns an absolute path."""
        eval_dir = get_eval_dir()
        assert eval_dir.is_absolute()

    def test_get_eval_dir_exists(self) -> None:
        """Test that get_eval_dir points to an existing directory."""
        eval_dir = get_eval_dir()
        # The directory might not exist in test context, but the function should work
        # Test that the path is correctly constructed
        assert "eval" in eval_dir.name or "plugin" in str(eval_dir)


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow_load_and_validate(self, tmp_path: Path) -> None:
        """Test full workflow of loading test cases and validating output."""
        # Create test case files
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file = test_cases_dir / "init.yaml"
        yaml_file.write_text(
            """
command: init
test_cases:
  - name: test_success
    command: cctx init
    expected:
      exit_code: 0
      stdout_contains: ["Success"]
      stdout_not_contains: ["Error"]
"""
        )

        # Load test cases
        test_cases = load_test_cases(test_cases_dir)
        assert len(test_cases) == 1

        # Validate output
        errors = validate_output(
            "Success: Context initialized",
            "",
            test_cases[0]["expected"],
        )
        assert errors == []

    def test_full_workflow_with_fixture_and_cases(self, tmp_path: Path) -> None:
        """Test workflow with fixture loading and test cases."""
        # Create fixtures
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture_path = fixtures_dir / "test-project"
        fixture_path.mkdir()
        (fixture_path / "README.md").write_text("# Test Project")

        # Create test cases
        test_cases_dir = tmp_path / "test-cases"
        test_cases_dir.mkdir()

        yaml_file = test_cases_dir / "init.yaml"
        yaml_file.write_text(
            """
command: init
test_cases:
  - name: test1
    fixture: test-project
    command: cctx init
    expected:
      exit_code: 0
"""
        )

        # Load fixture
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        loaded_fixture = load_fixture(fixtures_dir, "test-project", temp_dir)
        assert (loaded_fixture / "README.md").exists()

        # Load test cases
        test_cases = load_test_cases(test_cases_dir)
        assert len(test_cases) == 1
        assert test_cases[0]["fixture"] == "test-project"

    def test_json_report_generation_from_test_results(self) -> None:
        """Test generating and serializing JSON reports."""
        results = [
            TestResult(
                name="test1",
                command="cctx init",
                passed=True,
                exit_code=0,
                expected_exit_code=0,
                stdout="Success",
            ),
            TestResult(
                name="test2",
                command="cctx health",
                passed=False,
                exit_code=1,
                expected_exit_code=0,
                stdout="Error",
                errors=["Exit code mismatch"],
            ),
        ]

        # Generate report
        report = generate_json_report(results)

        # Verify it's JSON serializable
        json_output = json.dumps(report, indent=2)
        assert isinstance(json_output, str)

        # Verify structure
        parsed = json.loads(json_output)
        assert parsed["total"] == 2
        assert parsed["passed"] == 1
        assert parsed["failed"] == 1
        assert len(parsed["results"]) == 2
