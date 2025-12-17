# Constraints

Hard rules this system must obey. Violations are bugs.

## Invariants

Properties that must always be true:

1. **Invariant name**
   - What: Description of the invariant
   - Why: Reason this must hold
   - Violation: What breaks if violated

## Boundaries

Limits on system behavior:

| Boundary | Limit | Reason |
|----------|-------|--------|
| Example | 100 max | Performance constraint |

## External Constraints

Requirements imposed by dependencies or environment:

- **Phaser**: Must run in browser context
- **TypeScript**: Strict mode enabled

## Assumptions

What this system assumes to be true:

- Assumption 1
- Assumption 2
