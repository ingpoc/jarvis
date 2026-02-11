#!/bin/bash
# Jarvis Stop Script - Stops all Jarvis processes

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

JARVIS_HOME="$HOME/.jarvis"
PID_DIR="$JARVIS_HOME/pids"
MENUBAR_LABEL="com.jarvis.menubar"
DAEMON_LABEL="com.jarvis.daemon"

echo -e "${RED}=== Stopping Jarvis ===${NC}"
echo ""

# Function to kill process by PID file
kill_process() {
    local name=$1
    local pid_file="$PID_DIR/$2.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}◆ Stopping $name (PID: $pid)...${NC}"
            kill "$pid" 2>/dev/null || true
            # Wait up to 5 seconds
            for i in {1..10}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 0.5
            done
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    else
        echo -e "${GREEN}✓ No $name PID file found${NC}"
    fi
}

# Stop in reverse order: menu bar, daemon, tunnel
kill_process "Menu Bar" "menubar"
kill_process "Daemon" "daemon"
kill_process "Tunnel" "tunnel"

# Unload launchd agent for menu bar app (if present)
launchctl bootout "gui/$(id -u)/$MENUBAR_LABEL" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/$DAEMON_LABEL" 2>/dev/null || true

# Also kill any remaining processes by name
echo ""
echo -e "${RED}◆ Cleaning up any remaining processes...${NC}"

# Kill any localtunnel processes
pkill -f "localtunnel.*jarvis-voice" 2>/dev/null || true

# Kill any jarvis daemon processes
pkill -f "jarvis.*daemon" 2>/dev/null || true

# Kill any JarvisApp processes
pkill -f "JarvisApp" 2>/dev/null || true

# Kill any Python jarvis processes
pkill -f "python.*jarvis" 2>/dev/null || true

# Kill log viewer terminals started by start-jarvis.sh
pkill -f "bash $PID_DIR/log_viewer.sh" 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ Jarvis stopped${NC}"
