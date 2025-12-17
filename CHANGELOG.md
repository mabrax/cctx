# Changelog

All notable changes to lctx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-12-16

### Added

#### Phase 1: Project Scaffolding
- Python package structure with UV
- Typer-based CLI framework
- Basic project configuration (ruff, mypy, pytest)
- CI workflow (lint, typecheck, test)

#### Phase 2: Core Data Layer
- SQLite database with 5 tables (systems, system_dependencies, adrs, adr_systems, adr_tags)
- ContextDB connection manager with transaction support
- CRUD operations for systems and ADRs
- Graph generation and analysis (BFS traversal, cycle detection, topological sort)
- Configuration precedence chain (CLI > env > .lctxrc > pyproject.toml > defaults)
- Template manager with 5 templates (snapshot, constraints, decisions, debt, adr)
- Atomic scaffolding for .ctx/ directories

#### Phase 3: CLI Commands
- `lctx init` - Initialize .ctx/ directory structure
- `lctx health` - Run health checks with 4 validators
- `lctx status` - Show Living Context status summary
- `lctx sync` - Identify stale documentation
- `lctx validate` - Pre-commit validation checks
- `lctx add-system` - Create .ctx/ for a system with DB registration
- `lctx adr` - Create ADR from template with DB registration
- `lctx list` - List systems, ADRs, or debt items

#### Phase 4: Validation Engine
- SnapshotValidator: File existence, dependency accuracy
- AdrValidator: Orphan detection, broken references, DB sync, superseded chains
- DebtAuditor: Age threshold (30 days), resolution detection, priority tracking
- FreshnessChecker: Staleness detection for snapshot/decisions/constraints/graph
- ValidationRunner: Parallel execution, aggregated results, selective validator runs

#### Phase 6: Claude Code Plugin
- Plugin manifest (.claude-plugin/plugin.json)
- 8 slash commands for Claude Code integration
- Living Context skill with 15+ trigger words
- Pre-write hook for .ctx/ edit warnings
- Evaluation system with rubric, fixtures, and 46 test cases
- `lctx plugin install` - Install plugin to project or user scope
- `lctx plugin eval` - Run plugin evaluation tests

### Technical Details

- 606 tests passing
- Full type coverage (mypy strict mode)
- Ruff linting with comprehensive rule set
- Python 3.10+ compatibility
