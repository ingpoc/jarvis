# 🤖 JARVIS Development Workflow

**Version:** 1.0.0
**Last Updated:** 2025-02-12
**Status:** Active - Under Continuous Improvement

---

## 📋 Overview

This is a **self-improving development workflow** designed for autonomous AI development. It evolves through continuous testing, measurement, and iteration.

### Core Principles

1. **Phased Execution** - 6 distinct phases from planning to learning
2. **Measured Outcomes** - Every task is timed and analyzed
3. **Persistent Learning** - Decisions stored in Context Graph for semantic retrieval
4. **Continuous Improvement** - Weekly workflow optimization based on metrics
5. **Hybrid Environment** - Local development + container testing for reliability

> **⚠️ IMPORTANT:** Apple Containers have MCP tool limitations. See [container-limitations.md](container-limitations.md) for details. Use local development for interactive work, containers for server/browser testing.

---

## 🔄 The 6-Phase Workflow

### Phase 1: Planning & Analysis
- [ ] Understand task requirements
- [ ] Break down into sub-tasks
- [ ] Identify dependencies and risks
- [ ] Select tech stack and tools
- [ ] Estimate complexity (Simple/Medium/Complex)
- [ ] **Query Context Graph** for similar past decisions

### Phase 2: Environment Setup

**Decision Point:** Container vs Local

```
Need interactive development (coding, debugging, iteration)?
├─ YES → Use LOCAL environment (faster, full interactivity)
└─ NO  → Use CONTAINER (server testing, browser automation, isolation)
```

- [ ] Decide: Local or Container based on task type
- [ ] **If Local:** Install dependencies, verify environment
- [ ] **If Container:**
  - [ ] Create Apple Container with appropriate image
  - [ ] Note: MCP tools lack interactive mode limitations
  - [ ] For server testing: Map ports, start long-running process
  - [ ] For browser testing: Use browser_test tools
- [ ] **Log setup time** to sessions/

> See [container-limitations.md](container-limitations.md) for when to use each approach

### Phase 3: Implementation
- [ ] Write code following test-driven development
- [ ] Implement features incrementally
- [ ] Add error handling and logging
- [ ] Follow language/framework best practices
- [ ] Commit frequently with meaningful messages
- [ ] **Track implementation time**

### Phase 4: Testing & Validation
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Use browser testing tools (Playwright) if web app
- [ ] Test API endpoints if applicable
- [ ] Fix failures (max 100 iterations)
- [ ] **Record test pass rate and time**

### Phase 5: Review & Quality Gates
- [ ] Run code review tools (if available)
- [ ] Verify all tests pass
- [ ] Check code coverage
- [ ] Document any hacks or TODOs
- [ ] Create git commit (if T2+ permissions)
- [ ] **Quality gate: Must pass all tests**

### Phase 6: Learning & Storage
- [ ] Store decisions to Context Graph
- [ ] Document what worked/failed
- [ ] Update workflow if improvements found
- [ ] Log metrics to sessions/
- [ ] Identify bottlenecks for next iteration
- [ ] **Mark task outcome: success/failure**

---

## 📊 Metrics to Track

For every task, log to `.jarvis/sessions/session-{date}.md`:

```yaml
task_id: task-{timestamp}
task_description: {brief description}
complexity: simple|medium|complex
start_time: {ISO timestamp}
phases:
  planning: {duration}
  setup: {duration}
  implementation: {duration}
  testing: {duration}
  review: {duration}
  learning: {duration}
total_time: {duration}
outcome: success|failure
tests_pass: true|false
bugs_found: {count}
bottlenecks: [{list}]
learnings: [{key insights}]
```

---

## 🧪 Testing the Workflow

### When to Test
- **After every 5 tasks** - Automated workflow review
- **Weekly** - Manual workflow optimization
- **Monthly** - Research new tools and patterns

### How to Test
1. Create isolated container
2. Run workflow on sample task
3. Compare metrics to baseline
4. If improved: Update workflow
5. If worse: Revert and analyze

---

## 🗂️ Context Graph Categories

Store decisions in these categories:
- `architecture` - System design decisions
- `framework` - Library/framework choices
- `testing` - Testing strategies
- `deployment` - Deployment patterns
- `error` - Error handling approaches
- `performance` - Optimization decisions
- `general` - Everything else

---

## 📦 Container Templates

See `.jarvis/templates/containers.json` for pre-configured specs:

- `node-20` - Node.js development
- `python-311` - Python development
- `rust-latest` - Rust development
- `fullstack` - Node + PostgreSQL + Redis
- `browser-test` - Playwright + Chromium

---

## 🔄 Improvement Schedule

```json
{
  "daily_review": "Check session logs for anomalies",
  "weekly_optimization": "Analyze bottlenecks, update workflow",
  "monthly_research": "WebSearch for AI dev best practices",
  "quarterly_overhaul": "Major workflow restructuring if needed"
}
```

---

## 🚀 Quick Start

1. Read this README
2. Check phase-specific docs in `phase-*.md`
3. Start a task
4. Follow phases 1-6
5. Store learnings
6. Improve workflow

---

## 📈 Version History

- **v1.0.0** (2025-02-12) - Initial workflow definition
  - 6-phase framework
  - Context Graph integration
  - Container-based testing
  - Metrics tracking

---

*This workflow is alive. It learns. It improves. Make it better.*
