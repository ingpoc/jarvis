"""ElevenLabs voice integration: bidirectional voice for Jarvis.

Supports:
- TTS: Jarvis speaks status updates and notifications
- Voice calls: Jarvis calls user for decisions, user gives verbal commands
- WebSocket connection to ElevenLabs Conversational AI API
- macOS native audio via AVFoundation (fallback: pyaudio)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import struct
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import websockets

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

if TYPE_CHECKING:
    from jarvis.events import EventCollector

logger = logging.getLogger(__name__)

ELEVENLABS_CONVAI_URL = "wss://api.elevenlabs.io/v1/convai/conversation"


def _require_websockets():
    if not HAS_WEBSOCKETS:
        raise ImportError(
            "websockets is required for voice integration. "
            "Install with: pip install websockets"
        )


class AudioPlayer:
    """macOS-native audio playback. Falls back to writing temp files."""

    def __init__(self):
        self._use_avfoundation = False
        try:
            import AVFoundation  # noqa: F401

            self._use_avfoundation = True
        except ImportError:
            pass

    async def play_audio(self, audio_data: bytes, sample_rate: int = 22050):
        """Play raw PCM audio data."""
        if self._use_avfoundation:
            await self._play_avfoundation(audio_data, sample_rate)
        else:
            await self._play_afplay(audio_data, sample_rate)

    async def _play_avfoundation(self, audio_data: bytes, sample_rate: int):
        """Play audio using AVFoundation."""
        try:
            import AVFoundation
            import Foundation

            # Write WAV to temp file
            wav_data = self._pcm_to_wav(audio_data, sample_rate)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_data)
                temp_path = f.name

            url = Foundation.NSURL.fileURLWithPath_(temp_path)
            player = AVFoundation.AVAudioPlayer.alloc().initWithContentsOfURL_error_(url, None)
            if player:
                player.play()
                # Wait for playback
                while player.isPlaying():
                    await asyncio.sleep(0.1)

            Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"AVFoundation playback failed: {e}")

    async def _play_afplay(self, audio_data: bytes, sample_rate: int):
        """Fallback: write WAV and play with afplay."""
        wav_data = self._pcm_to_wav(audio_data, sample_rate)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_data)
            temp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "afplay", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int, channels: int = 1, bits: int = 16) -> bytes:
        """Convert raw PCM to WAV format."""
        data_size = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM format
            channels,
            sample_rate,
            sample_rate * channels * bits // 8,
            channels * bits // 8,
            bits,
            b"data",
            data_size,
        )
        return header + pcm_data


class AudioRecorder:
    """macOS-native audio recording."""

    async def record(self, duration: float = 5.0, sample_rate: int = 16000) -> bytes:
        """Record audio from default microphone. Returns raw PCM bytes."""
        try:
            # Use macOS `rec` (SoX) or fall back to silence
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "rec", "-q", "-r", str(sample_rate), "-c", "1", "-b", "16",
                temp_path, "trim", "0", str(duration),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=duration + 5)

            data = Path(temp_path).read_bytes()
            Path(temp_path).unlink(missing_ok=True)
            # Skip WAV header (44 bytes)
            return data[44:] if len(data) > 44 else b""
        except Exception as e:
            logger.warning(f"Audio recording failed: {e}")
            return b""


class ElevenLabsVoiceClient:
    """Bidirectional voice client for ElevenLabs Conversational AI."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        event_collector: EventCollector | None = None,
        auto_call_on_error: bool = False,
        auto_call_on_approval: bool = True,
    ):
        _require_websockets()
        self._api_key = api_key
        self._agent_id = agent_id
        self._event_collector = event_collector
        self._auto_call_on_error = auto_call_on_error
        self._auto_call_on_approval = auto_call_on_approval

        self._ws = None
        self._connected = False
        self._player = AudioPlayer()
        self._recorder = AudioRecorder()
        self._conversation_id: str | None = None

        # Subscribe to events
        if self._event_collector:
            self._event_collector.add_listener(self._on_event)

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self):
        """Establish WebSocket connection to ElevenLabs."""
        url = f"{ELEVENLABS_CONVAI_URL}?agent_id={self._agent_id}"
        headers = {"xi-api-key": self._api_key}

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._connected = True
        logger.info("Voice client connected to ElevenLabs")

        # Start receive loop
        asyncio.create_task(self._receive_loop())

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            logger.info("Voice client disconnected")

    async def speak(self, text: str):
        """Send text for TTS playback (one-shot)."""
        if not self._connected:
            await self.connect()

        await self._ws.send(json.dumps({
            "type": "user_message",
            "text": text,
        }))

    async def call_user(self, reason: str) -> str | None:
        """Initiate a voice call: notify user, start conversation, return transcript.

        Flow:
        1. Send macOS notification that Jarvis wants to talk
        2. Wait for user to accept (or timeout)
        3. Speak the reason
        4. Listen for user response
        5. Return transcribed text

        Returns:
            User's transcribed response, or None if no response.
        """
        # Native notification
        from jarvis.notifications import notify, Priority

        await notify(
            "Jarvis wants to talk",
            reason[:100],
            Priority.CRITICAL,
            sound=True,
        )

        # Brief pause for user to notice
        await asyncio.sleep(2)

        if not self._connected:
            await self.connect()

        # Speak the reason
        await self.speak(reason)

        # Wait for and collect response
        await asyncio.sleep(1)  # Brief pause after TTS
        audio_data = await self._recorder.record(duration=10.0)

        if not audio_data:
            return None

        # Send audio to ElevenLabs for processing
        audio_b64 = base64.b64encode(audio_data).decode()
        await self._ws.send(json.dumps({
            "type": "audio",
            "audio": audio_b64,
        }))

        # Wait for transcript response
        transcript = await self._wait_for_transcript(timeout=15)
        return transcript

    async def _receive_loop(self):
        """Background loop: receive and process WebSocket messages."""
        try:
            async for message in self._ws:
                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "audio":
                    # Play received audio
                    audio_b64 = data.get("audio", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await self._player.play_audio(audio_bytes)

                elif msg_type == "conversation_id":
                    self._conversation_id = data.get("conversation_id")

                elif msg_type == "tool_call":
                    # Agent wants to call a Jarvis tool
                    await self._handle_tool_call(
                        data.get("tool_name", ""),
                        data.get("parameters", {}),
                    )

                elif msg_type == "error":
                    logger.error(f"Voice API error: {data.get('message', '')}")

        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            logger.info("Voice WebSocket connection closed")
        except Exception as e:
            self._connected = False
            logger.error(f"Voice receive loop error: {e}")

    async def _wait_for_transcript(self, timeout: float = 15) -> str | None:
        """Wait for a transcript response from the API."""
        try:
            end_time = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
                    data = json.loads(message)
                    if data.get("type") == "transcript":
                        return data.get("text", "")
                    if data.get("type") == "audio":
                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            await self._player.play_audio(base64.b64decode(audio_b64))
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            logger.warning(f"Transcript wait error: {e}")
        return None

    async def _handle_tool_call(self, tool_name: str, params: dict):
        """Route voice-triggered tool calls to Jarvis."""
        logger.info(f"Voice tool call: {tool_name}({params})")
        if self._event_collector:
            self._event_collector.emit(
                "tool_use",
                f"Voice-triggered: {tool_name}",
                metadata={"source": "voice", "tool": tool_name, "params": params},
            )

    def _on_event(self, event_data: dict):
        """Handle events from EventCollector."""
        event_type = event_data.get("event_type", "")
        summary = event_data.get("summary", "")

        if event_type == "error" and self._auto_call_on_error:
            asyncio.create_task(self.call_user(f"Error occurred: {summary}"))
        elif event_type == "approval_needed" and self._auto_call_on_approval:
            asyncio.create_task(self.call_user(f"Approval needed: {summary}"))
