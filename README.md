# lctx - Living Context CLI Tool

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
cd lctx
uv sync --dev
uv run lctx --help
```

## Quick Start

```bash
# Initialize Living Context in your project
lctx init

# Add a system to track
lctx add-system src/systems/auth

# Check documentation health
lctx health

# Create an Architecture Decision Record
lctx adr "Use JWT for authentication"

# Show status summary
lctx status
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `lctx init [path] [--force]` | Initialize `.ctx/` and install Claude Code plugin |
| `lctx health [--deep]` | Run health checks on documentation |
| `lctx doctor [--fix] [--dry-run]` | Find and fix common issues |
| `lctx status` | Show Living Context status summary |
| `lctx sync [--dry-run]` | Identify stale documentation |
| `lctx validate` | Run pre-commit validation checks |
| `lctx add-system <path>` | Create `.ctx/` for a system/module |
| `lctx adr <title>` | Create new Architecture Decision Record |
| `lctx list [systems\|adrs\|debt]` | List registered entities |
| `lctx eval [--command] [--case]` | Run plugin evaluation tests |

### Common Options

All commands support:
- `--json` - Output as JSON (for scripting)
- `--quiet` / `-q` - Minimal output (for CI)
- `--ctx-dir` - Override context directory name (default: `.ctx`)

## Directory Structure

After initialization, lctx creates:

```
.ctx/
├── knowledge.db    # SQLite database (ADRs, systems, dependencies)
├── graph.json      # Dependency graph
├── templates/      # Documentation templates
│   ├── snapshot.md
│   ├── constraints.md
│   ├── decisions.md
│   ├── debt.md
│   └── adr.md
└── adr/            # Global ADRs
```

For each system:

```
src/systems/<name>/.ctx/
├── snapshot.md     # Purpose, public API, dependencies
├── constraints.md  # Invariants and boundaries
├── decisions.md    # Index of ADRs for this system
├── debt.md         # Known technical debt
└── adr/            # System-specific ADRs
```

## Validators

`lctx health` runs four validators:

| Validator | Checks |
|-----------|--------|
| **Snapshot** | File existence, dependency accuracy |
| **ADR** | Orphan detection, broken refs, DB sync |
| **Debt Auditor** | Age thresholds, resolution status |
| **Freshness** | Staleness detection for all docs |

Use `--deep` for comprehensive checks including constraint validation.

## Doctor Command

The `doctor` command finds issues and can automatically fix many of them:

```bash
# See what issues exist and which can be fixed
lctx doctor

# Preview what fixes would be applied (no changes made)
lctx doctor --dry-run

# Apply all available fixes
lctx doctor --fix

# Verbose output with detailed information
lctx doctor --fix --verbose
```

### Available Fixes

| Fix Type | What It Does |
|----------|--------------|
| `missing_snapshot` | Creates `snapshot.md` from template for systems missing it |
| `stale_graph` | Regenerates `graph.json` from current system dependencies |

### Options

| Flag | Description |
|------|-------------|
| `--fix` | Apply fixes automatically |
| `--dry-run`, `-n` | Show what would be fixed without making changes |
| `--json` | Output results as JSON (for scripting) |
| `--verbose`, `-v` | Show detailed output |

### Exit Codes

- `0` - All issues fixed or no issues found
- `1` - Issues remain unfixed

### Typical Workflow

```bash
# 1. Check health to see all issues
lctx health

# 2. See which issues can be auto-fixed
lctx doctor

# 3. Preview the fixes
lctx doctor --dry-run

# 4. Apply the fixes
lctx doctor --fix

# 5. Verify health is now clean
lctx health
```

## Claude Code Integration

The Claude Code plugin is automatically installed when you run `lctx init`. The plugin provides:

- **8 slash commands** (`/context-init`, `/context-health`, etc.)
- **Living Context skill** (triggered by context-related questions)
- **Pre-write hook** (warns on `.ctx/` edits)

Plugin files are installed to `.claude/plugins/living-context/` in your project.

### Reinitializing

If you need to reinstall the plugin or reset your context:

```bash
# Reinitialize everything (overwrites existing files)
lctx init --force
```

### Plugin Evaluation

Test the plugin with the built-in eval system:

```bash
# Run all tests
lctx eval

# Test specific command
lctx eval --command health

# Run specific test case
lctx eval --case "health-deep-check"

# JSON output for CI
lctx eval --json
```

## Workflow

### Before Modifying a System

1. Read `snapshot.md` to understand purpose and API
2. Check `constraints.md` for invariants
3. Review `debt.md` for known issues

### After Modifying a System

1. Update `snapshot.md` if API changed
2. Add ADR if architectural decision was made
3. Update `debt.md` if shortcuts were taken
4. Run `lctx health` to verify

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
lctx validate
```

Or use the plugin's hook which runs automatically.

## Migration from Embedded Version

If you have an existing `.ctx/` structure from the embedded Plantasia implementation:

1. **Database is compatible** - `knowledge.db` schema matches
2. **Templates may differ** - Compare and merge if customized
3. **Install CLI** - `uv add lctx` or install from source
4. **Verify** - Run `lctx health` to check compatibility

Key differences:
- CLI is standalone (not project-specific)
- Plugin provides Claude Code integration
- Validators are more comprehensive

## Configuration

lctx looks for configuration in order:
1. CLI flags (`--ctx-dir`)
2. Environment variables (`LCTX_CTX_DIR`)
3. `.lctxrc` file in project root
4. `pyproject.toml` `[tool.lctx]` section
5. Defaults (`.ctx`)

Example `.lctxrc`:

```toml
ctx_dir = ".context"
systems_dir = "src/modules"
```

## Development

```bash
# Clone and setup
git clone <repo>
cd lctx
uv sync --dev

# Run the CLI
uv run lctx --help

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests

# Run type checking
uv run mypy src

# Run all checks
uv run ruff check src tests && uv run mypy src && uv run pytest
```

## License

MIT
