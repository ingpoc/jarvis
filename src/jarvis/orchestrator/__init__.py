"""Jarvis orchestrator subpackage.

Provides modular components for the main orchestrator:
- JarvisOrchestrator: Main orchestration engine
- DynamicCapabilitiesManager: Runtime registration of MCP servers, agents, skills
- MCPConfigLoader: Loading MCP server configurations from .mcp.json
- SystemPromptBuilder: Building context-aware system prompts
- OrchestratorHooks: Pre/post tool and message hooks
"""

from .core import JarvisOrchestrator
from .capabilities import DynamicCapabilitiesManager
from .mcp_loader import MCPConfigLoader
from .prompts import SystemPromptBuilder
from .hooks import OrchestratorHooks

__all__ = [
    "JarvisOrchestrator",
    "DynamicCapabilitiesManager",
    "MCPConfigLoader",
    "SystemPromptBuilder",
    "OrchestratorHooks",
]
