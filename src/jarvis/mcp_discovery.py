"""MCP discovery & creation pipeline.

Discovers, proposes, generates, installs, and registers MCP servers
from the npm/GitHub ecosystem.

Pipeline:
1. Registry search: query npm/GitHub for MCP servers matching a need
2. Server proposal: present candidates to user for approval
3. Server generation: generate custom MCP server code via GLM 4.7
4. Server installation: install approved servers to local directory
5. Server registration: add to MCP config for future sessions
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MCP_SERVERS_DIR = Path.home() / ".jarvis" / "mcp-servers"
MCP_CONFIG_FILE = Path.home() / ".jarvis" / "mcp-config.json"


@dataclass
class MCPServerCandidate:
    """A discovered MCP server candidate."""
    name: str
    description: str
    source: str  # "npm", "github", "generated"
    package_name: str  # npm package or github repo
    version: str = ""
    tools: list[str] = field(default_factory=list)
    install_command: str = ""
    confidence: float = 0.0
    approved: bool = False


@dataclass
class MCPServerConfig:
    """Configuration for an installed MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    health_check: bool = True


class MCPDiscoveryPipeline:
    """Discovers and manages MCP servers from the ecosystem."""

    def __init__(self):
        MCP_SERVERS_DIR.mkdir(parents=True, exist_ok=True)
        self._installed_servers: dict[str, MCPServerConfig] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load MCP server configuration from disk."""
        if MCP_CONFIG_FILE.exists():
            try:
                data = json.loads(MCP_CONFIG_FILE.read_text())
                for name, cfg in data.get("servers", {}).items():
                    self._installed_servers[name] = MCPServerConfig(
                        name=name,
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env=cfg.get("env", {}),
                        enabled=cfg.get("enabled", True),
                        health_check=cfg.get("health_check", True),
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load MCP config: {e}")

    def _save_config(self) -> None:
        """Save MCP server configuration to disk."""
        data = {
            "servers": {
                name: {
                    "command": cfg.command,
                    "args": cfg.args,
                    "env": cfg.env,
                    "enabled": cfg.enabled,
                    "health_check": cfg.health_check,
                }
                for name, cfg in self._installed_servers.items()
            }
        }
        MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        MCP_CONFIG_FILE.write_text(json.dumps(data, indent=2))

    async def search_npm_registry(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[MCPServerCandidate]:
        """Search npm registry for MCP servers.

        Args:
            query: Search query (e.g., "mcp-server database")
            max_results: Maximum number of results

        Returns:
            List of MCP server candidates
        """
        candidates = []
        try:
            import httpx

            search_query = f"mcp-server {query}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://registry.npmjs.org/-/v1/search",
                    params={
                        "text": search_query,
                        "size": max_results,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(f"npm search failed: {resp.status_code}")
                    return candidates

                data = resp.json()
                for obj in data.get("objects", []):
                    pkg = obj.get("package", {})
                    name = pkg.get("name", "")
                    # Filter for MCP-related packages
                    if "mcp" not in name.lower() and "mcp" not in pkg.get("description", "").lower():
                        continue

                    candidates.append(MCPServerCandidate(
                        name=name.replace("@", "").replace("/", "-"),
                        description=pkg.get("description", ""),
                        source="npm",
                        package_name=name,
                        version=pkg.get("version", "latest"),
                        install_command=f"npm install -g {name}",
                        confidence=min(1.0, obj.get("score", {}).get("final", 0.5)),
                    ))

        except ImportError:
            logger.warning("httpx not available for npm registry search")
        except Exception as e:
            logger.error(f"npm registry search error: {e}")

        logger.info(f"Found {len(candidates)} MCP server candidates on npm for '{query}'")
        return candidates

    async def search_github(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[MCPServerCandidate]:
        """Search GitHub for MCP server repositories.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of MCP server candidates
        """
        candidates = []
        try:
            import httpx

            search_query = f"mcp-server {query} language:typescript language:python"
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {}
                gh_token = os.environ.get("GITHUB_TOKEN")
                if gh_token:
                    headers["Authorization"] = f"token {gh_token}"

                resp = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": search_query,
                        "sort": "stars",
                        "per_page": max_results,
                    },
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning(f"GitHub search failed: {resp.status_code}")
                    return candidates

                data = resp.json()
                for repo in data.get("items", []):
                    full_name = repo.get("full_name", "")
                    candidates.append(MCPServerCandidate(
                        name=repo.get("name", ""),
                        description=repo.get("description", ""),
                        source="github",
                        package_name=full_name,
                        install_command=f"git clone https://github.com/{full_name}",
                        confidence=min(1.0, repo.get("stargazers_count", 0) / 100),
                    ))

        except ImportError:
            logger.warning("httpx not available for GitHub search")
        except Exception as e:
            logger.error(f"GitHub search error: {e}")

        logger.info(f"Found {len(candidates)} MCP server candidates on GitHub for '{query}'")
        return candidates

    async def search_all(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[MCPServerCandidate]:
        """Search all registries for MCP servers.

        Combines results from npm and GitHub, sorted by confidence.
        """
        npm_results, github_results = await asyncio.gather(
            self.search_npm_registry(query, max_results),
            self.search_github(query, max_results),
            return_exceptions=True,
        )

        candidates = []
        if isinstance(npm_results, list):
            candidates.extend(npm_results)
        if isinstance(github_results, list):
            candidates.extend(github_results)

        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:max_results]

    def propose_server(self, candidate: MCPServerCandidate) -> dict:
        """Create a proposal for user approval.

        Returns a proposal dict that can be sent to the UI for
        user review and approval.
        """
        return {
            "name": candidate.name,
            "description": candidate.description,
            "source": candidate.source,
            "package": candidate.package_name,
            "install_command": candidate.install_command,
            "confidence": candidate.confidence,
            "tools": candidate.tools,
            "requires_approval": True,
        }

    async def generate_server(
        self,
        name: str,
        description: str,
        tools: list[dict],
    ) -> dict[str, Any]:
        """Generate a custom MCP server using GLM 4.7.

        Args:
            name: Server name
            description: What the server should do
            tools: List of tool definitions [{name, description, parameters}]

        Returns:
            dict with generated server code and metadata
        """
        # Build the MCP server template
        tool_defs = []
        for tool in tools:
            tool_defs.append(f"""
    @server.tool()
    async def {tool['name']}({', '.join(p['name'] + ': str' for p in tool.get('parameters', []))}) -> str:
        \"\"\"{tool['description']}\"\"\"
        # TODO: Implement {tool['name']}
        return json.dumps({{"status": "not_implemented", "tool": "{tool['name']}"}})
