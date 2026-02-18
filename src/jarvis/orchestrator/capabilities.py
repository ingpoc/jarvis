"""Dynamic capabilities management for Jarvis orchestrator.

Handles dynamic MCP servers, agents, and skills that can be registered at runtime
and persist across daemon restarts.
"""

import json
import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import AgentDefinition

from jarvis.config import JARVIS_HOME

logger = logging.getLogger(__name__)

_DYNAMIC_CAPS_FILE = JARVIS_HOME / "dynamic_capabilities.json"


class DynamicCapabilitiesManager:
    """Manages dynamic MCP servers, agents, and skills."""

    def __init__(self):
        self._mcp_servers: dict[str, dict] = {}
        self._agents: dict[str, AgentDefinition] = {}
        self._skills: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load dynamic capabilities from disk."""
        if not _DYNAMIC_CAPS_FILE.exists():
            return
        try:
            data = json.loads(_DYNAMIC_CAPS_FILE.read_text())
        except Exception as exc:
            logger.warning("Failed to load dynamic capabilities: %s", exc)
            return

        for name, server in (data.get("mcp_servers", {}) or {}).items():
            if isinstance(server, dict):
                self._mcp_servers[str(name)] = server

        for name, skill in (data.get("skills", {}) or {}).items():
            if not isinstance(skill, dict):
                continue
            desc = str(skill.get("description", "")).strip()
            content = str(skill.get("content", "")).strip()
            if desc and content:
                self._skills[str(name)] = {"description": desc, "content": content}

        for name, raw_agent in (data.get("agents", {}) or {}).items():
            if not isinstance(raw_agent, dict):
                continue
            description = str(raw_agent.get("description", "")).strip()
            prompt = str(raw_agent.get("prompt", "")).strip()
            if not description or not prompt:
                continue
            tools = raw_agent.get("tools")
            model = raw_agent.get("model")
            safe_model = model if model in ("sonnet", "opus", "haiku", "inherit", None) else "inherit"
            self._agents[str(name)] = AgentDefinition(
                description=description,
                prompt=prompt,
                tools=tools if isinstance(tools, list) else None,
                model=safe_model,
            )

    def _persist(self) -> None:
        """Persist dynamic capabilities so they survive daemon restart."""
        try:
            JARVIS_HOME.mkdir(parents=True, exist_ok=True)
            agents_payload: dict[str, dict] = {}
            for name, agent in self._agents.items():
                agents_payload[name] = {
                    "description": agent.description,
                    "prompt": agent.prompt,
                    "tools": list(agent.tools) if agent.tools else [],
                    "model": agent.model,
                }
            payload = {
                "mcp_servers": self._mcp_servers,
                "agents": agents_payload,
                "skills": self._skills,
            }
            _DYNAMIC_CAPS_FILE.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            logger.warning("Failed to persist dynamic capabilities: %s", exc)

    @property
    def mcp_servers(self) -> dict[str, dict]:
        return self._mcp_servers

    @property
    def agents(self) -> dict[str, AgentDefinition]:
        return self._agents

    @property
    def skills(self) -> dict[str, dict]:
        return self._skills

    def register_mcp_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Register a dynamic stdio MCP server."""
        if not name.strip():
            return {"success": False, "error": "MCP server name is required"}
        if not command.strip():
            return {"success": False, "error": "MCP server command is required"}
        if name.startswith("jarvis-"):
            return {"success": False, "error": "Reserved MCP server prefix: jarvis-"}

        self._mcp_servers[name] = {
            "type": "stdio",
            "command": command,
            "args": args or [],
            "env": env or {},
        }
        self._persist()
        return {
            "success": True,
            "name": name,
            "server_count": len(self._mcp_servers),
        }

    def register_agent(
        self,
        name: str,
        description: str,
        prompt: str,
        tools: list[str] | None = None,
        model: str | None = None,
    ) -> dict:
        """Register a dynamic SDK sub-agent."""
        if not name.strip():
            return {"success": False, "error": "Agent name is required"}
        if not description.strip() or not prompt.strip():
            return {"success": False, "error": "Agent description and prompt are required"}
        safe_model = model if model in ("sonnet", "opus", "haiku", "inherit", None) else "inherit"
        self._agents[name] = AgentDefinition(
            description=description,
            prompt=prompt,
            tools=tools or None,
            model=safe_model,
        )
        self._persist()
        return {"success": True, "name": name, "agent_count": len(self._agents)}

    def register_skill(self, name: str, description: str, content: str) -> dict:
        """Register a dynamic skill instruction block."""
        if not name.strip():
            return {"success": False, "error": "Skill name is required"}
        if not description.strip() or not content.strip():
            return {"success": False, "error": "Skill description and content are required"}
        self._skills[name] = {
            "description": description.strip(),
            "content": content.strip(),
        }
        self._persist()
        return {"success": True, "name": name, "skill_count": len(self._skills)}
