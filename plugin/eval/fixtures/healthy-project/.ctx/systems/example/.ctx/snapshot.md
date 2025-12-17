# Example System

> A well-documented example system for testing context validation.

## Purpose

This system demonstrates a properly documented Living Context module with all required documentation in place.

## Public API

| Export | Type | Description |
|--------|------|-------------|
| `getExample` | function | Returns example data |
| `ExampleConfig` | interface | Configuration for the example system |

## Dependencies

| System | Why |
|--------|-----|
| (none) | This system is independent |

## Dependents

| System | Uses |
|--------|------|
| (none) | No other systems depend on this |

## Files

| File | Purpose |
|------|---------|
| `index.ts` | Public exports |
| `types.ts` | Type definitions |

## Constraints

See `constraints.md` for detailed constraints.

- Must maintain immutability of exported config objects
- No side effects on module load

## Known Debt

None currently tracked.
