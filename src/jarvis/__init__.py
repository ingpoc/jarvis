"""Jarvis: Autonomous Mac-native development partner."""

__version__ = "0.4.0"

from jarvis.orchestrator import JarvisOrchestrator
from jarvis.agents import MultiAgentPipeline
from jarvis.container_templates import ContainerTemplate
from jarvis.loop_detector import LoopDetector
from jarvis.decision_tracer import DecisionTracer
from jarvis.harness import BuildHarness, HarnessState
from jarvis.feature_manager import FeatureManager, Feature
from jarvis.events import EventCollector
from jarvis.code_orchestrator import CodeOrchestrator
from jarvis.fs_watcher import FileSystemWatcher
from jarvis.idle_mode import IdleModeProcessor, IdleState
from jarvis.context_layers import build_context_layers, format_context_for_prompt
from jarvis.universal_heuristics import seed_universal_heuristics, auto_seed_project

__all__ = [
    "JarvisOrchestrator",
    "MultiAgentPipeline",
    "ContainerTemplate",
    "LoopDetector",
    "DecisionTracer",
    "BuildHarness",
    "HarnessState",
    "FeatureManager",
    "Feature",
    "EventCollector",
    "CodeOrchestrator",
    "FileSystemWatcher",
    "IdleModeProcessor",
    "IdleState",
    "build_context_layers",
    "format_context_for_prompt",
    "seed_universal_heuristics",
    "auto_seed_project",
]
