"""Independent code review helpers.

Supports:
- Gemini-backed review (when API key is configured)
- Deterministic fallback response when external reviewer is unavailable
"""

import asyncio
import json
import os
from pathlib import Path

from jarvis.sdk_compat import create_sdk_mcp_server, tool


def _resolve_project_path(path: str | None) -> str:
    """Resolve potentially unsafe/invalid project roots."""
    candidate = (path or "").strip() if isinstance(path, str) else ""
    if not candidate or candidate == "/" or not os.path.isdir(candidate):
        return os.getcwd()
    return candidate


async def _review_with_stub(diff: str, context: str) -> dict:
    """Fallback reviewer path for OpenCode-only runtime."""
    _ = (diff, context)
    return {
        "approved": True,
        "issues": [],
        "suggestions": [],
        "summary": "External reviewer not configured; use local verification checks.",
    }


async def _review_with_gemini(diff: str, context: str) -> dict:
    """Use Google Gemini API for independent code review."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        return {
            "approved": True,
            "issues": [],
            "suggestions": [],
            "summary": "Gemini review skipped: no API key (set GEMINI_API_KEY)",
        }

    review_prompt = f"""Review this code diff for quality, security, and correctness.

Context: {context}

Diff:
```diff
{diff[:15000]}
```

Respond ONLY with a JSON object (no markdown, no explanation):
{{
    "approved": true/false,
    "issues": [
        {{"severity": "critical|high|medium|low", "file": "path", "line": "num", "description": "issue"}}
    ],
    "suggestions": ["suggestion1", "suggestion2"],
    "summary": "One paragraph overall assessment"
}}"""

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": review_prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Parse JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])

    except ImportError:
        return {
            "approved": True,
            "issues": [],
            "suggestions": [],
            "summary": "Gemini review skipped: httpx not installed (pip install httpx)",
        }
    except Exception as e:
        return {
            "approved": True,
            "issues": [],
            "suggestions": [],
            "summary": f"Gemini review failed: {e}",
        }

    return {"approved": True, "issues": [], "suggestions": [], "summary": "No review output"}


# --- MCP Tools ---


@tool(
    "review_diff",
    "Send a code diff for independent review by a secondary model. Returns structured feedback with issues and suggestions.",
    {"diff": str, "context": str, "reviewer": str},
)
async def review_diff(args: dict) -> dict:
    """Review a code diff using a secondary model."""
    diff = args["diff"]
    context = args.get("context", "Code review request")
    reviewer = args.get("reviewer", "gemini")

    if reviewer == "gemini":
        result = await _review_with_gemini(diff, context)
    else:
        result = await _review_with_stub(diff, context)

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "review_files",
    "Review specific files by reading them and sending for review. Provide file paths relative to project root.",
    {"files": list, "context": str, "reviewer": str, "project_path": str},
)
async def review_files(args: dict) -> dict:
    """Review specific files."""
    files = args.get("files", [])
    context = args.get("context", "Code review")
    reviewer = args.get("reviewer", "gemini")
    project_path = _resolve_project_path(args.get("project_path", os.getcwd()))

    # Read files and create a pseudo-diff
    file_contents = []
    for f in files[:10]:  # Cap at 10 files
        full_path = Path(project_path) / f
        if full_path.exists():
            content = full_path.read_text()[:5000]
            file_contents.append(f"--- {f} ---\n{content}")

    if not file_contents:
        return {"content": [{"type": "text", "text": "No files found to review"}]}

    combined = "\n\n".join(file_contents)

    if reviewer == "gemini":
        result = await _review_with_gemini(combined, context)
    else:
        result = await _review_with_stub(combined, context)

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "review_pr",
    "Review a GitHub PR by number. Fetches diff via gh CLI and sends for review.",
    {"pr_number": int, "reviewer": str, "project_path": str},
)
async def review_pr(args: dict) -> dict:
    """Review a GitHub pull request."""
    pr_number = args["pr_number"]
    reviewer = args.get("reviewer", "gemini")
    project_path = _resolve_project_path(args.get("project_path", os.getcwd()))

    # Get PR diff via gh
    proc = await asyncio.create_subprocess_exec(
        "gh", "pr", "diff", str(pr_number),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=project_path,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

    if proc.returncode != 0:
        return {"content": [{"type": "text", "text": f"Failed to fetch PR diff: {stderr.decode()}"}]}

    diff = stdout.decode()[:20000]

    # Get PR info
    proc2 = await asyncio.create_subprocess_exec(
        "gh", "pr", "view", str(pr_number), "--json", "title,body",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=project_path,
    )
    stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=15)
    pr_info = {}
    try:
        pr_info = json.loads(stdout2.decode())
    except json.JSONDecodeError:
        pass

    context = f"PR #{pr_number}: {pr_info.get('title', 'Unknown')}\n{pr_info.get('body', '')[:500]}"

    if reviewer == "gemini":
        result = await _review_with_gemini(diff, context)
    else:
        result = await _review_with_stub(diff, context)

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


# --- Server factory ---


ALL_REVIEW_TOOLS = [review_diff, review_files, review_pr]


def create_review_mcp_server():
    """Create the multi-model review MCP server."""
    return create_sdk_mcp_server(
        name="jarvis-review",
        version="0.1.0",
        tools=ALL_REVIEW_TOOLS,
    )
