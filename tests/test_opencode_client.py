from jarvis.opencode_client import OpenCodeClient


def test_normalize_model_variants() -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    assert client._normalize_model("opencode/default") is None
    assert client._normalize_model("opencode:coder") == {
        "providerID": "opencode",
        "modelID": "coder",
    }
    assert client._normalize_model("opencode/minimax-m2.5-free") == {
        "providerID": "opencode",
        "modelID": "minimax-m2.5-free",
    }
    assert client._normalize_model("opencode/zen/minimax/m2.5-free") == {
        "providerID": "zen",
        "modelID": "minimax/m2.5-free",
    }
    assert client._normalize_model("opencode") is None
    assert client._normalize_model("opencode-default") is None
    assert client._normalize_model("openai/gpt-5.2") == {
        "providerID": "openai",
        "modelID": "gpt-5.2",
    }


def test_extract_text_prefers_last_text_part() -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    payload = {
        "parts": [
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "first"},
            {"type": "tool", "name": "bash"},
            {"type": "text", "text": "final answer"},
        ]
    }
    assert client._extract_text_from_parts(payload) == "final answer"
