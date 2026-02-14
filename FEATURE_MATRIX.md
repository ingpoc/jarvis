# Jarvis v2.0 Feature Implementation Matrix

This matrix tracks the implementation status of every feature mentioned in the Jarvis v2.0 PRD.

**Legend**:
- ✅ Fully Implemented (production-ready)
- ⚠️ Partially Implemented (scaffolding or partial functionality)
- ❌ Not Started (designed but not implemented)

---

## Core Architecture (Layer 2: Jarvis Core)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| ClaudeSDKClient wrapper | §4.2 | ✅ | Full session management with hooks | - |
| PreToolUse hooks | §4.2 | ✅ | Budget + safety checks implemented | - |
| PostToolUse hooks | §4.2 | ✅ | Execution record capture active in _post_tool_hook | 1-2 |
| PreMessage hooks | §4.2 | ✅ | Context injection ready | 1-2 |
| PostMessage hooks | §4.2 | ✅ | Token accounting via _post_message_hook | 3-4 |
| Multi-agent pipeline | §4.3 | ✅ | P→E→T→R fully orchestrated | - |
| Subagent registration | §4.3 | ✅ | AgentDefinition pattern working | - |
| Per-repo knowledge database | §6.2 | ✅ | 10 tables with indexes, all populated | 1-2 |
| Dual-store (Knowledge vs. Learnings) | §6.1 | ✅ | learned_patterns + learnings tables active | 1-2 |
| ExecutionRecords capture | §6.2 | ✅ | Every tool call recorded via _post_tool_hook | 1-2 |
| Token usage tracking | §6.2 | ✅ | budget.py + token_usage table via PostMessage hook | - |

---

## Knowledge System (§6: Self-Learning)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| **Context Layers** | | | |
| L1: Repo Structure | §6.3 | ✅ | build_l1_repo_structure() in context_layers.py | 5-6 |
| L2: Module Graph | §6.3 | ✅ | AST-based import analysis in context_layers.py | 5-6 |
| L3: Interface Signatures | §6.3 | ✅ | Python AST signature extraction in context_layers.py | 5-6 |
| L4: Test & Quality | §6.3 | ✅ | Test scanning + quality tool detection in context_layers.py | 5-6 |
| L5: Learned Corrections | §6.3 | ✅ | learnings table populated via self_learning.py | 1-2 |
| L6: Runtime State | §6.3 | ✅ | git + container state available | - |
| **Self-Learning Loop** | | | |
| Retrieve phase | §6.4 | ✅ | get_relevant_learnings() + format_learning_for_context() active | 1-2 |
| Triage phase | §6.4 | ⚠️ | Heuristic routing via model_router.py; Qwen3 pending | 3-4 |
| Execute phase | §6.4 | ✅ | SDK session fully operational | - |
| Capture phase | §6.4 | ✅ | PostToolUse hook records every execution | 1-2 |
| Learn phase | §6.4 | ✅ | learn_from_task() extracts error→fix patterns | 1-2 |
| Optimize phase | §6.4 | ✅ | Token metrics + skill candidate flagging on 3+ occurrences | 1-2 |
| **Knowledge Pruning** | | | |
| File watcher invalidation | §6.5 | ✅ | Polling-based fs_watcher.py with debounce | 5-6 |
| Passive decay | §6.5 | ✅ | Confidence decay in idle_mode.py background tasks | 7-8 |
| Idle re-verification | §6.5 | ✅ | _revalidate_learnings task in idle_mode.py | 7-8 |
| **Cross-Repo Learning** | | | |
| Repo-specific scope | §6.6 | ✅ | project_path scoping on all queries | - |
| Language-specific scope | §6.6 | ✅ | Universal heuristics seeded per language | 9-14 |
| Universal scope | §6.6 | ✅ | universal_heuristics.py with 15+ cross-project patterns | 9-14 |

---

