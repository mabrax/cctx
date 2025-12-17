---
description: Create .ctx/ structure for a system or module
argument-hint: "<path>"
---

Create Living Context documentation for a new system.

Run: `cctx add-system $ARGUMENTS`

Creates in `<path>/.ctx/`:
- `snapshot.md` - System purpose, API, dependencies
- `constraints.md` - Invariants and boundaries
- `decisions.md` - Index of ADRs
- `debt.md` - Technical debt tracking

Also registers the system in the knowledge database.
