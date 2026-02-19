# Harness Purpose Map

Purpose map to prevent harness bloat. Every enforced item must have a clear reason and a delete condition.

## Purpose Table

| Item | Owner | Trigger | Purpose | Prevents | Keep if | Remove when |
|---|---|---|---|---|---|---|
| `AGENTS.md` / `CLAUDE.md` core principles | Repo docs | Every session | Always-on behavior contract | Drift from expected workflow | Needed in most sessions | Rule unused for 30+ sessions and covered elsewhere |
| `scripts/agent_docs_lint.py` research gate | Repo lint | Docs/research updates | Enforce scored verdict structure | Incomplete/hand-wavy research integrations | Catches real failures | No findings for 60+ days and CI/hook signal is noisy |
| `scripts/agent_docs_lint.py` memory gate | Repo lint | Memory/research updates | Enforce typed memory schema + index | Unstructured continuity notes | Memory remains queryable and consistent | Replaced by stronger deterministic schema validator |
| `memory/` typed repository | Repo memory | Durable lessons/decisions | Versioned long-term continuity layer | Context death between sessions | Memory retrieval improves outcomes | Proven unused/low-value over measured review window |
| `scripts/validate_jarvis.py` governance check | Repo validation | Pre-commit/manual validation | Single entrypoint for core gates | Partial validation runs | Reduces missed checks | Superseded by CI-only gating with same reliability |
| `.githooks/pre-commit` | Git hook | Every commit | Automatic local enforcement | “Forgot to run checks” | Blocks bad commits early | Team standard moves to centralized pre-receive/CI and local hook becomes redundant |
| `docs/workflow/social-post-intake.md` | Workflow docs | Social URL research input | Efficient extraction cascade | Partial evidence from login-walled posts | Saves repeated extraction failures | Social source mix changes and process no longer used |

## Keep/Delete Review Cadence

Run every 30 days:

1. Count lint findings by category.
2. Count false positives and friction incidents.
3. Remove or relax any gate with low protection value and high friction.
4. Promote high-value recurring rules to concise always-on principles.

## Non-Negotiable Rule

No new gate without:

- at least one concrete failure trace
- clear owner
- measurable success metric
- explicit delete condition

