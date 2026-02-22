"""Core orchestrator: OpenCode-first execution with Apple Containers.

Supports two modes:
- Single-agent (Phase 1): Direct task execution with one agent
- Pipeline alias (Phase 2): mapped to single-agent execution in OpenCode-only mode

Uses OpenCode runtime with:
- Dynamic tool/MCP capability wiring
- Hooks for budget enforcement and trust checks
- Session resume for continuity
- macOS native notifications
"""

import asyncio
import json
import logging
import os
import re
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jarvis.budget import BudgetController
from jarvis.code_orchestrator import CodeOrchestrator
from jarvis.config import JARVIS_HOME, JARVIS_OPENCODE_CONFIG, JarvisConfig
from jarvis.decision_tracer import DecisionTracer, TraceCategory
from jarvis.browser_tools import create_browser_mcp_server
from jarvis.context_files import (
    append_project_turn,
    ensure_core_context_files,
    ensure_project_jarvis_file,
)
from jarvis.container_tools import create_container_mcp_server, cleanup_containers
from jarvis.events import EventCollector, EVENT_TASK_START, EVENT_TASK_COMPLETE, EVENT_ERROR
from jarvis.git_tools import create_git_mcp_server
from jarvis.harness import BuildHarness
from jarvis.memory import MemoryStore
from jarvis.loop_detector import LoopDetector
from jarvis.mail_pipeline import LocalMailDigestService, ZapierMailClient
from jarvis.notifications import (
    notify_approval_needed,
    notify_task_completed,
    notify_task_failed,
    notify_task_started,
)
from jarvis.review_tools import create_review_mcp_server
from jarvis.trust import TrustEngine
from jarvis.self_learning import learn_from_task

# Subpackage modules
from jarvis.orchestrator.capabilities import DynamicCapabilitiesManager
from jarvis.orchestrator.mcp_loader import MCPConfigLoader
from jarvis.orchestrator.prompts import SystemPromptBuilder
from jarvis.orchestrator.hooks import OrchestratorHooks


logger = logging.getLogger(__name__)


CODER_EXPERT_AGENT = "coder-expert"
MAIL_CHIEF_AGENT = "mail-chief"
MAIL_ROUTE = "mail"

MAIL_SERVER_HINTS = ("zapier", "mail")
MAIL_TOOL_HINTS = (
    "mail_",
    "gmail_",
    "outlook_",
    "inbox_",
    "message_",
    "thread_",
)
DEFAULT_MAIL_TOOLS = [
    # Keep empty by default: exact Zapier tool names are injected via
    # JARVIS_MAIL_TOOLS to avoid invalid wildcard tool specs.
]

CODER_ROUTE_PATTERNS = (
    "code",
    "bug",
    "fix",
    "refactor",
    "test",
    "lint",
    "build",
    "compile",
    "function",
    "class",
    "typescript",
    "python",
    "swift",
    "javascript",
)
MAIL_ROUTE_PATTERNS = (
    "mail",
    "gmail",
    "outlook",
    "inbox",
    "email",
    "follow up",
    "follow-up",
    "unread",
    "missed",
)

A2A_WORKFLOW_MODES = {"auto", "single", "stepwise", "parallel"}
A2A_PARALLEL_KEYWORDS = (
    "parallel",
    "subagent",
    "sub-agent",
    "worktree",
    "worktrees",
    "multiple agents",
    "multi-agent",
    "security review",
    "code review",
    "pull request",
    "raise pr",
)
A2A_STEPWISE_KEYWORDS = (
    "design",
    "develop",
    "implement",
    "build",
    "test",
    "browser",
    "e2e",
    "api",
    "start server",
    "restart server",
    "fix",
    "verify",
)

RESEARCH_HANDOFF_START = "[RESEARCH_HANDOFF_JSON]"
RESEARCH_HANDOFF_END = "[/RESEARCH_HANDOFF_JSON]"
QUALITY_RESULT_START = "[QUALITY_RESULT_JSON]"
QUALITY_RESULT_END = "[/QUALITY_RESULT_JSON]"


