"""Python client for the Foundation Models Swift bridge.

Connects to the local HTTP server running in the SwiftUI app
to perform ultra-fast on-device classification and summarization
via Apple's Foundation Models framework.

Architecture:
    Python (this client) → HTTP POST localhost:9848 → Swift server → Foundation Models

The Swift bridge runs as part of the JarvisApp menubar app.
If the bridge is not running, all methods return fallback values.
"""

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

BRIDGE_URL = "http://127.0.0.1:9848"
CONNECT_TIMEOUT = 2.0  # seconds
REQUEST_TIMEOUT = 5.0  # seconds


class FoundationModelsClient:
    """Client for the Foundation Models Swift bridge."""

    def __init__(self, base_url: str = BRIDGE_URL):
        self.base_url = base_url
        self._available: bool | None = None
        self._last_health_check: float = 0
        self._health_check_interval: float = 60.0  # Re-check every 60s
        self._request_count: int = 0
        self._total_latency_ms: float = 0

    async def _post(self, payload: dict) -> dict | None:
        """Send a POST request to the Foundation Models bridge."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )
                if response.status_code == 200:
                    return response.json()
                logger.debug(f"Bridge returned {response.status_code}")
                return None
        except ImportError:
            # Fallback to urllib if httpx not available
            return await self._post_urllib(payload)
        except Exception as e:
            logger.debug(f"Bridge request failed: {e}")
            self._available = False
            return None

    async def _post_urllib(self, payload: dict) -> dict | None:
        """Fallback POST using urllib (no httpx dependency)."""
        import urllib.request
        import urllib.error

        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.base_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT),
            )
            return json.loads(response.read().decode())
        except Exception as e:
            logger.debug(f"Bridge urllib request failed: {e}")
            self._available = False
            return None

    async def is_available(self) -> bool:
        """Check if the Foundation Models bridge is running."""
        now = time.time()
        if (
            self._available is not None
            and now - self._last_health_check < self._health_check_interval
        ):
            return self._available

        result = await self._post({"action": "health"})
        self._available = result is not None and result.get("status") == "ok"
        self._last_health_check = now

        if self._available:
            logger.info("Foundation Models bridge is available")
        return self._available

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Classify text using Foundation Models.

        Ultra-fast on-device classification (<100ms typically).

        Args:
            text: Text to classify
            categories: List of categories to classify into

        Returns:
            dict with 'label', 'confidence', 'latency_ms'
        """
        if categories is None:
            categories = ["simple", "moderate", "complex"]

        start = time.monotonic()
        result = await self._post({
            "action": "classify",
            "text": text[:1000],
            "categories": categories,
        })
        elapsed_ms = (time.monotonic() - start) * 1000

        self._request_count += 1
        self._total_latency_ms += elapsed_ms

        if result:
            return {
                "label": result.get("label", categories[0]),
                "confidence": result.get("confidence", 0.0),
                "latency_ms": result.get("latencyMs", elapsed_ms),
                "source": "foundation_models",
            }

        # Fallback
        return {
            "label": categories[0] if categories else "unknown",
            "confidence": 0.0,
            "latency_ms": elapsed_ms,
            "source": "fallback",
        }

    async def classify_task_complexity(self, task_description: str) -> dict[str, Any]:
        """Classify a development task's complexity.

        Returns 'simple', 'moderate', or 'complex' with confidence.
        """
        return await self.classify(
            task_description,
            categories=["simple", "moderate", "complex"],
        )

    async def classify_intent(self, user_input: str) -> dict[str, Any]:
        """Classify user intent from natural language input.

        Returns the detected intent category.
        """
        return await self.classify(
            user_input,
            categories=[
                "run_task", "ask_question", "view_status",
                "approve", "cancel", "configure",
            ],
        )

    async def summarize(self, text: str, max_length: int = 100) -> str:
        """Summarize text using Foundation Models.

        Args:
            text: Text to summarize
            max_length: Maximum characters in summary

        Returns:
            Summarized text
        """
        result = await self._post({
            "action": "summarize",
            "text": text[:2000],
            "max_length": max_length,
        })

        if result and "summary" in result:
            return result["summary"]

        # Fallback: simple truncation
        return text[:max_length]

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        avg_ms = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0
        )
        return {
            "available": self._available,
            "request_count": self._request_count,
            "avg_latency_ms": round(avg_ms, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
            "base_url": self.base_url,
        }


# Singleton instance
_client_instance: FoundationModelsClient | None = None


def get_foundation_client() -> FoundationModelsClient:
    """Get the global Foundation Models client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = FoundationModelsClient()
    return _client_instance
