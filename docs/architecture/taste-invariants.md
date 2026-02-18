# Taste Invariants

Mechanical rules for code quality.

---

## Current Invariants

| Rule | Linter | Error Message |
|------|--------|---------------|
| WebSocket messages use `data` wrapper | `jarvis_api_lint.py` | "Move params to data object" |

---

## Planned Invariants

| Rule | Category | Priority |
|------|----------|----------|
| Structured logging (JSON) | Observability | High |
| File size < 500 lines | Maintainability | Medium |
| No bare except | Error handling | High |
| Type hints on public APIs | Documentation | Medium |
| Docstrings on classes | Documentation | Low |

---

## Error Message Pattern

Error messages MUST include remediation instructions:

```
# Bad
ERROR: Invalid message format

# Good
ERROR: WebSocket message missing 'data' wrapper.
FIX: Use {"action": "chat", "data": {"message": "..."}} not {"action": "chat", "message": "..."}
```

This enables agents to self-fix.

---

## Adding New Invariants

1. **Identify pattern**: Good or bad behavior
2. **Write rule**: Clear, mechanical check
3. **Create linter**: Python script in `scripts/`
4. **Add remediation**: Error message with FIX instruction
5. **Test**: Run against codebase
6. **Document**: Add to this file

---

## Linter Template

```python
#!/usr/bin/env python3
"""Linter for [invariant name]."""

import sys
from pathlib import Path

def check_file(path: Path) -> list[str]:
    """Check file for violations. Return list of errors with FIX instructions."""
    errors = []
    # ... check logic
    return errors

def main():
    errors = []
    for py_file in Path("src").rglob("*.py"):
        errors.extend(check_file(py_file))

    if errors:
        for e in errors:
            print(e)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## Key Insight

> "In human-first workflow, rules feel pedantic. With agents, they become multipliers: once encoded, they apply everywhere at once."
