# Living Context Plugin Evaluation Rubric

This rubric provides a standardized framework for LLM-as-judge evaluation of Living Context (`lctx`) CLI commands and plugin functionality.

## Overview

| Dimension | Weight | Focus Area |
|-----------|--------|------------|
| Execution | 30% | Reliability and correctness of command execution |
| Detection Accuracy | 25% | Quality of issue identification |
| Guidance Quality | 20% | Usefulness of messages and recommendations |
| State Modification | 15% | Correctness of artifact changes |
| Performance | 10% | Speed and resource efficiency |

**Pass Threshold**: Weighted average >= 70 (Grade C or better)

---

## 1. Execution (30%)

Evaluates whether commands run correctly and produce expected outputs.

### Criteria Table

| Score | Exit Codes | Stability | Output Format | Completion |
|-------|------------|-----------|---------------|------------|
| **5** | Correct exit code for all scenarios (0 success, non-zero errors) | Zero crashes, all exceptions handled gracefully | Perfect format matching (JSON valid, tables aligned, text properly formatted) | Completes well within expected time bounds |
| **4** | Correct exit codes with minor edge case issues | No crashes, rare unhandled warnings | Format correct with minor cosmetic issues | Completes within expected time |
| **3** | Exit codes mostly correct, some inconsistencies | Occasional non-fatal errors that recover | Format parseable but has inconsistencies | Completes but slower than expected |
| **2** | Exit codes frequently incorrect | Crashes on some inputs, partial recovery | Format broken in ways that affect parsing | Often times out or hangs |
| **1** | Exit codes always wrong or missing | Crashes consistently, no error handling | Output unparseable or missing | Fails to complete |

### Evaluation Checklist

- [ ] Success operations return exit code 0
- [ ] Validation failures return exit code 1
- [ ] System errors return exit code 2
- [ ] No unhandled exceptions in logs
- [ ] JSON output passes `jq` validation
- [ ] Table output has consistent column alignment
- [ ] Command completes within 10 seconds for typical projects

---

## 2. Detection Accuracy (25%)

Evaluates the quality of issue detection for validation and health check commands.

### Criteria Table

| Score | True Positives | False Positives | Completeness | Location Precision |
|-------|----------------|-----------------|--------------|-------------------|
| **5** | Identifies 100% of actual issues | Zero false positives | Finds all relevant issues across all files | Pinpoints exact file, line, and column |
| **4** | Identifies 90%+ of actual issues | Rare false positives (<5%) | Misses only obscure edge cases | Identifies file and approximate location |
| **3** | Identifies 75%+ of actual issues | Some false positives (<15%) | Misses some secondary issues | Identifies correct file |
| **2** | Identifies 50%+ of actual issues | Many false positives (<30%) | Misses many obvious issues | Sometimes wrong file |
| **1** | Identifies <50% of actual issues | Majority are false positives | Fails to detect most issues | Locations unreliable |

### Evaluation Checklist

- [ ] All seeded issues in test fixtures are detected
- [ ] No healthy files flagged as problematic
- [ ] Stale documentation correctly identified
- [ ] Missing required sections detected
- [ ] Orphaned references caught
- [ ] Issue locations match actual problem source

---

## 3. Guidance Quality (20%)

Evaluates the usefulness of error messages, warnings, and remediation suggestions.

### Criteria Table

| Score | Actionability | Context Relevance | Remediation Steps | Severity Levels |
|-------|---------------|-------------------|-------------------|-----------------|
| **5** | Messages provide specific, immediately actionable instructions | Every message directly relates to the detected problem | Clear, step-by-step fix instructions included | Severity perfectly matches issue impact |
| **4** | Messages suggest clear actions with minor ambiguity | Messages relevant with occasional extra context | Remediation included but may need interpretation | Severity generally appropriate |
| **3** | Messages indicate what's wrong but not how to fix | Most messages relate to actual problems | General guidance provided, specifics missing | Some severity misclassifications |
| **2** | Messages vague or overly technical | Messages often tangential to real issues | Remediation unhelpful or missing | Severity frequently wrong |
| **1** | Messages incomprehensible or misleading | Messages unrelated to actual problems | No remediation guidance | Severity random or missing |

### Evaluation Checklist

- [ ] Error messages explain what went wrong
- [ ] Warning messages explain potential consequences
- [ ] Each message includes a suggested fix
- [ ] Critical issues marked as errors, not warnings
- [ ] Informational messages don't flood output
- [ ] Technical jargon explained or avoided

---

## 4. State Modification (15%)

Evaluates correctness of file and database changes made by commands.

### Criteria Table

