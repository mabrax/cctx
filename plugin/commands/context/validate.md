---
description: Run pre-commit validation checks
argument-hint: ""
---

Run essential validators for pre-commit hooks.

Run: `lctx validate`

Runs a subset of validators suitable for pre-commit:
- Snapshot validator (file existence, dependencies)
- ADR validator (consistency checks)

This is faster than `health` and designed for commit-time validation.
