"""MCP server configuration loading for Jarvis orchestrator.

Handles loading MCP server configurations from .mcp.json files and
resolving paths for built-in MCP servers.
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from jarvis.config import JARVIS_MCP_RUNTIME_CONFIG

logger = logging.getLogger(__name__)

# Repository root for fallback .mcp.json lookup
REPO_ROOT = Path(__file__).resolve().parents[3]


class MCPConfigLoader:
    """Loads and parses MCP server configurations."""

    def __init__(self, project_path: str):
        self.project_path = project_path

    def load_configured_mcp_servers(self) -> dict[str, dict]:
        """Load MCP servers from project config and built-in documentation defaults."""
        configured: dict[str, dict] = {}

        # Strict source of truth: runtime workflow MCP config under ~/.jarvis.
        mcp_candidates = [
            JARVIS_MCP_RUNTIME_CONFIG,
        ]
        for mcp_json_path in mcp_candidates:
            if not mcp_json_path.exists():
                continue
            try:
                data = json.loads(mcp_json_path.read_text())
                server_map = data.get("mcpServers", {})
                if isinstance(server_map, dict):
                    for name, raw in server_map.items():
                        parsed = self._parse_project_mcp_server(name, raw)
                        if parsed and name not in configured:
                            configured[name] = parsed
            except Exception as exc:
                logger.warning("Failed to parse .mcp.json (%s): %s", mcp_json_path, exc)

        # Ensure doc/repo lookup MCPs are available by default.
        if "context7" not in configured and shutil.which("npx"):
            context7_args = ["-y", "@upstash/context7-mcp"]
            api_key = os.environ.get("CONTEXT7_API_KEY") or os.environ.get("CTX7_API_KEY")
            if api_key:
                context7_args.extend(["--api-key", api_key])
            configured["context7"] = {
                "type": "stdio",
                "command": "npx",
                "args": context7_args,
            }
        if "deepwiki" not in configured:
            configured["deepwiki"] = {
                "type": "http",
                "url": "https://mcp.deepwiki.com/mcp",
            }

        return configured

    def _parse_project_mcp_server(self, name: str, raw: object) -> dict | None:
        """Parse one .mcp.json server entry into Claude Agent SDK format."""
        if not isinstance(raw, dict):
            return None
        if "url" in raw and raw.get("url"):
            url = self._expand_env_placeholders(str(raw["url"]))
            headers = self._expand_headers(raw.get("headers", {}) or {})
            return {
                "type": "http",
                "url": url,
                "headers": headers,
            }

        command = self._expand_env_placeholders(str(raw.get("command", "")).strip())
        args = [self._expand_env_placeholders(str(a)) for a in (raw.get("args", []) or [])]
        env = {
            str(k): self._expand_env_placeholders(str(v))
            for k, v in (raw.get("env", {}) or {}).items()
        }
        if not command:
            return None

        if name == "context-graph":
            command, args, env = self._resolve_context_graph(command, args, env)
        elif name == "token-efficient":
            command, args = self._resolve_token_efficient(command, args)

        return {
            "type": "stdio",
            "command": command,
            "args": args,
            "env": env,
        }

    @staticmethod
    def _expand_env_placeholders(value: str) -> str:
        """Expand ${VAR} placeholders from environment, keeping unresolved values unchanged."""
        if not isinstance(value, str) or "${" not in value:
            return value

        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", _replace, value)

    def _expand_headers(self, headers: dict[str, Any]) -> dict[str, str]:
        """Expand env placeholders in headers and drop unresolved placeholder values."""
        expanded: dict[str, str] = {}
        for key, val in headers.items():
            sval = self._expand_env_placeholders(str(val))
            if "${" in sval:  # unresolved placeholder
                continue
            if sval.strip():
                expanded[str(key)] = sval
        return expanded

    def _resolve_context_graph(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
    ) -> tuple[str, list[str], dict[str, str]]:
        """Normalize context-graph config to a valid path + cache dir."""
        candidate_dirs = [
            Path(self.project_path) / "mcp" / "context-graph-mcp",
            REPO_ROOT / "mcp" / "context-graph-mcp",
            Path(self.project_path).parents[1] / "mcp-servers" / "context-graph-mcp",
            Path(self.project_path).parents[2] / "mcp-servers" / "context-graph-mcp",
        ]
        selected = next((p for p in candidate_dirs if (p / "server.py").exists()), None)
        if selected:
            command = "uv"
            args = ["--directory", str(selected), "run", "python", "server.py"]
            env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache-codex")
        return command, args, env

    def _resolve_token_efficient(self, command: str, args: list[str]) -> tuple[str, list[str]]:
        """Normalize token-efficient config to direct stdio node launch."""
        candidate_files = [
            Path(self.project_path) / "mcp" / "token-efficient-mcp" / "dist" / "index.js",
            REPO_ROOT / "mcp" / "token-efficient-mcp" / "dist" / "index.js",
            Path(self.project_path).parents[1] / "mcp-servers" / "token-efficient-mcp" / "dist" / "index.js",
            Path(self.project_path).parents[2] / "mcp-servers" / "token-efficient-mcp" / "dist" / "index.js",
        ]
        selected = next((p for p in candidate_files if p.exists()), None)
        if selected:
            return "node", [str(selected)]

        # If .mcp.json used srt wrapper, fall back to plain node invocation.
        if command == "srt" and args and args[0] == "node":
            return "node", args[1:]
        return command, args

    def build_mcp_servers_map(
        self,
        container_server: dict,
        git_server: dict,
        review_server: dict,
        browser_server: dict,
        configured_servers: dict[str, dict],
        dynamic_servers: dict[str, dict],
    ) -> dict[str, dict]:
        """Build the complete MCP server map."""
        servers: dict[str, dict] = {
            "jarvis-container": container_server,
            "jarvis-git": git_server,
            "jarvis-review": review_server,
            "jarvis-browser": browser_server,
        }
        servers.update(configured_servers)
        servers.update(dynamic_servers)
        return servers
