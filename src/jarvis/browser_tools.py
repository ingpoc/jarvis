"""Headless browser testing inside Apple Containers via Playwright.

Since GLM 4.7 doesn't support Claude-in-Chrome, Jarvis uses headless
Playwright running inside Apple Containers for browser testing:
- Install Playwright + browsers inside the container
- Run tests headlessly (no GUI needed)
- Capture screenshots, console logs, network errors
- Supports both Playwright Test runner and raw API

Container workflow:
1. container_run with node:22 image
2. container_exec: npx playwright install --with-deps chromium
3. container_exec: run tests or navigate + screenshot
"""

import asyncio
import json
import os
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool


# --- Setup Tools ---


@tool(
    "browser_setup",
    "Install Playwright + Chromium inside an Apple Container. Run this once per container before any browser tests.",
    {"container_id": str, "browsers": str},
)
async def browser_setup(args: dict) -> dict:
    """Install Playwright in a running container."""
    container_id = args["container_id"]
    browsers = args.get("browsers", "chromium")

    commands = [
        "npm init -y 2>/dev/null",
        "npm install playwright @playwright/test",
        f"npx playwright install --with-deps {browsers}",
    ]

    results = []
    for cmd in commands:
        proc = await asyncio.create_subprocess_exec(
            "container", "exec", container_id, "sh", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        results.append({
            "command": cmd,
            "exit_code": proc.returncode,
            "output": stdout.decode()[-500:],
            "error": stderr.decode()[-500:] if proc.returncode != 0 else "",
        })
        if proc.returncode != 0:
            return {"content": [{"type": "text", "text": json.dumps({
                "status": "failed",
                "step": cmd,
                "error": stderr.decode()[-500:],
            }, indent=2)}]}

    return {"content": [{"type": "text", "text": json.dumps({
        "status": "ready",
        "browsers": browsers,
        "container": container_id,
    }, indent=2)}]}


# --- Testing Tools ---


@tool(
    "browser_test_run",
    "Run Playwright tests inside an Apple Container. Provide the test file path relative to the container workspace.",
    {"container_id": str, "test_path": str, "headed": bool, "workers": int},
)
async def browser_test_run(args: dict) -> dict:
    """Run Playwright test suite."""
    container_id = args["container_id"]
    test_path = args.get("test_path", "tests/")
    workers = args.get("workers", 1)

    cmd = (
        f"cd /workspace && npx playwright test {test_path} "
        f"--workers={workers} --reporter=json 2>&1 | tail -100"
    )

    proc = await asyncio.create_subprocess_exec(
        "container", "exec", container_id, "sh", "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    output = stdout.decode()[-5000:]

    # Try to parse JSON test results
    try:
        start = output.find("{")
        if start >= 0:
            results = json.loads(output[start:])
            summary = {
                "status": "passed" if results.get("stats", {}).get("unexpected", 0) == 0 else "failed",
                "total": results.get("stats", {}).get("expected", 0),
                "passed": results.get("stats", {}).get("expected", 0) - results.get("stats", {}).get("unexpected", 0),
                "failed": results.get("stats", {}).get("unexpected", 0),
                "duration_ms": results.get("stats", {}).get("duration", 0),
            }
            return {"content": [{"type": "text", "text": json.dumps(summary, indent=2)}]}
    except (json.JSONDecodeError, KeyError):
        pass

    return {"content": [{"type": "text", "text": output}]}


@tool(
    "browser_navigate",
    "Navigate to a URL and capture screenshot + console logs + network errors. Uses headless Chromium inside an Apple Container.",
    {"container_id": str, "url": str, "screenshot_path": str, "wait_for": str},
)
async def browser_navigate(args: dict) -> dict:
    """Navigate to URL and capture page state."""
    container_id = args["container_id"]
    url = args["url"]
    screenshot_path = args.get("screenshot_path", "/workspace/screenshot.png")
    wait_for = args.get("wait_for", "networkidle")

    # Inline Playwright script for navigation + capture
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const context = await browser.newContext({{ viewport: {{ width: 1280, height: 720 }} }});
    const page = await context.newPage();

    const consoleLogs = [];
    const networkErrors = [];

    page.on('console', msg => consoleLogs.push({{
        type: msg.type(),
        text: msg.text().substring(0, 200)
    }}));

    page.on('requestfailed', req => networkErrors.push({{
        url: req.url().substring(0, 200),
        error: req.failure()?.errorText || 'unknown'
    }}));

    try {{
        await page.goto('{url}', {{ waitUntil: '{wait_for}', timeout: 30000 }});
        await page.screenshot({{ path: '{screenshot_path}', fullPage: false }});

        const title = await page.title();
        const bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 500) || '');

        console.log(JSON.stringify({{
            status: 'ok',
            url: page.url(),
            title,
            bodyPreview: bodyText.substring(0, 300),
            consoleLogs: consoleLogs.slice(-10),
            networkErrors: networkErrors.slice(-5),
            screenshot: '{screenshot_path}'
        }}));
    }} catch (e) {{
        console.log(JSON.stringify({{
            status: 'error',
            error: e.message,
            consoleLogs: consoleLogs.slice(-5),
            networkErrors: networkErrors.slice(-5)
        }}));
    }}

    await browser.close();
}})();
"""

    # Write script to container and execute
    proc = await asyncio.create_subprocess_exec(
        "container", "exec", container_id, "sh", "-c",
        f"cat > /tmp/navigate.js << 'SCRIPT_EOF'\n{script}\nSCRIPT_EOF\nnode /tmp/navigate.js",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    output = stdout.decode().strip()

    try:
        result = json.loads(output)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except json.JSONDecodeError:
        return {"content": [{"type": "text", "text": f"Raw output: {output[-2000:]}\nStderr: {stderr.decode()[-1000:]}"}]}


@tool(
    "browser_interact",
    "Interact with a page: click, fill, select, check elements. Runs headless Playwright script inside an Apple Container.",
    {"container_id": str, "url": str, "actions": list, "screenshot_after": bool},
)
async def browser_interact(args: dict) -> dict:
    """Run a sequence of browser interactions.

    Actions format: [{"action": "click|fill|select|wait", "selector": "css", "value": "text"}]
    """
    container_id = args["container_id"]
    url = args["url"]
    actions = args.get("actions", [])
    screenshot_after = args.get("screenshot_after", True)

    # Build action code
    action_lines = []
    for i, act in enumerate(actions[:20]):  # Cap at 20 actions
        action_type = act.get("action", "click")
        selector = act.get("selector", "").replace("'", "\\'")
        value = act.get("value", "").replace("'", "\\'")

        if action_type == "click":
            action_lines.append(f"    await page.click('{selector}');")
        elif action_type == "fill":
            action_lines.append(f"    await page.fill('{selector}', '{value}');")
        elif action_type == "select":
            action_lines.append(f"    await page.selectOption('{selector}', '{value}');")
        elif action_type == "wait":
            action_lines.append(f"    await page.waitForSelector('{selector}', {{ timeout: 10000 }});")
        elif action_type == "press":
            action_lines.append(f"    await page.press('{selector}', '{value}');")

        action_lines.append(f"    results.push({{ step: {i}, action: '{action_type}', selector: '{selector}', status: 'ok' }});")

    actions_code = "\n".join(action_lines)
    screenshot_code = ""
    if screenshot_after:
        screenshot_code = "    await page.screenshot({ path: '/workspace/interaction.png' });"

    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage({{ viewport: {{ width: 1280, height: 720 }} }});
    const results = [];

    try {{
        await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
{actions_code}
{screenshot_code}
        console.log(JSON.stringify({{ status: 'ok', results, url: page.url(), title: await page.title() }}));
    }} catch (e) {{
        console.log(JSON.stringify({{ status: 'error', error: e.message, results }}));
    }}

    await browser.close();
}})();
"""

    proc = await asyncio.create_subprocess_exec(
        "container", "exec", container_id, "sh", "-c",
        f"cat > /tmp/interact.js << 'SCRIPT_EOF'\n{script}\nSCRIPT_EOF\nnode /tmp/interact.js",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    output = stdout.decode().strip()

    try:
        result = json.loads(output)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except json.JSONDecodeError:
        return {"content": [{"type": "text", "text": f"Output: {output[-2000:]}"}]}


@tool(
    "browser_api_test",
    "Test API endpoints from inside an Apple Container. Supports GET/POST/PUT/DELETE with headers and body.",
    {"container_id": str, "method": str, "url": str, "headers": dict, "body": str, "expected_status": int},
)
async def browser_api_test(args: dict) -> dict:
    """Test an API endpoint from inside a container."""
    container_id = args["container_id"]
    method = args.get("method", "GET").upper()
    url = args["url"]
    headers = args.get("headers", {})
    body = args.get("body", "")
    expected_status = args.get("expected_status", 200)

    # Build curl command
    curl_parts = ["curl", "-s", "-w", "'\\n%{http_code}'", "-X", method]
    for k, v in headers.items():
        curl_parts.extend(["-H", f"'{k}: {v}'"])
    if body and method in ("POST", "PUT", "PATCH"):
        curl_parts.extend(["-d", f"'{body}'"])
    curl_parts.append(f"'{url}'")

    cmd = " ".join(curl_parts)

    proc = await asyncio.create_subprocess_exec(
        "container", "exec", container_id, "sh", "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    output = stdout.decode().strip()

    # Parse response body and status code
    lines = output.rsplit("\n", 1)
    response_body = lines[0] if len(lines) > 1 else output
    status_code = int(lines[-1]) if len(lines) > 1 and lines[-1].isdigit() else 0

    # Try to parse JSON body
    parsed_body = response_body[:3000]
    try:
        parsed_body = json.loads(response_body)
    except json.JSONDecodeError:
        pass

    result = {
        "status_code": status_code,
        "expected": expected_status,
        "passed": status_code == expected_status,
        "body": parsed_body,
    }

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "browser_wallet_test",
    "Test a Solana dApp with a mock wallet (Solflare/Phantom). Injects a mock wallet provider so the dApp thinks a wallet is connected. Useful for testing wallet-connected flows without a real browser extension.",
    {"container_id": str, "url": str, "wallet_address": str, "actions": list, "network": str},
)
async def browser_wallet_test(args: dict) -> dict:
    """Test a Solana dApp with mock wallet injection.

    Injects window.solflare / window.phantom with a mock provider that
    auto-approves connections and returns the given wallet address.
    Then executes UI actions and captures results.
    """
    container_id = args["container_id"]
    url = args["url"]
    wallet_address = args.get("wallet_address", "11111111111111111111111111111111")
    actions = args.get("actions", [])
    network = args.get("network", "devnet")

    # Build action code
    action_lines = []
    for i, act in enumerate(actions[:15]):
        action_type = act.get("action", "click")
        selector = act.get("selector", "").replace("'", "\\'")
        value = act.get("value", "").replace("'", "\\'")

        if action_type == "click":
            action_lines.append(f"        await page.click('{selector}');")
        elif action_type == "fill":
            action_lines.append(f"        await page.fill('{selector}', '{value}');")
        elif action_type == "wait":
            action_lines.append(f"        await page.waitForSelector('{selector}', {{ timeout: 10000 }});")

        action_lines.append(f"        results.push({{ step: {i}, action: '{action_type}', status: 'ok' }});")

    actions_code = "\n".join(action_lines) if action_lines else "        // No actions"

    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const context = await browser.newContext({{ viewport: {{ width: 1280, height: 720 }} }});
    const page = await context.newPage();
    const results = [];
    const consoleLogs = [];

    page.on('console', msg => consoleLogs.push({{ type: msg.type(), text: msg.text().substring(0, 200) }}));

    // Inject mock Solflare/Phantom wallet BEFORE page loads
    await page.addInitScript(() => {{
        const mockPublicKey = {{
            toBase58: () => '{wallet_address}',
            toString: () => '{wallet_address}',
            toBytes: () => new Uint8Array(32),
        }};

        const mockWallet = {{
            isConnected: true,
            publicKey: mockPublicKey,
            network: '{network}',
            connect: async () => ({{ publicKey: mockPublicKey }}),
            disconnect: async () => {{}},
            signTransaction: async (tx) => tx,
            signAllTransactions: async (txs) => txs,
            signMessage: async (msg) => new Uint8Array(64),
            on: (event, cb) => {{}},
            off: (event, cb) => {{}},
            emit: (event) => {{}},
            isSolflare: true,
            isPhantom: true,
        }};

        window.solflare = mockWallet;
        window.phantom = {{ solana: mockWallet }};
        window.solana = mockWallet;
    }});

    try {{
        await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
        await page.waitForTimeout(2000);  // Let dApp detect wallet

        // Check if dApp detected the wallet
        const walletDetected = await page.evaluate(() => {{
            return {{
                solflare: !!window.solflare,
                phantom: !!window.phantom,
                solana: !!window.solana,
                connected: window.solflare?.isConnected || false,
            }};
        }});
        results.push({{ step: 'wallet_inject', ...walletDetected }});

{actions_code}

        await page.screenshot({{ path: '/workspace/wallet-test.png' }});

        console.log(JSON.stringify({{
            status: 'ok',
            wallet: '{wallet_address}',
            network: '{network}',
            results,
            consoleLogs: consoleLogs.slice(-10),
            screenshot: '/workspace/wallet-test.png'
        }}));
    }} catch (e) {{
        console.log(JSON.stringify({{
            status: 'error',
            error: e.message,
            results,
            consoleLogs: consoleLogs.slice(-5)
        }}));
    }}

    await browser.close();
}})();
"""

    proc = await asyncio.create_subprocess_exec(
        "container", "exec", container_id, "sh", "-c",
        f"cat > /tmp/wallet_test.js << 'SCRIPT_EOF'\n{script}\nSCRIPT_EOF\nnode /tmp/wallet_test.js",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    output = stdout.decode().strip()

    try:
        result = json.loads(output)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except json.JSONDecodeError:
        return {"content": [{"type": "text", "text": f"Output: {output[-2000:]}\nStderr: {stderr.decode()[-500:]}"}]}


# --- Server factory ---


ALL_BROWSER_TOOLS = [browser_setup, browser_test_run, browser_navigate, browser_interact, browser_api_test, browser_wallet_test]


def create_browser_mcp_server():
    """Create the headless browser testing MCP server."""
    return create_sdk_mcp_server(
        name="jarvis-browser",
        version="0.1.0",
        tools=ALL_BROWSER_TOOLS,
    )
