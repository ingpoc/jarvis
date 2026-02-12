# Phase 6: Learning & Storage

**Goal:** Capture insights and improve future workflow.

---

## Checklist

- [ ] **Store Decisions to Context Graph**
  ```bash
  context_store_trace(
    decision: "{what was decided and why}",
    category: "{architecture|framework|testing|deployment|error|performance|general}",
    outcome: "{success|failure|pending}"
  )
  ```

- [ ] **Update Workflow if Needed**
  - Did we discover a better approach?
  - Are any steps redundant?
  - Can we automate something?
  - Update relevant phase documents

- [ ] **Log Session Metrics**
  - Create session log in `.jarvis/sessions/`
  - Record time for each phase
  - Note bottlenecks
  - Document lessons learned

- [ ] **Identify Improvements**
  - What took longer than expected?
  - What could be streamlined?
  - What tools would help?
  - What patterns emerged?

- [ ] **Clean Up**
  - Stop and remove container
  - Archive logs
  - Commit workflow changes

- [ ] **Schedule Next Review**
  - Mark calendar for workflow review
  - Set improvement triggers

---

## Context Graph Storage Examples

### Framework Decision
```bash
context_store_trace(
  decision: "Chose FastAPI over Flask for REST API because of built-in async support, automatic OpenAPI docs, and better type hints",
  category: "framework",
  outcome: "success"
)
```

### Architecture Pattern
```bash
context_store_trace(
  decision: "Used repository pattern for data access to separate business logic from database operations",
  category: "architecture",
  outcome: "success"
)
```

### Testing Strategy
```bash
context_store_trace(
  decision: "Used Playwright for browser testing instead of Selenium because of better async support and faster execution",
  category: "testing",
  outcome: "success"
)
```

### Learning from Failure
```bash
context_store_trace(
  decision: "Tried to use SQLite for concurrent writes but hit database locked errors. Switched to PostgreSQL",
  category: "error",
  outcome: "failure"
)
```

---

## Session Log Template

Create file: `.jarvis/sessions/session-{YYYY-MM-DD}-{task-name}.md`

```markdown
# Session: {task_name}

**Date:** {YYYY-MM-DD HH:MM}
**Task ID:** task-{timestamp}
**Complexity:** {simple|medium|complex}

---

## Task Description
{what was built}

---

## Phase Metrics

| Phase | Planned | Actual | Variance |
|-------|---------|--------|----------|
| Planning | {min} | {min} | {+/-} |
| Setup | {min} | {min} | {+/-} |
| Implementation | {min} | {min} | {+/-} |
| Testing | {min} | {min} | {+/-} |
| Review | {min} | {min} | {+/-} |
| Learning | {min} | {min} | {+/-} |
| **TOTAL** | **{min}** | **{min}** | **{+/-}** |

---

## Context Graph Entries Stored
1. {category}: {decision_summary}
2. {category}: {decision_summary}

---

## What Worked Well
- {success_1}
- {success_2}

---

## What Didn't Work
- {issue_1}
- {issue_2}

---

## Bottlenecks Identified
1. {bottleneck_1} - {potential_solution}
2. {bottleneck_2} - {potential_solution}

---

## Ideas for Improvement
- {idea_1}
- {idea_2}

---

## Tools Used
- {tool_1}
- {tool_2}

---

## Next Session Goals
1. {goal_1}
2. {goal_2}

---

## Outcome
✅ SUCCESS / ❌ FAILURE

**Notes:** {additional notes}
```

---

## Workflow Improvement Triggers

Consider updating the workflow when:

### 🚨 Immediate Triggers
- Same step fails 3+ times
- New tool available that would help
- Critical bug in workflow discovered

### 📅 Weekly Triggers
- 5+ tasks completed
- Average phase time exceeds budget by 50%
- New pattern emerges across tasks

### 🔍 Monthly Triggers
- Research reveals better practices
- Team feedback received
- Major tool updates available

---

## Query Context Graph for Insights

### Find Similar Situations
```bash
# Before starting a task
context_query_traces(
  query: "REST API authentication patterns",
  limit: 5
)
```

### Review Past Decisions
```bash
# See what worked before
context_query_traces(
  query: "database choice for high throughput",
  category: "architecture",
  outcome: "success",
  limit: 5
)
```

### Learn from Failures
```bash
# What didn't work
context_query_traces(
  query: "testing issues",
  outcome: "failure",
  limit: 5
)
```

### List All Categories
```bash
# See what decision types we've made
context_list_categories()
```

---

## Cleanup Tasks

```bash
# Stop container
container_stop(
  container_id: "{container_id}",
  remove: true,
  force: false
)

# Commit workflow changes
git_add(".jarvis/")
git_commit("docs: update workflow based on learnings")

# Archive old sessions
# (move sessions older than 30 days to archive/)
```

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 5-10 minutes |
| Medium | 10-15 minutes |
| Complex | 15-30 minutes |

---

## 🎯 Workflow Complete!

Task is complete. Next steps:

1. Take a break if needed
2. Start next task or
3. Run workflow improvement cycle
4. Share learnings with team

---

*Remember: The workflow is never "done". It's always improving.*
