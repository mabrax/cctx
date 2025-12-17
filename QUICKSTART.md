# lctx Quick Reference

## First Time Setup

```bash
cd your-project
lctx init    # Creates .ctx/ AND installs Claude Code plugin
```

> **One command** sets up everything: context database, templates, and Claude Code integration.

## Daily Commands

```bash
lctx health          # Check if docs are healthy
lctx doctor          # Find fixable issues
lctx status          # Quick overview (systems, ADRs, deps)
lctx sync --dry-run  # What docs need updating?
```

## Adding Things

```bash
lctx add-system src/systems/auth     # New system
lctx adr "Use Redis for caching"     # New ADR
```

## Listing Things

```bash
lctx list systems    # All registered systems
lctx list adrs       # All ADRs with status
lctx list debt       # Technical debt items
```

## Pre-Commit

```bash
lctx validate        # Fast check (snapshot + ADR only)
lctx health --deep   # Full check with constraints
```

## Fixing Issues

```bash
lctx doctor              # See what can be fixed
lctx doctor --dry-run    # Preview fixes (no changes)
lctx doctor --fix        # Apply all fixes
```

## Workflow Reminder

**Before changing a system:** Read its `.ctx/snapshot.md`

**After changing a system:**
1. Update `snapshot.md` if API changed
2. Run `lctx health`
3. Run `lctx doctor --fix` if issues are fixable

**Making architectural decisions:** `lctx adr "Decision title"`
