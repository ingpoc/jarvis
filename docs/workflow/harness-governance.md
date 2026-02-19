# Harness Governance (Claude + Codex)

Defines what we enforce, what we keep optional, and where each type of knowledge belongs.

## Enforcement Scope

| Runtime | Mechanical enforcement | Policy enforcement |
|---------|-------------------------|--------------------|
| Claude Code | Hooks (`PreToolUse` / `PostToolUse`) | `CLAUDE.md` + rules + skills |
| Codex | Exec-policy / runtime settings (no `PreToolUse` equivalent) | `AGENTS.md` + `~/.codex/rules/*` |

## Always-On Core Principles

These belong in `AGENTS.md` / `CLAUDE.md` and should load every session:

1. Best idea wins (agent challenges assumptions).
2. Fail loud: no silent continuation after tool/data failure.
3. Use fallback chain before concluding blocked.
4. Store non-trivial failure→fix learnings in context graph.
5. Promote only validated research into always-on policy.

## Progressive vs Always-On

| Location | Put here when | Promotion test |
|----------|---------------|----------------|
| `docs/workflow/` | New/uncertain research, process notes | Works in 2+ sessions with measurable gain |
| `docs/principles/` / `docs/architecture/` | Validated repeatable pattern | Stable across contexts, low ambiguity |
| `AGENTS.md` / `CLAUDE.md` | High-frequency core principles only | Needed in most sessions, concise, durable |
| Skills (`SKILL.md`) | Multi-step situational workflows | 3+ concrete steps, non-trivial branching |
| Hooks / exec-policy | Deterministic enforcement needed | Repeated violations or high cost of failure |

## Tool Failure Policy (Cross-Runtime)

1. Attempt primary tool.
2. On failure/empty/truncated: apply configured fallback chain.
3. If still blocked: report explicit blocker (do not continue with missing evidence).
4. After successful workaround: store trace with `problem`, `root_cause`, `fix`, `validation`, `outcome`.

## Research Gate Enforcement (Cross-Runtime)

- Policy: `AGENTS.md` / `CLAUDE.md` require scored verdict first for URL/article research tasks.
- Deterministic gate: `python3 scripts/agent_docs_lint.py` enforces required `research-evaluator` sections for:
  - `docs/workflow/skipped/*.md`
  - `docs/workflow/*.md` files tagged with `**Evaluation**: research-evaluator`
- Outcome: same artifact contract is enforced for both Codex and Claude, independent of pre-tool hook differences.

## Memory Gate Enforcement (Cross-Runtime)

- Policy: durable decisions/lessons/preferences must be stored in typed `memory/` notes.
- Deterministic gate: `python3 scripts/agent_docs_lint.py` enforces:
  - required memory folder layout and templates
  - required note frontmatter (`title`, `date`, `category`, `priority`, `status`, `source`, `tags`)
  - category-folder consistency and priority/status enums
  - required note body sections and `memory/INDEX.md` coverage
- Outcome: continuity knowledge stays structured, searchable, and versioned without relying on reminders.

## Anti-Overengineering Guardrails

Do not enforce yet unless failure rate/volume justifies:

- Always-on multi-agent debate for every research article.
- Full autonomous PR self-review loops at low PR volume.
- Auto-promoting research claims into always-on rules without validation history.
