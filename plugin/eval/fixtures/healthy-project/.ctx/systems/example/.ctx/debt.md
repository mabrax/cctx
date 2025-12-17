# Technical Debt

Tracked shortcuts and known issues requiring future work.

## Active Debt

| ID | Description | Created | Priority | Impact |
|----|-------------|---------|----------|--------|
| DEBT-001 | Consider caching for repeated getExample() calls | 2025-06-01 | low | Slight performance impact on high-frequency calls |

## Priority Guide

- **high** - Blocks features or causes bugs
- **medium** - Slows development or maintenance
- **low** - Cleanup, nice-to-have improvements

## Resolved Debt

| ID | Description | Resolved | Resolution |
|----|-------------|----------|------------|
| DEBT-000 | Type definitions were incomplete | 2025-02-15 | Completed full TypeScript migration |

## Adding Debt

When adding debt:
1. Assign next ID number
2. Describe the shortcut taken
3. Note why it was acceptable at the time
4. Estimate impact if left unresolved
