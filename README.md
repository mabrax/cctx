# cctx - Living Context CLI Tool

Co-located documentation that stays synchronized with code. No more archaeological digs through outdated wikis--context lives where the code lives.

> **Status**: Alpha - Testing in progress

## Philosophy

Living Context keeps documentation close to the code it describes:
- **Snapshots** capture system purpose, API, and dependencies
- **Constraints** define invariants that must never be violated
- **ADRs** record architectural decisions with full context
- **Debt tracking** makes technical debt visible and actionable

When documentation lives with code, it gets updated with code.

## Installation

```bash
# From source (development)
cd cctx
uv sync --dev
uv run cctx --help
```

## Quick Start

```bash
# Initialize Living Context in your project
cctx init

# Add a system to track
cctx add-system src/systems/auth

# Check documentation health
cctx health

# Create an Architecture Decision Record
cctx adr "Use JWT for authentication"

# Show status summary
cctx status
```

## Commands

| Command | Description |
|---------|-------------|
| `cctx init [path] [--force]` | Initialize `.ctx/` and install Claude Code plugin |
| `cctx health [--deep]` | Run health checks on documentation |
| `cctx doctor [--fix] [--dry-run]` | Find and fix common issues |
| `cctx status` | Show Living Context status summary |
| `cctx sync [--dry-run]` | Identify stale documentation |
| `cctx validate` | Run pre-commit validation checks |
| `cctx add-system <path>` | Create `.ctx/` for a system/module |
| `cctx adr <title>` | Create new Architecture Decision Record |
| `cctx list [systems\|adrs\|debt]` | List registered entities |
| `cctx eval [--command] [--case]` | Run plugin evaluation tests |

All commands support `--json` (for scripting), `--quiet` (for CI), and `--ctx-dir` (override default `.ctx`).

## Directory Structure

```
.ctx/
├── knowledge.db    # SQLite database (ADRs, systems, dependencies)
├── graph.json      # Dependency graph
├── templates/      # Documentation templates
└── adr/            # Global ADRs

src/systems/<name>/.ctx/
├── snapshot.md     # Purpose, public API, dependencies
├── constraints.md  # Invariants and boundaries
├── decisions.md    # Index of ADRs for this system
├── debt.md         # Known technical debt
└── adr/            # System-specific ADRs
```

## Validators

`cctx health` runs four validators:

| Validator | Checks |
|-----------|--------|
| **Snapshot** | File existence, dependency accuracy |
| **ADR** | Orphan detection, broken refs, DB sync |
| **Debt Auditor** | Age thresholds, resolution status |
| **Freshness** | Staleness detection for all docs |

Use `--deep` for comprehensive checks including constraint validation.

## Doctor Command

Find and fix issues automatically:

```bash
cctx doctor              # See issues and available fixes
cctx doctor --dry-run    # Preview fixes without applying
cctx doctor --fix        # Apply all available fixes
```

## Claude Code Integration

The plugin is automatically installed with `cctx init`, providing:

- **8 slash commands** (`/context-init`, `/context-health`, etc.)
- **Living Context skill** (triggered by context-related questions)
- **Pre-write hook** (warns on `.ctx/` edits)

Run `cctx eval` to test the plugin integration.

## Workflow

**Before modifying a system:** Read `snapshot.md`, check `constraints.md`, review `debt.md`.

**After modifying a system:** Update docs if API changed, add ADR if decisions were made, run `cctx health`.

**Pre-commit hook** (optional):
```bash
#!/bin/bash
cctx validate
```

## Configuration

cctx looks for configuration in order: CLI flags → environment variables (`LCTX_CTX_DIR`) → `.cctxrc` → `pyproject.toml [tool.cctx]` → defaults.

```toml
# .cctxrc
ctx_dir = ".context"
systems_dir = "src/modules"
```

## Development

```bash
git clone <repo> && cd cctx
uv sync --dev
uv run pytest                    # Run tests
uv run ruff check src tests      # Lint
uv run mypy src                  # Type check
```

## License

MIT
