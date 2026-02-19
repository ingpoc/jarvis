import asyncio
from unittest.mock import patch

from jarvis.local_model_manager import LocalModelManager


def test_switch_to_foundation_succeeds_when_afm_available() -> None:
    manager = LocalModelManager()

    with patch("jarvis.local_model_manager.is_afm_available", return_value=True):
        result = asyncio.run(manager.switch_model("foundation-models"))

    assert result["success"] is True
    assert result["provider"] == "foundation"
    assert manager.provider is not None
    assert manager.current_model == "foundation-models"


def test_switch_to_remote_model_is_not_local_runtime() -> None:
    manager = LocalModelManager()

    result = asyncio.run(manager.switch_model("claude-sonnet-4-5-20250929"))

    assert "error" in result
    assert "not a local runtime" in result["error"]
    assert manager.provider is None
    assert manager.current_model is None


def test_generate_without_local_provider_raises() -> None:
    manager = LocalModelManager()

    with patch("jarvis.local_model_manager.is_afm_available", return_value=True):
        asyncio.run(manager.switch_model("foundation-models"))

    asyncio.run(manager.shutdown())

    try:
        asyncio.run(manager.generate("hello"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "No local model provider active" in str(exc)
