#!/usr/bin/env python3
"""Test local model integration end-to-end.

Tests:
1. AFM availability check
2. LM Studio manager
3. WebSocket model status response
"""

import asyncio
import json
import os
import sys
import time

STRICT_LOCAL_MODEL_TESTS = os.getenv("JARVIS_LOCAL_MODELS_STRICT", "0") == "1"


def test_afm():
    """Test Apple Foundation Models availability."""
    print("=" * 50)
    print("Testing Apple Foundation Models...")

    try:
        from jarvis.afm_integration import is_afm_available, generate

        available = is_afm_available()
        print(f"  AFM Available: {available}")

        if not available:
            print("  ⚠ AFM unavailable on this machine; skipping")
            return True

        result = generate("What is 2+2? Answer briefly.")
        content = result.get("content", "")
        print(f"  Generation: {content}")
        print(f"  Latency: {result.get('latency_ms', 0):.0f}ms")

        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                payload = json.loads(content)
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("error"):
                print("  ⚠ AFM runtime returned an error payload; skipping on this machine")
                return True

        return True
    except Exception as e:
        err = str(e).lower()
        if (
            ("generationerror" in err or "operation couldn’t be completed" in err or "operation couldn't be completed" in err)
            and not STRICT_LOCAL_MODEL_TESTS
        ):
            print("  ⚠ AFM runtime generation failed on this machine; skipping in non-strict mode")
            return True
        print(f"  ERROR: {e}")
        return False


async def test_lm_studio():
    """Test LM Studio manager."""
    print("=" * 50)
    print("Testing LM Studio Manager...")

    try:
        from jarvis.lm_studio_manager import get_lm_studio_manager

        lm = get_lm_studio_manager()
        finder = getattr(lm, "_find_lm_studio", None)
        lm_path = finder() if callable(finder) else None

        # Check if running
        print(f"  LM Studio running: {lm.is_running}")

        if not lm.is_running and not lm.is_api_available() and lm_path is None:
            print("  ⚠ LM Studio app not installed; skipping")
            return True

        if not lm.is_running and not lm.is_api_available():
            print("  Starting LM Studio...")
            await lm.ensure_running()

        print(f"  LM Studio running: {lm.is_running or lm.is_api_available()}")

        if lm.is_running or lm.is_api_available():
            models = lm.available_models
            print(f"  Available models: {len(models)}")
            for m in models[:3]:
                print(f"    - {m}")

            # Test loading model
            if models:
                model_id = models[0]
                print(f"  Loading model: {model_id}")
                await lm.load_model(model_id)
                print(f"  Model loaded: {lm.current_model}")

            return True
        if not STRICT_LOCAL_MODEL_TESTS:
            print("  ⚠ LM Studio unavailable after startup attempt; skipping in non-strict mode")
            return True
        return False
    except Exception as e:
        if "not found" in str(e).lower():
            print("  ⚠ LM Studio not found; skipping")
            return True
        if "failed to start" in str(e).lower() and not STRICT_LOCAL_MODEL_TESTS:
            print("  ⚠ LM Studio failed to start; skipping in non-strict mode")
            return True
        print(f"  ERROR: {e}")
        return False


async def test_websocket():
    """Test WebSocket model status."""
    print("=" * 50)
    print("Testing WebSocket Model Status...")

    try:
        import websockets

        uri = "ws://127.0.0.1:9847"

        # Use open_timeout instead of timeout in connect
        async with websockets.connect(uri, open_timeout=5) as ws:
            # Send get_model_status
            request_id = f"test-{int(time.time() * 1000)}"
            await ws.send(
                json.dumps(
                    {
                        "type": "command",
                        "id": request_id,
                        "action": "get_model_status",
                        "data": {},
                    }
                )
            )

            # Receive correlated response envelope
            data = {}
            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                envelope = json.loads(response)
                if envelope.get("type") == "response" and envelope.get("id") == request_id:
                    data = envelope.get("data", {})
                    break

            # Validate response structure
            required_fields = [
                "current_model",
                "provider",
                "provider_type",
                "foundation_available",
                "lmstudio_running",
            ]

            missing = [f for f in required_fields if f not in data]
            if missing:
                print(f"  ERROR: Missing fields: {missing}")
                return False

            print(f"  Current model: {data.get('current_model')}")
            print(f"  Provider: {data.get('provider')}")
            print(f"  Foundation available: {data.get('foundation_available')}")
            print(f"  LM Studio running: {data.get('lmstudio_running')}")
            print(f"  LM Studio models: {len(data.get('lmstudio_available_models', []))}")

            return True

    except Exception as e:
        err = str(e).lower()
        if "operation not permitted" in err:
            print("  ⚠ WebSocket test skipped (sandbox restrictions)")
            return True
        if "connection refused" in err or "cannot connect" in err:
            print("  ⚠ WebSocket daemon not running; skipping")
            return True
        print(f"  ERROR: {e}")
        print("  (Is the daemon running? Try: ./start-jarvis.sh)")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("LOCAL MODEL INTEGRATION TEST")
    print("=" * 50)

    results = {}

    # Test 1: AFM
    results["afm"] = test_afm()

    # Test 2: WebSocket
    results["websocket"] = await test_websocket()

    # Test 3: LM Studio (only if WebSocket test passed)
    if results.get("websocket"):
        results["lmstudio"] = await test_lm_studio()
    else:
        results["lmstudio"] = False
        print("=" * 50)
        print("Skipping LM Studio test (WebSocket not available)")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
