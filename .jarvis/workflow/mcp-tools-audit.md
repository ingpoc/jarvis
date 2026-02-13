# MCP Tools Audit

**Date:** 2025-02-12 23:50 UTC
**Purpose:** Document which MCP tools work, which have issues, and when to use each

---

## ✅ Working Tools (Verified)

### 1. Context7 - Documentation Queries
**Server:** `context7`
**Status:** ✅ WORKING

**Tools:**
- `resolve-library-id` - Find library ID for documentation queries
- `query-docs` - Query framework/library documentation

**Usage:**
```python
# Step 1: Resolve library
resolve-library_id(libraryName="react", query="test")

# Step 2: Query documentation
query-docs(libraryId="/websites/react_dev", query="how to use useEffect")
```

**Best For:**
- Framework/library documentation
- Code examples
- API references
- Quick syntax lookup

**Token Cost:** Low to Medium

**When to Use:**
- ✅ First resort for framework/library questions
- ✅ When you need code examples
- ✅ API parameter lookup
- ❌ NOT for general web search

---

### 2. DeepWiki - GitHub Repository Analysis
**Server:** `deepwiki`
**Status:** ✅ WORKING

**Tools:**
- `ask_question` - Ask questions about GitHub repos
- `read_wiki_structure` - Get repo documentation topics
- `read_wiki_contents` - Read full wiki content

**Usage:**
```python
# Ask question about repo
ask_question(repoName="apple/container", question="How do I run containers?")

# Get wiki structure
read_wiki_structure(repoName="facebook/react")

# Read specific wiki
read_wiki_contents(repoName="vercel/next.js")
```

**Best For:**
- Understanding open-source projects
- Repository-specific questions
- Architecture and design decisions
- Contributing guidelines

**Token Cost:** Medium

**When to Use:**
- ✅ Questions about specific GitHub repos
- ✅ Understanding project architecture
- ✅ "How does X work in Y repo?"
- ❌ NOT for general coding questions

---

### 3. Apple Containers (jarvis-container) - PARTIAL
**Server:** `jarvis-container`
**Status:** ⚠️ LIMITED (See container-limitations.md)

**Working Tools:**
- `container_run` - Create container (exits immediately, no interactive mode)
- `container_list` - List containers with status
- `container_inspect` - Get detailed container info
- `container_logs` - Get container logs
- `container_stats` - Get resource usage
- `container_stop` - Stop/remove containers

**Broken/Limited Tools:**
- `container_exec` - Only works if container stays running (rare without interactive mode)

**Missing Parameters:**
- No `interactive` boolean flag
- No `tty` boolean flag
- No `command` parameter (runs default, exits immediately)

**Workaround Found:**
```python
# Create container with long-running process
container_run(
    image="ubuntu:latest",
    name="my-container",
    # Note: Still can't specify command, but some images have long-running defaults
)

# If container stays alive, you can exec:
container_exec(container_id="my-container", command="ls /")
```

**Best For:**
- ❌ Interactive development (use local instead)
- ✅ Server testing (start web server in container)
- ✅ Production environment simulation
- ✅ Browser testing (with server running)

**Token Cost:** Low

**When to Use:**
- ❌ NOT for interactive development
- ✅ For testing long-running servers
- ✅ For browser automation testing
- ✅ For production-like environment testing

**See Also:** `.jarvis/workflow/container-limitations.md` for full analysis

---

### 4. Git Operations (jarvis-git) - WORKING
**Server:** `jarvis-git`
**Status:** ✅ WORKING

**Tools:**
- `git_add` - Stage files
- `git_branch` - List/create branches
- `git_clone` - Clone repositories
- `git_commit` - Create commits
- `git_create_branch` - Create new branch
- `git_create_pr` - Create GitHub PRs (T3+)
- `git_diff` - Show diffs
- `git_log` - Show commit history
- `git_push` - Push to remote (T3+)
- `git_stash` - Stash/restore changes
- `git_status` - Show working tree status

**Usage:**
```python
# Standard workflow
git_status(path="/path/to/project")
git_add(path="/path/to/project", files="file1.txt file2.txt")
git_commit(path="/path/to/project", message="Add feature X")
git_push(path="/path/to/project", remote="origin", branch="main", set_upstream=true)
```

