---
description: List registered entities
argument-hint: "[systems|adrs|debt]"
---

List entities tracked in the Living Context database.

Run: `cctx list $ARGUMENTS`

Options:
- `systems` - List all registered systems with paths
- `adrs` - List ADRs with status and date
- `debt` - List technical debt items by priority

Without arguments, shows a summary of all entity types.
