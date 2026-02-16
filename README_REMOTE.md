# Jarvis Remote Access

Enable remote control and monitoring of Jarvis from anywhere using Tailscale VPN.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Remote (You)                            │
│  ┌──────────────┐              ┌──────────────┐             │
│  │  Mac GUI     │              │  iPhone App  │             │
│  │  (SwiftUI)   │              │  (SwiftUI)   │             │
│  └──────┬───────┘              └──────┬───────┘             │
│         │                             │                      │
│         └──────────┬──────────────────┘                      │
│                    │                                         │
│         ┌──────────▼───────────┐                            │
│         │   Tailscale VPN      │ (encrypted, mesh)          │
│         └──────────┬───────────┘                            │
└────────────────────┼─────────────────────────────────────────┘
                     │ Internet
┌────────────────────┼─────────────────────────────────────────┐
│              Mac Mini (Home)                                 │
│                    │                                         │
│         ┌──────────▼───────────┐                            │
│         │  Jarvis Server       │                            │
│         │  - WSS (0.0.0.0)     │  Port 9848                 │
│         │  - JWT Auth          │  Port 9849 (REST)          │
│         │  - Tailscale Funnel  │                            │
│         └──────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Server Setup (Mac Mini)

```bash
# Install Tailscale
brew install --cask tailscale
sudo tailscale up

# Run the setup script
cd jarvis-mac
./scripts/tailscale-setup.sh
```

### 2. Enable Remote Server

```bash
# Copy and configure environment
cp .env.example .env
nano .env  # Set JARVIS_JWT_SECRET

# Enable remote server
export JARVIS_REMOTE_ENABLED=true
python -m jarvis.daemon
```

### 3. Client Setup

**Mac GUI:**

```bash
cd jarvis-mac/JarvisApp
swift run
# Use Setup Wizard to pair with server
```

**iPhone App:**

1. Install Tailscale from App Store
2. Log in to same tailnet
3. Open Jarvis app and complete onboarding

## Configuration

### .env Settings

```bash
# Remote Server
JARVIS_REMOTE_ENABLED=true
JARVIS_REMOTE_PORT=9848
JARVIS_REMOTE_BIND=0.0.0.0

# JWT Auth
JARVIS_JWT_SECRET=<generate-with: python -c "import secrets; print(secrets.token_urlsafe(32))">
JARVIS_JWT_EXPIRY=86400  # 24 hours

# Tailscale
TAILSCALE_ENABLED=true
TAILSCALE_FUNNEL_PORT=9848

# Device Limits
MAX_DEVICES=10
DEVICE_EXPIRY_DAYS=365
```

## Device Pairing Flow

```
1. Client requests pairing
   POST /api/pair {device_name}

2. Server returns QR token
   {token, qr_data, expires_at}

3. Client shows QR code

4. Admin approves on server
   POST /api/confirm {token}

5. Client receives credentials
   {api_key, jwt, device_id, expires_at}

6. Client connects with JWT
   WSS + Authorization: Bearer <jwt>
```

## Security

- **Transport**: WSS (TLS 1.3) required for all connections
- **Auth**: JWT with HS256, 24h expiry
- **Device limits**: Max 10 registered devices
- **Rate limiting**: 10 commands/minute per device
- **Tunnels**: Encrypted via Tailscale (no public exposure)

## Troubleshooting

### Cannot connect remotely

```bash
# Check Tailscale status
tailscale status

# Verify funnel is running
tailscale funnel status

# Check if port is listening
netstat -an | grep 9848

# Test connection
curl -wss://<tailscale-ip>:9848/api/health
```

### Authentication errors

```bash
# Verify JWT secret matches
echo $JARVIS_JWT_SECRET

# Check device registration
sqlite3 ~/.jarvis/devices.db "SELECT * FROM devices;"
```

### Tailscale funnel issues

```bash
# Reset and restart funnel
tailscale funnel --reset
tailscale funnel 9848 --bg

# Check logs
log stream --predicate 'process == "Tailscale"'
```

## API Endpoints

### Pairing

- `POST /api/pair` - Initiate pairing
- `POST /api/confirm` - Confirm pairing

### Status

- `GET /api/health` - Health check
- `GET /api/status` - Server status

### Device Management (requires auth)

- `GET /api/devices` - List devices
- `DELETE /api/devices/{id}` - Revoke device

## WebSocket Commands

### Client → Server

```json
{"type": "command", "action": "get_status"}
{"type": "command", "action": "get_timeline", "data": {"limit": 50}}
{"type": "command", "action": "approve", "data": {"task_id": "..."}}
{"type": "command", "action": "deny", "data": {"task_id": "..."}}
{"type": "command", "action": "run_task", "data": {"description": "..."}}
{"type": "command", "action": "send_voice", "data": {"text": "..."}}
```

### Server → Client (Events)

```json
{"type": "event", "data": {...event...}}
{"type": "auth_success", "data": {"device_id": "..."}}
{"type": "error", "data": {"message": "..."}}
```
