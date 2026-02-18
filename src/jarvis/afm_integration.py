"""Direct Apple Foundation Models integration.

Uses apple-foundation-models Python package directly for lowest latency.
No HTTP bridge needed - runs in-process with the daemon.

This is the fastest option (<1s latency) when Apple Intelligence is available.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_afm_session: Any = None
_afm_available: bool | None = None


def is_afm_available() -> bool:
    """Check if Apple Foundation Models are available."""
    global _afm_available
    if _afm_available is not None:
        return _afm_available

    try:
        from applefoundationmodels import apple_intelligence_available

        _afm_available = apple_intelligence_available()
    except ImportError:
        _afm_available = False
        logger.debug("apple-foundation-models not installed")
    except Exception as e:
        _afm_available = False
        logger.debug(f"Foundation Models unavailable: {e}")

    return _afm_available


def get_session():
    """Get or create Foundation Models session."""
    global _afm_session

    if _afm_session is None:
        try:
            from applefoundationmodels import Session

            _afm_session = Session()
            logger.info("Foundation Models session created")
        except Exception as e:
            logger.error(f"Failed to create AFM session: {e}")
            raise

    return _afm_session


def generate(prompt: str, max_tokens: int = 1024) -> dict[str, Any]:
    """Generate response from Foundation Models."""
    if not is_afm_available():
        raise RuntimeError("Foundation Models not available")

    start = time.time()
    session = get_session()

    try:
        result = session.generate(prompt)
        elapsed_ms = (time.time() - start) * 1000

        return {
            "content": result.content,
            "latency_ms": elapsed_ms,
            "model": "apple-foundation-models",
        }
    except Exception as e:
        logger.error(f"AFM generation failed: {e}")
        raise


def close_session():
    """Close Foundation Models session."""
    global _afm_session
    if _afm_session:
        try:
            _afm_session.close()
        except Exception:
            pass
        _afm_session = None
        logger.info("Foundation Models session closed")


def get_stats() -> dict[str, Any]:
    """Get Foundation Models stats."""
    if not is_afm_available():
        return {"available": False}

    session = get_session()
    return {
        "available": True,
        "version": session.get_version() if session else None,
        "ready": session.is_ready() if session else False,
    }
