#!/usr/bin/env python3
"""Living Context plugin evaluation runner.

Executes test cases against the lctx CLI and validates results.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TestResult:
    """Result of a single test case execution."""

    name: str
    command: str
    passed: bool
    exit_code: int
    expected_exit_code: int
    stdout: str
    stderr: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "name": self.name,
            "passed": self.passed,
            "exit_code": self.exit_code,
        }
        if not self.passed:
            result["expected_exit_code"] = self.expected_exit_code
            result["errors"] = self.errors
        return result


def get_eval_dir() -> Path:
    """Get the evaluation directory path."""
    return Path(__file__).parent.resolve()


def load_test_cases(
    test_cases_dir: Path, command: str | None = None, case: str | None = None
) -> list[dict[str, Any]]:
    """Load test cases from YAML files.

    Args:
        test_cases_dir: Directory containing test case YAML files
        command: Optional filter for specific command (matches yaml filename)
        case: Optional filter for specific test case name

    Returns:
        List of test case dictionaries
    """
    all_cases: list[dict[str, Any]] = []

    yaml_files = sorted(test_cases_dir.glob("*.yaml"))

    for yaml_file in yaml_files:
        # Filter by command if specified
        if command and yaml_file.stem != command:
            continue

        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "test_cases" not in data:
            continue

        command_name = data.get("command", yaml_file.stem)

        for test_case in data["test_cases"]:
            # Filter by case name if specified
            if case and test_case.get("name") != case:
                continue

            # Add metadata
            test_case["_command_group"] = command_name
            test_case["_source_file"] = yaml_file.name
            all_cases.append(test_case)

    return all_cases


def load_fixture(fixtures_dir: Path, fixture_name: str, temp_dir: Path) -> Path:
    """Copy a fixture to a temporary directory for isolated testing.

    Args:
        fixtures_dir: Directory containing fixtures
        fixture_name: Name of the fixture to load
        temp_dir: Temporary directory to copy fixture to

    Returns:
        Path to the copied fixture directory
    """
    fixture_path = fixtures_dir / fixture_name

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")

    dest_path = temp_dir / fixture_name

    # Copy the entire fixture directory
    shutil.copytree(fixture_path, dest_path, dirs_exist_ok=True)

    return dest_path


def validate_output(stdout: str, stderr: str, expected: dict[str, Any]) -> list[str]:
    """Validate command output against expected values.

    Args:
        stdout: Standard output from command
        stderr: Standard error from command
        expected: Expected values dictionary

    Returns:
        List of validation error messages
    """
    errors: list[str] = []
    combined_output = stdout + "\n" + stderr

    # Check stdout_contains
    if "stdout_contains" in expected:
        for pattern in expected["stdout_contains"]:
            if pattern.lower() not in combined_output.lower():
                errors.append(f"Expected '{pattern}' in output")

    # Check stdout_not_contains
    if "stdout_not_contains" in expected:
        for pattern in expected["stdout_not_contains"]:
            if pattern.lower() in combined_output.lower():
                errors.append(f"Unexpected '{pattern}' in output")

    # Check json_fields - validate JSON output contains required fields
    if "json_fields" in expected:
        try:
            # Try to parse stdout as JSON
            json_output = json.loads(stdout)
            for field_name in expected["json_fields"]:
                if field_name not in json_output:
                    errors.append(f"Missing JSON field: {field_name}")
        except json.JSONDecodeError:
            errors.append("Output is not valid JSON")

    # Check regex patterns
    if "stdout_matches" in expected:
        for pattern in expected["stdout_matches"]:
            if not re.search(pattern, combined_output, re.IGNORECASE | re.MULTILINE):
                errors.append(f"Output did not match pattern: {pattern}")

    return errors


def run_test_case(
    test_case: dict[str, Any],
    work_dir: Path,
    cctx_project_dir: Path,
    verbose: bool = False,
) -> TestResult:
    """Execute a single test case and validate results.

    Args:
        test_case: Test case dictionary from YAML
        work_dir: Working directory for the test (fixture location)
        cctx_project_dir: Path to the cctx project for uv run
        verbose: Whether to show detailed output

    Returns:
        TestResult with pass/fail status and details
    """
    name = test_case["name"]
    command = test_case["command"]
    expected = test_case.get("expected", {})
    expected_exit_code = expected.get("exit_code", 0)

    # Execute the command
    try:
        result = subprocess.run(
            shlex.split(command),
            shell=False,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **dict(__import__("os").environ),
                "CCTX_PROJECT_DIR": str(cctx_project_dir),
            },
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return TestResult(
            name=name,
            command=command,
            passed=False,
            exit_code=-1,
            expected_exit_code=expected_exit_code,
            stdout="",
            stderr="",
            errors=["Command timed out after 30 seconds"],
        )
    except Exception as e:
        return TestResult(
            name=name,
            command=command,
            passed=False,
            exit_code=-1,
            expected_exit_code=expected_exit_code,
            stdout="",
            stderr="",
            errors=[f"Command execution failed: {e}"],
        )

    # Validate results
    errors: list[str] = []

    # Check exit code
    if exit_code != expected_exit_code:
        errors.append(f"Exit code {exit_code}, expected {expected_exit_code}")

    # Validate output
    output_errors = validate_output(stdout, stderr, expected)
    errors.extend(output_errors)

    passed = len(errors) == 0

    return TestResult(
        name=name,
        command=command,
        passed=passed,
        exit_code=exit_code,
        expected_exit_code=expected_exit_code,
        stdout=stdout,
        stderr=stderr,
        errors=errors,
    )


def print_result(result: TestResult, verbose: bool = False) -> None:
    """Print a test result to stdout.

    Args:
        result: TestResult to print
        verbose: Whether to show detailed output
    """
    status = "PASS" if result.passed else "FAIL"
    status_color = "\033[92m" if result.passed else "\033[91m"
    reset_color = "\033[0m"

    print(f"  [{status_color}{status}{reset_color}] {result.name}")

    if verbose or not result.passed:
        if result.errors:
            for error in result.errors:
                print(f"       - {error}")
        if verbose and result.stdout:
            print(f"       stdout: {result.stdout[:200]}...")
        if verbose and result.stderr:
            print(f"       stderr: {result.stderr[:200]}...")


def print_summary(results: list[TestResult]) -> None:
    """Print a summary of test results.

    Args:
        results: List of TestResults to summarize
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print()
    print("=" * 50)
    print(f"Results: {passed}/{total} passed")
    if failed > 0:
        print(f"\033[91mFailed: {failed}\033[0m")
    else:
        print("\033[92mAll tests passed!\033[0m")
    print("=" * 50)


