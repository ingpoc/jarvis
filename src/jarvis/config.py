"""Jarvis configuration management."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

JARVIS_HOME = Path.home() / ".jarvis"
JARVIS_DB = JARVIS_HOME / "jarvis.db"
JARVIS_CONFIG = JARVIS_HOME / "config.json"
JARVIS_LOGS = JARVIS_HOME / "logs"


@dataclass
class ContainerConfig:
    """Apple Container defaults."""

    default_image: str = "ubuntu:latest"
    default_cpus: int = 4
    default_memory: str = "2G"
    network: str = "default"
    workspace_dir: str = "/workspace"
    default_template: str = "auto"


@dataclass
class BudgetConfig:
    """Spending limits."""

    max_per_session_usd: float = 50.0
    max_per_day_usd: float = 200.0
    max_turns_per_subtask: int = 10
    max_turns_per_task: int = 50


@dataclass
class ModelConfig:
    """Model routing.

    Supports standard Claude model IDs and GLM 4.7 proxy IDs.
    When using GLM 4.7 (z.ai proxy), set via:
        jarvis config models.executor=glm-4.7
        jarvis config models.planner=glm-4.7
    """

    planner: str = "claude-opus-4-6"
    executor: str = "claude-sonnet-4-5-20250929"
    reviewer: str = "claude-sonnet-4-5-20250929"
    quick: str = "claude-haiku-4-5-20251001"


@dataclass
class SlackConfig:
    """Slack integration settings."""

    bot_token: str = ""
    app_token: str = ""
    default_channel: str = "#jarvis"
    enabled: bool = False


@dataclass
class VoiceConfig:
    """ElevenLabs voice integration settings."""

    api_key: str = ""
    agent_id: str = ""
    enabled: bool = False
    auto_call_on_error: bool = False
    auto_call_on_approval: bool = True


@dataclass
class KnowledgeConfig:
    """Knowledge system settings."""

    enable_learning: bool = True
    enable_skill_generation: bool = True
    skill_generation_threshold: int = 3  # Minimum pattern occurrences
    context_pre_filtering: bool = True
    context_reduction_target: float = 0.7  # 70% reduction target


@dataclass
class IdleConfig:
    """Idle mode processing settings."""

    idle_threshold_minutes: float = 10.0
    enable_background_processing: bool = True
    skill_generation_batch_size: int = 5
    file_watcher_poll_interval: float = 30.0
    file_watcher_debounce: float = 5.0


@dataclass
class ResourceConfig:
    """Resource management settings (24GB Mac Mini budget)."""

    qwen3_memory_mb: int = 3000
    container_memory_mb: int = 1500
    max_concurrent_containers: int = 2


@dataclass
class JarvisConfig:
    """Top-level Jarvis configuration."""

    container: ContainerConfig = field(default_factory=ContainerConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    idle: IdleConfig = field(default_factory=IdleConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    trust_tier: int = 1  # Default T1 (Assistant)

    @classmethod
    def load(cls) -> "JarvisConfig":
        """Load config from disk or return defaults.

        Also checks ANTHROPIC_DEFAULT_*_MODEL env vars for GLM 4.7 routing.
        Env vars override file config for model selection.
        """
        config = cls()
        if JARVIS_CONFIG.exists():
            data = json.loads(JARVIS_CONFIG.read_text())
            if "container" in data:
                for k, v in data["container"].items():
                    setattr(config.container, k, v)
            if "budget" in data:
                for k, v in data["budget"].items():
                    setattr(config.budget, k, v)
            if "models" in data:
                for k, v in data["models"].items():
                    setattr(config.models, k, v)
            if "slack" in data:
                for k, v in data["slack"].items():
                    setattr(config.slack, k, v)
            if "voice" in data:
                for k, v in data["voice"].items():
                    setattr(config.voice, k, v)
            if "knowledge" in data:
                for k, v in data["knowledge"].items():
                    setattr(config.knowledge, k, v)
            if "idle" in data:
                for k, v in data["idle"].items():
                    setattr(config.idle, k, v)
            if "resources" in data:
                for k, v in data["resources"].items():
                    setattr(config.resources, k, v)
            if "trust_tier" in data:
                config.trust_tier = data["trust_tier"]

        # Env var overrides for tokens
        slack_bot = os.environ.get("JARVIS_SLACK_BOT_TOKEN")
        slack_app = os.environ.get("JARVIS_SLACK_APP_TOKEN")
        voice_key = os.environ.get("ELEVENLABS_API_KEY")
        voice_agent = os.environ.get("ELEVENLABS_AGENT_ID")

        if slack_bot:
            config.slack.bot_token = slack_bot
        if slack_app:
            config.slack.app_token = slack_app
        if voice_key:
            config.voice.api_key = voice_key
        if voice_agent:
            config.voice.agent_id = voice_agent

        # Env var overrides (supports GLM 4.7 / z.ai proxy)
        opus_model = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        sonnet_model = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        haiku_model = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")

        if opus_model:
            config.models.planner = opus_model
        if sonnet_model:
            config.models.executor = sonnet_model
            config.models.reviewer = sonnet_model
        if haiku_model:
            config.models.quick = haiku_model

        return config

    def save(self) -> None:
        """Persist config to disk."""
        JARVIS_HOME.mkdir(parents=True, exist_ok=True)
        data = {
            "container": {
                "default_image": self.container.default_image,
                "default_cpus": self.container.default_cpus,
                "default_memory": self.container.default_memory,
                "network": self.container.network,
                "workspace_dir": self.container.workspace_dir,
                "default_template": self.container.default_template,
            },
            "budget": {
                "max_per_session_usd": self.budget.max_per_session_usd,
                "max_per_day_usd": self.budget.max_per_day_usd,
                "max_turns_per_subtask": self.budget.max_turns_per_subtask,
                "max_turns_per_task": self.budget.max_turns_per_task,
            },
            "models": {
                "planner": self.models.planner,
                "executor": self.models.executor,
                "reviewer": self.models.reviewer,
                "quick": self.models.quick,
            },
            "slack": {
                "bot_token": self.slack.bot_token,
                "app_token": self.slack.app_token,
                "default_channel": self.slack.default_channel,
                "enabled": self.slack.enabled,
            },
            "voice": {
                "api_key": self.voice.api_key,
                "agent_id": self.voice.agent_id,
                "enabled": self.voice.enabled,
                "auto_call_on_error": self.voice.auto_call_on_error,
                "auto_call_on_approval": self.voice.auto_call_on_approval,
            },
            "knowledge": {
                "enable_learning": self.knowledge.enable_learning,
                "enable_skill_generation": self.knowledge.enable_skill_generation,
                "skill_generation_threshold": self.knowledge.skill_generation_threshold,
                "context_pre_filtering": self.knowledge.context_pre_filtering,
                "context_reduction_target": self.knowledge.context_reduction_target,
            },
            "idle": {
                "idle_threshold_minutes": self.idle.idle_threshold_minutes,
                "enable_background_processing": self.idle.enable_background_processing,
                "skill_generation_batch_size": self.idle.skill_generation_batch_size,
                "file_watcher_poll_interval": self.idle.file_watcher_poll_interval,
                "file_watcher_debounce": self.idle.file_watcher_debounce,
            },
            "resources": {
                "qwen3_memory_mb": self.resources.qwen3_memory_mb,
                "container_memory_mb": self.resources.container_memory_mb,
                "max_concurrent_containers": self.resources.max_concurrent_containers,
            },
            "trust_tier": self.trust_tier,
        }
        JARVIS_CONFIG.write_text(json.dumps(data, indent=2))


def ensure_jarvis_home() -> None:
    """Create Jarvis home directory structure."""
    JARVIS_HOME.mkdir(parents=True, exist_ok=True)
    JARVIS_LOGS.mkdir(parents=True, exist_ok=True)
