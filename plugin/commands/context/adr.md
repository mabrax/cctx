---
description: Create a new Architecture Decision Record
argument-hint: "<title> [--system=<path>]"
---

Create a new ADR from template.

Run: `lctx adr $ARGUMENTS`

Creates:
- New ADR file with auto-incremented number
- YAML frontmatter with status, date, context
- Standard sections: Context, Decision, Consequences

Use `--system=<path>` to associate the ADR with a specific system.
The ADR is automatically registered in the knowledge database.
