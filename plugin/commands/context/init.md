---
description: Initialize Living Context (.ctx/) in a project
argument-hint: "[path]"
---

Initialize Living Context documentation structure in the current or specified directory.

Run: `lctx init $ARGUMENTS`

This creates:
- `.ctx/knowledge.db` - SQLite database for systems, ADRs, dependencies
- `.ctx/graph.json` - Generated dependency graph
- `.ctx/templates/` - Documentation templates
