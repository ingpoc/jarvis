"""Multi-agent pipeline: Planner -> Executor(s) -> Reviewer -> Integration.

Implements the Jarvis agent architecture:
- Planner (Opus): Decomposes tasks, identifies files, creates subtask plan
- Executor (Sonnet): Implements changes in sandboxed Apple Containers
- Tester (Sonnet): Writes and runs tests, iterates on failures
- Reviewer (Gemini/Opus): Independent code review via review_tools MCP

Each agent is defined as a Claude Agent SDK AgentDefinition and
orchestrated through the main agent loop.
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
)

from jarvis.browser_tools import create_browser_mcp_server
from jarvis.decision_tracer import DecisionTracer, TraceCategory
from jarvis.loop_detector import LoopDetector, LoopAction, build_intervention_message
from jarvis.budget import BudgetController
from jarvis.config import JarvisConfig
from jarvis.container_tools import create_container_mcp_server
from jarvis.git_tools import create_git_mcp_server
from jarvis.memory import MemoryStore
from jarvis.notifications import (
    notify_approval_needed,
    notify_review_complete,
    notify_task_completed,
    notify_task_failed,
    notify_task_started,
)
from jarvis.review_tools import create_review_mcp_server
from jarvis.trust import TrustEngine


# --- Agent Definitions ---

PLANNER_AGENT = AgentDefinition(
    description="Senior architect that decomposes tasks into executable subtasks",
    prompt="""You are the Planner agent for Jarvis.

Your job:
1. Analyze the user's task request
2. Read the codebase to understand structure (use Glob, Read, Grep)
3. Break the task into small, concrete subtasks
4. Identify which files need to be created/modified
5. Choose the right container template for execution
6. Output a structured plan

Output your plan as JSON:
{
    "subtasks": [
        {
            "id": "subtask-1",
            "description": "What to do",
            "files": ["src/foo.ts", "src/bar.ts"],
            "type": "implement|test|config",
            "depends_on": []
        }
    ],
    "container_image": "node:22",
    "estimated_complexity": "low|medium|high",
    "review_needed": true/false,
    "notes": "Any architectural decisions or considerations"
}

Be precise. Each subtask should be completable in one agent turn.""",
    tools=["Read", "Glob", "Grep", "WebSearch"],
    model="opus",
)

EXECUTOR_AGENT = AgentDefinition(
    description="Expert developer that implements code changes in sandboxed containers",
    prompt="""You are the Executor agent for Jarvis.

Your job:
1. Receive a specific subtask from the Planner
2. Work inside an Apple Container VM (use container_exec for all commands)
3. Implement the required changes
4. Run the build to verify compilation
5. Report what was done

Rules:
- Install packages inside the container (npm install, pip install)
- Always verify your changes compile/build
- Keep changes focused and minimal
- Use conventional commit style for descriptions
- Cap retries at 5 for any failing command

## Code Orchestration (batch operations)
When performing multi-step operations (e.g., read 5 files, grep across codebase,
run multiple commands), prefer writing a Python script using the tools.* namespace:
- tools.container_exec(container_id, command) - run command in container
- tools.git_status() - check git status
- tools.read_file(path) - read a file
- tools.write_file(path, content) - write a file
- tools.list_files(pattern) - glob for files
- tools.grep(pattern) - search file contents
- Store intermediate results in the `results` dict
- The script runs in a sandbox; results stay local (no LLM round-trips)
- Use this for batch file reads, multi-step builds, or data gathering""",
    tools=[
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "mcp__jarvis-container__container_exec",
        "mcp__jarvis-container__container_run",
        "mcp__jarvis-container__container_logs",
    ],
    model="sonnet",
)

TESTER_AGENT = AgentDefinition(
    description="QA engineer that writes and runs tests, iterating on failures",
    prompt="""You are the Tester agent for Jarvis.

