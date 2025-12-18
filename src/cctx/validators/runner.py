"""Validation runner for orchestrating all validators.

Provides a unified interface to run all validators and aggregate results.
Supports parallel execution and selective validator runs.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cctx.validators.adr_validator import AdrValidator
from cctx.validators.base import BaseValidator, ValidationIssue, ValidatorResult
from cctx.validators.debt_auditor import DebtAuditor
from cctx.validators.freshness_checker import FreshnessChecker
from cctx.validators.snapshot_validator import SnapshotValidator


@dataclass
class AggregatedResult:
    """Aggregated results from running multiple validators.

    Attributes:
        status: Overall status ("pass" if all validators pass, "fail" otherwise).
        validators_run: Number of validators executed.
        total_issues: Total number of issues across all validators.
        errors: Number of error-severity issues.
        warnings: Number of warning-severity issues.
        infos: Number of info-severity issues.
        results: Individual results from each validator.
        all_issues: Flattened list of all issues from all validators.
    """

    status: Literal["pass", "fail"]
    validators_run: int
    total_issues: int
    errors: int
    warnings: int
    infos: int
    results: list[ValidatorResult]
    all_issues: list[ValidationIssue]


class ValidationRunner:
    """Orchestrates running all validators.

    Supports:
    - Running all validators
    - Running specific validators by name
    - Parallel execution for performance
    - Deep validation (includes constraint checker - future)
    """

    # Available validator classes
    VALIDATORS: dict[str, type[BaseValidator]] = {
        "snapshot": SnapshotValidator,
        "adr": AdrValidator,
        "debt": DebtAuditor,
        "freshness": FreshnessChecker,
    }

    # Default validators for standard health check
    DEFAULT_VALIDATORS = ["snapshot", "adr", "debt", "freshness"]

    # Validators only run in deep mode
    DEEP_VALIDATORS: list[str] = []  # constraint-checker would go here

    def __init__(
        self,
        project_root: Path,
        db_path: Path,
        parallel: bool = True,
    ) -> None:
        """Initialize validation runner.

        Args:
            project_root: Root directory of the project.
            db_path: Path to the Living Context knowledge database.
            parallel: Whether to run validators in parallel.
        """
        self.project_root = project_root
        self.db_path = db_path
        self.parallel = parallel

    def run_all(self, deep: bool = False) -> AggregatedResult:
        """Run all validators.

        Args:
            deep: If True, includes deep validation checks.

        Returns:
            AggregatedResult with combined outcomes from all validators.
        """
        validators_to_run = self.DEFAULT_VALIDATORS.copy()
        if deep:
            validators_to_run.extend(self.DEEP_VALIDATORS)

        return self.run_validators(validators_to_run)

    def run_validators(self, validator_names: list[str]) -> AggregatedResult:
        """Run specific validators by name.

        Args:
            validator_names: List of validator names to run.

        Returns:
            AggregatedResult with combined outcomes.
        """
        results: list[ValidatorResult] = []

        # Filter to valid validator names
        valid_names = [name for name in validator_names if name in self.VALIDATORS]

        if not valid_names:
            return AggregatedResult(
                status="pass",
                validators_run=0,
                total_issues=0,
                errors=0,
                warnings=0,
                infos=0,
                results=[],
                all_issues=[],
            )

        if self.parallel and len(valid_names) > 1:
            results = self._run_parallel(valid_names)
        else:
            results = self._run_sequential(valid_names)

        return self._aggregate_results(results)

    def run_single(self, validator_name: str) -> ValidatorResult | None:
        """Run a single validator by name.

        Args:
            validator_name: Name of the validator to run.

        Returns:
            ValidatorResult, or None if validator not found.
        """
        if validator_name not in self.VALIDATORS:
            return None

        validator = self._create_validator(validator_name)
        return validator.validate()

    def _create_validator(self, name: str) -> BaseValidator:
        """Create a validator instance by name.

        Args:
            name: Validator name.

        Returns:
            Validator instance.

        Raises:
            KeyError: If validator name is not found.
        """
        validator_class = self.VALIDATORS[name]
        return validator_class(self.project_root, self.db_path)

    def _run_sequential(self, validator_names: list[str]) -> list[ValidatorResult]:
        """Run validators sequentially.

        Args:
            validator_names: List of validator names.

        Returns:
            List of validator results.
        """
        results: list[ValidatorResult] = []

        for name in validator_names:
            try:
                validator = self._create_validator(name)
                result = validator.validate()
                results.append(result)
            except Exception as e:
                # Create error result for failed validator
                results.append(
                    ValidatorResult(
                        name=name,
                        status="fail",
                        issues=[
                            ValidationIssue(
                                system="",
                                check="validator_error",
                                severity="error",
                                message=f"Validator failed: {e!s}",
                            )
                        ],
                        systems_checked=0,
                    )
                )

        return results

    def _run_parallel(self, validator_names: list[str]) -> list[ValidatorResult]:
        """Run validators in parallel using ThreadPoolExecutor.

        Args:
            validator_names: List of validator names.

        Returns:
            List of validator results.
        """
        results: list[ValidatorResult] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(validator_names)) as executor:
            # Submit all validators
            future_to_name: dict[concurrent.futures.Future[ValidatorResult], str] = {}
            for name in validator_names:
                try:
                    validator = self._create_validator(name)
                    future = executor.submit(validator.validate)
                    future_to_name[future] = name
                except Exception as e:
                    # Immediate failure for validator creation
                    results.append(
                        ValidatorResult(
                            name=name,
                            status="fail",
                            issues=[
                                ValidationIssue(
                                    system="",
                                    check="validator_error",
                                    severity="error",
                                    message=f"Failed to create validator: {e!s}",
                                )
                            ],
                            systems_checked=0,
                        )
                    )

            # Collect results
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(
                        ValidatorResult(
                            name=name,
                            status="fail",
                            issues=[
                                ValidationIssue(
                                    system="",
                                    check="validator_error",
                                    severity="error",
                                    message=f"Validator failed: {e!s}",
                                )
                            ],
                            systems_checked=0,
                        )
                    )

        return results

    def _aggregate_results(self, results: list[ValidatorResult]) -> AggregatedResult:
        """Aggregate multiple validator results into a single summary.

        Args:
            results: List of validator results.

        Returns:
            AggregatedResult combining all results.
        """
        all_issues: list[ValidationIssue] = []
        errors = 0
        warnings = 0
        infos = 0

        for result in results:
            all_issues.extend(result.issues)

        for issue in all_issues:
            if issue.severity == "error":
                errors += 1
            elif issue.severity == "warning":
                warnings += 1
            else:
                infos += 1

        # Overall status is fail if any validator failed
        has_failures = any(result.status == "fail" for result in results)
        status: Literal["pass", "fail"] = "fail" if has_failures else "pass"

        return AggregatedResult(
            status=status,
            validators_run=len(results),
            total_issues=len(all_issues),
            errors=errors,
            warnings=warnings,
            infos=infos,
            results=results,
            all_issues=all_issues,
        )
