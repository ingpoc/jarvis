#!/bin/bash
# Tailscale integration setup for Jarvis remote access

set -e

echo "🔧 Jarvis Tailscale Setup"
echo ""

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! command -v brew &> /dev/null; then
            echo "❌ Homebrew not found. Please install from https://brew.sh"
            exit 1
        fi
        brew install --cask tailscale
    else
        echo "❌ Please install Tailscale from https://tailscale.com"
        exit 1
    fi
fi

# Check if logged in
echo "📝 Checking Tailscale status..."
STATUS=$(tailscale status --json 2>/dev/null || echo "{}")

if echo "$STATUS" | grep -q '"BackendState":"Running"'; then
    echo "✅ Tailscale is running"
else
    echo "⚠️  Tailscale not logged in. Starting..."
    sudo tailscale up
fi

# Get Tailscale IP
TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
if [ -n "$TS_IP" ]; then
    echo "✅ Tailscale IP: $TS_IP"
else
    echo "❌ Could not get Tailscale IP"
    exit 1
fi

# Update .env with Tailscale configuration
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
    echo "📝 Updating .env configuration..."

    # Enable remote server
    sed -i '' 's/JARVIS_REMOTE_ENABLED=.*/JARVIS_REMOTE_ENABLED=true/' "$ENV_FILE" 2>/dev/null || \
        echo "JARVIS_REMOTE_ENABLED=true" >> "$ENV_FILE"

    # Enable Tailscale
    sed -i '' 's/TAILSCALE_ENABLED=.*/TAILSCALE_ENABLED=true/' "$ENV_FILE" 2>/dev/null || \
        echo "TAILSCALE_ENABLED=true" >> "$ENV_FILE"

    echo "✅ Configuration updated"
else
    echo "⚠️  .env file not found. Copy .env.example to .env first."
fi

# Start funnel on port 9848
echo "🌐 Starting Tailscale funnel on port 9848..."
tailscale funnel 9848 --bg --check=false

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start Jarvis daemon with remote enabled:"
echo "   export JARVIS_REMOTE_ENABLED=true"
echo "   python -m jarvis.daemon"
echo ""
echo "2. On client devices, install Tailscale and log in to same tailnet"
echo "3. Connect using WSS URL: wss://$TS_IP:9848"
echo ""
echo "To stop funnel later:"
echo "   tailscale funnel --reset"
