# Jarvis

Autonomous Mac-native development partner powered by Claude Agent SDK and Apple Containers.

## Overview

Jarvis is an AI-powered development assistant that runs locally on your Mac. It autonomously handles coding tasks, runs tests, manages Git operations, and integrates with your existing development workflow.

```
┌─────────────────────────────────────────────────────────────┐
│                        Jarvis                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │  Mac GUI     │    │  Menu Bar    │    │  Slack Bot   │ │
│  │  (SwiftUI)   │◄──►│  (SwiftUI)   │    │  (Optional)  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │        │
│         └────────────────────┼────────────────────┘        │
│                              │                             │
│         ┌────────────────────▼────────────────────┐        │
│         │         Jarvis Daemon (Python)          │        │
│         │  - WebSocket Server (ws://127.0.0.1:9847)│       │
│         │  - Remote WSS Server (wss://0.0.0.0:9848)│       │
│         │  - Event Collector + Orchestrator        │        │
│         └────────────────────┬────────────────────┘        │
│                              │                             │
│         ┌────────────────────▼────────────────────┐        │
│         │        Claude Agent SDK                  │        │
│         └────────────────────┬────────────────────┘        │
│                              │                             │
│         ┌────────────────────▼────────────────────┐        │
│         │  Apple Containers │ File System │ Git    │        │
│         └──────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Autonomous Task Execution**: Describe what you want, Jarvis figures out how to do it
- **Smart Code Generation**: Uses Claude Agent SDK for intelligent code synthesis
- **Automated Testing**: Runs tests and reports results automatically
- **Git Integration**: Handles commits, branches, and status checks
- **Approval Workflow**: Requires approval for destructive operations
- **Real-time Updates**: Menu bar app shows current status
- **Event Timeline**: Complete history of all actions
- **Slack Integration**: (Optional) Get notifications and send commands via Slack
- **Voice Control**: (Optional) Use ElevenLabs for voice feedback
- **Remote Access**: Control Jarvis from anywhere via Tailscale VPN

## Installation

### Prerequisites

- macOS 14+ (Sonoma or later)
- Python 3.11+
- Swift 5.10+ (for GUI apps)

### Install Python Package

```bash
cd jarvis-mac
pip install -e .
```

### Install Optional Dependencies

```bash
# Slack integration
pip install -e ".[slack]"

# Voice feedback
pip install -e ".[voice]"

# Everything
pip install -e ".[all]"
```

### Install Mac GUI

```bash
cd JarvisApp
swift run
```

The app will appear in your menu bar.

## Quick Start

### 1. Start the Daemon

```bash
cd jarvis-mac
python -m jarvis.daemon
```

The daemon starts:

- Local WebSocket server on `ws://127.0.0.1:9847`
- Event collector for real-time updates
- Optional Slack bot and voice client

### 2. Use the CLI

```bash
# Run a task
jarvis run "Add user authentication to the app"

# Check status
jarvis status

# View timeline
jarvis timeline

# Interactive mode
jarvis
```

### 3. Use the Mac GUI

Open the Jarvis app from your Applications folder or run:

```bash
cd JarvisApp
swift run
```

Click the menu bar icon to:

- View current status
- See recent events
- Approve/deny pending actions
- Send commands

## Configuration

Create a `.env` file in the jarvis-mac directory:

```bash
cp .env.example .env
```

Key configuration options:

```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Slack (optional)
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# ElevenLabs Voice (optional)
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...

# Remote Access (see README_REMOTE.md)
JARVIS_REMOTE_ENABLED=false
JARVIS_JWT_SECRET=...
```

## Architecture

### Core Components

```
jarvis-mac/
├── src/jarvis/
│   ├── daemon.py          # Main daemon entry point
│   ├── orchestrator.py    # Task orchestration
│   ├── ws_server.py       # Local WebSocket server
│   ├── remote_server.py   # Remote WSS server with auth
│   ├── auth.py            # JWT authentication
│   ├── events.py          # Event collector
│   ├── memory.py          # SQLite event storage
│   ├── cli.py             # Command-line interface
│   └── ...
├── JarvisApp/             # Mac GUI (SwiftUI)
│   └── Sources/JarvisApp/
│       ├── MainWindowApp.swift
│       ├── Views/          # Dashboard, Timeline, etc.
│       └── Models/
├── JarvisClient/          # Shared Swift Package
│   └── Sources/JarvisClient/
│       ├── Networking/     # WebSocket, REST, Auth
│       ├── Models/         # Shared data models
│       └── Utilities/      # Tailscale, events
├── JarvisiOS/             # iPhone App (SwiftUI)
└── scripts/               # Setup and utility scripts
```

### Data Flow

```
User Command
    │
    ▼
┌─────────────────┐
│   CLI / GUI     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │◄──────┐
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│ Claude Agent    │       │
│     SDK         │       │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│   Tool Use      │       │
│  (Containers,   │       │
│   Git, etc.)    │       │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│  Event Collector│───────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GUI / Slack    │
└─────────────────┘
```

## Available Commands

### CLI Commands

```bash
jarvis run "describe your task here"
jarvis status
jarvis timeline [--limit 50]
jarvis approve <task_id>
jarvis deny <task_id>
```

### WebSocket Commands

Send JSON via WebSocket to `ws://127.0.0.1:9847`:

```json
{"type": "command", "action": "get_status"}
{"type": "command", "action": "get_timeline", "data": {"limit": 50}}
{"type": "command", "action": "approve", "data": {"task_id": "..."}}
{"type": "command", "action": "deny", "data": {"task_id": "..."}}
{"type": "command", "action": "run_task", "data": {"description": "..."}}
```

## Event Types

| Type | Description |
|------|-------------|
| `tool_use` | A tool was executed |
| `state_change` | Agent state changed |
| `feature_start` | Feature development started |
| `feature_complete` | Feature completed |
| `error` | An error occurred |
| `approval_needed` | Waiting for user approval |
| `cost` | API cost update |
| `trust_change` | Trust level changed |
| `task_start` | Task started |
| `task_complete` | Task completed |

## Remote Access

Jarvis supports remote control via Tailscale VPN. See [README_REMOTE.md](README_REMOTE.md) for complete setup instructions.

### Quick Remote Setup

```bash
# Install Tailscale
brew install --cask tailscale
sudo tailscale up

# Run setup script
./scripts/tailscale-setup.sh

# Enable remote server
export JARVIS_REMOTE_ENABLED=true
python -m jarvis.daemon
```

## Development

### Running Tests

```bash
cd jarvis-mac
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy src/jarvis
```

### Building GUI Apps

```bash
# Mac GUI
cd JarvisApp
swift build

# iOS App
# Open JarvisiOS/ in Xcode and build
```

## Troubleshooting

### Daemon won't start

```bash
# Check for port conflicts
lsof -i :9847
lsof -i :9848

# Check logs
tail -f ~/.jarvis/jarvis.log
```

### GUI can't connect

```bash
# Verify WebSocket is running
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:9847/
```

### Remote access issues

See [README_REMOTE.md](README_REMOTE.md) troubleshooting section.

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- GitHub Issues: [github.com/yourusername/jarvis-mac/issues]
- Documentation: [docs/](docs/)
- Remote Access: [README_REMOTE.md](README_REMOTE.md)
