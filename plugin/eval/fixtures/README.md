# Living Context Plugin Evaluation Fixtures

Test fixtures for evaluating the Living Context plugin's validation and initialization capabilities.

## Fixture Overview

### 1. healthy-project

A complete, well-maintained Living Context project used to test successful validation scenarios.

**Structure:**
```
healthy-project/
├── .ctx/
│   ├── knowledge.db          (1 system, 1 ADR - all valid)
│   ├── graph.json            (current, reflects actual systems)
│   └── systems/
│       └── example/
│           └── .ctx/
│               ├── snapshot.md        (complete and current)
│               ├── constraints.md     (well-defined invariants)
│               ├── decisions.md       (indexed ADR)
│               ├── debt.md            (tracked active debt)
│               └── adr/
│                   └── ADR-001.md     (TypeScript architecture decision)
```

**Characteristics:**
- All documentation is complete and current
- Database is consistent with filesystem
- All ADRs are referenced and have corresponding files
- All systems are registered and documented
- Validators should PASS

**Use Cases:**
- Baseline for healthy context
- Reference for well-documented systems
- Golden path testing

---

### 2. unhealthy-project

A project with multiple documentation issues used to test validator detection of problems.

**Structure:**
```
unhealthy-project/
├── .ctx/
│   ├── knowledge.db          (2 systems, 1 orphan ADR)
│   ├── graph.json            (outdated from June 2024)
│   └── systems/
│       └── example/
│           └── .ctx/
│               ├── snapshot.md        (references non-existent dependencies)
│               ├── constraints.md     (incomplete and outdated)
│               ├── decisions.md       (out of sync with database)
│               ├── debt.md            (extensive, overdue debt)
│               └── adr/
│                   └── ADR-001.md     (orphaned - references removed system)
```

**Problems:**
- Stale database (updated June 2024)
- Orphaned ADR in database (references `src/systems/removed-system`)
- System references non-existent dependencies
- Incomplete constraints documentation
- Extensive overdue technical debt (5 high-priority items)
- Out-of-sync decisions log
- 2 systems but missing documentation for `src/systems/legacy`

**Validators should DETECT:**
- Orphaned ADR records
- Stale documentation (mtime older than threshold)
- Inconsistent system references
- Missing system documentation
- Overdue debt items
- Database/filesystem desynchronization

**Use Cases:**
- Test error detection capabilities
- Verify validator rules and thresholds
- Test reporting of multiple issues
- Validate remediation workflows

---

### 3. empty-project

A minimal project with no Living Context documentation used to test initialization.

**Structure:**
```
empty-project/
├── README.md                 (project documentation only)
├── (no .ctx/ directory)
```

**Characteristics:**
- No `.ctx/` directory
- No documentation
- Clean slate ready for initialization
- No database or configuration

**Use Cases:**
- Test `context init` command
- Verify initial structure creation
- Test default configuration
- Baseline for new projects

---

### 4. partial-project

A project with partial documentation setup to test incremental documentation.

**Structure:**
```
partial-project/
├── .ctx/
│   ├── knowledge.db          (2 systems registered, 0 ADRs)
│   └── graph.json            (current, but systems lack docs)
├── src/
│   ├── core/
│   │   ├── index.ts          (implemented but undocumented)
│   │   └── (no .ctx/)
│   └── systems/
│       └── auth/
│           ├── index.ts      (implemented but undocumented)
│           └── (no .ctx/)
```

**Characteristics:**
- Global context exists with database
- Database has 2 systems registered
- No system-level `.ctx/` directories
- Source code exists but undocumented
- No ADRs
- Graph is complete but system docs are missing

**Issues:**
- Database describes systems that lack documentation
- Validators should flag missing system documentation
- Mismatch between registered systems and documented systems

**Use Cases:**
- Test detection of missing system documentation
- Verify incremental documentation workflows
- Test system registration vs. documentation sync
- Partial state recovery procedures

---

## Database Content

### healthy-project.knowledge.db

**Systems:**
- `src/systems/example` - Example System (created 2025-01-01, updated 2025-12-15)

**ADRs:**
- `ADR-001` - Use TypeScript for type safety (accepted, 2025-01-15)
  - System: `src/systems/example`
  - Tags: `architecture`, `typescript`

### unhealthy-project.knowledge.db

**Systems:**
- `src/systems/example` - Example System (stale: updated 2024-06-15)
- `src/systems/legacy` - Legacy System (very stale: updated 2023-12-01)

**ADRs:**
- `ADR-001` - Architecture Decision for Nonexistent System (accepted, 2025-01-15)
  - System: `src/systems/removed-system` (ORPHANED - does not exist)
  - Tag: `orphan`

### partial-project.knowledge.db

**Systems:**
- `src/core` - Core System (created 2025-01-01, updated 2025-12-10)
- `src/systems/auth` - Auth System (created 2025-02-01, updated 2025-12-10)
  - Depends on: `src/core`

**ADRs:**
- (none)

---

## Graph Content

### healthy-project

Single system with no dependencies. Graph is current (generated 2025-12-15).

### unhealthy-project

Three systems (two real, one removed):
- `src/systems/example` depends on `src/systems/legacy`
- `src/systems/removed-system` (orphaned)
- Graph is stale (generated 2025-06-01)

### partial-project

Two systems with dependency:
- `src/systems/auth` depends on `src/core`
- Graph is current (generated 2025-12-10)

---

## Testing Strategy

Use these fixtures to test:

1. **Healthy Validation**: empty, partial, healthy → all should pass
2. **Issue Detection**: unhealthy → all validators should trigger
3. **Initialization**: empty-project → test init workflow
4. **Incremental Docs**: partial-project → test adding missing docs
5. **Recovery**: unhealthy-project → test remediation workflows

---

## Fixture Maintenance

When updating fixtures:

1. Keep healthy-project in known-good state
2. Document any changes to unhealthy-project issues
3. Do not add real source code (keep empty-project minimal)
4. Update this README when adding test cases