| Score | Artifact Creation | Database Consistency | Idempotency | Side Effects |
|-------|-------------------|---------------------|-------------|--------------|
| **5** | All artifacts created correctly in right locations | Database fully consistent after operations | Running twice produces identical results | Zero unintended changes |
| **4** | Artifacts correct with minor formatting differences | Database consistent, minor orphaned records | Idempotent with negligible differences | Rare, harmless side effects |
| **3** | Artifacts created but with structural issues | Database mostly consistent, some sync issues | Some differences on repeated runs | Occasional unintended changes |
| **2** | Missing or incorrectly placed artifacts | Database frequently inconsistent | Significant differences each run | Multiple side effects |
| **1** | Artifacts corrupt or completely wrong | Database corruption possible | Each run produces different state | Destructive side effects |

### Evaluation Checklist

- [ ] Created files match expected templates
- [ ] Database records have all required fields
- [ ] Foreign key relationships maintained
- [ ] `init` command idempotent (safe to run twice)
- [ ] `sync` command doesn't modify unchanged files
- [ ] Backup created before destructive operations
- [ ] No orphaned temporary files left behind

---

## 5. Performance (10%)

Evaluates execution speed and resource efficiency.

### Criteria Table

| Score | Execution Time | Memory Usage | CPU Usage | Scalability |
|-------|----------------|--------------|-----------|-------------|
| **5** | Completes in <2s for typical project | Memory stable, no growth over time | Minimal CPU spike, quick return to idle | Linear scaling with project size |
| **4** | Completes in <5s for typical project | Minor memory growth, cleaned up after | Moderate CPU usage, reasonable duration | Near-linear scaling |
| **3** | Completes in <10s for typical project | Noticeable memory growth, eventually freed | High CPU for extended period | Polynomial scaling (manageable) |
| **2** | Completes in <30s for typical project | Memory leak potential | CPU bound for duration | Poor scaling, degrades quickly |
| **1** | Takes >30s or times out | Memory exhaustion possible | CPU maxed, affects system | Unusable at scale |

### Evaluation Checklist

- [ ] `health` command completes in <5s for 50 systems
- [ ] `validate` command completes in <3s per file
- [ ] Memory usage stays under 100MB for typical projects
- [ ] No CPU spinning or blocking operations
- [ ] Large project (100+ systems) completes in <60s

---

## Scoring Calculation

### Formula

```
Final Score = (Execution * 0.30) + (Detection * 0.25) + (Guidance * 0.20) +
              (State * 0.15) + (Performance * 0.10)
```

### Grade Scale

| Grade | Score Range | Interpretation |
|-------|-------------|----------------|
| **A** | 90-100 | Excellent - Production ready, exceeds expectations |
| **B** | 80-89 | Good - Production ready with minor improvements needed |
| **C** | 70-79 | Acceptable - Meets minimum requirements, improvements recommended |
| **D** | 60-69 | Needs Improvement - Not production ready, significant issues |
| **F** | <60 | Fail - Major rework required |

---

## Evaluation Template

Use this template when evaluating a command:

```markdown
## Evaluation: `lctx <command>`

**Date**: YYYY-MM-DD
**Evaluator**: LLM/Human
**Test Case**: [fixture/scenario name]

### Scores

| Dimension | Score (1-5) | Weight | Weighted |
|-----------|-------------|--------|----------|
| Execution | X | 30% | X.XX |
| Detection Accuracy | X | 25% | X.XX |
| Guidance Quality | X | 20% | X.XX |
| State Modification | X | 15% | X.XX |
| Performance | X | 10% | X.XX |
| **Total** | - | 100% | **XX.XX** |

**Grade**: X

### Observations

**Execution**:
- [specific observations]

**Detection Accuracy**:
- [specific observations]

**Guidance Quality**:
- [specific observations]

**State Modification**:
- [specific observations]

**Performance**:
- [specific observations]

### Pass/Fail

- [ ] Weighted average >= 70
- [ ] No dimension scored 1
- [ ] No critical bugs observed

**Result**: PASS / FAIL
```

---

## Special Considerations

### Command-Specific Weights

Some commands may warrant adjusted weights:

| Command | Execution | Detection | Guidance | State | Performance |
|---------|-----------|-----------|----------|-------|-------------|
| `init` | 35% | 10% | 15% | 35% | 5% |
| `validate` | 25% | 35% | 25% | 5% | 10% |
| `health` | 25% | 30% | 20% | 10% | 15% |
| `sync` | 30% | 20% | 15% | 30% | 5% |

### Automatic Fail Conditions

Regardless of score, evaluation should FAIL if:

1. Command causes data loss
2. Database corruption detected
3. Security vulnerability exposed
4. Infinite loop or system hang
5. Exit code 0 returned on error

### Edge Case Handling

Award bonus points (up to +5 to final score) for:

- Graceful handling of malformed input
- Helpful messages for common mistakes
- Recovery from partial failures
- Clear timeout/cancellation support
