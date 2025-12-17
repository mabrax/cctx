# Living Context Claude Plugin

A Claude Code plugin that provides co-located documentation management—keeping your system architecture, decisions, and technical debt synchronized with your codebase.

## Features

- **Automated Documentation**: Generate and maintain `.ctx/` structures for systems
- **Architecture Decisions**: Create and track ADRs with full history
- **Technical Debt Tracking**: Document, prioritize, and monitor technical debt
- **Health Checks**: Validate documentation consistency and freshness
- **Pre-commit Integration**: Fast validation suitable for git hooks
- **Dependency Tracking**: Maintain accurate system dependency graphs

## Installation

Copy the plugin to your Claude Code configuration directory:

```bash
cp -r cctx/plugin ~/.claude/plugins/living-context/
```

The plugin will then be available in Claude Code.

## Requirements

- **UV Package Manager**: The plugin requires UV for running cctx commands
  - Install UV: https://docs.astral.sh/uv/
  - Ensure UV is in your PATH
- **cctx Installed**: Install via UV in your project:
  ```bash
  uv add --dev cctx
  ```

All plugin commands use the `uv run cctx` pattern to execute the Living Context CLI.

## Available Commands

### 1. /context:init
**Initialize Living Context**

Set up Living Context documentation structure in your project.

```bash
uv run cctx init [path]
```

Creates:
- `.ctx/knowledge.db` - SQLite database for systems, ADRs, and dependencies
- `.ctx/graph.json` - Generated dependency graph
- `.ctx/templates/` - Documentation templates for new systems and ADRs

### 2. /context:health
**Run health checks**

Validate Living Context documentation consistency and quality.

```bash
uv run cctx health [--deep]
```

Runs validators for:
- **Snapshot**: File existence and dependency accuracy
- **ADR**: Orphan detection, broken references, database synchronization
- **Debt**: Age threshold checking and resolution detection
- **Freshness** (with `--deep`): Staleness detection across all documentation

Use `--deep` for comprehensive freshness checking.

### 3. /context:status
**Show status summary**

Display a quick overview of Living Context health and metrics.

```bash
uv run cctx status
```

Shows:
- Total systems registered
- Total ADRs and their statuses
- Technical debt items by priority
- Overall health status

### 4. /context:sync
**Sync documentation**

Identify and report stale documentation that needs updating.

```bash
uv run cctx sync [--dry-run]
```

Uses freshness checking to identify:
- Stale `snapshot.md` files
- Outdated `decisions.md` files
- Constraints that may need review
- `graph.json` that needs regeneration

Use `--dry-run` to preview changes without taking action.

### 5. /context:validate
**Pre-commit validation**

Run essential validators suitable for git hooks.

```bash
uv run cctx validate
```

Runs a fast subset of validators:
- Snapshot validator (file existence and dependencies)
- ADR validator (consistency checks)

Designed for commit-time validation—faster than full health checks.

### 6. /context:add-system
**Create system context**

Set up Living Context documentation for a new system or module.

```bash
uv run cctx add-system <path>
```

Creates in `<path>/.ctx/`:
- `snapshot.md` - System purpose, public API, and dependencies
- `constraints.md` - Invariants and boundaries
- `decisions.md` - Index of Architecture Decision Records
- `debt.md` - Technical debt tracking

Automatically registers the system in the knowledge database.

### 7. /context:adr
**Create Architecture Decision Record**

Create a new ADR with proper metadata and registration.

```bash
uv run cctx adr "<title>" [--system=<path>]
```

Creates:
- New ADR file with auto-incremented number
- YAML frontmatter with status, date, and context
- Standard sections: Context, Decision, Consequences

Use `--system=<path>` to associate the ADR with a specific system. The ADR is automatically registered in the knowledge database.

### 8. /context:list
**List entities**

Query Living Context database for registered entities.

```bash
uv run cctx list [systems|adrs|debt]
```

Options:
- `systems` - List all registered systems with their paths
- `adrs` - List ADRs with status and creation date
- `debt` - List technical debt items sorted by priority

Without arguments, shows a summary of all entity types.

## Quick Start

1. **Initialize Living Context in your project:**
   ```bash
   /context:init
   ```

2. **Create documentation for your first system:**
   ```bash
   /context:add-system src/systems/my-system
   ```

3. **Create an Architecture Decision Record:**
   ```bash
   /context:adr "Use event sourcing for audit logs" --system=src/systems/my-system
   ```

4. **Check overall health:**
   ```bash
   /context:status
   ```

5. **Validate before commits:**
   ```bash
   /context:validate
   ```

## Integration with Git Hooks

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/sh
uv run cctx validate
```

This ensures documentation stays synchronized with code changes.

## Documentation Structure

After initialization, your project will have:

```
.ctx/
├── knowledge.db          # SQLite database
├── graph.json            # Dependency graph
├── README.md             # System documentation
└── templates/            # Documentation templates
    ├── snapshot.template.md
    ├── constraints.template.md
    ├── decisions.template.md
    ├── debt.template.md
    └── adr.template.md

src/systems/
└── <system-name>/
    └── .ctx/
        ├── snapshot.md       # Purpose, API, dependencies
        ├── constraints.md    # Invariants and boundaries
        ├── decisions.md      # ADR index
        ├── debt.md           # Technical debt
        └── adr/              # Architecture Decision Records
            ├── ADR-001.md
            └── ADR-002.md
```

## License

MIT

## Support

For issues and feature requests, visit the [Living Context repository](https://github.com/mabrax/cctx).
