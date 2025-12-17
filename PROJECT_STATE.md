# cctx - Project State

> Last updated: 2025-12-17
> Git commit: cdf4ca3 (main)
> Version: 0.1.0

## What is this project?

**cctx** (Living Context CLI Tool) is a Python CLI that keeps documentation co-located with code. Instead of outdated wikis, context lives where the code lives.

Core idea: Each system/module gets a `.ctx/` directory containing:
- `snapshot.md` - Purpose, public API, dependencies
- `constraints.md` - Invariants and boundaries
- `decisions.md` - Index of ADRs
- `debt.md` - Known technical debt
- `adr/` - Architecture Decision Records

## Current Status

**Phase: Alpha - Just extracted from Plantasia-ts**

The project was extracted from an embedded implementation in another project and released as a standalone CLI tool.

| Metric | Value |
|--------|-------|
| Tests | 668 passing |
| Type checking | mypy strict, clean |
| Linting | ruff, clean |
| Python | 3.10+ |

## Architecture Overview

```
cctx/
├── src/cctx/
│   ├── cli.py           # Main Typer CLI entry point
│   ├── database.py      # SQLite ContextDB connection manager
│   ├── schema.py        # Database schema (5 tables)
│   ├── crud.py          # System CRUD operations
│   ├── adr_crud.py      # ADR CRUD operations
│   ├── graph.py         # Dependency graph (BFS, cycles, topo sort)
│   ├── config.py        # Config precedence chain
│   ├── scaffolder.py    # Atomic .ctx/ directory creation
│   ├── template_manager.py  # 5 doc templates
│   ├── validators/      # 4 validators + runner
│   │   ├── snapshot_validator.py
│   │   ├── adr_validator.py
│   │   ├── debt_auditor.py
│   │   ├── freshness_checker.py
│   │   └── runner.py
│   └── fixers/          # Auto-fix capabilities
│       ├── scaffolding_fixer.py
│       ├── snapshot_fixer.py
│       ├── graph_fixer.py
│       └── adr_fixer.py
├── plugin/              # Claude Code integration
│   ├── commands/        # 8 slash commands
│   ├── skills/          # Living Context skill
│   ├── hooks/           # Pre-write warning hook
│   └── eval/            # 46 test cases
└── tests/               # 17 test files
```

## CLI Commands

| Command | Purpose |
|---------|---------|
| `cctx init` | Initialize .ctx/ and install Claude Code plugin |
| `cctx health` | Run 4 validators on documentation |
| `cctx doctor [--fix]` | Find and auto-fix issues |
| `cctx status` | Show summary (systems, ADRs, deps) |
| `cctx sync` | Identify stale documentation |
| `cctx validate` | Pre-commit validation |
| `cctx add-system <path>` | Scaffold system .ctx/ |
| `cctx adr <title>` | Create new ADR |
| `cctx list [systems|adrs|debt]` | List entities |
| `cctx eval` | Run plugin evaluation tests |

## Database Schema

5 tables in SQLite (`knowledge.db`):
1. `systems` - Registered systems with path, name, description
2. `system_dependencies` - System-to-system dependencies
3. `adrs` - Architecture Decision Records
4. `adr_systems` - ADR-to-system links
5. `adr_tags` - ADR tags

## Key Dependencies

- `typer` - CLI framework
- `rich` - Terminal formatting
- `pyyaml` - YAML parsing for configs

## What's Working

- Full CLI with all commands
- SQLite database layer
- 4 validators (snapshot, ADR, debt, freshness)
- Auto-fix capabilities (missing snapshots, stale graphs)
- Claude Code plugin (slash commands, skill, hooks)
- Plugin evaluation system with fixtures
- CI pipeline (lint, typecheck, test)
- PyPI publishing workflow

## In Progress / Next Steps

*Nothing currently in progress*

## Known Issues / Technical Debt

- `debt` listing not fully implemented (placeholder)
- One pytest warning about TestResult class in eval runner

## How to Work on This Project

```bash
# Setup
cd cctx
uv sync --dev

# Run CLI
uv run cctx --help

# Run tests
uv run pytest

# Run all checks
uv run ruff check src tests && uv run mypy src && uv run pytest
```

## Session Log

| Date | Summary |
|------|---------|
| 2025-12-17 | Created initial PROJECT_STATE.md snapshot |

---

*This file is a living document. Update it at the end of each work session.*