Your job:
1. Review the implemented changes
2. Write appropriate tests (unit, integration, browser)
3. Run the test suite inside the container
4. If tests fail, analyze and fix (up to 5 retries)
5. For web apps: use browser_setup + browser_navigate/browser_test_run for E2E tests
6. For Solana dApps: use browser_wallet_test with mock Solflare/Phantom wallet
7. Report test results

Rules:
- Run tests inside the container (container_exec)
- If a test fails 5 times, stop and report the issue
- Never modify the implementation code -- only test files
- Cover edge cases and error conditions
- Use the project's existing test framework
- For browser tests: install Playwright first with browser_setup""",
    tools=[
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "mcp__jarvis-container__container_exec",
        "mcp__jarvis-container__container_logs",
        "mcp__jarvis-browser__browser_setup",
        "mcp__jarvis-browser__browser_test_run",
        "mcp__jarvis-browser__browser_navigate",
        "mcp__jarvis-browser__browser_interact",
        "mcp__jarvis-browser__browser_api_test",
        "mcp__jarvis-browser__browser_wallet_test",
    ],
    model="sonnet",
)

REVIEWER_AGENT = AgentDefinition(
    description="Code reviewer that provides independent quality assessment",
    prompt="""You are the Reviewer agent for Jarvis.

Your job:
1. Review all changes made by the Executor
2. Use the review_diff or review_files tools for independent assessment
3. Check for: security issues, code quality, performance, correctness
4. Provide structured feedback

If issues are found, return them clearly so the Executor can fix them.
If the code is good, approve it.""",
    tools=[
        "Read", "Glob", "Grep",
        "mcp__jarvis-review__review_diff",
        "mcp__jarvis-review__review_files",
    ],
    model="opus",
)


@dataclass
class SubtaskResult:
    """Result from a single subtask execution."""

    subtask_id: str
    status: str  # completed, failed
    output: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    files_changed: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result from the full multi-agent pipeline."""

    task_id: str
    status: str  # completed, failed, review_rejected
    plan: dict | None = None
    subtask_results: list[SubtaskResult] = field(default_factory=list)
    review: dict | None = None
    total_cost_usd: float = 0.0
    total_turns: int = 0
    container_ids: list[str] = field(default_factory=list)


