"""Jarvis: Autonomous Mac-native development partner."""

from __future__ import annotations

from importlib import import_module

__version__ = "0.5.0"

__all__ = [
    "JarvisOrchestrator",
    "ContainerTemplate",
    "DockerFallback",
    "get_docker_fallback",
    "LoopDetector",
    "DecisionTracer",
    "BuildHarness",
    "HarnessState",
    "FeatureManager",
    "Feature",
    "EventCollector",
    "CodeOrchestrator",
    "FileSystemWatcher",
    "create_file_watcher",
    "IdleModeProcessor",
    "IdleState",
    "build_context_layers",
    "format_context_for_prompt",
    "build_incremental_context",
    "seed_universal_heuristics",
    "auto_seed_project",
    "generate_skills_from_patterns",
    "select_session_skills",
    "MAX_SKILLS_PER_SESSION",
    "MCPDiscoveryPipeline",
    "get_mcp_discovery",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "JarvisOrchestrator": ("jarvis.orchestrator", "JarvisOrchestrator"),
    "ContainerTemplate": ("jarvis.container_templates", "ContainerTemplate"),
    "DockerFallback": ("jarvis.container_templates", "DockerFallback"),
    "get_docker_fallback": ("jarvis.container_templates", "get_docker_fallback"),
    "LoopDetector": ("jarvis.loop_detector", "LoopDetector"),
    "DecisionTracer": ("jarvis.decision_tracer", "DecisionTracer"),
    "BuildHarness": ("jarvis.harness", "BuildHarness"),
    "HarnessState": ("jarvis.harness", "HarnessState"),
    "FeatureManager": ("jarvis.feature_manager", "FeatureManager"),
    "Feature": ("jarvis.feature_manager", "Feature"),
    "EventCollector": ("jarvis.events", "EventCollector"),
    "CodeOrchestrator": ("jarvis.code_orchestrator", "CodeOrchestrator"),
    "FileSystemWatcher": ("jarvis.fs_watcher", "FileSystemWatcher"),
    "create_file_watcher": ("jarvis.fs_watcher", "create_file_watcher"),
    "IdleModeProcessor": ("jarvis.idle_mode", "IdleModeProcessor"),
    "IdleState": ("jarvis.idle_mode", "IdleState"),
    "build_context_layers": ("jarvis.context_layers", "build_context_layers"),
    "format_context_for_prompt": ("jarvis.context_layers", "format_context_for_prompt"),
    "build_incremental_context": ("jarvis.context_layers", "build_incremental_context"),
    "seed_universal_heuristics": ("jarvis.universal_heuristics", "seed_universal_heuristics"),
    "auto_seed_project": ("jarvis.universal_heuristics", "auto_seed_project"),
    "generate_skills_from_patterns": ("jarvis.skill_generator", "generate_skills_from_patterns"),
    "select_session_skills": ("jarvis.skill_generator", "select_session_skills"),
    "MAX_SKILLS_PER_SESSION": ("jarvis.skill_generator", "MAX_SKILLS_PER_SESSION"),
    "MCPDiscoveryPipeline": ("jarvis.mcp_discovery", "MCPDiscoveryPipeline"),
    "get_mcp_discovery": ("jarvis.mcp_discovery", "get_mcp_discovery"),
}


def __getattr__(name: str):
    """Lazy-load heavy exports to keep base import light."""
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'jarvis' has no attribute '{name}'")
    module_name, attr_name = export
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