""")

        server_code = f'''"""MCP Server: {name}

{description}

Auto-generated by Jarvis v2.0 MCP Discovery Pipeline.
"""

import json
from mcp.server import Server

server = Server("{name}")

{"".join(tool_defs)}

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
'''

        # Save to MCP servers directory
        server_dir = MCP_SERVERS_DIR / name
        server_dir.mkdir(parents=True, exist_ok=True)
        server_file = server_dir / "server.py"
        server_file.write_text(server_code)

        logger.info(f"Generated MCP server '{name}' at {server_file}")

        return {
            "name": name,
            "path": str(server_file),
            "tools": [t["name"] for t in tools],
            "source": "generated",
        }

    async def install_server(self, candidate: MCPServerCandidate) -> dict[str, Any]:
        """Install an approved MCP server.

        Args:
            candidate: Approved server candidate

        Returns:
            dict with installation results
        """
        if candidate.source == "npm":
            return await self._install_npm_server(candidate)
        elif candidate.source == "github":
            return await self._install_github_server(candidate)
        elif candidate.source == "generated":
            return {"status": "already_installed", "name": candidate.name}
        else:
            return {"status": "error", "error": f"Unknown source: {candidate.source}"}

    async def _install_npm_server(self, candidate: MCPServerCandidate) -> dict[str, Any]:
        """Install an MCP server from npm."""
        server_dir = MCP_SERVERS_DIR / candidate.name
        server_dir.mkdir(parents=True, exist_ok=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "install", candidate.package_name,
                cwd=str(server_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode != 0:
                return {
                    "status": "error",
                    "error": stderr.decode().strip(),
                }

            return {
                "status": "installed",
                "name": candidate.name,
                "path": str(server_dir),
                "source": "npm",
            }

        except asyncio.TimeoutError:
            return {"status": "error", "error": "Installation timed out"}
        except FileNotFoundError:
            return {"status": "error", "error": "npm not found"}

    async def _install_github_server(self, candidate: MCPServerCandidate) -> dict[str, Any]:
        """Install an MCP server from GitHub."""
        server_dir = MCP_SERVERS_DIR / candidate.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone",
                f"https://github.com/{candidate.package_name}",
                str(server_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode != 0:
                return {
                    "status": "error",
                    "error": stderr.decode().strip(),
                }

            return {
                "status": "installed",
                "name": candidate.name,
                "path": str(server_dir),
                "source": "github",
            }

        except asyncio.TimeoutError:
            return {"status": "error", "error": "Clone timed out"}
        except FileNotFoundError:
            return {"status": "error", "error": "git not found"}

    def register_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> MCPServerConfig:
        """Register an installed MCP server in the config.

        Args:
            name: Server name
            command: Command to start the server
            args: Command arguments
            env: Environment variables

        Returns:
            The registered server config
        """
        config = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
        )
        self._installed_servers[name] = config
        self._save_config()
        logger.info(f"Registered MCP server: {name}")
        return config

    def unregister_server(self, name: str) -> bool:
        """Remove a server from the config."""
        if name in self._installed_servers:
            del self._installed_servers[name]
            self._save_config()
            return True
        return False

    def list_servers(self) -> list[MCPServerConfig]:
        """List all registered MCP servers."""
        return list(self._installed_servers.values())

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "installed_servers": len(self._installed_servers),
            "enabled_servers": sum(
                1 for s in self._installed_servers.values() if s.enabled
            ),
            "servers_dir": str(MCP_SERVERS_DIR),
            "config_file": str(MCP_CONFIG_FILE),
        }


# Singleton instance
_pipeline_instance: MCPDiscoveryPipeline | None = None


def get_mcp_discovery() -> MCPDiscoveryPipeline:
    """Get the global MCP discovery pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = MCPDiscoveryPipeline()
    return _pipeline_instance
