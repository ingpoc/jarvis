"""Jarvis: Autonomous Mac-native development partner."""

__version__ = "0.2.0"

from jarvis.orchestrator import JarvisOrchestrator
from jarvis.agents import MultiAgentPipeline
from jarvis.container_templates import ContainerTemplate
from jarvis.loop_detector import LoopDetector
from jarvis.decision_tracer import DecisionTracer
from jarvis.harness import BuildHarness, HarnessState
from jarvis.feature_manager import FeatureManager, Feature
from jarvis.events import EventCollector
from jarvis.code_orchestrator import CodeOrchestrator

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
]
