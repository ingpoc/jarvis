"""Jarvis configuration management."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

JARVIS_HOME = Path.home() / ".jarvis"
JARVIS_DB = JARVIS_HOME / "jarvis.db"
JARVIS_CONFIG = JARVIS_HOME / "config.json"
JARVIS_LOGS = JARVIS_HOME / "logs"
DEFAULT_WORKSPACE_ROOT = "/Users/gurusharan/Documents/remote-claude/Jarvisworkspace"


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
class ResearchConfig:
    """Autonomous idle research settings."""

    # Opt-in: keep disabled by default to avoid unexpected background execution/spam.
    enabled: bool = False
    topic: str = "@bcherny Claude Code workflow optimization and autonomous dev systems"
    interval_minutes: int = 30
    max_runs_per_day: int = 48
    max_sources_per_run: int = 3
    min_days_before_repeat: int = 14
    bookmarks_file: str = "~/.jarvis/x-bookmarks.txt"
    enable_x_bookmarks_api: bool = False
    source_urls: list[str] = field(default_factory=lambda: [
        "https://www.anthropic.com/engineering",
        "https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/",
        "https://openai.com/index/inside-our-in-house-data-agent/",
    ])


@dataclass
class JarvisConfig:
    """Top-level Jarvis configuration."""

    container: ContainerConfig = field(default_factory=ContainerConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    workspace_root: str = DEFAULT_WORKSPACE_ROOT
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
            if "research" in data:
                for k, v in data["research"].items():
                    setattr(config.research, k, v)
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
            "research": {
                "enabled": self.research.enabled,
                "topic": self.research.topic,
                "interval_minutes": self.research.interval_minutes,
                "max_runs_per_day": self.research.max_runs_per_day,
                "max_sources_per_run": self.research.max_sources_per_run,
                "min_days_before_repeat": self.research.min_days_before_repeat,
                "bookmarks_file": self.research.bookmarks_file,
                "enable_x_bookmarks_api": self.research.enable_x_bookmarks_api,
                "source_urls": self.research.source_urls,
            },
            "workspace_root": self.workspace_root,
            "trust_tier": self.trust_tier,
        }
        JARVIS_CONFIG.write_text(json.dumps(data, indent=2))


def ensure_jarvis_home() -> None:
    """Create Jarvis home directory structure."""
    JARVIS_HOME.mkdir(parents=True, exist_ok=True)
    JARVIS_LOGS.mkdir(parents=True, exist_ok=True)
