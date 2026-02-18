#!/usr/bin/env python3
"""Comprehensive validation script for Jarvis local models.

Run this before submitting changes to ensure everything works:
    python scripts/validate_local_models.py

Or use the wrapper:
    ./scripts/validate_jarvis.py
"""

import asyncio
import json
import subprocess
import sys
import time


def run_cmd(cmd, timeout=30):
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"


def check_daemon():
    """Check if daemon is running."""
    print("Checking daemon...")
    code, out, _ = run_cmd("lsof -i :9847 -sTCP:LISTEN | head -2")
    if code == 0 and "9847" in out:
        print("  ✓ Daemon running on port 9847")
        return True
    else:
        print("  ✗ Daemon not running")
        return False


def check_websocket_response():
    """Verify WebSocket returns proper model status."""
    print("Checking WebSocket model status...")

    code, out, err = run_cmd(
        """
cd /Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac && 
.venv/bin/python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'action': 'get_model_status'}))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        print('OK' if 'foundation_available' in data else 'FAIL')
asyncio.run(test())
" 2>&1
""",
        timeout=10,
    )

    if "OK" in out:
        print("  ✓ WebSocket response valid")
        return True
    else:
        print(f"  ✗ WebSocket response invalid: {out[:200]}")
        return False


def check_afm():
    """Check AFM availability."""
    print("Checking Foundation Models...")

    code, out, _ = run_cmd(
        """
cd /Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac && 
.venv/bin/python -c "
from jarvis.afm_integration import is_afm_available
print('OK' if is_afm_available() else 'FAIL')
" 2>&1
""",
        timeout=10,
    )

    if "OK" in out:
        print("  ✓ Foundation Models available")
        return True
    else:
        print("  ✗ Foundation Models not available")
        return False


def check_lmstudio_manager():
    """Check LM Studio manager."""
    print("Checking LM Studio Manager...")

    code, out, _ = run_cmd(
        """
cd /Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac && 
.venv/bin/python -c "
import asyncio
from jarvis.lm_studio_manager import get_lm_studio_manager
async def test():
    lm = get_lm_studio_manager()
    print('OK' if hasattr(lm, 'is_running') else 'FAIL')
asyncio.run(test())
" 2>&1
""",
        timeout=10,
    )

    if "OK" in out:
        print("  ✓ LM Studio Manager module works")
        return True
    else:
        print("  ✗ LM Studio Manager module failed")
        return False


def check_python_lint():
    """Check Python files for syntax errors."""
    print("Checking Python lint...")

    files = [
        "src/jarvis/afm_integration.py",
        "src/jarvis/lm_studio_manager.py",
        "src/jarvis/local_model_manager.py",
        "src/jarvis/ws_server.py",
    ]

    all_ok = True
    for f in files:
        code, _, err = run_cmd(f"python3 -m py_compile {f}")
        if code == 0:
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f}: {err[:100]}")
            all_ok = False

    return all_ok


def check_swift_build():
    """Check Swift build."""
    print("Checking Swift build...")

    # Just check syntax, don't do full build (too slow)
    code, out, err = run_cmd(
        """
cd /Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac/JarvisApp &&
swift build --package-path . 2>&1 | tail -5
""",
        timeout=60,
    )

    if "error:" not in out.lower() and "error:" not in (err or "").lower():
        print("  ✓ Swift package resolves")
        return True
    else:
        print(f"  ✗ Swift build issue: {err[:100]}")
        return False


def main():
    print("=" * 50)
    print("JARVIS LOCAL MODELS VALIDATION")
    print("=" * 50)
    print()

    results = {}

    # Quick checks (no daemon needed)
    results["python_lint"] = check_python_lint()
    results["swift_build"] = check_swift_build()

    # Daemon-dependent checks
    daemon_running = check_daemon()
    if daemon_running:
        results["websocket"] = check_websocket_response()
        results["afm"] = check_afm()
        results["lmstudio"] = check_lmstudio_manager()
    else:
        print()
        print("Skipping daemon-dependent checks (daemon not running)")
        print("Start with: ./start-jarvis.sh")

    # Summary
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {name}")

    print()
    if passed == total:
        print(f"All {total} checks passed!")
        return 0
    else:
        print(f"{total - passed} check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