**Best For:**
- All git operations
- Version control workflow
- Commit/Push operations (with T3+ trust)

**Token Cost:** Low

**When to Use:**
- ✅ All git operations (status, add, commit, push, etc.)
- ✅ Creating PRs (if T3+ trust level)
- ✅ Standard git workflows

---

### 5. Code Review (jarvis-review) - NOT TESTED
**Server:** `jarvis-review`
**Status:** ❓ NOT TESTED YET

**Tools:**
- `review_diff` - Review code diffs
- `review_files` - Review specific files
- `review_pr` - Review GitHub PRs

**When to Use:**
- ✅ Independent code quality checks
- ✅ PR review assistance
- ✅ Diff analysis

**Note:** Should test to verify effectiveness

---

### 6. Token-Efficient Tools - NOT TESTED
**Server:** `token-efficient`
**Status:** ❓ NOT TESTED YET

**Tools:**
- `execute_code` - Execute Python/Bash/Node code (98% token savings)
- `process_csv` - Process CSV files efficiently (99% token savings)
- `process_logs` - Process log files with regex
- `batch_process_csv` - Process multiple CSVs (80% token savings)
- `search_tools` - Search available tools (95% token savings vs listing all)

**When to Use:**
- ✅ Code execution (instead of Bash tool)
- ✅ CSV/log processing (instead of Read tool)
- ✅ Finding tools by keyword (instead of loading all)
- ✅ Any time you want to minimize token usage

**Note:** These are CRITICAL for token efficiency. Should use them!

---

### 7. Slack Integration (claude.ai Slack) - PERMISSION REQUIRED
**Server:** `claude.ai Slack`
**Status:** 🔒 NEEDS PERMISSION

**Tools:**
- `slack_create_canvas` - Create Slack Canvas documents
- `slack_read_canvas` - Read Canvas content
- `slack_read_channel` - Read channel messages
- `slack_read_thread` - Read thread conversations
- `slack_read_user_profile` - Get user info
- `slack_schedule_message` - Schedule messages
- `slack_search_channels` - Find channels
- `slack_search_public` - Search public channels
- `slack_search_public_and_private` - Search all channels (needs permission)
- `slack_search_users` - Find users
- `slack_send_message` - Send messages
- `slack_send_message_draft` - Create message drafts

**When to Use:**
- ✅ If task involves Slack communication
- ✅ Documenting in Slack Canvases
- ✅ Reading/searching Slack history

**Note:** Must request user permission first

---

### 8. Zapier Integration (claude.ai Zapier MCP Servers) - NOT TESTED
**Server:** `claude.ai Zapier MCP Servers`
**Status:** ❓ NOT TESTED YET

**Tools:**
- `get_configuration_url` - Get Zapier config URL
- `gmail_find_email` - Find emails
- `gmail_reply_to_email` - Reply to emails
- `gmail_send_email` - Send emails
- `slack_send_private_channel_message` - Send to private Slack channels

**When to Use:**
- ✅ Email operations
- ✅ Private Slack messaging
- ✅ Automation workflows

**Note:** Should test to verify capabilities

---

### 9. Comet Bridge (comet-bridge) - NOT TESTED
**Server:** `comet-bridge`
**Status:** ❓ NOT TESTED YET

**Tools:**
- `comet_ask` - Send prompt to Comet/Perplexity (blocks, waits for response)
- `comet_connect` - Connect to Comet browser
- `comet_mode` - Switch Perplexity search mode
- `comet_poll` - Check agent status
- `comet_screenshot` - Capture screenshot
- `comet_stop` - Stop current agent task

**When to Use:**
- ✅ Real-time web browsing
- ✅ Complex research tasks
- ✅ Interactive web tasks
- ❌ NOT for simple web searches (use WebSearch instead)

**Token Cost:** Medium (blocks on agent response)

**Note:** Useful for tasks requiring actual browser interaction

---

### 10. Web Reader (web_reader) - HIGH TOKEN COST
**Server:** `web_reader`
**Status:** ⚠️ WORKS BUT EXPENSIVE

