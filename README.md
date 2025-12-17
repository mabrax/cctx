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

### Core Commands

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

### Common Options

All commands support:
- `--json` - Output as JSON (for scripting)
- `--quiet` / `-q` - Minimal output (for CI)
- `--ctx-dir` - Override context directory name (default: `.ctx`)

## Directory Structure

After initialization, cctx creates:

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

`cctx health` runs four validators:

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
cctx doctor

# Preview what fixes would be applied (no changes made)
cctx doctor --dry-run

# Apply all available fixes
cctx doctor --fix

# Verbose output with detailed information
cctx doctor --fix --verbose
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
cctx health

# 2. See which issues can be auto-fixed
cctx doctor

# 3. Preview the fixes
cctx doctor --dry-run

# 4. Apply the fixes
cctx doctor --fix

# 5. Verify health is now clean
cctx health
```

## Claude Code Integration

The Claude Code plugin is automatically installed when you run `cctx init`. The plugin provides:

- **8 slash commands** (`/context-init`, `/context-health`, etc.)
- **Living Context skill** (triggered by context-related questions)
- **Pre-write hook** (warns on `.ctx/` edits)

Plugin files are installed to `.claude/plugins/living-context/` in your project.

### Reinitializing

If you need to reinstall the plugin or reset your context:

```bash
# Reinitialize everything (overwrites existing files)
cctx init --force
```

### Plugin Evaluation

Test the plugin with the built-in eval system:

```bash
# Run all tests
cctx eval

# Test specific command
cctx eval --command health

# Run specific test case
cctx eval --case "health-deep-check"

# JSON output for CI
cctx eval --json
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
4. Run `cctx health` to verify

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
cctx validate
```

Or use the plugin's hook which runs automatically.

## Migration from Embedded Version

If you have an existing `.ctx/` structure from the embedded Plantasia implementation:

1. **Database is compatible** - `knowledge.db` schema matches
2. **Templates may differ** - Compare and merge if customized
3. **Install CLI** - `uv add cctx` or install from source
4. **Verify** - Run `cctx health` to check compatibility

Key differences:
- CLI is standalone (not project-specific)
- Plugin provides Claude Code integration
- Validators are more comprehensive

## Configuration

cctx looks for configuration in order:
1. CLI flags (`--ctx-dir`)
2. Environment variables (`LCTX_CTX_DIR`)
3. `.cctxrc` file in project root
4. `pyproject.toml` `[tool.cctx]` section
5. Defaults (`.ctx`)

Example `.cctxrc`:

```toml
ctx_dir = ".context"
systems_dir = "src/modules"
```

## Development

```bash
# Clone and setup
git clone <repo>
cd cctx
uv sync --dev

# Run the CLI
uv run cctx --help

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
