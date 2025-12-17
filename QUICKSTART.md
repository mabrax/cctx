# cctx Quick Reference

## First Time Setup

```bash
cd your-project
cctx init    # Creates .ctx/ AND installs Claude Code plugin
```

> **One command** sets up everything: context database, templates, and Claude Code integration.

## Daily Commands

```bash
cctx health          # Check if docs are healthy
cctx doctor          # Find fixable issues
cctx status          # Quick overview (systems, ADRs, deps)
cctx sync --dry-run  # What docs need updating?
```

## Adding Things

```bash
cctx add-system src/systems/auth     # New system
cctx adr "Use Redis for caching"     # New ADR
```

## Listing Things

```bash
cctx list systems    # All registered systems
cctx list adrs       # All ADRs with status
cctx list debt       # Technical debt items
```

## Pre-Commit

```bash
cctx validate        # Fast check (snapshot + ADR only)
cctx health --deep   # Full check with constraints
```

## Fixing Issues

```bash
cctx doctor              # See what can be fixed
cctx doctor --dry-run    # Preview fixes (no changes)
cctx doctor --fix        # Apply all fixes
```

## Workflow Reminder

**Before changing a system:** Read its `.ctx/snapshot.md`

**After changing a system:**
1. Update `snapshot.md` if API changed
2. Run `cctx health`
3. Run `cctx doctor --fix` if issues are fixable

**Making architectural decisions:** `cctx adr "Decision title"`