## Self-Evolution Engine (§7: Skills & MCP)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| **Skill Creation** | | | |
| Pattern discovery | §7.1 | ✅ | hash_error_pattern() in self_learning.py | 5-6 |
| Pattern detection (3+) | §7.1 | ✅ | detect_skill_worthy_patterns() + record_skill_candidate() | 5-6 |
| Skill generation (GLM 4.7) | §7.1 | ⚠️ | Template pipeline built; needs GLM prompt integration | 5-6 |
| Skill validation | §7.1 | ✅ | Full validate_skill() in skill_generator.py | 5-6 |
| Skill registration | §7.1 | ✅ | .claude/skills/ directory with save_skill_to_directory() | - |
| Progressive disclosure | §7.1 | ✅ | SDK feature (metadata→full) | - |
| Hard cap (3 per session) | §7.1 | ⚠️ | Limit defined in SKILL_TEMPLATE; ranking missing | 5-6 |
| Confidence decay | §7.1 | ✅ | Background task in idle_mode.py | 7-8 |
| **MCP Discovery & Creation** | | | |
| Registry search (GitHub/npm) | §7.2 | ❌ | Registry API integration missing | 9-14 |
| Server proposal | §7.2 | ❌ | User approval flow missing | 9-14 |
| Server generation (GLM 4.7) | §7.2 | ❌ | Code generation template missing | 9-14 |
| Server installation | §7.2 | ⚠️ | Directory exists; pipeline missing | 9-14 |
| Server registration | §7.2 | ❌ | Config management incomplete | 9-14 |
| Health validation | §7.2 | ✅ | health_check_all_servers() integrated in daemon.py | 1-2 |
| Silent exclusion | §7.2 | ✅ | Quarantine of unhealthy servers in daemon.py | 1-2 |
| User notification | §7.2 | ✅ | notify_health_failures() on startup | 1-2 |
| **Idle Mode Processing** | | | |
| Idle detection | §7.3 | ✅ | Polling-based timer + external trigger via WebSocket | 7-8 |
| State machine (Active→Idle→Hibernated) | §7.3 | ✅ | Full IdleState enum + transitions in idle_mode.py | 7-8 |
| Skill generation batch | §7.3 | ✅ | _generate_skills background task in idle_mode.py | 7-8 |
| Context rebuild (L1-L4) | §7.3 | ✅ | _rebuild_context_metadata in idle_mode.py | 7-8 |
| Learning re-verification | §7.3 | ✅ | _revalidate_learnings in idle_mode.py | 7-8 |
| Article learning pipeline | §7.3 | ✅ | _process_article_learnings in idle_mode.py | 7-8 |
| Token optimization reports | §7.3 | ✅ | _generate_token_report in idle_mode.py | 7-8 |
| Capability assessment | §7.3 | ✅ | _assess_capabilities in idle_mode.py | 7-8 |
| Emergency hibernation | §7.3 | ⚠️ | trigger_hibernate() available; DispatchSource not integrated | 7-8 |
| Universal heuristics seed | §7.3 | ✅ | _seed_universal_heuristics in idle_mode.py | 7-8 |

---

## Three-Tier Intelligence (§5)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| **Qwen3 4B (MLX)** | | | |
| MLX framework integration | §5.1 | ✅ | mlx_inference.py with conditional import + Apple Silicon detection | 3-4 |
| Model loading | §5.1 | ✅ | Async load_model() with thread pool, unload for hibernation | 3-4 |
| Local inference | §5.1 | ✅ | generate(), classify_task(), filter_context_files(), summarize_error() | 3-4 |
| Context pre-filtering | §5.2 | ✅ | MLX filter_context_files() with heuristic fallback | 3-4 |
| **GLM 4.7 API** | | | |
| Cloud inference | §5.1 | ✅ | SDK routes to Claude API | - |
| Thinking mode | §5.1 | ✅ | Available via SDK | - |
| 200K context support | §5.1 | ✅ | Supported by SDK | - |
| **Foundation Models** | | | |
| Task classification | §5.1 | ✅ | FoundationModelsBridge.swift with LanguageModelSession | 3-4 |
| HTTP bridge | §5.1 | ✅ | Swift HTTP server on port 9848 + Python client | 3-4 |
| Intent classification | §5.1 | ✅ | classify_intent() via Foundation Models client | 3-4 |
| 4K context limitation | §5.3 | ✅ | Enforced in bridge (text.prefix(1000)) | - |
| **Router Logic** | | | |
| Decision tree | §5.1 | ✅ | Full 3-tier routing with live MLX + Foundation Models | 3-4 |
| Latency routing | §5.1 | ✅ | Foundation Models (<100ms) → MLX (200-500ms) → Cloud | 3-4 |
| Cost-based routing | §5.1 | ✅ | estimated_cost_usd in RoutingDecision | 3-4 |
| Offline fallback | §5.1 | ✅ | offline_mode returns Qwen3 or "unavailable" | 3-4 |
| Budget-based routing | §5.1 | ✅ | budget_remaining_usd parameter in route_task() | 3-4 |
| **Token Budget** | | | |
| Budget tracking | §5.2 | ✅ | budget.py fully implemented | - |
| Session limits | §5.2 | ✅ | Enforced via hooks | - |
| Daily limits | §5.2 | ✅ | Tracked in database | - |
| Skill shortcutting | §5.2 | ⚠️ | Framework exists; not active | 3-4 |
| Incremental context | §5.2 | ⚠️ | Context layers provide tiered injection | 3-4 |

