#!/bin/bash
# Jarvis Startup Script - Starts daemon, menu bar app, and tunnel

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

JARVIS_DIR="/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac"
JARVIS_HOME="$HOME/.jarvis"
PID_DIR="$JARVIS_HOME/pids"
LOG_DIR="$JARVIS_HOME/logs"
LOCK_FILE="$PID_DIR/start.lock"
MENUBAR_BIN="$JARVIS_DIR/JarvisApp/.build/debug/JarvisApp"
MENUBAR_LABEL="com.jarvis.menubar"
MENUBAR_AGENT_PLIST="$HOME/Library/LaunchAgents/${MENUBAR_LABEL}.plist"
DAEMON_LABEL="com.jarvis.daemon"
DAEMON_AGENT_PLIST="$HOME/Library/LaunchAgents/${DAEMON_LABEL}.plist"
DAEMON_WRAPPER="$PID_DIR/run_jarvis_daemon.sh"

STARTED_TUNNEL_PID=""
STARTED_DAEMON_PID=""
STARTED_MENUBAR_PID=""
STARTUP_OK=0

# Create directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

cd "$JARVIS_DIR"

# Prefer project venv python when available so `jarvis` module resolves consistently.
if [ -x "$JARVIS_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$JARVIS_DIR/.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

cleanup_on_error() {
    rm -f "$LOCK_FILE" 2>/dev/null || true
    if [ "$STARTUP_OK" -eq 1 ]; then
        return
    fi
    echo "Startup failed. Cleaning up processes started in this run..."
    for pid in "$STARTED_MENUBAR_PID" "$STARTED_DAEMON_PID" "$STARTED_TUNNEL_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup_on_error EXIT

is_pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_pid() {
    local pid_file="$1"
    local pid="$2"
    echo "$pid" > "$pid_file"
}

safe_kill_pid() {
    local pid="$1"
    if ! is_pid_alive "$pid"; then
        return 0
    fi
    kill "$pid" 2>/dev/null || true
    sleep 1
    if is_pid_alive "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
    fi
}

wait_for_port_listen() {
    local port="$1"
    local timeout_seconds="${2:-15}"
    local elapsed=0
    while [ "$elapsed" -lt "$timeout_seconds" ]; do
        if lsof -n -P -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

print_failure_log_tail() {
    local log_file="$1"
    local label="$2"
    if [ -f "$log_file" ]; then
        echo -e "${YELLOW}--- Last ${label} log lines ---${NC}"
        tail -n 80 "$log_file" || true
    fi
}

verify_service_started() {
    local service_name="$1"
    local pid="$2"
    local log_file="$3"
    local port="$4"

    if ! is_pid_alive "$pid"; then
        echo "❌ ${service_name} failed: process exited immediately (PID ${pid})"
        print_failure_log_tail "$log_file" "$service_name"
        exit 1
    fi

    if [ -n "$port" ] && ! wait_for_port_listen "$port" 20; then
        echo "❌ ${service_name} failed: port ${port} did not become ready"
        print_failure_log_tail "$log_file" "$service_name"
        exit 1
    fi
}

write_menubar_launch_agent() {
    mkdir -p "$(dirname "$MENUBAR_AGENT_PLIST")"
    cat > "$MENUBAR_AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$MENUBAR_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$MENUBAR_BIN</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$JARVIS_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/menubar.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/menubar.log</string>
</dict>
</plist>
EOF
}

write_daemon_launch_agent() {
    mkdir -p "$(dirname "$DAEMON_AGENT_PLIST")"
    cat > "$DAEMON_WRAPPER" <<EOF
#!/bin/bash
set -euo pipefail
cd "$JARVIS_DIR"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\${PATH:-}"
if [ -f "$JARVIS_HOME/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$JARVIS_HOME/.env"
  set +a
fi
exec env PYTHONPATH="$JARVIS_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}" "$PYTHON_BIN" -m jarvis.daemon
EOF
    chmod +x "$DAEMON_WRAPPER"

    cat > "$DAEMON_AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$DAEMON_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DAEMON_WRAPPER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$JARVIS_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daemon.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daemon.log</string>
</dict>
</plist>
EOF
}

start_daemon_with_launchctl() {
    write_daemon_launch_agent
    local gui_domain="gui/$(id -u)"

    launchctl bootout "$gui_domain/$DAEMON_LABEL" >/dev/null 2>&1 || true
    launchctl bootstrap "$gui_domain" "$DAEMON_AGENT_PLIST"
    launchctl kickstart -k "$gui_domain/$DAEMON_LABEL" >/dev/null 2>&1 || true

    local pid
    pid="$(launchctl print "$gui_domain/$DAEMON_LABEL" 2>/dev/null | awk -F'= ' '/pid = / {gsub(/;/, "", $2); print $2; exit}')"
    if [ -n "${pid:-}" ]; then
        write_pid "$PID_DIR/daemon.pid" "$pid"
        echo "  Daemon PID: $pid"
        STARTED_DAEMON_PID="$pid"
    else
        echo "❌ Daemon failed: launchctl did not report a running PID"
        print_failure_log_tail "$LOG_DIR/daemon.log" "Daemon"
        exit 1
    fi
}

start_menubar_with_launchctl() {
    write_menubar_launch_agent
    local gui_domain="gui/$(id -u)"

    launchctl bootout "$gui_domain/$MENUBAR_LABEL" >/dev/null 2>&1 || true
    launchctl bootstrap "$gui_domain" "$MENUBAR_AGENT_PLIST"
    launchctl kickstart -k "$gui_domain/$MENUBAR_LABEL" >/dev/null 2>&1 || true

    local pid
    pid="$(launchctl print "$gui_domain/$MENUBAR_LABEL" 2>/dev/null | awk -F'= ' '/pid = / {gsub(/;/, "", $2); print $2; exit}')"
    if [ -n "${pid:-}" ]; then
        write_pid "$PID_DIR/menubar.pid" "$pid"
        echo "  Menu bar PID: $pid"
        STARTED_MENUBAR_PID="$pid"
    else
        echo "❌ Menu bar app failed: launchctl did not report a running PID"
        print_failure_log_tail "$LOG_DIR/menubar.log" "Menu bar app"
        exit 1
    fi
}

echo -e "${BLUE}=== Jarvis Startup ===${NC}"
echo ""

mkdir -p "$PID_DIR" "$LOG_DIR"
if [ -e "$LOCK_FILE" ]; then
    existing_lock_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [ -n "$existing_lock_pid" ] && is_pid_alive "$existing_lock_pid"; then
        echo "Another startup is already in progress (PID: $existing_lock_pid)"
        exit 1
    fi
fi
write_pid "$LOCK_FILE" "$$"

# Kill any processes on our ports first
echo -e "${YELLOW}◆ Checking for existing processes on ports 9847, 9848...${NC}"
for port in 9847 9848; do
    PID=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}  Killing process on port $port (PID: $PID)${NC}"
        for p in $PID; do
            safe_kill_pid "$p"
        done
    fi
done

# Load environment variables
if [ -f "$JARVIS_HOME/.env" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$JARVIS_HOME/.env"
    set +a
fi

export JARVIS_API_TOKEN="${JARVIS_API_TOKEN:-jarvis-voice-token}"
export ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}"
export ELEVENLABS_AGENT_ID="${ELEVENLABS_AGENT_ID:-}"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${ANTHROPIC_DEFAULT_OPUS_MODEL:-glm-4.7}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${ANTHROPIC_DEFAULT_SONNET_MODEL:-glm-4.7}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-glm-4.7}"

# Check if already running
if [ -f "$PID_DIR/tunnel.pid" ] && is_pid_alive "$(cat "$PID_DIR/tunnel.pid")"; then
    echo -e "${YELLOW}⚠️  Tunnel already running (PID: $(cat "$PID_DIR/tunnel.pid"))${NC}"
else
    # Start localtunnel for webhooks
    echo -e "${GREEN}▶ Starting tunnel on port 9848...${NC}"
    nohup npx localtunnel --port 9848 --subdomain jarvis-voice \
        > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    STARTED_TUNNEL_PID="$TUNNEL_PID"
    write_pid "$PID_DIR/tunnel.pid" "$TUNNEL_PID"
    echo "  Tunnel PID: $TUNNEL_PID"
    sleep 2
    verify_service_started "Tunnel" "$TUNNEL_PID" "$LOG_DIR/tunnel.log" ""
fi

if [ -f "$PID_DIR/daemon.pid" ] && is_pid_alive "$(cat "$PID_DIR/daemon.pid")"; then
    echo -e "${YELLOW}⚠️  Daemon already running (PID: $(cat "$PID_DIR/daemon.pid"))${NC}"
else
    # Start Jarvis daemon in background
    echo -e "${GREEN}▶ Starting Jarvis daemon...${NC}"
    cd "$JARVIS_DIR"
    start_daemon_with_launchctl
    verify_service_started "Daemon" "$(cat "$PID_DIR/daemon.pid")" "$LOG_DIR/daemon.log" "9847"
fi

if [ -f "$PID_DIR/menubar.pid" ] && is_pid_alive "$(cat "$PID_DIR/menubar.pid")"; then
    echo -e "${YELLOW}⚠️  Menu bar already running (PID: $(cat "$PID_DIR/menubar.pid"))${NC}"
else
    # Start menu bar app
    echo -e "${GREEN}▶ Starting menu bar app...${NC}"
    if [ ! -x "$MENUBAR_BIN" ]; then
        swift build --package-path JarvisApp >> "$LOG_DIR/menubar.log" 2>&1
    fi
    start_menubar_with_launchctl
    sleep 2
    verify_service_started "Menu bar app" "$(cat "$PID_DIR/menubar.pid")" "$LOG_DIR/menubar.log" ""
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

# Open a single Terminal log viewer instance (avoid duplicate tabs/windows)
if pgrep -f "bash $PID_DIR/log_viewer.sh" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Log viewer already running; reusing existing terminal${NC}"
elif command -v osascript >/dev/null 2>&1; then
    osascript << EOF
tell application "Terminal"
    activate
    set newTab to do script "bash $PID_DIR/log_viewer.sh"
    set custom title of newTab to "Jarvis Logs"
end tell
EOF
else
    echo -e "${YELLOW}⚠️  osascript not available; skipping log viewer terminal auto-open${NC}"
fi

sleep 1

echo ""
echo "Logs: $LOG_DIR/"
echo "To stop: ./stop-jarvis.sh"

STARTUP_OK=1
rm -f "$LOCK_FILE"
