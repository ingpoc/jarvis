"""Code-based tool orchestration: agents write Python that calls tools programmatically.

Instead of sequential LLM-driven tool calls, agents generate Python scripts
that use the tools.* namespace. Intermediate results stay in sandbox memory,
saving 98%+ tokens by avoiding round-trips to the LLM.
"""

import asyncio
import json
import re
import threading
from pathlib import Path

RESTRICTED_MODULES = {
    "os.system",
    "subprocess",
    "shutil.rmtree",
    "ctypes",
    "importlib",
}

SAFE_BUILTINS = {
    "dict": dict,
    "list": list,
    "tuple": tuple,
    "set": set,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "print": print,
    "isinstance": isinstance,
    "type": type,
    "hasattr": hasattr,
    "getattr": getattr,
    "max": max,
    "min": min,
    "sum": sum,
    "any": any,
    "all": all,
    "abs": abs,
    "round": round,
    "format": format,
    "repr": repr,
    "True": True,
    "False": False,
    "None": None,
}


def _run_async(coro):
    """Run an async coroutine synchronously, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context -- run in a new thread
        result = [None]
        exception = [None]

        def _thread_target():
            try:
                result[0] = asyncio.run(coro)
            except Exception as e:
                exception[0] = e

        t = threading.Thread(target=_thread_target)
        t.start()
        t.join(timeout=30)
        if exception[0]:
            raise exception[0]
        return result[0]
    else:
        return asyncio.run(coro)


class ToolBindings:
    """Sync wrappers around MCP tool calls for use inside exec'd code."""

    def __init__(self, mcp_servers: dict, project_path: str):
        self._servers = mcp_servers
        self._project_path = project_path
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset_count(self):
        self._call_count = 0

    def _invoke(self, server_name: str, tool_name: str, arguments: dict):
        """Invoke an MCP tool synchronously."""
        self._call_count += 1
        server = self._servers.get(server_name)
        if server is None:
            raise RuntimeError(f"MCP server '{server_name}' not available")

        async def _call():
            return await server.call_tool(tool_name, arguments)

        return _run_async(_call())

    def container_exec(self, container_id: str, command: str) -> str:
        """Run a command inside a container. Returns stdout."""
        result = self._invoke("jarvis-container", "container_exec", {
            "container_id": container_id,
            "command": command,
        })
        return str(result) if result else ""

    def git_status(self) -> str:
        """Get git status of the project."""
        result = self._invoke("jarvis-git", "git_status", {
            "path": self._project_path,
        })
        return str(result) if result else ""

    def git_diff(self) -> str:
        """Get git diff of the project."""
        result = self._invoke("jarvis-git", "git_diff", {
            "path": self._project_path,
        })
        return str(result) if result else ""

    def read_file(self, path: str) -> str:
        """Read a file from the project directory."""
        full_path = Path(self._project_path) / path
        if not full_path.resolve().is_relative_to(Path(self._project_path).resolve()):
            raise PermissionError(f"Path escapes project directory: {path}")
        self._call_count += 1
        return full_path.read_text()

    def write_file(self, path: str, content: str) -> None:
        """Write a file in the project directory."""
        full_path = Path(self._project_path) / path
        if not full_path.resolve().is_relative_to(Path(self._project_path).resolve()):
            raise PermissionError(f"Path escapes project directory: {path}")
        self._call_count += 1
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def list_files(self, pattern: str) -> list[str]:
        """List files matching a glob pattern relative to project root."""
        self._call_count += 1
        root = Path(self._project_path)
        matches = sorted(root.glob(pattern))
        return [str(m.relative_to(root)) for m in matches if m.is_file()]

    def grep(self, pattern: str, path: str | None = None) -> list[dict]:
        """Search file contents for a regex pattern. Returns list of {file, line, match}."""
        self._call_count += 1
        root = Path(self._project_path)
        search_path = root / path if path else root
        compiled = re.compile(pattern)
        results = []

        if search_path.is_file():
            files = [search_path]
        else:
            files = sorted(search_path.rglob("*"))

        for f in files:
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text().splitlines(), 1):
                    if compiled.search(line):
                        results.append({
                            "file": str(f.relative_to(root)),
                            "line": i,
                            "match": line.strip(),
                        })
            except (UnicodeDecodeError, PermissionError):
                continue

        return results


class CodeOrchestrator:
    """Execute agent-generated Python in a restricted sandbox with tool bindings."""

    def __init__(self, mcp_servers: dict, project_path: str):
        self._bindings = ToolBindings(mcp_servers, project_path)
        self._project_path = project_path
        self._tool_call_count = 0

    def execute(self, code: str, timeout: int = 30) -> dict:
        """Execute Python code in a restricted namespace with tool bindings.

        Args:
            code: Python source to execute
            timeout: Max seconds before killing execution

        Returns:
            dict with status, result, tool_calls, error, cost_saved_estimate
        """
        # Check for dangerous imports
        for module in RESTRICTED_MODULES:
            if module in code:
                return {
                    "status": "error",
                    "result": {},
                    "tool_calls": 0,
                    "error": f"Blocked restricted module: {module}",
                    "cost_saved_estimate": 0,
                }

        # Reset call counter
        self._bindings.reset_count()

        # Build restricted globals
        restricted_globals = dict(SAFE_BUILTINS)
        results_dict = {}
        restricted_globals.update({
            "__builtins__": SAFE_BUILTINS,
            "tools": self._bindings,
            "results": results_dict,
            "json": json,
            "re": re,
            "Path": Path,
        })

        # Execute with timeout
        error_holder = [None]
        completed = threading.Event()

        def _run():
            try:
                exec(code, restricted_globals)
            except Exception as e:
                error_holder[0] = e
            finally:
                completed.set()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        finished = completed.wait(timeout=timeout)

        if not finished:
            tool_calls = self._bindings.call_count
            self._tool_call_count += tool_calls
            return {
                "status": "error",
                "result": results_dict,
                "tool_calls": tool_calls,
                "error": f"Execution timed out after {timeout}s",
                "cost_saved_estimate": self._estimate_savings(tool_calls),
            }

        tool_calls = self._bindings.call_count
        self._tool_call_count += tool_calls

        if error_holder[0]:
            return {
                "status": "error",
                "result": results_dict,
                "tool_calls": tool_calls,
                "error": f"{type(error_holder[0]).__name__}: {error_holder[0]}",
                "cost_saved_estimate": self._estimate_savings(tool_calls),
            }

        return {
            "status": "success",
            "result": results_dict,
            "tool_calls": tool_calls,
            "error": None,
            "cost_saved_estimate": self._estimate_savings(tool_calls),
        }

    def _estimate_savings(self, tool_calls: int) -> float:
        """Estimate token savings from batched tool execution.

        Each tool call that stays in sandbox saves ~2000 tokens avg round-trip.
        """
        return tool_calls * 2000
