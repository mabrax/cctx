# Fixture Validation Notes

Quick reference for expected validator behavior on each fixture.

## healthy-project

**Expected Status**: PASS

**Validation Checklist:**
- [x] Database exists and is valid
- [x] All ADRs in database have corresponding files
- [x] All systems have complete documentation
- [x] snapshot.md exists and is well-formed
- [x] constraints.md exists with defined invariants
- [x] decisions.md indexes all ADRs
- [x] debt.md tracks active debt appropriately
- [x] All ADR files reference valid systems
- [x] graph.json is current (dated 2025-12-15)
- [x] No orphaned records

**Files to Check:**
- `/healthy-project/.ctx/knowledge.db` - Contains 1 system, 1 ADR (all consistent)
- `/healthy-project/.ctx/systems/example/.ctx/*` - Complete documentation set

---

## unhealthy-project

**Expected Status**: FAIL (Multiple Issues)

**Issues Validators Should Detect:**

1. **Stale Database**
   - graph.json dated 2025-06-01 (6 months old)
   - snapshot.mtime: 2024-06-15 (18 months old)
   - Should trigger staleness warning

2. **Orphaned ADR**
   - ADR-001 in database references `src/systems/removed-system`
   - System does not exist in current systems
   - Should trigger orphan detection

3. **Inconsistent Dependencies**
   - snapshot.md lists `src/systems/removed-system` as dependency
   - Database shows same dependency
   - System no longer exists
   - Should trigger unresolved dependency error

4. **Missing System Documentation**
   - `src/systems/legacy` exists in database
   - No `.ctx/` directory for legacy system
   - Should trigger incomplete documentation error

5. **Incomplete Documentation**
   - constraints.md is bare-bones ("OUTDATED AND INCOMPLETE")
   - debt.md lists 5 high-priority items, none resolved
   - decisions.md notes missing files

6. **Documentation Quality Issues**
   - Multiple [MISSING] and [OUTDATED] markers
   - Incomplete tables and sections
   - References to non-existent files

**Files to Check:**
- `/unhealthy-project/.ctx/knowledge.db` - Contains 2 systems, 1 orphan ADR
- `/unhealthy-project/.ctx/graph.json` - Lists 3 systems (one doesn't exist)
- `/unhealthy-project/.ctx/systems/example/.ctx/*` - Multiple problems

**Expected Validator Output:**
```
ERRORS:
  - Orphaned ADR: ADR-001 references removed system
  - Unresolved dependency: src/systems/removed-system
  - Missing documentation: src/systems/legacy
  - Stale documentation: snapshot.md (180+ days old)

WARNINGS:
  - Overdue debt items: 5 high-priority items
  - Incomplete constraints documentation
  - Out-of-sync decisions log
  - Deprecated exports documented
```

---

## empty-project

**Expected Status**: PASS (for init testing)

**Validation:**
- [x] No `.ctx/` directory exists
- [x] No database
- [x] No documentation
- [x] Ready for initialization

**Expected Behavior:**
- Should pass pre-init validation (nothing to validate)
- Should be ready for `context init` command
- Init command should create clean structure

**Files:**
- `/empty-project/README.md` only (no context files)

---

## partial-project

**Expected Status**: FAIL (Missing Documentation)

**Issues Validators Should Detect:**

1. **Missing System Documentation**
   - `src/core` registered in database
   - No `.ctx/` directory at `src/core/.ctx/`
   - Should trigger missing documentation

2. **Missing System Documentation**
   - `src/systems/auth` registered in database
   - No `.ctx/` directory at `src/systems/auth/.ctx/`
   - Should trigger missing documentation

3. **Database/Filesystem Mismatch**
   - Database claims 2 systems
   - Filesystem shows only source files, no docs
   - Should trigger sync error

4. **No ADRs**
   - No `adr/` directory at global or system level
   - No ADRs despite systems being complex

**Expected Validator Output:**
```
ERRORS:
  - Missing system documentation: src/core/.ctx/
  - Missing system documentation: src/systems/auth/.ctx/
  - Database/filesystem desynchronization detected

WARNINGS:
  - No ADRs for 2 registered systems
  - Consider documenting architectural decisions
```

**Expected Remediation:**
- Run `context snapshot-init` to create system documentation
- Run `context adr-init` to create decision framework

---

## Quick Validation Script

```bash
# Test healthy project
validate /path/to/cctx/plugin/eval/fixtures/healthy-project/
# Expected: PASS

# Test unhealthy project
validate /path/to/cctx/plugin/eval/fixtures/unhealthy-project/
# Expected: FAIL (orphan, stale, missing, incomplete)

# Test empty project
validate /path/to/cctx/plugin/eval/fixtures/empty-project/
# Expected: PASS or SKIP (no context to validate)

# Test partial project
validate /path/to/cctx/plugin/eval/fixtures/partial-project/
# Expected: FAIL (missing documentation)
```

---

## Fixture Refresh Dates

These fixtures should be periodically updated:

- **healthy-project**: Update mtime annually to avoid false staleness warnings
- **unhealthy-project**: Keep old dates to test staleness detection
- **empty-project**: No changes needed (static)
- **partial-project**: Keep incomplete to test remediation workflows

---

## Adding New Fixtures

If adding test fixtures:

1. Create directory structure
2. Add README explaining fixture purpose
3. Populate with realistic data
4. Document expected validator behavior
5. Add entry to this file with validation notes
6. Test with actual validator before committing
