# USER_WORKSPACE.md (Distilled)

Last updated: 2026-02-16
Purpose: Concise blueprint for making Jarvis a continuous learning engine, aligned with `.agent/ARCHITECTURE.md`.

## 1) Target Outcome

Jarvis should improve decision quality over time by:
1. Capturing execution outcomes (success/failure/rollback/approval events).
2. Converting outcomes into structured, reusable patterns.
3. Injecting only relevant patterns into future runs (progressive disclosure).
4. Adopting new techniques only after test/eval evidence.

## 2) Architecture Updates Required

## A. Learning Pipeline (Core)

Add/standardize a pipeline with explicit stages:
1. **Capture**: record task/tool/result events with correlation IDs.
2. **Reflect**: extract root-cause and prevention patterns from failures and high-signal successes.
3. **Store**: persist patterns as typed records (not raw prompt blobs).
4. **Retrieve**: score/select relevant patterns for new tasks.
5. **Apply**: inject minimal high-signal guidance into prompt/context.
6. **Validate**: compare outcomes before/after pattern use; update confidence.

## B. Pattern Store Schema (Required)

Each learned pattern should contain:
1. `pattern_id`
2. `type`: `failure` | `success` | `heuristic` | `research`
3. `scope`: `global` | `project` | `task-class`
4. `trigger_signature`: files/tools/errors/task tags
5. `recommendation`: actionable instruction
6. `confidence`: float
7. `evidence`: links to task ids, test results, artifacts
8. `first_seen`, `last_seen`, `frequency`
9. `status`: `active` | `deprecated` | `rejected`

## C. Reflection Worker (Controlled)

Use a dedicated reflection flow (can be in-process initially):
1. Trigger after terminal task states and major tool failures.
2. Produce structured pattern candidate.
3. Run validation gate before activation.
4. Never auto-promote low-confidence patterns.

## D. Research Ingestion Loop (Optional-but-useful)

For external articles/bookmarks/research:
1. Ingest source metadata and dedupe by URL/hash.
2. Extract claims into structured form.
3. Map claims to Jarvis capabilities and target workflows.
4. Run experiments/evals before promoting into active heuristics.

## E. SDK-Native Upgrades (High Priority)

1. `ClaudeSDKClient.interrupt()` for deterministic cancellation.
2. Per-channel/context session isolation to avoid context bleed.
3. Hook-first policy enforcement (PreToolUse/PostToolUse and relevant lifecycle hooks).
4. Subagents only for bounded specialized jobs (research/test/review), not default for every task.

## 3) Configuration Required

## A. Continuous Learning Controls

Add config group (example):

```json5
{
  "learning": {
    "enabled": true,
    "reflection_enabled": true,
    "min_confidence_to_apply": 0.65,
    "min_confidence_to_promote": 0.80,
    "max_patterns_in_prompt": 5,
    "pattern_decay_days": 30,
    "auto_deprecate_on_failures": true
  }
}
```

## B. A2A + Orchestrator Controls

```json5
{
  "a2a": {
    "enabled": true,
    "port": 9848,
    "auth_token_file": "~/.jarvis/a2a_token",
    "caller_tiers": {
      "openclaw:default": 1
    },
    "context_workspaces": {
      "jarvis-mac": "/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac"
    }
  }
}
```

## C. Progressive Disclosure Controls

```json5
{
  "context": {
    "progressive_disclosure": true,
    "inject_metadata_first": true,
    "max_injected_patterns": 5,
    "max_research_items": 2,
    "require_relevance_score": 0.70
  }
}
```

## D. Reliability + Performance Controls

```json5
{
  "runtime": {
    "task_timeout_secs": 0,
    "stale_task_recovery_secs": 0,
    "memory_guard_enabled": true,
    "streaming_required_for_long_tasks": true
  }
}
```

## 4) What Is Important vs Not Helpful

## Important (Keep)
1. Structured pattern learning from real execution outcomes.
2. Eval-gated adoption for research/heuristics.
3. Hook-governed policy and explicit failure semantics.
4. Progressive-disclosure context injection.
5. Deterministic state transitions and traceability.

## Not Helpful (Drop)
1. Repetitive narrative architecture prose with no implementation path.
2. Unstructured “store everything” memory behavior.
3. Blind auto-adoption of research claims.
4. Hardcoded heuristic routing rules when contract-based behavior is available.

## 5) Minimal Milestone Plan

1. Implement interrupt cancellation + task state mapping.
2. Implement pattern schema + reflection candidate generation.
3. Implement pattern retrieval/injection with disclosure limits.
4. Add eval gate for pattern promotion.
5. Add research ingestion dedupe + experiment path.

## 6) Acceptance Criteria

1. Repeated failure classes show measurable first-pass improvement over time.
2. No unbounded memory/context growth in long-lived sessions.
3. All promoted patterns are traceable to evidence and can be rolled back.
4. Continuous learning never bypasses trust/budget/policy gates.

## 7) Evidence Notes (DeepWiki-Backed)

1. `ingpoc/jarvis` DeepWiki indicates Jarvis already has:
   - MemoryStore
   - decision traces
   - self-learning loop hooks
   - idle processing
   This supports prioritizing structured learning/reflection instead of inventing a new memory base layer first.

2. `sst/opencode` DeepWiki confirms:
   - subagents, MCP integration, session continuity, and runtime controls
   This supports OpenCode-first architecture and prioritizing robust cancellation/timeout handling.

3. `ingpoc/jarvis` DeepWiki highlights container tooling limitations as a reliability bottleneck.
   This supports prioritizing runtime/cancellation/state correctness before advanced autonomous research workers.

4. OpenClaw architecture research indicates external-agent integration is capability/tool driven.
   This supports keeping Jarvis as execution engine and OpenClaw as orchestrator via explicit A2A contract.

## 8) Harness Engineering Insights (Applied to Jarvis)

Source: https://openai.com/index/harness-engineering/

The article reinforces that harness quality often drives larger gains than model changes alone.
Applied to Jarvis:

1. Harness-first optimization:
   - prioritize execution loop correctness, tool reliability, and feedback surfaces before model tuning.
   - implication: A2A correctness + cancellation + state mapping are top priority.

2. Keep instructions compact and navigable:
   - avoid oversized static prompts/docs as primary control mechanism.
  - implication: keep `.agent/ARCHITECTURE.md` concise, route detail through structured files and retrieval.

3. Increase agent legibility of system state:
   - agent should see clear diagnostics and progress signals.
   - implication: expose deterministic task status, errors, and artifact outputs in a unified schema.

4. Use reviewer loops for quality:
   - multi-agent review/test loops can improve reliability and speed when bounded.
   - implication: use subagents for targeted review/test/research validation, not for every turn.

5. Treat process as part of model performance:
   - throughput gains require stronger merge/test/quality gates.
   - implication: eval-gated promotion for learning patterns and workflow changes is mandatory.

6. Manage entropy actively:
   - stale memory/patterns degrade quality.
   - implication: decay/deprecate low-confidence patterns and keep memory store curated.
