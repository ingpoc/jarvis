# MCP Tools Status Summary

**Date:** 2025-02-12 23:55 UTC
**Purpose:** Quick reference for which MCP tools actually work without permission

---

## ✅ Available & Working (No Permission Needed)

### 1. **Context7** - Documentation Queries
- `resolve-library-id` - Find library ID
- `query-docs` - Query framework docs

**Use for:** Framework/library documentation, code examples

---

### 2. **DeepWiki** - GitHub Repository Analysis
- `ask_question` - Ask about GitHub repos
- `read_wiki_structure` - Get repo topics
- `read_wiki_contents` - Read repo wiki

**Use for:** GitHub repo questions, architecture, contributing

---

### 3. **Apple Containers** (jarvis-container)
- `container_run` - Create container (limited)
- `container_list` - List containers
- `container_inspect` - Get container details
- `container_logs` - Get container logs
- `container_stats` - Get resource usage
- `container_stop` - Stop container
- `container_exec` - Execute in container (only if running)

**Limitations:** No interactive mode, containers exit immediately

**Use for:** Server testing, browser automation (NOT interactive dev)

**Documentation:** See `container-limitations.md`

---

### 4. **Git Operations** (jarvis-git)
- `git_add` - Stage files
- `git_branch` - Branch operations
- `git_clone` - Clone repos
- `git_commit` - Create commits
- `git_create_branch` - Create new branch
- `git_create_pr` - Create PRs (T3+)
- `git_diff` - Show diffs
- `git_log` - Show history
- `git_push` - Push to remote (T3+)
- `git_stash` - Stash/restore
- `git_status` - Show status

**Use for:** All git operations

---

### 5. **Browser Testing** (jarvis-browser)
- `browser_setup` - Install Playwright/Chromium
- `browser_navigate` - Navigate to URL and screenshot
- `browser_interact` - Click/fill/select on page
- `browser_test_run` - Run Playwright tests
- `browser_api_test` - Test REST APIs
- `browser_wallet_test` - Test Solana dApps

**Use for:** Web testing, UI automation, API testing

---

### 6. **Image Analysis** (4.5v MCP)
- `mcp__4_5v_mcp__analyze_image` - Analyze images with AI vision

**Use for:** Image analysis, screenshot interpretation

---

## 🔒 Requires Permission (Not Currently Available)

### Context Graph (HIGH PRIORITY)
- `context_store_trace` - Store decisions
- `context_query_traces` - Semantic search
- `context_list_traces` - List traces
- `context_get_trace` - Get trace details
- `context_update_outcome` - Update outcome
- `context_list_categories` - List categories

**Why Important:** Persistent learning across sessions

---

### Token-Efficient Tools (MEDIUM PRIORITY)
- `execute_code` - Execute code (98% token savings)
- `process_csv` - Process CSVs (99% token savings)
- `process_logs` - Process logs (99% token savings)
- `batch_process_csv` - Batch CSV processing (80% token savings)
- `search_tools` - Search tools (95% token savings)
- `get_token_savings_report` - Get savings report
- `list_token_efficient_tools` - List available tools

**Why Important:** Dramatically reduce token usage

---

### Slack Integration (LOW PRIORITY - If Needed)
- All slack tools (create_canvas, read_channel, send_message, etc.)

**Why Important:** Only if task involves Slack

---

### Comet Bridge (LOW PRIORITY)
- `comet_ask` - Send to Comet/Perplexity
- `comet_connect` - Connect browser
- `comet_mode` - Switch search mode
- `comet_poll` - Check status
- `comet_screenshot` - Screenshot
- `comet_stop` - Stop task

**Why Important:** Real-time web browsing (alternative to WebSearch)

---

### Zapier Integration (LOW PRIORITY - If Needed)
- `get_configuration_url` - Config URL
- `gmail_find_email` - Find emails
- `gmail_reply_to_email` - Reply
- `gmail_send_email` - Send
- `slack_send_private_channel_message` - Private Slack

**Why Important:** Only if automation needed

---

## 🎯 Tool Selection Guidelines

### Documentation Questions
```
1. Context7 (framework/lib docs)
2. DeepWiki (GitHub repos)
3. WebReader (LAST RESORT - too expensive)
```

### Code Execution
```
1. token-efficient/execute_code (if available)
2. Bash (current fallback)
```

### Container Operations
```
1. Local development (interactive work)
2. Apple Containers (server testing only - see limitations doc)
```

### Git Operations
```
1. jarvis-git tools (all operations)
```

### Web Research
```
1. WebSearch (general queries)
2. Comet Bridge (complex browsing tasks)
3. WebReader (LAST RESORT - expensive)
```

---

## 📋 Priority Checklist

### High Priority - Request Permission
- [ ] **Context Graph** - Persistent learning, semantic search of decisions

### Medium Priority - Test When Available
- [ ] **Token-efficient tools** - Especially execute_code and process_csv

### Low Priority - Request If Needed
- [ ] **Slack tools** - Only if Slack integration needed
- [ ] **Comet Bridge** - Only if complex web browsing needed
- [ ] **Zapier tools** - Only if automation needed

---

## 🔍 Current Status Summary

| Tool Category | Available | Working | Needs Permission |
|--------------|-----------|---------|------------------|
| Documentation (Context7) | ✅ | ✅ | ❌ |
| GitHub Analysis (DeepWiki) | ✅ | ✅ | ❌ |
| Containers (jarvis) | ✅ | ⚠️ Limited | ❌ |
| Git (jarvis-git) | ✅ | ✅ | ❌ |
| Browser Testing | ✅ | ❓ Not tested | ❌ |
| Token-efficient | ❌ | - | 🔒 |
| Context Graph | ❌ | - | 🔒 |
| Slack | ❌ | - | 🔒 |
| Comet Bridge | ❌ | - | 🔒 |
| Zapier | ❌ | - | 🔒 |

**Legend:** ✅ Available | ⚠️ Limited | ❓ Not tested | 🔒 Needs permission

---

**Last Updated:** 2025-02-12 23:55 UTC
**Action:** Request Context Graph permission for persistent learning