**Tools:**
- `webReader` - Fetch and convert URL to markdown

**Token Cost:** VERY HIGH (consumes lots of context tokens)

**When to Use:**
- ⚠️ LAST RESORT only
- ❌ NOT for documentation (use Context7)
- ❌ NOT for GitHub repos (use DeepWiki)
- ❌ NOT for web searches (use WebSearch)
- ✅ Only when URL is not available elsewhere

**Better Alternatives:**
- Documentation → Context7
- GitHub repos → DeepWiki
- General info → WebSearch
- Code execution → token-efficient/execute_code

---

## 🔒 Tools Requiring Permission

### Context Graph (context-graph)
**Status:** 🔒 NEEDS PERMISSION

**Tools:**
- `context_store_trace` - Store decisions with embeddings
- `context_query_traces` - Semantic search for decisions
- `context_list_traces` - List all traces
- `context_get_trace` - Get specific trace details
- `context_update_outcome` - Update trace outcome
- `context_list_categories` - List categories

**Why It's Important:**
- Semantic search of past decisions
- Persistent learning across sessions
- Pattern recognition in decision-making

**Action:** Request permission from user

---

## 📊 Tool Selection Priority (Decision Tree)

```
Need to X?
├─ Documentation/Code Examples
│  ├─ Framework/Library? → Context7 (FIRST)
│  └─ GitHub Repo? → DeepWiki
│
├─ Execute Code
│  ├─ Simple command? → token-efficient/execute_code (FIRST)
│  └─ Complex script? → Bash (if execute_code fails)
│
├─ Web Research
│  ├─ General search? → WebSearch (FIRST)
│  └─ Specific URL? → web_reader (LAST RESORT - high token cost)
│
├─ Git Operations
│  └─ Any git task? → jarvis-git tools
│
├─ Container Operations
│  ├─ Interactive dev? → Use LOCAL (container tools don't support)
│  └─ Server testing? → jarvis-container (with long-running process)
│
├─ Data Processing
│  ├─ CSV/Logs? → token-efficient/process_* tools (FIRST)
│  └─ Other files? → Read tool
│
└─ Slack/Email/Other
   └─ Specific task? → Check if MCP tool exists
      └─ If yes → Request permission if needed
      └─ If no → Use Bash/manual alternative
```

---

## 🎯 Key Learnings

1. **Context7 > WebReader** - Use Context7 for docs, NOT web_reader (token expensive)
2. **DeepWiki > WebSearch** - For GitHub repos, DeepWiki is better
3. **Token-efficient tools** - Use them! They save 80-99% tokens
4. **Container limitations** - Use local for dev, containers for servers only
5. **Ask for permissions** - Context Graph would be valuable for persistent learning

---

## 🔄 Future Actions

1. ✅ DONE - Audit all MCP tools
2. ⏭️ Test token-efficient tools (execute_code, process_csv, etc.)
3. ⏭️ Test Comet Bridge for web browsing
4. ⏭️ Request Context Graph permission (high value)
5. ⏭️ Update workflow README with tool selection guide

---

## 📋 Tool Categories

| Category | Tools | Status | Notes |
|----------|-------|--------|-------|
| **Documentation** | Context7, DeepWiki | ✅ Working | Use first! |
| **Execution** | token-efficient/execute_code, Bash | ⚠️ Partial | execute_code saves tokens |
| **Containers** | jarvis-container | ⚠️ Limited | No interactive mode |
| **Git** | jarvis-git | ✅ Working | Full git operations |
| **Web Research** | WebSearch, web_reader, Comet | ⚠️ Partial | web_reader is expensive |
| **Data Processing** | token-efficient/process_* | ❓ Not tested | Should save tokens |
| **Communication** | Slack, Zapier, Email | 🔒 Need perm | Ask user |
| **Learning** | Context Graph | 🔒 Need perm | High priority! |
| **Review** | jarvis-review | ❓ Not tested | Should test |

---

**Audit Date:** 2025-02-12 23:50 UTC
**Audited By:** JARVIS (autonomous development workflow)
**Next Audit:** After testing token-efficient tools