class JarvisOrchestrator:
    """Main Jarvis orchestration engine."""

    def __init__(self, project_path: str | None = None):
        self.config = JarvisConfig.load()
        default_workspace = (
            os.environ.get("JARVIS_WORKSPACE") or self.config.workspace_root or os.getcwd()
        )
        self.project_path = str(Path(project_path or default_workspace).expanduser().resolve())
        Path(self.project_path).mkdir(parents=True, exist_ok=True)
        ensure_core_context_files()
        ensure_project_jarvis_file(self.project_path)

        # Core components
        self.trust = TrustEngine()
        self.budget = BudgetController()
        self.memory = MemoryStore()
        self.tracer = DecisionTracer(memory=self.memory)

        # MCP servers
        self.container_server = create_container_mcp_server()
        self.git_server = create_git_mcp_server()
        self.review_server = create_review_mcp_server()
        self.browser_server = create_browser_mcp_server()

        # Use subpackage modules
        self._mcp_loader = MCPConfigLoader(self.project_path)
        self._capabilities = DynamicCapabilitiesManager()
        self._prompt_builder = SystemPromptBuilder(
            trust=self.trust,
            budget=self.budget,
            memory=self.memory,
            project_path=self.project_path,
            config_max_turns=self.config.budget.max_turns_per_subtask,
        )

        # Load configured MCP servers
        self._configured_mcp_servers = self._mcp_loader.load_configured_mcp_servers()

        # Session state
        self._session_id: str | None = None
        self._active_containers: list[str] = []
        self.loop_detector = LoopDetector(max_iterations=self.config.budget.max_turns_per_subtask)
        self.events = EventCollector(memory=self.memory)
        self._chat_lock = asyncio.Lock()
        self._chat_client: Any | None = None
        self._channel_id = "default"  # Default channel for this orchestrator
        # Preserve OpenCode conversation continuity per logical channel/context.
        self._opencode_session_by_channel: dict[str, str] = {}

        # Code orchestrator
        self.code_orchestrator = CodeOrchestrator(
            mcp_servers={
                "jarvis-container": self.container_server,
                "jarvis-git": self.git_server,
            },
            project_path=self.project_path,
        )

        # Hooks (initialized after notifications module is available)
        self._hooks: OrchestratorHooks | None = None

        self._preflight_status: dict = {
            "ready": False,
            "checked_at": None,
            "live_check": False,
            "errors": ["preflight_not_run"],
            "warnings": [],
            "provider": {
                "type": "opencode",
                "config_path": str(JARVIS_OPENCODE_CONFIG),
                "config_present": JARVIS_OPENCODE_CONFIG.exists(),
            },
            "models": {
                "planner": self.config.models.planner,
                "executor": self.config.models.executor,
                "reviewer": self.config.models.reviewer,
                "quick": self.config.models.quick,
            },
        }
        self._register_default_specialist_agents()

    def _init_hooks(self) -> None:
        """Initialize hooks lazily (after notifications module is imported)."""
        if self._hooks is None:
            import jarvis.notifications as notifications

            self._hooks = OrchestratorHooks(
                trust=self.trust,
                budget=self.budget,
                memory=self.memory,
                loop_detector=self.loop_detector,
                events=self.events,
                project_path=self.project_path,
                notifications_module=notifications,
            )

    def _build_mcp_servers(self) -> dict:
        """Build static + dynamic MCP server map."""
        return self._mcp_loader.build_mcp_servers_map(
            container_server=self.container_server,
            git_server=self.git_server,
            review_server=self.review_server,
            browser_server=self.browser_server,
            configured_servers=self._configured_mcp_servers,
            dynamic_servers=self._capabilities.mcp_servers,
        )

    def _register_default_specialist_agents(self) -> None:
        """Install default specialist agents once (persisted by capabilities manager)."""
        if CODER_EXPERT_AGENT not in self._capabilities.agents:
            self._capabilities.register_agent(
                name=CODER_EXPERT_AGENT,
                description="Expert software engineer for implementation, debugging, testing, and code review.",
                prompt=(
                    "You are a senior engineer. Work in this order: plan, implement, run verification "
                    "(tests/lint/build), review risks, then summarize. Never claim success without executed "
                    "verification evidence."
                ),
                model="inherit",
            )
        if MAIL_CHIEF_AGENT not in self._capabilities.agents:
            self._capabilities.register_agent(
                name=MAIL_CHIEF_AGENT,
                description="Inbox triage specialist for missed replies, deadlines, and action items.",
                prompt=(
                    "You triage email and produce concise, actionable digests. Classify items into urgent, "
                    "reply_today, waiting_on_them, and fyi. Flag missed follow-ups and explicit asks."
                ),
                model="inherit",
            )

    @staticmethod
    def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
        text_lower = text.lower()
        return any(p in text_lower for p in patterns)

    def _build_mail_tool_allowlist(self) -> list[str]:
        """Return known mail tool names plus user-defined tool names."""
        extra = os.environ.get("JARVIS_MAIL_TOOLS", "")
        from_env = [name.strip() for name in extra.split(",") if name.strip()]
        return sorted(set([*DEFAULT_MAIL_TOOLS, *from_env]))

    def _has_mail_tool_allowlist(self) -> bool:
        """Whether explicit mail tools are configured for the active backend."""
        return len(self._build_mail_tool_allowlist()) > 0

    def _mail_digest_mode(self) -> str:
        """Resolve mail digest execution mode.

        OpenCode-only runtime.
        """
        return "local"

    def _has_mail_mcp_server(self) -> bool:
        """Detect whether a mail-related MCP server is configured."""
        server_names = set(self._build_mcp_servers().keys())
        return any(any(hint in name.lower() for hint in MAIL_SERVER_HINTS) for name in server_names)

    def _build_mail_mcp_servers(self) -> dict[str, Any]:
        """Return only mail-related MCP servers (Zapier/mail connectors)."""
        all_servers = self._build_mcp_servers()
        mail_servers = {
            name: cfg
            for name, cfg in all_servers.items()
            if any(hint in name.lower() for hint in MAIL_SERVER_HINTS)
        }
        return mail_servers

    def _select_specialist(self, user_text: str) -> tuple[str | None, str]:
        """Return (specialist_agent_name, route_label)."""
        if self._contains_any(user_text, MAIL_ROUTE_PATTERNS):
            return MAIL_CHIEF_AGENT, MAIL_ROUTE
        if self._contains_any(user_text, CODER_ROUTE_PATTERNS):
            return CODER_EXPERT_AGENT, "coding"
        return None, "chat"

    def _augment_prompt_for_specialist(self, text: str, specialist: str | None, mode: str) -> str:
        """Add deterministic delegation instructions when a specialist is selected."""
        if specialist == CODER_EXPERT_AGENT:
            return (
                f"Delegate this {mode} to the `{CODER_EXPERT_AGENT}` agent first, then continue.\n"
                "Completion gate: do not mark done without verification commands and their results.\n\n"
                f"User request:\n{text}"
            )
        if specialist == MAIL_CHIEF_AGENT:
            return (
                f"Delegate this {mode} to `{MAIL_CHIEF_AGENT}` first, then continue.\n"
                "Use available mail tools to triage inbox items. Output with sections: urgent, reply_today, "
                "waiting_on_them, fyi, top_3_now.\n\n"
                f"User request:\n{text}"
            )
        return text

    def _is_coding_task(self, task_description: str) -> bool:
        return self._contains_any(task_description, CODER_ROUTE_PATTERNS)

    def _has_verification_command(self, tool_calls: list[dict[str, Any]]) -> bool:
        """Require at least one test/lint/build/check command for coding tasks."""
        verification_hints = (
            " test",
            "pytest",
            "vitest",
            "jest",
            "swift test",
            "cargo test",
            "go test",
            "xcodebuild test",
            "lint",
            "ruff",
            "mypy",
            "typecheck",
            "build",
            "compile",
            "check",
        )
        for call in tool_calls:
            text = str(call.get("command", "")).lower()
            if text and any(h in text for h in verification_hints):
                return True
        return False

    def _extract_command_for_tool_call(self, tool_name: str, tool_input: Any) -> str:
        """Best-effort command extraction from tool-call input payload."""
        if not isinstance(tool_input, dict):
            return ""
        if tool_name == "Bash":
            return str(tool_input.get("command") or tool_input.get("cmd") or "").strip()
        if "container_exec" in tool_name:
            return str(tool_input.get("command") or "").strip()
        if tool_name.startswith("mcp__jarvis-browser__browser_test_run"):
            return "browser_test_run"
        return ""

    def _enforce_coder_completion_gate(
        self,
        *,
        specialist: str | None,
        task_description: str,
        tool_calls: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> None:
        """Fail coding tasks that claim completion without verification commands."""
        if specialist != CODER_EXPERT_AGENT:
            return
        if result.get("status") != "completed":
            return
        if not self._is_coding_task(task_description):
            return
        if self._has_verification_command(tool_calls):
            return

        result["status"] = "failed"
        result["output"] = (
            (result.get("output") or "").strip()
            + "\n\nQuality gate failed: no verification command (tests/lint/build/check) was executed."
        ).strip()

    def _extract_urls_from_text(self, text: str) -> list[str]:
        """Extract and normalize HTTP(S) URLs from free-form text."""
        if not text:
            return []
        matches = re.findall(r"https?://[^\s<>()\"']+", text, flags=re.IGNORECASE)
        urls: list[str] = []
        seen: set[str] = set()
        for raw in matches:
            cleaned = raw.rstrip(".,;:!?)]}")
            try:
                parts = urlsplit(cleaned)
            except Exception:
                continue
            if parts.scheme not in ("http", "https") or not parts.netloc:
                continue
            normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
            if normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def _ingest_research_urls_from_text(self, text: str, source: str) -> int:
        urls = self._extract_urls_from_text(text)
        if not urls:
            return 0
        add_research_sources = getattr(self.memory, "add_research_sources", None)
        if not callable(add_research_sources):
            return 0
        try:
            added = int(add_research_sources(urls, source=source) or 0)
        except Exception:
            logger.debug("Failed to ingest research URLs from %s", source, exc_info=True)
            return 0
        if added:
            self.events.emit(
                "research_sources_added",
                f"Added {added} research source(s) from {source}",
                metadata={"source": source, "count": added, "urls": urls[:20]},
            )
        return added

    @staticmethod
    def _extract_tagged_block(
        text: str,
        *,
        start_tag: str,
        end_tag: str,
    ) -> tuple[str, str | None]:
        """Extract tagged block body and return (clean_text, body)."""
        if not text:
            return "", None
        pattern = re.compile(
            rf"{re.escape(start_tag)}\s*(.*?)\s*{re.escape(end_tag)}",
            flags=re.DOTALL,
        )
        matches = list(pattern.finditer(text))
        if not matches:
            return text, None
        body = matches[-1].group(1).strip()
        clean_text = pattern.sub("", text).strip()
        return clean_text, body

    def _extract_research_handoff(self, text: str) -> tuple[str, dict[str, Any] | None]:
        """Parse optional research handoff payload from delegated task text."""
        clean_text, body = self._extract_tagged_block(
            text,
            start_tag=RESEARCH_HANDOFF_START,
            end_tag=RESEARCH_HANDOFF_END,
        )
        if not body:
            return clean_text, None
        try:
            raw = json.loads(body)
        except Exception:
            return clean_text, None
        if not isinstance(raw, dict):
            return clean_text, None

        research_id = str(raw.get("researchId") or "").strip()
        verdict = str(raw.get("proposedVerdict") or "").strip().lower()
        if not research_id or verdict not in {"adopt", "adapt", "skip"}:
            return clean_text, None

        handoff: dict[str, Any] = {
            "research_id": research_id,
            "proposed_verdict": verdict,
            "must_use_in_workflow": bool(raw.get("mustUseInWorkflow", False)),
            "notes": str(raw.get("notes") or "").strip(),
        }
        if isinstance(raw.get("confidence"), (int, float)):
            handoff["confidence"] = max(0.0, min(1.0, float(raw["confidence"])))
        return clean_text, handoff

    def _evaluate_research_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        """Gate execution using structured research verdict."""
        verdict = str(handoff.get("proposed_verdict") or "").strip().lower()
        confidence = float(handoff.get("confidence", 0.0) or 0.0)
        must_use = bool(handoff.get("must_use_in_workflow", False))
        research_id = str(handoff.get("research_id") or "").strip()

        if verdict == "skip":
            allow_execution = False
            reason = "Research verdict is skip; execution blocked to avoid low-value implementation."
        elif verdict == "adapt":
            allow_execution = True
            reason = (
                "Research verdict is adapt; execute with explicit constraints and verification."
            )
        else:
            allow_execution = True
            reason = "Research verdict is adopt; proceed with implementation."

        return {
            "research_id": research_id,
            "decision": verdict,
            "confidence": confidence,
            "must_use_in_workflow": must_use,
            "allow_execution": allow_execution,
            "reason": reason,
        }

    def _augment_task_with_quality_contract(self, task_description: str, gate: dict[str, Any]) -> str:
        """Append deterministic completion contract for research-driven execution."""
        verdict = str(gate.get("decision") or "").strip().lower() or "adapt"
        research_id = str(gate.get("research_id") or "").strip()
        return (
            f"{task_description}\n\n"
            "Research handoff policy (mandatory):\n"
            f"- research_id: {research_id}\n"
            f"- verdict_to_use: {verdict}\n"
            "- Ensure implementation follows this verdict before closing.\n"
            "- Run concrete verification (tests/lint/build/check or equivalent).\n"
            "- Final output must include this exact JSON block:\n"
            f"{QUALITY_RESULT_START}\n"
            '{\n'
            '  "research_id": "<id>",\n'
            '  "verdict_used": "adopt|adapt|skip",\n'
            '  "quality_outcome": "passed|partial|failed",\n'
            '  "verification_evidence": ["<command/evidence>", "..."],\n'
            '  "reason": "<why this outcome>",\n'
            '  "next_action": "<optional next step>"\n'
            '}\n'
            f"{QUALITY_RESULT_END}\n"
        )

    def _extract_quality_result(self, output_text: str) -> dict[str, Any] | None:
        """Parse and validate mandatory quality contract block."""
        _, body = self._extract_tagged_block(
            output_text or "",
            start_tag=QUALITY_RESULT_START,
            end_tag=QUALITY_RESULT_END,
        )
        if not body:
            return None
        try:
            raw = json.loads(body)
        except Exception:
            return None
        if not isinstance(raw, dict):
            return None

        quality_outcome = str(raw.get("quality_outcome") or "").strip().lower()
        verdict_used = str(raw.get("verdict_used") or "").strip().lower()
        if quality_outcome not in {"passed", "partial", "failed"}:
            return None
        if verdict_used not in {"adopt", "adapt", "skip"}:
            return None
        evidence = raw.get("verification_evidence")
        if not isinstance(evidence, list):
            evidence = []
        normalized_evidence = [str(item).strip() for item in evidence if str(item).strip()]

        return {
            "research_id": str(raw.get("research_id") or "").strip(),
            "verdict_used": verdict_used,
            "quality_outcome": quality_outcome,
            "verification_evidence": normalized_evidence,
            "reason": str(raw.get("reason") or "").strip(),
            "next_action": str(raw.get("next_action") or "").strip(),
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt with project context and trust level."""
        return self._prompt_builder.build()

    def _build_allowed_tools(self) -> list[str]:
        """Build tool list based on trust tier."""
        trust_status = self.trust.status(self.project_path)
        tier = trust_status["tier"]

        # Base tools everyone gets (T0+)
        tools = [
            "Read",
            "Glob",
            "Grep",
            "WebSearch",
            "WebFetch",
            "mcp__context7__resolve-library-id",
            "mcp__context7__query-docs",
            "mcp__deepwiki__read_wiki_structure",
            "mcp__deepwiki__read_wiki_contents",
            "mcp__deepwiki__ask_question",
            "mcp__context-graph__context_get_trace",
            "mcp__context-graph__context_list_categories",
            "mcp__context-graph__context_list_traces",
            "mcp__context-graph__context_query_traces",
            "mcp__context-graph__context_store_trace",
            "mcp__context-graph__context_update_outcome",
            "mcp__token-efficient__batch_process_csv",
            "mcp__token-efficient__execute_code",
            "mcp__token-efficient__get_token_savings_report",
            "mcp__token-efficient__list_token_efficient_tools",
            "mcp__token-efficient__process_csv",
            "mcp__token-efficient__process_logs",
            "mcp__token-efficient__search_tools",
            "mcp__comet-bridge__comet_ask",
            "mcp__comet-bridge__comet_connect",
            "mcp__comet-bridge__comet_mode",
            "mcp__comet-bridge__comet_poll",
            "mcp__comet-bridge__comet_screenshot",
            "mcp__comet-bridge__comet_stop",
            "mcp__jarvis-x-bookmarks__x_health",
            "mcp__jarvis-x-bookmarks__x_get_me",
            "mcp__jarvis-x-bookmarks__x_list_bookmarks",
            "mcp__jarvis-x-bookmarks__x_list_bookmark_folders",
            "mcp__jarvis-x-bookmarks__x_list_folder_bookmarks",
        ]

        # Mail tools are opt-in by config or by detected mail MCP server.
        if self.config.mail.enabled or self._has_mail_mcp_server():
            tools.extend(self._build_mail_tool_allowlist())

        if tier >= 1:  # Assistant: edit, test, search
            tools.extend(["Edit", "Write", "Bash", "Task", "Skill", "NotebookEdit"])
            tools.extend(
                [
                    "mcp__jarvis-git__git_clone",
                    "mcp__jarvis-git__git_status",
                    "mcp__jarvis-git__git_diff",
                    "mcp__jarvis-git__git_log",
                    "mcp__jarvis-git__git_branch",
                ]
            )

        if tier >= 2:  # Developer: containers, packages, git commit
            tools.extend(
                [
                    "mcp__jarvis-container__container_run",
                    "mcp__jarvis-container__container_exec",
                    "mcp__jarvis-container__container_stop",
                    "mcp__jarvis-container__container_list",
                    "mcp__jarvis-container__container_logs",
                    "mcp__jarvis-container__container_inspect",
                    "mcp__jarvis-container__container_stats",
                    "mcp__jarvis-git__git_add",
                    "mcp__jarvis-git__git_commit",
                    "mcp__jarvis-git__git_create_branch",
                    "mcp__jarvis-git__git_stash",
                    "mcp__jarvis-review__review_diff",
                    "mcp__jarvis-review__review_files",
                    "mcp__jarvis-browser__browser_setup",
                    "mcp__jarvis-browser__browser_test_run",
                    "mcp__jarvis-browser__browser_navigate",
                    "mcp__jarvis-browser__browser_interact",
                    "mcp__jarvis-browser__browser_api_test",
                    "mcp__jarvis-browser__browser_wallet_test",
                ]
            )

        if tier >= 3:  # Trusted Dev: push, PRs
            tools.extend(
                [
                    "mcp__jarvis-git__git_push",
                    "mcp__jarvis-git__git_create_pr",
                    "mcp__jarvis-review__review_pr",
                ]
            )

        return tools

    async def _pre_tool_hook(
        self, input_data: dict, tool_use_id: str | None, context: dict
    ) -> dict:
        """Hook: enforce trust and budget before tool execution."""
        self._init_hooks()
        return await self._hooks.pre_tool_hook(input_data, tool_use_id, context)

    async def _post_tool_hook(
        self, input_data: dict, tool_use_id: str | None, context: dict
    ) -> dict:
        """Hook: track container lifecycle, emit events, detect loops, capture execution records."""
        self._init_hooks()
        result = await self._hooks.post_tool_hook(input_data, tool_use_id, context)
        # Track active containers locally (not in hooks module)
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response", "")
        if "container_run" in tool_name and isinstance(tool_response, str):
            try:
                data = json.loads(tool_response)
                if data.get("status") == "running":
                    container_id = data.get("container_id")
                    if container_id:
                        self._active_containers.append(container_id)
            except (json.JSONDecodeError, TypeError):
                pass
        return result

    async def _post_message_hook(self, input_data: dict, context: dict) -> dict:
        """Hook: track token usage and costs from tool/message events."""
        self._init_hooks()
        context["session_id"] = self._session_id
        context["model"] = self.config.models.executor
        return await self._hooks.post_message_hook(input_data, context)

    def _derive_provider_from_model(self, model_id: str) -> str:
        """Infer provider from model ID for config-coherency checks."""
        model = str(model_id or "")
        if model.startswith("opencode/") or model.startswith("opencode:") or model == "opencode":
            return "opencode"
        return "opencode"

    def _effective_provider_type(self) -> str:
        """OpenCode-only policy: always return opencode."""
        model_id = self.config.models.executor
        derived = self._derive_provider_from_model(model_id)
        configured = str(getattr(self.config.models, "provider_type", "")).strip().lower() or "opencode"
        if configured != "opencode" or derived != "opencode":
            logger.warning(
                "provider_type/model mismatch (configured=%s, derived=%s, model=%s); forcing opencode",
                configured,
                derived,
                model_id,
            )
        return derived

    def _build_runtime_system_prompt(self, provider_type: str) -> str:
        """Return provider-aware system prompt."""
        _ = provider_type
        return self._build_system_prompt()

    def _build_options(self, permission_mode: str = "acceptEdits") -> dict[str, Any]:
        """Compatibility shim retained for callers that inspect allowed tools."""
        _ = permission_mode
        return {
            "allowed_tools": self._build_allowed_tools(),
            "mcp_servers": self._build_mcp_servers(),
        }

    async def _run_task_local(
        self,
        task_id: str,
        task_description: str,
        provider_type: str,
        model_id: str,
        emit_notifications: bool,
    ) -> dict:
        """Legacy local-model path is disabled in OpenCode-only mode."""
        _ = (task_description, provider_type, model_id, emit_notifications)
        return {
            "task_id": task_id,
            "status": "failed",
            "cost_usd": 0.0,
            "turns": 1,
            "session_id": None,
            "output": "Local model execution is disabled. Configure opencode/* model IDs.",
        }

    async def _chat_local(self, user_message: str, provider_type: str, model_id: str) -> dict:
        """Legacy local-model chat path is disabled in OpenCode-only mode."""
        _ = (user_message, provider_type, model_id)
        return {
            "status": "error",
            "route": "chat",
            "reply": "Local model chat is disabled. Configure opencode/* model IDs.",
            "decision": {"mode": "chat", "confidence": 0.0, "reason": "local_model_disabled"},
        }

    async def _run_task_opencode(
        self,
        task_id: str,
        task_description: str,
        model_id: str,
        emit_notifications: bool,
        channel_id: str | None = None,
        resume_session_id: str | None = None,
    ) -> dict:
        """Run task through OpenCode server in non-interactive mode."""
        from jarvis.opencode_client import get_opencode_client

        result = {
            "task_id": task_id,
            "status": "unknown",
            "cost_usd": 0.0,
            "turns": 1,
            "session_id": None,
            "output": "",
        }

        try:
            self._ensure_opencode_config_env()
            client = get_opencode_client()
            agent_name = os.environ.get("JARVIS_OPENCODE_AGENT", "").strip() or None
            timeout_seconds = int(os.environ.get("JARVIS_OPENCODE_TIMEOUT_SECS", "300"))
            prior_session_id = (
                self._opencode_session_by_channel.get(channel_id, "").strip()
                if channel_id
                else ""
            ) or None
            effective_resume_session_id = resume_session_id or prior_session_id
            last_info_signature: str | None = None

            async def on_progress(payload: dict[str, Any]) -> None:
                nonlocal last_info_signature
                if not isinstance(payload, dict):
                    return
                if str(payload.get("type") or "").strip().lower() == "message_info":
                    info = payload.get("info")
                    if isinstance(info, dict):
                        role = str(info.get("role") or "").strip().lower()
                        if role and role != "assistant":
                            return
                        path_info = info.get("path") if isinstance(info.get("path"), dict) else {}
                        signature_payload = {
                            "role": role,
                            "providerID": info.get("providerID"),
                            "modelID": info.get("modelID"),
                            "agent": info.get("agent"),
                            "cwd": (path_info or {}).get("cwd"),
                        }
                        signature = json.dumps(signature_payload, sort_keys=True, default=str)
                        if signature == last_info_signature:
                            return
                        last_info_signature = signature
                self._emit_opencode_progress(task_id, payload)

            run = await client.run_task(
                task_description,
                model_id=model_id,
                agent=agent_name,
                cwd=self.project_path,
                resume_session_id=effective_resume_session_id,
                timeout_seconds=timeout_seconds,
                on_progress=on_progress,
            )
            result["session_id"] = run.session_id
            if channel_id and run.session_id:
                self._opencode_session_by_channel[channel_id] = run.session_id
            result["output"] = run.text
            result["status"] = "completed"

            self.events.emit(
                EVENT_TASK_COMPLETE,
                result["output"][:200],
                task_id=task_id,
                metadata={
                    "status": "completed",
                    "provider": "opencode",
                    "session_id": run.session_id,
                    "resumed_session": bool(effective_resume_session_id),
                    "channel_id": channel_id or "",
                },
            )
            if emit_notifications:
                await notify_task_completed(task_id, result["output"])
        except Exception as e:
            result["status"] = "failed"
            result["output"] = f"OpenCode error: {e}"
            self.events.emit(EVENT_ERROR, str(e), task_id=task_id, metadata={"provider": "opencode"})

        return result

    def _emit_opencode_progress(self, task_id: str, payload: dict[str, Any]) -> None:
        """Emit timeline-friendly progress events from native OpenCode message payloads."""
        if not isinstance(payload, dict):
            return
        payload_type = str(payload.get("type") or "").strip().lower()
        if payload_type == "message_info":
            info = payload.get("info")
            if not isinstance(info, dict):
                return
            path_info = info.get("path") if isinstance(info.get("path"), dict) else {}
            cwd = str((path_info or {}).get("cwd") or "")
            provider_id = str(info.get("providerID") or "")
            model_id = str(info.get("modelID") or "")
            agent = str(info.get("agent") or "")
            summary = f"OpenCode session cwd={cwd or 'unknown'} model={model_id or 'unknown'}"
            self.events.emit(
                "task_execution_config",
                summary,
                task_id=task_id,
                metadata={
                    "provider_type": provider_id or "opencode",
                    "model_id": model_id,
                    "agent": agent,
                    "cwd": cwd,
                    "session_id": str(payload.get("session_id") or ""),
                    "source": "opencode_message_info",
                },
            )
            return
        if payload_type != "message_part":
            return
        part = payload.get("part")
        if not isinstance(part, dict):
            return
        part_type = str(part.get("type") or "").strip().lower()
        if not part_type:
            return

        metadata: dict[str, Any] = {
            "tool": f"opencode:{part_type}",
            "session_id": str(payload.get("session_id") or ""),
        }
        for key in ("command", "file", "path", "name", "reason", "text"):
            value = part.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                metadata[key] = text[:1000]

        summary = self._opencode_part_summary(part_type, part)
        self.events.emit(
            "tool_use",
            summary,
            task_id=task_id,
            metadata=metadata,
        )

    @staticmethod
    def _opencode_part_summary(part_type: str, part: dict[str, Any]) -> str:
        """Build concise summaries for OpenCode part stream events."""
        if part_type == "step-start":
            return "opencode step started"
        if part_type == "step-finish":
            reason = str(part.get("reason") or "").strip()
            return f"opencode step finished ({reason})" if reason else "opencode step finished"
        if part_type == "reasoning":
            text = str(part.get("text") or "").strip()
            return f"opencode reasoning: {text[:140]}" if text else "opencode reasoning"

        # Tool-ish parts in OpenCode commonly include explicit names/commands/paths.
        name = str(part.get("name") or "").strip()
        command = str(part.get("command") or "").strip()
        path = str(part.get("path") or "").strip()
        if name:
            return f"opencode {part_type}: {name}"
        if command:
            compact = re.sub(r"\s+", " ", command).strip()
            return f"opencode {part_type}: {compact[:140]}"
        if path:
            return f"opencode {part_type}: {path}"
        text = str(part.get("text") or "").strip()
        if text:
            return f"opencode {part_type}: {text[:140]}"
        return f"opencode {part_type}"

    async def _chat_opencode(self, user_message: str, model_id: str) -> dict:
        """Handle chat via OpenCode server."""
        from jarvis.opencode_client import get_opencode_client

        try:
            self._ensure_opencode_config_env()
            client = get_opencode_client()
            agent_name = os.environ.get("JARVIS_OPENCODE_CHAT_AGENT", "").strip() or None
            run = await client.run_task(
                user_message,
                model_id=model_id,
                agent=agent_name,
                timeout_seconds=int(os.environ.get("JARVIS_OPENCODE_CHAT_TIMEOUT_SECS", "120")),
            )
            reply = run.text.strip()
            self.events.emit(
                "chat_assistant",
                reply[:200],
                cost_usd=0.0,
                metadata={"reply": reply[:5000], "tools": [], "provider": "opencode"},
            )
            decision = {"mode": "chat", "confidence": 1.0, "reason": "opencode"}
            self.events.emit(
                "chat_route",
                "mode=chat provider=opencode",
                metadata={"decision": decision, "session_id": run.session_id},
            )
            self.memory.save_channel_turn("message", self.project_path, user_message, reply)
            append_project_turn(
                self.project_path,
                actor="chat:opencode",
                message=user_message,
                outcome=reply[:500],
            )
            return {
                "status": "completed",
                "route": "chat",
                "reply": reply,
                "decision": decision,
            }
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("opencode chat failed: %s\n%s", e, tb)
            self.events.emit(
                EVENT_ERROR,
                str(e)[:200],
                metadata={"error": str(e), "provider": "opencode"},
            )
            return {
                "status": "error",
                "route": "chat",
                "reply": f"OpenCode error: {e}",
                "decision": {"mode": "chat", "confidence": 0.0, "reason": "opencode_error"},
            }

    def _resolve_task_provider_for_origin(
        self,
        *,
        origin: str,
        provider_type: str,
        model_id: str,
    ) -> tuple[str, str]:
        """Resolve provider/model for task execution (OpenCode-only policy)."""
        _ = origin
        forced_provider = "opencode"
        forced_model = model_id
        if not (
            forced_model.startswith("opencode/")
            or forced_model.startswith("opencode:")
            or forced_model == "opencode"
        ):
            forced_model = os.environ.get("JARVIS_A2A_OPENCODE_MODEL", "opencode/glm-5-free").strip()
            if not forced_model:
                forced_model = "opencode/glm-5-free"

        if provider_type != forced_provider or forced_model != model_id:
            logger.info(
                "A2A provider override applied: provider %s -> %s, model %s -> %s",
                provider_type,
                forced_provider,
                model_id,
                forced_model,
            )
        return forced_provider, forced_model

    @staticmethod
    def _normalize_a2a_workflow_mode(raw_mode: str | None) -> str:
        mode = str(raw_mode or "").strip().lower()
        return mode if mode in A2A_WORKFLOW_MODES else "auto"

    def _select_a2a_workflow(self, *, origin: str, task_description: str) -> tuple[str, str]:
        """Use runtime autonomy for workflow selection."""
        if origin == "a2a":
            return "runtime", "runtime_autonomy"
        return "runtime", "origin_non_a2a"

    def _apply_a2a_workflow_prompt(self, *, task_description: str, workflow_mode: str) -> str:
        """Do not inject deterministic workflow prompts; let runtime choose."""
        return task_description

    async def _finalize_task_result(
        self,
        *,
        result: dict[str, Any],
        provider_type: str,
        specialist: str | None,
        task_description: str,
        tool_calls: list[dict[str, Any]],
        task_id: str,
        route: str,
        workflow_mode: str,
        origin: str,
        emit_notifications: bool,
        callback: Callable[[str, dict], None] | None,
    ) -> dict:
        """Finalize task bookkeeping, learning, and notifications for all providers."""
        if provider_type != "opencode":
            self._enforce_coder_completion_gate(
                specialist=specialist,
                task_description=task_description,
                tool_calls=tool_calls,
                result=result,
            )

        # Update task record
        final_status = result["status"]
        if final_status not in ("completed", "failed", "cancelled"):
            final_status = "failed"
        self.memory.transition_task(
            task_id,
            final_status,
            cost_usd=result["cost_usd"],
            turns=result["turns"],
            session_id=result["session_id"],
            result=result["output"][:5000],
        )

        # Store decision trace
        try:
            trace_outcome = "success" if result["status"] == "completed" else "failure"
            trace_context: dict[str, Any] = {
                "turns": result["turns"],
                "cost": result["cost_usd"],
                "route": route,
            }
            quality_assessment = result.get("quality_assessment")
            if isinstance(quality_assessment, dict):
                trace_context["quality_outcome"] = str(
                    quality_assessment.get("quality_outcome") or ""
                ).strip()
                trace_context["verification_evidence_count"] = len(
                    quality_assessment.get("verification_evidence")
                    if isinstance(quality_assessment.get("verification_evidence"), list)
                    else []
                )
            research_gate = result.get("research_gate")
            if isinstance(research_gate, dict):
                trace_context["research_id"] = str(research_gate.get("research_id") or "").strip()
                trace_context["research_decision"] = str(
                    research_gate.get("decision") or ""
                ).strip()
            await self.tracer.store_trace(
                category=TraceCategory.TASK_EXECUTION,
                description=task_description[:500],
                decision=(
                    "Executed task "
                    f"(route={route}, specialist={specialist or 'none'})"
                ),
                context=trace_context,
                outcome=trace_outcome,
                project_path=self.project_path,
            )
        except Exception:
            pass

        # Self-learning: extract patterns from execution records
        if self.config.knowledge.enable_learning:
            try:
                records = self.memory.get_execution_records(task_id=task_id, limit=1)
                if records:
                    learning_stats = await learn_from_task(
                        task_id=task_id,
                        project_path=self.project_path,
                        memory=self.memory,
                    )
                    if learning_stats.get("errors_found", 0) > 0:
                        logger.info(
                            f"Learning loop: Task {task_id} - "
                            f"{learning_stats['errors_found']} errors found, "
                            f"{learning_stats['learnings_saved']} patterns saved, "
                            f"{learning_stats['skills_flagged']} skill candidates flagged"
                        )
                    if learning_stats["learnings_saved"] > 0:
                        self.events.emit(
                            "learning_captured",
                            f"Learned {learning_stats['learnings_saved']} patterns from task",
                            task_id=task_id,
                            metadata=learning_stats,
                        )
                else:
                    logger.debug(f"Learning loop: Task {task_id} - No execution records to analyze")
            except Exception as e:
                logger.warning(f"Learning extraction failed for task {task_id}: {e}", exc_info=True)
                self.events.emit(EVENT_ERROR, f"Learning extraction failed: {e}", task_id=task_id)
        else:
            logger.debug(f"Learning loop: Disabled by config for task {task_id}")

        # Events + macOS notifications
        if result["status"] == "completed":
            self.events.emit(
                EVENT_TASK_COMPLETE,
                task_description,
                task_id=task_id,
                cost_usd=result["cost_usd"],
                metadata={"origin": origin, "emit_notifications": emit_notifications},
            )
            if emit_notifications:
                await notify_task_completed(task_id, task_description, result["cost_usd"])
        elif result["status"] in ("failed", "error"):
            self.events.emit(
                EVENT_ERROR,
                result["output"][:200],
                task_id=task_id,
                metadata={
                    "error": result["output"][:5000],
                    "origin": origin,
                    "emit_notifications": emit_notifications,
                },
            )
            if emit_notifications:
                await notify_task_failed(task_id, task_description, result["output"][:100])

        append_project_turn(
            self.project_path,
            actor=f"task:{origin}",
            message=task_description,
            outcome=(
                f"status={result['status']} turns={result['turns']} "
                f"cost=${result['cost_usd']:.2f}"
            ),
        )

        if callback:
            callback("task_completed", result)

        return result

    def _ensure_opencode_config_env(self) -> None:
        """Point OpenCode to strict system opencode config."""
        if os.environ.get("OPENCODE_CONFIG"):
            return
        if JARVIS_OPENCODE_CONFIG.exists():
            os.environ["OPENCODE_CONFIG"] = str(JARVIS_OPENCODE_CONFIG)

    def register_mcp_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Register a dynamic stdio MCP server for future task/chat turns."""
        return self._capabilities.register_mcp_server(name, command, args, env)

    def register_agent(
        self,
        name: str,
        description: str,
        prompt: str,
        tools: list[str] | None = None,
        model: str | None = None,
    ) -> dict:
        """Register a dynamic SDK sub-agent."""
        return self._capabilities.register_agent(name, description, prompt, tools, model)

    def register_skill(self, name: str, description: str, content: str) -> dict:
        """Register a dynamic skill instruction block visible to Jarvis."""
        return self._capabilities.register_skill(name, description, content)

    def get_capabilities(self) -> dict:
        """Return capability inventory for UI/diagnostics."""
        dynamic_names = sorted(self._capabilities.mcp_servers.keys())
        static_names = [
            "jarvis-container",
            "jarvis-git",
            "jarvis-review",
            "jarvis-browser",
            *sorted(self._configured_mcp_servers.keys()),
        ]
        dynamic_agents = sorted(self._capabilities.agents.keys())
        dynamic_skills = sorted(self._capabilities.skills.keys())
        tools = sorted(set(self._build_allowed_tools()))
        capability_tools = tools + [f"mcp://{n}" for n in (static_names + dynamic_names)]
        capability_tools += ["hook://PreToolUse", "hook://PostToolUse"]
        capability_tools += [
            "agent://planner",
            "agent://executor",
            "agent://tester",
            "agent://reviewer",
        ]
        capability_tools += [f"agent://{name}" for name in dynamic_agents]
        capability_tools += ["skill://Skill"]
        capability_tools += [f"skill://{name}" for name in dynamic_skills]
        capability_tools += ["code_orchestrator://execute"]
        return {
            "tools": sorted(set(capability_tools)),
            "mcp_servers": {
                "static": static_names,
                "dynamic": dynamic_names,
            },
            "hooks": ["PreToolUse", "PostToolUse"],
            "agents": ["planner", "executor", "tester", "reviewer", *dynamic_agents],
            "skills_enabled": True,
            "skills": dynamic_skills,
        }

    def run_code_orchestration(self, code: str, timeout: int = 30) -> dict:
        """Execute batched tool script via CodeOrchestrator."""
        result = self.code_orchestrator.execute(code, timeout=timeout)
        summary = (
            f"status={result.get('status')} "
            f"tool_calls={result.get('tool_calls', 0)} "
            f"saved~{result.get('cost_saved_estimate', 0)} tokens"
        )
        self.events.emit(
            EVENT_TOOL_USE,
            "code_orchestrator.execute",
            metadata={
                "summary": summary,
                "status": result.get("status"),
                "tool_calls": result.get("tool_calls", 0),
                "error": result.get("error"),
            },
        )
        return result

    async def run_task(
        self,
        task_description: str,
        callback=None,
        *,
        origin: str = "user",
        emit_notifications: bool = True,
        channel_id: str | None = None,
        resume_session_id: str | None = None,
    ) -> dict:
        """Execute a task autonomously.

        Args:
            task_description: Natural language task description
            callback: Optional callback(event_type, data) for progress reporting
            origin: Origin identifier (user, a2a, ws, etc.)
            emit_notifications: Whether to emit notifications
            channel_id: Optional channel ID for session isolation
            resume_session_id: Optional OpenCode session id for explicit resume

        Returns:
            Task result dict with status, cost, session_id
        """
        # Note: we do NOT call set_channel() here to avoid mutating shared
        # _channel_id state and introducing race conditions with concurrent A2A tasks.
        task_description, research_handoff = self._extract_research_handoff(task_description)
        if origin != "idle_research":
            self._ingest_research_urls_from_text(task_description, source=f"task:{origin}")

        specialist: str | None = None
        route = "autonomous"
        routed_description = task_description
        workflow_mode = ""
        workflow_reason = "autonomous_runtime"
        _ = workflow_reason
        research_gate: dict[str, Any] | None = None

        # Create task record
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        self.memory.create_task(task_id, task_description, self.project_path)
        self.memory.transition_task(task_id, "in_progress")

        ensure_project_jarvis_file(self.project_path)
        if emit_notifications:
            await notify_task_started(task_id, task_description)
        self.events.emit(
            EVENT_TASK_START,
            task_description,
            task_id=task_id,
            metadata={
                "origin": origin,
                "emit_notifications": emit_notifications,
            },
        )
        if callback:
            callback("task_started", {"id": task_id, "description": task_description})

        # Execute through OpenCode runtime.
        provider_type = self._effective_provider_type()
        model_id = self.config.models.executor
        provider_type, model_id = self._resolve_task_provider_for_origin(
            origin=origin,
            provider_type=provider_type,
            model_id=model_id,
        )
        self.events.emit(
            "task_execution_config",
            f"provider={provider_type} model={model_id}",
            task_id=task_id,
            metadata={
                "origin": origin,
                "provider_type": provider_type,
                "model_id": model_id,
            },
        )

        if research_handoff:
            research_gate = self._evaluate_research_handoff(research_handoff)
            self.events.emit(
                "research_gate_decision",
                f"research={research_gate['research_id']} decision={research_gate['decision']}",
                task_id=task_id,
                metadata=research_gate,
            )
            if not research_gate["allow_execution"]:
                blocked_result = {
                    "task_id": task_id,
                    "status": "failed",
                    "cost_usd": 0.0,
                    "turns": 0,
                    "session_id": None,
                    "output": (
                        "Research gate blocked execution.\n"
                        f"research_id={research_gate['research_id']} "
                        f"decision={research_gate['decision']} "
                        f"reason={research_gate['reason']}"
                    ),
                    "research_gate": research_gate,
                    "quality_assessment": {
                        "research_id": research_gate["research_id"],
                        "verdict_used": research_gate["decision"],
                        "quality_outcome": "failed",
                        "verification_evidence": [],
                        "reason": research_gate["reason"],
                        "next_action": "Revise research verdict before delegation.",
                    },
                }
                return await self._finalize_task_result(
                    result=blocked_result,
                    provider_type=provider_type,
                    specialist=specialist,
                    task_description=task_description,
                    tool_calls=[],
                    task_id=task_id,
                    route=route,
                    workflow_mode=workflow_mode,
                    origin=origin,
                    emit_notifications=emit_notifications,
                    callback=callback,
                )

            routed_description = self._augment_task_with_quality_contract(
                routed_description,
                research_gate,
            )

        opencode_result = await self._run_task_opencode(
            task_id,
            routed_description,
            model_id,
            emit_notifications,
            channel_id=channel_id,
            resume_session_id=resume_session_id,
        )
        if research_gate:
            quality = self._extract_quality_result(str(opencode_result.get("output") or ""))
            if quality is None:
                quality = {
                    "research_id": research_gate["research_id"],
                    "verdict_used": research_gate["decision"],
                    "quality_outcome": "failed",
                    "verification_evidence": [],
                    "reason": (
                        "Missing or invalid quality result block. "
                        f"Expected tags {QUALITY_RESULT_START}...{QUALITY_RESULT_END}."
                    ),
                    "next_action": "Re-run delegated task with mandatory quality block.",
                }
                opencode_result["status"] = "failed"
                opencode_result["output"] = (
                    (str(opencode_result.get("output") or "")).strip()
                    + "\n\nQuality contract failed: missing/invalid QUALITY_RESULT_JSON block."
                ).strip()
            else:
                if quality["verdict_used"] != research_gate["decision"]:
                    opencode_result["status"] = "failed"
                    opencode_result["output"] = (
                        (str(opencode_result.get("output") or "")).strip()
                        + "\n\nQuality contract failed: verdict_used does not match research gate decision."
                    ).strip()
                if quality["quality_outcome"] != "passed":
                    opencode_result["status"] = "failed"
                    opencode_result["output"] = (
                        (str(opencode_result.get("output") or "")).strip()
                        + f"\n\nQuality outcome not passed: {quality['quality_outcome']}."
                    ).strip()
            opencode_result["research_gate"] = research_gate
            opencode_result["quality_assessment"] = quality
            self.events.emit(
                "research_quality_outcome",
                f"research={research_gate['research_id']} outcome={quality['quality_outcome']}",
                task_id=task_id,
                metadata={
                    "research_gate": research_gate,
                    "quality_assessment": quality,
                },
            )

        return await self._finalize_task_result(
            result=opencode_result,
            provider_type=provider_type,
            specialist=specialist,
            task_description=task_description,
            tool_calls=[],
            task_id=task_id,
            route=route,
            workflow_mode=workflow_mode,
            origin=origin,
            emit_notifications=emit_notifications,
            callback=callback,
        )

    def set_channel(self, channel_id: str) -> None:
        """Set the default channel for this orchestrator instance."""
        self._channel_id = channel_id

    async def _reset_chat_client(self, channel_id: str | None = None) -> None:
        """Reset chat/session state for cleanup."""
        _ = channel_id
        if self._chat_client is not None:
            try:
                disconnect = getattr(self._chat_client, "disconnect", None)
                if callable(disconnect):
                    await disconnect()
            except Exception:
                pass
            self._chat_client = None
        self._session_id = None

    async def close(self) -> None:
        """Graceful shutdown for orchestrator state."""
        await self._reset_chat_client()

    def get_preflight_status(self) -> dict:
        """Return last known model/provider preflight result."""
        return dict(self._preflight_status)

    async def run_model_preflight(
        self, *, live_check: bool = False, timeout_seconds: int = 25
    ) -> dict:
        """Validate provider+models before serving requests."""
        _ = timeout_seconds
        errors: list[str] = []
        warnings: list[str] = []
        provider = {
            "type": "opencode",
            "config_path": str(JARVIS_OPENCODE_CONFIG),
            "config_present": JARVIS_OPENCODE_CONFIG.exists(),
        }
        models = {
            "planner": self.config.models.planner,
            "executor": self.config.models.executor,
            "reviewer": self.config.models.reviewer,
            "quick": self.config.models.quick,
        }

        for key, value in models.items():
            if not str(value).strip():
                errors.append(f"missing_model:{key}")
        if not provider["config_present"]:
            errors.append("missing_opencode_config")
        non_opencode = [k for k, v in models.items() if not str(v).strip().lower().startswith("opencode/")]
        if non_opencode:
            warnings.append(f"non_opencode_models:{','.join(non_opencode)}")
        if str(self.config.models.provider_type or "").strip().lower() != "opencode":
            warnings.append("provider_type_not_opencode")

        live_probe = {"attempted": bool(live_check), "ok": False, "error": ""}
        if live_check and not errors:
            try:
                from jarvis.opencode_client import get_opencode_client

                self._ensure_opencode_config_env()
                client = get_opencode_client()
                await asyncio.wait_for(asyncio.to_thread(client.list_models), timeout=10)
                live_probe["ok"] = True
            except Exception as exc:
                live_probe["error"] = str(exc)
                errors.append("live_probe_failed")

        status = {
            "ready": len(errors) == 0,
            "checked_at": time.time(),
            "live_check": bool(live_check),
            "errors": errors,
            "warnings": warnings,
            "provider": provider,
            "models": models,
            "live_probe": live_probe,
        }
        self._preflight_status = status
        return dict(status)

    async def chat(self, user_message: str, *, origin: str = "message") -> dict:
        """Conversational entrypoint (single-pass).

        Every user message goes directly to the chat model. The model itself
        decides when to ask questions vs. invoke tools.

        Returns:
            Dict with status, route, reply, decision (backward-compat shape).
        """
        self._ingest_research_urls_from_text(user_message, source=f"chat:{origin}")
        specialist: str | None = None
        route = "autonomous"

        ensure_project_jarvis_file(self.project_path)
        self.events.emit(
            "chat_user",
            user_message[:200],
            metadata={"message": user_message[:5000]},
        )

        provider_type = self._effective_provider_type()
        model_id = self.config.models.executor

        if specialist == MAIL_CHIEF_AGENT and not self._has_mail_mcp_server():
            reply = (
                "Mail routing requested, but no mail MCP server is configured. "
                "Add a Zapier MCP server and enable `mail.enabled` in Jarvis config."
            )
            self.events.emit(
                EVENT_ERROR,
                reply[:200],
                metadata={"error": reply, "route": route, "specialist": specialist},
            )
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            append_project_turn(
                self.project_path,
                actor=f"chat:{origin}",
                message=user_message,
                outcome=reply[:500],
            )
            return {
                "status": "failed",
                "route": route,
                "reply": reply,
                "decision": {"mode": "chat", "confidence": 0.0, "reason": "mail_mcp_not_configured"},
            }

        if (
            specialist == MAIL_CHIEF_AGENT
            and provider_type != "opencode"
            and not self._has_mail_tool_allowlist()
        ):
            reply = (
                "Mail routing requested, but no explicit mail tool allowlist is set. "
                "Set JARVIS_MAIL_TOOLS to exact Zapier tool names (comma-separated)."
            )
            self.events.emit(
                EVENT_ERROR,
                reply[:200],
                metadata={"error": reply, "route": route, "specialist": specialist},
            )
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            append_project_turn(
                self.project_path,
                actor=f"chat:{origin}",
                message=user_message,
                outcome=reply[:500],
            )
            return {
                "status": "failed",
                "route": route,
                "reply": reply,
                "decision": {
                    "mode": "chat",
                    "confidence": 0.0,
                    "reason": "mail_tool_allowlist_missing",
                },
            }

        if specialist == MAIL_CHIEF_AGENT and provider_type == "opencode":
            digest_result = await self.run_mail_digest(force=True, origin=f"chat:{origin}")
            status = str(digest_result.get("status", "") or "").strip().lower()
            if status in {"completed", "skipped"}:
                digest = digest_result.get("digest") if isinstance(digest_result, dict) else None
                reply = self._format_mail_digest_reply_for_chat(digest if isinstance(digest, dict) else {})
                decision = {"mode": "chat", "confidence": 1.0, "reason": "mail_digest_local"}
                self.events.emit(
                    "chat_assistant",
                    reply[:200],
                    cost_usd=0.0,
                    metadata={"reply": reply[:5000], "tools": ["zapier_mail_digest"], "provider": "opencode"},
                )
                self.events.emit(
                    "chat_route",
                    "mode=chat route=mail conf=1.0",
                    metadata={"decision": decision, "origin": origin},
                )
                self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
                append_project_turn(
                    self.project_path,
                    actor=f"chat:{origin}",
                    message=user_message,
                    outcome=reply[:500],
                )
                return {
                    "status": "completed",
                    "route": MAIL_ROUTE,
                    "reply": reply,
                    "decision": decision,
                }

            reply = str(digest_result.get("error") or "Mail digest failed")
            self.events.emit(
                EVENT_ERROR,
                reply[:200],
                metadata={"error": reply, "route": route, "specialist": specialist},
            )
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            append_project_turn(
                self.project_path,
                actor=f"chat:{origin}",
                message=user_message,
                outcome=reply[:500],
            )
            return {
                "status": "failed",
                "route": MAIL_ROUTE,
                "reply": reply,
                "decision": {"mode": "chat", "confidence": 0.0, "reason": "mail_digest_failed"},
            }

        # OpenCode-only execution.
        _ = (provider_type, route)
        return await self._chat_opencode(user_message, model_id)

    async def handle_message(
        self,
        user_message: str,
        *,
        origin: str = "message",
    ) -> dict:
        """Backward-compat alias for chat(). Callers: ws_server and integrations."""
        return await self.chat(user_message, origin=origin)

    def _normalize_mail_digest(self, payload: Any, fallback_text: str) -> dict[str, Any]:
        """Normalize digest payload into a stable schema."""
        if not isinstance(payload, dict):
            payload = {}
        digest = {
            "urgent": payload.get("urgent") if isinstance(payload.get("urgent"), list) else [],
            "reply_today": (
                payload.get("reply_today") if isinstance(payload.get("reply_today"), list) else []
            ),
            "waiting_on_them": (
                payload.get("waiting_on_them")
                if isinstance(payload.get("waiting_on_them"), list)
                else []
            ),
            "fyi": payload.get("fyi") if isinstance(payload.get("fyi"), list) else [],
            "top_3_now": (
                payload.get("top_3_now") if isinstance(payload.get("top_3_now"), list) else []
            ),
        }
        digest["raw_summary"] = str(payload.get("summary") or fallback_text).strip()[:5000]
        return digest

    def _format_mail_digest_reply_for_chat(self, digest: dict[str, Any]) -> str:
        """Render digest payload to a concise chat-friendly summary."""
        summary = str(digest.get("raw_summary") or "").strip()
        urgent = digest.get("urgent") if isinstance(digest.get("urgent"), list) else []
        reply_today = digest.get("reply_today") if isinstance(digest.get("reply_today"), list) else []
        waiting = (
            digest.get("waiting_on_them") if isinstance(digest.get("waiting_on_them"), list) else []
        )
        fyi = digest.get("fyi") if isinstance(digest.get("fyi"), list) else []
        top_3 = digest.get("top_3_now") if isinstance(digest.get("top_3_now"), list) else []

        lines = [
            "Mail digest ready.",
            (
                f"Urgent: {len(urgent)}, Reply today: {len(reply_today)}, "
                f"Waiting: {len(waiting)}, FYI: {len(fyi)}"
            ),
        ]
        if summary:
            lines.append(summary)
        if top_3:
            lines.append("Top 3 now:")
            for idx, item in enumerate(top_3[:3], start=1):
                if not isinstance(item, dict):
                    continue
                subject = str(item.get("subject") or item.get("thread_id") or "Untitled")
                reason = str(item.get("reason") or item.get("next_action") or "").strip()
                if reason:
                    lines.append(f"{idx}. {subject} - {reason}")
                else:
                    lines.append(f"{idx}. {subject}")
        return "\n".join(lines).strip()[:5000]

    def get_mail_digest(
        self,
        *,
        run_date: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Read stored mail digest runs."""
        return self.memory.get_mail_digest_runs(
            run_date=run_date,
            project_path=self.project_path,
            limit=limit,
        )

    def update_mail_schedule(
        self,
        *,
        enabled: bool | None = None,
        time_local: str | None = None,
        timezone: str | None = None,
        window_hours: int | None = None,
        include_weekends: bool | None = None,
    ) -> dict[str, Any]:
        """Update mail schedule settings and persist config."""
        if enabled is not None:
            self.config.mail.digest_enabled = bool(enabled)
            if enabled:
                self.config.mail.enabled = True
        if time_local is not None:
            self.config.mail.digest_time_local = str(time_local).strip()
        if timezone is not None:
            self.config.mail.timezone = str(timezone).strip()
        if window_hours is not None:
            self.config.mail.window_hours = max(1, min(int(window_hours), 168))
        if include_weekends is not None:
            self.config.mail.include_weekends = bool(include_weekends)
        self.config.save()
        return {
            "enabled": self.config.mail.enabled,
            "digest_enabled": self.config.mail.digest_enabled,
            "digest_time_local": self.config.mail.digest_time_local,
            "timezone": self.config.mail.timezone,
            "window_hours": self.config.mail.window_hours,
            "include_weekends": self.config.mail.include_weekends,
        }

    async def run_mail_digest(
        self,
        *,
        window_hours: int | None = None,
        force: bool = False,
        origin: str = "mail_digest",
    ) -> dict[str, Any]:
        """Generate and persist a daily mail digest via the mail specialist."""
        if not self._has_mail_mcp_server():
            return {
                "status": "failed",
                "error": "No mail MCP server configured",
                "route": MAIL_ROUTE,
            }
        if not self._has_mail_tool_allowlist():
            return {
                "status": "failed",
                "error": "No mail tool allowlist configured (set JARVIS_MAIL_TOOLS)",
                "route": MAIL_ROUTE,
            }

        tz_name = self.config.mail.timezone or "America/Los_Angeles"
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
            tz_name = "UTC"

        now_local = datetime.now(tz)
        run_date = now_local.strftime("%Y-%m-%d")
        run_key = f"{self.project_path}|{tz_name}|{run_date}"
        effective_window = int(window_hours or self.config.mail.window_hours or 24)

        if not force and self.memory.has_mail_digest_run(run_key):
            existing = self.memory.get_mail_digest_runs(
                run_date=run_date,
                project_path=self.project_path,
                limit=1,
            )
            return {
                "status": "skipped",
                "reason": "already_ran_today",
                "route": MAIL_ROUTE,
                "run_date": run_date,
                "digest": existing[0]["digest"] if existing else None,
            }

        mode = self._mail_digest_mode()
        response_text = ""
        cost_usd = 0.0
        turns = 0
        status = "failed"
        payload: dict[str, Any] = {}
        client = ZapierMailClient.from_env()
        if not client:
            return {
                "status": "failed",
                "error": "Zapier MCP URL missing (set ZAPIER_MCP_URL)",
                "route": MAIL_ROUTE,
            }

        pipeline = LocalMailDigestService(client)
        try:
            payload, response_text = await pipeline.build_digest(
                window_hours=effective_window,
                local_model_id=None,
            )
            status = "completed"
        except Exception as exc:
            status = "failed"
            response_text = f"Local mail digest execution failed: {exc}"

        digest = self._normalize_mail_digest(payload, response_text.strip())
        counts = {
            "urgent": len(digest["urgent"]),
            "reply_today": len(digest["reply_today"]),
            "waiting_on_them": len(digest["waiting_on_them"]),
            "fyi": len(digest["fyi"]),
        }
        summary = (
            f"Urgent: {counts['urgent']}, Reply today: {counts['reply_today']}, "
            f"Waiting: {counts['waiting_on_them']}, FYI: {counts['fyi']}"
        )

        self.memory.save_mail_digest_run(
            run_key=run_key,
            run_date=run_date,
            timezone=tz_name,
            window_hours=effective_window,
            status=status,
            summary=summary,
            digest=digest,
            project_path=self.project_path,
        )
        for priority in ("urgent", "reply_today", "waiting_on_them", "fyi"):
            for item in digest.get(priority, []):
                if not isinstance(item, dict):
                    continue
                self.memory.upsert_mail_thread_state(
                    thread_id=str(item.get("thread_id") or "").strip(),
                    subject=str(item.get("subject") or "").strip(),
                    last_action=str(item.get("next_action") or "").strip(),
                    priority=priority,
                    metadata=item,
                )

        self.events.emit(
            "mail_digest_ready" if status == "completed" else EVENT_ERROR,
            summary if status == "completed" else response_text[:200],
            metadata={
                "route": MAIL_ROUTE,
                "origin": origin,
                "run_date": run_date,
                "timezone": tz_name,
                "counts": counts,
                "cost_usd": cost_usd,
                "mode": mode,
            },
            cost_usd=cost_usd,
        )

        return {
            "status": status,
            "route": MAIL_ROUTE,
            "run_date": run_date,
            "timezone": tz_name,
            "summary": summary,
            "counts": counts,
            "digest": digest,
            "cost_usd": cost_usd,
            "turns": turns,
            "mode": mode,
        }

    async def _cleanup_containers(self) -> None:
        """Stop and remove all active containers."""
        await cleanup_containers(self._active_containers)
        self._active_containers.clear()

    async def get_status(self) -> dict:
        """Get current Jarvis status.

        Returns a dict compatible with the SwiftUI JarvisStatusResponse.
        """
        trust_status = self.trust.status(self.project_path)
        budget_status = self.budget.summary()
        active_tasks = self.memory.list_tasks(self.project_path, status="in_progress")
        recent_tasks = self.memory.list_tasks(self.project_path)[:5]

        # Derive overall status for SwiftUI
        if active_tasks:
            overall_status = "building"
        elif any(True for _ in self.memory.list_tasks(self.project_path, status="failed")):
            overall_status = "error"
        else:
            overall_status = "idle"

        latest_mail = self.memory.get_mail_digest_runs(project_path=self.project_path, limit=1)
        latest_mail_run = latest_mail[0] if latest_mail else None

        return {
            "status": overall_status,
            "project": self.project_path,
            "trust": {
                "tier": trust_status["tier"],
                "tier_name": trust_status["tier_name"],
                "successful_tasks": trust_status["successful_tasks"],
                "total_tasks": trust_status["total_tasks"],
                "rollbacks": trust_status["rollbacks"],
                "tasks_until_upgrade": trust_status["tasks_until_upgrade"],
            },
            "budget": {
                "session": budget_status["session"],
                "daily": budget_status["daily"],
                "turns": budget_status["turns"],
            },
            "current_session": self._session_id,
            "current_feature": active_tasks[0].description if active_tasks else None,
            "active_tasks": [{"id": t.id, "description": t.description} for t in active_tasks],
            "recent_tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "status": t.status,
                    "cost": f"${t.cost_usd:.2f}",
                }
                for t in recent_tasks
            ],
            "containers": len(self._active_containers),
            "session_id": self._session_id,
            "preflight": self.get_preflight_status(),
            "mail": {
                "enabled": self.config.mail.enabled,
                "digest_enabled": self.config.mail.digest_enabled,
                "digest_time_local": self.config.mail.digest_time_local,
                "timezone": self.config.mail.timezone,
                "window_hours": self.config.mail.window_hours,
                "latest_digest": latest_mail_run,
            },
        }

    def should_use_pipeline(self, task_description: str) -> bool:
        """Pipeline mode is disabled in OpenCode-only runtime."""
        _ = task_description
        return False

    async def run_pipeline(self, task_description: str, callback=None) -> dict:
        """Compatibility alias: route pipeline requests through run_task()."""
        return await self.run_task(task_description, callback=callback, origin="pipeline")

    async def run_autonomous(self, description: str, callback=None, resume: bool = False) -> dict:
        """Run the autonomous build harness for a project.

        Creates a BuildHarness that loops through features:
        init → implement → test → commit → next feature.

        Args:
            description: Project/task description for planning
            callback: Optional progress callback
            resume: If True, resume from saved state

        Returns:
            Dict with build results
        """
        harness = BuildHarness(
            project_path=self.project_path,
            orchestrator=self,
        )

        if resume:
            harness._load_state()

        self.events.emit(
            "build_start",
            f"Autonomous build: {description[:100]}",
            metadata={"description": description, "resume": resume},
        )

        try:
            await harness.run(callback=callback)
            status = harness._context.state.value
            self.events.emit(
                "build_complete",
                f"Build finished in state: {status}",
                metadata={"final_state": status},
            )
            return {
                "status": status,
                "state": harness._context.state.value,
                "history": harness._context.history,
            }
        except Exception as e:
            self.events.emit(EVENT_ERROR, f"Build failed: {e}")
            return {"status": "error", "error": str(e)}

    async def save_session(self) -> None:
        """Save session summary for cross-session continuity."""
        if not self._session_id:
            return

        completed = self.memory.list_tasks(self.project_path, status="completed")
        pending = self.memory.list_tasks(self.project_path, status="pending")

        summary_parts = []
        for task in completed[-5:]:
            summary_parts.append(f"- Completed: {task.description}")
        for task in pending[:5]:
            summary_parts.append(f"- Pending: {task.description}")

        self.memory.save_session_summary(
            session_id=self._session_id,
            project_path=self.project_path,
            summary="\n".join(summary_parts) or "No tasks recorded",
            tasks_completed=[t.id for t in completed[-5:]],
            tasks_remaining=[t.id for t in pending[:5]],
        )
