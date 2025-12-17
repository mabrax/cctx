---
description: Sync documentation with codebase changes
argument-hint: "[--dry-run]"
---

Check for and report stale documentation that needs updating.

Run: `cctx sync $ARGUMENTS`

Uses the freshness checker to identify:
- Stale snapshot.md files
- Outdated decisions.md files
- Constraints that may need review
- Graph.json that needs regeneration

Use `--dry-run` to preview what would be flagged without taking action.
