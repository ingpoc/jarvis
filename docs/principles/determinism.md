# Determinism

Code verification over LLM judgment.

---

## The Problem

| LLM Judgment | Reality |
|--------------|---------|
| "Tests appear to pass" | ❌ Actually failed |
| "Looks like valid JSON" | ❌ Syntax error |
| "Server should be up" | ❌ Crashed on startup |
| "I think this works" | ❌ Doesn't work |

---

## The Solution

| Task | LLM (Bad) | Code (Good) |
|------|-----------|-------------|
| Tests passed? | "Tests appear to pass" | `pytest; echo $?` |
| Valid JSON? | "Looks like valid JSON" | `python -c "json.load(f)"` |
| Server running? | "Server should be up" | `curl -s localhost/health` |
| File exists? | "Should be there" | `test -f file && echo yes` |

---

## Rules

| Rule | Enforcement |
|------|-------------|
| Use exit codes (0/1) | Scripts return boolean |
| Version prompts | Semantic versioning |
| Hash-validate critical prompts | SHA256 check |
| Never trust LLM judgment | Always verify with code |

---

## Verification Patterns

```bash
# Good: Exit code
pytest tests/ && echo "PASS" || echo "FAIL"

# Bad: Output parsing
pytest tests/  # LLM reads output, judges

# Good: Health check
curl -sf http://localhost:8000/health

# Bad: Assume running
# Server started, should work
```

---

## Prompt Versioning

| Version | Change |
|---------|--------|
| 1.0.0 | Initial |
| 1.1.0 | Minor clarification |
| 2.0.0 | Breaking change |

```python
# Store with hash
prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]
versioned_prompt = f"{prompt}#v{version}-{prompt_hash}"
```

---

## Self-Verification Checklist

Before declaring complete:

- [ ] Tests pass (exit code 0)
- [ ] No runtime errors (check logs)
- [ ] Expected output produced (verify with code)
- [ ] Health checks pass (curl endpoints)
- [ ] Git clean (no uncommitted changes)

---

## Key Insight

> "LLM judgment is unreliable. Code verification is deterministic."
