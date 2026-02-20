"""Jarvis services - pluggable integrations."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ElevenLabsTTS"]


def __getattr__(name: str):
    if name != "ElevenLabsTTS":
        raise AttributeError(f"module 'jarvis.services' has no attribute '{name}'")
    value = getattr(import_module("jarvis.services.elevenlabs_tts"), "ElevenLabsTTS")
    globals()[name] = value
    return value
