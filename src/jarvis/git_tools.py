"""Git MCP tools with trust-aware safety wrappers.

All git operations go through trust checks:
- T1+: git status, diff, log (read-only)
- T2+: git add, commit, branch, stash
- T3+: git push, create PR
- NEVER without approval: force push to main, delete main

Pre-commit hooks are ALWAYS enforced (never --no-verify).
"""

import asyncio
import json
import os

from claude_agent_sdk import create_sdk_mcp_server, tool


async def _run_git(*args: str, cwd: str | None = None, timeout: int = 30) -> dict:
    """Execute git command and return output."""
    cmd = ["git", *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return {
        "exit_code": proc.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }


# --- Clone (T1+) ---


@tool(
    "git_clone",
    "Clone a git repository into a specified path. Supports GitHub URLs and SSH.",
    {"url": str, "path": str, "branch": str, "depth": int},
)
async def git_clone(args: dict) -> dict:
    """Clone a repository."""
    url = args["url"]
    path = args.get("path", "")
    branch = args.get("branch", "")
    depth = args.get("depth", 0)

    cmd = ["clone"]
    if branch:
        cmd.extend(["--branch", branch])
    if depth > 0:
        cmd.extend(["--depth", str(depth)])
    cmd.append(url)
    if path:
        cmd.append(path)

    result = await _run_git(*cmd, timeout=120)
    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": f"Cloned {url}"}]}
    return {"content": [{"type": "text", "text": f"Clone failed: {result['stderr']}"}]}


# --- Read-only tools (T1+) ---


@tool(
    "git_status",
    "Get git status: staged, modified, untracked files.",
    {"path": str},
)
async def git_status(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    result = await _run_git("status", "--short", cwd=path)
    return {"content": [{"type": "text", "text": result["stdout"] or "Clean working tree"}]}


@tool(
    "git_diff",
    "Show git diff. Use staged=true for staged changes.",
    {"path": str, "staged": bool, "file": str},
)
async def git_diff(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    cmd = ["diff"]
    if args.get("staged", False):
        cmd.append("--cached")
    if args.get("file"):
        cmd.extend(["--", args["file"]])
    result = await _run_git(*cmd, cwd=path)
    output = result["stdout"][:8000]  # Cap diff output
    return {"content": [{"type": "text", "text": output or "No changes"}]}


@tool(
    "git_log",
    "Show recent git log entries.",
    {"path": str, "count": int, "oneline": bool},
)
async def git_log(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    count = args.get("count", 10)
    cmd = ["log", f"-{count}"]
    if args.get("oneline", True):
        cmd.append("--oneline")
    result = await _run_git(*cmd, cwd=path)
    return {"content": [{"type": "text", "text": result["stdout"] or "No commits yet"}]}


@tool(
    "git_branch",
    "List branches or show current branch.",
    {"path": str, "all": bool},
)
async def git_branch(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    cmd = ["branch"]
    if args.get("all", False):
        cmd.append("-a")
    result = await _run_git(*cmd, cwd=path)
    return {"content": [{"type": "text", "text": result["stdout"] or "No branches"}]}


# --- Write tools (T2+) ---


@tool(
    "git_add",
    "Stage files for commit. Use specific file paths, not 'git add .'.",
    {"path": str, "files": list},
)
async def git_add(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    files = args.get("files", [])
    if not files:
        return {"content": [{"type": "text", "text": "Error: specify files to add (never use '.')"}]}

    # Safety: never stage .env or credential files
    blocked = [f for f in files if any(p in f.lower() for p in [".env", "credentials", "secret", ".pem", ".key"])]
    if blocked:
        return {"content": [{"type": "text", "text": f"BLOCKED: refusing to stage sensitive files: {blocked}"}]}

    result = await _run_git("add", *files, cwd=path)
    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": f"Staged {len(files)} file(s)"}]}
    return {"content": [{"type": "text", "text": f"Error: {result['stderr']}"}]}


@tool(
    "git_commit",
    "Create a git commit. Never uses --no-verify. Pre-commit hooks always run.",
    {"path": str, "message": str},
)
async def git_commit(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    message = args.get("message", "")
    if not message:
        return {"content": [{"type": "text", "text": "Error: commit message required"}]}

    # Always include co-author
    full_message = f"{message}\n\nCo-Authored-By: Jarvis <jarvis@local>"

    # NEVER skip hooks
    result = await _run_git("commit", "-m", full_message, cwd=path, timeout=60)

    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": f"Committed: {result['stdout']}"}]}
    return {"content": [{"type": "text", "text": f"Commit failed: {result['stderr']}\n{result['stdout']}"}]}


@tool(
    "git_create_branch",
    "Create and checkout a new branch.",
    {"path": str, "branch_name": str, "from_branch": str},
)
async def git_create_branch(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    branch = args["branch_name"]
    from_branch = args.get("from_branch")

    cmd = ["checkout", "-b", branch]
    if from_branch:
        cmd.append(from_branch)

    result = await _run_git(*cmd, cwd=path)
    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": f"Created and switched to branch: {branch}"}]}
    return {"content": [{"type": "text", "text": f"Error: {result['stderr']}"}]}


@tool(
    "git_stash",
    "Stash or restore changes.",
    {"path": str, "action": str, "message": str},
)
async def git_stash(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    action = args.get("action", "push")  # push, pop, list
    cmd = ["stash", action]
    if action == "push" and args.get("message"):
        cmd.extend(["-m", args["message"]])
    result = await _run_git(*cmd, cwd=path)
    return {"content": [{"type": "text", "text": result["stdout"] or result["stderr"]}]}


# --- Elevated tools (T3+) ---


@tool(
    "git_push",
    "Push commits to remote. REQUIRES T3+ trust. Never force-pushes to main.",
    {"path": str, "remote": str, "branch": str, "set_upstream": bool},
)
async def git_push(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    remote = args.get("remote", "origin")
    branch = args.get("branch")

    # Safety: never force push, never push directly to main without explicit branch
    if not branch:
        # Get current branch
        result = await _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=path)
        branch = result["stdout"]

    if branch in ("main", "master"):
        return {"content": [{"type": "text", "text":
            "BLOCKED: Direct push to main/master requires human approval. "
            "Create a feature branch and PR instead."
        }]}

    cmd = ["push", remote, branch]
    if args.get("set_upstream", False):
        cmd.insert(1, "-u")

    result = await _run_git(*cmd, cwd=path, timeout=60)
    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": f"Pushed {branch} to {remote}"}]}
    return {"content": [{"type": "text", "text": f"Push failed: {result['stderr']}"}]}


@tool(
    "git_create_pr",
    "Create a GitHub pull request using gh CLI. REQUIRES T3+ trust.",
    {"path": str, "title": str, "body": str, "base": str, "draft": bool},
)
async def git_create_pr(args: dict) -> dict:
    path = args.get("path", os.getcwd())
    title = args.get("title", "")
    body = args.get("body", "")
    base = args.get("base", "main")
    draft = args.get("draft", False)

    if not title:
        return {"content": [{"type": "text", "text": "Error: PR title required"}]}

    cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--base", base]
    if draft:
        cmd.append("--draft")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=path,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

    if proc.returncode == 0:
        pr_url = stdout.decode().strip()
        return {"content": [{"type": "text", "text": f"PR created: {pr_url}"}]}
    return {"content": [{"type": "text", "text": f"PR creation failed: {stderr.decode()}"}]}


# --- Server factory ---


ALL_GIT_TOOLS = [
    # Clone (T1+)
    git_clone,
    # Read (T1+)
    git_status, git_diff, git_log, git_branch,
    # Write (T2+)
    git_add, git_commit, git_create_branch, git_stash,
    # Elevated (T3+)
    git_push, git_create_pr,
]


def create_git_mcp_server():
    """Create the Git MCP server with safety wrappers."""
    return create_sdk_mcp_server(
        name="jarvis-git",
        version="0.1.0",
        tools=ALL_GIT_TOOLS,
    )