def generate_json_report(results: list[TestResult]) -> dict[str, Any]:
    """Generate a JSON report of test results.

    Args:
        results: List of TestResults

    Returns:
        Dictionary suitable for JSON output
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": [r.to_dict() for r in results],
    }


def main() -> int:
    """Main entry point for the evaluation runner.

    Returns:
        Exit code (0 if all tests pass, 1 if any fail)
    """
    parser = argparse.ArgumentParser(
        description="Living Context plugin evaluation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py                      # Run all tests
  python runner.py --command init       # Run only init command tests
  python runner.py --case health_healthy_project  # Run specific test
  python runner.py --json               # Output results as JSON
  python runner.py --verbose            # Show detailed output
""",
    )
    parser.add_argument(
        "--command",
        type=str,
        help="Run tests for specific command only (e.g., init, health, validate)",
    )
    parser.add_argument(
        "--case",
        type=str,
        help="Run specific test case only (by name)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Detailed output including stdout/stderr",
    )

    args = parser.parse_args()

    # Determine paths
    eval_dir = get_eval_dir()
    test_cases_dir = eval_dir / "test-cases"
    fixtures_dir = eval_dir / "fixtures"
    cctx_project_dir = eval_dir.parent.parent  # cctx/ directory

    # Validate directories exist
    if not test_cases_dir.exists():
        print(f"Error: Test cases directory not found: {test_cases_dir}", file=sys.stderr)
        return 1

    if not fixtures_dir.exists():
        print(f"Error: Fixtures directory not found: {fixtures_dir}", file=sys.stderr)
        return 1

    # Load test cases
    test_cases = load_test_cases(test_cases_dir, args.command, args.case)

    if not test_cases:
        if args.json:
            print(json.dumps({"total": 0, "passed": 0, "failed": 0, "results": []}))
        else:
            print("No test cases found matching criteria")
        return 0

    if not args.json:
        print(f"Running {len(test_cases)} test case(s)...")
        print()

    # Run tests
    results: list[TestResult] = []

    # Group test cases by fixture for display purposes
    fixture_cases: dict[str, list[dict[str, Any]]] = {}
    for tc in test_cases:
        fixture = tc.get("fixture", "empty-project")
        if fixture not in fixture_cases:
            fixture_cases[fixture] = []
        fixture_cases[fixture].append(tc)

    # Run each test case with its own fresh fixture copy for isolation
    for fixture_name, cases in fixture_cases.items():
        if not args.json:
            print(f"Fixture: {fixture_name}")

        for tc in cases:
            # Create a fresh temp directory for each test case
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                try:
                    work_dir = load_fixture(fixtures_dir, fixture_name, temp_path)
                except FileNotFoundError as e:
                    results.append(
                        TestResult(
                            name=tc["name"],
                            command=tc.get("command", ""),
                            passed=False,
                            exit_code=-1,
                            expected_exit_code=tc.get("expected", {}).get("exit_code", 0),
                            stdout="",
                            stderr="",
                            errors=[str(e)],
                        )
                    )
                    if not args.json:
                        print_result(results[-1], args.verbose)
                    continue

                result = run_test_case(tc, work_dir, cctx_project_dir, args.verbose)
                results.append(result)

                if not args.json:
                    print_result(result, args.verbose)

        if not args.json:
            print()

    # Output results
    if args.json:
        report = generate_json_report(results)
        print(json.dumps(report, indent=2))
    else:
        print_summary(results)

    # Return exit code based on results
    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
