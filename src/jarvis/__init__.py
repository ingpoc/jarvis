"""Jarvis: Autonomous Mac-native development partner."""

__version__ = "0.5.0"

from jarvis.orchestrator import JarvisOrchestrator
from jarvis.agents import MultiAgentPipeline
from jarvis.container_templates import ContainerTemplate, DockerFallback, get_docker_fallback
from jarvis.loop_detector import LoopDetector
from jarvis.decision_tracer import DecisionTracer
from jarvis.harness import BuildHarness, HarnessState
from jarvis.feature_manager import FeatureManager, Feature
from jarvis.events import EventCollector
from jarvis.code_orchestrator import CodeOrchestrator
from jarvis.fs_watcher import FileSystemWatcher, create_file_watcher
from jarvis.idle_mode import IdleModeProcessor, IdleState
from jarvis.context_layers import build_context_layers, format_context_for_prompt, build_incremental_context
from jarvis.universal_heuristics import seed_universal_heuristics, auto_seed_project
from jarvis.model_router import ModelRouter, get_model_router, ModelTier
from jarvis.skill_generator import (
    generate_skills_from_patterns,
    select_session_skills,
    MAX_SKILLS_PER_SESSION,
)
from jarvis.mcp_discovery import MCPDiscoveryPipeline, get_mcp_discovery

__all__ = [
    "JarvisOrchestrator",
    "MultiAgentPipeline",
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
    "ModelRouter",
    "get_model_router",
    "ModelTier",
    "generate_skills_from_patterns",
    "select_session_skills",
    "MAX_SKILLS_PER_SESSION",
    "MCPDiscoveryPipeline",
    "get_mcp_discovery",
]
