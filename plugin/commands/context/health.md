---
description: Run health checks on Living Context documentation
argument-hint: "[--deep]"
---

Run all validators to check Living Context health.

Run: `cctx health $ARGUMENTS`

Validators:
- **Snapshot**: File existence, dependency accuracy
- **ADR**: Orphan detection, broken references, DB sync
- **Debt**: Age threshold, resolution detection
- **Freshness** (--deep): Staleness detection for all docs

Use `--deep` for comprehensive freshness checking.
