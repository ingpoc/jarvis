"""ElevenLabs Text-to-Speech service for Jarvis voice output."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from jarvis.config import VoiceConfig
    from jarvis.events import EventCollector

logger = logging.getLogger(__name__)


class ElevenLabsTTS:
    """ElevenLabs streaming TTS service."""

    API_BASE = "https://api.elevenlabs.io/v1"

    # Default voice - can be configured
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" voice

    # Popular voice presets
    VOICE_PRESETS: dict[str, str] = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "drew": "29vD33N1CtxCmqQRPOWJ",
        "clyde": "2EiwWnXFnvU5JabPnv8n",
        "sarah": "EXAVITQu4vr4xnSDxMaL",
        "adam": "ER6fLYmz5xvfGDxjkJ3o",
        "fin": "flq6F7mA2pmHP6SGX0oB",
        "antoni": "ErXwobaYiN0q8SxFU9eQ",
        "thomas": "VR6DPewxieCOVkMmCnfZ",
    }

    def __init__(
        self,
        config: VoiceConfig | None = None,
        api_key: str = "",
        voice_id: str = "",
        model_id: str = "eleven_multilingual_v2",
        event_collector: EventCollector | None = None,
        auto_speak_errors: bool = False,
    ):
        """Initialize TTS service.

        Args:
            config: Voice configuration with API key (optional)
            api_key: ElevenLabs API key (overrides config)
            voice_id: Voice ID to use (overrides config)
            model_id: TTS model ID
            event_collector: Optional event collector for auto-speak
            auto_speak_errors: If True, speak error events automatically
        """
        # Use config if provided, otherwise use direct params
        if config is not None:
            self.config = config
            self._api_key = config.api_key
            self._voice_id = config.agent_id or self.DEFAULT_VOICE_ID
            self._enabled = config.enabled
        else:
            self._api_key = api_key
            self._voice_id = voice_id or self.DEFAULT_VOICE_ID
            self._enabled = bool(api_key)
            # Create a minimal config-like object
            class _Config:
                def __init__(self, api_key: str, agent_id: str, enabled: bool):
                    self.api_key = api_key
                    self.agent_id = agent_id
                    self.enabled = enabled
            self.config = _Config(self._api_key, self._voice_id, self._enabled)

        self._model_id = model_id
        self._event_collector = event_collector
        self._auto_speak_errors = auto_speak_errors
        self._client: httpx.AsyncClient | None = None

        # Subscribe to events if auto-speak enabled
        if event_collector and auto_speak_errors:
            event_collector.add_listener(self._on_event)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"xi-api-key": self._api_key},
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _on_event(self, event_data: dict):
        """Handle events from EventCollector."""
        event_type = event_data.get("event_type", "")
        if event_type == "error" and self._auto_speak_errors:
            summary = event_data.get("summary", "An error occurred")
            asyncio.create_task(self.speak_and_play(f"Error: {summary}"))

    async def speak(self, text: str, voice_id: str | None = None) -> Path | None:
        """Convert text to speech and save to file.

        Args:
            text: Text to synthesize

        Returns:
            Path to audio file if successful, None otherwise
        """
        if not self.config.enabled or not self.config.api_key:
            logger.debug("TTS disabled or no API key")
            return None

        if not text or not text.strip():
            return None

        try:
            # Call ElevenLabs TTS API
            response = await self.client.post(
                f"{self.API_BASE}/text-to-speech/{self.voice_id}",
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    }
                }
            )
            response.raise_for_status()

            # Save audio to temp file
            output_path = Path(tempfile.gettempdir()) / f"jarvis_tts_{id(text)}.mp3"
            output_path.write_bytes(response.content)

            logger.debug(f"TTS audio saved to {output_path}")
            return output_path

        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.status_code} {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    async def get_available_voices(self) -> list[dict]:
        """Get list of available voices.

        Returns:
            List of voice dictionaries
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.API_BASE}/voices")
            response.raise_for_status()
            data = response.json()
            return data.get("voices", [])
        except Exception as e:
            logger.warning(f"Failed to get voices: {e}")
            return []

    @staticmethod
    def get_voice_id(name: str) -> str | None:
        """Get voice ID by name (case-insensitive).

        Args:
            name: Voice name (e.g., "rachel", "Rachel")

        Returns:
            Voice ID or None if not found
        """
        return ElevenLabsTTS.VOICE_PRESETS.get(name.lower())

    @staticmethod
    def list_available_voices() -> dict[str, str]:
        """List all available voice presets.

        Returns:
            Dict mapping voice names to IDs
        """
        return ElevenLabsTTS.VOICE_PRESETS.copy()


async def play_audio_file(file_path: Path) -> bool:
    """Play audio file on macOS using afplay.

    Args:
        file_path: Path to audio file

    Returns:
        True if successful, False otherwise
    """
    try:
        import subprocess

        proc = await asyncio.create_subprocess_exec(
            "afplay",
            str(file_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        return proc.returncode == 0

    except Exception as e:
        logger.error(f"Audio playback failed: {e}")
        return False


async def speak_and_play(text: str, tts: ElevenLabsTTS) -> bool:
    """Convert text to speech and play it.

    Args:
        text: Text to speak
        tts: TTS service instance

    Returns:
        True if successful, False otherwise
    """
    audio_file = await tts.speak(text)
    if not audio_file:
        return False

    try:
        result = await play_audio_file(audio_file)
        # Cleanup temp file
        audio_file.unlink(missing_ok=True)
        return result
    except Exception:
        audio_file.unlink(missing_ok=True)
        return False


async def demo():
    """Demo the TTS service."""
    import os

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("Set ELEVENLABS_API_KEY env var")
        return

    tts = ElevenLabsTTS(api_key=api_key)

    # List voices
    print("\nAvailable voice presets:")
    for name, voice_id in tts.list_available_voices().items():
        print(f"  - {name}: {voice_id}")

    # Speak
    print("\nSpeaking...")
    success = await speak_and_play("Hello, I am Jarvis. Your autonomous development partner.", tts)
    print(f"Success: {success}")

    await tts.close()


if __name__ == "__main__":
    asyncio.run(demo())