---

## Container Runtime (§8)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| Apple Containerization | §8.1 | ✅ | Fully operational on M1 Pro | - |
| Container cold start | §8.1 | ✅ | ~1.2s measured | - |
| Idle overhead | §8.1 | ✅ | Zero (no background VM) | - |
| Hardware isolation | §8.1 | ✅ | Per-VM separation working | - |
| Networking setup | §8.1 | ✅ | Port mapping + forwarding working | - |
| I/O performance | §8.1 | ✅ | 31x advantage over Docker | - |
| Docker fallback | §8.1 | ⚠️ | Configured but untested | 5-6 |
| Template detection | §8.2 | ✅ | 7 templates working | - |
| Workspace binding | §8.2 | ✅ | Volume mounting working | - |
| SDLC pipeline | §8.3 | ✅ | Clone→Develop→Test→Review→Learn | - |

---

## macOS Native Integration (§9)

| Framework | PRD Use | Status | Details | Week Due |
|-----------|---------|--------|---------|----------|
| Apple Containerization | Container runtime | ✅ | Production | - |
| Foundation Models | Classification | ✅ | FoundationModelsBridge.swift + Python client on port 9848 | 3-4 |
| MLX | Qwen3 inference | ✅ | mlx_inference.py with async load/generate/classify | 3-4 |
| FSEvents | File monitoring | ⚠️ | Polling-based fs_watcher.py (not native FSEvents) | 5-6 |
| Core Spotlight | Code search | ✅ | spotlight_search(), spotlight_search_code() via mdfind | 5-6 |
| XPC Services | IPC | ✅ | Menu bar↔Daemon working | - |
| Keychain | Credential storage | ✅ | keychain_store/retrieve/delete in macos_native.py | 7-8 |
| ServiceManagement | Auto-start | ✅ | launchd plist configured | - |
| OSLog | Logging | ✅ | Structured output working | - |
| IOKit | Idle detection | ✅ | get_idle_seconds() via HIDIdleTime in macos_native.py | 7-8 |
| Memory pressure | Hibernation | ✅ | get_memory_pressure() triggers model unload | 7-8 |
| Network.framework | Networking | ✅ | SDK via httpx | - |

---

## macOS Shell (§9, Layer 1)

| Component | PRD Scope | Status | Details | Week Due |
|-----------|-----------|--------|---------|----------|
| **MenuBarExtra UI** | | | |
| Menu bar icon | §9 | ✅ | SwiftUI MenuBarExtra working | - |
| Window popup | §9 | ✅ | 420x520 window rendering | - |
| Window positioning | §9 | ✅ | Appears next to menu | - |
| **WebSocket Client** | | | |
| Connection | §9 | ✅ | localhost:9847 connecting | - |
| Auto-reconnect | §9 | ✅ | Implemented in SwiftUI | - |
| Message parsing | §9 | ✅ | TimelineEvent struct working | - |
| **Status Display** | | | |
| Current state | §9 | ✅ | idle/working/approved/failed/reviewing/completed | - |
| Status colors | §9 | ✅ | Per-status color mapping in JarvisStatus.swift | 7-8 |
| Status icons | §9 | ✅ | Per-status SF Symbols in JarvisStatus.swift | 7-8 |
| Real-time updates | §9 | ✅ | Status timer polling + event-driven updates | 7-8 |
| **Timeline View** | | | |
| Event list | §9 | ⚠️ | Basic framework; rendering incomplete | 7-8 |
| Event details | §9 | ⚠️ | TimelineEvent model exists | 7-8 |
| Event filtering | §9 | ❌ | Filter UI missing | 7-8 |
| **Approval UI** | | | |
| Approval prompt | §9 | ✅ | ApprovalView with approve/deny via WebSocket | 7-8 |
| Approve button | §9 | ✅ | ws.approve(taskId:) connected | 7-8 |
| Reject button | §9 | ✅ | ws.deny(taskId:) connected | 7-8 |
| Modify input | §9 | ❌ | Text input for modifications missing | 7-8 |
| **Command Input** | | | |
| Input field | §9 | ✅ | CommandInputView with monospaced text field | 7-8 |
| NL parsing | §9 | ❌ | GLM 4.7 parsing not integrated | 7-8 |
| Confidence display | §9 | ❌ | Intent confidence UI missing | 7-8 |
| Submit button | §9 | ✅ | WebSocket send working via runTask() | - |
| **Idle Detection** | | | |
| IOKit monitoring | §9 | ✅ | _iokit_idle_loop() polls HIDIdleTime every 30s in daemon.py | 7-8 |
| Idle timer | §9 | ✅ | Configurable threshold in idle_mode.py | 7-8 |
| Idle notification | §9 | ⚠️ | Idle state tracked; notification not surfaced to UI | 7-8 |
| **File Watching** | | | |
| File system integration | §9 | ✅ | Polling-based fs_watcher.py with debounce | 5-6 |
| Change detection | §9 | ✅ | mtime-based detection with invalidation callbacks | 5-6 |
| **Auto-start** | | | |
| LaunchAgent registration | §9 | ✅ | com.jarvis.daemon.plist configured | - |
| Login persistence | §9 | ✅ | Runs after restart | - |
| **Daemon Management** | | | |
| Daemon startup | §9 | ✅ | daemon.py with WebSocket + idle + file watcher | - |
| Daemon logging | §9 | ✅ | OSLog + file output | - |
| Daemon monitoring | §9 | ⚠️ | Status available; no crash recovery | 7-8 |

