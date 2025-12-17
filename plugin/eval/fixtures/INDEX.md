# Fixture Index

Quick navigation and reference for Living Context evaluation fixtures.

## Directory Structure

```
fixtures/
├── README.md                      # Overview and detailed descriptions
├── VALIDATION_NOTES.md            # Expected validator behavior
├── INDEX.md                       # This file
├── healthy-project/               # PASS fixture
│   └── .ctx/
│       ├── knowledge.db
│       ├── graph.json
│       └── systems/example/.ctx/
│           ├── snapshot.md
│           ├── constraints.md
│           ├── decisions.md
│           ├── debt.md
│           └── adr/ADR-001.md
├── unhealthy-project/             # FAIL fixture (multiple issues)
│   └── .ctx/
│       ├── knowledge.db
│       ├── graph.json
│       ├── adr/                   # (orphan ADR location)
│       └── systems/example/.ctx/
│           ├── snapshot.md
│           ├── constraints.md
│           ├── decisions.md
│           ├── debt.md
│           └── adr/ADR-001.md
├── empty-project/                 # INIT fixture
│   └── README.md
├── partial-project/               # INCOMPLETE fixture
│   ├── .ctx/
│   │   ├── knowledge.db
│   │   └── graph.json
│   └── src/
│       ├── core/index.ts
│       └── systems/auth/index.ts
```

## Quick Reference

| Fixture | Status | Purpose | Database | Docs | Issues |
|---------|--------|---------|----------|------|--------|
| **healthy** | PASS | Reference | 1 sys, 1 ADR | Complete | None |
| **unhealthy** | FAIL | Error detection | 2 sys, 1 orphan | Stale, incomplete | 6+ problems |
| **empty** | SKIP | Initialization | None | None | None (expected) |
| **partial** | FAIL | Incomplete docs | 2 sys, 0 ADR | Missing | Undocumented |

## For Test Writers

### Testing Healthy Path

```python
from pathlib import Path

fixture_path = Path("cctx/plugin/eval/fixtures/healthy-project")
result = validator.validate(fixture_path)
assert result.status == "PASS"
assert len(result.errors) == 0
assert len(result.warnings) == 0
```

### Testing Error Detection

```python
fixture_path = Path("cctx/plugin/eval/fixtures/unhealthy-project")
result = validator.validate(fixture_path)
assert result.status == "FAIL"
assert "orphaned" in str(result.errors).lower()
assert "stale" in str(result.warnings).lower()
```

### Testing Initialization

```python
fixture_path = Path("cctx/plugin/eval/fixtures/empty-project")
result = init_command.run(fixture_path)
assert (fixture_path / ".ctx").exists()
assert (fixture_path / ".ctx" / "knowledge.db").exists()
```

### Testing Incremental Documentation

```python
fixture_path = Path("cctx/plugin/eval/fixtures/partial-project")
result = validator.validate(fixture_path)
assert result.status == "FAIL"
assert "missing" in str(result.errors).lower()

# After adding docs
result = validator.validate(fixture_path)
assert result.status == "PASS"
```

## File Locations for Test References

**Healthy Project:**
- `cctx/plugin/eval/fixtures/healthy-project/.ctx/knowledge.db`
- `cctx/plugin/eval/fixtures/healthy-project/.ctx/systems/example/.ctx/snapshot.md`

**Unhealthy Project:**
- `cctx/plugin/eval/fixtures/unhealthy-project/.ctx/knowledge.db` (2 systems, 1 orphan ADR)
- `cctx/plugin/eval/fixtures/unhealthy-project/.ctx/graph.json` (stale: 2025-06-01)

**Empty Project:**
- `cctx/plugin/eval/fixtures/empty-project/` (no .ctx/)

**Partial Project:**
- `cctx/plugin/eval/fixtures/partial-project/.ctx/knowledge.db` (2 systems)
- `cctx/plugin/eval/fixtures/partial-project/src/core/` (no docs)
- `cctx/plugin/eval/fixtures/partial-project/src/systems/auth/` (no docs)

## Database Contents

### healthy-project.knowledge.db

```sql
-- Systems
SELECT * FROM systems;
-- Result: 1 row
--   path: src/systems/example
--   name: Example System
--   updated_at: 2025-12-15

-- ADRs
SELECT * FROM adrs;
-- Result: 1 row
--   id: ADR-001
--   title: Use TypeScript for type safety
--   status: accepted
--   system: src/systems/example
```

### unhealthy-project.knowledge.db

```sql
-- Systems
SELECT * FROM systems;
-- Result: 2 rows
--   src/systems/example (updated 2024-06-15 - STALE)
--   src/systems/legacy (updated 2023-12-01 - VERY STALE)

-- ADRs
SELECT * FROM adrs;
-- Result: 1 row
--   id: ADR-001
--   status: accepted
--   system: src/systems/removed-system (ORPHANED - doesn't exist)
```

### partial-project.knowledge.db

```sql
-- Systems
SELECT * FROM systems;
-- Result: 2 rows
--   src/core
--   src/systems/auth (depends_on: src/core)

-- ADRs
SELECT * FROM adrs;
-- Result: 0 rows (no ADRs)
```

## Known Behavior

### healthy-project
- All validation checks pass
- Database and filesystem in sync
- All ADRs have corresponding files
- Can be used as golden-path reference

### unhealthy-project
- Multiple validation failures expected
- Orphaned ADR (DB references non-existent system)
- Stale documentation (6+ months old)
- Missing system documentation
- Extensive overdue debt
- Good for testing error detection and reporting

### empty-project
- No validation needed (no context)
- Good for testing init command
- Should create clean structure

### partial-project
- Validation fails due to missing documentation
- Systems registered but not documented
- No ADRs despite system complexity
- Good for testing incremental workflow

## Maintenance Notes

- **Do not modify** healthy-project unless fixing bugs
- **Keep unhealthy-project broken** (intentional for testing)
- **Do not add source code** to empty-project
- **Do not document** partial-project (testing incomplete state)

For updates, see VALIDATION_NOTES.md fixture refresh dates.

## See Also

- [README.md](README.md) - Detailed fixture descriptions
- [VALIDATION_NOTES.md](VALIDATION_NOTES.md) - Expected validator behavior
- [cctx/src/cctx/data/schema.sql](../../src/cctx/data/schema.sql) - Database schema
- [cctx/src/cctx/templates/](../../src/cctx/templates/) - Documentation templates
