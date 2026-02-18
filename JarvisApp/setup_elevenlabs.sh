#!/bin/bash

# Jarvis ElevenLabs Voice Setup Script

echo "=== Jarvis Voice ElevenLabs Setup ==="
echo ""

# Check for API key
if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "⚠️  ELEVENLABS_API_KEY not set"
    echo ""
    echo "Please set your API key:"
    echo "  export ELEVENLABS_API_KEY='sk-your-key-here'"
    echo ""
    echo "Get your key at: https://elevenlabs.io/app/developers/api-keys"
    exit 1
fi

echo "✓ API key found: ${ELEVENLABS_API_KEY:0:10}..."

# Try to use CLI
echo ""
echo "Attempting to push tools to ElevenLabs..."

# Check if logged in
if elevenlabs auth whoami --no-ui 2>&1 | grep -q "Not logged in"; then
    echo "⚠️  Not logged in to ElevenLabs"
    echo ""
    echo "Please login first:"
    echo "  elevenlabs auth login"
    echo ""
    echo "Or initialize the project:"
    echo "  elevenlabs agents init"
    exit 1
fi

# Push tools
echo ""
echo "Pushing webhook tools..."
elevenlabs tools push --no-ui

echo ""
echo "=== Setup Complete ==="
