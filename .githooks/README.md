# Repo Git Hooks

Managed hooks for deterministic repo checks.

Install once per clone:

```bash
bash scripts/install_git_hooks.sh
```

Current hooks:

- `pre-commit`: runs `python3 scripts/validate_jarvis.py`
