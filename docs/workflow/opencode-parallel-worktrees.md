# OpenCode Parallel Worktrees for Jarvis

Use this workflow when Jarvis needs to execute large tasks with parallel subagents using isolated git worktrees and containers.

## Research Verdict (2026-02-20)

**Score**: 11/12 — **Adopt**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Novelty | 2/3 | Parallel worktrees are known, but applying them to Jarvis+OpenCode with strict gating is new in this stack |
| Relevance | 3/3 | Directly targets long-running delegated work and reliability |
| Claim validity | 3/3 | Claude Code docs + OpenCode docs + DeepWiki session architecture align |
| Implementation cost | 3/3 | Incremental rollout with clear phases |
| Total | 11/12 | Adopt |

## Sources

- Claude Code workflow guidance (parallel sessions + worktrees): https://code.claude.com/docs/en/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees
- Claude Code memory/import model: https://code.claude.com/docs/en/memory
- Claude Code subagents: https://docs.anthropic.com/en/docs/claude-code/sub-agents
- OpenCode agents/subagents: https://opencode.ai/docs/agents/
- OpenCode skills discovery: https://opencode.ai/docs/skills
- OpenCode ACP: https://opencode.ai/docs/acp/
- OpenCode GitHub integration (branch/PR/issue automation): https://opencode.ai/docs/github/
- OpenCode repository: https://github.com/sst/opencode
- OpenCode architecture via DeepWiki (sessions/routes/events): https://deepwiki.com/search/how-does-opencode-support-mult_e8d51542-62e2-412b-91c3-4c82ceaba730

## Goal

Enable Jarvis to execute big tasks through multiple specialized subagents, each running:

1. its own git worktree,
2. its own container runtime,
3. its own OpenCode session,
4. and deterministic quality gates before merge/PR.

## Non-Negotiables

1. Delegated execution tasks use `provider_type=opencode` only.
2. Every subagent runs in an isolated worktree path.
3. UI work requires browser-based MCP validation before task completion.
4. No direct merge to `main`; only branch + PR flow.
5. All non-trivial failure->fix paths are persisted to context graph.

## Architecture

| Layer | Responsibility | Owner |
|------|----------------|-------|
| Manager (Jarvis Orchestrator) | Plan DAG, spawn/cancel workers, collect artifacts, enforce gates | `jarvis.orchestrator` |
| Worker Subagent | Execute one bounded subtask in its own worktree/container | OpenCode session |
| Evidence/Gating | Run tests/lint/api/browser/security checks with pass/fail contract | Jarvis verifier pipeline |
| GitHub Handoff | Push branch, open/update PR, open issue on blocker | Jarvis GitHub integration |
| Learning Loop | Query/store/update traces for repeated patterns | Context graph MCP |

## Subagent Roles

| Role | Write Access | Required Checks | Output |
|------|--------------|-----------------|--------|
| `implementer` | Yes | unit + lint + typecheck | code diff + notes |
| `test-runner` | Yes | integration + regression | failing/passing evidence |
| `browser-tester` | Limited (test harness only) | browser MCP scenario checks | screenshots + console logs |
| `security-reviewer` | No by default | SAST/dependency/security checklist | findings report |
| `code-reviewer` | No by default | architecture/style/risk review | review comments |

## Execution Flow

1. Manager creates root branch and planning record.
2. For each parallelizable node, manager creates `git worktree add` branch.
3. Manager starts container per worktree and initializes OpenCode session.
4. Worker runs task with role-scoped instructions and tool permissions.
5. Worker emits heartbeat and progress artifacts.
6. On completion, manager runs gate bundle.
7. If gates pass, branch is pushed and PR is opened or updated.
8. If gates fail, manager either loops fix attempts or opens blocker issue.
9. Manager summarizes outcomes and updates context graph traces.

## Worktree + Container Contract

| Item | Contract |
|------|----------|
| Worktree path | `tmp/worktrees/<task-id>/<role>` |
| Branch name | `jarvis/<task-id>/<role>` |
| Container label | `jarvis-task=<task-id>,jarvis-role=<role>` |
| Session metadata | include `task_id`, `role`, `branch`, `worktree_path` |
| Cleanup policy | delete container + worktree only after artifact sync |

## OpenCode Session Contract

For each worker session:

1. create session with role instruction + bounded objective,
2. stream prompt execution with timeout + heartbeat,
3. persist session IDs in manager state,
4. support cancel/retry without losing evidence,
5. fork only when a role needs internal parallel decomposition.

## Required Gate Bundle

| Gate | Applies to | Hard Fail |
|------|-------------|-----------|
| Format/Lint/Typecheck | all code changes | yes |
| Unit tests | all feature changes | yes |
| Integration/API checks | backend/shared flows | yes |
| Browser MCP checks | frontend/UI tasks | yes |
| Security scan/review | dependency/auth/network changes | yes |

## Browser Testing Standard

For frontend deliverables, worker must verify:

1. app boots cleanly (`npm run dev` or equivalent),
2. key flow works in browser automation,
3. no blocking console/network errors,
4. screenshots/logs attached in artifacts.

If browser checks are missing, status cannot be `completed`.

## PR/Issue Handoff

| Scenario | Action |
|----------|--------|
| All gates pass | push branch + open/update PR with artifacts |
| Repeated gate failures | open issue with repro + logs + failing checks |
| External dependency blocked | open issue and mark task `blocked` |

PR body minimum:

1. summary of subtask objective,
2. gates run with pass/fail evidence,
3. risk/rollback notes,
4. linked issues and task IDs.

## Rollout Plan

1. Phase 1: single-worker containerized worktree flow + gates.
2. Phase 2: two-role parallel flow (`implementer` + `code-reviewer`).
3. Phase 3: full role matrix with browser/security reviewers.
4. Phase 4: auto PR/issue handoff and trace-driven optimization.

## Open Questions to Resolve in Code

1. Preferred container manager abstraction in Jarvis runtime.
2. Branch/worktree garbage collection cadence and retention.
3. Max parallel workers per machine profile.
4. Retry budgets by gate type (test vs browser vs network).

## Memory Promotion

**Memory Action**: Promote this as default big-task execution pattern for Jarvis delegated engineering work. Keep OpenClaw as router/research layer, Jarvis as OpenCode execution layer.
