"""Jarvis configuration management."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

JARVIS_HOME = Path.home() / ".jarvis"
JARVIS_DB = JARVIS_HOME / "jarvis.db"
JARVIS_CONFIG = JARVIS_HOME / "config.json"
JARVIS_LOGS = JARVIS_HOME / "logs"
DEFAULT_WORKSPACE_ROOT = str((JARVIS_HOME / "workspaces").expanduser())


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

    Supports standard Claude model IDs and z.ai GLM models via environment variables.

    For z.ai/GLM models, use model aliases (opus/sonnet/haiku) and set environment:
        export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
        export ANTHROPIC_AUTH_TOKEN=<your-z.ai-api-key>
        export ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5
        export ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5
        export ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5

    Then set Jarvis to use aliases:
        jarvis config models.executor=sonnet
        jarvis config models.planner=opus

    Local models (use provider_type to switch):
        - foundation-models: Apple Foundation Models (direct Python)
    """

    planner: str = "opus"
    executor: str = "sonnet"
    reviewer: str = "sonnet"
    quick: str = "haiku"
    provider_type: str = "anthropic"  # anthropic, foundation, mlx, opencode


@dataclass
class SlackConfig:
    """Slack integration settings."""

    bot_token: str = ""
    app_token: str = ""
    default_channel: str = "#jarvis"
    research_channel: str = "#jarvisresearch"
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
class A2AConfig:
    """A2A protocol server settings."""

    enabled: bool = True
    port: int = 9848  # Can override with JARVIS_A2A_PORT env var
    default_trust_tier: int = 1
    token_path: str = ""  # Empty means ~/.jarvis/a2a_token
    task_timeout_seconds: int = 300  # 5 minutes for blocking tasks


@dataclass
class MailConfig:
    """Mail assistant settings."""

    enabled: bool = False
    digest_enabled: bool = False
    digest_time_local: str = "08:00"  # HH:MM (24h)
    timezone: str = "America/Los_Angeles"
    window_hours: int = 24
    include_weekends: bool = True


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
    a2a: A2AConfig = field(default_factory=A2AConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    idle: IdleConfig = field(default_factory=IdleConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    trust_tier: int = 1  # Default T1 (Assistant)
    workspace_root: str | None = DEFAULT_WORKSPACE_ROOT  # Default workspace directory

    @classmethod
    def load(cls) -> "JarvisConfig":
        """Load config from disk or return defaults.

        Also checks ANTHROPIC_DEFAULT_*_MODEL env vars for GLM 4.7 routing.
        Env vars override file config for model selection.
        """
        config = cls()

        def apply_section(section_obj, data, name):
            if name in data:
                for k, v in data[name].items():
                    setattr(section_obj, k, v)

        if JARVIS_CONFIG.exists():
            data = json.loads(JARVIS_CONFIG.read_text())
            apply_section(config.container, data, "container")
            apply_section(config.budget, data, "budget")
            apply_section(config.models, data, "models")
            apply_section(config.slack, data, "slack")
            apply_section(config.voice, data, "voice")
            apply_section(config.mail, data, "mail")
            apply_section(config.knowledge, data, "knowledge")
            apply_section(config.idle, data, "idle")
            apply_section(config.resources, data, "resources")
            apply_section(config.a2a, data, "a2a")
            if "trust_tier" in data:
                config.trust_tier = data["trust_tier"]
            if "workspace_root" in data:
                config.workspace_root = data["workspace_root"]

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
        workspace_root = os.environ.get("JARVIS_WORKSPACE")
        if workspace_root:
            config.workspace_root = workspace_root

        # Env var overrides (supports GLM 4.7 / z.ai proxy).
        # Only apply alias-based overrides when the current value is still an alias.
        # This preserves explicit model selections saved by the menu-bar model picker
        # (for example: foundation-models or a concrete Claude model ID).
        def _is_alias(value: str, alias: str) -> bool:
            return str(value or "").strip().lower() == alias

        opus_model = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        sonnet_model = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        haiku_model = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")

        if opus_model and _is_alias(config.models.planner, "opus"):
            config.models.planner = opus_model
        if sonnet_model and _is_alias(config.models.executor, "sonnet"):
            config.models.executor = sonnet_model
        if sonnet_model and _is_alias(config.models.reviewer, "sonnet"):
            config.models.reviewer = sonnet_model
        if haiku_model and _is_alias(config.models.quick, "haiku"):
            config.models.quick = haiku_model

        # A2A env var overrides
        a2a_port = os.environ.get("JARVIS_A2A_PORT")
        if a2a_port:
            config.a2a.port = int(a2a_port)
        a2a_enabled = os.environ.get("JARVIS_A2A_ENABLED")
        if a2a_enabled:
            config.a2a.enabled = a2a_enabled.lower() in ("true", "1", "yes")

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
                "provider_type": getattr(self.models, "provider_type", "anthropic"),
            },
            "slack": {
                "bot_token": self.slack.bot_token,
                "app_token": self.slack.app_token,
                "default_channel": self.slack.default_channel,
                "research_channel": self.slack.research_channel,
                "enabled": self.slack.enabled,
            },
            "voice": {
                "api_key": self.voice.api_key,
                "agent_id": self.voice.agent_id,
                "enabled": self.voice.enabled,
                "auto_call_on_error": self.voice.auto_call_on_error,
                "auto_call_on_approval": self.voice.auto_call_on_approval,
            },
            "mail": {
                "enabled": self.mail.enabled,
                "digest_enabled": self.mail.digest_enabled,
                "digest_time_local": self.mail.digest_time_local,
                "timezone": self.mail.timezone,
                "window_hours": self.mail.window_hours,
                "include_weekends": self.mail.include_weekends,
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
            "a2a": {
                "enabled": self.a2a.enabled,
                "port": self.a2a.port,
                "default_trust_tier": self.a2a.default_trust_tier,
                "token_path": self.a2a.token_path,
                "task_timeout_seconds": self.a2a.task_timeout_seconds,
            },
            "trust_tier": self.trust_tier,
        }
        JARVIS_CONFIG.write_text(json.dumps(data, indent=2))


def ensure_jarvis_home() -> None:
    """Create Jarvis home directory structure."""
    JARVIS_HOME.mkdir(parents=True, exist_ok=True)
    JARVIS_LOGS.mkdir(parents=True, exist_ok=True)
