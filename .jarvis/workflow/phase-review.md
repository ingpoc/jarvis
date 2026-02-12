# Phase 5: Review & Quality Gates

**Goal:** Ensure code meets quality standards before completion.

---

## Checklist

- [ ] **Code Review**
  - Run automated review tools if available
  - Check for code smells
  - Verify naming conventions
  - Check for duplication

- [ ] **Test Verification**
  - All tests passing? ✅
  - Coverage >80%? ✅
  - No skipped tests? ✅

- [ ] **Documentation**
  - Code is commented where complex
  - README is updated
  - API documentation exists
  - Examples provided

- [ ] **Security Check**
  - No hardcoded secrets
  - Input validation present
  - Error messages don't leak info
  - Dependencies are up to date

- [ ] **Performance Check**
  - No obvious bottlenecks
  - Database queries optimized
  - No memory leaks
  - Response times acceptable

- [ ] **Git Commit**
  ```bash
  git_add("{files}")
  git_commit(
    message: "{clear, descriptive message}",
    co_authored_by: "Claude Opus 4.6 <noreply@anthropic.com>"
  )
  ```

---

## Quality Gates

### ❌ BLOCKERS (Must Fix)
- Tests failing
- Security vulnerabilities
- Critical bugs
- <60% code coverage

### ⚠️ WARNINGS (Should Fix)
- 60-80% code coverage
- Some code duplication
- Missing documentation
- Performance concerns

### ✅ ACCEPTABLE
- >80% code coverage
- All tests passing
- Good documentation
- Clean code structure

---

## Code Review Checklist

### Architecture
- [ ] Separation of concerns
- [ ] Modular design
- [ ] Clear data flow
- [ ] Scalable structure

### Code Style
- [ ] Consistent naming
- [ ] Proper indentation
- [ ] No dead code
- [ ] No commented-out code

### Error Handling
- [ ] Try-catch where needed
- [ ] Meaningful error messages
- [ ] Error logging present
- [ ] Graceful degradation

### Testing
- [ ] Tests cover requirements
- [ ] Edge cases tested
- [ ] Error cases tested
- [ ] Tests are readable

### Security
- [ ] Input validation
- [ ] Output encoding
- [ ] Authentication/authorization
- [ ] No secrets in code

---

## Review Template

```markdown
## Code Review: {task_name}

### Summary
{brief description of what was built}

### Quality Metrics
| Metric | Value | Status |
|--------|-------|--------|
| Tests Passing | {count}/{count} | ✅/❌ |
| Code Coverage | {percentage}% | ✅/⚠️/❌ |
| Lines of Code | {count} | - |
| Cyclomatic Complexity | {score} | ✅/⚠️ |

### What's Good
- {strength_1}
- {strength_2}

### What Could Be Better
- {improvement_1}
- {improvement_2}

### Issues Found
- {issue_1} (severity: high/medium/low)
- {issue_2} (severity: high/medium/low)

### Decision
✅ APPROVED / ⚠️ APPROVED WITH WARNINGS / ❌ REJECTED

### Next Steps
1. {action_1}
2. {action_2}
```

---

## Automated Review Tools

If available, use:
```bash
# Code review via MCP
review_diff(
  diff: "{git diff output}",
  context: "{task description}",
  reviewer: "claude-sonnet"
)

# Or review specific files
review_files(
  files: "{file_list}",
  context: "{task description}",
  reviewer: "claude-sonnet"
)
```

---

## Commit Message Format

```
{type}: {brief description}

{detailed explanation if needed}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Adding tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 5-10 minutes |
| Medium | 10-20 minutes |
| Complex | 20-40 minutes |

---

## Next Phase

Once review is complete and quality gates pass, proceed to **Phase 6: Learning & Storage**.