class MultiAgentPipeline:
    """Orchestrates the Planner -> Executor(s) -> Tester -> Reviewer pipeline."""

    def __init__(self, project_path: str | None = None):
        self.project_path = project_path or os.getcwd()
        self.config = JarvisConfig.load()
        self.trust = TrustEngine()
        self.budget = BudgetController()
        self.memory = MemoryStore()
        self._tracer = DecisionTracer(memory=self.memory)

        # MCP servers
        self._container_server = create_container_mcp_server()
        self._git_server = create_git_mcp_server()
        self._review_server = create_review_mcp_server()
        self._browser_server = create_browser_mcp_server()

        self._active_containers: list[str] = []
        self._loop_detector = LoopDetector(
            max_iterations=self.config.budget.max_turns_per_subtask
        )

    def _build_mcp_servers(self) -> dict:
        """All MCP servers for agent use."""
        return {
            "jarvis-container": self._container_server,
            "jarvis-git": self._git_server,
            "jarvis-review": self._review_server,
            "jarvis-browser": self._browser_server,
        }

    def _build_agents(self) -> dict[str, AgentDefinition]:
        """All agent definitions."""
        return {
            "planner": PLANNER_AGENT,
            "executor": EXECUTOR_AGENT,
            "tester": TESTER_AGENT,
            "reviewer": REVIEWER_AGENT,
        }

    async def _pre_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Enforce budget and trust on every tool call."""
        can_continue, reason = self.budget.enforce()
        if not can_continue:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Budget limit: {reason}",
                }
            }

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Block git push below T3
        if tool_name == "Bash" and "git push" in tool_input.get("command", ""):
            allowed, reason = self.trust.can_perform(self.project_path, "git_push")
            if not allowed:
                await notify_approval_needed("", "git push")
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }

        return {}

    async def _post_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: detect loops after tool execution."""
        tool_name = input_data.get("tool_name", "")
        tool_input_str = json.dumps(input_data.get("tool_input", {}))
        tool_response = input_data.get("tool_response", "")
        tool_output_str = str(tool_response)[:5120]
        error = None
        if isinstance(tool_response, str) and "error" in tool_response.lower():
            error = tool_response[:1024]

        subtask_id = context.get("task_id", "default")
        action = self._loop_detector.record_iteration(
            subtask_id, tool_name, tool_input_str, tool_output_str, error
        )

        if action != LoopAction.CONTINUE:
            tracker = self._loop_detector.get_tracker(subtask_id)
            message = build_intervention_message(action, tracker)

            if action == LoopAction.ESCALATE:
                await notify_approval_needed(subtask_id, "loop_escalation")

            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "message": message,
                }
            }

        return {}

    def _build_options(self, task_prompt: str) -> ClaudeAgentOptions:
        """Build full options with all agents, MCP servers, and hooks."""
        trust_status = self.trust.status(self.project_path)

        system_prompt = f"""You are Jarvis, an autonomous development partner with a multi-agent pipeline.

## Available Agents
- **planner**: Decomposes tasks into subtasks (uses Opus)
- **executor**: Implements code in sandboxed Apple Containers (uses Sonnet)
- **tester**: Writes and runs tests (uses Sonnet)
- **reviewer**: Independent code review (uses Opus/Gemini)

## Workflow
1. Use the planner agent to analyze the task and create a plan
2. For each subtask, use the executor agent inside an Apple Container
3. After implementation, use the tester agent to verify
4. Use the reviewer agent for quality assessment
5. If review passes, commit with git tools
6. Clean up containers

## Trust: T{trust_status['tier']} ({trust_status['tier_name']})
## Budget: {json.dumps(self.budget.summary())}

## Container Usage
- Start containers with container_run (they're isolated Linux VMs)
- Execute inside with container_exec
- Mount project source with --volume
- Clean up with container_stop when done

## Git Safety
- Stage specific files (never 'git add .')
- Never skip pre-commit hooks
- Never force push to main/master
- Include "Co-Authored-By: Jarvis" in commits"""

        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            model=self.config.models.executor,
            allowed_tools=[
                "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task",
                "WebSearch", "WebFetch", "Skill", "NotebookEdit",
                "mcp__jarvis-container__container_run",
                "mcp__jarvis-container__container_exec",
                "mcp__jarvis-container__container_stop",
                "mcp__jarvis-container__container_list",
                "mcp__jarvis-container__container_logs",
                "mcp__jarvis-container__container_inspect",
                "mcp__jarvis-container__container_stats",
                "mcp__jarvis-git__git_clone",
                "mcp__jarvis-git__git_status",
                "mcp__jarvis-git__git_diff",
                "mcp__jarvis-git__git_log",
                "mcp__jarvis-git__git_branch",
                "mcp__jarvis-git__git_add",
                "mcp__jarvis-git__git_commit",
                "mcp__jarvis-git__git_create_branch",
                "mcp__jarvis-git__git_stash",
                "mcp__jarvis-git__git_push",
                "mcp__jarvis-git__git_create_pr",
                "mcp__jarvis-review__review_diff",
                "mcp__jarvis-review__review_files",
                "mcp__jarvis-review__review_pr",
                "mcp__jarvis-browser__browser_setup",
                "mcp__jarvis-browser__browser_test_run",
                "mcp__jarvis-browser__browser_navigate",
                "mcp__jarvis-browser__browser_interact",
                "mcp__jarvis-browser__browser_api_test",
                "mcp__jarvis-browser__browser_wallet_test",
            ],
            permission_mode="acceptEdits",
            max_turns=self.config.budget.max_turns_per_task,
            max_budget_usd=self.config.budget.max_per_session_usd,
            cwd=self.project_path,
            mcp_servers=self._build_mcp_servers(),
            agents=self._build_agents(),
            hooks={
                "PreToolUse": [HookMatcher(hooks=[self._pre_tool_hook])],
                "PostToolUse": [HookMatcher(hooks=[self._post_tool_hook])],
            },
        )

    async def run(self, task_description: str, callback=None) -> PipelineResult:
        """Execute the full multi-agent pipeline for a task.

        Args:
            task_description: Natural language task
            callback: Optional progress callback(event_type, data)

        Returns:
            PipelineResult with all details
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        result = PipelineResult(task_id=task_id, status="in_progress")

        # Record task
        self.memory.create_task(task_id, task_description, self.project_path)
        self.memory.update_task(task_id, status="in_progress")

        await notify_task_started(task_id, task_description)
        if callback:
            callback("pipeline_started", {"task_id": task_id})

        # The main agent drives the multi-agent pipeline
        # It uses the planner/executor/tester/reviewer as subagents
        augmented_prompt = f"""Execute this task using the multi-agent pipeline:

TASK: {task_description}

STEPS:
1. First, use the 'planner' agent to analyze the task and create a plan
2. Set up an Apple Container for the work (container_run with volume mount of {self.project_path})
3. For each subtask in the plan, use the 'executor' agent to implement
4. Use the 'tester' agent to run tests
5. Use the 'reviewer' agent to review changes
6. If review passes: use git tools to commit changes
7. Clean up containers with container_stop

IMPORTANT: Work inside Apple Containers for isolation. Mount the project source.
Report progress at each step."""

        options = self._build_options(augmented_prompt)

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(augmented_prompt)

                async for message in client.receive_response():
                    if isinstance(message, SystemMessage):
                        if message.subtype == "init":
                            session_id = message.data.get("session_id")
                            if callback:
                                callback("session_started", {"session_id": session_id})

                    elif isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                if callback:
                                    callback("agent_text", {"text": block.text[:300]})
                            elif isinstance(block, ToolUseBlock):
                                if callback:
                                    callback("agent_tool", {"tool": block.name})

                    elif isinstance(message, ResultMessage):
                        cost = message.total_cost_usd or 0.0
                        result.total_cost_usd = cost
                        result.total_turns = message.num_turns
                        result.status = "completed" if not message.is_error else "failed"

                        self.budget.record_cost(cost, message.num_turns, task_description)

                        if not message.is_error:
                            self.trust.record_success(self.project_path)
                            await notify_task_completed(task_id, task_description, cost)
                        else:
                            self.trust.record_failure(self.project_path)
                            await notify_task_failed(task_id, task_description, "Pipeline failed")

        except Exception as e:
            result.status = "error"
            await notify_task_failed(task_id, task_description, str(e)[:100])

        finally:
            await self._cleanup_containers()

        # Update task record
        self.memory.update_task(
            task_id,
            status=result.status,
            cost_usd=result.total_cost_usd,
            turns=result.total_turns,
        )

        # Store decision trace
        try:
            trace_outcome = "success" if result.status == "completed" else "failure"
            await self._tracer.store_trace(
                category=TraceCategory.TASK_EXECUTION,
                description=task_description[:500],
                decision=f"Executed as pipeline ({len(result.subtask_results)} subtasks)",
                context={"turns": result.total_turns, "cost": result.total_cost_usd},
                outcome=trace_outcome,
                project_path=self.project_path,
            )
        except Exception:
            pass

        if callback:
            callback("pipeline_completed", {
                "task_id": task_id,
                "status": result.status,
                "cost": result.total_cost_usd,
                "turns": result.total_turns,
            })

        return result

    async def _cleanup_containers(self) -> None:
        """Stop and remove all active containers."""
        for cid in self._active_containers:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "container", "stop", cid,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=10)
                proc = await asyncio.create_subprocess_exec(
                    "container", "delete", cid,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=10)
            except Exception:
                pass
        self._active_containers.clear()
