#!/bin/bash
# Jarvis Startup Script - Starts daemon, menu bar app, and tunnel

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

JARVIS_DIR="/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac"
JARVIS_HOME="$HOME/.jarvis"
PID_DIR="$JARVIS_HOME/pids"
LOG_DIR="$JARVIS_HOME/logs"

# Create directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

cd "$JARVIS_DIR"

echo -e "${BLUE}=== Jarvis Startup ===${NC}"
echo ""

# Kill any processes on our ports first
echo -e "${YELLOW}◆ Checking for existing processes on ports 9847, 9848...${NC}"
for port in 9847 9848; do
    PID=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}  Killing process on port $port (PID: $PID)${NC}"
        kill -9 $PID 2>/dev/null || true
    fi
done

# Load environment variables
if [ -f "$JARVIS_HOME/.env" ]; then
    export $(grep -v '^#' "$JARVIS_HOME/.env" | xargs)
fi

export JARVIS_API_TOKEN="${JARVIS_API_TOKEN:-jarvis-voice-token}"
export ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-sk_c9df0f18a3a688f08f7ba6cfd36c5c97f4c45340b8e236fb}"
export ELEVENLABS_AGENT_ID="${ELEVENLABS_AGENT_ID:-agent_0901kgpfery0e3695pj6p7dejngy}"

# Check if already running
if [ -f "$PID_DIR/tunnel.pid" ] && kill -0 $(cat "$PID_DIR/tunnel.pid") 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Tunnel already running (PID: $(cat "$PID_DIR/tunnel.pid"))${NC}"
else
    # Start localtunnel for webhooks
    echo -e "${GREEN}▶ Starting tunnel on port 9848...${NC}"
    nohup npx localtunnel --port 9848 --subdomain jarvis-voice \
        > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    echo $TUNNEL_PID > "$PID_DIR/tunnel.pid"
    echo "  Tunnel PID: $TUNNEL_PID"
    sleep 2
fi

if [ -f "$PID_DIR/daemon.pid" ] && kill -0 $(cat "$PID_DIR/daemon.pid") 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Daemon already running (PID: $(cat "$PID_DIR/daemon.pid"))${NC}"
else
    # Start Jarvis daemon in background
    echo -e "${GREEN}▶ Starting Jarvis daemon...${NC}"
    cd "$JARVIS_DIR" && python3 -m jarvis.daemon \
        > "$LOG_DIR/daemon.log" 2>&1 &
    DAEMON_PID=$!
    echo $DAEMON_PID > "$PID_DIR/daemon.pid"
    echo "  Daemon PID: $DAEMON_PID"
    sleep 2
fi

if [ -f "$PID_DIR/menubar.pid" ] && kill -0 $(cat "$PID_DIR/menubar.pid") 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Menu bar already running (PID: $(cat "$PID_DIR/menubar.pid"))${NC}"
else
    # Start menu bar app
    echo -e "${GREEN}▶ Starting menu bar app...${NC}"
    nohup swift run --package-path JarvisApp \
        > "$LOG_DIR/menubar.log" 2>&1 &
    MENUBAR_PID=$!
    echo $MENUBAR_PID > "$PID_DIR/menubar.pid"
    echo "  Menu bar PID: $MENUBAR_PID"
fi

echo ""
echo -e "${GREEN}✓ Jarvis is running!${NC}"
echo ""

# Open log viewer terminal
echo -e "${BLUE}◆ Opening log viewer terminal...${NC}"

# Create a script for the log viewer terminal
cat > "$PID_DIR/log_viewer.sh" << 'EOF'
#!/bin/bash
LOG_DIR="$HOME/.jarvis/logs"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}=== Jarvis Log Viewer ===${NC}"
echo -e "${YELLOW}Press Ctrl+C to close log viewer (Jarvis continues running)${NC}"
echo ""

# Use temp files to track line counts (bash 3.2 compatible)
COUNT_DIR="$HOME/.jarvis/pids"
mkdir -p "$COUNT_DIR"
daemon_count_file="$COUNT_DIR/daemon_lines.count"
menubar_count_file="$COUNT_DIR/menubar_lines.count"
tunnel_count_file="$COUNT_DIR/tunnel_lines.count"

# Function to get/set line count
get_count() { cat "$1" 2>/dev/null || echo 0; }
set_count() { echo "$1" > "$2"; }

# Function to color output
color_line() {
    local line="$1"
    local log_name="$2"
    if echo "$line" | grep -qi "error\|exception\|failed\|fatal"; then
        echo -e "${RED}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "warn\|warning"; then
        echo -e "${YELLOW}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "info"; then
        echo -e "${GREEN}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "task.*complete\|success\|finished"; then
        echo -e "${CYAN}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "task.*start\|starting\|running"; then
        echo -e "${BLUE}[${log_name}]${NC} $line"
    else
        echo -e "[${log_name}] $line"
    fi
}

# Show existing content
echo -e "${BLUE}--- Existing log content ---${NC}"
for log_name in daemon menubar tunnel; do
    log_file="$LOG_DIR/${log_name}.log"
    if [ -f "$log_file" ]; then
        lines=$(wc -l < "$log_file" 2>/dev/null || echo 0)
        if [ "$lines" -gt 0 ]; then
            echo -e "${BLUE}>>> ${log_name}.log (${lines} lines) <<<${NC}"
            while IFS= read -r line; do
                color_line "$line" "${log_name}"
            done < "$log_file"
            # Save initial count
            set_count "$lines" "$COUNT_DIR/${log_name}_lines.count"
        fi
    fi
done

echo -e "${BLUE}--- Monitoring for new logs (Ctrl+C to stop) ---${NC}"
echo ""

# Monitor loop
while true; do
    for log_name in daemon menubar tunnel; do
        log_file="$LOG_DIR/${log_name}.log"
        count_file="$COUNT_DIR/${log_name}_lines.count"

        if [ -f "$log_file" ]; then
            current_lines=$(wc -l < "$log_file")
            old_lines=$(get_count "$count_file")

            if [ "$current_lines" -gt "$old_lines" ]; then
                # Show new lines
                tail -n +"$((old_lines + 1))" "$log_file" 2>/dev/null | while IFS= read -r line; do
                    color_line "$line" "${log_name}"
                done
                set_count "$current_lines" "$count_file"
            fi
        fi
    done
    sleep 0.5
done
EOF

chmod +x "$PID_DIR/log_viewer.sh"

# Open new Terminal window with the log viewer
osascript << EOF
tell application "Terminal"
    activate
    set newTab to do script "bash $PID_DIR/log_viewer.sh"
    set custom title of newTab to "Jarvis Logs"
end tell
EOF

sleep 1

echo ""
echo "Logs: $LOG_DIR/"
echo "To stop: ./stop-jarvis.sh"