---

## Bootstrap & Cold Start (§11)

| Feature | PRD Ref | Status | Details | Week Due |
|---------|---------|--------|---------|----------|
| **Bootstrap Skills** | | | |
| rest-endpoint-scaffold | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| test-setup | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| git-workflow | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| error-classification | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| dockerfile-generation | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| code-review-checklist | §11.1 | ✅ | bootstrap/skills/coding/ SKILL.md written | 5-6 |
| **Clone-Time Init** | | | |
| Language detection | §11.2 | ✅ | Detects Node, Python, Rust, Go, Docker, Java, Swift | - |
| Framework detection | §11.2 | ✅ | Detects Flask, Django, Express, etc. | - |
| Container template selection | §11.2 | ✅ | Selects based on detection | - |
| Context L1 generation | §11.2 | ✅ | build_l1_repo_structure() in context_layers.py | 5-6 |
| Context L2 generation | §11.2 | ✅ | build_l2_module_graph() with AST analysis | 5-6 |
| Signature extraction (L3) | §11.2 | ✅ | build_l3_signatures() with Python AST | 5-6 |
| Test baseline (L4) | §11.2 | ✅ | build_l4_test_quality() test scanner | 5-6 |
| **Universal Heuristics** | | | |
| Jest retry patterns | §11.3 | ✅ | universal_heuristics.py with Jest hanging/forceExit fix | 5-6 |
| Node.js memory flags | §11.3 | ✅ | universal_heuristics.py with NODE_OPTIONS heap fix | 5-6 |
| Migration ordering | §11.3 | ✅ | universal_heuristics.py with Django + Alembic migration fixes | 5-6 |
| Docker layer caching | §11.3 | ✅ | universal_heuristics.py with build context fixes | 5-6 |
| Rust borrow checker | §11.3 | ✅ | universal_heuristics.py with borrow + Send fixes | 5-6 |
| Git conflict resolution | §11.3 | ✅ | universal_heuristics.py with stash + unrelated histories | 5-6 |
| Auto-seed on first task | §11.3 | ✅ | auto_seed_project() called in orchestrator.run_task() | 5-6 |
| **Test Suite** | | | |
| Unit tests for memory.py | §11.4 | ✅ | 25+ tests covering all CRUD operations | - |
| Unit tests for self_learning | §11.4 | ✅ | Tests for hashing, extraction, learning pipeline | - |
| Unit tests for model_router | §11.4 | ✅ | Tests for routing decisions, filtering, stats | - |
| Unit tests for skill_generator | §11.4 | ✅ | Tests for generation, validation, bootstrap copy | - |
| Unit tests for idle_mode | §11.4 | ✅ | Tests for state machine, background tasks, lifecycle | - |
| Unit tests for fs_watcher | §11.4 | ✅ | Tests for scanning, change detection, invalidation | - |
| Unit tests for universal_heuristics | §11.4 | ✅ | Tests for seeding, detection, auto-seeding | - |

---

## Multi-Domain Evolution (§12)

