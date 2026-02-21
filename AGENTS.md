# Jarvis

Agent-first development. Humans steer, agents execute.

---

## Docs Index

```
[Jarvis Docs Index]|root: ./docs
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for Jarvis tasks
|TRIGGERS:
|daemon/ws changes → jarvis/debugging.md
|adding API → jarvis/api-reference.md
|tests failing → principles/determinism.md
|large data → principles/token-efficiency.md
|need a diagram / architecture diagram → workflow/draw-io-diagram-generation.md
|local models / OpenCode / Foundation Models → workflow/local-models-integration.md
|openclaw gateway / slack / model auth / sandbox / pairing issues → workflow/openclaw-integration.md
|openclaw delegation / openclaw workspace docs / openclaw rule sync → workflow/openclaw-jarvis-integration.md
|parallel subagents / git worktrees / containerized execution → workflow/opencode-parallel-worktrees.md
|autonomous workflow choice / self-evolving execution loop → workflow/jarvis-autonomous-evolution.md
|control plane / workspace-mcp-skills visibility → jarvis/api-reference.md
|scripts/validation/build → jarvis/scripts.md
|research paper/article/URL shared → load research-evaluator skill
|X/LinkedIn/Threads post shared → workflow/social-post-intake.md then research-evaluator
|memory/continuity/decisions/preferences requested → memory/README.md
|github accounts / gh auth / ingpoc / openclaw-gurusharan / GH_TOKEN / direnv → workflow/github-account-isolation.md
|tool failure / tool discovery / rule placement → workflow/harness-governance.md
|harness complexity / overengineering concerns → workflow/harness-purpose-map.md
|optimizing codex / claude code / claude agent sdk capabilities → capabilities/README.md
|new optimization proposal / should we add this capability → capabilities/checklist.md
|principles:{agent-first.md,progressive-disclosure.md,determinism.md,token-efficiency.md}
|updating docs / storing bugs / context graph → workflow/context-learning-loop.md
|workflow:{openai-harness.md,openai-unrolling-codex-agent-loop.md,openai-unlocking-codex-harness.md,langchain-improving-deep-agents-harness-engineering.md,vercel-agents-md.md,local-models-integration.md,openclaw-integration.md,openclaw-jarvis-integration.md,opencode-parallel-worktrees.md,jarvis-autonomous-evolution.md,context-learning-loop.md,harness-governance.md,harness-purpose-map.md,social-post-intake.md}
|capabilities:{README.md,checklist.md,codex.md,claude-code.md,claude-agent-sdk-python.md}
|architecture:{layers.md,taste-invariants.md}
|jarvis:{debugging.md,api-reference.md,conventions.md,scripts.md}
```

---

## Quick Start

| Task | Command |
|------|---------|
| Start | `./start-jarvis.sh` |
| Stop | `./stop-jarvis.sh` |
| Test WS | `python3 scripts/validate_local_models.py` |
| Lint | `python3 scripts/jarvis_api_lint.py` |

---

## Critical Rules

### GitHub Account (MANDATORY — check before any gh command)

**Always openclaw-gurusharan. Never ingpoc.**

Inherited `GH_TOKEN` from the launch shell overrides `GH_CONFIG_DIR`. Always extract explicitly:

```bash
export GH_CONFIG_DIR=~/.jarvis/gh-config
export GH_TOKEN=$(GH_CONFIG_DIR=~/.jarvis/gh-config GH_TOKEN= GITHUB_TOKEN= gh auth token --hostname github.com)
export GITHUB_TOKEN=$GH_TOKEN
# Verify:
GH_CONFIG_DIR=~/.jarvis/gh-config gh auth status 2>&1 | grep openclaw-gurusharan
```

If grep returns empty → wrong account. Repeat the export steps. See `docs/workflow/github-account-isolation.md`.

---

### WebSocket Format

```text
{"action": "<name>", "data": {...}, "id": "optional"}
```

**Common error**: Putting `message` at top level. Wrap in `data`.

---

## Principles

| Principle | Rule |
|-----------|------|
| Expert judgment | Apply expertise proactively. If there's a better way, say so — don't just execute. |
| Best idea wins | Reason with the user. Challenge assumptions. Right answer can come from either side. |
| Judgment over filing | Research gets evaluated, not just stored. Always load `research-evaluator` skill. |
| Research gate | For URL/article research tasks: produce scored verdict first (`Adopt/Adapt/Skip`) before updating rules/docs. |
| CLAUDE.md gate | Add here only if: silent failure without it + needed ≥80% sessions + fits ≤3 lines. Otherwise → `docs/` + trigger. |
| Self-improving harness | When agent struggles → identify what's missing → agent writes the fix into repo. |
| Fail loud | On tool/data failures: fallback or report blocker. Never continue with missing evidence. |
| Learn every fix | After non-trivial failure→fix, store a project-scoped context trace. |
| Memory-first continuity | Promote repeated durable learnings to `memory/` with typed notes and priorities. |

---

## Conventions

| Area | Rule |
|------|------|
| Git | No force-push main, no amend, no --no-verify |
| Tools | Token-efficient MCP for large data |
| Security | T2 (developer) - no prod deploys |
| Verify | Tests pass (exit 0), lint passes, daemon healthy |

---

## Delegated Coding Workflow (Global)

For tasks delegated from OpenClaw to Jarvis over A2A:

1. Provider is OpenCode only (`provider_type=opencode`).
2. Jarvis decides subagents, skills, workflow, worktrees, and containers autonomously at runtime from task context + docs.
3. Frontend/UI tasks are incomplete unless browser-based validation is included.
4. Large parallel work should follow `docs/workflow/opencode-parallel-worktrees.md`.
5. Keep OpenClaw as router/research layer; keep Jarvis as execution layer.

---

## Docs + Compression Loop

1. Jarvis must update `docs/` in the same session after any non-trivial implementation or failure->fix work (no reminder required).
2. Keep `AGENTS.md` compressed: only stable high-frequency rules and trigger/index pointers.
3. Put detailed procedures and rationale in `docs/workflow/*.md`; reference them from `AGENTS.md` instead of duplicating.
4. If a new repeated workflow appears, add one-line trigger in Docs Index and create/update the detailed workflow doc.
5. Do not mark work complete until docs and relevant index entries are synchronized with behavior changes.