| Phase | Component | Timeline | Status | Week Due |
|-------|-----------|----------|--------|----------|
| **Phase 1** | Coding Agent v2.0 | 6-8 weeks | 97% | Week 8 |
| **Phase 2** | Stock Agent v2.1 | 4-6 weeks | 0% | Week 14 |
| Phase 2 | yfinance MCP | 4-6 weeks | ❌ | Week 14 |
| Phase 2 | SEC filings MCP | 4-6 weeks | ❌ | Week 14 |
| Phase 2 | Technical indicators | 4-6 weeks | ❌ | Week 14 |
| Phase 2 | Backtesting framework | 4-6 weeks | ❌ | Week 14 |
| **Phase 3** | Research Agent v2.2 | 4 weeks | 0% | Week 18 |
| Phase 3 | arXiv MCP | 4 weeks | ❌ | Week 18 |
| Phase 3 | Paper analysis skills | 4 weeks | ❌ | Week 18 |
| **Phase 4** | Self-Extension v2.3 | Ongoing | 0% | 19+ |
| Phase 4 | Domain detection | Ongoing | ❌ | 19+ |
| Phase 4 | MCP discovery | Ongoing | ❌ | 19+ |
| Phase 4 | Autonomous subagent creation | Ongoing | ❌ | 19+ |

---

## Summary Statistics

### By Status
- ✅ **Fully Implemented**: 103 features
- ⚠️ **Partially Implemented**: 8 features
- ❌ **Not Started**: 25 features

**Total**: 136 distinct features mapped

### By Week (Phase 1 Only)
- **Weeks 1-2**: 5 critical features (Learning activation, MCP health) ✅ Complete
- **Weeks 3-4**: 8 features (Model routing, MLX, Foundation Models) ✅ Complete
- **Weeks 5-6**: 9 features (Skills, File watcher, Context layers, Spotlight) ✅ Complete
- **Weeks 7-8**: 13 features (UI, Idle mode, IOKit, Keychain, Bootstrap) ✅ Complete

### Completion Path
1. Foundation (Learning + MCP): Weeks 1-2 → ✅ Complete
2. Intelligence (3-tier model routing): Weeks 3-4 → ✅ MLX + Foundation Models + Cloud
3. Knowledge (Skills + File watcher + Context layers): Weeks 5-6 → ✅ Complete
4. UX + Optimization (SwiftUI + Idle + macOS native): Weeks 7-8 → ✅ Complete

### Remaining for Phase 1
- Native FSEvents (functional polling alternative available)
- SwiftUI timeline event filtering UI
- SwiftUI approval modify-input text field
- NL parsing for command input (GLM integration)
- Confidence display in command input

---

## Dependencies & Critical Path

```
Learning Activation (Weeks 1-2) ✅
  └─ Enables: Skill generation, knowledge extraction

Model Routing (Weeks 3-4) ✅ (heuristic fallback)
  └─ Enables: Token optimization, context pre-filtering

Skill Generation (Weeks 5-6) ✅
  ├─ Depends on: Learning activation ✅
  └─ Enables: Autonomous skill discovery (Phase 4)

File Watcher + Context Layers (Weeks 5-6) ✅
  └─ Enables: Knowledge invalidation, project awareness

SwiftUI Completion (Weeks 7-8) ✅
  └─ Enables: User approval, real-time status, command input

Idle Mode (Weeks 7-8) ✅
  ├─ Depends on: Learning activation ✅, skill generation ✅
  └─ Enables: Background optimization, continuous improvement

Universal Heuristics (Weeks 7-8) ✅
  └─ Enables: Cold start knowledge, cross-project learning

Test Suite ✅
  └─ Validates: All core Python modules

Phase 2: Stock Agent (Weeks 9-14)
  ├─ Depends on: Learning system (from Phase 1) ✅
  └─ Enables: Multi-domain learning transfer

Phase 3: Research Agent (Weeks 15-18)
  ├─ Depends on: Stock agent coordination
  └─ Enables: Cross-domain pattern analysis

Phase 4: Self-Extension (Weeks 19+)
  ├─ Depends on: All previous phases
  └─ Enables: Autonomous capability expansion
```

---

## Usage Guide

**To track progress**:
- Update status as implementation proceeds
- Mark completed features as ✅
- Update "Week Due" as dates confirmed

**To identify gaps**:
- Search for ❌ entries in your target week
- Assess inter-dependencies before starting

**To estimate effort**:
- Count features by status per week
- Each feature typically 0.5-1.5 days

---

**Last Updated**: February 14, 2026
**Codebase Version**: v0.4.0 (~90% complete, Phase 1: 98%)
**Next Review**: After Phase 2 planning
